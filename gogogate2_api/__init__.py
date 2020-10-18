"""Base package for gate API code."""
import abc
import base64
from hashlib import sha1
import json
import secrets
import time
from typing import Any, Dict, Generic, Optional, Tuple, TypeVar, Union, cast
import uuid
from xml.etree.ElementTree import Element  # nosec

from Crypto.Cipher import AES  # nosec
from Crypto.Cipher._mode_cbc import CbcMode  # nosec
from defusedxml import ElementTree
import httpx
from typing_extensions import Final

from .common import (
    AbstractDoor,
    ApiError,
    CredentialsIncorrectException,
    CredentialsNotSetException,
    DoorNotSetException,
    DoorStatus,
    ExceptionGenerator,
    GogoGate2ActivateResponse,
    GogoGate2InfoResponse,
    InvalidApiCodeException,
    InvalidOptionException,
    ISmartGateActivateResponse,
    ISmartGateDoor,
    ISmartGateInfoResponse,
    RequestOption,
    assumed_state_to_door_status,
    element_to_api_error,
    element_to_gogogate2_activate_response,
    element_to_gogogate2_info_response,
    element_to_ismartgate_activate_response,
    element_to_ismartgate_info_response,
    get_door_by_id,
)
from .const import (
    TRANSITION_COMPLETE_DURATION,
    GogoGate2ApiErrorCode,
    ISmartGateApiErrorCode,
)

DEFAULT_TIMEOUT = 20


class ApiCipher:
    """AES/CBC/PKCS5Padding algorithm."""

    def __init__(self, key: str) -> None:
        """Initialize the object."""
        self._key: Final[str] = key
        self._key_bytes: Final[bytes] = key.encode("utf-8")

    def encrypt(self, content: str, init_vector: Optional[str] = None) -> str:
        """Encrypt content."""
        init_vector_bytes: Final[bytes] = ApiCipher.pad_pkcs5(
            init_vector or uuid.uuid4().hex
        ).encode("utf-8")[: AES.block_size]
        content_bytes: Final[bytes] = ISmartGateApiCipher.pad_pkcs5(content).encode(
            "utf-8"
        )
        cipher: Final[CbcMode] = cast(
            CbcMode, AES.new(self._key_bytes, AES.MODE_CBC, init_vector_bytes)
        )
        encrypted_bytes: Final[bytes] = cipher.encrypt(content_bytes)
        return str(init_vector_bytes + base64.b64encode(encrypted_bytes), "utf-8")

    def decrypt(self, content: str) -> str:
        """Decrypt content."""
        init_vector: Final[bytes] = content.encode("utf-8")[: AES.block_size]
        encrypted_bytes: Final[bytes] = base64.b64decode(content[AES.block_size :])
        cipher: Final[CbcMode] = cast(
            CbcMode, AES.new(self._key_bytes, AES.MODE_CBC, init_vector)
        )
        return ApiCipher.unpad_pkcs5(cipher.decrypt(encrypted_bytes)).decode("utf-8")

    @staticmethod
    def pad_pkcs5(data: str) -> str:
        """Add padding to bytes."""
        block_size: Final[int] = AES.block_size
        return data + (block_size - len(data) % block_size) * chr(
            block_size - len(data) % block_size
        )

    @staticmethod
    def unpad_pkcs5(data: bytes) -> bytes:
        """Remove padding from bytes."""
        return data[0 : -data[-1]]


class GogoGate2ApiCipher(ApiCipher):
    """Cipher for GogoGate2 devices."""

    SHARED_SECRET: Final[str] = "0e3b7%i1X9@54cAf"

    def __init__(self) -> None:
        """Initialize the object."""
        super().__init__(GogoGate2ApiCipher.SHARED_SECRET)


class ISmartGateApiCipher(ApiCipher):
    """Cipher for iSmartGate devices."""

    RAW_TOKEN_FORMAT: Final[str] = "%s@ismartgate"

    def __init__(self, username: str, password: str) -> None:
        """Initialize the object."""
        self._username: Final[str] = username
        self._password: Final[str] = password

        # Calculate the token.
        raw_token: Final[str] = (
            ISmartGateApiCipher.RAW_TOKEN_FORMAT % self._username.lower()
        )
        self._token: Final[str] = sha1(raw_token.encode("utf-8")).hexdigest()  # nosec

        # Calculate the key and pass it onto the superclass.
        sha1_hex_str: Final[str] = sha1(  # nosec
            (self._username.lower() + self._password).encode()
        ).hexdigest()

        super().__init__(
            f"{sha1_hex_str[32:36]}a{sha1_hex_str[7:10]}!{sha1_hex_str[18:21]}*#{sha1_hex_str[24:26]}"
        )

    @property
    def token(self) -> str:
        """Get the token."""
        return self._token


ApiCipherType = TypeVar(
    "ApiCipherType", bound=Union[GogoGate2ApiCipher, ISmartGateApiCipher]
)
InfoResponseType = TypeVar(
    "InfoResponseType", bound=Union[GogoGate2InfoResponse, ISmartGateInfoResponse]
)
ActivateResponseType = TypeVar(
    "ActivateResponseType",
    bound=Union[GogoGate2ActivateResponse, ISmartGateActivateResponse],
)


class AbstractGateApi(  # pylint: disable=too-many-instance-attributes
    Generic[ApiCipherType, InfoResponseType, ActivateResponseType], abc.ABC
):
    """API capable of communicating with a gogogate2 devices."""

    API_URL_TEMPLATE: Final[str] = "http://%s/api.php"

    def __init__(
        self,
        host: str,
        username: str,
        password: str,
        api_cipher: ApiCipherType,
        timeout: Optional[int] = DEFAULT_TIMEOUT,
    ) -> None:
        """Initialize the object."""
        self._host: Final[str] = host
        self._username: Final[str] = username
        self._password: Final[str] = password
        self._cipher: Final[ApiCipherType] = api_cipher
        self._timeout = timeout or DEFAULT_TIMEOUT
        self._api_url: Final[str] = AbstractGateApi.API_URL_TEMPLATE % host
        self._assumed_door_status: Dict[int, Tuple[float, DoorStatus]] = {}
        self._async_client = httpx.AsyncClient()

    @property
    def host(self) -> str:
        """Get the host."""
        return self._host

    @property
    def username(self) -> str:
        """Get the username."""
        return self._username

    @property
    def password(self) -> str:
        """Get the password."""
        return self._password

    @property
    def cipher(self) -> ApiCipherType:
        """Get the cipher."""
        return self._cipher

    def _build_params(
        self,
        option: RequestOption,
        arg1: Optional[str] = None,
        arg2: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Create params for the get request."""
        command_str: Final[str] = json.dumps(
            (
                self._username,
                self._password,
                option.value,
                "" if arg1 is None else arg1,
                "" if arg2 is None else arg2,
            )
        )
        return {
            "url": self._api_url,
            "params": {
                "data": self._cipher.encrypt(command_str),
                **self._get_extra_url_params(),
            },
            "timeout": self._timeout,
        }

    async def _async_request(
        self,
        option: RequestOption,
        arg1: Optional[str] = None,
        arg2: Optional[str] = None,
    ) -> Element:
        response: Final[httpx.Response] = await self._async_client.get(
            **self._build_params(option, arg1, arg2)
        )

        response.raise_for_status()

        return self._parse_response(response)

    def _parse_response(self, response: httpx.Response) -> Element:
        """Parse the response from the device."""
        response_raw: Final[str] = response.content.decode("utf-8")

        try:
            # Error messages are returned unencrypted so we try to decrypt the response.
            # if that fails, then we use what was returned.
            response_text = self._cipher.decrypt(response.content.decode("utf-8"))
        except ValueError:
            response_text = response_raw

        root_element: Final[Element] = ElementTree.fromstring(response_text)

        error_element: Final[Optional[Element]] = root_element.find("error")
        if error_element:
            api_error: Final[ApiError] = element_to_api_error(error_element)
            raise self._get_exception_map().get(api_error.code, ApiError)(
                api_error.code, api_error.message
            )

        return root_element

    @abc.abstractmethod
    async def async_info(self) -> InfoResponseType:
        """Get info about the device and doors."""

    @abc.abstractmethod
    async def async_activate(self, door_id: int) -> ActivateResponseType:
        """Send a command to open/close/stop the door.

        Devices do not have a status for opening or closing. So running
        this method during an action will stop the door. It's recommended you
        use open_door() or close_door() as those methods check the status
        before running and run if needed."""

    @abc.abstractmethod
    def _get_activate_api_code(self, info: InfoResponseType, door_id: int) -> str:
        """Get api code for activate actions."""

    @staticmethod
    @abc.abstractmethod
    def _get_exception_map() -> Dict[int, ExceptionGenerator]:
        """Return a more specific exception."""

    # pylint: disable=no-self-use
    def _get_extra_url_params(self) -> Dict[str, str]:
        return {}

    async def _async_info(self) -> Element:
        """Get info about the device and doors."""
        return await self._async_request(RequestOption.INFO)

    @property
    def _assumed_status(self) -> Dict[int, DoorStatus]:
        """Build a dict of non-expired assumed door status."""
        now = time.time()
        non_expired_assumed_status = {}
        for door_id, assumed_status in self._assumed_door_status.items():
            expire_time, door_status = assumed_status
            if expire_time < now:
                continue
            non_expired_assumed_status[door_id] = door_status

        return non_expired_assumed_status

    async def _async_activate(
        self, door_id: int, info: Optional[InfoResponseType] = None
    ) -> Element:
        """Send a command to open/close/stop the door.

        Gogogate2/iSmartGate do not have a status for opening or closing. So
        running this method during an action will stop the door. It's
        recommended you use open_door() or close_door() as those methods check
        the status before running and run if needed."""
        return await self._async_request(
            RequestOption.ACTIVATE,
            str(door_id),
            self._get_activate_api_code(
                info if info else await self.async_info(), door_id
            ),
        )

    async def _async_set_door_status(
        self, door_id: int, door_status: DoorStatus
    ) -> bool:
        """Send call to open/close a door if door is not already in that state."""
        if door_status == DoorStatus.UNDEFINED:
            return False

        # Get current door status.
        info: Final[InfoResponseType] = await self.async_info()
        door: Final[Optional[AbstractDoor]] = get_door_by_id(door_id, info)

        # No door found or door already at desired status.
        if not door or assumed_state_to_door_status(
            door.status
        ) == assumed_state_to_door_status(door_status):
            return False

        await self._async_activate(door_id, info)
        return True

    def _set_assumed_door_status(self, door_id: int, door_status: DoorStatus) -> None:
        """Set a temporary assumed state for the expected duration."""
        self._assumed_door_status[door_id] = (
            time.time() + TRANSITION_COMPLETE_DURATION,
            door_status,
        )

    async def async_close_door(self, door_id: int) -> bool:
        """Close a door.

        :return True if close command sent, False otherwise.
        """
        response = await self._async_set_door_status(door_id, DoorStatus.CLOSED)
        if response:
            self._set_assumed_door_status(door_id, DoorStatus.CLOSING)
        return response

    async def async_open_door(self, door_id: int) -> bool:
        """Open a door.

        :return True if open command sent, False otherwise.
        """
        response = await self._async_set_door_status(door_id, DoorStatus.OPENED)
        if response:
            self._set_assumed_door_status(door_id, DoorStatus.OPENING)
        return response

    async def async_remove(self) -> None:
        """Remove the object"""
        await self._async_client.aclose()


class ISmartGateApi(
    AbstractGateApi[
        ISmartGateApiCipher, ISmartGateInfoResponse, ISmartGateActivateResponse
    ]
):
    """API for interacting with iSmartGate devices."""

    def __init__(
        self,
        host: str,
        username: str,
        password: str,
        timeout: Optional[int] = DEFAULT_TIMEOUT,
    ) -> None:
        """Initialize the object."""
        super().__init__(
            host,
            username,
            password,
            ISmartGateApiCipher(username, password),
            timeout=timeout,
        )

    async def async_info(self) -> ISmartGateInfoResponse:
        """Get info about the device and doors."""
        return element_to_ismartgate_info_response(
            await self._async_info(), self._assumed_status
        )

    async def async_activate(self, door_id: int) -> ISmartGateActivateResponse:
        """Send a command to open/close/stop the door.

        Devices do not have a status for opening or closing. So running
        this method during an action will stop the door. It's recommended you
        use open_door() or close_door() as those methods check the status
        before running and run if needed."""
        return element_to_ismartgate_activate_response(
            await self._async_activate(door_id)
        )

    #  pylint: disable=no-self-use
    def _get_activate_api_code(self, info: ISmartGateInfoResponse, door_id: int) -> str:
        """Get api code for activate actions."""
        door: Final[Optional[AbstractDoor]] = get_door_by_id(door_id, info)
        if not door:
            raise Exception(f"Door with id {door_id} not found.")

        return cast(ISmartGateDoor, door).apicode

    @staticmethod
    def _get_exception_map() -> Dict[int, ExceptionGenerator]:
        """Return a more specific exception."""
        return {
            ISmartGateApiErrorCode.CREDENTIALS_NOT_SET.value: CredentialsNotSetException,
            ISmartGateApiErrorCode.CREDENTIALS_INCORRECT.value: CredentialsIncorrectException,
            ISmartGateApiErrorCode.INVALID_OPTION.value: InvalidOptionException,
            ISmartGateApiErrorCode.INVALID_API_CODE.value: InvalidApiCodeException,
            ISmartGateApiErrorCode.DOOR_NOT_SET.value: DoorNotSetException,
        }

    def _get_extra_url_params(self) -> Dict[str, str]:
        """Get extra url params when making calls."""
        return {
            "t": str(secrets.randbelow(100000000) + 1),
            "token": self.cipher.token,
        }


class GogoGate2Api(
    AbstractGateApi[
        GogoGate2ApiCipher, GogoGate2InfoResponse, GogoGate2ActivateResponse
    ]
):
    """API for interacting with GogoGate2 devices."""

    def __init__(
        self,
        host: str,
        username: str,
        password: str,
        timeout: Optional[int] = DEFAULT_TIMEOUT,
    ) -> None:
        """Initialize the object."""
        super().__init__(
            host, username, password, GogoGate2ApiCipher(), timeout=timeout
        )

    async def async_info(self) -> GogoGate2InfoResponse:
        """Get info about the device and doors."""
        return element_to_gogogate2_info_response(
            await self._async_info(), self._assumed_status
        )

    async def async_activate(self, door_id: int) -> GogoGate2ActivateResponse:
        """Send a command to open/close/stop the door.

        Devices do not have a status for opening or closing. So running
        this method during an action will stop the door. It's recommended you
        use open_door() or close_door() as those methods check the status
        before running and run if needed."""
        return element_to_gogogate2_activate_response(
            await self._async_activate(door_id)
        )

    @staticmethod
    def _get_exception_map() -> Dict[int, ExceptionGenerator]:
        """Return a more specific exception."""
        return {
            GogoGate2ApiErrorCode.CREDENTIALS_NOT_SET.value: CredentialsNotSetException,
            GogoGate2ApiErrorCode.CREDENTIALS_INCORRECT.value: CredentialsIncorrectException,
            GogoGate2ApiErrorCode.INVALID_OPTION.value: InvalidOptionException,
            GogoGate2ApiErrorCode.INVALID_API_CODE.value: InvalidApiCodeException,
            GogoGate2ApiErrorCode.DOOR_NOT_SET.value: DoorNotSetException,
        }

    # pylint: disable=unused-argument, no-self-use
    def _get_activate_api_code(self, info: GogoGate2InfoResponse, door_id: int) -> str:
        """Get api code for activate actions."""
        return info.apicode
