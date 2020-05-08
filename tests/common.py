"""Common test code."""
import json
from typing import Any, Dict
from urllib.parse import parse_qs, urlparse

from gogogate2_api import SHARED_SECRET, ApiCipher
from gogogate2_api.common import DoorMode, DoorStatus
import responses


class MockGogoGateServer:
    """Mock server."""

    def __init__(
        self,
        host: str,
        username: str = "username1",
        password: str = "password1",
        api_code: str = "api_code1",
    ):
        """Init object."""
        self.host = host
        self.username: str = username
        self.password: str = password
        self.api_code: str = api_code
        self.http_status: int = 200
        self._cipher = ApiCipher(SHARED_SECRET)
        self._devices: Dict[int, dict] = {
            1: {
                "permission": "yes",
                "name": "Gate",
                "mode": DoorMode.GARAGE.value,
                "status": DoorStatus.CLOSED.value,
                "sensor": "yes",
                "sensorid": "WIRE",
                "camera": "no",
                "events": 1234,
            },
            2: {
                "permission": "yes",
                "name": "Garage",
                "mode": DoorMode.GARAGE.value,
                "status": DoorStatus.OPENED.value,
                "sensor": "yes",
                "sensorid": "WIRE",
                "camera": "no",
                "events": 4321,
                "temperature": 13,
            },
            3: {
                "permission": "yes",
                "name": None,
                "mode": DoorMode.GARAGE.value,
                "status": DoorStatus.UNDEFINED.value,
                "sensor": "no",
                "camera": "no",
                "events": 0,
            },
        }

        responses.add_callback(
            responses.GET, f"http://{self.host}/api.php", callback=self._handle_request
        )

    def set_device_status(self, device_id: int, status: str) -> None:
        """Set the status of a device."""
        self._devices[device_id]["status"] = status

    # pylint: disable=too-many-return-statements
    def _handle_request(self, request: Any) -> tuple:
        # Simulate an HTTP error.
        if self.http_status != 200:
            return self._new_response("")

        # Parse the request.
        query = parse_qs(urlparse(request.url).query)
        data = query["data"][0]

        try:
            decrypted = self._cipher.decrypt(data.encode("utf-8"))
            payload = json.loads(decrypted)
            username = payload[0]
            password = payload[1]
            command = payload[2]
            door_id = payload[3]
            api_code = payload[4]
        except Exception:  # pylint: disable=broad-except
            return self._error_response(11, "Error: corrupted data")

        # Validate credentials.
        if username is None or password is None:
            return self._error_response(2, "Error: login or password not set")

        if username != self.username or password != self.password:
            return self._error_response(1, "Error: wrong login or password")

        if command == "info":
            return self._info_response()

        if command != "activate":
            return self._error_response(9, "Error: invalid option")

        if api_code != self.api_code:
            return self._error_response(18, "Error: invalid API code")

        if not door_id.isdigit():
            return self._error_response(8, "Error: door not set")

        door = self._devices.get(int(door_id))
        if not door:
            return self._error_response(5, "Error: invalid door")

        if not door["name"]:
            return self._new_response(
                """
                    <result>OK</result>
                """
            )

        current_status = door["status"]
        door["status"] = (
            DoorStatus.CLOSED.value
            if current_status == DoorStatus.OPENED.value
            else DoorStatus.OPENED.value
        )

        return self._new_response(
            """
                <result>OK</result>
            """
        )

    def _device_to_xml_str(self, device_id: int) -> str:
        device_dict: dict = self._devices[device_id]
        return "\n".join(
            [f"<{key}>{value}</{key}>" for key, value in device_dict.items()]
        )

    def _info_response(self) -> tuple:
        return self._new_response(
            f"""
                <user>{self.username}</user>
                <gogogatename>home</gogogatename>
                <model>GGG2</model>
                <apiversion>1.5</apiversion>
                <remoteaccessenabled>0</remoteaccessenabled>
                <remoteaccess>abcdefg12345.my-gogogate.com</remoteaccess>
                <firmwareversion>260\n</firmwareversion>
                <apicode>{self.api_code}</apicode>
                <door1>
                    {self._device_to_xml_str(1)}
                </door1>
                <door2>
                    {self._device_to_xml_str(2)}
                </door2>
                <door3>
                    <permission>yes</permission>
                    <name></name>
                    <mode>garage</mode>
                    <status>undefined</status>
                    <sensor>no</sensor>
                    <camera>no</camera>
                    <events>0</events>
                </door3>
                <outputs>
                    <output1>off</output1>
                    <output2>off</output2>
                    <output3>off</output3>
                </outputs>
                <network>
                    <ip>127.0.1.1</ip>
                </network>
                <wifi>
                    <SSID></SSID>
                    <linkquality>61%</linkquality>
                    <signal>-67 dBm</signal>
                </wifi>
            """
        )

    def _error_response(self, code: int, message: str) -> tuple:
        return self._new_response(
            f"""
                <error>
                    <errorcode>{code}</errorcode>
                    <errormsg>{message}</errormsg>
                </error>
            """
        )

    def _new_response(self, xml_str: str) -> tuple:
        return (
            self.http_status,
            {},
            self._cipher.encrypt(
                f"""<?xml version="1.0"?>
                    <response>
                         {xml_str}
                    </response>
                """
            ),
        )
