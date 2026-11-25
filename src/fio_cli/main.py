from __future__ import annotations

import json as jsonlib
import re
import hashlib
from csv import reader, writer
from collections import defaultdict
from difflib import get_close_matches
from io import StringIO
from typing import Annotated, Any

import jmespath
import typer
from jmespath.exceptions import JMESPathError

from .config import load_config
from .errors import AuthConfigError, CliUsageError, TransportError, UpstreamRequestError, fail
from .manifest import Endpoint, endpoint_map, load_endpoints
from .sdk_adapter import call_get

app = typer.Typer(no_args_is_help=True, help="FIO CLI")


def _parse_query(items: list[str]) -> dict[str, str]:
	query: dict[str, str] = {}
	for item in items:
		if "=" not in item:
			raise CliUsageError(f"Invalid --query value '{item}'. Use key=value")
		k, v = item.split("=", 1)
		k = k.strip()
		if not k:
			raise CliUsageError(f"Invalid --query value '{item}'. Empty key")
		query[k] = v
	return query


def _group_for(path: str) -> str:
	parts = path.strip("/").split("/")
	return parts[0] if parts else "misc"


def _clean_summary(text: str) -> str:
	return re.sub(r"\s*#\s*noqa:\s*E501\s*$", "", text).strip()


def _endpoint_meta(ep: Endpoint) -> dict[str, object]:
	return {
		"endpoint": ep.path,
		"method": ep.method,
		"summary": _clean_summary(ep.summary) if ep.summary else None,
		"params": [
			{
				"name": p.get("name"),
				"in": p.get("in"),
				"required": bool(p.get("required")),
			}
			for p in ep.params
		],
		"response_type": ep.response_type,
		"auth": ep.auth,
		"examples": {
			"get": f"fio get {ep.path.lstrip('/')}",
			"filter_jmespath": f"fio get {ep.path.lstrip('/')} --filter \"[0]\"",
		},
	}


def _complete_endpoint(incomplete: str):
	for path in sorted(endpoint_map().keys()):
		if path.startswith(incomplete):
			yield path


def _resolve_endpoint(path: str, endpoints: dict[str, Endpoint]) -> Endpoint | None:
	exact = endpoints.get(path)
	if exact is not None:
		return exact
	for template, endpoint in endpoints.items():
		pattern = "^" + re.sub(r"\\\{[^/]+\\\}", r"[^/]+", re.escape(template)) + "$"
		if re.match(pattern, path):
			return endpoint
	return None


def _resolve_or_exit(path: str, endpoints: dict[str, Endpoint]) -> Endpoint:
	ep = _resolve_endpoint(path, endpoints)
	if ep is not None:
		return ep
	typer.echo(f"Unknown endpoint: {path}", err=True)
	suggest = get_close_matches(path, list(endpoints.keys()), n=5, cutoff=0.25)
	if suggest:
		typer.echo("Did you mean:", err=True)
		for s in suggest:
			typer.echo(f"\t{s}", err=True)
	raise typer.Exit(code=2)


def _config_values_ci() -> dict[str, str]:
	return {k.replace("_", "").lower(): v for k, v in load_config().items() if v}


def _resolve_path_parameters(path: str) -> str:
	if not re.search(r"\{[^{}\/]+\}", path):
		return path
	config = _config_values_ci()

	def replace(match: re.Match[str]) -> str:
		name = match.group(1)
		value = config.get(name.replace("_", "").lower())
		if not value:
			raise CliUsageError(f"No config value for path parameter {{{name}}}; provide a value in the path.")
		return value

	return re.sub(r"\{([^{}\/]+)\}", replace, path)


def _csv_to_tsv(text: str) -> str:
	in_buf = StringIO(text)
	rows = list(reader(in_buf))
	out_buf = StringIO()
	w = writer(out_buf, delimiter="\t", lineterminator="\n")
	w.writerows(rows)
	return out_buf.getvalue()


def _csv_to_rows(text: str) -> list[dict[str, str]]:
	rows = list(reader(StringIO(text)))
	if not rows:
		return []
	headers = rows[0]
	out: list[dict[str, str]] = []
	for raw in rows[1:]:
		row = {h: raw[i] if i < len(raw) else "" for i, h in enumerate(headers)}
		out.append(row)
	return out


def _rows_to_delimited_text(rows: list[dict[str, Any]], *, pretty: bool) -> str:
	if not rows:
		return ""
	headers: list[str] = []
	seen: set[str] = set()
	for row in rows:
		for k in row:
			if k not in seen:
				seen.add(k)
				headers.append(k)
	out_buf = StringIO()
	w = writer(out_buf, delimiter="\t" if pretty else ",", lineterminator="\n")
	w.writerow(headers)
	for row in rows:
		w.writerow([row.get(h, "") for h in headers])
	return out_buf.getvalue()


def _looks_like_tabular_rows(value: object) -> bool:
	return isinstance(value, list) and all(isinstance(item, dict) for item in value)


def _apply_filter(data: object, expr: str) -> object:
	return jmespath.search(expr, data)


def _type_name(value: object) -> str:
	if value is None:
		return "null"
	if isinstance(value, bool):
		return "bool"
	if isinstance(value, (int, float)):
		return "number"
	if isinstance(value, str):
		return "string"
	if isinstance(value, list):
		return "array"
	if isinstance(value, dict):
		return "object"
	return "mixed"


def _merge_types(types: set[str]) -> str:
	return next(iter(types)) if len(types) == 1 else "mixed"


def _collect_json_shape(value: object, path: str, out: dict[str, set[str]]) -> None:
	key = path or "$"
	out.setdefault(key, set()).add(_type_name(value))
	if isinstance(value, dict):
		for k, v in value.items():
			child = f"{path}.{k}" if path else k
			_collect_json_shape(v, child, out)
	elif isinstance(value, list):
		for item in value:
			child = f"{path}[]" if path else "[]"
			_collect_json_shape(item, child, out)


def _shape_for_json(value: object) -> dict[str, object]:
	shape: dict[str, set[str]] = {}
	_collect_json_shape(value, "", shape)
	fields = [{"path": p, "type": _merge_types(t)} for p, t in sorted(shape.items(), key=lambda i: i[0])]
	return {
		"root_type": _type_name(value),
		"fields": fields,
	}


def _infer_csv_column_types(rows: list[dict[str, str]]) -> list[dict[str, str]]:
	if not rows:
		return []
	cols = list(rows[0].keys())
	out: list[dict[str, str]] = []
	for col in cols:
		types: set[str] = set()
		for row in rows:
			v = row.get(col, "")
			if v == "":
				types.add("null")
				continue
			if v.lower() in {"true", "false"}:
				types.add("bool")
				continue
			try:
				float(v)
				types.add("number")
				continue
			except ValueError:
				pass
			types.add("string")
		out.append({"name": col, "type": _merge_types(types)})
	return out


def _as_text(resp: object) -> str | None:
	if isinstance(resp, bytes):
		return resp.decode("utf-8", errors="replace")
	if isinstance(resp, bytearray):
		return bytes(resp).decode("utf-8", errors="replace")
	if isinstance(resp, str):
		return resp
	return None


def _echo_output(text: str) -> None:
	typer.echo(text, nl=not text.endswith("\n"))


def _shape_for_csv(text: str) -> dict[str, object]:
	csv_rows = reader(StringIO(text))
	headers = next(csv_rows, None)
	if headers is None:
		return {"root_type": "array", "row_count": 0, "columns": []}
	rows_sample: list[dict[str, str]] = []
	row_count = 0
	for raw in csv_rows:
		row_count += 1
		if len(rows_sample) < 200:
			rows_sample.append({h: raw[i] if i < len(raw) else "" for i, h in enumerate(headers)})
	return {
		"root_type": "array",
		"row_count": row_count,
		"columns": _infer_csv_column_types(rows_sample),
	}


def _format_response(resp: object, *, pretty: bool, is_csv: bool=False) -> str:
	text = _as_text(resp)
	if text is not None:
		return _csv_to_tsv(text) if pretty and is_csv else text
	if pretty:
		return jsonlib.dumps(resp, indent="\t", sort_keys=True, default=str)
	return jsonlib.dumps(resp, separators=(",", ":"), sort_keys=True, default=str)


def _context_payload() -> dict[str, object]:
	# Match runtime auth resolution used by requests.
	config = load_config()
	api_key = config.get("fio_rest_key", "")
	username = config.get("user_name", "")
	cx = config.get("cx_code", "")
	fingerprint = hashlib.sha256(api_key.encode("utf-8")).hexdigest()[:12] if api_key else None
	return {
		"username": username or None,
		"cx": cx or None,
		"fio_api_key_present": bool(api_key),
		"fio_api_key_fingerprint": fingerprint,
	}


@app.command("list")
def list_commands() -> None:
	"""List available commands and GET endpoints."""
	typer.echo("Commands:")
	typer.echo("\tlist\tList commands and endpoint catalog")
	typer.echo("\tsearch\tSearch endpoint catalog")
	typer.echo("\tget\tExecute GET request for endpoint")
	typer.echo("\tshape\tDescribe endpoint response structure")
	typer.echo("\tcontext\tShow resolved runtime context")
	typer.echo("")
	groups: dict[str, list[Endpoint]] = defaultdict(list)
	for ep in load_endpoints():
		if ep.method != "GET":
			continue
		groups[_group_for(ep.path)].append(ep)
	for grp in sorted(groups):
		typer.echo(f"[{grp}]")
		for ep in sorted(groups[grp], key=lambda i: i.path):
			s = _clean_summary(ep.summary or "")
			typer.echo(f"\t{ep.path.lstrip('/')}\t{s}")


@app.command("search")
def search_commands(term: str) -> None:
	"""Fuzzy search endpoint catalog."""
	term_l = term.lower().strip()
	if not term_l:
		raise typer.Exit(code=0)
	endpoints = [e for e in load_endpoints() if e.method == "GET"]
	matches = [
		e
		for e in endpoints
		if term_l in e.path.lower() or term_l in (e.summary or "").lower()
	]
	if not matches:
		paths = [e.path.lstrip("/") for e in endpoints]
		suggest = get_close_matches(term_l, paths, n=5, cutoff=0.3)
		typer.echo("No endpoint matches.")
		if suggest:
			typer.echo("Did you mean:")
			for s in suggest:
				typer.echo(f"\t{s}")
		raise typer.Exit(code=0)
	for e in sorted(matches, key=lambda x: x.path):
		typer.echo(f"{e.path.lstrip('/')}\t{_clean_summary(e.summary or '')}")


@app.command("context")
def show_context(
	pretty: Annotated[bool, typer.Option("--pretty", help="Pretty output mode")]=False,
) -> None:
	"""Show resolved runtime context for analysis/data queries."""
	if pretty:
		typer.echo(jsonlib.dumps(_context_payload(), indent="\t", sort_keys=True))
	else:
		typer.echo(jsonlib.dumps(_context_payload(), separators=(",", ":"), sort_keys=True))


@app.command(
	"get",
	context_settings={"allow_extra_args": True, "ignore_unknown_options": True},
)
def get_endpoint(
	endpoint: Annotated[str, typer.Argument(autocompletion=_complete_endpoint)],
	query: Annotated[list[str], typer.Option("--query", "-q", hidden=True)]=[],
	pretty: Annotated[bool, typer.Option("--pretty", help="Pretty output mode")]=False,
	filter_expr: Annotated[str | None, typer.Option("--filter", help="Client-side JMESPath filter expression")]=None,
) -> None:
	"""Call an SDK GET endpoint by path."""
	endpoints = endpoint_map()
	path = endpoint.strip().strip("/")
	_resolve_or_exit(path, endpoints)

	try:
		path = _resolve_path_parameters(path)
		q = _parse_query(query)
		resp = call_get(path, q)
		is_csv = path.startswith("csv/")
		if filter_expr is not None:
			if is_csv:
				raw_text = _format_response(resp, pretty=False, is_csv=True)
				filtered = _apply_filter(_csv_to_rows(raw_text), filter_expr)
				if _looks_like_tabular_rows(filtered):
					out = _rows_to_delimited_text(filtered, pretty=pretty)  # type: ignore[arg-type]
				elif isinstance(filtered, dict):
					out = _rows_to_delimited_text([filtered], pretty=pretty)
				else:
					out = _format_response(filtered, pretty=pretty, is_csv=False)
			else:
				filtered = _apply_filter(resp, filter_expr)
				out = _format_response(filtered, pretty=pretty, is_csv=False)
		else:
			out = _format_response(resp, pretty=pretty, is_csv=is_csv)
		_echo_output(out)
	except JMESPathError as exc:
		fail(f"Invalid JMESPath --filter expression: {exc}", 2)
	except CliUsageError as exc:
		fail(str(exc), 2)
	except AuthConfigError as exc:
		fail(str(exc), 3)
	except UpstreamRequestError as exc:
		fail(str(exc), 4)
	except TransportError as exc:
		fail(str(exc), 5)
	except Exception as exc:  # noqa: BLE001
		fail(f"Unknown internal failure: {exc}", 1)


@app.command("shape")
def shape_endpoint(
	endpoint: Annotated[str, typer.Argument(autocompletion=_complete_endpoint)],
	query: Annotated[list[str], typer.Option("--query", "-q", hidden=True)]=[],
	pretty: Annotated[bool, typer.Option("--pretty", help="Pretty output mode")]=False,
) -> None:
	"""Describe response structure for an endpoint (use this to craft JMESPath filters)."""
	endpoints = endpoint_map()
	path = endpoint.strip().strip("/")
	ep = _resolve_or_exit(path, endpoints)
	try:
		path = _resolve_path_parameters(path)
		q = _parse_query(query)
		resp = call_get(path, q)
		if path.startswith("csv/"):
			raw_text = _format_response(resp, pretty=False, is_csv=True)
			data_shape = _shape_for_csv(raw_text)
		else:
			data_shape = _shape_for_json(resp)
		shape = {
			"endpoint_meta": _endpoint_meta(ep),
			"data_shape": data_shape,
		}
		out = _format_response(shape, pretty=pretty, is_csv=False)
		_echo_output(out)
	except CliUsageError as exc:
		fail(str(exc), 2)
	except AuthConfigError as exc:
		fail(str(exc), 3)
	except UpstreamRequestError as exc:
		fail(str(exc), 4)
	except TransportError as exc:
		fail(str(exc), 5)
	except Exception as exc:  # noqa: BLE001
		fail(f"Unknown internal failure: {exc}", 1)


def main() -> None:
	app()


if __name__ == "__main__":
	main()
