from _core._utils import (
    digitToChar,
    str_base,
    parse_cookie_string,
    clearHTML,
    json_minimal,
    formatResults,
    randStr
)

def test_digitToChar():
    assert digitToChar(5) == "5"
    assert digitToChar(10) == "a"
    assert digitToChar(15) == "f"

def test_str_base():
    assert str_base(10, 36) == "a"
    assert str_base(35, 36) == "z"
    assert str_base(36, 36) == "10"
    assert str_base(-10, 36) == "-a"

def test_parse_cookie_string():
    cookie_str = "c_user=123; xs=abc; fr=xyz;"
    parsed = parse_cookie_string(cookie_str)
    assert parsed == {"c_user": "123", "xs": "abc", "fr": "xyz"}
    
    # Test empty or malformed
    assert parse_cookie_string("") == {}
    assert parse_cookie_string("just_a_string") == {}

def test_clearHTML():
    html = "<div>Hello <b>World</b></div>"
    assert clearHTML(html) == "Hello World"

def test_json_minimal():
    data = {"a": 1, "b": 2}
    # ensure no spaces around separators
    assert json_minimal(data) == '{"a":1,"b":2}'

def test_formatResults():
    res = formatResults("success", "Done")
    assert res == {"status": "success", "message": "Done"}

def test_randStr():
    s1 = randStr(10)
    s2 = randStr(10)
    assert len(s1) == 10
    assert len(s2) == 10
    assert s1 != s2
