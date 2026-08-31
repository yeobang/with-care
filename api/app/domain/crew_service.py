"""크루 서비스 (P1). 불변식 I1·I2·I6·I7의 유일한 강제 지점.

여기의 가드를 우회하는 쓰기 경로를 만들지 않는다 (라우터는 반드시 이 계층을 거친다).
"""

from datetime import timedelta, timezone

from sqlalchemy import select
from sqlalchemy.orm import Session as DbSession

from app.domain import errors
from app.domain.models import (
    Charter,
    Child,
    Consent,
    Crew,
    CrewMember,
    CrewStatus,
    Invite,
    MemberRole,
    User,
    _now,
)

# 가정(요구사항에 없는 기본값): 초대장은 7일 후 만료 — 카톡방에 방치된 링크가 영구 관문이 되지 않게
INVITE_TTL = timedelta(days=7)


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


def create_invite(
    db: DbSession, crew_id: str, inviter: User, role: MemberRole = MemberRole.PARENT
) -> Invite:
    _require_parent(db, crew_id, inviter.id)  # 초대는 부모 멤버만 (§25-2)
    invite = Invite(crew_id=crew_id, inviter_id=inviter.id, role=role)
    db.add(invite)
    db.flush()
    return invite


def join_crew(db: DbSession, user: User, invite_token: str) -> CrewMember:
    """I1 관문의 P1 절반: 본인인증 + 유효한 초대 없이는 멤버가 될 수 없다.

    (인계 자체는 세션 계층(P2)에서 멤버십을 다시 검증한다.)
    """
    _require_verified(user)
    invite = db.get(Invite, invite_token)
    if invite is None or invite.used_by is not None or invite_expired(invite):
        raise errors.HandoffGateViolation("유효한 초대 없이는 크루에 합류할 수 없다 (I1)")
    already = db.scalar(
        select(CrewMember).where(
            CrewMember.crew_id == invite.crew_id, CrewMember.user_id == user.id
        )
    )
    if already is not None:
        raise ValueError("이미 이 크루의 멤버다")  # 초대장은 소모하지 않는다
    invite.used_by = user.id
    member = CrewMember(crew_id=invite.crew_id, user_id=user.id, role=invite.role)
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
    # 재제출 = 기존 행 갱신 — 아이 프로필 변경 후 재동의(§19-5)가 이 경로를 쓴다
    consent = db.scalar(
        select(Consent).where(Consent.crew_id == crew_id, Consent.user_id == user.id)
    )
    if consent is None:
        consent = Consent(crew_id=crew_id, user_id=user.id)
        db.add(consent)
    consent.liability_ack = liability_ack
    consent.photo_consent = photo_consent
    consent.guardian_consent = guardian_consent
    consent.consented_at = _now()
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


def invite_expired(invite: Invite) -> bool:
    created = invite.created_at
    if created.tzinfo is None:  # SQLite 등은 tz를 벗겨 저장한다
        created = created.replace(tzinfo=timezone.utc)
    return _now() - created > INVITE_TTL


def update_child(db: DbSession, user: User, child_id: str, **updates) -> Child:
    """아이 프로필 수정 — 보호자 본인만.

    §19-5/I2: 아이 정보(알레르기·투약 등)가 바뀌면 그 보호자의 포괄 합의를 무효화한다.
    재동의(submit_consent 재제출) 전에는 보드 참여가 막힌다 (_require_consent).
    """
    child = db.get(Child, child_id)
    if child is None or child.guardian_id != user.id:
        raise ValueError("존재하지 않는 아이")  # 남의 아이는 존재 여부도 알리지 않는다 (I6)
    for key, value in updates.items():
        if key in ("id", "guardian_id") or not hasattr(child, key):
            raise ValueError(f"수정할 수 없는 항목: {key}")
        setattr(child, key, value)
    for m in db.scalars(select(CrewMember).where(CrewMember.user_id == user.id)).all():
        consent = db.scalar(
            select(Consent).where(Consent.crew_id == m.crew_id, Consent.user_id == user.id)
        )
        if consent is not None:
            consent.consented_at = None  # 재동의 전까지 is_complete=False
    db.flush()
    return child


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


def _require_parent(db: DbSession, crew_id: str, user_id: str) -> CrewMember:
    """§25-2: 장부·보드 쓰기·초대·규약은 부모 멤버 전용 — 시터의 접근 경계 (I6 세분화)."""
    member = _require_member(db, crew_id, user_id)
    if member.role != MemberRole.PARENT:
        raise errors.CrewIsolationViolation("부모 멤버 전용 기능이다 (§25-2)")
    return member
