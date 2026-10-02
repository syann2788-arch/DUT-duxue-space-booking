"""Verify the actual CLI against migrated isolated databases, never the demo DB."""
import json
import os
from pathlib import Path
import sqlite3
import subprocess
import sys

BACKEND = Path(__file__).resolve().parents[1]


def invoke(args, env):
    return subprocess.run([sys.executable, *args], cwd=BACKEND, env=env,
                          capture_output=True, text=True, timeout=60)


def environment(db):
    return {**os.environ, 'DATABASE_URL': 'sqlite+aiosqlite:///' + str(db),
            'APP_ENV': 'production', 'SECRET_KEY': 'isolated-reference-test-key-' + 'x' * 32}


def test_production_cli_requires_migration(tmp_path):
    response = invoke(['init_reference_data.py'], environment(tmp_path / 'unmigrated.db'))
    assert response.returncode != 0
    assert '请先执行 alembic upgrade head' in response.stderr


def test_reference_initialization_preserves_configuration_and_accounts(tmp_path):
    db_path = tmp_path / 'reference.db'
    env = environment(db_path)
    migration = invoke(['-m', 'alembic', 'upgrade', 'head'], env)
    assert migration.returncode == 0, migration.stderr
    first = invoke(['init_reference_data.py'], env)
    assert first.returncode == 0, first.stderr
    assert json.loads(first.stdout) == {'created_rooms': 12, 'created_rules': 10}
    with sqlite3.connect(db_path) as db:
        assert db.execute('SELECT count(*) FROM users').fetchone()[0] == 0
        db.execute("UPDATE rooms SET name='学校配置', capacity=17, who_can_reserve='counselor', is_active=0 WHERE room_code='A102'")
        db.execute("UPDATE room_scene_rules SET capacity=3, priority=99, is_enabled=0 WHERE room_id=(SELECT id FROM rooms WHERE room_code='A102') AND scene='study'")
        db.execute("INSERT INTO users(student_id,name,phone,class_name,password_hash,role,is_active,must_change_password,session_version,created_at) VALUES ('school_admin','虚构管理员','','管理员','unchanged-hash','admin',1,0,7,'2026-10-02')")
        db.execute("INSERT INTO system_settings(key,value,description,updated_at) VALUES ('max_minutes_per_day','120','学校配置','2026-10-02')")
        before = db.execute('SELECT * FROM users').fetchall()
    second = invoke(['init_reference_data.py'], env)
    assert second.returncode == 0, second.stderr
    assert json.loads(second.stdout) == {'created_rooms': 0, 'created_rules': 0}
    with sqlite3.connect(db_path) as db:
        assert db.execute('SELECT * FROM users').fetchall() == before
        assert db.execute("SELECT name,capacity,who_can_reserve,is_active FROM rooms WHERE room_code='A102'").fetchone() == ('学校配置',17,'counselor',0)
        assert db.execute("SELECT capacity,priority,is_enabled FROM room_scene_rules WHERE room_id=(SELECT id FROM rooms WHERE room_code='A102') AND scene='study'").fetchone() == (3,99,0)
        assert db.execute("SELECT value FROM system_settings WHERE key='max_minutes_per_day'").fetchone()[0] == 120
        assert db.execute('SELECT count(*) FROM rooms').fetchone()[0] == 12
        assert db.execute('SELECT count(*) FROM room_scene_rules').fetchone()[0] == 10
        db.execute("DELETE FROM room_scene_rules WHERE room_id=(SELECT id FROM rooms WHERE room_code='A103') AND scene='music'")
    third = invoke(['init_reference_data.py'], env)
    assert third.returncode == 0, third.stderr
    assert json.loads(third.stdout) == {'created_rooms': 0, 'created_rules': 1}
    forbidden = invoke(['seed.py'], env)
    assert forbidden.returncode != 0 and '演示 seed' in forbidden.stderr
