from app.services.qa_service import validate_pair


def test_qa_happy_path() -> None:
    results = validate_pair("Hi {0} <b>x</b>|y", "Bonjour {A} <b>x</b>|y")
    assert all(r.ok for r in results)


def test_qa_detects_issues() -> None:
    results = validate_pair("A {0}|<b>x</b>", "A |<b>x</i>")
    as_map = {r.rule: r.ok for r in results}
    assert as_map["PLACEHOLDER_COUNT"] is False
    assert as_map["PIPE_COUNT"] is True
    assert as_map["TAG_WELL_FORMED"] is False
