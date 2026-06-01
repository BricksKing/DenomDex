from __future__ import annotations

import importlib
import logging
import os
import tomllib
from pathlib import Path
from typing import Any

from django.apps import AppConfig

log = logging.getLogger("admin_panel.extra_apps")


def find_repo_root() -> Path:
    cwd = Path.cwd()

    for base in [cwd, *cwd.parents]:
        if (base / "bdextra.py").is_file() and (base / "ballsdex").is_dir():
            return base

    # When settings are imported from admin_panel/settings/*.py
    return Path(__file__).resolve().parents[2]


def find_extra_toml() -> Path | None:
    candidates: list[Path] = []

    env_path = os.environ.get("BALLSDEXBOT_EXTRA_TOML")
    if env_path:
        candidates.append(Path(env_path))

    root = find_repo_root()

    candidates.extend(
        [
            root / "config" / "extra.toml",
            root / "admin_panel" / "config" / "extra.toml",
        ]
    )

    seen: set[Path] = set()

    for candidate in candidates:
        try:
            resolved = candidate.resolve()
        except OSError:
            continue

        if resolved in seen:
            continue

        seen.add(resolved)

        if resolved.is_file():
            return resolved

    return None


def load_extra_toml() -> dict[str, Any]:
    extra_toml = find_extra_toml()

    if extra_toml is None:
        return {}

    with extra_toml.open("rb") as file:
        return tomllib.load(file)


def find_app_config_path(package_path: str) -> str | None:
    """
    package_path is from extra.toml:

        path = "collector"

    This imports:

        collector.apps

    Then finds an AppConfig class and returns:

        collector.apps.CollectorConfig
    """
    try:
        apps_module = importlib.import_module(f"{package_path}.apps")
    except Exception:
        log.exception("Could not import %s.apps", package_path)
        return None

    for attr_name in dir(apps_module):
        attr = getattr(apps_module, attr_name)

        if not isinstance(attr, type):
            continue

        if not issubclass(attr, AppConfig):
            continue

        if attr is AppConfig:
            continue

        if getattr(attr, "name", None) != package_path:
            continue

        return f"{package_path}.apps.{attr.__name__}"

    # fallback: accept any AppConfig subclass with dpy_package
    for attr_name in dir(apps_module):
        attr = getattr(apps_module, attr_name)

        if (
            isinstance(attr, type)
            and issubclass(attr, AppConfig)
            and attr is not AppConfig
            and getattr(attr, "dpy_package", None)
        ):
            return f"{package_path}.apps.{attr.__name__}"

    log.warning("No AppConfig found for package path %s", package_path)
    return None


def get_extra_installed_apps() -> list[str]:
    data = load_extra_toml()
    raw_packages = data.get("ballsdex", {}).get("packages", [])

    installed_apps: list[str] = []

    for package in raw_packages:
        if not package.get("enabled", False):
            continue

        package_path = package.get("path")
        if not package_path:
            continue

        app_config_path = find_app_config_path(package_path)

        if app_config_path:
            installed_apps.append(app_config_path)

    return installed_apps
