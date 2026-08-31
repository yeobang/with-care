from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.deps import get_current_user, get_db
from app.domain import crew_service as svc
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


class ChildPatch(BaseModel):
    """부분 수정 — 보낸 항목만 반영. 수정 시 보호자 재동의가 필요해진다 (§19-5)."""

    name: str | None = Field(default=None, min_length=1, max_length=50)
    birth_year_month: str | None = Field(default=None, pattern=r"^\d{4}-\d{2}$")
    emergency_contact: str | None = Field(default=None, min_length=1, max_length=100)
    traits: str | None = None
    allergies: str | None = None
    medication: str | None = None


@router.patch("/my/children/{child_id}", response_model=ChildOut)
def update_child(
    child_id: str,
    body: ChildPatch,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> Child:
    updates = {k: v for k, v in body.model_dump().items() if v is not None}
    return svc.update_child(db, user, child_id, **updates)
