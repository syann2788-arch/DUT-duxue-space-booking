"""Run explicitly after migration; inserts defaults without demo users or overwrites."""
import asyncio
import json
from app.config import validate_runtime_security
from app.database import init_db, async_session, engine
from app.domain.reference_data import initialize_reference_data


async def main():
    validate_runtime_security()
    try:
        await init_db()
        async with async_session() as db:
            result = await initialize_reference_data(db)
            await db.commit()
        print(json.dumps(result, ensure_ascii=False))
    finally:
        await engine.dispose()


if __name__ == "__main__":
    asyncio.run(main())
