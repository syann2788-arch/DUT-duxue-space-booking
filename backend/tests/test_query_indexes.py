import asyncio

from sqlalchemy import inspect

from app.database import engine


def test_reservation_query_indexes_exist():
    async def read_indexes():
        async with engine.connect() as connection:
            return await connection.run_sync(
                lambda sync_connection: {
                    item["name"]: tuple(item["column_names"])
                    for item in inspect(sync_connection).get_indexes("reservations")
                }
            )

    indexes = asyncio.run(read_indexes())
    assert indexes["ix_reservations_status_date"] == ("status", "date")
    assert indexes["ix_reservations_user_date"] == ("user_id", "date")
