from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.deps import get_current_user, get_db
from app.domain.models import Child, User

router = APIRouter(tags=["users"])


class SignupIn(BaseModel):
    name: str = Field(min_length=1, max_length=50)


class UserOut(BaseModel):
    id: str
    name: str
    identity_verified: bool


@router.post("/users", response_model=UserOut)
def signup(body: SignupIn, db: Session = Depends(get_db)) -> User:
    # dev: 즉시 인증 처리. TODO(P6): PASS 본인인증 연동 후 verified는 그 결과로만 설정
    user = User(name=body.name, identity_verified=True)
    db.add(user)
    db.flush()
    return user


@router.get("/me", response_model=UserOut)
def me(user: User = Depends(get_current_user)) -> User:
    return user


class ChildIn(BaseModel):
    name: str = Field(min_length=1, max_length=50)
    birth_year_month: str = Field(pattern=r"^\d{4}-\d{2}$")
    emergency_contact: str = Field(min_length=1, max_length=100)
    traits: str = ""
    allergies: str = ""
    medication: str = ""


class ChildOut(ChildIn):
    id: str


@router.post("/my/children", response_model=ChildOut)
def add_child(body: ChildIn, user: User = Depends(get_current_user), db: Session = Depends(get_db)) -> Child:
    child = Child(guardian_id=user.id, **body.model_dump())
    db.add(child)
    db.flush()
    return child


@router.get("/my/children", response_model=list[ChildOut])
def my_children(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    return db.scalars(select(Child).where(Child.guardian_id == user.id)).all()
