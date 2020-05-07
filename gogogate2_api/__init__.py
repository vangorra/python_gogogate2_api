"""Base package for gogogate2 API code."""
import base64
import json
from typing import Optional, cast
import uuid
from xml.etree.ElementTree import Element  # nosec

from Cryptodome.Cipher import AES
from Cryptodome.Cipher._mode_cbc import CbcMode
from defusedxml import ElementTree
import requests
from typing_extensions import Final

from .common import (
    DoorStatus,
    GogoGate2Response,
    element_to_api_error,
    element_to_info_response,
    get_door_by_id,
)

SHARED_SECRET: Final = "0e3b7%i1X9@54cAf"


class ApiCipher:
    """Cipher specific for encrypting calls to/from gogogate2 devices."""

    def __init__(self, key: str) -> None:
        """Initialize the object."""
        self._key: Final = key.encode("utf-8")

    def encrypt(self, raw: str) -> str:
        """Encrypt data going to a device."""
        raw_bytes: Final[bytes] = ApiCipher.pad(raw).encode("utf-8")
        init_vector: Final[bytes] = uuid.uuid4().hex[: AES.block_size].encode("utf-8")
        cipher = cast(CbcMode, AES.new(self._key, AES.MODE_CBC, init_vector))
        return str(init_vector + base64.b64encode(cipher.encrypt(raw_bytes)), "utf-8")

    def decrypt(self, enc: bytes) -> bytes:
        """Decrypt data from a device."""
        init_vector: Final[bytes] = enc[:16]
        b64_decoded_bytes: Final[bytes] = base64.b64decode(enc[16:])
        cipher = cast(CbcMode, AES.new(self._key, AES.MODE_CBC, init_vector))
        return ApiCipher.unpad(cipher.decrypt(b64_decoded_bytes))

    @staticmethod
    def pad(data: str) -> str:
        """Add padding to bytes."""
        block_size = 16
        return data + (block_size - len(data) % block_size) * chr(
            block_size - len(data) % block_size
        )

    @staticmethod
    def unpad(data: bytes) -> bytes:
        """Remove padding from bytes."""
        return data[0 : -data[-1]]


class GogoGate2Api:
    """API capable of communicating with a gogogate2 devices."""

    def __init__(self, host: str, username: str, password: str) -> None:
        """Initialize the object."""
        self._host: Final = host
        self._username: Final = username
        self._password: Final = password
        self._api_url: Final = f"http://{host}/api.php"
        self._api_cipher: Final[ApiCipher] = ApiCipher(SHARED_SECRET)
        self._api_code: Optional[str] = None

    def _request(
        self, action: str, arg1: Optional[str] = None, arg2: Optional[str] = None
    ) -> Element:
        command_str = json.dumps(
            (
                self._username,
                self._password,
                action,
                "" if arg1 is None else arg1,
                "" if arg2 is None else arg2,
            )
        )

        response = requests.get(
            self._api_url,
            params={"data": self._api_cipher.encrypt(command_str)},
            timeout=2,
        )

        response_text = self._api_cipher.decrypt(response.content)
        root_element: Element = ElementTree.fromstring(response_text)

        error_element = root_element.find("error")
        if error_element:
            raise element_to_api_error(error_element)

        return root_element

    def _handle_generic_response(self, element: Element) -> GogoGate2Response:
        response = element_to_info_response(element)
        self._api_code = response.apicode
        return response

    @property
    def api_code(self) -> Optional[str]:
        """Get the current api code."""
        return self._api_code

    def clear_api_code(self) -> None:
        """Clear the api key."""
        self._api_code = None

    def info(self) -> GogoGate2Response:
        """Get info about the device and doors."""
        return self._handle_generic_response(self._request("info"))

    def activate(self, door_id: int) -> GogoGate2Response:
        """Send a command to open/close/stop the door.

        Gogogate2 does not have a status for opening or closing. So running
        this method during an action will stop the door. It's recommended you
        use open_door() or close_door() as those methods check the status
        before running and run if needed."""
        if not self._api_code:
            self.info()

        return self._handle_generic_response(
            self._request("activate", str(door_id), self._api_code)
        )

    def _set_door_status(self, door_id: int, door_status: DoorStatus) -> bool:
        """Send call to open/close a door if door is not already in that state."""
        if door_status == DoorStatus.UNDEFINED:
            return False

        # Get current door status.
        response = self.info()
        door = get_door_by_id(door_id, response)

        # No door found.
        if door is None:
            return False

        # Door already at status.
        if door.status == door_status:
            return False

        self.activate(door_id)
        return True

    def close_door(self, door_id: int) -> bool:
        """Close a door.

        :return True if close command sent, False otherwise.
        """
        return self._set_door_status(door_id, DoorStatus.CLOSED)

    def open_door(self, door_id: int) -> bool:
        """Open a door.

        :return True if open command sent, False otherwise.
        """
        return self._set_door_status(door_id, DoorStatus.OPENED)
