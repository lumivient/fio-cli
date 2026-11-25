from pathlib import Path

from fio_cli.config import load_config


def _write_config(path: Path, *, user_name: str) -> None:
	path.write_text(f'user_name = "{user_name}"\n')


def test_project_config_takes_priority_over_user_config(tmp_path: Path) -> None:
	project = tmp_path / "project"
	project.mkdir()
	home = tmp_path / "home"
	user_config = home / ".config" / "prun-ai" / "config.toml"
	user_config.parent.mkdir(parents=True)
	_write_config(project / "config.toml", user_name="project-user")
	_write_config(user_config, user_name="shared-user")

	assert load_config(cwd=project, home=home)["user_name"] == "project-user"


def test_user_config_is_used_when_project_config_is_absent(tmp_path: Path) -> None:
	project = tmp_path / "project"
	project.mkdir()
	home = tmp_path / "home"
	user_config = home / ".config" / "prun-ai" / "config.toml"
	user_config.parent.mkdir(parents=True)
	_write_config(user_config, user_name="shared-user")

	assert load_config(cwd=project, home=home)["user_name"] == "shared-user"
