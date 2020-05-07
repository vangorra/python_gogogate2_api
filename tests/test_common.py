"""Tests for common code."""
from xml.etree.ElementTree import Element  # nosec

from defusedxml import ElementTree
from gogogate2_api.common import (
    DoorStatus,
    TagNotFoundException,
    TextEmptyException,
    UnexpectedTypeException,
    element_text_or_raise,
    enum_or_raise,
    int_or_raise,
    str_or_raise,
)
import pytest


def test_element_exceptions() -> None:
    """Test exceptions thrown while parsing xml elements."""
    root_element: Element = ElementTree.fromstring(
        """
            <response>
                <tag1></tag1>
                <tag2>value</tag2>
            </response>
        """
    )

    with pytest.raises(TagNotFoundException) as exinfo:
        element_text_or_raise(root_element, "tag3")
        assert exinfo.value.tag == "tag3"

    with pytest.raises(TextEmptyException) as exinfo:
        element_text_or_raise(root_element, "tag1")
        assert exinfo.value.tag == "tag1"

    with pytest.raises(UnexpectedTypeException) as exinfo:
        int_or_raise(element_text_or_raise(root_element, "tag2"))
        assert exinfo.value.value == "value"
        assert exinfo.value.expected == int


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
