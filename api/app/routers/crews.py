from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.deps import get_current_user, get_db
from app.domain import crew_service as svc
from app.domain.models import Charter, CrewMember, SettlementMode, User

router = APIRouter(tags=["crews"])


class CrewIn(BaseModel):
    name: str = Field(min_length=1, max_length=50)


@router.post("/crews")
def create_crew(body: CrewIn, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    crew = svc.create_crew(db, user, body.name)
    return svc.get_crew_view(db, crew.id, user)


@router.get("/my/crews")
def my_crews(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    memberships = db.scalars(select(CrewMember).where(CrewMember.user_id == user.id)).all()
    return [svc.get_crew_view(db, m.crew_id, user) for m in memberships]


@router.get("/crews/{crew_id}")
def crew_view(crew_id: str, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    return svc.get_crew_view(db, crew_id, user)


@router.post("/crews/{crew_id}/invites")
def create_invite(crew_id: str, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    invite = svc.create_invite(db, crew_id, user)
    return {"token": invite.token}


@router.post("/invites/{token}/join")
def join(token: str, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    member = svc.join_crew(db, user, token)
    return svc.get_crew_view(db, member.crew_id, user)


class ConsentIn(BaseModel):
    liability_ack: bool
    photo_consent: bool
    guardian_consent: bool


@router.post("/crews/{crew_id}/consent")
def consent(crew_id: str, body: ConsentIn, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    svc.submit_consent(db, crew_id, user, **body.model_dump())
    return {"ok": True}


class CharterIn(BaseModel):
    """규약 조정 입력 — 값을 안 보내면 기본값 그대로 확정 (백지 협상 금지)."""

    settlement_mode: SettlementMode | None = None
    credit_price_krw: int | None = Field(default=None, ge=0)
    host_fee_krw: int | None = Field(default=None, ge=0)
    no_show_fine_krw: int | None = Field(default=None, ge=0)
    care_rules: str | None = None
    handoff_method: str | None = None


@router.get("/crews/{crew_id}/charter")
def charter_view(crew_id: str, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    svc._require_member(db, crew_id, user.id)
    c = db.scalar(select(Charter).where(Charter.crew_id == crew_id))
    return {
        "settlement_mode": str(c.settlement_mode),
        "credit_price_krw": c.credit_price_krw,
        "host_fee_krw": c.host_fee_krw,
        "no_show_fine_krw": c.no_show_fine_krw,
        "care_rules": c.care_rules,
        "handoff_method": c.handoff_method,
        "is_complete": c.is_complete,
    }


@router.post("/crews/{crew_id}/charter/confirm")
def confirm_charter(crew_id: str, body: CharterIn, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    updates = {k: v for k, v in body.model_dump().items() if v is not None}
    svc.confirm_charter(db, crew_id, user, **updates)
    return {"ok": True}


@router.post("/crews/{crew_id}/activate")
def activate(crew_id: str, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    svc.activate_crew(db, crew_id, user)
    return svc.get_crew_view(db, crew_id, user)
