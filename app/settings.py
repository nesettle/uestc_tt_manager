from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field
from typing import Any

from app.runtime import get_runtime_paths, initialize_runtime_environment


RUNTIME_PATHS = initialize_runtime_environment()
PROJECT_ROOT = RUNTIME_PATHS.project_root
RESOURCE_ROOT = RUNTIME_PATHS.resource_root
USER_DATA_ROOT = RUNTIME_PATHS.user_data_root
DATA_DIR = RUNTIME_PATHS.data_dir
RUNS_DIR = RUNTIME_PATHS.runs_dir
FORM_EXPORTS_DIR = RUNTIME_PATHS.form_exports_dir
BROWSER_STATE_DIR = RUNTIME_PATHS.browser_state_dir
STATIC_DIR = RUNTIME_PATHS.static_dir
TEMPLATES_DIR = RUNTIME_PATHS.templates_dir
VENDOR_DIR = RUNTIME_PATHS.vendor_dir
CONFIG_PATH = RUNTIME_PATHS.config_path
QUALIFICATION_MASTER_PATH = RUNTIME_PATHS.qualification_master_path
DEFAULT_NAPCAT_CONFIG_PATH = ""
DEFAULT_NOTIFY_TEMPLATE = (
    "{name}同学你好，我是乒协机器人，这边发现你在正赛资格名单中，但单打项目报名表中没有你的信息。"
    "请你确认是否参加成电杯单打项目，如果参加，请填写群里的单打报名链接。"
)


@dataclass
class FormBinding:
    title: str = ""
    entries_url: str = ""


@dataclass
class DiscoveredForm:
    title: str
    url: str
    entries_url: str
    updated_at: str = ""


@dataclass
class AppConfig:
    qualification_form: FormBinding = field(default_factory=FormBinding)
    singles_form: FormBinding = field(default_factory=FormBinding)
    doubles_form: FormBinding = field(default_factory=FormBinding)
    team_form: FormBinding = field(default_factory=FormBinding)
    event_group_id: str = ""
    jinshuju_home_url: str = "https://jinshuju.net/home"
    jinshuju_profile_dir: str = str(BROWSER_STATE_DIR / "jinshuju_profile")
    napcat_config_path: str = DEFAULT_NAPCAT_CONFIG_PATH
    notify_template: str = DEFAULT_NOTIFY_TEMPLATE
    discovered_forms: list[DiscoveredForm] = field(default_factory=list)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "AppConfig":
        def parse_binding(key: str) -> FormBinding:
            raw = data.get(key) or {}
            return FormBinding(
                title=str(raw.get("title", "")).strip(),
                entries_url=str(raw.get("entries_url", "")).strip(),
            )

        discovered_forms = []
        for item in data.get("discovered_forms", []) or []:
            title = str(item.get("title", "")).strip()
            url = str(item.get("url", "")).strip()
            entries_url = str(item.get("entries_url", "")).strip()
            updated_at = str(item.get("updated_at", "")).strip()
            if title or url or entries_url:
                discovered_forms.append(
                    DiscoveredForm(
                        title=title,
                        url=url,
                        entries_url=entries_url,
                        updated_at=updated_at,
                    )
                )

        return cls(
            qualification_form=parse_binding("qualification_form"),
            singles_form=parse_binding("singles_form"),
            doubles_form=parse_binding("doubles_form"),
            team_form=parse_binding("team_form"),
            event_group_id=str(data.get("event_group_id", "")).strip(),
            jinshuju_home_url=str(data.get("jinshuju_home_url", "https://jinshuju.net/home")).strip()
            or "https://jinshuju.net/home",
            jinshuju_profile_dir=str(
                data.get("jinshuju_profile_dir", str(BROWSER_STATE_DIR / "jinshuju_profile"))
            ).strip()
            or str(BROWSER_STATE_DIR / "jinshuju_profile"),
            napcat_config_path=str(data.get("napcat_config_path", DEFAULT_NAPCAT_CONFIG_PATH)).strip()
            or DEFAULT_NAPCAT_CONFIG_PATH,
            notify_template=str(data.get("notify_template", DEFAULT_NOTIFY_TEMPLATE)).strip() or DEFAULT_NOTIFY_TEMPLATE,
            discovered_forms=discovered_forms,
        )

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def ensure_directories() -> None:
    initialize_runtime_environment()


def load_config() -> AppConfig:
    ensure_directories()
    if not CONFIG_PATH.exists():
        config = AppConfig()
        save_config(config)
        return config
    return AppConfig.from_dict(json.loads(CONFIG_PATH.read_text(encoding="utf-8")))


def save_config(config: AppConfig) -> None:
    ensure_directories()
    CONFIG_PATH.write_text(
        json.dumps(config.to_dict(), ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
