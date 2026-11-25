import fio_cli.sdk_adapter as sdk_adapter
from fio_cli.sdk_adapter import _normalize_query


def test_injects_apikey_for_csv_endpoint_when_missing() -> None:
	q = _normalize_query("csv/burnrate", {"username": "u"}, "k123", None)
	assert q["apikey"] == "k123"
	assert q["username"] == "u"


def test_does_not_override_existing_apikey() -> None:
	q = _normalize_query("csv/burnrate", {"apikey": "manual", "username": "u"}, "k123", "env-user")
	assert q["apikey"] == "manual"


def test_does_not_inject_for_other_endpoint() -> None:
	q = _normalize_query("user/73nkins", {}, "k123", "env-user")
	assert "apikey" not in q
	assert "username" not in q


def test_injects_username_for_csv_endpoint_when_missing() -> None:
	q = _normalize_query("csv/sites", {}, "k123", "env-user")
	assert q["apikey"] == "k123"
	assert q["username"] == "env-user"


def test_does_not_override_existing_username() -> None:
	q = _normalize_query("csv/sites", {"username": "cli-user"}, "k123", "env-user")
	assert q["username"] == "cli-user"


def test_call_get_uses_toml_credentials(monkeypatch) -> None:
	seen: dict[str, object] = {}

	class FakeClient:
		def __init__(self, configuration) -> None:
			seen["configuration"] = configuration

		def call_api(self, *args, **kwargs):
			seen["query_params"] = kwargs["query_params"]
			return {"ok": True}

	monkeypatch.setattr(sdk_adapter, "load_config", lambda: {"fio_rest_key": "key", "user_name": "user"})
	monkeypatch.setattr(sdk_adapter, "ApiClient", FakeClient)

	assert sdk_adapter.call_get("csv/sites", {}) == {"ok": True}
	assert seen["configuration"].api_key["Authorization"] == "key"  # type: ignore[index,union-attr]
	assert seen["query_params"] == [("apikey", "key"), ("username", "user")]
