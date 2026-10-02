import asyncio
from datetime import timedelta
from app.database import async_session
from app.models import User, Reservation, ReservationStatus, local_now
from app.domain.reservations import _daily_minutes, refresh_reservation_states
from app.domain.restrictions import get_active_restriction
from app.domain.settings import get_runtime_config
from test_business import register, upload_campus_card
from conftest import auth_header


def admin_headers(client):
    return auth_header(client.post('/api/auth/login', json={'student_id': 'admin001', 'password': 'admin123'}).json()['access_token'])


def test_reset_single_use_reissue_session_revocation_and_audit(client):
    headers = auth_header(register(client, 81))
    uid = client.get('/api/auth/me', headers=headers).json()['id']
    endpoint = f'/api/admin/users/{uid}/password-reset'
    admin = admin_headers(client)
    payload = {'admin_password': 'admin123', 'reason': '线下核验本人'}
    assert client.post(endpoint, headers=headers, json=payload).status_code == 403
    assert client.post(endpoint, headers=admin, json={**payload, 'admin_password': 'wrong'}).status_code == 403
    old = client.post(endpoint, headers=admin, json=payload).json()['credential']
    credential = client.post(endpoint, headers=admin, json=payload).json()['credential']
    def reset(value):
        return client.post('/api/auth/password/reset', json={'credential': value, 'new_password': 'Newpass123'})
    assert reset(old).status_code == 400
    assert reset(credential).status_code == 200
    assert reset(credential).status_code == 400
    assert client.get('/api/auth/me', headers=headers).status_code == 401
    assert client.post('/api/auth/login', json={'student_id': '20260081', 'password': 'Test1234'}).status_code == 401
    new = client.post('/api/auth/login', json={'student_id': '20260081', 'password': 'Newpass123'})
    assert new.status_code == 200
    headers = auth_header(new.json()['access_token'])
    assert client.post('/api/auth/password/change', headers=headers, json={'current_password': 'Newpass123', 'new_password': 'Changed123'}).status_code == 200
    assert client.get('/api/auth/me', headers=headers).status_code == 401
    audit = client.get('/api/admin/audit?limit=100', headers=admin).json()
    assert 'password_reset.complete' in {row['action'] for row in audit['items']}
    assert credential not in str(audit) and 'Newpass123' not in str(audit)


def test_completed_quota_and_multiday_outage(client):
    token = register(client, 82)
    headers = auth_header(token)
    day = local_now().date() + timedelta(days=6)
    base = {'scene': 'study', 'date': day.isoformat(), 'people_count': 1, 'purpose': '个人自习', 'campus_card_media_id': upload_campus_card(client, token)}
    created = client.post('/api/reservations', headers=headers, json={**base, 'start_slot': 0, 'end_slot': 8})
    assert created.status_code == 201, created.text
    uid = client.get('/api/auth/me', headers=headers).json()['id']
    async def prepare():
        async with async_session() as db:
            reservation = await db.get(Reservation, created.json()['id'])
            reservation.status = ReservationStatus.completed
            await db.commit()
            assert await _daily_minutes(db, uid, day, await get_runtime_config(db)) == 240
    asyncio.run(prepare())
    base['campus_card_media_id'] = upload_campus_card(client, token)
    rejected = client.post('/api/reservations', headers=headers, json={**base, 'start_slot': 9, 'end_slot': 10})
    assert rejected.status_code == 400, rejected.text
    async def outage():
        async with async_session() as db:
            reservation = await db.get(Reservation, created.json()['id'])
            reservation.date = local_now().date() - timedelta(days=4)
            reservation.status = ReservationStatus.approved
            await db.commit()
            await refresh_reservation_states(db)
            await db.refresh(reservation)
            assert reservation.status == ReservationStatus.missed
    asyncio.run(outage())
    page = client.get('/api/admin/worklist?kind=violations&limit=1', headers=admin_headers(client))
    assert page.status_code == 200, page.text
    assert page.json()['total'] >= 1 and len(page.json()['items']) == 1


def test_future_restriction_boundaries_and_inbox_privacy(client):
    headers = auth_header(register(client, 83))
    outsider = auth_header(register(client, 84))
    uid = client.get('/api/auth/me', headers=headers).json()['id']
    start = local_now() + timedelta(days=2)
    end = start + timedelta(days=1)
    admin = admin_headers(client)
    response = client.post(f'/api/admin/users/{uid}/restrictions', headers=admin, json={'level': 'timed', 'reason': '指定区间测试', 'starts_at': start.isoformat() + '+08:00', 'ends_at': end.isoformat() + '+08:00'})
    assert response.status_code == 201, response.text
    assert client.get('/api/auth/me', headers=headers).json()['booking_restricted'] is False
    async def boundaries():
        async with async_session() as db:
            user = await db.get(User, uid)
            assert await get_active_restriction(db, user, start - timedelta(seconds=1)) is None
            assert (await get_active_restriction(db, user, start)).id == response.json()['id']
            assert await get_active_restriction(db, user, end) is None
    asyncio.run(boundaries())
    inbox = client.get('/api/notifications/my', headers=headers).json()
    assert any(n['payload'].get('reason') == '指定区间测试' for n in inbox['items'])
    assert not any(n['payload'].get('change') == 'expired' for n in inbox['items'])
    assert not any(n['payload'].get('reason') == '指定区间测试' for n in client.get('/api/notifications/my', headers=outsider).json()['items'])
    assert client.get('/api/admin/audit', headers=headers).status_code == 403
    assert client.get('/api/admin/worklist', headers=headers).status_code == 403


def test_auto_approval_catches_up_once_after_scheduled_time(client, monkeypatch):
    from app import tasks
    from app.models import SystemSetting
    calls = []
    now = local_now().replace(hour=23, minute=7)
    async def config(db):
        return {'auto_approval_time': '23:00'}
    async def approve(db):
        calls.append(True)
        return 2
    async def noop(db):
        return 0
    async def clear_cursor():
        async with async_session() as db:
            row = await db.get(SystemSetting, 'last_auto_approval_date')
            if row:
                await db.delete(row)
                await db.commit()
    asyncio.run(clear_cursor())
    monkeypatch.setattr(tasks, 'local_now', lambda: now)
    monkeypatch.setattr(tasks, 'get_runtime_config', config)
    monkeypatch.setattr(tasks, 'auto_approve_pending', approve)
    for name in ('refresh_reservation_states', 'expire_restrictions', 'purge_expired_private_media', 'deliver_due_notifications'):
        monkeypatch.setattr(tasks, name, noop)
    assert asyncio.run(tasks.minute_tick())['approved'] == 2
    assert asyncio.run(tasks.minute_tick())['approved'] == 0
    assert len(calls) == 1


def test_expired_reset_and_initial_counselor_password(client):
    from app.domain.users import create_counselor_user
    from app.auth import hash_password
    from app.models import PasswordResetCredential
    from sqlalchemy import select
    headers = auth_header(register(client, 85))
    uid = client.get('/api/auth/me', headers=headers).json()['id']
    issued = client.post(f'/api/admin/users/{uid}/password-reset', headers=admin_headers(client), json={'admin_password': 'admin123', 'reason': '核验本人'}).json()
    async def prepare():
        async with async_session() as db:
            row = await db.scalar(select(PasswordResetCredential).where(PasswordResetCredential.user_id == uid))
            row.expires_at = local_now() - timedelta(seconds=1)
            await db.commit()
            await create_counselor_user(db, 'staff_delivery_test', '辅导员测试', '13900009999', '2601', hash_password('Initial123'))
    asyncio.run(prepare())
    assert client.post('/api/auth/password/reset', json={'credential': issued['credential'], 'new_password': 'Expired123'}).status_code == 400
    response = client.post('/api/auth/login', json={'student_id': 'staff_delivery_test', 'password': 'Initial123'})
    assert response.json()['user']['must_change_password'] is True
    counselor = auth_header(response.json()['access_token'])
    assert client.get('/api/reservations/my', headers=counselor).status_code == 403
    assert client.post('/api/auth/password/change', headers=counselor, json={'current_password': 'Initial123', 'new_password': 'Changed123'}).status_code == 200
