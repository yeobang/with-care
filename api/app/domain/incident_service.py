"""규약 집행 (P9): 세션 취소·노쇼 기록 — 판정은 사람, 고지는 앱 (§24-1).

기록은 append-only: 수정·삭제 경로가 없다 (소급 조작 불가 — §4-A 기록 무결성).
벌금은 규약 스냅샷을 고지·가시화까지만 — 징수 코드는 이 코드베이스 어디에도 없다 (I5).
"""

from sqlalchemy import select
from sqlalchemy.orm import Session as DbSession

from app.domain import errors
from app.domain.crew_service import _require_member
from app.domain.models import (
    AssignmentChild,
    CareSession,
    Charter,
    Child,
    IncidentKind,
    SessionIncident,
    User,
    _now,
)


def _participants(db: DbSession, session: CareSession) -> set[str]:
    rows = db.scalars(
        select(AssignmentChild).where(AssignmentChild.assignment_id == session.assignment_id)
    ).all()
    return {db.get(Child, r.child_id).guardian_id for r in rows} | {session.caregiver_id}


def cancel_session(db: DbSession, session_id: str, user: User) -> CareSession:
    """시작 전 취소. 시작된 세션의 문제는 취소가 아니라 인시던트 기록으로 (기록 무결성)."""
    session = db.get(CareSession, session_id)
    if session is None:
        raise ValueError("존재하지 않는 세션")
    _require_member(db, session.crew_id, user.id)
    if user.id not in _participants(db, session):
        raise errors.HumanChoiceViolation("세션 참여자만 취소할 수 있다 (I4)")
    if session.handoff_started_at is not None:
        raise ValueError("이미 시작된 세션은 취소할 수 없다 (문제는 노쇼·사고 기록으로)")
    if session.canceled_at is None:  # 재탭 멱등
        session.canceled_at = _now()
        session.canceled_by = user.id
        db.flush()
    return session


def report_incident(
    db: DbSession, session_id: str, reporter: User, *, kind: IncidentKind, offender_id: str
) -> tuple[SessionIncident, bool]:
    """노쇼·급취소 기록 → (기록, 신규 여부). 같은 세션·대상·종류 재기록은 멱등."""
    session = db.get(CareSession, session_id)
    if session is None:
        raise ValueError("존재하지 않는 세션")
    _require_member(db, session.crew_id, reporter.id)
    participants = _participants(db, session)
    if reporter.id not in participants:
        raise errors.HumanChoiceViolation("세션 참여자만 기록할 수 있다 (I4)")
    if offender_id not in participants:
        raise ValueError("세션 참여자만 대상으로 기록할 수 있다")
    existing = db.scalar(
        select(SessionIncident).where(
            SessionIncident.session_id == session_id,
            SessionIncident.offender_id == offender_id,
            SessionIncident.kind == kind,
        )
    )
    if existing is not None:
        return existing, False
    charter = db.scalar(select(Charter).where(Charter.crew_id == session.crew_id))
    incident = SessionIncident(
        session_id=session_id,
        crew_id=session.crew_id,
        reported_by=reporter.id,
        offender_id=offender_id,
        kind=kind,
        fine_krw=charter.no_show_fine_krw if charter else 0,  # 기록 시점 스냅샷
    )
    db.add(incident)
    db.flush()
    return incident, True


def incident_counts(db: DbSession, crew_id: str, requester: User) -> list[dict]:
    """반복 가시화 배지 (§4-A): 크루 멤버만 조회 (I6)."""
    _require_member(db, crew_id, requester.id)
    rows = db.scalars(
        select(SessionIncident).where(SessionIncident.crew_id == crew_id)
    ).all()
    per: dict[str, dict] = {}
    for r in rows:
        d = per.setdefault(
            r.offender_id, {"user_id": r.offender_id, "count": 0, "fine_krw_total": 0}
        )
        d["count"] += 1
        d["fine_krw_total"] += r.fine_krw
    return sorted(per.values(), key=lambda d: -d["count"])
