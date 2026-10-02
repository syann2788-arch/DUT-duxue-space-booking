"""Synthetic checks executed inside the backend image by verify-container-handover.py."""
import asyncio,csv,json,os,stat,subprocess,sys
from pathlib import Path
sys.path.insert(0,'/app')
from sqlalchemy import select,func
from app.database import async_session, engine
from app.models import Room,RoomSceneRule,User,local_now
from datetime import timedelta

def run_async(coro):
    async def isolated():
        try:
            return await coro
        finally:
            await engine.dispose()
    return asyncio.run(isolated())

def cli(*args):
    r=subprocess.run([sys.executable,*args],cwd='/app',capture_output=True,text=True)
    assert r.returncode==0,r.stderr
    return r.stdout
cli('-m','alembic','upgrade','head')
async def counts():
    async with async_session() as db:return [await db.scalar(select(func.count()).select_from(m)) for m in (Room,RoomSceneRule,User)]
assert run_async(counts())==[0,0,0]
processes=[subprocess.Popen([sys.executable,'init_reference_data.py'],cwd='/app',stdout=subprocess.PIPE,stderr=subprocess.PIPE,text=True) for _ in range(2)]
results=[]
for p in processes:
    out,err=p.communicate(timeout=30);assert p.returncode==0,err;results.append(json.loads(out))
assert sorted(r['created_rooms'] for r in results)==[0,12]
assert sorted(r['created_rules'] for r in results)==[0,10]
assert run_async(counts())==[12,10,0]
async def edit(check=False):
    async with async_session() as db:
        room=await db.scalar(select(Room).where(Room.room_code=='A102'))
        rule=await db.scalar(select(RoomSceneRule).where(RoomSceneRule.room_id==room.id,RoomSceneRule.scene=='study'))
        if check:
            assert room.capacity==17 and not room.is_active
            assert rule.capacity==3 and not rule.is_enabled and rule.priority==99
        else:
            room.capacity=17;room.is_active=False;rule.capacity=3;rule.is_enabled=False;rule.priority=99
            await db.commit()
run_async(edit());assert json.loads(cli('init_reference_data.py'))=={'created_rooms':0,'created_rules':0};run_async(edit(True))
import create_admin
answers=iter(['school_test_admin','虚构管理员']);create_admin.input=lambda _:next(answers)
create_admin.getpass.getpass=lambda _:'SyntheticAdmin123'
run_async(create_admin.main())
source=Path('/tmp/synthetic-counselors.csv')
with source.open('w') as f:
    w=csv.writer(f);w.writerow(['职务','姓名','联系方式','负责班级']);w.writerow(['辅导员','虚构辅导员','13900009988','2601'])
os.environ['COUNSELOR_CSV_PATH']=str(source);os.environ['COUNSELOR_CREDENTIALS_OUTPUT']='/app/credentials/synthetic.json'
import import_counselors
run_async(import_counselors.import_counselors())
output=Path(os.environ['COUNSELOR_CREDENTIALS_OUTPUT']);assert stat.S_IMODE(output.stat().st_mode)==0o600
from fastapi.testclient import TestClient
from app.main import app
with TestClient(app) as client:
    credentials=json.loads(output.read_text())[0]
    response=client.post('/api/auth/login',json={'student_id':credentials['login_id'],'password':credentials['password']})
    assert response.status_code==200,response.text
    assert response.json()['user']['must_change_password']
    headers={'Authorization':'Bearer '+response.json()['access_token']}
    assert client.get('/api/reservations/my',headers=headers).status_code==403
    assert client.post('/api/auth/password/change',headers=headers,json={'current_password':credentials['password'],'new_password':'SyntheticChanged123'}).status_code==200
    for i,scene in enumerate(['study','meeting','event','music']):
        result=client.post('/api/auth/register',json={'student_id':f'2026880{i}','name':'虚构学生','phone':f'1390000900{i}','class_name':'2601','password':'SyntheticStudent123'})
        assert result.status_code==200,result.text
        headers={'Authorization':'Bearer '+result.json()['access_token']}
        photo=client.post('/api/reservations/campus-card-photo',headers=headers,files={'file':('test.jpg',b'\xff\xd8\xff\xe0synthetic','image/jpeg')})
        assert photo.status_code==201,photo.text
        slot=14 if scene=='music' else 0
        result=client.post('/api/reservations',headers=headers,json={'scene':scene,'date':(local_now().date()+timedelta(days=1)).isoformat(),'start_slot':slot,'end_slot':slot+1,'people_count':1,'purpose':'开展校内空间预约验证活动','campus_card_media_id':photo.json()['media_id']})
        assert result.status_code==201,result.text
output.unlink();source.unlink()
print('PASS: PostgreSQL migration, parallel/repeated initialization, preservation, admin provisioning, private counselor credentials, forced password change, four-scene bookings')
