"""도메인 모델 (P1): 사용자·크루·초대·규약·아이·포괄 합의.

I8(연령 분기 금지): 이 모듈과 서비스 계층은 아이의 나이로 분기하지 않는다.
허용된 예외 두 곳뿐 — 0~2세 보류 플래그(가드레일 §2), I3의 영유아 카운트(P2).
"""

import enum
import uuid
from datetime import datetime, timezone

from sqlalchemy import ForeignKey, String, UniqueConstraint
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


def _id() -> str:
    return str(uuid.uuid4())


def _now() -> datetime:
    return datetime.now(timezone.utc)


class Base(DeclarativeBase):
    pass


class CrewStatus(enum.StrEnum):
    DRAFT = "draft"      # 규약 미확정 — 세션 불가 (I7)
    ACTIVE = "active"


class SettlementMode(enum.StrEnum):
    """§2 긴장②: 정산 모드는 크루가 고른다."""

    NONE = "none"          # 기록만
    ROTATION = "rotation"  # 교대 균형 알림
    CREDIT = "credit"      # 크레딧 장부 (+선택적 정산 밸브)


class User(Base):
    __tablename__ = "users"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_id)
    name: Mapped[str] = mapped_column(String(50))
    # MVP: Supabase Auth 계정 + 플래그. 본인인증(PASS) 연동은 P6 이후 (docs/03-dev-plan.md)
    identity_verified: Mapped[bool] = mapped_column(default=False)
    created_at: Mapped[datetime] = mapped_column(default=_now)


class Crew(Base):
    __tablename__ = "crews"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_id)
    name: Mapped[str] = mapped_column(String(50))
    status: Mapped[CrewStatus] = mapped_column(String(10), default=CrewStatus.DRAFT)
    created_at: Mapped[datetime] = mapped_column(default=_now)

    charter: Mapped["Charter"] = relationship(back_populates="crew", uselist=False)
    members: Mapped[list["CrewMember"]] = relationship(back_populates="crew")


class CrewMember(Base):
    __tablename__ = "crew_members"
    __table_args__ = (UniqueConstraint("crew_id", "user_id"),)

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_id)
    crew_id: Mapped[str] = mapped_column(ForeignKey("crews.id"))
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id"))
    is_owner: Mapped[bool] = mapped_column(default=False)
    joined_at: Mapped[datetime] = mapped_column(default=_now)

    crew: Mapped[Crew] = relationship(back_populates="members")


class Invite(Base):
    __tablename__ = "invites"

    token: Mapped[str] = mapped_column(String(36), primary_key=True, default=_id)
    crew_id: Mapped[str] = mapped_column(ForeignKey("crews.id"))
    inviter_id: Mapped[str] = mapped_column(ForeignKey("users.id"))
    used_by: Mapped[str | None] = mapped_column(ForeignKey("users.id"), default=None)
    created_at: Mapped[datetime] = mapped_column(default=_now)


class Charter(Base):
    """크루 규약. 앱이 기본값을 제시하고 크루는 조정만 한다 (백지 협상 금지, I7)."""

    __tablename__ = "charters"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_id)
    crew_id: Mapped[str] = mapped_column(ForeignKey("crews.id"), unique=True)
    settlement_mode: Mapped[SettlementMode] = mapped_column(String(10), default=SettlementMode.ROTATION)
    credit_price_krw: Mapped[int] = mapped_column(default=8000)   # 1크레딧(1시간) 원화 가치
    host_fee_krw: Mapped[int] = mapped_column(default=5000)       # 호스트 사례 (회당)
    no_show_fine_krw: Mapped[int] = mapped_column(default=10000)  # 노쇼 벌금
    care_rules: Mapped[str] = mapped_column(String(2000), default="")   # 스크린타임·간식·훈육 등
    handoff_method: Mapped[str] = mapped_column(String(500), default="")  # 인계 방식 (연령대별 결은 여기로)
    confirmed_at: Mapped[datetime | None] = mapped_column(default=None)

    crew: Mapped[Crew] = relationship(back_populates="charter")

    @property
    def is_complete(self) -> bool:
        return self.confirmed_at is not None


class Child(Base):
    __tablename__ = "children"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_id)
    guardian_id: Mapped[str] = mapped_column(ForeignKey("users.id"))
    name: Mapped[str] = mapped_column(String(50))
    birth_year_month: Mapped[str] = mapped_column(String(7))  # "2021-03" — 최소 수집 원칙
    traits: Mapped[str] = mapped_column(String(1000), default="")
    allergies: Mapped[str] = mapped_column(String(1000), default="")
    medication: Mapped[str] = mapped_column(String(1000), default="")
    emergency_contact: Mapped[str] = mapped_column(String(100))


class Consent(Base):
    """포괄 합의 (I2): 가입 시 1회, 아이 프로필 변경 시 재확인 (§19-5)."""

    __tablename__ = "consents"
    __table_args__ = (UniqueConstraint("crew_id", "user_id"),)

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_id)
    crew_id: Mapped[str] = mapped_column(ForeignKey("crews.id"))
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id"))
    liability_ack: Mapped[bool] = mapped_column(default=False)      # 책임 범위 확인
    photo_consent: Mapped[bool] = mapped_column(default=False)      # 세션 사진 (크루 내 한정)
    guardian_consent: Mapped[bool] = mapped_column(default=False)   # 만14세 미만 법정대리인 동의
    consented_at: Mapped[datetime | None] = mapped_column(default=None)

    @property
    def is_complete(self) -> bool:
        return (
            self.consented_at is not None
            and self.liability_ack
            and self.photo_consent
            and self.guardian_consent
        )


# --- P2: 주간 보드 ---


class SlotKind(enum.StrEnum):
    AVAILABLE = "available"  # 이 시간에 내가 돌봄 가능
    NEED = "need"            # 이 시간에 우리 아이 돌봄 필요


class BoardSlot(Base):
    """주간 조율 보드의 한 칸: 각 부모가 탭으로 입력 (§11 — 채팅이 아니라 구조화 입력)."""

    __tablename__ = "board_slots"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_id)
    crew_id: Mapped[str] = mapped_column(ForeignKey("crews.id"))
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id"))
    kind: Mapped[SlotKind] = mapped_column(String(10))
    date: Mapped[str] = mapped_column(String(10))       # "2026-09-01"
    start_hour: Mapped[int] = mapped_column()            # 0~23
    end_hour: Mapped[int] = mapped_column()
    child_id: Mapped[str | None] = mapped_column(ForeignKey("children.id"), default=None)  # NEED일 때
    created_at: Mapped[datetime] = mapped_column(default=_now)


class ProposalStatus(enum.StrEnum):
    PROPOSED = "proposed"    # 앱이 후보로 나열함 — 아직 아무 효력 없음 (I4)
    CONFIRMED = "confirmed"  # 관련 가정 전원이 확정 탭
    DECLINED = "declined"


class Assignment(Base):
    """배정 후보. 앱은 후보를 '나열'만 하고, 효력은 전원 확정 탭에서만 생긴다 (I4)."""

    __tablename__ = "assignments"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_id)
    crew_id: Mapped[str] = mapped_column(ForeignKey("crews.id"))
    caregiver_id: Mapped[str] = mapped_column(ForeignKey("users.id"))
    date: Mapped[str] = mapped_column(String(10))
    start_hour: Mapped[int] = mapped_column()
    end_hour: Mapped[int] = mapped_column()
    status: Mapped[ProposalStatus] = mapped_column(String(10), default=ProposalStatus.PROPOSED)
    created_at: Mapped[datetime] = mapped_column(default=_now)

    children: Mapped[list["AssignmentChild"]] = relationship(back_populates="assignment")


class AssignmentChild(Base):
    __tablename__ = "assignment_children"
    __table_args__ = (UniqueConstraint("assignment_id", "child_id"),)

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_id)
    assignment_id: Mapped[str] = mapped_column(ForeignKey("assignments.id"))
    child_id: Mapped[str] = mapped_column(ForeignKey("children.id"))
    guardian_confirmed: Mapped[bool] = mapped_column(default=False)  # I4: 가정별 명시적 확정 탭

    assignment: Mapped[Assignment] = relationship(back_populates="children")


class CareSession(Base):
    """확정된 돌봄 세션. Assignment 전원 확정 시에만 생성된다."""

    __tablename__ = "care_sessions"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_id)
    crew_id: Mapped[str] = mapped_column(ForeignKey("crews.id"))
    assignment_id: Mapped[str] = mapped_column(ForeignKey("assignments.id"), unique=True)
    caregiver_id: Mapped[str] = mapped_column(ForeignKey("users.id"))
    date: Mapped[str] = mapped_column(String(10))
    start_hour: Mapped[int] = mapped_column()
    end_hour: Mapped[int] = mapped_column()
    handoff_started_at: Mapped[datetime | None] = mapped_column(default=None)
    handoff_ended_at: Mapped[datetime | None] = mapped_column(default=None)
    created_at: Mapped[datetime] = mapped_column(default=_now)
