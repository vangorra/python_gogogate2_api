"""Tets for main API."""
from gogogate2_api import DoorStatus, GogoGate2Api, get_door_by_id
from gogogate2_api.common import ApiError
import pytest
import requests
import responses

from .common import MockGogoGateServer


@responses.activate
def test_api_errors() -> None:
    """Test api errors."""
    server = MockGogoGateServer("device1")

    # Incorrect username/password.
    api = GogoGate2Api(server.host, "fakeuser", "fakepassword")
    with pytest.raises(ApiError) as exinfo:
        api.info()
        assert exinfo.value.code == 1
        assert exinfo.value.message == "Error: wrong login or password"

    # HTTP error.
    api = GogoGate2Api("fakehost", "fakeuser", "fakepassword")
    with pytest.raises(requests.exceptions.ConnectionError):
        api.info()


@responses.activate
def test_activate() -> None:
    """Test activate."""
    server = MockGogoGateServer("device1")
    api = GogoGate2Api(server.host, server.username, server.password)

    response = api.activate(1)
    assert response
    assert response.result


@responses.activate
# pylint: disable=too-many-statements
def test_open_and_close_door() -> None:
    """Test open and close door."""
    server = MockGogoGateServer("device1")
    api = GogoGate2Api(server.host, server.username, server.password)

    # Initial info.
    response = api.info()
    door1 = get_door_by_id(1, response)
    door2 = get_door_by_id(2, response)
    door3 = get_door_by_id(3, response)
    assert door1
    assert door2
    assert door3
    assert door1.status == DoorStatus.CLOSED
    assert door2.status == DoorStatus.OPENED
    assert door3.status == DoorStatus.UNDEFINED

    # Nothing changes because door is already closed.
    assert api.close_door(1) is False
    response = api.info()
    door1 = get_door_by_id(1, response)
    door2 = get_door_by_id(2, response)
    door3 = get_door_by_id(3, response)
    assert door1
    assert door2
    assert door3
    assert door1.status == DoorStatus.CLOSED
    assert door2.status == DoorStatus.OPENED
    assert door3.status == DoorStatus.UNDEFINED

    # Open a door.
    assert api.open_door(1) is True
    response = api.info()
    door1 = get_door_by_id(1, response)
    door2 = get_door_by_id(2, response)
    door3 = get_door_by_id(3, response)
    assert door1
    assert door2
    assert door3
    assert door1.status == DoorStatus.OPENED
    assert door2.status == DoorStatus.OPENED
    assert door3.status == DoorStatus.UNDEFINED

    # Close a door.
    assert api.close_door(2) is True
    response = api.info()
    door1 = get_door_by_id(1, response)
    door2 = get_door_by_id(2, response)
    door3 = get_door_by_id(3, response)
    assert door1
    assert door2
    assert door3
    assert door1.status == DoorStatus.OPENED
    assert door2.status == DoorStatus.CLOSED
    assert door3.status == DoorStatus.UNDEFINED

    # No change for already closed door.
    assert api.close_door(2) is False
    response = api.info()
    door1 = get_door_by_id(1, response)
    door2 = get_door_by_id(2, response)
    door3 = get_door_by_id(3, response)
    assert door1
    assert door2
    assert door3
    assert door1.status == DoorStatus.OPENED
    assert door2.status == DoorStatus.CLOSED
    assert door3.status == DoorStatus.UNDEFINED

    # No change for unknown door.
    assert api.close_door(8) is False
    response = api.info()
    door1 = get_door_by_id(1, response)
    door2 = get_door_by_id(2, response)
    door3 = get_door_by_id(3, response)
    assert door1
    assert door2
    assert door3
    assert door1.status == DoorStatus.OPENED
    assert door2.status == DoorStatus.CLOSED
    assert door3.status == DoorStatus.UNDEFINED

    # No change for unsupported status.
    # pylint: disable=protected-access
    assert api._set_door_status(1, DoorStatus.UNDEFINED) is False
    response = api.info()
    door1 = get_door_by_id(1, response)
    door2 = get_door_by_id(2, response)
    door3 = get_door_by_id(3, response)
    assert door1
    assert door2
    assert door3
    assert door1.status == DoorStatus.OPENED
    assert door2.status == DoorStatus.CLOSED
    assert door3.status == DoorStatus.UNDEFINED
