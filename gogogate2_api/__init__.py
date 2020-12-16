"""Base package for gate API code."""
import abc
import base64
from datetime import datetime, timedelta
from hashlib import sha1
import json
import secrets
from typing import Dict, Generic, Optional, TypeVar, Union, cast
import uuid
from xml.etree.ElementTree import Element  # nosec

from Crypto.Cipher import AES  # nosec
from Crypto.Cipher._mode_cbc import CbcMode  # nosec
from defusedxml import ElementTree
from httpx import AsyncClient
from typing_extensions import Final

from .common import (
    CLOSE_DOOR_STATUSES,
    OPEN_DOOR_STATUSES,
    AllDoorStatus,
    ApiError,
    CachedTransitionDoorStatus,
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
    TransitionDoorStatus,
    element_to_api_error,
    element_to_gogogate2_activate_response,
    element_to_gogogate2_info_response,
    element_to_ismartgate_activate_response,
    element_to_ismartgate_info_response,
    get_configured_doors,
    get_door_by_id,
    InvalidDoorException,
)
from .const import GogoGate2ApiErrorCode, ISmartGateApiErrorCode


class ApiCipher:
    """AES/CBC/PKCS5Padding algorithm."""

    def __init__(self, key: str) -> None:
        """Initialize the object."""
        self._key: Final = key
        self._key_bytes: Final = key.encode("utf-8")

    def encrypt(self, content: str, init_vector: Optional[str] = None) -> str:
        """Encrypt content."""
        init_vector_bytes: Final = ApiCipher.pad_pkcs5(
            init_vector or uuid.uuid4().hex
        ).encode("utf-8")[: AES.block_size]
        content_bytes: Final = ISmartGateApiCipher.pad_pkcs5(content).encode("utf-8")
        cipher: Final = cast(
            CbcMode, AES.new(self._key_bytes, AES.MODE_CBC, init_vector_bytes)
        )
        encrypted_bytes: Final = cipher.encrypt(content_bytes)
        return str(init_vector_bytes + base64.b64encode(encrypted_bytes), "utf-8")

    def decrypt(self, content: str) -> str:
        """Decrypt content."""
        init_vector: Final = content.encode("utf-8")[: AES.block_size]
        encrypted_bytes: Final = base64.b64decode(content[AES.block_size :])
        cipher: Final = cast(
            CbcMode, AES.new(self._key_bytes, AES.MODE_CBC, init_vector)
        )
        return ApiCipher.unpad_pkcs5(cipher.decrypt(encrypted_bytes)).decode("utf-8")

    @staticmethod
    def pad_pkcs5(data: str) -> str:
        """Add padding to bytes."""
        block_size: Final = AES.block_size
        return data + (block_size - len(data) % block_size) * chr(
            block_size - len(data) % block_size
        )

    @staticmethod
    def unpad_pkcs5(data: bytes) -> bytes:
        """Remove padding from bytes."""
        return data[0 : -data[-1]]


class GogoGate2ApiCipher(ApiCipher):
    """Cipher for GogoGate2 devices."""

    SHARED_SECRET: Final = "0e3b7%i1X9@54cAf"

    def __init__(self) -> None:
        """Initialize the object."""
        super().__init__(GogoGate2ApiCipher.SHARED_SECRET)


class ISmartGateApiCipher(ApiCipher):
    """Cipher for iSmartGate devices."""

    RAW_TOKEN_FORMAT: Final = "%s@ismartgate"

    def __init__(self, username: str, password: str) -> None:
        """Initialize the object."""
        self._username: Final = username
        self._password: Final = password

        # Calculate the token.
        raw_token: Final[
            str
        ] = ISmartGateApiCipher.RAW_TOKEN_FORMAT % self._username.lower()
        self._token: Final = sha1(raw_token.encode("utf-8")).hexdigest()  # nosec

        # Calculate the key and pass it onto the superclass.
        sha1_hex_str: Final = sha1(  # nosec
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


# pylint: disable=too-many-instance-attributes
class AbstractGateApi(
    Generic[ApiCipherType, InfoResponseType, ActivateResponseType], abc.ABC
):
    """API capable of communicating with a gogogate2 devices."""

    API_URL_TEMPLATE: Final = "http://%s/api.php"
    DEFAULT_REQUEST_TIMEOUT = timedelta(seconds=20)
    DEFAULT_TRANSITION_STATUS_TIMEOUT = timedelta(seconds=55)

    def __init__(
        self,
        host: str,
        username: str,
        password: str,
        api_cipher: ApiCipherType,
        request_timeout: timedelta = DEFAULT_REQUEST_TIMEOUT,
        transition_status_timeout: timedelta = DEFAULT_TRANSITION_STATUS_TIMEOUT,
    ) -> None:
        """Initialize the object."""
        self._host: Final = host
        self._username: Final = username
        self._password: Final = password
        self._cipher: Final = api_cipher
        self._request_timeout: Final = request_timeout
        self._transition_status_timeout: Final = transition_status_timeout
        self._api_url: Final = AbstractGateApi.API_URL_TEMPLATE % host
        self._transition_door_status: Final[Dict[int, CachedTransitionDoorStatus]] = {}

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

    async def _async_request(
        self,
        option: RequestOption,
        arg1: Optional[str] = None,
        arg2: Optional[str] = None,
    ) -> Element:
        command_str: Final = json.dumps(
            (
                self._username,
                self._password,
                option.value,
                "" if arg1 is None else arg1,
                "" if arg2 is None else arg2,
            )
        )

        async with AsyncClient() as client:
            response: Final = await client.get(
                self._api_url,
                params={
                    "data": self._cipher.encrypt(command_str),
                    **self._get_extra_url_params(),
                },
                timeout=self._request_timeout.seconds,
            )
        response_raw: Final = response.content.decode("utf-8")

        try:
            # Error messages are returned unencrypted so we try to decrypt the response.
            # if that fails, then we use what was returned.
            response_text = self._cipher.decrypt(response_raw)
        except ValueError:
            response_text = response_raw

        root_element: Final = ElementTree.fromstring(response_text)

        error_element: Final = root_element.find("error")
        if error_element:
            api_error: Final = element_to_api_error(error_element)
            raise self._get_exception_map().get(api_error.code, ApiError)(
                api_error.code, api_error.message
            )

        return cast(Element, root_element)

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
        self,
        door_id: int,
        target_door_status: DoorStatus,
        consider_transitional_states: bool = True,
    ) -> bool:
        """Send call to open/close a door if door is not already in that state."""
        if target_door_status == DoorStatus.UNDEFINED:
            return False

        # Get current door status.
        info: Final = await self.async_info()
        statuses: Final = self._get_door_statuses(
            info, use_transitional_status=consider_transitional_states
        )
        current_door_status: Final = statuses.get(door_id)
        result_door_statuses: Final = OPEN_DOOR_STATUSES if target_door_status == DoorStatus.OPENED else CLOSE_DOOR_STATUSES
        transitional_door_status: Final = TransitionDoorStatus.OPENING if target_door_status == DoorStatus.OPENED else TransitionDoorStatus.CLOSING

        # Door is invalid, not configured, already in desired state or transitioning to it.
        if not current_door_status or current_door_status in result_door_statuses:
            return False

        await self._async_activate(door_id, info)

        # Set the transitional status.
        self._transition_door_status[door_id] = CachedTransitionDoorStatus(
            door_id=door_id,
            activated=datetime.utcnow(),
            transition_status=transitional_door_status,
            target_status=target_door_status,
        )

        return True

    async def async_close_door(
        self, door_id: int, consider_transitional_states: bool = True
    ) -> bool:
        """Close a door.

        :return True if close command sent, False otherwise.
        """
        return await self._async_set_door_status(
            door_id,
            DoorStatus.CLOSED,
            consider_transitional_states=consider_transitional_states,
        )

    async def async_open_door(
        self, door_id: int, consider_transitional_states: bool = True
    ) -> bool:
        """Open a door.

        :return True if open command sent, False otherwise.
        """
        return await self._async_set_door_status(
            door_id,
            DoorStatus.OPENED,
            consider_transitional_states=consider_transitional_states,
        )

    def _get_door_statuses(
        self, info: InfoResponseType, use_transitional_status: bool = True
    ) -> Dict[int, AllDoorStatus]:
        doors: Final = get_configured_doors(info)

        # Clean out the cache.
        for (cached_door_id, cached_transitional_status,) in list(
            self._transition_door_status.items()
        ):
            if (
                datetime.utcnow() - cached_transitional_status.activated
                >= self._transition_status_timeout
            ):
                del self._transition_door_status[cached_door_id]

        # For each door, determine the status.
        result: Final[Dict[int, AllDoorStatus]] = {}
        for door in doors:
            transitional_status = self._transition_door_status.get(door.door_id)
            if (
                use_transitional_status
                and transitional_status
                and transitional_status.target_status != door.status
            ):
                result[door.door_id] = transitional_status.transition_status
            else:
                result[door.door_id] = door.status

        return result

    async def async_get_door_statuses(
        self, use_transitional_status: bool = True
    ) -> Dict[int, AllDoorStatus]:
        """Get configured door statuses."""
        return self._get_door_statuses(
            await self.async_info(), use_transitional_status=use_transitional_status
        )


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
        request_timeout: timedelta = AbstractGateApi.DEFAULT_REQUEST_TIMEOUT,
        transition_status_timeout: timedelta = AbstractGateApi.DEFAULT_TRANSITION_STATUS_TIMEOUT,
    ) -> None:
        """Initialize the object."""
        super().__init__(
            host,
            username,
            password,
            ISmartGateApiCipher(username, password),
            request_timeout=request_timeout,
            transition_status_timeout=transition_status_timeout,
        )

    async def async_info(self) -> ISmartGateInfoResponse:
        """Get info about the device and doors."""
        return element_to_ismartgate_info_response(await self._async_info())

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
        door: Final = get_door_by_id(door_id, info)
        if not door:
            raise InvalidDoorException(door_id)

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
        request_timeout: timedelta = AbstractGateApi.DEFAULT_REQUEST_TIMEOUT,
        transition_status_timeout: timedelta = AbstractGateApi.DEFAULT_TRANSITION_STATUS_TIMEOUT,
    ) -> None:
        """Initialize the object."""
        super().__init__(
            host,
            username,
            password,
            GogoGate2ApiCipher(),
            request_timeout=request_timeout,
            transition_status_timeout=transition_status_timeout,
        )

    async def async_info(self) -> GogoGate2InfoResponse:
        """Get info about the device and doors."""
        return element_to_gogogate2_info_response(await self._async_info())

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
