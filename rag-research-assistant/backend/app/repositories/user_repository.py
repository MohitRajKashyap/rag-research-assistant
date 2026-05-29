"""
User Repository
Data access layer for user operations.
All DB queries go through repositories, not services.
"""
import uuid
from typing import Optional, List
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, update, func
from sqlalchemy.orm import selectinload
import structlog

from app.models.user import User, UserRole
from app.core.security import hash_password, generate_api_key

logger = structlog.get_logger(__name__)


class UserRepository:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def get_by_id(self, user_id: uuid.UUID) -> Optional[User]:
        result = await self.db.execute(
            select(User).where(User.id == user_id)
        )
        return result.scalar_one_or_none()

    async def get_by_email(self, email: str) -> Optional[User]:
        result = await self.db.execute(
            select(User).where(User.email == email.lower())
        )
        return result.scalar_one_or_none()

    async def get_by_username(self, username: str) -> Optional[User]:
        result = await self.db.execute(
            select(User).where(User.username == username)
        )
        return result.scalar_one_or_none()

    async def get_by_api_key(self, api_key: str) -> Optional[User]:
        result = await self.db.execute(
            select(User).where(User.api_key == api_key)
        )
        return result.scalar_one_or_none()

    async def create(
        self,
        email: str,
        username: str,
        password: str,
        full_name: Optional[str] = None,
        role: UserRole = UserRole.USER,
    ) -> User:
        user = User(
            email=email.lower(),
            username=username,
            hashed_password=hash_password(password),
            full_name=full_name,
            role=role,
        )
        self.db.add(user)
        await self.db.flush()
        await self.db.refresh(user)
        logger.info("User created", user_id=str(user.id), email=email)
        return user

    async def update(self, user: User, **kwargs) -> User:
        for key, value in kwargs.items():
            if hasattr(user, key) and value is not None:
                setattr(user, key, value)
        await self.db.flush()
        await self.db.refresh(user)
        return user

    async def update_password(self, user: User, new_password: str) -> User:
        user.hashed_password = hash_password(new_password)
        await self.db.flush()
        return user

    async def generate_api_key(self, user: User) -> str:
        key = generate_api_key()
        user.api_key = key
        await self.db.flush()
        return key

    async def increment_usage(
        self,
        user_id: uuid.UUID,
        queries: int = 0,
        tokens: int = 0,
        documents: int = 0,
    ) -> None:
        await self.db.execute(
            update(User)
            .where(User.id == user_id)
            .values(
                total_queries=User.total_queries + queries,
                total_tokens_used=User.total_tokens_used + tokens,
                total_documents_uploaded=User.total_documents_uploaded + documents,
            )
        )

    async def list_users(
        self,
        skip: int = 0,
        limit: int = 20,
        role: Optional[UserRole] = None,
        is_active: Optional[bool] = None,
    ) -> tuple[List[User], int]:
        query = select(User)
        count_query = select(func.count(User.id))
        if role:
            query = query.where(User.role == role)
            count_query = count_query.where(User.role == role)
        if is_active is not None:
            query = query.where(User.is_active == is_active)
            count_query = count_query.where(User.is_active == is_active)

        total_result = await self.db.execute(count_query)
        total = total_result.scalar()

        query = query.offset(skip).limit(limit).order_by(User.created_at.desc())
        result = await self.db.execute(query)
        users = result.scalars().all()

        return list(users), total

    async def deactivate(self, user: User) -> User:
        user.is_active = False
        await self.db.flush()
        return user

    async def email_exists(self, email: str) -> bool:
        result = await self.db.execute(
            select(func.count(User.id)).where(User.email == email.lower())
        )
        return result.scalar() > 0

    async def username_exists(self, username: str) -> bool:
        result = await self.db.execute(
            select(func.count(User.id)).where(User.username == username)
        )
        return result.scalar() > 0
