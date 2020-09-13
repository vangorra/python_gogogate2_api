"""Common test code."""
import abc
import json
from typing import Any, Dict, Generic, List, Optional, Tuple, TypeVar, Union
from urllib.parse import parse_qs, urlparse
from xml.dom.minidom import parseString

import dicttoxml
from gogogate2_api import AbstractGateApi, ApiCipher, ISmartGateApiCipher
from gogogate2_api.common import (
    DoorMode,
    DoorStatus,
    EnhancedJSONEncoder,
    GogoGate2Door,
    GogoGate2InfoResponse,
    ISmartGateDoor,
    ISmartGateInfoResponse,
    Network,
    Outputs,
    RequestOption,
    RestrictedAccessException,
    ServicePath,
    Wifi,
    int_or_none,
)
from gogogate2_api.const import (
    LOGIN_FORM_BUTTON,
    LOGIN_FORM_PASSWORD,
    LOGIN_FORM_USER,
    NONE_INT,
    GogoGate2ApiErrorCode,
    ISmartGateApiErrorCode,
)
import responses
from typing_extensions import Final

MockInfoResponse = TypeVar(
    "MockInfoResponse", bound=Union[GogoGate2InfoResponse, ISmartGateInfoResponse]
)


# pylint: disable=too-many-instance-attributes
class AbstractMockServer(Generic[MockInfoResponse], abc.ABC):
    """Mock server."""

    def __init__(
        self,
        api: AbstractGateApi,
        api_code: str = "api_code1",
        host: Optional[str] = None,
        username: Optional[str] = None,
        password: Optional[str] = None,
    ):
        """Init object."""
        self.host: Final[str] = host or api.host
        self.username: Final[str] = username or api.username
        self.password: Final[str] = password or api.password
        self.api_code: Final[str] = api_code
        self.http_status: Final[int] = 200
        self.cipher: Final[ApiCipher] = api.cipher
        self._info_data: dict = json.loads(
            json.dumps(self._get_info_data(), indent=2, cls=EnhancedJSONEncoder)
        )
        self._temp_data: Dict[int, Tuple[str, str]] = {
            1: (str(23456), str(NONE_INT)),
            2: (str(NONE_INT), str(20)),
            3: ("", ""),
        }
        self._is_web_authenticated: bool = False

        responses.reset()
        responses.add_callback(
            responses.GET,
            AbstractGateApi.service_url(self.host, ServicePath.API),
            callback=self._handle_api_get,
        )
        responses.add_callback(
            responses.GET,
            AbstractGateApi.service_url(self.host, ServicePath.INDEX),
            callback=self._handle_index_get,
        )
        responses.add_callback(
            responses.POST,
            AbstractGateApi.service_url(self.host, ServicePath.INDEX),
            callback=self._handle_index_post,
        )
        responses.add_callback(
            responses.GET,
            AbstractGateApi.service_url(self.host, ServicePath.ISG_TEMPERATURE),
            callback=self._handle_isg_temperature_get,
        )

    @abc.abstractmethod
    def _get_info_data(self) -> MockInfoResponse:
        pass

    @abc.abstractmethod
    def _get_error_corrupted_data_response(self) -> tuple:
        pass

    @abc.abstractmethod
    def _get_error_token_not_set_response(self) -> tuple:
        pass

    @abc.abstractmethod
    def _get_error_invalid_token_response(self) -> tuple:
        pass

    @abc.abstractmethod
    def _get_error_absent_credentials_response(self) -> tuple:
        pass

    @abc.abstractmethod
    def _get_error_invalid_credentials_response(self) -> tuple:
        pass

    @abc.abstractmethod
    def _get_error_invalid_option_response(self) -> tuple:
        pass

    @abc.abstractmethod
    def _get_error_activate_invalid_api_code_response(self) -> tuple:
        pass

    @abc.abstractmethod
    def _get_error_activate_door_id_not_set_response(self) -> tuple:
        pass

    @abc.abstractmethod
    def _get_error_activate_invalid_door_response(self) -> tuple:
        pass

    def set_device_status(self, door_id: int, door_status: DoorStatus) -> None:
        """Set the status of a device."""
        self._info_data[f"door{door_id}"]["status"] = door_status.value

    def _handle_index_get(
        self, request: Any  # pylint: disable=unused-argument
    ) -> tuple:
        self._is_web_authenticated = False
        return (200, {}, "This always returns HTML with a HTTP 200 status code.")

    def _handle_index_post(self, request: Any) -> tuple:
        self._is_web_authenticated = False

        data: Final[dict] = parse_qs(request.body)
        if (
            LOGIN_FORM_USER in data
            and LOGIN_FORM_PASSWORD in data
            and LOGIN_FORM_BUTTON in data
        ):
            self._is_web_authenticated = (
                data[LOGIN_FORM_USER][0] == self.username
                and data[LOGIN_FORM_PASSWORD][0] == self.password
            )

        return (200, {}, "This always returns HTML with a HTTP 200 status code.")

    def _handle_isg_temperature_get(self, request: Any) -> tuple:
        if not self._is_web_authenticated:
            return (200, {}, RestrictedAccessException.RESPONSE_ERROR)

        query: Final[dict] = parse_qs(urlparse(request.url).query)
        door_id = int_or_none(query.get("door", ["0"])[0])
        if door_id is None or door_id < 1 or door_id > 3:
            return (200, {}, "")

        return (200, {}, json.dumps(self._temp_data[door_id]))

    # pylint: disable=too-many-return-statements
    def _handle_api_get(self, request: Any) -> tuple:
        # Simulate an HTTP error.
        if self.http_status != 200:
            return self._new_response("")

        # Parse the request.
        query: Final[dict] = parse_qs(urlparse(request.url).query)
        data: Final[str] = query["data"][0]

        try:
            decrypted: Final[str] = self.cipher.decrypt(data)
            payload: Final[List[str]] = json.loads(decrypted)
            username: Final[str] = payload[0]
            password: Final[str] = payload[1]
            option: Final[str] = payload[2]
            arg1: Final[str] = payload[3]
            arg2: Final[str] = payload[4]
        except Exception as ex:  # pylint: disable=broad-except
            print(ex)
            return self._get_error_corrupted_data_response()

        # Maybe validate token.
        if isinstance(self.cipher, ISmartGateApiCipher):

            if "token" not in query:
                return self._get_error_token_not_set_response()

            # API returns invalid credentials when token is wrong
            token: Final[str] = query["token"][0]
            if token != self.cipher.token:
                return self._get_error_invalid_token_response()

        # Validate credentials.
        if not username or not password:
            return self._get_error_absent_credentials_response()

        if username != self.username or password != self.password:
            return self._get_error_invalid_credentials_response()

        if option not in [item.value for item in RequestOption]:
            return self._get_error_invalid_option_response()

        if option == RequestOption.INFO.value:
            return self._info_response()

        if option == RequestOption.ACTIVATE.value:
            return self._activate_response(arg1, arg2)

        return self._okay_response()

    def _okay_response(self) -> tuple:
        return self._new_response({"result": "OK"})

    def _activate_response(self, door_id: str, api_code: str) -> tuple:
        if api_code != self.api_code:
            return self._get_error_activate_invalid_api_code_response()

        if not door_id.isdigit():
            return self._get_error_activate_door_id_not_set_response()

        door: Final[dict] = self._info_data[f"door{door_id}"]
        if not door:
            return self._get_error_activate_invalid_door_response()

        # This door is not setup.
        if not door["name"]:
            return self._okay_response()

        door["status"] = (
            DoorStatus.CLOSED.value
            if door["status"] == DoorStatus.OPENED.value
            else DoorStatus.OPENED.value
        )

        return self._okay_response()

    def _info_response(self) -> tuple:
        return self._new_response(self._info_data)

    def _error_response(self, code: int, message: str) -> tuple:
        return self._new_response(
            {"error": {"errorcode": code, "errormsg": f"Code: {code} - {message}"}},
            encrypt=False,
        )

    def _new_response(self, data: Any, encrypt: bool = True) -> tuple:
        xml_str = parseString(
            dicttoxml.dicttoxml(data, custom_root="response", attr_type=False)
        ).toprettyxml()

        return (
            self.http_status,
            {},
            self.cipher.encrypt(xml_str) if encrypt else xml_str,
        )


class MockGogoGate2Server(AbstractMockServer[GogoGate2InfoResponse]):
    """Test server for GogoGate2"""

    def _get_info_data(self) -> GogoGate2InfoResponse:
        return GogoGate2InfoResponse(
            user=self.username,
            model="GG2",
            apicode=self.api_code,
            apiversion="apiversion123",
            remoteaccessenabled=0,
            remoteaccess="abcdefg12345.my-gogogate.com",
            firmwareversion="761",
            gogogatename="Home",
            door1=GogoGate2Door(
                door_id=1,
                permission=True,
                name="My Door 1",
                gate=False,
                status=DoorStatus.CLOSED,
                mode=DoorMode.GARAGE,
                sensor=True,
                camera=False,
                events=None,
                sensorid="sensor123",
                temperature=16.3,
            ),
            door2=GogoGate2Door(
                door_id=3,
                permission=True,
                name="My Door 2",
                gate=True,
                status=DoorStatus.OPENED,
                mode=DoorMode.GARAGE,
                sensor=False,
                camera=False,
                events=None,
                sensorid="sensor123",
                temperature=16.3,
            ),
            door3=GogoGate2Door(
                door_id=3,
                permission=True,
                name=None,
                gate=False,
                status=DoorStatus.UNDEFINED,
                mode=DoorMode.GARAGE,
                sensor=False,
                camera=False,
                events=None,
                sensorid="sensor123",
                temperature=16.3,
            ),
            outputs=Outputs(output1=True, output2=False, output3=False,),
            network=Network(ip="127.0.0.1"),
            wifi=Wifi(SSID="Wifi network", linkquality="80%", signal="20"),
        )

    def _get_error_corrupted_data_response(self) -> tuple:
        return self._error_response(
            GogoGate2ApiErrorCode.CORRUPTED_DATA.value, "Error: corrupted data"
        )

    def _get_error_invalid_token_response(self) -> tuple:
        return self._error_response(
            GogoGate2ApiErrorCode.INVALID_TOKEN.value, "Error: invalid token",
        )

    def _get_error_token_not_set_response(self) -> tuple:
        return self._error_response(
            GogoGate2ApiErrorCode.TOKEN_NOT_SET.value, "Error: token not set",
        )

    def _get_error_absent_credentials_response(self) -> tuple:
        return self._error_response(
            GogoGate2ApiErrorCode.CREDENTIALS_NOT_SET.value,
            "Error: login or password not set",
        )

    def _get_error_invalid_credentials_response(self) -> tuple:
        return self._error_response(
            GogoGate2ApiErrorCode.CREDENTIALS_INCORRECT.value,
            "Error: wrong login or password",
        )

    def _get_error_invalid_option_response(self) -> tuple:
        return self._error_response(
            GogoGate2ApiErrorCode.INVALID_OPTION.value, "Error: invalid option"
        )

    def _get_error_activate_invalid_api_code_response(self) -> tuple:
        return self._error_response(
            GogoGate2ApiErrorCode.INVALID_API_CODE.value, "Error: invalid API code"
        )

    def _get_error_activate_door_id_not_set_response(self) -> tuple:
        return self._error_response(
            GogoGate2ApiErrorCode.DOOR_NOT_SET.value, "Error: door not set"
        )

    def _get_error_activate_invalid_door_response(self) -> tuple:
        return self._error_response(
            GogoGate2ApiErrorCode.INVALID_DOOR.value, "Error: invalid door"
        )


class MockISmartGateServer(AbstractMockServer[ISmartGateInfoResponse]):
    """Test server for ISmartGate"""

    def _get_info_data(self) -> ISmartGateInfoResponse:
        return ISmartGateInfoResponse(
            pin=1234,
            lang="en",
            ismartgatename="Home",
            newfirmware=False,
            user=self.username,
            model="GG2",
            apiversion="apiversion123",
            remoteaccessenabled=0,
            remoteaccess="abcdefg12345.my-gogogate.com",
            firmwareversion="761",
            door1=ISmartGateDoor(
                enabled=True,
                apicode=self.api_code,
                customimage=False,
                door_id=1,
                permission=True,
                name="My Door 1",
                gate=False,
                status=DoorStatus.CLOSED,
                mode=DoorMode.GARAGE,
                sensor=True,
                camera=False,
                events=None,
                sensorid="sensor123",
                temperature=16.3,
            ),
            door2=ISmartGateDoor(
                enabled=True,
                apicode=self.api_code,
                customimage=False,
                door_id=3,
                permission=True,
                name="My Door 2",
                gate=True,
                status=DoorStatus.OPENED,
                mode=DoorMode.GARAGE,
                sensor=False,
                camera=False,
                events=None,
                sensorid="sensor123",
                temperature=16.3,
            ),
            door3=ISmartGateDoor(
                enabled=True,
                apicode=self.api_code,
                customimage=False,
                door_id=3,
                permission=True,
                name=None,
                gate=False,
                status=DoorStatus.UNDEFINED,
                mode=DoorMode.GARAGE,
                sensor=False,
                camera=False,
                events=None,
                sensorid="sensor123",
                temperature=16.3,
            ),
            network=Network(ip="127.0.0.1"),
            wifi=Wifi(SSID="Wifi network", linkquality="80%", signal="20"),
        )

    def _get_error_corrupted_data_response(self) -> tuple:
        return self._error_response(
            GogoGate2ApiErrorCode.CORRUPTED_DATA.value, "Error: corrupted data"
        )

    def _get_error_invalid_token_response(self) -> tuple:
        return self._error_response(
            ISmartGateApiErrorCode.INVALID_TOKEN.value, "Error: invalid token",
        )

    def _get_error_token_not_set_response(self) -> tuple:
        return self._error_response(
            ISmartGateApiErrorCode.TOKEN_NOT_SET.value, "Error: token not set",
        )

    def _get_error_absent_credentials_response(self) -> tuple:
        return self._error_response(
            ISmartGateApiErrorCode.CREDENTIALS_NOT_SET.value,
            "Error: login or password not set",
        )

    def _get_error_invalid_credentials_response(self) -> tuple:
        return self._error_response(
            ISmartGateApiErrorCode.CREDENTIALS_INCORRECT.value,
            "Error: wrong login or password",
        )

    def _get_error_invalid_option_response(self) -> tuple:
        return self._error_response(
            ISmartGateApiErrorCode.INVALID_OPTION.value, "Error: invalid option"
        )

    def _get_error_activate_invalid_api_code_response(self) -> tuple:
        return self._error_response(
            ISmartGateApiErrorCode.INVALID_API_CODE.value, "Error: invalid API code"
        )

    def _get_error_activate_door_id_not_set_response(self) -> tuple:
        return self._error_response(
            ISmartGateApiErrorCode.DOOR_NOT_SET.value, "Error: door not set"
        )

    def _get_error_activate_invalid_door_response(self) -> tuple:
        return self._error_response(
            ISmartGateApiErrorCode.INVALID_DOOR.value, "Error: invalid door"
        )
