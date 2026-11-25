from __future__ import annotations

import tomllib
from pathlib import Path

from .errors import AuthConfigError


def load_config(*, cwd: Path | None = None, home: Path | None = None) -> dict[str, str]:
	project_path = (cwd or Path.cwd()) / "config.toml"
	user_path = (home or Path.home()) / ".config" / "prun-ai" / "config.toml"
	for path in (project_path, user_path):
		if not path.is_file():
			continue
		try:
			data = tomllib.loads(path.read_text())
		except tomllib.TOMLDecodeError as exc:
			raise AuthConfigError(f"Invalid config.toml: {exc}") from exc
		return {key: value.strip() for key, value in data.items() if isinstance(value, str)}
	return {}
