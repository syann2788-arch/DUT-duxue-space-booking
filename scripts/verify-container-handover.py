"""Run a disposable PostgreSQL/container smoke check; never connects to school data.

Build duxue-handover-local:01-02 first. Requires Docker and postgres:16-alpine.
"""
from pathlib import Path
import subprocess
import time
from uuid import uuid4

network = "duxue-handover-" + uuid4().hex[:8]
database = network + "-db"
credentials = network + "-credentials"
helper = Path(__file__).with_name("container-handover-smoke.py").resolve()


def run(args, **kwargs):
    return subprocess.run(["docker", *args], check=True, **kwargs)


try:
    run(["network", "create", network], stdout=subprocess.DEVNULL)
    run(["volume", "create", credentials], stdout=subprocess.DEVNULL)
    run(["run", "-d", "--name", database, "--network", network, "--network-alias", "db",
         "-e", "POSTGRES_PASSWORD=isolated-test-only", "-e", "POSTGRES_DB=handover",
         "postgres:16-alpine"], stdout=subprocess.DEVNULL)
    for attempt in range(30):
        ready = subprocess.run(["docker", "exec", database, "pg_isready", "-U", "postgres"], capture_output=True)
        if ready.returncode == 0:
            break
        time.sleep(1)
    else:
        raise RuntimeError("Isolated PostgreSQL did not become ready")
    run(["run", "--rm", "--network", network,
         "-e", "APP_ENV=production",
         "-e", "DATABASE_URL=postgresql+asyncpg://postgres:isolated-test-only@db:5432/handover",
         "-e", "SECRET_KEY=isolated-handover-test-" + "x" * 32,
         "-v", str(helper) + ":/tmp/verify.py:ro",
         "-v", credentials + ":/app/credentials",
         "duxue-handover-local:01-02", "python", "/tmp/verify.py"])
finally:
    for command in (["rm", "-fv", database], ["volume", "rm", credentials], ["network", "rm", network]):
        subprocess.run(["docker", *command], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
