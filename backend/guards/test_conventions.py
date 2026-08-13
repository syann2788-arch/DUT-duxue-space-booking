"""Convention guard tests (eng-vibe step 2).

These are NOT business tests. They AST-scan source files to assert the project's
most expensive conventions hold, so divergence fails the gate in <1s instead of
shipping as a double-booking / timezone / split-state bug. Each guard is paired
with a 【守护】annotation in CLAUDE.md.

Run standalone (no DB, no app import):
    cd backend && python -m pytest guards/ -q
"""
from __future__ import annotations

import ast
import os
from pathlib import Path

APP_DIR = Path(__file__).resolve().parent.parent / "app"
ROUTER_DIR = APP_DIR / "routers"
PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
IGNORED_TREE_NAMES = {
    ".git", ".pytest_cache", ".venv", "__pycache__", "dist", "node_modules",
    "unpackage", "uploads",
}
FRONTEND_SOURCE_SUFFIXES = {
    ".css", ".html", ".js", ".json", ".jsx", ".md", ".ts", ".tsx",
    ".vue", ".wxml", ".wxss",
}


def _python_files(root: Path):
    yield from _source_files(root, {".py"})


def _source_files(root: Path, suffixes: set[str]):
    """Yield controlled source files without entering generated/dependency trees."""
    for current_root, directory_names, file_names in os.walk(root):
        directory_names[:] = [
            name for name in directory_names if name not in IGNORED_TREE_NAMES
        ]
        for file_name in file_names:
            path = Path(current_root) / file_name
            if path.suffix.lower() in suffixes:
                yield path


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
    【守护: CLAUDE.md 硬性技术约定 - 状态机】"""
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
    "PublicStatus", "ViolationType", "MediaPurpose",
}


def test_wechat_project_cannot_deploy_legacy_cloudfunctions():
    """The formal WeChat project may only expose the miniprogram entry."""
    import json

    config = json.loads(_read(PROJECT_ROOT / "project.config.json"))
    assert config.get("miniprogramRoot") == "miniprogram/"
    forbidden = {"cloudfunctionRoot", "cloudfunctionTemplateRoot", "cloud"}
    offenders = sorted(forbidden.intersection(config))
    assert not offenders, "正式微信项目配置不得暴露旧云函数入口: " + ", ".join(offenders)


def test_large_list_routes_are_bounded():
    """Formal clients must not reintroduce unbounded history reads."""
    reservation_router = _read(ROUTER_DIR / "reservations.py")
    admin_router = _read(ROUTER_DIR / "admin.py")
    assert '@router.get("/my", response_model=ReservationPageOut)' in reservation_router
    for route, response_model in (
        ('/reservations', 'ReservationAdminPageOut'),
        ('/cleanup', 'ReservationAdminPageOut'),
        ('/users', 'UserPageOut'),
    ):
        assert f'@router.get("{route}", response_model={response_model})' in admin_router
    for text in (reservation_router, admin_router):
        assert "le=100" in text, "长列表分页必须保留每页 100 条上限"


def test_domain_enums_defined_only_in_models():
    """State-machine enums have one source (models.py). A second definition
    silently splits the state space and breaks every .value comparison, every
    SAEnum column, and every status filter query.
    【守护: CLAUDE.md 硬性技术约定 - 状态机】"""
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
    【守护: CLAUDE.md 硬性技术约定 - 时区】"""
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
    """CLAUDE.md: 所有时间校验(取消截止、签到宽限)在 services.py 内完成，不在
    router 层。Routers importing timedelta is the leading indicator of
    deadline/grace logic leaking into the thin layer and running outside the
    booking transaction. `date`/`datetime` for type hints & filenames are fine.
    【守护: CLAUDE.md 硬性技术约定 - 数据流】"""
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
    【守护: CLAUDE.md 不可破坏的业务红线 #3】"""
    offenders = []
    for name in ("miniprogram", "frontend"):
        root = PROJECT_ROOT / name
        if not root.exists():
            continue
        for path in _source_files(root, FRONTEND_SOURCE_SUFFIXES):
            text = _read(path)
            for needle in ("AppSecret", "WECHAT_APP_SECRET", "app_secret", "APP_SECRET"):
                if needle in text:
                    offenders.append(f"{path}: 出现 {needle}")
    assert not offenders, "前端目录禁止出现 AppSecret 相关字样（红线 #3）:\n" + "\n".join(offenders)


def test_constitution_no_v1_cloud_terms():
    """CLAUDE.md 是 v2 宪法，不得残留第一版微信云开发的术语。残留术语会让
    后续会话误以为还在用云函数/云数据库，是分状态机的典型源头。集合/record
    是云数据库术语，app.call/cloud.openapi/session_token 是 v1 调用模式。
    【守护: CLAUDE.md 视觉规范唯一源 / 技术栈 v2 化】"""
    claude = _read(PROJECT_ROOT / "CLAUDE.md")
    offenders = []
    for needle in ("app.call", "cloud.openapi", "session_token", "users 集合", "reservations 集合"):
        if needle in claude:
            offenders.append(f"CLAUDE.md 残留 v1 术语: {needle}")
    assert not offenders, "CLAUDE.md 不得残留 v1 云函数/云数据库术语:\n" + "\n".join(offenders)


def test_constitution_frontend_mainline_consistent():
    """三份宪法级文档（CLAUDE.md / AGENTS.md / docs/ARCHITECTURE.md）对前端
    主线的声明必须一致。主线归属是方向性决策，文档互相矛盾会让每次会话重新
    争论"到底改哪个前端"。miniprogram 是正式 v2 主线是已拍板决策。
    【守护: CLAUDE.md 技术栈 - 前端主线】"""
    mainline_claims = {
        "CLAUDE.md": "miniprogram",
        "AGENTS.md": "miniprogram",
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
        for line in text.splitlines():
            stripped = line.strip()
            if "frontend" not in stripped:
                continue
            if "miniprogram" in stripped:
                continue
            if any(neg in stripped for neg in ("不是", "非主线", "参考", "仅作", "不作为", "废弃")):
                continue
            if "主线" in stripped or "交付" in stripped:
                offenders.append(f"{filename}: 可能把 frontend 声明为主线，与决策矛盾: {stripped}")
    assert not offenders, "三份宪法文档前端主线声明不一致:\n" + "\n".join(offenders)


LEGACY_PURPLE_VALUES = {
    "#6b2d8e", "#672987", "#7d3da0", "#9252b5", "#572073", "#8b4daf",
    "#f1e8f6", "#f1e7f7", "#f5eef9", "#f8f1fc", "#f8f1fb", "#eee8f1",
    "#dcd0e8", "#bda3ca", "#b0a0c0", "#d0c8d8", "#faf6fc", "#f6f5f8",
    "#f8f3fb", "#765589", "#e0cfee", "#e8e2ed", "#d7c5df",
}


def test_miniprogram_no_legacy_purple():
    """miniprogram/ 已从旧紫 #6b2d8e 体系迁移到橙紫(橙 #F25B15 + 紫 #6B46C1)。
    旧紫色值复现是迁移回退的直接指标--色值散落 15 文件 68 处的历史证明"靠记得"
    守不住，必须靠扫描。设计稿 colors_and_type.css 是视觉规范唯一源，旧紫不在
    该体系内。CLAUDE.md 待办已记录迁移完成。
    【守护: CLAUDE.md 视觉规范唯一源 / 工作约定 - UI 风格】"""
    offenders = []
    root = PROJECT_ROOT / "miniprogram"
    if not root.exists():
        return
    for path in _source_files(root, {".wxss", ".wxml", ".json", ".js"}):
        text = _read(path)
        lower = text.lower()
        for legacy in LEGACY_PURPLE_VALUES:
            if legacy in lower:
                for i, line in enumerate(text.splitlines(), 1):
                    if legacy in line.lower():
                        offenders.append(f"{path.name}:{i} 残留旧紫 {legacy}")
    assert not offenders, "miniprogram 不得残留旧紫色值(已迁移到橙紫):\n" + "\n".join(offenders)
