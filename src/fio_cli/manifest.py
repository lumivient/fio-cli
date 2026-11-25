from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any


@dataclass(frozen=True)
class Endpoint:
	path: str
	method: str
	api_class: str
	sdk_method: str
	summary: str
	params: list[dict[str, Any]]
	response_type: str | None
	auth: list[str]


_CACHE: list[Endpoint] | None = None

# Endpoints matching any prefix here are hidden from CLI behavior.
# Prefixes are compared against normalized paths without a leading slash.
ENDPOINT_BLACKLIST_PREFIXES = (
	"auth",
	"admin",
	"chat",
	"contract/allcontracts/{UserName}",
	"contract/concerns/{UserName}",
	"contract/loans/{UserName}",
	"contract/taco",
	"usersettings",
	"version",
)


def _is_blacklisted(path: str) -> bool:
	normalized = path.lstrip("/")
	return any(
		normalized == prefix or normalized.startswith(f"{prefix}/")
		for prefix in ENDPOINT_BLACKLIST_PREFIXES
	)


def manifest_path() -> Path:
	return Path(__file__).resolve().parent / "endpoints.json"


def load_endpoints() -> list[Endpoint]:
	global _CACHE
	if _CACHE is not None:
		return _CACHE
	with manifest_path().open("r", encoding="utf-8") as f:
		raw = json.load(f)
	_CACHE = [Endpoint(**item) for item in raw if not _is_blacklisted(item["path"])]
	return _CACHE


def endpoint_map() -> dict[str, Endpoint]:
	return {e.path.lstrip("/"): e for e in load_endpoints() if e.method == "GET"}
