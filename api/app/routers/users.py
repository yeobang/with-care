from fastapi import APIRouter, Depends, Header, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.config import settings
from app.deps import get_current_user, get_db
from app.domain import crew_service as svc
from app.domain.models import Child, User
from app.infra import auth_jwt, identity

router = APIRouter(tags=["users"])


class SignupIn(BaseModel):
    name: str = Field(min_length=1, max_length=50)


class UserOut(BaseModel):
    id: str
    name: str
    identity_verified: bool


@router.post("/users", response_model=UserOut)
def signup(
    body: SignupIn,
    db: Session = Depends(get_db),
    authorization: str | None = Header(default=None),
) -> User:
    """가입 = Supabase Auth 계정(JWT sub)에 프로필 행 생성. 본인인증은 별도 단계.

    dev 한정: 토큰 없이도 가입 가능 (X-User-Id 흐름·테스트용).
    """
    if authorization and authorization.lower().startswith("bearer "):
        claims = auth_jwt.verify(authorization[7:])
        existing = db.get(User, claims["sub"])
        if existing is not None:
            return existing  # 재가입 멱등
        user = User(id=claims["sub"], name=body.name, identity_verified=False)
    elif settings.env == "dev":
        user = User(name=body.name, identity_verified=False)
    else:
        raise HTTPException(status_code=401, detail="Bearer 토큰 필요")
    db.add(user)
    db.flush()
    return user


@router.get("/me", response_model=UserOut)
def me(user: User = Depends(get_current_user)) -> User:
    return user


@router.post("/identity/verify", response_model=UserOut)
def identity_verify(
    user: User = Depends(get_current_user), db: Session = Depends(get_db)
) -> User:
    """본인인증 (I1의 실물 관문). 현재는 스텁 어댑터 — PASS류 확보 시 어댑터만 교체."""
    if not identity.get_verifier().verify(user.id, user.name):
        raise HTTPException(status_code=403, detail="본인인증 실패")
    user.identity_verified = True
    db.flush()
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
