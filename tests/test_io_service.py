from app.services.shared.io import (
    is_blank_value,
    normalize_content_value,
    normalize_non_content_value,
    safe_to_str,
)


def test_safe_to_str_and_blank_detection_follow_io_spec() -> None:
    assert safe_to_str(None) == ""
    assert safe_to_str("", strip=True) == ""
    assert safe_to_str("  a  ", strip=True) == "a"
    assert safe_to_str("  a  ", strip=False) == "  a  "
    assert safe_to_str(0, strip=True) == "0"
    assert safe_to_str(0.0, strip=True) == "0.0"
    assert safe_to_str(float("nan"), strip=True) == "nan"

    assert is_blank_value(None) is True
    assert is_blank_value("") is True
    assert is_blank_value("   ") is True
    assert is_blank_value(0) is False
    assert is_blank_value(0.0) is False
    assert is_blank_value(float("nan")) is False
    assert is_blank_value("nan") is False


def test_content_and_non_content_normalization_use_different_strip_rules() -> None:
    assert normalize_non_content_value("  welcome.title  ") == "welcome.title"
    assert normalize_non_content_value("   ") == ""

    assert normalize_content_value("  Bonjour  ") == "  Bonjour  "
    assert normalize_content_value("   ") == ""
    assert normalize_content_value(None) == ""
