from pathlib import Path


REPOSITORY_ROOT = Path(__file__).resolve().parents[2]
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
