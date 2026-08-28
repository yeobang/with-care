"""크루 서비스 (P1). 불변식 I1·I2·I6·I7의 유일한 강제 지점.

여기의 가드를 우회하는 쓰기 경로를 만들지 않는다 (라우터는 반드시 이 계층을 거친다).
"""

from sqlalchemy import select
from sqlalchemy.orm import Session as DbSession

from app.domain import errors
from app.domain.models import (
    Charter,
    Consent,
    Crew,
    CrewMember,
    CrewStatus,
    Invite,
    User,
)


def create_crew(db: DbSession, owner: User, name: str) -> Crew:
    """크루 생성. 규약은 기본값으로 즉시 동반 생성된다 (백지 협상 금지) — 단, 미확정(DRAFT)."""
    _require_verified(owner)
    crew = Crew(name=name)
    db.add(crew)
    db.flush()
    db.add(Charter(crew_id=crew.id))  # 기본값 제시
    db.add(CrewMember(crew_id=crew.id, user_id=owner.id, is_owner=True))
    db.flush()
    return crew


def create_invite(db: DbSession, crew_id: str, inviter: User) -> Invite:
    _require_member(db, crew_id, inviter.id)
    invite = Invite(crew_id=crew_id, inviter_id=inviter.id)
    db.add(invite)
    db.flush()
    return invite


def join_crew(db: DbSession, user: User, invite_token: str) -> CrewMember:
    """I1 관문의 P1 절반: 본인인증 + 유효한 초대 없이는 멤버가 될 수 없다.

    (인계 자체는 세션 계층(P2)에서 멤버십을 다시 검증한다.)
    """
    _require_verified(user)
    invite = db.get(Invite, invite_token)
    if invite is None or invite.used_by is not None:
        raise errors.HandoffGateViolation("유효한 초대 없이는 크루에 합류할 수 없다 (I1)")
    invite.used_by = user.id
    member = CrewMember(crew_id=invite.crew_id, user_id=user.id)
    db.add(member)
    db.flush()
    return member


def submit_consent(
    db: DbSession,
    crew_id: str,
    user: User,
    *,
    liability_ack: bool,
    photo_consent: bool,
    guardian_consent: bool,
) -> Consent:
    from app.domain.models import _now

    _require_member(db, crew_id, user.id)
    if not (liability_ack and photo_consent and guardian_consent):
        raise errors.ConsentMissing("포괄 합의는 부분 동의로 성립하지 않는다 (I2)")
    consent = Consent(
        crew_id=crew_id,
        user_id=user.id,
        liability_ack=liability_ack,
        photo_consent=photo_consent,
        guardian_consent=guardian_consent,
        consented_at=_now(),
    )
    db.add(consent)
    db.flush()
    return consent


def confirm_charter(db: DbSession, crew_id: str, user: User, **updates) -> Charter:
    """규약 확정. 크루는 기본값을 조정한 뒤 확정한다."""
    from app.domain.models import _now

    _require_member(db, crew_id, user.id)
    charter = db.scalar(select(Charter).where(Charter.crew_id == crew_id))
    assert charter is not None
    for key, value in updates.items():
        if not hasattr(charter, key):
            raise ValueError(f"규약에 없는 항목: {key}")
        setattr(charter, key, value)
    charter.confirmed_at = _now()
    db.flush()
    return charter


def activate_crew(db: DbSession, crew_id: str, user: User) -> Crew:
    """크루 활성화 관문 — I7(규약) + I2(전원 합의)를 여기서 강제한다."""
    _require_member(db, crew_id, user.id)
    crew = db.get(Crew, crew_id)
    assert crew is not None
    charter = db.scalar(select(Charter).where(Charter.crew_id == crew_id))
    if charter is None or not charter.is_complete:
        raise errors.CharterIncomplete("규약 없는 크루는 활성화되지 않는다 (I7)")
    members = db.scalars(select(CrewMember).where(CrewMember.crew_id == crew_id)).all()
    for m in members:
        consent = db.scalar(
            select(Consent).where(Consent.crew_id == crew_id, Consent.user_id == m.user_id)
        )
        if consent is None or not consent.is_complete:
            raise errors.ConsentMissing(f"멤버 전원의 포괄 합의 전에는 활성화할 수 없다 (I2): user={m.user_id}")
    crew.status = CrewStatus.ACTIVE
    db.flush()
    return crew


def get_crew_view(db: DbSession, crew_id: str, requester: User) -> dict:
    """크루 데이터 조회 — I6: 멤버가 아니면 어떤 필드도 반환하지 않는다."""
    _require_member(db, crew_id, requester.id)
    crew = db.get(Crew, crew_id)
    assert crew is not None
    charter = db.scalar(select(Charter).where(Charter.crew_id == crew_id))
    members = db.scalars(select(CrewMember).where(CrewMember.crew_id == crew_id)).all()
    return {
        "id": crew.id,
        "name": crew.name,
        "status": str(crew.status),
        "charter_complete": bool(charter and charter.is_complete),
        "member_count": len(members),
    }


# --- 내부 가드 ---

def _require_verified(user: User) -> None:
    if not user.identity_verified:
        raise errors.HandoffGateViolation("본인인증 없이는 크루 활동 불가 (I1)")


def _require_member(db: DbSession, crew_id: str, user_id: str) -> CrewMember:
    member = db.scalar(
        select(CrewMember).where(CrewMember.crew_id == crew_id, CrewMember.user_id == user_id)
    )
    if member is None:
        raise errors.CrewIsolationViolation("크루 데이터는 크루 멤버만 접근할 수 있다 (I6)")
    return member
