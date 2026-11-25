import pytest
from typer.testing import CliRunner

from fio_cli.errors import CliUsageError
from fio_cli.main import _resolve_endpoint, _resolve_path_parameters, app
from fio_cli.manifest import Endpoint


def _mk(path: str) -> Endpoint:
	return Endpoint(
		path=f"/{path}",
		method="GET",
		api_class="UserApi",
		sdk_method="x",
		summary="",
		params=[],
		response_type=None,
		auth=[],
	)


def test_resolve_exact_match_preferred() -> None:
	endpoints = {
		"user/{UserName}": _mk("user/{UserName}"),
		"user/me": _mk("user/me"),
	}
	result = _resolve_endpoint("user/me", endpoints)
	assert result is not None
	assert result.path == "/user/me"


def test_resolve_template_match() -> None:
	endpoints = {
		"user/{UserName}": _mk("user/{UserName}"),
	}
	result = _resolve_endpoint("user/73nkins", endpoints)
	assert result is not None
	assert result.path == "/user/{UserName}"


def test_resolve_template_segment_count_must_match() -> None:
	endpoints = {
		"user/{UserName}": _mk("user/{UserName}"),
	}
	assert _resolve_endpoint("user/73nkins/extra", endpoints) is None


def test_placeholder_uses_config_value(monkeypatch) -> None:
	monkeypatch.setattr("fio_cli.main.load_config", lambda: {"user_name": "73nkins"})
	assert _resolve_path_parameters("rain/userplanets/{UserName}") == "rain/userplanets/73nkins"


def test_missing_placeholder_value_reports_error(monkeypatch) -> None:
	monkeypatch.setattr("fio_cli.main.load_config", lambda: {})
	with pytest.raises(CliUsageError, match="UserName"):
		_resolve_path_parameters("user/{UserName}")


@pytest.mark.parametrize("command", ["get", "shape"])
def test_commands_resolve_placeholders_and_require_segments(monkeypatch, command) -> None:
	monkeypatch.setattr("fio_cli.main.load_config", lambda: {"user_name": "73nkins"})
	monkeypatch.setattr("fio_cli.main.endpoint_map", lambda: {"user/{UserName}": _mk("user/{UserName}")})
	seen = []
	monkeypatch.setattr("fio_cli.main.call_get", lambda path, query: seen.append(path) or {})
	runner = CliRunner()
	assert runner.invoke(app, [command, "user/{UserName}"]).exit_code == 0
	assert seen == ["user/73nkins"]
	assert runner.invoke(app, [command, "user"]).exit_code == 2
	assert runner.invoke(app, [command, "user/other"]).exit_code == 0
	assert seen[-1] == "user/other"


