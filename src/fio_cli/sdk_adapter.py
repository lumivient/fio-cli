from __future__ import annotations

from typing import Any

from fio_sdk import ApiClient, Configuration
from fio_sdk.rest import ApiException
import urllib3.exceptions

from .config import load_config
from .errors import AuthConfigError, TransportError, UpstreamRequestError

CSV_APIKEY_ENDPOINTS = {
	"csv/burnrate",
	"csv/cxos",
	"csv/inventory",
	"csv/sites",
	"csv/workforce",
}


def _normalize_query(path: str, query: dict[str, Any], api_key: str, username: str | None) -> dict[str, Any]:
	normalized = dict(query)
	p = path.strip().strip("/")
	if p in CSV_APIKEY_ENDPOINTS:
		if "apikey" not in normalized:
			normalized["apikey"] = api_key
		if "username" not in normalized and username:
			normalized["username"] = username
	return normalized


def call_get(path: str, query: dict[str, Any]) -> Any:
	config_values = load_config()
	api_key = config_values.get("fio_rest_key", "")
	username = config_values.get("user_name")
	if not api_key:
		raise AuthConfigError("fio_rest_key missing. Set it in config.toml")

	config = Configuration()
	config.api_key["Authorization"] = api_key
	client = ApiClient(configuration=config)
	normalized_query = _normalize_query(path, query, api_key, username)

	try:
		data = client.call_api(
			f"/{path.lstrip('/')}",
			"GET",
			query_params=list(normalized_query.items()) if normalized_query else None,
			auth_settings=["api_key"],
			response_type="object",
			_return_http_data_only=True,
		)
		return data
	except ApiException as exc:
		status = getattr(exc, "status", None)
		if status in (400, 404):
			raise UpstreamRequestError(f"Upstream request failed: HTTP {status}") from exc
		if status in (401, 403):
			raise AuthConfigError(
				f"Auth failed: HTTP {status}. Check fio_rest_key in config.toml and run `fio context` to verify loaded key fingerprint."
			) from exc
		raise UpstreamRequestError(f"Upstream API error: HTTP {status or 'unknown'}") from exc
	except (urllib3.exceptions.HTTPError, TimeoutError, ConnectionError) as exc:
		raise TransportError(f"Network/transport error: {exc}") from exc
