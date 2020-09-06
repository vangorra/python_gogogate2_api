"""Common code for gate APIs."""
import dataclasses
from dataclasses import dataclass
from enum import Enum
import json
from typing import Any, Callable, Optional, Tuple, Type, TypeVar, Union, cast
from xml.etree.ElementTree import Element  # nosec

from typing_extensions import Final

GenericType = TypeVar("GenericType")


class TagException(Exception):
    """General exception for tags."""

    def __init__(self, tag: str, message: str) -> None:
        super().__init__(message)
        self._tag: Final[str] = tag

    @property
    def tag(self) -> str:
        """Get the tag."""
        return self._tag


class TagNotFoundException(TagException):
    """Thrown when encountering an unexpected type."""

    def __init__(self, tag: str) -> None:
        """Initialize."""
        super().__init__(tag, f"Did not find element tag '{tag}'.")


class TextEmptyException(TagException):
    """Thrown when encountering an unexpected type."""

    def __init__(self, tag: str) -> None:
        """Initialize."""
        super().__init__(tag, f"Text was empty for tag '{tag}'.")


class UnexpectedTypeException(Exception):
    """Thrown when encountering an unexpected type."""

    def __init__(self, value: Any, expected: Type[GenericType]):
        """Initialize."""
        super().__init__(
            'Expected of "%s" to be "%s" but was "%s."' % (value, expected, type(value))
        )
        self._value: Final[Any] = value
        self._expected: Final[Type[GenericType]] = expected

    @property
    def value(self) -> Any:
        """Get value."""
        return self._value

    @property
    def expected(self) -> Type[GenericType]:
        """Get expected type."""
        return self._expected


def enforce_type(value: Any, expected: Type[GenericType]) -> GenericType:
    """Enforce a data type."""
    if not isinstance(value, expected):
        raise UnexpectedTypeException(value, expected)

    return value


def value_or_none(
    value: Any, convert_fn: Callable[[Any], GenericType]
) -> Union[GenericType, None]:
    """Convert a value given a specific conversion function."""
    if value is None:
        return None

    try:
        return convert_fn(value)
    except Exception:  # pylint: disable=broad-except
        return None


def enum_or_raise(value: Optional[Union[str, int]], enum: Type[Enum]) -> Enum:
    """Return Enum or raise exception."""
    if value is None:
        raise UnexpectedTypeException(value, enum)

    return enum(value)


def str_or_raise(value: Any) -> str:
    """Return string or raise exception."""
    return enforce_type(str_or_none(value), str)


def str_or_none(value: Any) -> Optional[str]:
    """Return str or None."""
    return value_or_none(value, str)


def int_or_raise(value: Any) -> int:
    """Return int or raise exception."""
    return enforce_type(int_or_none(value), int)


def int_or_none(value: Any) -> Optional[int]:
    """Return int or None."""
    return value_or_none(value, int)


def float_or_none(value: Any) -> Optional[float]:
    """Return float or None."""
    return value_or_none(value, float)


class EnhancedJSONEncoder(json.JSONEncoder):
    """JSON encoder."""

    # pylint: disable=method-hidden
    def default(self, o) -> Any:  # type: ignore
        """Encode the object."""
        if dataclasses.is_dataclass(o):
            return dataclasses.asdict(o)
        if isinstance(o, Enum):
            return o.value
        return super().default(o)


class ApiError(Exception):
    """Generic API error."""

    def __init__(self, code: int, message: str) -> None:
        super().__init__(f"Code: {code} - {message}")
        self._code: Final[int] = code
        self._message: Final[str] = message

    @property
    def code(self) -> int:
        """Get the error code."""
        return self._code

    @property
    def message(self) -> str:
        """Get the error message."""
        return self._message


class CredentialsNotSetException(ApiError):
    """Credentials not set exception."""


class CredentialsIncorrectException(ApiError):
    """Credentials incorrect exception."""


class InvalidOptionException(ApiError):
    """Invalid option exception."""


class InvalidApiCodeException(ApiError):
    """Invalid api code exception."""


class DoorNotSetException(ApiError):
    """Door not set exception."""


ExceptionGenerator = Callable[[int, str], ApiError]


class DoorStatus(Enum):
    """Door status."""

    CLOSED = "closed"
    OPENED = "opened"
    UNDEFINED = "undefined"


class DoorMode(Enum):
    """Door mode."""

    GARAGE = "garage"
    PULSE = "pulse"
    ON_OFF = "onoff"


class RequestOption(Enum):
    """Request option."""

    INFO = "info"
    ACTIVATE = "activate"


@dataclass(frozen=True)
# pylint: disable=too-many-instance-attributes
class AbstractDoor:
    """Door object."""

    door_id: int
    permission: bool
    name: Optional[str]
    mode: DoorMode
    gate: bool
    status: DoorStatus
    sensor: bool
    camera: bool
    events: Optional[int]
    sensorid: Optional[str]
    temperature: Optional[float]


@dataclass(frozen=True)
class GogoGate2Door(AbstractDoor):
    """Door object."""


@dataclass(frozen=True)
class ISmartGateDoor(AbstractDoor):
    """Door object."""

    enabled: bool
    apicode: str
    customimage: bool


@dataclass(frozen=True)
class Outputs:
    """Outputs object."""

    output1: bool
    output2: bool
    output3: bool


@dataclass(frozen=True)
class Network:
    """Network object."""

    ip: str  # pylint: disable=invalid-name


@dataclass(frozen=True)
class Wifi:
    """Wifi object."""

    SSID: Optional[str]  # pylint: disable=invalid-name
    linkquality: Optional[str]
    signal: Optional[str]


@dataclass(frozen=True)
class AbstractActivateResponse:
    """Response from activate calls."""

    result: bool


@dataclass(frozen=True)
class GogoGate2ActivateResponse(AbstractActivateResponse):
    """GogoGate2 response from activate calls."""


@dataclass(frozen=True)
class ISmartGateActivateResponse(AbstractActivateResponse):
    """iSmartGate response from activate calls."""


@dataclass(frozen=True)
# pylint: disable=too-many-instance-attributes
class AbstractInfoResponse:
    """Response from info calls."""

    user: str
    model: str
    apiversion: str
    remoteaccessenabled: int
    remoteaccess: str
    firmwareversion: str

    door1: AbstractDoor
    door2: AbstractDoor
    door3: AbstractDoor

    network: Network
    wifi: Wifi


@dataclass(frozen=True)
#  pylint: disable=too-many-instance-attributes
class GogoGate2InfoResponse(AbstractInfoResponse):
    """Response from gogogate2 api calls."""

    gogogatename: str
    apicode: str
    door1: GogoGate2Door
    door2: GogoGate2Door
    door3: GogoGate2Door
    outputs: Outputs


@dataclass(frozen=True)
class ISmartGateInfoResponse(AbstractInfoResponse):
    """Response from iSmartGate info calls."""

    pin: int
    lang: str
    ismartgatename: str
    newfirmware: bool

    door1: ISmartGateDoor
    door2: ISmartGateDoor
    door3: ISmartGateDoor


def element_or_none(element: Optional[Element], tag: str) -> Optional[Element]:
    """Get element from xml element."""
    return None if element is None else element.find(tag)


def element_or_raise(element: Optional[Element], tag: str) -> Element:
    """Get element from xml element."""
    found_element: Final[Optional[Element]] = element_or_none(element, tag)
    if found_element is None:
        raise TagNotFoundException(tag)

    return found_element


def element_text_or_none(element: Optional[Element], tag: str) -> Optional[str]:
    """Get element text from xml element."""
    found_element: Final[Optional[Element]] = element_or_none(element, tag)
    return (
        None
        if found_element is None
        else None
        if found_element.text is None
        else found_element.text.strip()
    )


def element_text_or_raise(element: Optional[Element], tag: str) -> str:
    """Get element text from xml element."""
    found_element: Final[Element] = element_or_raise(element, tag)
    if found_element.text is None:
        raise TextEmptyException(tag)

    return found_element.text.strip()


def element_int_or_raise(element: Optional[Element], tag: str) -> int:
    """Get element int from xml element."""
    found_element: Final[Element] = element_or_raise(element, tag)
    if found_element.text is None:
        raise TextEmptyException(tag)

    return int_or_raise(found_element.text.strip())


def element_to_api_error(element: Element) -> ApiError:
    """Get api error from xml element."""
    return ApiError(
        code=int_or_raise(element_text_or_raise(element, "errorcode")),
        message=element_text_or_raise(element, "errormsg"),
    )


def wifi_or_raise(element: Element) -> Wifi:
    """Get wifi from xml element."""
    return Wifi(
        SSID=element_text_or_none(element, "SSID"),
        linkquality=element_text_or_none(element, "linkquality"),
        signal=element_text_or_none(element, "signal"),
    )


def network_or_raise(element: Element) -> Network:
    """Get network from xml element."""
    return Network(ip=element_text_or_raise(element, "ip"),)


def outputs_or_raise(element: Element) -> Outputs:
    """Get outputs from xml element."""
    return Outputs(
        output1=element_text_or_raise(element, "output1").lower() == "on",
        output2=element_text_or_raise(element, "output2").lower() == "on",
        output3=element_text_or_raise(element, "output3").lower() == "on",
    )


def gogogate2_door_or_raise(door_id: int, element: Element) -> GogoGate2Door:
    """Get door from xml element."""
    temp = float_or_none(element_text_or_none(element, "temperature"))
    return GogoGate2Door(
        door_id=door_id,
        permission=element_text_or_raise(element, "permission").lower() == "yes",
        name=element_text_or_none(element, "name"),
        gate=False,
        mode=cast(
            DoorMode, enum_or_raise(element_text_or_raise(element, "mode"), DoorMode)
        ),
        status=cast(
            DoorStatus,
            enum_or_raise(element_text_or_raise(element, "status"), DoorStatus),
        ),
        sensor=element_text_or_raise(element, "sensor").lower() == "yes",
        sensorid=element_text_or_none(element, "sensorid"),
        camera=element_text_or_raise(element, "camera").lower() == "yes",
        events=int_or_none(element_text_or_none(element, "events")),
        temperature=None if temp is None else None if temp < -100000 else temp,
    )


def ismartgate_door_or_raise(door_id: int, element: Element) -> ISmartGateDoor:
    """Get door from xml element."""
    temp: Final[Optional[float]] = float_or_none(
        element_text_or_none(element, "temperature")
    )
    return ISmartGateDoor(
        door_id=door_id,
        enabled=element_text_or_raise(element, "enabled").lower() == "yes",
        apicode=element_text_or_raise(element, "apicode"),
        customimage=element_text_or_raise(element, "customimage").lower() == "yes",
        permission=element_text_or_raise(element, "permission").lower() == "yes",
        name=element_text_or_none(element, "name"),
        gate=element_text_or_raise(element, "gate").lower() == "yes",
        mode=cast(
            DoorMode, enum_or_raise(element_text_or_raise(element, "mode"), DoorMode)
        ),
        status=cast(
            DoorStatus,
            enum_or_raise(element_text_or_raise(element, "status"), DoorStatus),
        ),
        sensor=element_text_or_raise(element, "sensor").lower() == "yes",
        sensorid=element_text_or_none(element, "sensorid"),
        camera=element_text_or_raise(element, "camera").lower() == "yes",
        events=int_or_none(element_text_or_none(element, "events")),
        temperature=None if temp is None else None if temp < -100000 else temp,
    )


def element_to_gogogate2_info_response(element: Element) -> GogoGate2InfoResponse:
    """Get response from xml element."""
    return GogoGate2InfoResponse(
        user=element_text_or_raise(element, "user"),
        gogogatename=element_text_or_raise(element, "gogogatename"),
        model=element_text_or_raise(element, "model"),
        apiversion=element_text_or_raise(element, "apiversion"),
        remoteaccessenabled=element_text_or_raise(element, "remoteaccessenabled")
        == "1",
        remoteaccess=element_text_or_raise(element, "remoteaccess"),
        firmwareversion=element_text_or_raise(element, "firmwareversion"),
        apicode=element_text_or_raise(element, "apicode"),
        door1=gogogate2_door_or_raise(1, element_or_raise(element, "door1")),
        door2=gogogate2_door_or_raise(2, element_or_raise(element, "door2")),
        door3=gogogate2_door_or_raise(3, element_or_raise(element, "door3")),
        outputs=outputs_or_raise(element_or_raise(element, "outputs")),
        network=network_or_raise(element_or_raise(element, "network")),
        wifi=wifi_or_raise(element_or_raise(element, "wifi")),
    )


def element_to_ismartgate_info_response(element: Element) -> ISmartGateInfoResponse:
    """Get response from xml element."""
    return ISmartGateInfoResponse(
        user=element_text_or_raise(element, "user"),
        pin=element_int_or_raise(element, "pin"),
        lang=element_text_or_raise(element, "lang"),
        ismartgatename=element_text_or_raise(element, "ismartgatename"),
        model=element_text_or_raise(element, "model"),
        apiversion=element_text_or_raise(element, "apiversion"),
        remoteaccessenabled=element_text_or_raise(element, "remoteaccessenabled")
        == "1",
        remoteaccess=element_text_or_raise(element, "remoteaccess"),
        firmwareversion=element_text_or_raise(element, "firmwareversion"),
        newfirmware=element_text_or_raise(element, "newfirmware").lower() == "yes",
        door1=ismartgate_door_or_raise(1, element_or_raise(element, "door1")),
        door2=ismartgate_door_or_raise(2, element_or_raise(element, "door2")),
        door3=ismartgate_door_or_raise(3, element_or_raise(element, "door3")),
        network=network_or_raise(element_or_raise(element, "network")),
        wifi=wifi_or_raise(element_or_raise(element, "wifi")),
    )


def element_to_gogogate2_activate_response(
    element: Element,
) -> GogoGate2ActivateResponse:
    """Get response from xml element."""
    return GogoGate2ActivateResponse(
        result=element_text_or_raise(element, "result").lower() == "ok"
    )


def element_to_ismartgate_activate_response(
    element: Element,
) -> ISmartGateActivateResponse:
    """Get response from xml element."""
    return ISmartGateActivateResponse(
        result=element_text_or_raise(element, "result").lower() == "ok"
    )


def get_door_by_id(
    door_id: int, response: AbstractInfoResponse
) -> Optional[AbstractDoor]:
    """Get a door from a gogogate2 response."""
    return next(
        iter([door for door in get_doors(response) if door.door_id == door_id]), None
    )


def get_doors(response: AbstractInfoResponse) -> Tuple[AbstractDoor, ...]:
    """Get a tuple of doors from a response."""
    return (response.door1, response.door2, response.door3)


def get_configured_doors(response: AbstractInfoResponse) -> Tuple[AbstractDoor, ...]:
    """Get a tuple of configured doors from a response."""
    return tuple([door for door in get_doors(response) if door.name])
