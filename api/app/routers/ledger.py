from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.orm import Session

from app import notifications
from app.deps import get_current_user, get_db
from app.domain import ledger_service as ledger
from app.domain.crew_service import _require_member
from app.domain.models import Settlement, SettlementStatus, User

router = APIRouter(tags=["ledger"])


@router.get("/crews/{crew_id}/ledger")
def crew_balances(crew_id: str, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    return ledger.balances(db, crew_id, user)


@router.post("/crews/{crew_id}/settlements/{month}/compute")
def compute(crew_id: str, month: str, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    rows = ledger.compute_settlement(db, crew_id, month, user)
    return [_out(s) for s in rows]


@router.get("/crews/{crew_id}/settlements")
def list_settlements(crew_id: str, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    _require_member(db, crew_id, user.id)
    rows = db.scalars(select(Settlement).where(Settlement.crew_id == crew_id)).all()
    return [_out(s) for s in rows]


@router.post("/crews/{crew_id}/settlements/nudge")
def nudge(crew_id: str, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    """미정산 독촉 (수동 트리거 — 매일 09:00 자동 독촉과 별개). 앱이 악역을 대신한다."""
    _require_member(db, crew_id, user.id)
    return {"nudged_users": notifications.nudge_settlements(db, crew_id)}


@router.post("/settlements/{settlement_id}/received")
def received(settlement_id: str, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    return _out(ledger.confirm_settlement(db, settlement_id, user))


def _out(s: Settlement) -> dict:
    return {
        "id": s.id,
        "month": s.month,
        "from_user": s.from_user,
        "to_user": s.to_user,
        "amount_krw": s.amount_krw,
        "status": str(s.status),
        "unsettled": s.status != SettlementStatus.CONFIRMED,
    }
