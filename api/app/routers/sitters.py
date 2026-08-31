"""시터 트랙 API (P10, §25). 결제 없음 — 금액은 계산·안내까지."""

from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.orm import Session

from app import notifications
from app.deps import get_current_user, get_db
from app.domain import sitter_service as svc
from app.domain.crew_service import _require_member
from app.domain.models import (
    SitterProfile,
    SitterQuote,
    SitterQuoteFamily,
    SitterRequest,
    SitterRequestChild,
    User,
)

router = APIRouter(tags=["sitters"])


class ProfileIn(BaseModel):
    hourly_krw: int = Field(gt=0, le=1_000_000)
    intro: str = Field(default="", max_length=500)


@router.post("/sitters/me")
def upsert_profile(body: ProfileIn, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    p = svc.upsert_profile(db, user, hourly_krw=body.hourly_krw, intro=body.intro)
    return {"hourly_krw": p.hourly_krw, "intro": p.intro}


@router.get("/sitters/me")
def my_profile(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    p = db.scalar(select(SitterProfile).where(SitterProfile.user_id == user.id))
    return {"hourly_krw": p.hourly_krw, "intro": p.intro} if p else None


class RequestIn(BaseModel):
    date: str = Field(pattern=r"^\d{4}-\d{2}-\d{2}$")
    start_hour: int = Field(ge=0, le=23)
    end_hour: int = Field(ge=1, le=24)
    child_ids: list[str] = Field(min_length=1)


@router.post("/crews/{crew_id}/sitter-requests")
def create_request(crew_id: str, body: RequestIn, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    req = svc.create_request(db, crew_id, user, **body.model_dump())
    return _request_out(db, req)


@router.get("/crews/{crew_id}/sitter-requests")
def list_requests(crew_id: str, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    _require_member(db, crew_id, user.id)  # 시터도 견적 제출을 위해 목록은 본다
    rows = db.scalars(
        select(SitterRequest).where(SitterRequest.crew_id == crew_id)
    ).all()
    return [_request_out(db, r) for r in rows]


class JoinIn(BaseModel):
    child_id: str


@router.post("/sitter-requests/{request_id}/join")
def join_request(request_id: str, body: JoinIn, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    req = svc.join_request(db, request_id, user, body.child_id)
    return _request_out(db, req)


@router.post("/sitter-requests/{request_id}/quotes")
def submit_quote(request_id: str, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    quote, created = svc.submit_quote(db, request_id, user)
    if created:
        notifications.notify_new_quote(db, quote)
    return _quote_out(db, quote)


@router.post("/sitter-quotes/{quote_id}/confirm")
def confirm_quote(quote_id: str, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    quote = db.get(SitterQuote, quote_id)
    was_confirmed = quote is not None and str(quote.status) == "confirmed"
    session = svc.confirm_quote(db, quote_id, user)
    if session is not None and not was_confirmed:
        notifications.notify_session_confirmed(db, session)
        if svc.recurrence_warning(db, session):
            notifications.notify_recurrence(db, session.crew_id)  # §25-6: 경고, 차단 아님
    return {"session_id": session.id if session else None}


@router.post("/sitter-quotes/{quote_id}/decline")
def decline_quote(quote_id: str, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    quote = svc.decline_quote(db, quote_id, user)
    return {"status": str(quote.status)}


def _quote_out(db: Session, q: SitterQuote) -> dict:
    fams = db.scalars(
        select(SitterQuoteFamily).where(SitterQuoteFamily.quote_id == q.id)
    ).all()
    return {
        "id": q.id,
        "sitter_user_id": q.sitter_user_id,
        "hourly_krw": q.hourly_krw,
        "surge": q.surge,
        "total_krw": q.total_krw,
        "per_family_krw": q.per_family_krw,
        "status": str(q.status),
        "families": [
            {"guardian_id": f.guardian_id, "confirmed": f.confirmed} for f in fams
        ],
    }


def _request_out(db: Session, r: SitterRequest) -> dict:
    children = db.scalars(
        select(SitterRequestChild).where(SitterRequestChild.request_id == r.id)
    ).all()
    quotes = db.scalars(
        select(SitterQuote).where(SitterQuote.request_id == r.id)
    ).all()
    return {
        "id": r.id,
        "date": r.date,
        "start_hour": r.start_hour,
        "end_hour": r.end_hour,
        "status": str(r.status),
        "child_count": len(children),
        "quotes": [_quote_out(db, q) for q in quotes],
    }
