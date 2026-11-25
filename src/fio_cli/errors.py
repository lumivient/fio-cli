from __future__ import annotations

import typer


class CliUsageError(Exception):
	pass


class AuthConfigError(Exception):
	pass


class UpstreamRequestError(Exception):
	pass


class TransportError(Exception):
	pass


def fail(message: str, code: int) -> None:
	typer.echo(message, err=True)
	raise typer.Exit(code=code)
