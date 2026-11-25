from fio_cli.main import (
	_apply_filter,
	_csv_to_rows,
	_rows_to_delimited_text,
	_shape_for_csv,
	_shape_for_json,
)


def test_apply_filter_nested_json() -> None:
	data = {
		"items": [
			{"ticker": "H2O", "price": 5},
			{"ticker": "ORE", "price": 8},
		]
	}
	out = _apply_filter(data, "items[?ticker=='H2O'].price | [0]")
	assert out == 5


def test_apply_filter_scalar_json() -> None:
	data = {"meta": {"exchange": "NC1"}}
	out = _apply_filter(data, "meta.exchange")
	assert out == "NC1"


def test_csv_rows_parse_and_filter() -> None:
	csv_text = "Ticker,Price\nH2O,5\nORE,8\n"
	rows = _csv_to_rows(csv_text)
	assert rows == [{"Ticker": "H2O", "Price": "5"}, {"Ticker": "ORE", "Price": "8"}]
	out = _apply_filter(rows, "[?Ticker=='ORE']")
	assert out == [{"Ticker": "ORE", "Price": "8"}]


def test_rows_to_delimited_text_csv_and_tsv() -> None:
	rows = [{"Ticker": "H2O", "Price": "5"}]
	assert _rows_to_delimited_text(rows, pretty=False) == "Ticker,Price\nH2O,5\n"
	assert _rows_to_delimited_text(rows, pretty=True) == "Ticker\tPrice\nH2O\t5\n"


def test_csv_indexed_single_row_keeps_tabular_output() -> None:
	csv_text = "Ticker,CX,Price\nRAT,IC1,12\nRAT,NC1,13\n"
	rows = _csv_to_rows(csv_text)
	filtered = _apply_filter(rows, "[?Ticker=='RAT' && CX=='IC1'] | [0]")
	assert isinstance(filtered, dict)
	assert _rows_to_delimited_text([filtered], pretty=False) == "Ticker,CX,Price\nRAT,IC1,12\n"


def test_shape_for_json_includes_paths_and_types() -> None:
	shape = _shape_for_json({"a": 1, "b": [{"c": "x"}]})
	assert shape["root_type"] == "object"
	fields = {f["path"]: f["type"] for f in shape["fields"]}  # type: ignore[index]
	assert fields["$"] == "object"
	assert fields["a"] == "number"
	assert fields["b"] == "array"
	assert fields["b[]"] == "object"
	assert fields["b[].c"] == "string"


def test_shape_for_csv_has_columns() -> None:
	shape = _shape_for_csv("Ticker,Price,Active\nH2O,5,true\nORE,8,false\n")
	assert shape["root_type"] == "array"
	assert shape["row_count"] == 2
	cols = {c["name"]: c["type"] for c in shape["columns"]}  # type: ignore[index]
	assert cols["Ticker"] == "string"
	assert cols["Price"] == "number"
	assert cols["Active"] == "bool"
