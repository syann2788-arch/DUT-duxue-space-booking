"""Offline encrypted PostgreSQL/public/private media snapshots; never stops writers.

Requires Python 3.12+, PostgreSQL 16 clients and age. Empty restore targets only;
migration is a separate operation with a checked DATABASE_URL.
"""
import hashlib
import json
import os
from pathlib import Path, PurePosixPath
import shutil
import subprocess
import sys
import tarfile
import tempfile
from datetime import datetime, timezone
from urllib.parse import unquote, urlsplit
from uuid import uuid4


def required(key):
    value = os.environ.get(key, "").strip()
    if not value:
        raise RuntimeError(f"缺少环境变量 {key}")
    return value


def command(args, *, output=False):
    result = subprocess.run(args, capture_output=True, text=True)
    if result.returncode:
        raise RuntimeError(f"{Path(args[0]).name} 执行失败，退出码 {result.returncode}；检查受控环境配置")
    return result.stdout.strip() if output else None


def target(url):
    try:
        parsed = urlsplit(url)
        if parsed.scheme not in {"postgresql", "postgres", "postgresql+asyncpg"} or not parsed.hostname or parsed.query or parsed.fragment:
            raise ValueError()
        name = unquote(parsed.path.lstrip("/"))
        if not name or "/" in name or not parsed.username:
            raise ValueError()
        return (parsed.hostname.lower(), parsed.port or 5432, name, unquote(parsed.username))
    except ValueError:
        raise RuntimeError("数据库URL必须为明确的PostgreSQL主机/端口/库名/用户，不支持查询参数") from None


def native_url():
    url = required("POSTGRES_BACKUP_URL")
    if urlsplit(url).scheme not in {"postgresql", "postgres"}:
        raise RuntimeError("POSTGRES_BACKUP_URL必须使用postgresql://，不能使用asyncpg驱动URL")
    return url


def sql(url, statement):
    return command(["psql", "--no-psqlrc", "--tuples-only", "--no-align", "--set=ON_ERROR_STOP=1", "--dbname", url, "--command", statement], output=True)


def checksum(file):
    digest = hashlib.sha256()
    with file.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def media_paths():
    public = Path(required("UPLOAD_DIR")).resolve()
    private = Path(required("PRIVATE_UPLOAD_DIR")).resolve()
    if public == private or public in private.parents or private in public.parents:
        raise RuntimeError("公开/私密媒体目录必须独立，不能重叠")
    return {"public": public, "private": private}


def backup():
    if required("BACKUP_WRITES_STOPPED") != "yes":
        raise RuntimeError("先停止所有API、worker、导入等写入和清理，再设置BACKUP_WRITES_STOPPED=yes")
    url = native_url()
    endpoint = target(url)
    paths = media_paths()
    for directory in paths.values():
        if not directory.is_dir():
            raise RuntimeError("媒体目录不存在，拒绝不完整备份")
    recipient = required("BACKUP_AGE_RECIPIENT")
    base = Path(required("BACKUP_DIR")).resolve()
    if any(base == directory or directory in base.parents for directory in paths.values()):
        raise RuntimeError("备份目录不能位于媒体目录中")
    base.mkdir(parents=True, exist_ok=True, mode=0o700)
    name = "snapshot-" + datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ") + "-" + uuid4().hex[:8]
    with tempfile.TemporaryDirectory(prefix=".plain-", dir=base) as temporary:
        work = Path(temporary)
        encrypted = work / "bundle"
        encrypted.mkdir(mode=0o700)
        revision = sql(url, "SELECT version_num FROM alembic_version")
        command(["pg_dump", "--format=custom", "--no-owner", "--no-acl", "--file", str(work / "database.dump"), url])
        with tarfile.open(work / "media.tar.gz", "w:gz", dereference=True) as archive:
            for kind, directory in paths.items():
                archive.add(directory, arcname=kind, recursive=False)
                for item in sorted(directory.rglob("*")):
                    if item.is_symlink() or not (item.is_file() or item.is_dir()):
                        raise RuntimeError("媒体目录包含链接或特殊文件，拒绝备份")
                    archive.add(item, arcname=f"{kind}/{item.relative_to(directory).as_posix()}", recursive=False)
        files = []
        for plain in ("database.dump", "media.tar.gz"):
            destination = encrypted / (plain + ".age")
            command(["age", "-r", recipient, "-o", str(destination), str(work / plain)])
            files.append({"path": destination.name, "size": destination.stat().st_size, "sha256": checksum(destination)})
        manifest = {"schemaVersion": 1, "createdAt": datetime.now(timezone.utc).isoformat(),
                    "schemaRevision": revision, "sourceCommit": os.environ.get("BACKUP_SOURCE_COMMIT", "unknown"),
                    "sourceDatabase": {"host": endpoint[0], "port": endpoint[1], "name": endpoint[2]}, "files": files}
        (encrypted / "manifest.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n")
        encrypted.rename(base / name)
    print(f"备份完成: {base / name}")


def restore():
    if required("RESTORE_WRITES_STOPPED") != "yes":
        raise RuntimeError("先停止目标环境所有写入，再设置RESTORE_WRITES_STOPPED=yes")
    url = native_url()
    endpoint = target(url)
    migration_url = required("DATABASE_URL")
    if urlsplit(migration_url).scheme != "postgresql+asyncpg":
        raise RuntimeError("迁移DATABASE_URL必须使用postgresql+asyncpg://")
    if endpoint != target(migration_url):
        raise RuntimeError("恢复与迁移DATABASE_URL目标不一致，拒绝恢复")
    if required("RESTORE_TARGET_CONFIRM") != endpoint[2]:
        raise RuntimeError("RESTORE_TARGET_CONFIRM必须等于目标库名")
    paths = media_paths()
    for directory in paths.values():
        directory.mkdir(parents=True, exist_ok=True)
        if any(directory.iterdir()):
            raise RuntimeError("目标媒体目录必须为空，拒绝混入其他恢复点")
        probe = directory / (".write-check-" + uuid4().hex)
        probe.write_bytes(b"")
        probe.unlink()
    bundle = Path(required("BACKUP_SET"))
    manifest = json.loads((bundle / "manifest.json").read_text())
    if manifest.get("schemaVersion") != 1 or {f["path"] for f in manifest["files"]} != {"database.dump.age", "media.tar.gz.age"} or len(manifest["files"]) != 2:
        raise RuntimeError("不支持或不完整的备份清单")
    for file in manifest["files"]:
        location = bundle / file["path"]
        if location.stat().st_size != file["size"] or checksum(location) != file["sha256"]:
            raise RuntimeError("备份文件校验失败，尚未写入数据库")
    identity = required("BACKUP_AGE_IDENTITY")
    with tempfile.TemporaryDirectory(prefix="duxue-restore-") as temporary:
        work = Path(temporary)
        for plain in ("database.dump", "media.tar.gz"):
            command(["age", "-d", "-i", identity, "-o", str(work / plain), str(bundle / (plain + ".age"))])
        with tarfile.open(work / "media.tar.gz", "r:gz") as archive:
            for member in archive.getmembers():
                name = PurePosixPath(member.name)
                if name.is_absolute() or ".." in name.parts or not name.parts or name.parts[0] not in paths or not (member.isfile() or member.isdir()):
                    raise RuntimeError("媒体归档包含不安全路径或链接，拒绝恢复")
            archive.extractall(work / "media", filter="data")
        if any(not (work / "media" / kind).is_dir() for kind in paths):
            raise RuntimeError("媒体归档缺少公开或私密目录，尚未写入数据库")
        command(["pg_restore", "--list", str(work / "database.dump")])
        objects = sql(url, "SELECT count(*) FROM pg_class c JOIN pg_namespace n ON n.oid=c.relnamespace WHERE n.nspname='public'")
        if objects != "0":
            raise RuntimeError("目标数据库public schema必须为空，禁止直接覆盖现有库")
        command(["pg_restore", "--exit-on-error", "--single-transaction", "--no-owner", "--no-acl", "--dbname", url, str(work / "database.dump")])
        if sql(url, "SELECT version_num FROM alembic_version") != manifest["schemaRevision"]:
            raise RuntimeError("恢复后的schema revision与备份不一致，保持停写排查")
        for kind, directory in paths.items():
            shutil.copytree(work / "media" / kind, directory, dirs_exist_ok=True)
    print("恢复完成；保持停写，先校正媒体属主并使用已核对的DATABASE_URL执行alembic upgrade head，再启动API/worker验收")


if __name__ == "__main__":
    os.umask(0o077)
    try:
        if len(sys.argv) != 2 or sys.argv[1] not in {"backup", "restore"}:
            raise RuntimeError("用法: backup_restore.py backup|restore")
        {"backup": backup, "restore": restore}[sys.argv[1]]()
    except (RuntimeError, OSError, ValueError, KeyError, tarfile.TarError) as exc:
        print(f"备份/恢复失败: {exc}", file=sys.stderr)
        sys.exit(1)
