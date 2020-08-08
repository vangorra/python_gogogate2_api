"""Constants for gate devices"""
from enum import IntEnum


class GogoGate2ApiErrorCode(IntEnum):
    """Common API error codes."""

    CREDENTIALS_NOT_SET = 2
    CREDENTIALS_INCORRECT = 1
    INVALID_OPTION = 9
    CORRUPTED_DATA = 11

    INVALID_API_CODE = 18
    DOOR_NOT_SET = 8
    INVALID_DOOR = 5

    # These are not thrown by the api.
    INVALID_TOKEN = 998
    TOKEN_NOT_SET = 999


class ISmartGateApiErrorCode(IntEnum):
    """Common API error codes."""

    CREDENTIALS_NOT_SET = 22
    CREDENTIALS_INCORRECT = 11
    INVALID_OPTION = 9
    TOKEN_NOT_SET = 21
    INVALID_API_CODE = 10
    DOOR_NOT_SET = 8

    # These are not thrown by the api.
    INVALID_DOOR = 997
    INVALID_TOKEN = 998
    CORRUPTED_DATA = 999
