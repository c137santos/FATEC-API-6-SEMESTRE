from sqlalchemy import select

from backend.core.models import User


async def test_create_user(session):
    user = User(
        username='Nico Robin', email='Nico@Robin.com', password='poneglyph'
    )

    session.add(user)
    await session.commit()
    await session.refresh(user)

    result = await session.scalar(
        select(User).where(User.email == 'Nico@Robin.com')
    )

    assert result.username == 'Nico Robin'
