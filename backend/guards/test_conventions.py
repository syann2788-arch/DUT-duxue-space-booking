"""Convention guard tests (eng-vibe step 2).

These are NOT business tests. They AST-scan source files to assert the project's
most expensive conventions hold, so divergence fails the gate in <1s instead of
shipping as a double-booking / timezone / split-state bug. Each guard is paired
with a 【守护】annotation in AGENTS.md.

Run standalone (no DB, no app import):
    cd backend && python -m pytest guards/ -q
"""
from __future__ import annotations

import ast
from pathlib import Path

REPOSITORY_ROOT = Path(__file__).resolve().parents[2]
APP_DIR = Path(__file__).resolve().parent.parent / "app"
ROUTER_DIR = APP_DIR / "routers"
PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
SOURCE_ROOTS = (
    REPOSITORY_ROOT / "backend" / "app",
    REPOSITORY_ROOT / "backend" / "tests",
    REPOSITORY_ROOT / "miniprogram",
)
TEXT_SUFFIXES = {".py", ".js", ".json", ".wxml", ".wxss"}
EXCLUDED_DIRS = {"node_modules", "dist", "unpackage", ".uni-src", "__pycache__"}


def controlled_source_files():
    for root in SOURCE_ROOTS:
        for path in root.rglob("*"):
            if not path.is_file() or path.suffix.lower() not in TEXT_SUFFIXES:
                continue
            if any(part in EXCLUDED_DIRS for part in path.parts):
                continue
            yield path


def test_controlled_source_scan_is_utf8_and_bounded():
    files = list(controlled_source_files())
    assert files
    assert len(files) < 300
    for path in files:
        path.read_text(encoding="utf-8")


def test_production_guards_and_private_response_models_remain_present():
    config_source = (REPOSITORY_ROOT / "backend" / "app" / "config.py").read_text(encoding="utf-8")
    schema_source = (REPOSITORY_ROOT / "backend" / "app" / "schemas.py").read_text(encoding="utf-8")
    service_source = (REPOSITORY_ROOT / "backend" / "app" / "services.py").read_text(encoding="utf-8")
    assert "validate_runtime_settings" in config_source
    assert 'value.startswith("/uploads/cleanup_")' in schema_source
    assert "class ReservationBaseOut" in schema_source
    assert "Reservation.date >= recent_cutoff" in service_source


def _python_files(root: Path):
    yield from root.rglob("*.py")


def _parse(path: Path) -> ast.AST | None:
    try:
        return ast.parse(path.read_text(encoding="utf-8"))
    except SyntaxError:
        return None


def test_occupying_statuses_defined_only_in_services():
    """OCCUPYING_STATUSES / DAILY_LIMIT_STATUSES are the single source for
    "which reservation statuses occupy a slot / count toward the daily limit".
    Redefining them elsewhere is the classic double-booking divergence: the new
    copy drifts when a status is added, and one path books over the other.
    【守护: AGENTS.md 关键设计决策 - 状态机】"""
    offenders = []
    for path in _python_files(APP_DIR):
        tree = _parse(path)
        if tree is None:
            continue
        for node in ast.walk(tree):
            if isinstance(node, ast.Assign):
                for target in node.targets:
                    if isinstance(target, ast.Name) and target.id in {"OCCUPYING_STATUSES", "DAILY_LIMIT_STATUSES"}:
                        if path.name != "services.py":
                            offenders.append(f"{path.name}:{node.lineno} 重新定义了 {target.id}")
    assert not offenders, "OCCUPYING_STATUSES 必须只在 app/services.py 定义:\n" + "\n".join(offenders)


DOMAIN_ENUMS = {
    "UserRole", "SceneType", "UsageMode", "ReservationStatus", "ReviewDecision",
    "CleanupStatus", "RestrictionLevel", "NotificationType", "NotificationStatus",
    "PublicStatus", "ViolationType",
}


def test_domain_enums_defined_only_in_models():
    """State-machine enums have one source (models.py). A second definition
    silently splits the state space and breaks every .value comparison, every
    SAEnum column, and every status filter query.
    【守护: AGENTS.md 关键设计决策 - 状态机】"""
    offenders = []
    for path in _python_files(APP_DIR):
        tree = _parse(path)
        if tree is None:
            continue
        for node in ast.walk(tree):
            if isinstance(node, ast.ClassDef) and node.name in DOMAIN_ENUMS:
                if path.name != "models.py":
                    offenders.append(f"{path.name}:{node.lineno} 重复定义 {node.name}")
    assert not offenders, "领域枚举必须只在 app/models.py 定义:\n" + "\n".join(offenders)


def test_services_use_local_now_not_bare_datetime_now():
    """All "now" reads in business logic go through local_now() (Asia/Shanghai,
    naive, matching the Date + slot representation). A bare datetime.now() mixes
    UTC/local time and silently breaks every cancel-deadline, checkin-grace and
    violation comparison.
    【守护: AGENTS.md 关键设计决策 - 时区】"""
    services = APP_DIR / "services.py"
    tree = _parse(services)
    assert tree is not None, "services.py 解析失败"
    offenders = []
    for node in ast.walk(tree):
        if (isinstance(node, ast.Call)
                and isinstance(node.func, ast.Attribute)
                and node.func.attr == "now"
                and isinstance(node.func.value, ast.Name)
                and node.func.value.id == "datetime"):
            offenders.append(f"services.py:{node.lineno} 用了 datetime.now()，应改用 local_now()")
    assert not offenders, "services.py 必须用 local_now()，禁止 datetime.now():\n" + "\n".join(offenders)


def test_routers_do_not_perform_time_arithmetic():
    """AGENTS.md: 所有时间校验(取消截止、签到宽限)在 services.py 内完成，不在
    router 层。Routers importing timedelta is the leading indicator of
    deadline/grace logic leaking into the thin layer and running outside the
    booking transaction. `date`/`datetime` for type hints & filenames are fine.
    【守护: AGENTS.md 关键设计决策 - 数据流】"""
    offenders = []
    for path in sorted(ROUTER_DIR.glob("*.py")):
        tree = _parse(path)
        if tree is None:
            continue
        for node in ast.walk(tree):
            if isinstance(node, ast.ImportFrom) and node.module and node.module.startswith("datetime"):
                for alias in node.names:
                    if alias.name == "timedelta":
                        offenders.append(f"{path.name}:{node.lineno} 导入了 timedelta")
    assert not offenders, "router 层禁止 timedelta 时间运算，deadline/grace 校验须在 services.py:\n" + "\n".join(offenders)


def _read(path: Path) -> str:
    try:
        return path.read_text(encoding="utf-8")
    except (OSError, UnicodeError):
        return ""


def test_appsecret_never_reaches_frontend():
    """业务红线 #3: 微信 AppSecret 永不下发前端/小程序。前端目录里出现
    AppSecret / WECHAT_APP_SECRET / app_secret 是凭据泄露的直接指标--不是
    "会不会被调用"，而是"它根本不该出现在那里"。只扫前端目录，后端使用是
    合法的（code2session、订阅消息）。
    【守护: AGENTS.md 技术栈 - 后端密钥边界】"""
    offenders = []
    for name in ("miniprogram",):
        root = PROJECT_ROOT / name
        if not root.exists():
            continue
        for path in root.rglob("*"):
            if not path.is_file():
                continue
            if path.suffix.lower() in {".pyc", ".png", ".jpg", ".jpeg", ".gif", ".webp"}:
                continue
            text = _read(path)
            for needle in ("AppSecret", "WECHAT_APP_SECRET", "app_secret", "APP_SECRET"):
                if needle in text:
                    offenders.append(f"{path}: 出现 {needle}")
    assert not offenders, "前端目录禁止出现 AppSecret 相关字样（红线 #3）:\n" + "\n".join(offenders)


def test_canonical_guidance_no_v1_cloud_terms():
    """AGENTS.md 是唯一完整开发规范，不得残留第一版微信云开发调用术语。残留术语会让
    后续会话误以为还在用云函数/云数据库，是分状态机的典型源头。集合/record
    是云数据库术语，app.call/cloud.openapi/session_token 是 v1 调用模式。
    【守护: AGENTS.md 唯一正式运行链路】"""
    guidance = _read(PROJECT_ROOT / "AGENTS.md")
    offenders = []
    for needle in ("app.call", "cloud.openapi", "session_token", "users 集合", "reservations 集合"):
        if needle in guidance:
            offenders.append(f"AGENTS.md 残留 v1 术语: {needle}")
    assert not offenders, "AGENTS.md 不得残留 v1 云函数/云数据库调用术语:\n" + "\n".join(offenders)


def test_canonical_documents_keep_single_runtime_mainline():
    """AGENTS.md、README 和架构文档必须声明同一条正式运行链路。
    【守护: AGENTS.md 唯一正式运行链路】"""
    mainline_claims = {
        "AGENTS.md": "miniprogram",
        "README.md": "miniprogram",
        "docs/ARCHITECTURE.md": "miniprogram",
    }
    offenders = []
    for filename, expected in mainline_claims.items():
        path = PROJECT_ROOT / filename
        text = _read(path)
        if not text:
            offenders.append(f"{filename}: 文件缺失或为空")
            continue
        if expected not in text:
            offenders.append(f"{filename}: 未声明 {expected} 为主线")
        if "backend" not in text:
            offenders.append(f"{filename}: 未声明 backend 为后端")
    assert not offenders, "正式运行链路声明不一致:\n" + "\n".join(offenders)


def test_deprecated_parallel_implementations_do_not_return():
    """旧实现保留在 Git 历史，不得重新进入正式工作树或微信工程配置。
    【守护: AGENTS.md 唯一正式运行链路】"""
    offenders = []
    for name in ("frontend", "cloudfunctions"):
        if (PROJECT_ROOT / name).exists():
            offenders.append(f"仓库根目录重新出现已归档实现: {name}/")
    project_config = _read(PROJECT_ROOT / "project.config.json")
    for needle in ("cloudfunctionRoot", "cloudfunctionTemplateRoot"):
        if needle in project_config:
            offenders.append(f"project.config.json 重新出现 {needle}")
    assert not offenders, "不得恢复平行前端/后端:\n" + "\n".join(offenders)


DISALLOWED_BRAND_VALUES = {
    "#f25b15", "#b8430a", "#fef1ea", "#f5c9b0", "#6b46c1", "#f1edfb",
    "#6b2d8e", "#672987", "#7d3da0", "#9252b5", "#572073", "#8b4daf",
    "#f1e8f6", "#f1e7f7", "#f5eef9", "#f8f1fc", "#f8f1fb", "#eee8f1",
    "#dcd0e8", "#bda3ca", "#b0a0c0", "#d0c8d8", "#faf6fc", "#f6f5f8",
    "#f8f3fb", "#765589", "#e0cfee", "#e8e2ed", "#d7c5df",
}


def test_miniprogram_uses_approved_purple_ivory_palette():
    """正式小程序使用清华紫 #612276 + 米白 #F8F6FA。
    学长原型的橙紫和第一版散落的灰紫都不得重新成为品牌色；布局与交互可继续
    参考原型，品牌色以 app.wxss 为唯一源。
    【守护: AGENTS.md 微信前端主题约定】"""
    offenders = []
    root = PROJECT_ROOT / "miniprogram"
    if not root.exists():
        return
    for path in root.rglob("*"):
        if not path.is_file():
            continue
        if path.suffix.lower() not in {".wxss", ".wxml", ".json", ".js"}:
            continue
        text = _read(path)
        lower = text.lower()
        for disallowed in DISALLOWED_BRAND_VALUES:
            if disallowed in lower:
                for i, line in enumerate(text.splitlines(), 1):
                    if disallowed in line.lower():
                        offenders.append(f"{path.name}:{i} 残留未批准品牌色 {disallowed}")
    assert not offenders, "miniprogram 只允许清华紫 + 米白品牌体系:\n" + "\n".join(offenders)
