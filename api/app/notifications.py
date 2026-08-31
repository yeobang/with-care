"""알림 조립 계층 (P7) — "조르기는 전자동, 고르기는 사람" (I4).

원칙:
- 모든 발송은 best-effort: 실패는 로그만 남기고 삼킨다. 푸시가 죽어도 본 흐름은 산다 (degrade).
- I6: 수신자는 항상 해당 크루/세션의 멤버로만 계산한다.
- 앱은 재촉·안내만 한다 — 어떤 알림도 확정을 대신하지 않는다 (I4).
"""

import logging

from sqlalchemy import func, select
from sqlalchemy.orm import Session as DbSession

from app.domain.models import (
    Assignment,
    AssignmentChild,
    CareSession,
    Charter,
    Child,
    Crew,
    CrewMember,
    CrewStatus,
    LedgerEntry,
    PushToken,
    SessionIncident,
    Settlement,
    SettlementMode,
    SettlementStatus,
    SitterQuote,
    SitterQuoteFamily,
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


def _session_guardians(db: DbSession, session: CareSession) -> set[str]:
    """세션 출처(이웃 배정/시터 견적)에 따라 관련 가정을 계산 (P10)."""
    if session.assignment_id is not None:
        return _assignment_guardians(db, session.assignment_id)
    if session.sitter_quote_id is not None:
        fams = db.scalars(
            select(SitterQuoteFamily).where(SitterQuoteFamily.quote_id == session.sitter_quote_id)
        ).all()
        return {f.guardian_id for f in fams}
    return set()


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
    targets = _session_guardians(db, session) | {session.caregiver_id}
    _send_to(
        db,
        targets,
        "돌봄이 확정됐어요",
        f"{session.date} {session.start_hour}~{session.end_hour}시",
    )


def notify_photo(db: DbSession, session: CareSession, uploader_id: str) -> None:
    """세션 사진 도착 → 업로더 제외 해당 가정들에 (크루 한정, I6)."""
    targets = _session_guardians(db, session) - {uploader_id}
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


def notify_cancel(db: DbSession, session: CareSession, canceler_id: str) -> None:
    """세션 취소 (P9) — 취소한 사람 제외 참여자 전원에게."""
    targets = (_session_guardians(db, session) | {session.caregiver_id}) - {canceler_id}
    _send_to(
        db, targets, "세션이 취소됐어요",
        f"{session.date} {session.start_hour}~{session.end_hour}시 — 보드에서 다시 조율해주세요",
    )


def notify_incident(db: DbSession, incident: SessionIncident) -> None:
    """벌금 자동 고지 (§24-1) — 사람이 악역이 되지 않게 앱이 말한다. 징수는 안 한다 (I5)."""
    kind_ko = "노쇼" if str(incident.kind) == "no_show" else "급취소"
    _send_to(
        db, {incident.offender_id}, f"{kind_ko} 기록 안내",
        f"크루 규약에 따라 벌금 {incident.fine_krw:,}원이 안내돼요 (앱은 징수하지 않아요)",
    )


def notify_new_quote(db: DbSession, quote: SitterQuote) -> None:
    """시터 견적 도착 (P10) — 참여 가정들에게. 확정은 각 가정의 탭 (I4)."""
    fams = db.scalars(
        select(SitterQuoteFamily).where(SitterQuoteFamily.quote_id == quote.id)
    ).all()
    surge = " · 당일 긴급 할증 1.5배" if quote.surge else ""
    _send_to(
        db, {f.guardian_id for f in fams}, "시터 견적 도착",
        f"총 {quote.total_krw:,}원 · 가정당 {quote.per_family_krw:,}원{surge} — 확정 탭은 각 가정이 직접",
    )


def notify_sitter_fallback(db: DbSession, crew_id: str) -> None:
    """§25-5: 시터 세션 취소 → 크루 전체 즉시 알림 + 공구 재가동 안내 (§4-A)."""
    members = db.scalars(select(CrewMember).where(CrewMember.crew_id == crew_id)).all()
    _send_to(
        db, {m.user_id for m in members}, "시터 돌봄 취소",
        "공구 요청을 다시 열었어요 — 크루 재요청 폴백을 재가동합니다",
    )


def notify_recurrence(db: DbSession, crew_id: str) -> None:
    """§25-6: 상시성 주의 경고 — 차단이 아니라 안내 (§19-2: 정기 돌봄은 자격·등록 통로)."""
    members = db.scalars(select(CrewMember).where(CrewMember.crew_id == crew_id)).all()
    _send_to(
        db, {m.user_id for m in members}, "상시성 주의",
        "같은 시터와의 돌봄이 이번 주 2회 이상이에요 — 정기 돌봄은 자격·등록 통로 검토를 권해요",
    )


ROTATION_BALANCE_THRESHOLD = 4  # §24-3 가정: 아이·시간. 전역 기본 — 추후 규약화 후보


def notify_rotation_balance(db: DbSession) -> None:
    """rotation 크루 균형 알림 (§24-3): 잔액 최대−최소 ≥ 임계면 교대 제안."""
    for crew in db.scalars(select(Crew).where(Crew.status == CrewStatus.ACTIVE)).all():
        charter = db.scalar(select(Charter).where(Charter.crew_id == crew.id))
        if charter is None or charter.settlement_mode != SettlementMode.ROTATION:
            continue
        rows = db.execute(
            select(LedgerEntry.user_id, func.sum(LedgerEntry.delta_child_hours))
            .where(LedgerEntry.crew_id == crew.id)
            .group_by(LedgerEntry.user_id)
        ).all()
        if not rows:
            continue
        vals = [int(v) for _, v in rows]
        if max(vals) - min(vals) < ROTATION_BALANCE_THRESHOLD:
            continue
        members = db.scalars(select(CrewMember).where(CrewMember.crew_id == crew.id)).all()
        _send_to(
            db, {m.user_id for m in members},
            f"{crew.name} 교대 균형",
            "요즘 돌봄이 한쪽으로 몰렸어요 — 다음 주엔 교대해보면 어때요?",
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
