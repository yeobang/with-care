"""알림 조립 계층 (P7) — "조르기는 전자동, 고르기는 사람" (I4).

원칙:
- 모든 발송은 best-effort: 실패는 로그만 남기고 삼킨다. 푸시가 죽어도 본 흐름은 산다 (degrade).
- I6: 수신자는 항상 해당 크루/세션의 멤버로만 계산한다.
- 앱은 재촉·안내만 한다 — 어떤 알림도 확정을 대신하지 않는다 (I4).
"""

import logging

from sqlalchemy import select
from sqlalchemy.orm import Session as DbSession

from app.domain.models import (
    Assignment,
    AssignmentChild,
    CareSession,
    Child,
    Crew,
    CrewMember,
    CrewStatus,
    PushToken,
    Settlement,
    SettlementStatus,
)
from app.infra import push

log = logging.getLogger(__name__)


def _send_to(db: DbSession, user_ids: set[str], title: str, body: str) -> None:
    """토큰 있는 수신자에게만 발송. 죽은 토큰(DeviceNotRegistered)은 정리."""
    try:
        rows = db.scalars(
            select(PushToken).where(PushToken.user_id.in_(list(user_ids)))
        ).all()
        if not rows:
            return
        tickets = push.send(
            [{"to": r.token, "title": title, "body": body} for r in rows]
        )
        for row, ticket in zip(rows, tickets):
            if ticket.get("details", {}).get("error") == "DeviceNotRegistered":
                db.delete(row)
        db.flush()
    except Exception:
        log.warning("푸시 발송 실패 — 본 흐름에 영향 없음", exc_info=True)


def _assignment_guardians(db: DbSession, assignment_id: str) -> set[str]:
    rows = db.scalars(
        select(AssignmentChild).where(AssignmentChild.assignment_id == assignment_id)
    ).all()
    return {db.get(Child, r.child_id).guardian_id for r in rows}


# --- 이벤트 알림 ---


def notify_proposals(db: DbSession, proposals: list[Assignment]) -> None:
    """배정 후보 도착 → 관련 가정에. 확정은 사람의 탭 (I4 — 앱은 조르기만)."""
    for a in proposals:
        _send_to(
            db,
            _assignment_guardians(db, a.id),
            "돌봄 후보가 나왔어요",
            f"{a.date} {a.start_hour}~{a.end_hour}시 — 보드에서 확정해주세요",
        )


def notify_session_confirmed(db: DbSession, session: CareSession) -> None:
    """전원 확정 → 세션 성립. 돌봄자 포함 전원에게."""
    targets = _assignment_guardians(db, session.assignment_id) | {session.caregiver_id}
    _send_to(
        db,
        targets,
        "돌봄이 확정됐어요",
        f"{session.date} {session.start_hour}~{session.end_hour}시",
    )


def notify_photo(db: DbSession, session: CareSession, uploader_id: str) -> None:
    """세션 사진 도착 → 업로더 제외 해당 가정들에 (크루 한정, I6)."""
    targets = _assignment_guardians(db, session.assignment_id) - {uploader_id}
    _send_to(db, targets, "사진이 도착했어요", "오늘 돌봄 사진을 확인해보세요")


def notify_gap_rerequest(db: DbSession, crew_id: str, gaps: list[dict], requester_id: str) -> None:
    """빈칸 재요청 (P8) — 크루 전체에 '조르기'. 요청일 뿐 배정이 아니다 (I4)."""
    members = db.scalars(
        select(CrewMember).where(CrewMember.crew_id == crew_id)
    ).all()
    _send_to(
        db,
        {m.user_id for m in members} - {requester_id},
        "돌봄 빈칸 재요청",
        f"채워지지 않은 돌봄 {len(gaps)}건 — 가능한 시간을 열어주실 수 있나요?",
    )


def notify_declined(db: DbSession, assignment: Assignment, decliner_id: str) -> None:
    """후보 거절 (P8) — 관련 가정·돌봄자에게 (거절한 사람 제외)."""
    targets = (
        _assignment_guardians(db, assignment.id) | {assignment.caregiver_id}
    ) - {decliner_id}
    _send_to(
        db,
        targets,
        "배정 후보가 거절됐어요",
        f"{assignment.date} {assignment.start_hour}~{assignment.end_hour}시 — 다른 후보를 확정하거나 다시 제안해주세요",
    )


# --- 독촉·리마인드 (악역의 자동화) ---


def nudge_settlements(db: DbSession, crew_id: str) -> int:
    """크루의 미정산(PENDING)을 보낸 쪽에 독촉. 발송 대상 사용자 수 반환."""
    pending = db.scalars(
        select(Settlement).where(
            Settlement.crew_id == crew_id,
            Settlement.status == SettlementStatus.PENDING,
        )
    ).all()
    per_user: dict[str, int] = {}
    for s in pending:
        per_user[s.from_user] = per_user.get(s.from_user, 0) + s.amount_krw
    for user_id, total in per_user.items():
        _send_to(
            db,
            {user_id},
            "미정산 알림",
            f"{total:,}원이 아직 미정산이에요 — 송금 후 받은 분이 확인하면 끝나요",
        )
    return len(per_user)


def nudge_all_pending(db: DbSession) -> None:
    """스케줄러용: 미정산이 있는 모든 크루에 독촉 (가정: 매일 09:00 KST)."""
    crew_ids = db.scalars(
        select(Settlement.crew_id)
        .where(Settlement.status == SettlementStatus.PENDING)
        .distinct()
    ).all()
    for crew_id in crew_ids:
        nudge_settlements(db, crew_id)


def remind_weekly_board(db: DbSession) -> None:
    """스케줄러용: 활성 크루 전원에 다음 주 보드 입력 리마인드 (가정: 일 18:00 KST)."""
    crews = db.scalars(select(Crew).where(Crew.status == CrewStatus.ACTIVE)).all()
    for crew in crews:
        members = db.scalars(
            select(CrewMember).where(CrewMember.crew_id == crew.id)
        ).all()
        _send_to(
            db,
            {m.user_id for m in members},
            f"{crew.name} 주간 보드",
            "다음 주 가능한 시간과 돌봄이 필요한 시간을 입력해주세요",
        )
