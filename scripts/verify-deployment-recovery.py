"""Disposable Compose deployment/recovery rehearsal with synthetic data only.

Requires Docker, postgres:16-alpine, duxue-handover-local:01-02 and
 duxue-ops-local:05-11. Removes only the two randomly named projects it creates.
"""
import base64
from datetime import datetime, timedelta
import hashlib
import json
from pathlib import Path
import subprocess
import tempfile
import time
import urllib.error
import urllib.request
from uuid import uuid4
from zoneinfo import ZoneInfo

ROOT = Path(__file__).resolve().parents[1]
PROJECTS = ["duxue-check-" + uuid4().hex[:8] + suffix for suffix in ("-source", "-restore")]
IMAGE = base64.b64decode("iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8/x8AAwMCAO+a9zsAAAAASUVORK5CYII=")
PASSWORD = "RehearsalOnly1234"


def request(base, endpoint, payload=None, token=None, upload=False, raw=False):
    headers = {"Authorization": "Bearer " + token} if token else {}
    data = None
    if upload:
        boundary = "duxue" + uuid4().hex
        data = (f'--{boundary}\r\nContent-Disposition: form-data; name="file"; filename="test.png"\r\nContent-Type: image/png\r\n\r\n'.encode() + IMAGE + f"\r\n--{boundary}--\r\n".encode())
        headers["Content-Type"] = "multipart/form-data; boundary=" + boundary
    elif payload is not None:
        data = json.dumps(payload).encode()
        headers["Content-Type"] = "application/json"
    req = urllib.request.Request(base + endpoint, data=data, headers=headers)
    with urllib.request.urlopen(req, timeout=10) as response:
        content = response.read()
        return content if raw else json.loads(content)


with tempfile.TemporaryDirectory(prefix="duxue-deployment-") as temporary:
    work = Path(temporary)
    (work / "backups").mkdir(mode=0o700)
    (work / "keys").mkdir(mode=0o700)
    environment = work / "compose.env"
    environment.write_text(f"POSTGRES_PASSWORD=isolated-test-only\nSECRET_KEY={'isolated-test-' + 'x' * 40}\nAPP_ENV=production\nBACKUP_DIR={work / 'backups'}\nBACKUP_KEY_DIR={work / 'keys'}\nWECHAT_APP_ID=\n")
    environment.chmod(0o600)
    override = work / "override.yml"
    override.write_text('''services:
  api:
    image: duxue-handover-local:01-02
    pull_policy: never
    ports: !override ["127.0.0.1::8000"]
  migrate:
    image: duxue-handover-local:01-02
    pull_policy: never
  worker:
    image: duxue-handover-local:01-02
    pull_policy: never
  ops:
    image: duxue-ops-local:05-11
    pull_policy: never
''')

    def compose(project, *args, expected=0, message=None):
        command = ["docker", "compose", "--env-file", str(environment), "-f", str(ROOT / "docker-compose.yml"), "-f", str(override), "-p", project, *args]
        result = subprocess.run(command, cwd=ROOT, capture_output=True, text=True)
        if (expected == 0 and result.returncode != 0) or (expected != 0 and result.returncode == 0):
            raise RuntimeError(f"Compose rehearsal failed: {args[0]}\n{result.stdout[-1200:]}\n{result.stderr[-2000:]}")
        if message and message not in result.stdout + result.stderr:
            raise RuntimeError(f"Expected rejection missing: {message}\n{result.stderr[-1000:]}")
        return result.stdout.strip()

    def sql(project, statement):
        return compose(project, "exec", "-T", "db", "psql", "-U", "shuyuan", "-d", "shuyuan", "-At", "-v", "ON_ERROR_STOP=1", "-c", statement)

    def ready(project):
        address = compose(project, "port", "api", "8000").splitlines()[0]
        base = "http://" + address
        for _ in range(60):
            try:
                body = request(base, "/api/ready")
                assert body["schema"]["current"] == "20261002_03" and body["worker"]["ok"]
                return base
            except (urllib.error.URLError, AssertionError):
                time.sleep(1)
        raise RuntimeError("API/worker readiness did not recover")

    def database_digests(project):
        return {table: hashlib.sha256(sql(project, f"SELECT coalesce(json_agg(t ORDER BY id)::text, '[]') FROM {table} t").encode()).hexdigest()
                for table in ("users", "rooms", "room_scene_rules", "reservations", "private_media", "space_messages", "admin_audit_logs")}

    def login(base, account):
        return request(base, "/api/auth/login", {"student_id": account, "password": PASSWORD})["access_token"]

    def ops_restore(project, snapshot, *overrides, expected=0, message=None):
        args = ["run", "--rm", "--no-deps", "-e", "RESTORE_WRITES_STOPPED=yes", "-e", "RESTORE_TARGET_CONFIRM=shuyuan",
                "-e", "BACKUP_SET=/backups/" + snapshot, "-e", "BACKUP_AGE_IDENTITY=/keys/identity.txt"]
        for key, value in overrides:
            args.extend(["-e", key + "=" + value])
        return compose(project, *args, "ops", "sh", "restore.sh", expected=expected, message=message)

    source, restored = PROJECTS
    started = time.monotonic()
    try:
        compose(source, "config", "--quiet")
        compose(source, "up", "-d", "db")
        compose(source, "run", "--rm", "migrate")
        assert sql(source, "SELECT count(*) FROM users") == "0"
        first = compose(source, "run", "--rm", "--no-deps", "api", "python", "init_reference_data.py")
        assert '"created_rooms": 12' in first and '"created_rules": 10' in first
        second = compose(source, "run", "--rm", "--no-deps", "api", "python", "init_reference_data.py")
        assert '"created_rooms": 0' in second and '"created_rules": 0' in second
        admin_code = "import asyncio,builtins,getpass; import create_admin; answers=iter(['school_test_admin','演练管理员']); builtins.input=lambda _:next(answers); getpass.getpass=lambda _: 'RehearsalOnly1234'; asyncio.run(create_admin.main())"
        compose(source, "run", "--rm", "--no-deps", "api", "python", "-c", admin_code)
        compose(source, "up", "-d", "api", "worker")
        base = ready(source)
        student = request(base, "/api/auth/register", {"student_id": "11120001", "name": "演练学生", "phone": "13800000001", "class_name": "2601", "password": PASSWORD})["access_token"]
        admin = login(base, "school_test_admin")
        media = request(base, "/api/reservations/campus-card-photo", token=student, upload=True)["media_id"]
        date = (datetime.now(ZoneInfo("Asia/Shanghai")) + timedelta(days=1)).date().isoformat()
        booking = request(base, "/api/reservations", {"scene": "study", "date": date, "start_slot": 2, "end_slot": 4, "people_count": 1, "purpose": "个人自习", "campus_card_media_id": media}, student)
        # Only this disposable synthetic fixture is advanced directly for message eligibility.
        sql(source, f"UPDATE reservations SET status='completed' WHERE id={int(booking['id'])}")
        public = request(base, f"/api/rooms/{booking['room_id']}/messages/photo", token=student, upload=True)["url"]
        request(base, f"/api/rooms/{booking['room_id']}/messages", {"content": "隔离演练留言", "photo_urls": [public]}, student)
        assert request(base, public, raw=True) == IMAGE
        assert request(base, "/api/media/" + media, token=admin, raw=True) == IMAGE
        try:
            request(base, "/api/media/" + media, raw=True)
            raise AssertionError("private media leaked")
        except urllib.error.HTTPError as exc:
            assert exc.code == 401
        compose(source, "restart", "api", "worker", "db")
        base = ready(source)
        assert request(base, public, raw=True) == IMAGE
        assert request(base, "/api/media/" + media, token=admin, raw=True) == IMAGE
        print("PASS: empty deployment, controlled initialization/admin, API/worker, upload/booking/message and restart persistence", flush=True)

        compose(source, "stop", "api", "worker")
        original = database_digests(source)
        compose(source, "run", "--rm", "--no-deps", "-v", str(work / "keys") + ":/keygen", "ops", "age-keygen", "-o", "/keygen/identity.txt")
        recipient = compose(source, "run", "--rm", "--no-deps", "ops", "age-keygen", "-y", "/keys/identity.txt")
        compose(source, "run", "--rm", "--no-deps", "-e", "BACKUP_AGE_RECIPIENT=" + recipient, "ops", "sh", "backup.sh", expected=1, message="BACKUP_WRITES_STOPPED")
        compose(source, "run", "--rm", "--no-deps", "-e", "BACKUP_WRITES_STOPPED=yes", "-e", "BACKUP_AGE_RECIPIENT=" + recipient, "ops", "sh", "backup.sh")
        snapshot = next((work / "backups").glob("snapshot-*"))
        assert {p.name for p in snapshot.iterdir()} == {"manifest.json", "database.dump.age", "media.tar.gz.age"}
        assert not list((work / "backups").glob(".plain-*"))
        assert json.loads((snapshot / "manifest.json").read_text())["schemaRevision"] == "20261002_03"
        compose(restored, "up", "-d", "--wait", "--wait-timeout", "60", "db")
        ops_restore(restored, snapshot.name, ("DATABASE_URL", "postgresql+asyncpg://shuyuan:isolated-test-only@db:5432/wrong"), expected=1, message="目标不一致")
        ops_restore(restored, snapshot.name, ("POSTGRES_BACKUP_URL", "postgresql+asyncpg://shuyuan:isolated-test-only@db:5432/shuyuan"), expected=1, message="不能使用asyncpg驱动URL")
        compose(source, "run", "--rm", "--no-deps", "ops", "python3", "-c", f"from pathlib import Path; p=Path('/backups/{snapshot.name}/database.dump.age'); p.write_bytes(p.read_bytes()+b'corruption')")
        ops_restore(restored, snapshot.name, expected=1, message="校验失败")
        compose(source, "run", "--rm", "--no-deps", "ops", "python3", "-c", f"from pathlib import Path; p=Path('/backups/{snapshot.name}/database.dump.age'); p.write_bytes(p.read_bytes()[:-10])")
        ops_restore(restored, snapshot.name, ("RESTORE_WRITES_STOPPED", "no"), expected=1, message="先停止目标环境")
        sql(restored, "CREATE TABLE sentinel(id integer)")
        ops_restore(restored, snapshot.name, expected=1, message="public schema必须为空")
        assert sql(restored, "SELECT count(*) FROM pg_tables WHERE schemaname='public'") == "1"
        sql(restored, "DROP TABLE sentinel")
        print("PASS: encrypted complete backup and rejection of unstopped writers, wrong target, corrupt snapshot and nonempty database", flush=True)

        ops_restore(restored, snapshot.name)
        assert database_digests(restored) == original
        ops_restore(restored, snapshot.name, expected=1, message="目标媒体目录必须为空")
        compose(restored, "run", "--rm", "--no-deps", "--user", "root", "api", "sh", "-c", "chown -R app:app /app/uploads /app/private_uploads")
        compose(restored, "run", "--rm", "migrate")
        compose(restored, "up", "-d", "api", "worker")
        restored_base = ready(restored)
        new_student = login(restored_base, "11120001")
        new_admin = login(restored_base, "school_test_admin")
        orders = request(restored_base, "/api/reservations/my", token=new_student)
        assert orders["total"] == 1 and orders["items"][0]["id"] == booking["id"]
        assert request(restored_base, public, raw=True) == IMAGE
        assert request(restored_base, "/api/media/" + media, token=new_admin, raw=True) == IMAGE
        compose(restored, "restart", "db", "api", "worker")
        restored_base = ready(restored)
        assert request(restored_base, public, raw=True) == IMAGE
        assert request(restored_base, "/api/media/" + media, token=new_admin, raw=True) == IMAGE
        assert request(restored_base, "/api/reservations/my", token=new_student)["total"] == 1
        print(f"PASS: 7 table digests matched; public/private media bytes and authorization, migration, restored API/worker and restart persistence; {time.monotonic()-started:.1f}s", flush=True)
    finally:
        for project in PROJECTS:
            subprocess.run(["docker", "compose", "--env-file", str(environment), "-f", str(ROOT / "docker-compose.yml"), "-f", str(override), "-p", project, "down", "--volumes", "--remove-orphans"], cwd=ROOT, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
