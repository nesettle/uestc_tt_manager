from __future__ import annotations

import os
import subprocess
import sys
import importlib.util
from dataclasses import asdict, dataclass
from functools import lru_cache
from pathlib import Path
from typing import Any


APP_NAME = "UESTC TT Manager"
DESKTOP_ENV_FLAG = "UESTC_TT_DESKTOP_MODE"
USER_DATA_ENV = "UESTC_TT_USER_DATA_DIR"
PLAYWRIGHT_ENV = "PLAYWRIGHT_BROWSERS_PATH"
DEFAULT_APPDATA_SUBDIR = "UESTC TT Manager"


@dataclass(frozen=True)
class RuntimePaths:
    project_root: Path
    resource_root: Path
    user_data_root: Path
    desktop_mode: bool
    frozen: bool
    data_dir: Path
    runs_dir: Path
    form_exports_dir: Path
    browser_state_dir: Path
    static_dir: Path
    templates_dir: Path
    vendor_dir: Path
    config_path: Path
    qualification_master_path: Path
    bundled_playwright_dir: Path

    def to_dict(self) -> dict[str, Any]:
        payload = asdict(self)
        return {key: str(value) if isinstance(value, Path) else value for key, value in payload.items()}


def is_frozen() -> bool:
    return bool(getattr(sys, "frozen", False))


def is_desktop_mode() -> bool:
    return is_frozen() or os.getenv(DESKTOP_ENV_FLAG, "").strip() == "1"


def _source_project_root() -> Path:
    return Path(__file__).resolve().parents[1]


def _resource_root() -> Path:
    if is_frozen():
        meipass = getattr(sys, "_MEIPASS", "")
        if meipass:
            return Path(meipass).resolve()
        return Path(sys.executable).resolve().parent
    return _source_project_root()


def _user_data_root(project_root: Path) -> Path:
    override = os.getenv(USER_DATA_ENV, "").strip()
    if override:
        return Path(override).expanduser().resolve()
    if not is_desktop_mode():
        return project_root
    local_app_data = os.getenv("LOCALAPPDATA", "").strip()
    if local_app_data:
        return Path(local_app_data) / DEFAULT_APPDATA_SUBDIR
    return Path.home() / "AppData" / "Local" / DEFAULT_APPDATA_SUBDIR


@lru_cache(maxsize=1)
def get_runtime_paths() -> RuntimePaths:
    project_root = _source_project_root()
    resource_root = _resource_root()
    user_data_root = _user_data_root(project_root)
    data_dir = user_data_root / "data"
    runs_dir = user_data_root / "runs"
    form_exports_dir = data_dir / "form_exports"
    browser_state_dir = user_data_root / "browser_state"
    static_dir = resource_root / "app" / "static"
    templates_dir = resource_root / "app" / "templates"
    vendor_dir = resource_root / "vendor"
    config_path = data_dir / "config.json"
    qualification_master_path = data_dir / "qualification_master.xlsx"
    bundled_playwright_dir = resource_root / "ms-playwright"
    return RuntimePaths(
        project_root=project_root,
        resource_root=resource_root,
        user_data_root=user_data_root,
        desktop_mode=is_desktop_mode(),
        frozen=is_frozen(),
        data_dir=data_dir,
        runs_dir=runs_dir,
        form_exports_dir=form_exports_dir,
        browser_state_dir=browser_state_dir,
        static_dir=static_dir,
        templates_dir=templates_dir,
        vendor_dir=vendor_dir,
        config_path=config_path,
        qualification_master_path=qualification_master_path,
        bundled_playwright_dir=bundled_playwright_dir,
    )


def reset_runtime_paths_cache() -> None:
    get_runtime_paths.cache_clear()


def ensure_runtime_directories() -> RuntimePaths:
    paths = get_runtime_paths()
    for path in (paths.user_data_root, paths.data_dir, paths.runs_dir, paths.form_exports_dir, paths.browser_state_dir):
        path.mkdir(parents=True, exist_ok=True)
    return paths


def initialize_runtime_environment() -> RuntimePaths:
    paths = ensure_runtime_directories()
    if paths.bundled_playwright_dir.exists():
        os.environ.setdefault(PLAYWRIGHT_ENV, str(paths.bundled_playwright_dir))
    return paths


def explorer_open(path: Path) -> None:
    subprocess.Popen(["explorer.exe", str(path)])


def detect_webview2_version() -> str:
    try:
        import winreg
    except ImportError:
        return ""

    keys = [
        (winreg.HKEY_CURRENT_USER, r"Software\Microsoft\EdgeUpdate\Clients\{F3017226-FE2A-4295-8BDF-00C3A9A7E4C5}"),
        (winreg.HKEY_LOCAL_MACHINE, r"Software\Microsoft\EdgeUpdate\Clients\{F3017226-FE2A-4295-8BDF-00C3A9A7E4C5}"),
        (winreg.HKEY_LOCAL_MACHINE, r"Software\WOW6432Node\Microsoft\EdgeUpdate\Clients\{F3017226-FE2A-4295-8BDF-00C3A9A7E4C5}"),
    ]
    for hive, key_path in keys:
        try:
            with winreg.OpenKey(hive, key_path) as handle:
                value, _ = winreg.QueryValueEx(handle, "pv")
                version = str(value or "").strip()
                if version:
                    return version
        except OSError:
            continue
    return ""


def runtime_summary() -> dict[str, Any]:
    paths = initialize_runtime_environment()
    webview2_version = detect_webview2_version()
    return {
        "app_name": APP_NAME,
        "desktop_mode": paths.desktop_mode,
        "frozen": paths.frozen,
        "paths": paths.to_dict(),
        "webview2_installed": bool(webview2_version),
        "webview2_version": webview2_version,
        "qtpy_installed": importlib.util.find_spec("qtpy") is not None,
        "pyside6_installed": importlib.util.find_spec("PySide6") is not None,
        "bundled_playwright_exists": paths.bundled_playwright_dir.exists(),
        "playwright_browsers_path": os.getenv(PLAYWRIGHT_ENV, "").strip(),
    }
