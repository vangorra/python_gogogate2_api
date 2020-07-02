"""Common code for gogogate2 API."""
from enum import Enum
from typing import (
    Any,
    Callable,
    NamedTuple,
    Optional,
    Tuple,
    Type,
    TypeVar,
    Union,
    cast,
)
from xml.etree.ElementTree import Element  # nosec

from typing_extensions import Final

GenericType = TypeVar("GenericType")


class TagNotFoundException(Exception):
    """Thrown when encountering an unexpected type."""

    def __init__(self, tag: str) -> None:
        """Initialize."""
        super().__init__(f"Did not find element tag '{tag}'.")
        self.tag = tag


class TextEmptyException(Exception):
    """Thrown when encountering an unexpected type."""

    def __init__(self, tag: str) -> None:
        """Initialize."""
        super().__init__(f"Text was empty for tag '{tag}'.")
        self.tag = tag


class UnexpectedTypeException(Exception):
    """Thrown when encountering an unexpected type."""

    def __init__(self, value: Any, expected: Type[GenericType]):
        """Initialize."""
        super().__init__(
            'Expected of "%s" to be "%s" but was "%s."' % (value, expected, type(value))
        )
        self.value = value
        self.expected = expected


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


class ApiError(Exception):
    """Generic API error."""

    def __init__(self, code: int, message: str) -> None:
        super(ApiError, self).__init__(f"Code: {code} - {message}")
        self.code: Final = code
        self.message: Final = message


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


class Door(NamedTuple):
    """Door object."""

    door_id: int
    permission: bool
    name: Optional[str]
    mode: DoorMode
    status: DoorStatus
    sensor: bool
    sensorid: Optional[str]
    camera: bool
    events: Optional[int]
    temperature: Optional[float]


class Outputs(NamedTuple):
    """Outputs object."""

    output1: bool
    output2: bool
    output3: bool


class Network(NamedTuple):
    """Network object."""

    ip: str


class Wifi(NamedTuple):
    """Wifi object."""

    SSID: Optional[str]
    linkquality: str
    signal: str


class InfoResponse(NamedTuple):
    """Response from gogogate2 api calls."""

    user: str
    gogogatename: str
    model: str
    apiversion: str
    remoteaccessenabled: int
    remoteaccess: str
    firmwareversion: str
    apicode: str
    door1: Door
    door2: Door
    door3: Door
    outputs: Outputs
    network: Network
    wifi: Wifi


class ActivateResponse(NamedTuple):
    """Response from gogogate2 activate calls."""

    result: bool


def element_or_none(element: Optional[Element], tag: str) -> Optional[Element]:
    """Get element from xml element."""
    return None if element is None else element.find(tag)


def element_or_raise(element: Optional[Element], tag: str) -> Element:
    """Get element from xml element."""
    element = element_or_none(element, tag)
    if element is None:
        raise TagNotFoundException(tag)

    return element


def element_text_or_none(element: Optional[Element], tag: str) -> Optional[str]:
    """Get element text from xml element."""
    element = element_or_none(element, tag)
    return (
        None
        if element is None
        else None
        if element.text is None
        else element.text.strip()
    )


def element_text_or_raise(element: Optional[Element], tag: str) -> str:
    """Get element text from xml element."""
    element = element_or_raise(element, tag)
    if element.text is None:
        raise TextEmptyException(tag)

    return element.text.strip()


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
        linkquality=element_text_or_raise(element, "linkquality"),
        signal=element_text_or_raise(element, "signal"),
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


def door_or_raise(door_id: int, element: Element) -> Door:
    """Get door from xml element."""
    temp = float_or_none(element_text_or_none(element, "temperature"))
    return Door(
        door_id=door_id,
        permission=element_text_or_raise(element, "permission").lower() == "yes",
        name=element_text_or_none(element, "name"),
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


def element_to_info_response(element: Element) -> InfoResponse:
    """Get response from xml element."""
    return InfoResponse(
        user=element_text_or_raise(element, "user"),
        gogogatename=element_text_or_raise(element, "gogogatename"),
        model=element_text_or_raise(element, "model"),
        apiversion=element_text_or_raise(element, "apiversion"),
        remoteaccessenabled=element_text_or_raise(element, "remoteaccessenabled")
        == "1",
        remoteaccess=element_text_or_raise(element, "remoteaccess"),
        firmwareversion=element_text_or_raise(element, "firmwareversion"),
        apicode=element_text_or_raise(element, "apicode"),
        door1=door_or_raise(1, element_or_raise(element, "door1")),
        door2=door_or_raise(2, element_or_raise(element, "door2")),
        door3=door_or_raise(3, element_or_raise(element, "door3")),
        outputs=outputs_or_raise(element_or_raise(element, "outputs")),
        network=network_or_raise(element_or_raise(element, "network")),
        wifi=wifi_or_raise(element_or_raise(element, "wifi")),
    )


def element_to_activate_response(element: Element) -> ActivateResponse:
    """Get response from xml element."""
    return ActivateResponse(
        result=element_text_or_raise(element, "result").lower() == "ok"
    )


def get_door_by_id(door_id: int, response: InfoResponse) -> Optional[Door]:
    """Get a door from a gogogate2 response."""
    return next(
        iter([door for door in get_doors(response) if door.door_id == door_id]), None
    )


def get_doors(response: InfoResponse) -> Tuple[Door, ...]:
    """Get a tuple of doors from a response."""
    return (response.door1, response.door2, response.door3)


def get_configured_doors(response: InfoResponse) -> Tuple[Door, ...]:
    """Get a tuple of configured doors from a response."""
    return tuple([door for door in get_doors(response) if door.name])
