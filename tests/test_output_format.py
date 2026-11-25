from fio_cli.main import _format_response


def test_format_bytes_as_plain_text() -> None:
	resp = b"a,b\\r\\n1,2\\r\\n"
	out = _format_response(resp, pretty=False)
	assert out == "a,b\\r\\n1,2\\r\\n"


def test_format_string_passthrough() -> None:
	out = _format_response("hello", pretty=False)
	assert out == "hello"


def test_format_object_as_minified_json_by_default() -> None:
	out = _format_response({"b": 1, "a": 2}, pretty=False)
	assert out == '{"a":2,"b":1}'


def test_format_object_as_pretty_json_when_pretty_enabled() -> None:
	out = _format_response({"b": 1, "a": 2}, pretty=True)
	assert out == '{\n\t"a": 2,\n\t"b": 1\n}'


def test_pretty_csv_string_is_converted_to_tsv() -> None:
	out = _format_response("a,b\n1,2\n", pretty=True, is_csv=True)
	assert out == "a\tb\n1\t2\n"


def test_csv_not_prettified_without_pretty_flag() -> None:
	out = _format_response("a,b\n1,2\n", pretty=False, is_csv=True)
	assert out == "a,b\n1,2\n"
