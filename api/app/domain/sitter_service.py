"""시터 트랙 (P10): 공구 요청 → 분할 견적 → 가정별 확정 → 세션 (§25).

I4: 견적은 후보 나열일 뿐 — 전 가정의 명시적 확정 탭이 모여야만 세션이 성립한다.
결제 제외(§23): 금액은 계산·안내까지. 결제·이체 코드는 이 모듈에도 어디에도 없다.
I3: 세션 성립 직전 영유아 5인 가드 동일 적용. 상시성(§25-6)은 경고 — 차단 아님.
"""

from datetime import date as date_type
from datetime import datetime
from zoneinfo import ZoneInfo

from sqlalchemy import select
from sqlalchemy.orm import Session as DbSession

from app.domain import errors
from app.domain.board_service import (
    MAX_PRESCHOOLERS_PER_CAREGIVER,
    _is_preschooler,
    _require_active,
    _require_consent,
)
from app.domain.crew_service import _require_member, _require_parent
from app.domain.models import (
    CareSession,
    Child,
    MemberRole,
    ProposalStatus,
    SitterProfile,
    SitterQuote,
    SitterQuoteFamily,
    SitterRequest,
    SitterRequestChild,
    SitterRequestStatus,
    User,
)

KST = ZoneInfo("Asia/Seoul")
SURGE_MULTIPLIER_PCT = 150  # §17-A 긴급 할증: 당일 요청 1.5배
RECURRENCE_WEEKLY_THRESHOLD = 2  # §25-6 가정: 같은 크루·시터, 같은 ISO 주


def _today_kst() -> str:
    return datetime.now(KST).date().isoformat()


def upsert_profile(db: DbSession, user: User, *, hourly_krw: int, intro: str = "") -> SitterProfile:
    """시터 프로필 (이웃→시터 문). 승급 요건 검증(§17-B)은 후속 — 지금은 자기 선언."""
    if hourly_krw <= 0:
        raise ValueError("시급은 양수여야 한다")
    profile = db.scalar(select(SitterProfile).where(SitterProfile.user_id == user.id))
    if profile is None:
        profile = SitterProfile(user_id=user.id)
        db.add(profile)
    profile.hourly_krw = hourly_krw
    profile.intro = intro
    db.flush()
    return profile


def create_request(
    db: DbSession, crew_id: str, user: User, *, date: str, start_hour: int, end_hour: int,
    child_ids: list[str],
) -> SitterRequest:
    _require_parent(db, crew_id, user.id)
    _require_active(db, crew_id)
    _require_consent(db, crew_id, user.id)
    if not (0 <= start_hour < end_hour <= 24):
        raise ValueError("시간 범위가 올바르지 않다")
    if not child_ids:
        raise ValueError("아이가 최소 하나 지정되어야 한다")
    for cid in child_ids:
        child = db.get(Child, cid)
        if child is None or child.guardian_id != user.id:
            raise ValueError("자기 아이로만 공구에 참여할 수 있다")
    req = SitterRequest(
        crew_id=crew_id, created_by=user.id, date=date,
        start_hour=start_hour, end_hour=end_hour,
    )
    db.add(req)
    db.flush()
    for cid in set(child_ids):
        db.add(SitterRequestChild(request_id=req.id, child_id=cid))
    db.flush()
    return req


def join_request(db: DbSession, request_id: str, user: User, child_id: str) -> SitterRequest:
    """다른 가정의 공구 참여 — 자기 아이로만. 재참여 멱등."""
    req = db.get(SitterRequest, request_id)
    if req is None:
        raise ValueError("존재하지 않는 공구 요청")
    _require_parent(db, req.crew_id, user.id)
    _require_consent(db, req.crew_id, user.id)
    if req.status != SitterRequestStatus.OPEN:
        raise ValueError("이미 매칭되었거나 종료된 요청")
    child = db.get(Child, child_id)
    if child is None or child.guardian_id != user.id:
        raise ValueError("자기 아이로만 공구에 참여할 수 있다")
    existing = db.scalar(
        select(SitterRequestChild).where(
            SitterRequestChild.request_id == request_id,
            SitterRequestChild.child_id == child_id,
        )
    )
    if existing is None:
        db.add(SitterRequestChild(request_id=request_id, child_id=child_id))
        db.flush()
    return req


def _request_families(db: DbSession, request_id: str) -> set[str]:
    rows = db.scalars(
        select(SitterRequestChild).where(SitterRequestChild.request_id == request_id)
    ).all()
    return {db.get(Child, r.child_id).guardian_id for r in rows}


def submit_quote(db: DbSession, request_id: str, sitter: User) -> tuple[SitterQuote, bool]:
    """시터의 견적 제출 → (견적, 신규 여부). 같은 요청 재제출은 멱등.

    견적 = 시급 스냅샷 × 시간 × (당일이면 1.5) / 분할 = 총액 ÷ 참여 가정 (절사, §25-3).
    """
    req = db.get(SitterRequest, request_id)
    if req is None:
        raise ValueError("존재하지 않는 공구 요청")
    member = _require_member(db, req.crew_id, sitter.id)
    if member.role != MemberRole.SITTER:
        raise errors.CrewIsolationViolation("시터 역할 멤버만 견적을 제출할 수 있다 (§25-1)")
    _require_consent(db, req.crew_id, sitter.id)  # §25-1: 시터도 포괄 합의 후 활동
    if req.status != SitterRequestStatus.OPEN:
        raise ValueError("이미 매칭되었거나 종료된 요청")
    profile = db.scalar(select(SitterProfile).where(SitterProfile.user_id == sitter.id))
    if profile is None:
        raise ValueError("시터 프로필(시급)을 먼저 등록해야 한다")
    existing = db.scalar(
        select(SitterQuote).where(
            SitterQuote.request_id == request_id, SitterQuote.sitter_user_id == sitter.id
        )
    )
    if existing is not None:
        return existing, False

    hours = req.end_hour - req.start_hour
    surge = req.date == _today_kst()
    total = hours * profile.hourly_krw
    if surge:
        total = total * SURGE_MULTIPLIER_PCT // 100
    families = _request_families(db, req.id)
    quote = SitterQuote(
        request_id=request_id, sitter_user_id=sitter.id,
        hourly_krw=profile.hourly_krw, surge=surge,
        total_krw=total, per_family_krw=total // len(families),
    )
    db.add(quote)
    db.flush()
    for g in families:
        db.add(SitterQuoteFamily(quote_id=quote.id, guardian_id=g))
    db.flush()
    return quote, True


def confirm_quote(db: DbSession, quote_id: str, guardian: User) -> CareSession | None:
    """가정별 확정 탭 (I4). 전 가정 확정 시에만 세션 성립 — 성립 직전 I3 가드."""
    quote = db.get(SitterQuote, quote_id)
    if quote is None:
        raise ValueError("존재하지 않는 견적")
    req = db.get(SitterRequest, quote.request_id)
    _require_parent(db, req.crew_id, guardian.id)
    _require_consent(db, req.crew_id, guardian.id)
    if quote.status == ProposalStatus.CONFIRMED:
        return db.scalar(select(CareSession).where(CareSession.sitter_quote_id == quote.id))
    if quote.status == ProposalStatus.DECLINED:
        raise ValueError("거절된 견적은 확정할 수 없다")
    if req.status != SitterRequestStatus.OPEN:
        raise ValueError("이미 매칭되었거나 종료된 요청")

    fams = db.scalars(
        select(SitterQuoteFamily).where(SitterQuoteFamily.quote_id == quote_id)
    ).all()
    mine = [f for f in fams if f.guardian_id == guardian.id]
    if not mine:
        raise errors.HumanChoiceViolation("자기 가정의 몫만 확정할 수 있다 (I4)")
    for f in mine:
        f.confirmed = True
    db.flush()
    if not all(f.confirmed for f in fams):
        return None  # 아직 전원 확정 아님 — 효력 없음 (I4)

    _guard_i3(db, req, quote.sitter_user_id)
    quote.status = ProposalStatus.CONFIRMED
    req.status = SitterRequestStatus.MATCHED
    session = CareSession(
        crew_id=req.crew_id, sitter_quote_id=quote.id, caregiver_id=quote.sitter_user_id,
        date=req.date, start_hour=req.start_hour, end_hour=req.end_hour,
    )
    db.add(session)
    db.flush()
    return session


def decline_quote(db: DbSession, quote_id: str, user: User) -> SitterQuote:
    """견적 거절 — 참여 가정 또는 시터 본인만 (I4). 재탭 멱등."""
    quote = db.get(SitterQuote, quote_id)
    if quote is None:
        raise ValueError("존재하지 않는 견적")
    req = db.get(SitterRequest, quote.request_id)
    _require_member(db, req.crew_id, user.id)
    if quote.status == ProposalStatus.DECLINED:
        return quote
    if quote.status == ProposalStatus.CONFIRMED:
        raise ValueError("이미 확정된 견적은 거절할 수 없다 (세션 취소로)")
    fams = db.scalars(
        select(SitterQuoteFamily).where(SitterQuoteFamily.quote_id == quote_id)
    ).all()
    if user.id != quote.sitter_user_id and not any(f.guardian_id == user.id for f in fams):
        raise errors.HumanChoiceViolation("참여 가정 또는 시터 본인만 거절할 수 있다 (I4)")
    quote.status = ProposalStatus.DECLINED
    db.flush()
    return quote


def _guard_i3(db: DbSession, req: SitterRequest, sitter_user_id: str) -> None:
    """I3: 돌봄자(시터) 1인 + 타인 영유아 5인 이상 세션 금지 — 이웃 트랙과 동일 가드."""
    others_preschoolers = 0
    rows = db.scalars(
        select(SitterRequestChild).where(SitterRequestChild.request_id == req.id)
    ).all()
    for r in rows:
        child = db.get(Child, r.child_id)
        if child.guardian_id == sitter_user_id:
            continue
        if _is_preschooler(child, req.date):  # I8-allow: I3 영유아 카운트
            others_preschoolers += 1
    if others_preschoolers > MAX_PRESCHOOLERS_PER_CAREGIVER:
        raise errors.UnlicensedCarePattern(
            f"돌봄자 1인이 타인 영유아 {others_preschoolers}명을 볼 수 없다 (I3: 상한 {MAX_PRESCHOOLERS_PER_CAREGIVER})"
        )


def recurrence_warning(db: DbSession, session: CareSession) -> bool:
    """§25-6: 같은 크루·같은 시터의 세션이 같은 ISO 주 임계(2회) 이상이면 True (경고 전용)."""
    rows = db.scalars(
        select(CareSession).where(
            CareSession.crew_id == session.crew_id,
            CareSession.caregiver_id == session.caregiver_id,
            CareSession.sitter_quote_id.is_not(None),
            CareSession.canceled_at.is_(None),
        )
    ).all()
    week = date_type.fromisoformat(session.date).isocalendar()[:2]
    n = sum(1 for s in rows if date_type.fromisoformat(s.date).isocalendar()[:2] == week)
    return n >= RECURRENCE_WEEKLY_THRESHOLD


def reopen_after_cancel(db: DbSession, session: CareSession) -> None:
    """§25-5: 시터 세션 취소 → 죽은 견적 처리 + 공구 요청 재개 (폴백 재가동)."""
    if session.sitter_quote_id is None:
        return
    quote = db.get(SitterQuote, session.sitter_quote_id)
    req = db.get(SitterRequest, quote.request_id)
    quote.status = ProposalStatus.DECLINED
    req.status = SitterRequestStatus.OPEN
    db.flush()
