import uuid

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ...database import get_admin_db
from ...exceptions import NotFoundError
from ...models import User
from .schemas import UserCreateSchema, UserResponseSchema, UserUpdateSchema

router = APIRouter(prefix="/users")
db_dependency = Depends(get_admin_db)


@router.get("", response_model=list[UserResponseSchema])
async def get_users(db: AsyncSession = db_dependency):
    users = (await db.scalars(select(User))).all()
    return users

@router.get("/{user_id}", response_model=UserResponseSchema)
async def get_user(user_id: uuid.UUID, db: AsyncSession = db_dependency):
    user = await db.scalar(select(User).where(User.id == user_id))

    if user is None:
        raise NotFoundError("User", user_id)

    return user

@router.post("", response_model=UserResponseSchema)
async def create_user(user: UserCreateSchema, db: AsyncSession = db_dependency):
    new_user = User(**user.model_dump(exclude_unset=True))
    db.add(new_user)
    try:
        await db.commit()
        await db.refresh(new_user)
    except Exception as err:
        await db.rollback()
        raise HTTPException(
            status_code=409,
            detail="Email already exists",
        ) from err

    return new_user

@router.put("/{user_id}", response_model=UserResponseSchema)
async def update_user(
    user_id: uuid.UUID, user: UserUpdateSchema, db: AsyncSession = db_dependency):
    existing_user = await db.scalar(select(User).where(User.id == user_id))

    if existing_user is None:
        raise NotFoundError("User", user_id)

    for key, value in user.model_dump(exclude_unset=True).items():
        setattr(existing_user, key, value)
    await db.commit()
    await db.refresh(existing_user)
    return existing_user

@router.delete("/{user_id}", status_code=204)
async def delete_user(user_id: uuid.UUID, db: AsyncSession = db_dependency):
    user = await db.scalar(select(User).where(User.id == user_id))

    if user is None:
        raise NotFoundError("User", user_id)

    await db.delete(user)
    await db.commit()
    return None
