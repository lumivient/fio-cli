from __future__ import annotations

import ast
import json
from pathlib import Path
from typing import Any

import fio_sdk

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "src" / "fio_cli" / "endpoints.json"


def _str(node: ast.AST) -> str | None:
	if isinstance(node, ast.Constant) and isinstance(node.value, str):
		return node.value
	return None


def _extract_assign_list(fn: ast.FunctionDef, name: str) -> list[str]:
	for stmt in fn.body:
		if isinstance(stmt, ast.Assign):
			for target in stmt.targets:
				if isinstance(target, ast.Name) and target.id == name and isinstance(stmt.value, ast.List):
					vals: list[str] = []
					for item in stmt.value.elts:
						s = _str(item)
						if s is not None:
							vals.append(s)
					return vals
	return []


def _extract_call_api(fn: ast.FunctionDef) -> tuple[str, str, str | None] | None:
	for stmt in ast.walk(fn):
		if isinstance(stmt, ast.Call) and isinstance(stmt.func, ast.Attribute) and stmt.func.attr == "call_api":
			if len(stmt.args) >= 2:
				path = _str(stmt.args[0])
				method = _str(stmt.args[1])
				if path and method:
					resp_type = None
					for kw in stmt.keywords:
						if kw.arg == "response_type":
							resp_type = _str(kw.value)
					return path, method, resp_type
	return None


def _extract_params(fn: ast.FunctionDef) -> list[dict[str, Any]]:
	args = fn.args.args
	names = [a.arg for a in args if a.arg not in ("self", "kwargs")]
	return [{"name": n, "required": True, "in": "path"} for n in names]


def build_manifest() -> list[dict[str, Any]]:
	api_dir = Path(fio_sdk.__file__).resolve().parent / "api"
	items: list[dict[str, Any]] = []
	for file in sorted(api_dir.glob("*_api.py")):
		source = file.read_text(encoding="utf-8")
		mod = ast.parse(source)
		api_class = ""
		for node in mod.body:
			if isinstance(node, ast.ClassDef):
				api_class = node.name
				for fn in node.body:
					if not isinstance(fn, ast.FunctionDef):
						continue
					if not fn.name.endswith("_with_http_info"):
						continue
					pair = _extract_call_api(fn)
					if not pair:
						continue
					path, method, response_type = pair
					params = _extract_params(fn)
					auth = _extract_assign_list(fn, "auth_settings")
					summary = ast.get_docstring(fn) or ""
					items.append(
						{
							"path": path,
							"method": method,
							"api_class": api_class,
							"sdk_method": fn.name,
							"summary": summary.splitlines()[0].strip() if summary else "",
							"params": params,
							"response_type": response_type,
							"auth": auth,
						}
					)
	# de-dupe same method/path
	seen = set()
	unique = []
	for item in items:
		key = (item["method"], item["path"])
		if key in seen:
			continue
		seen.add(key)
		unique.append(item)
	return unique


def main() -> None:
	manifest = build_manifest()
	OUT.parent.mkdir(parents=True, exist_ok=True)
	OUT.write_text(json.dumps(manifest, indent=2, sort_keys=True), encoding="utf-8")
	print(f"wrote {OUT} with {len(manifest)} endpoints")


if __name__ == "__main__":
	main()
