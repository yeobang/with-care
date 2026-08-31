from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.orm import Session

from app import notifications
from app.deps import get_current_user, get_db
from app.domain import board_service as board
from app.domain.crew_service import _require_member
from app.domain.models import (
    Assignment,
    AssignmentChild,
    BoardSlot,
    CareSession,
    Child,
    SlotKind,
    User,
)

router = APIRouter(tags=["board"])


class SlotIn(BaseModel):
    kind: SlotKind
    date: str = Field(pattern=r"^\d{4}-\d{2}-\d{2}$")
    start_hour: int = Field(ge=0, le=23)
    end_hour: int = Field(ge=1, le=24)
    child_id: str | None = None


@router.post("/crews/{crew_id}/slots")
def add_slot(crew_id: str, body: SlotIn, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    slot = board.add_slot(db, crew_id, user, **body.model_dump())
    return {"id": slot.id}


@router.get("/crews/{crew_id}/board")
def board_view(crew_id: str, date: str, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    _require_member(db, crew_id, user.id)
    slots = db.scalars(
        select(BoardSlot).where(BoardSlot.crew_id == crew_id, BoardSlot.date == date)
    ).all()
    return [
        {
            "id": s.id, "user_id": s.user_id, "kind": str(s.kind),
            "start_hour": s.start_hour, "end_hour": s.end_hour, "child_id": s.child_id,
        }
        for s in slots
    ]


@router.post("/crews/{crew_id}/propose")
def propose(crew_id: str, date: str, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    proposals = board.propose_assignments(db, crew_id, user, date)
    notifications.notify_proposals(db, proposals)  # best-effort — 실패해도 본 흐름 유지
    return [_assignment_out(db, a) for a in proposals]


@router.get("/crews/{crew_id}/proposals")
def list_proposals(crew_id: str, date: str, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    _require_member(db, crew_id, user.id)
    rows = db.scalars(
        select(Assignment).where(Assignment.crew_id == crew_id, Assignment.date == date)
    ).all()
    return [_assignment_out(db, a) for a in rows]


@router.post("/assignments/{assignment_id}/confirm")
def confirm(assignment_id: str, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    before = db.get(Assignment, assignment_id)
    was_confirmed = before is not None and str(before.status) == "confirmed"
    session = board.confirm_assignment(db, assignment_id, user)
    if session is not None and not was_confirmed:
        # 이번 탭으로 전원 확정이 성립한 순간에만 알림 (재탭 멱등 경로는 무알림)
        notifications.notify_session_confirmed(db, session)
    return {"session_id": session.id if session else None}


@router.get("/crews/{crew_id}/sessions")
def list_sessions(crew_id: str, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    _require_member(db, crew_id, user.id)
    rows = db.scalars(select(CareSession).where(CareSession.crew_id == crew_id)).all()
    return [
        {
            "id": s.id, "caregiver_id": s.caregiver_id, "date": s.date,
            "start_hour": s.start_hour, "end_hour": s.end_hour,
            "handoff_started_at": s.handoff_started_at.isoformat() if s.handoff_started_at else None,
            "handoff_ended_at": s.handoff_ended_at.isoformat() if s.handoff_ended_at else None,
        }
        for s in rows
    ]


@router.post("/sessions/{session_id}/handoff/{action}")
def handoff(session_id: str, action: str, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    """인계 확인 탭. 기록은 소급 조작 불가 — 이미 찍힌 시각은 덮어쓰지 않는다 (실패 전략 §4-A)."""
    from app.domain.models import _now

    session = db.get(CareSession, session_id)
    if session is None:
        raise HTTPException(status_code=404)
    _require_member(db, session.crew_id, user.id)
    if action == "start" and session.handoff_started_at is None:
        session.handoff_started_at = _now()
    elif action == "end" and session.handoff_ended_at is None:
        session.handoff_ended_at = _now()
        from app.domain import ledger_service

        ledger_service.record_session_credits(db, session)
    db.flush()
    return {"ok": True}


def _assignment_out(db: Session, a: Assignment) -> dict:
    rows = db.scalars(select(AssignmentChild).where(AssignmentChild.assignment_id == a.id)).all()
    out = []
    for r in rows:
        child = db.get(Child, r.child_id)
        out.append(
            {
                "child_id": r.child_id,
                "child_name": child.name,
                "guardian_id": child.guardian_id,
                "guardian_confirmed": r.guardian_confirmed,
            }
        )
    return {
        "id": a.id,
        "caregiver_id": a.caregiver_id,
        "date": a.date,
        "start_hour": a.start_hour,
        "end_hour": a.end_hour,
        "status": str(a.status),
        "children": out,
    }
