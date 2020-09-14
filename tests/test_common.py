"""Tests for common code."""
from xml.etree.ElementTree import Element  # nosec

from defusedxml import ElementTree
from gogogate2_api.common import (
    DoorMode,
    DoorStatus,
    GogoGate2Door,
    GogoGate2InfoResponse,
    Network,
    Outputs,
    TagNotFoundException,
    TextEmptyException,
    UnexpectedTypeException,
    Wifi,
    element_text_or_raise,
    enum_or_raise,
    get_configured_doors,
    int_or_raise,
    str_or_raise,
)
import pytest
from typing_extensions import Final


def test_element_exceptions() -> None:
    """Test exceptions thrown while parsing xml elements."""
    root_element: Final[Element] = ElementTree.fromstring(
        """
            <response>
                <tag1></tag1>
                <tag2>value</tag2>
            </response>
        """
    )

    with pytest.raises(TagNotFoundException) as exinfo1:
        element_text_or_raise(root_element, "tag3")
        assert exinfo1.value.tag == "tag3"

    with pytest.raises(TextEmptyException) as exinfo2:
        element_text_or_raise(root_element, "tag1")
        assert exinfo2.value.tag == "tag1"

    with pytest.raises(UnexpectedTypeException) as exinfo3:
        int_or_raise(element_text_or_raise(root_element, "tag2"))
        assert exinfo3.value.value == "value"
        assert exinfo3.value.expected == int


def test_str_or_raise() -> None:
    """Test exceptions for strings."""
    with pytest.raises(UnexpectedTypeException) as exinfo:
        str_or_raise(None)
        assert exinfo.value.value is None
        assert exinfo.value.expected == str

    assert str_or_raise(123) == "123"


def test_enum_or_raise() -> None:
    """Test exceptions for enums."""
    with pytest.raises(UnexpectedTypeException) as exinfo:
        enum_or_raise(None, DoorStatus)
        assert exinfo.value.value is None
        assert exinfo.value.expected == DoorStatus


def test_get_enabled_doors() -> None:
    """Test get configurd doors."""
    response: Final[GogoGate2InfoResponse] = GogoGate2InfoResponse(
        user="user1",
        gogogatename="gogogatename1",
        model="",
        apiversion="",
        remoteaccessenabled=False,
        remoteaccess="",
        firmwareversion="",
        apicode="",
        door1=GogoGate2Door(
            door_id=1,
            permission=True,
            name="Door1",
            gate=False,
            mode=DoorMode.GARAGE,
            status=DoorStatus.OPENED,
            sensor=True,
            sensorid=None,
            camera=False,
            events=2,
            temperature=None,
            voltage=None,
        ),
        door2=GogoGate2Door(
            door_id=2,
            permission=True,
            name=None,
            gate=True,
            mode=DoorMode.GARAGE,
            status=DoorStatus.OPENED,
            sensor=True,
            sensorid=None,
            camera=False,
            events=2,
            temperature=None,
            voltage=None,
        ),
        door3=GogoGate2Door(
            door_id=3,
            permission=True,
            name="Door3",
            gate=False,
            mode=DoorMode.GARAGE,
            status=DoorStatus.OPENED,
            sensor=True,
            sensorid=None,
            camera=False,
            events=2,
            temperature=None,
            voltage=None,
        ),
        outputs=Outputs(output1=True, output2=False, output3=True),
        network=Network(ip=""),
        wifi=Wifi(SSID="", linkquality="", signal=""),
    )

    assert get_configured_doors(response) == (response.door1, response.door3)
