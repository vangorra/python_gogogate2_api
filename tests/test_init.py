"""Tets for main API."""
from typing import Callable, Union

from gogogate2_api import (
    GogoGate2Api,
    GogoGate2ApiCipher,
    ISmartGateApi,
    ISmartGateApiCipher,
)
from gogogate2_api.common import ApiError, DoorStatus, get_door_by_id
from gogogate2_api.const import GogoGate2ApiErrorCode, ISmartGateApiErrorCode
import pytest
import requests
import responses

from .common import MockGogoGate2Server, MockISmartGateServer

ApiType = Union[GogoGate2Api, ISmartGateApi]
ServerType = Union[MockGogoGate2Server, MockISmartGateServer]
ApiGenerator = Callable[[str, str, str], ApiType]
ServerGenerator = Callable[..., ServerType]


def test_ismartgate_token() -> None:
    """Test token generation."""

    assert (
        ISmartGateApiCipher("admin", "password").token
        == "f7001ecfe4d09ea0e58cb09058ba11ffe3ea36f0"
    )
    assert (
        ISmartGateApiCipher("admin2", "password2").token
        == "6669032e03454ecd1c6ea59abe49c6ed4303ff63"
    )


def test_ismartgate_encrypt_decrypt() -> None:
    """Test encrypt/decrypt."""
    cipher = ISmartGateApiCipher("admin", "password")

    # Test encrypted contents matches exactly and can be decrypted.
    enc = cipher.encrypt(
        '["admin", "notRealPassword", "info", "", ""]', init_vector="497c04879e0d26af"
    )
    assert (
        enc
        == "497c04879e0d26afxuTQ0lB1Rd0c0G/l6Tiw+YCjnN9oG26d3I5IyGQpvkcpJ9l2aHDcTdquB0RnkWgi"
    )
    assert cipher.decrypt(enc) == '["admin", "notRealPassword", "info", "", ""]'

    # Test with generated initialization vector.
    assert cipher.decrypt(cipher.encrypt("Hello World")) == "Hello World"

    # Test initialization vector padding.
    assert (
        cipher.decrypt(cipher.encrypt("Hello World", init_vector="A")) == "Hello World"
    )


def test_gogogate2_cipher() -> None:
    """Test encrypt/decrypt."""
    cipher = GogoGate2ApiCipher()

    # Test encrypted contents matches exactly and can be decrypted.
    enc = cipher.encrypt(
        '["admin", "notRealPassword", "info", "", ""]', init_vector="497c04879e0d26af"
    )
    assert (
        enc
        == "497c04879e0d26afhnGLw5SJBnC0qUqNFHYTBgzIGsTyUF96EyZMyAHIUrLiQobociSp4fkBhf1sWSWc"
    )
    assert cipher.decrypt(enc) == '["admin", "notRealPassword", "info", "", ""]'

    # Test with generated initialization vector.
    assert cipher.decrypt(cipher.encrypt("Hello World")) == "Hello World"

    # Test initialization vector padding.
    assert (
        cipher.decrypt(cipher.encrypt("Hello World", init_vector="A")) == "Hello World"
    )


@pytest.mark.parametrize(
    ("api_generator", "server_generator", "error_code"),
    (
        (
            GogoGate2Api,
            MockGogoGate2Server,
            GogoGate2ApiErrorCode.CREDENTIALS_INCORRECT.value,
        ),
        (
            ISmartGateApi,
            MockISmartGateServer,
            ISmartGateApiErrorCode.CREDENTIALS_INCORRECT.value,
        ),
    ),
)
@responses.activate
def test_api_invalid_credentials(
    api_generator: ApiGenerator, server_generator: ServerGenerator, error_code: int
) -> None:
    """Test invalid credentials error."""
    # Incorrect username/password.
    api: ApiType = api_generator("device1", "fakeuser", "fakepassword")
    server_generator(api, username="fakeuser1", password="fakepassword2")
    with pytest.raises(ApiError) as exinfo:
        api.info()
    assert exinfo.value.code == error_code


@pytest.mark.parametrize(
    ("api_generator", "server_generator"),
    ((GogoGate2Api, MockGogoGate2Server), (ISmartGateApi, MockISmartGateServer)),
)
@responses.activate
def test_api_connection_error(
    api_generator: ApiGenerator, server_generator: ServerGenerator
) -> None:
    """Test http invalid host error."""
    api: ApiType = api_generator("device1", "fakeuser", "fakepassword")
    server_generator(api, host="realhost")
    with pytest.raises(requests.exceptions.ConnectionError):
        api.info()


@pytest.mark.parametrize(
    ("api_generator", "server_generator"),
    ((GogoGate2Api, MockGogoGate2Server), (ISmartGateApi, MockISmartGateServer)),
)
@responses.activate
def test_activate(
    api_generator: ApiGenerator, server_generator: ServerGenerator
) -> None:
    """Test activate."""
    api = api_generator("device1", "fakeuser", "fakepassword")
    server_generator(api)

    response = api.activate(1)
    assert response
    assert response.result


@pytest.mark.parametrize(
    ("api_generator", "server_generator"),
    ((GogoGate2Api, MockGogoGate2Server), (ISmartGateApi, MockISmartGateServer)),
)
@responses.activate
# pylint: disable=too-many-statements
def test_open_and_close_door(
    api_generator: ApiGenerator, server_generator: ServerGenerator
) -> None:
    """Test open and close door."""
    api = api_generator("device1", "fakeuser", "fakepassword")
    server_generator(api)

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


@pytest.mark.parametrize(
    ("api_generator", "server_generator", "true_value"),
    (
        (GogoGate2Api, MockGogoGate2Server, "1"),
        (ISmartGateApi, MockISmartGateServer, "yes"),
    ),
)
@responses.activate
# pylint: disable=too-many-statements
def test_remoteaccess(
    api_generator: ApiGenerator, server_generator: ServerGenerator, true_value: str
) -> None:
    """Test open and close door."""
    api = api_generator("device1", "fakeuser", "fakepassword")
    server = server_generator(api)

    server.set_info_value("remoteaccessenabled", "false")
    assert not api.info().remoteaccessenabled
    server.set_info_value("remoteaccessenabled", "no")
    assert not api.info().remoteaccessenabled
    server.set_info_value("remoteaccessenabled", "0")
    assert not api.info().remoteaccessenabled

    server.set_info_value("remoteaccessenabled", true_value)
    assert api.info().remoteaccessenabled
    server.set_info_value("remoteaccessenabled", true_value.upper())
    assert api.info().remoteaccessenabled
    server.set_info_value("remoteaccessenabled", true_value.lower())
    assert api.info().remoteaccessenabled


@pytest.mark.parametrize(
    ("api_generator", "server_generator"),
    ((GogoGate2Api, MockGogoGate2Server), (ISmartGateApi, MockISmartGateServer)),
)
@responses.activate
# pylint: disable=too-many-statements
def test_sensor_temperature_and_voltage(
    api_generator: ApiGenerator, server_generator: ServerGenerator
) -> None:
    """Test open and close door."""
    api = api_generator("device1", "fakeuser", "fakepassword")
    server_generator(api)

    # Initial info.
    response = api.info()
    assert response.door1.temperature == 16.3
    assert response.door1.voltage == 40

    assert response.door2.temperature is None
    assert response.door2.voltage == 40

    assert response.door3.temperature == 16.3
    assert response.door3.voltage is None
