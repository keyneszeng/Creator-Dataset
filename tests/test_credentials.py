from app.core.credentials import parse_cookie_header


def test_parse_cookie_header() -> None:
    assert parse_cookie_header("a1=abc; web_session=xyz; empty=") == {
        "a1": "abc",
        "web_session": "xyz",
        "empty": "",
    }
