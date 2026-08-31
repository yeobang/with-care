"""장부·정산 서비스 (P4). 불변식 I5의 영역.

이 모듈은 기록과 계산만 한다. 돈을 이동시키는 코드는 여기에도, 이 코드베이스 어디에도 없다.
(딥링크 URL 조립은 앱의 몫 — 서버는 금액과 상대만 계산한다.)
"""

from sqlalchemy import func, select
from sqlalchemy.orm import Session as DbSession

from app.domain import errors
from app.domain.crew_service import _require_member
from app.domain.models import (
    Assignment,
    AssignmentChild,
    CareSession,
    Charter,
    Child,
    LedgerEntry,
    Settlement,
    SettlementMode,
    SettlementStatus,
    User,
)


def record_session_credits(db: DbSession, session: CareSession) -> None:
    """세션 종료(돌려받음 확인) 시 1회 기입. 아이·시간, 제로섬 (§21).

    멱등: 같은 세션에 이미 기입돼 있으면 건너뜀 (기록은 소급 조작 불가).
    """
    existing = db.scalar(
        select(LedgerEntry).where(LedgerEntry.session_id == session.id)
    )
    if existing is not None:
        return
    hours = session.end_hour - session.start_hour
    rows = db.scalars(
        select(AssignmentChild).where(AssignmentChild.assignment_id == session.assignment_id)
    ).all()
    per_guardian: dict[str, int] = {}
    for r in rows:
        child = db.get(Child, r.child_id)
        if child.guardian_id == session.caregiver_id:
            continue  # 자기 아이는 장부 대상 아님
        per_guardian[child.guardian_id] = per_guardian.get(child.guardian_id, 0) + hours
    total = sum(per_guardian.values())
    if total == 0:
        return
    db.add(
        LedgerEntry(
            crew_id=session.crew_id, user_id=session.caregiver_id,
            session_id=session.id, delta_child_hours=total,
        )
    )
    for guardian_id, child_hours in per_guardian.items():
        db.add(
            LedgerEntry(
                crew_id=session.crew_id, user_id=guardian_id,
                session_id=session.id, delta_child_hours=-child_hours,
            )
        )
    db.flush()


def balances(db: DbSession, crew_id: str, requester: User) -> dict[str, int]:
    _require_member(db, crew_id, requester.id)
    rows = db.execute(
        select(LedgerEntry.user_id, func.sum(LedgerEntry.delta_child_hours))
        .where(LedgerEntry.crew_id == crew_id)
        .group_by(LedgerEntry.user_id)
    ).all()
    return {user_id: int(total) for user_id, total in rows}


def compute_settlement(db: DbSession, crew_id: str, month: str, requester: User) -> list[Settlement]:
    """월말 정산 제안 계산 (settlement_mode=credit 크루만). 멱등 — 이미 계산된 달은 그대로 반환.

    잔액 음수 가정 → 양수 가정으로 greedy 매칭. 금액 = 크레딧 × 규약 단가.
    """
    _require_member(db, crew_id, requester.id)
    existing = db.scalars(
        select(Settlement).where(Settlement.crew_id == crew_id, Settlement.month == month)
    ).all()
    if existing:
        return list(existing)

    charter = db.scalar(select(Charter).where(Charter.crew_id == crew_id))
    if charter is None or charter.settlement_mode != SettlementMode.CREDIT:
        return []  # rotation/none 크루는 기록만 (§21)

    bal = balances(db, crew_id, requester)
    # §22-3: 미확정(PENDING) 정산 몫은 차감 — 이미 제안된 몫을 다시 제안하지 않는다.
    # (확정된 몫은 confirm_settlement의 상쇄 기입으로 이미 잔액에 반영돼 있다.)
    pending = db.scalars(
        select(Settlement).where(
            Settlement.crew_id == crew_id, Settlement.status == SettlementStatus.PENDING
        )
    ).all()
    for p in pending:
        bal[p.from_user] = bal.get(p.from_user, 0) + p.amount_credits
        bal[p.to_user] = bal.get(p.to_user, 0) - p.amount_credits

    debtors = sorted([(u, -b) for u, b in bal.items() if b < 0], key=lambda x: -x[1])
    creditors = sorted([(u, b) for u, b in bal.items() if b > 0], key=lambda x: -x[1])
    result: list[Settlement] = []
    di, ci = 0, 0
    debtors = [[u, amt] for u, amt in debtors]
    creditors = [[u, amt] for u, amt in creditors]
    while di < len(debtors) and ci < len(creditors):
        d, c = debtors[di], creditors[ci]
        credits = min(d[1], c[1])
        settlement = Settlement(
            crew_id=crew_id, month=month,
            from_user=d[0], to_user=c[0],
            amount_krw=credits * charter.credit_price_krw,
            amount_credits=credits,
        )
        db.add(settlement)
        result.append(settlement)
        d[1] -= credits
        c[1] -= credits
        if d[1] == 0:
            di += 1
        if c[1] == 0:
            ci += 1
    db.flush()
    return result


def confirm_settlement(db: DbSession, settlement_id: str, user: User) -> Settlement:
    """"받았어요" 확인 — 받는 쪽만 누를 수 있다 (송금 사실의 증인은 수취인)."""
    from app.domain.models import _now

    settlement = db.get(Settlement, settlement_id)
    if settlement is None:
        raise ValueError("존재하지 않는 정산")
    _require_member(db, settlement.crew_id, user.id)
    if settlement.to_user != user.id:
        raise errors.HumanChoiceViolation("정산 확인은 받는 사람만 할 수 있다")
    if settlement.status != SettlementStatus.CONFIRMED:
        settlement.status = SettlementStatus.CONFIRMED
        settlement.confirmed_at = _now()
        # §22: 정산 확정 = 반대 부호 기입 — 정산된 몫을 장부에서 상쇄한다 (상쇄 쌍도 제로섬).
        # 감사 원칙 그대로: 기존 항목은 건드리지 않고 새 항목을 더할 뿐이다.
        db.add(
            LedgerEntry(
                crew_id=settlement.crew_id, user_id=settlement.from_user,
                settlement_id=settlement.id, delta_child_hours=settlement.amount_credits,
            )
        )
        db.add(
            LedgerEntry(
                crew_id=settlement.crew_id, user_id=settlement.to_user,
                settlement_id=settlement.id, delta_child_hours=-settlement.amount_credits,
            )
        )
        db.flush()
    return settlement
