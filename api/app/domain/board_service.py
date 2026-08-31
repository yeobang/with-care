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
from app.domain.models import Consent
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


def _merge_intervals(intervals: list[tuple[int, int]]) -> list[tuple[int, int]]:
    """인접(끝==시작)·중첩 구간 병합 — 1시간 슬롯 여러 개 = 연속 가능시간 (P8)."""
    out: list[list[int]] = []
    for st, en in sorted(intervals):
        if out and st <= out[-1][1]:
            out[-1][1] = max(out[-1][1], en)
        else:
            out.append([st, en])
    return [(a, b) for a, b in out]


def _need_units(needs: list[BoardSlot]) -> list[tuple[str, str, int, int]]:
    """(guardian_id, child_id, start, end) — 아이별로 병합된 '필요' 구간."""
    by_child: dict[tuple[str, str], list[tuple[int, int]]] = {}
    for n in needs:
        by_child.setdefault((n.user_id, n.child_id), []).append((n.start_hour, n.end_hour))
    return [
        (guardian, child, st, en)
        for (guardian, child), ivs in by_child.items()
        for st, en in _merge_intervals(ivs)
    ]


def _avail_by_caregiver(avails: list[BoardSlot]) -> dict[str, list[tuple[int, int]]]:
    by_user: dict[str, list[tuple[int, int]]] = {}
    for a in avails:
        by_user.setdefault(a.user_id, []).append((a.start_hour, a.end_hour))
    return {uid: _merge_intervals(ivs) for uid, ivs in by_user.items()}


def add_slot(
    db: DbSession, crew_id: str, user: User, *, kind: SlotKind,
    date: str, start_hour: int, end_hour: int, child_id: str | None = None,
) -> BoardSlot:
    _require_member(db, crew_id, user.id)
    _require_active(db, crew_id)
    _require_consent(db, crew_id, user.id)
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

    # 멱등(재호출·연타): 아무 가정도 확정하지 않은 PROPOSED 후보는 정리 후 재생성한다.
    # 확정 탭이 하나라도 찍힌 후보는 보존 — I4의 탭을 시스템이 소급 소실시키지 않는다.
    kept_keys: set[tuple] = set()
    for a in db.scalars(
        select(Assignment).where(Assignment.crew_id == crew_id, Assignment.date == date)
    ).all():
        rows = db.scalars(
            select(AssignmentChild).where(AssignmentChild.assignment_id == a.id)
        ).all()
        if a.status == ProposalStatus.PROPOSED and not any(r.guardian_confirmed for r in rows):
            for r in rows:
                db.delete(r)
            db.delete(a)
        else:
            kept_keys.add((a.caregiver_id, a.start_hour, a.end_hour, frozenset(r.child_id for r in rows)))
    db.flush()

    # P8: 인접·중첩 슬롯 병합 후 매칭 (1시간 슬롯 여러 개 = 연속 가능시간)
    units = _need_units(needs)
    proposals: list[Assignment] = []
    for caregiver_id, merged in _avail_by_caregiver(avails).items():
        for a_start, a_end in merged:
            covered = [
                u for u in units
                if u[0] != caregiver_id and u[2] >= a_start and u[3] <= a_end
            ]
            if not covered:
                continue
            start = min(u[2] for u in covered)
            end = max(u[3] for u in covered)
            child_ids = {u[1] for u in covered}
            if (caregiver_id, start, end, frozenset(child_ids)) in kept_keys:
                continue  # 보존된 후보와 동일 — 중복 생성 금지
            assignment = Assignment(
                crew_id=crew_id, caregiver_id=caregiver_id,
                date=date, start_hour=start, end_hour=end,
            )
            db.add(assignment)
            db.flush()
            for cid in child_ids:
                db.add(AssignmentChild(assignment_id=assignment.id, child_id=cid))
            proposals.append(assignment)
    db.flush()
    return proposals


def find_gaps(db: DbSession, crew_id: str, user: User, date: str) -> list[dict]:
    """빈칸 감지 (P8): 어떤 타인 돌봄자의 병합 가능구간에도 완전히 들어가지 않는 필요 구간.

    부분 커버도 빈칸으로 본다 — 반쪽 돌봄은 성립하지 않는다는 보수적 기준.
    (폴백 2단계 '시터 공구 제안'은 P10에서 이 결과를 입력으로 쓴다.)
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
    by_caregiver = _avail_by_caregiver(avails)
    gaps = []
    for guardian, child, st, en in _need_units(needs):
        covered = any(
            cg != guardian and a_start <= st and en <= a_end
            for cg, merged in by_caregiver.items()
            for a_start, a_end in merged
        )
        if not covered:
            gaps.append(
                {"guardian_id": guardian, "child_id": child, "start_hour": st, "end_hour": en}
            )
    return gaps


def decline_assignment(db: DbSession, assignment_id: str, user: User) -> Assignment:
    """배정 후보 거절 (I4의 다른 반쪽 — 거절도 사람의 명시적 탭).

    자기 아이가 포함된 가정 또는 돌봄자 본인만 거절할 수 있다. 거절은 후보 전체를
    무효화한다 (부분 거절 없음 — 후보는 다시 제안으로 재구성).
    확정된 배정의 취소(노쇼·급취소)는 P9 규약 집행 흐름에서 다룬다.
    """
    assignment = db.get(Assignment, assignment_id)
    if assignment is None:
        raise ValueError("존재하지 않는 배정 후보")
    _require_member(db, assignment.crew_id, user.id)
    _require_consent(db, assignment.crew_id, user.id)
    if assignment.status == ProposalStatus.DECLINED:
        return assignment  # 재탭 멱등
    if assignment.status == ProposalStatus.CONFIRMED:
        raise ValueError("이미 확정된 배정은 거절할 수 없다 (취소 흐름은 별도)")
    rows = db.scalars(
        select(AssignmentChild).where(AssignmentChild.assignment_id == assignment_id)
    ).all()
    involved = user.id == assignment.caregiver_id or any(
        db.get(Child, r.child_id).guardian_id == user.id for r in rows
    )
    if not involved:
        raise errors.HumanChoiceViolation("자기 아이가 포함된 후보 또는 자기 후보만 거절할 수 있다 (I4)")
    assignment.status = ProposalStatus.DECLINED
    db.flush()
    return assignment


def confirm_assignment(db: DbSession, assignment_id: str, guardian: User) -> CareSession | None:
    """가정별 확정 탭 (I4). 자기 아이 몫만 확정할 수 있다.

    전원이 확정되는 순간에만 세션이 생성되고, 생성 직전 I3 가드가 돈다.
    """
    assignment = db.get(Assignment, assignment_id)
    if assignment is None:
        raise ValueError("존재하지 않는 배정 후보")
    _require_member(db, assignment.crew_id, guardian.id)
    _require_consent(db, assignment.crew_id, guardian.id)

    if assignment.status == ProposalStatus.CONFIRMED:
        # 재탭 멱등: 이미 확정된 배정은 기존 세션을 그대로 돌려준다 (중복 세션 생성 금지)
        return db.scalar(select(CareSession).where(CareSession.assignment_id == assignment.id))
    if assignment.status == ProposalStatus.DECLINED:
        raise ValueError("거절된 배정 후보는 확정할 수 없다")

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

def _require_consent(db: DbSession, crew_id: str, user_id: str) -> None:
    """I2: 활성화 이후에 합류한 멤버도 합의 없이는 보드에 참여할 수 없다."""
    consent = db.scalar(
        select(Consent).where(Consent.crew_id == crew_id, Consent.user_id == user_id)
    )
    if consent is None or not consent.is_complete:
        raise errors.ConsentMissing("포괄 합의 없이는 크루 활동에 참여할 수 없다 (I2)")


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
