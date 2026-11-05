"""Application paths and Hermes environment discovery.

Everything the workbench needs is local. Hermes credentials are read at runtime
from the Hermes home directory and are never copied into the workbench DB.
"""
from __future__ import annotations

import os
from pathlib import Path
from typing import Any

PROJECT_ROOT = Path(__file__).resolve().parents[2]
DATA_DIR = PROJECT_ROOT / "data"
BACKUP_DIR = DATA_DIR / "backups"
WEB_DIST = PROJECT_ROOT / "web" / "dist"
LOG_DIR = DATA_DIR / "logs"

for _directory in (DATA_DIR, BACKUP_DIR, LOG_DIR):
    _directory.mkdir(parents=True, exist_ok=True)

DB_PATH = Path(os.environ.get("WORKBENCH_DB", DATA_DIR / "workbench.db"))

HERMES_HOME = Path(os.environ.get("HERMES_HOME", r"D:\.hermes"))
HERMES_DB = Path(os.environ.get("HERMES_DB", HERMES_HOME / "state.db"))
HERMES_BIN = Path(os.environ.get("HERMES_BIN", HERMES_HOME / "bin" / "hermes.exe"))
HERMES_ENV = Path(os.environ.get("HERMES_ENV", HERMES_HOME / ".env"))
HERMES_CONFIG = Path(os.environ.get("HERMES_CONFIG", HERMES_HOME / "config.yaml"))
HERMES_CHANNEL_DIR = Path(
    os.environ.get("HERMES_CHANNEL_DIR", HERMES_HOME / "channel_directory.json")
)

DEFAULT_DEEPSEEK_BASE_URL = "https://api.deepseek.com/v1"
DEFAULT_DEEPSEEK_MODEL = "deepseek-v4-flash"
DEFAULT_TIMEZONE = "Asia/Shanghai"

DEFAULT_TAXONOMY: dict[str, Any] = {
    "categories": [
        {
            "name": "产品研发",
            "color": "#5B7CFA",
            "description": "需求、开发、测试与发布",
            "subcategories": ["需求与设计", "开发实现", "测试验证", "发布上线"],
        },
        {
            "name": "客户与项目",
            "color": "#22C55E",
            "description": "售前方案、客户交付与技术支持",
            "subcategories": ["售前方案", "客户交付", "技术支持"],
        },
        {
            "name": "内容与市场",
            "color": "#8B5CF6",
            "description": "内容创作、市场活动与竞品研究",
            "subcategories": ["内容创作", "市场活动", "竞品研究"],
        },
        {
            "name": "运营与管理",
            "color": "#F59E0B",
            "description": "工作复盘、流程制度与团队协作",
            "subcategories": ["工作复盘", "流程制度", "团队协作"],
        },
        {
            "name": "其他",
            "color": "#64748B",
            "description": "跨部门、临时事项与其他工作",
            "subcategories": ["跨部门", "临时事项"],
        },
    ],
    "work_types": [
        "方案与售前",
        "内容创作",
        "技术研发",
        "测试验证",
        "客户交付",
        "技术支持",
        "会议与培训",
        "运营支持",
        "竞品研究",
        "复盘与管理",
        "其他",
    ],
}

LOCAL_CONFIG_PATH = Path(os.environ.get("WORKBENCH_CONFIG", DATA_DIR / "local.json"))


def read_local_config() -> dict[str, Any]:
    """Read optional local overrides. This file is never committed."""
    try:
        import json

        data = json.loads(LOCAL_CONFIG_PATH.read_text(encoding="utf-8"))
        return data if isinstance(data, dict) else {}
    except (OSError, ValueError):
        return {}


def taxonomy_config() -> dict[str, Any]:
    local = read_local_config().get("taxonomy") or {}
    categories = local.get("categories")
    if not isinstance(categories, list) or not categories:
        categories = DEFAULT_TAXONOMY["categories"]
    work_types = local.get("work_types")
    if not isinstance(work_types, list) or not work_types:
        work_types = DEFAULT_TAXONOMY["work_types"]
    return {"categories": categories, "work_types": work_types}


def _default_deliverable_roots() -> list[dict[str, Any]]:
    local = read_local_config().get("deliverable_roots")
    if isinstance(local, list) and local:
        return [item for item in local if isinstance(item, dict) and item.get("path")]

    roots: list[dict[str, Any]] = []
    outputs = os.environ.get("HERMES_OUTPUTS")
    if not outputs:
        candidate = HERMES_HOME / "outputs"
        outputs = str(candidate) if candidate.exists() else ""
    if outputs:
        roots.append(
            {
                "label": "Hermes 输出",
                "path": outputs,
                "enabled": True,
                "depth": 4,
            }
        )
    roots.extend(
        [
            {
                "label": "桌面",
                "path": str(Path.home() / "Desktop"),
                "enabled": True,
                "depth": 4,
            },
            {
                "label": "下载",
                "path": str(Path.home() / "Downloads"),
                "enabled": False,
                "depth": 3,
            },
            {
                "label": "文档",
                "path": str(Path.home() / "Documents"),
                "enabled": False,
                "depth": 3,
            },
        ]
    )
    return roots


DEFAULT_DELIVERABLE_ROOTS = _default_deliverable_roots()

DEFAULT_EXCLUDE_GLOBS = [
    "**/node_modules/**",
    "**/.git/**",
    "**/.venv/**",
    "**/venv/**",
    "**/__pycache__/**",
    "**/.pytest_cache/**",
    "**/.idea/**",
    "**/.vscode/**",
    "**/$RECYCLE.BIN/**",
    "**/System Volume Information/**",
    "**/archive/**",
    "**/backup/**",
    "**/backups/**",
    "**/Tencent Files/**",
    "**/BaiduNetdiskTmp/**",
    "**/OneNote 笔记本/**",
    "*.tmp",
    "*.lock",
    "*.db-wal",
    "*.db-shm",
]

DEFAULT_INCLUDE_EXT = [
    ".docx", ".doc", ".xlsx", ".xls", ".pptx", ".ppt", ".pdf", ".md", ".txt",
    ".html", ".htm", ".csv", ".json", ".png", ".jpg", ".jpeg", ".gif", ".svg",
    ".webp", ".mp4", ".mov", ".mp3", ".wav", ".zip", ".7z",
]


def read_hermes_env() -> dict[str, str]:
    """Parse KEY=VALUE pairs from the Hermes .env without exporting them."""
    values: dict[str, str] = {}
    if not HERMES_ENV.exists():
        return values
    try:
        for raw_line in HERMES_ENV.read_text(encoding="utf-8", errors="replace").splitlines():
            line = raw_line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, _, value = line.partition("=")
            value = value.strip().strip('"').strip("'")
            values[key.strip()] = value
    except OSError:
        return {}
    return values


def get_secret(name: str) -> str | None:
    value = os.environ.get(name)
    if value:
        return value
    return read_hermes_env().get(name)


def detect_feishu_target() -> str | None:
    """Return the first Feishu DM target advertised by Hermes."""
    try:
        import json

        data = json.loads(HERMES_CHANNEL_DIR.read_text(encoding="utf-8"))
        for channel in data.get("platforms", {}).get("feishu", []):
            chat_id = channel.get("id")
            if chat_id:
                return f"feishu:{chat_id}"
    except (OSError, ValueError, KeyError):
        pass
    return None


def hermes_home_status() -> dict[str, Any]:
    return {
        "hermes_home": str(HERMES_HOME),
        "hermes_db": str(HERMES_DB),
        "hermes_db_exists": HERMES_DB.exists(),
        "hermes_bin": str(HERMES_BIN),
        "hermes_bin_exists": HERMES_BIN.exists(),
        "hermes_env_exists": HERMES_ENV.exists(),
        "feishu_target": detect_feishu_target(),
        "deepseek_key_present": bool(get_secret("DEEPSEEK_API_KEY")),
    }
