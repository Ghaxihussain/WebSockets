# database.py
from sqlalchemy import select
from .models import async_session, Message


async def save_message(room_id: str, sender: str, content: str) -> Message:
    async with async_session() as session:
        msg = Message(room_id=room_id, sender=sender, content=content)
        session.add(msg)
        await session.commit()
        return msg


async def get_history(room_id: str, limit: int = 50) -> list[Message]:
    async with async_session() as session:
        stmt = (
            select(Message)
            .where(Message.room_id == room_id)
            .order_by(Message.timestamp.asc())
            .limit(limit)
        )
        result = await session.execute(stmt)
        return result.scalars().all()