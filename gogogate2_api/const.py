"""Constants for gogogate2"""
from enum import IntEnum


class ApiErrorCode(IntEnum):
    """Common API error codes."""

    CORRUPTED_DATA = 11
    CREDENTIALS_NOT_SET = 2
    CREDENTIALS_INCORRECT = 1
    INVALID_OPTION = 9
    INVALID_API_CODE = 18
    DOOR_NOT_SET = 8
    INVALID_DOOR = 5
