"""주간 보드 서비스 (P2). 불변식 I3·I4의 유일한 강제 지점.

I4(고르기는 사람): 이 모듈에는 배정을 자동 확정하는 코드 경로가 존재하지 않는다.
propose_assignments()는 후보를 '나열'할 뿐이고, 세션은 관련 가정 전원의
confirm_assignment() 탭이 모여야만 생성된다.
"""

from datetime import date as date_type

from sqlalchemy import select
from sqlalchemy.orm import Session as DbSession

from app.domain import errors
from app.domain.crew_service import _require_member
from app.domain.models import (
    Assignment,
    AssignmentChild,
    BoardSlot,
    CareSession,
    Child,
    Crew,
    CrewStatus,
    ProposalStatus,
    SlotKind,
    User,
)

MAX_PRESCHOOLERS_PER_CAREGIVER = 4  # I3: 영유아보육법 "상시 5인" 선 아래 (docs/00-ideation.md §18)


def add_slot(
    db: DbSession, crew_id: str, user: User, *, kind: SlotKind,
    date: str, start_hour: int, end_hour: int, child_id: str | None = None,
) -> BoardSlot:
    _require_member(db, crew_id, user.id)
    _require_active(db, crew_id)
    if not (0 <= start_hour < end_hour <= 24):
        raise ValueError("시간 범위가 올바르지 않다")
    if kind == SlotKind.NEED and child_id is None:
        raise ValueError("돌봄 필요 칸에는 아이가 지정되어야 한다")
    slot = BoardSlot(
        crew_id=crew_id, user_id=user.id, kind=kind,
        date=date, start_hour=start_hour, end_hour=end_hour, child_id=child_id,
    )
    db.add(slot)
    db.flush()
    return slot


def propose_assignments(db: DbSession, crew_id: str, user: User, date: str) -> list[Assignment]:
    """빈칸(NEED)과 가능시간(AVAILABLE)의 겹침으로 배정 '후보'를 나열한다.

    후보는 PROPOSED 상태로만 생성되며 아무 효력이 없다 (I4).
    같은 시간대에 가능한 돌봄자가 여럿이면 후보도 여럿 만든다 — 단일 추천 금지.
    """
    _require_member(db, crew_id, user.id)
    _require_active(db, crew_id)
    needs = db.scalars(
        select(BoardSlot).where(
            BoardSlot.crew_id == crew_id, BoardSlot.date == date, BoardSlot.kind == SlotKind.NEED
        )
    ).all()
    avails = db.scalars(
        select(BoardSlot).where(
            BoardSlot.crew_id == crew_id, BoardSlot.date == date, BoardSlot.kind == SlotKind.AVAILABLE
        )
    ).all()
    proposals: list[Assignment] = []
    for avail in avails:
        covered = [
            n for n in needs
            if n.user_id != avail.user_id
            and n.start_hour >= avail.start_hour and n.end_hour <= avail.end_hour
        ]
        if not covered:
            continue
        start = min(n.start_hour for n in covered)
        end = max(n.end_hour for n in covered)
        assignment = Assignment(
            crew_id=crew_id, caregiver_id=avail.user_id,
            date=date, start_hour=start, end_hour=end,
        )
        db.add(assignment)
        db.flush()
        for n in covered:
            db.add(AssignmentChild(assignment_id=assignment.id, child_id=n.child_id))
        proposals.append(assignment)
    db.flush()
    return proposals


def confirm_assignment(db: DbSession, assignment_id: str, guardian: User) -> CareSession | None:
    """가정별 확정 탭 (I4). 자기 아이 몫만 확정할 수 있다.

    전원이 확정되는 순간에만 세션이 생성되고, 생성 직전 I3 가드가 돈다.
    """
    assignment = db.get(Assignment, assignment_id)
    if assignment is None:
        raise ValueError("존재하지 않는 배정 후보")
    _require_member(db, assignment.crew_id, guardian.id)

    rows = db.scalars(
        select(AssignmentChild).where(AssignmentChild.assignment_id == assignment_id)
    ).all()
    mine = [r for r in rows if db.get(Child, r.child_id).guardian_id == guardian.id]
    if not mine:
        raise errors.HumanChoiceViolation("자기 아이의 배정만 확정할 수 있다 (I4)")
    for r in mine:
        r.guardian_confirmed = True
    db.flush()

    if not all(r.guardian_confirmed for r in rows):
        return None  # 아직 전원 확정 아님 — 효력 없음

    _guard_unlicensed_pattern(db, assignment, rows)  # I3
    assignment.status = ProposalStatus.CONFIRMED
    session = CareSession(
        crew_id=assignment.crew_id,
        assignment_id=assignment.id,
        caregiver_id=assignment.caregiver_id,
        date=assignment.date,
        start_hour=assignment.start_hour,
        end_hour=assignment.end_hour,
    )
    db.add(session)
    db.flush()
    return session


# --- 내부 가드 ---

def _require_active(db: DbSession, crew_id: str) -> None:
    crew = db.get(Crew, crew_id)
    if crew is None or crew.status != CrewStatus.ACTIVE:
        raise errors.CharterIncomplete("활성화되지 않은 크루에서는 보드를 쓸 수 없다 (I7)")


def _is_preschooler(child: Child, on_date: str) -> bool:
    """영유아(취학 전) 판정 — I8의 허용 예외: I3 카운트 전용 (가드레일 §2).

    근사 기준: 세션 날짜 기준 만 7세 미만. 정확한 취학 판정은 법률 게이트 2 결론 후 보정.
    """
    birth_year, birth_month = map(int, child.birth_year_month.split("-"))
    on = date_type.fromisoformat(on_date)
    age = on.year - birth_year - (1 if (on.month, 1) < (birth_month, 1) else 0)  # I8-allow: I3 영유아 카운트
    return age < 7  # I8-allow: I3 영유아 카운트


def _guard_unlicensed_pattern(db: DbSession, assignment: Assignment, rows: list[AssignmentChild]) -> None:
    """I3: 돌봄자 1인 + (자기 아이 제외) 영유아 5인 이상 세션 금지 (이웃 트랙)."""
    others_preschoolers = 0
    for r in rows:
        child = db.get(Child, r.child_id)
        if child.guardian_id == assignment.caregiver_id:
            continue  # 자기 아이는 카운트 제외
        if _is_preschooler(child, assignment.date):
            others_preschoolers += 1
    if others_preschoolers > MAX_PRESCHOOLERS_PER_CAREGIVER:
        raise errors.UnlicensedCarePattern(
            f"돌봄자 1인이 타인 영유아 {others_preschoolers}명을 볼 수 없다 (I3: 상한 {MAX_PRESCHOOLERS_PER_CAREGIVER})"
        )
