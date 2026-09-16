"""채팅 (§28) — 카톡 복제가 아니라 '대상이 붙은 대화'.

안전 경계 (§28):
- 단체방은 크루 멤버만 (I6)
- 1:1은 **같은 모임 멤버끼리만** — 낯선 성인이 아이 보호자에게 1:1로 접근하는 경로를 만들지 않는다
- 텍스트 전용 — 사진은 세션에만 붙는다 (I6·§19-7 우회 반출 차단)
- 삭제는 무효화 (분쟁 시 기록 무결성, §4-A)
"""

from sqlalchemy import func, select
from sqlalchemy.orm import Session as DbSession

from app.domain import errors
from app.domain.crew_service import _require_member
from app.domain.models import (
    ChatMember,
    ChatMessage,
    ChatRoom,
    Crew,
    CrewMember,
    RoomKind,
    User,
    _now,
)

MAX_PAGE = 100


def crew_room(db: DbSession, crew_id: str, user: User) -> ChatRoom:
    """모임 단체방 — 없으면 만들고, 멤버면 자동 합류시킨다."""
    _require_member(db, crew_id, user.id)  # I6
    room = db.scalar(
        select(ChatRoom).where(
            ChatRoom.crew_id == crew_id, ChatRoom.kind == RoomKind.CREW, ChatRoom.context_id.is_(None)
        )
    )
    if room is None:
        room = ChatRoom(kind=RoomKind.CREW, crew_id=crew_id)
        db.add(room)
        db.flush()
    _ensure_member(db, room.id, user.id)
    return room


def context_room(db: DbSession, crew_id: str, user: User, kind: str, target_id: str) -> ChatRoom:
    """특정 건(세션·후보·정산)에 붙는 대화방 — §28의 차별점.

    그 건을 여는 사람은 같은 대화를 본다. 카톡에서 흘러가버리는 맥락이 여기 남는다.
    """
    _require_member(db, crew_id, user.id)
    if kind not in ("session", "assignment", "settlement"):
        raise ValueError("알 수 없는 대상이에요")
    room = db.scalar(
        select(ChatRoom).where(ChatRoom.context_kind == kind, ChatRoom.context_id == target_id)
    )
    if room is None:
        room = ChatRoom(kind=RoomKind.CREW, crew_id=crew_id, context_kind=kind, context_id=target_id)
        db.add(room)
        db.flush()
    _ensure_member(db, room.id, user.id)
    return room


def dm_room(db: DbSession, user: User, other_id: str) -> ChatRoom:
    """1:1 — 같은 모임에 함께 속한 사람과만 (§28 안전 경계)."""
    if other_id == user.id:
        raise ValueError("자기 자신과는 대화할 수 없어요")
    shared = db.scalar(
        select(CrewMember.crew_id)
        .where(CrewMember.user_id == user.id)
        .where(
            CrewMember.crew_id.in_(
                select(CrewMember.crew_id).where(CrewMember.user_id == other_id)
            )
        )
        .limit(1)
    )
    if shared is None:
        raise errors.CrewIsolationViolation("같은 모임의 이웃과만 1:1 대화를 할 수 있어요")

    # 두 사람만 있는 기존 DM 찾기
    for room in db.scalars(
        select(ChatRoom).where(ChatRoom.kind == RoomKind.DM, ChatRoom.crew_id == shared)
    ).all():
        ids = {m.user_id for m in db.scalars(select(ChatMember).where(ChatMember.room_id == room.id)).all()}
        if ids == {user.id, other_id}:
            return room

    room = ChatRoom(kind=RoomKind.DM, crew_id=shared)
    db.add(room)
    db.flush()
    _ensure_member(db, room.id, user.id)
    _ensure_member(db, room.id, other_id)
    return room


def send(db: DbSession, room_id: str, sender: User, body: str) -> ChatMessage:
    _require_room_member(db, room_id, sender.id)
    if not body.strip():
        raise ValueError("내용을 입력해주세요")
    msg = ChatMessage(room_id=room_id, sender_id=sender.id, body=body.strip()[:2000])
    db.add(msg)
    db.flush()
    return msg


def history(db: DbSession, room_id: str, user: User, limit: int = 50) -> list[ChatMessage]:
    _require_room_member(db, room_id, user.id)
    rows = db.scalars(
        select(ChatMessage)
        .where(ChatMessage.room_id == room_id)
        .order_by(ChatMessage.created_at.desc())
        .limit(min(max(limit, 1), MAX_PAGE))
    ).all()
    return list(reversed(rows))


def mark_read(db: DbSession, room_id: str, user: User) -> None:
    m = _require_room_member(db, room_id, user.id)
    m.last_read_at = _now()
    db.flush()


def delete_message(db: DbSession, message_id: str, user: User) -> ChatMessage:
    """보낸 사람만. 무효화 — 행은 남고 표시만 '삭제된 메시지' (§4-A)."""
    msg = db.get(ChatMessage, message_id)
    if msg is None:
        raise ValueError("없는 메시지예요")
    if msg.sender_id != user.id:
        raise errors.HumanChoiceViolation("자기 메시지만 지울 수 있어요")
    if msg.deleted_at is None:
        msg.deleted_at = _now()
        db.flush()
    return msg


def my_rooms(db: DbSession, user: User) -> list[dict]:
    """내 대화 목록 — 마지막 메시지·안 읽은 수까지 한 번에 (N+1 회피)."""
    memberships = db.scalars(select(ChatMember).where(ChatMember.user_id == user.id)).all()
    out: list[dict] = []
    for m in memberships:
        room = db.get(ChatRoom, m.room_id)
        if room is None:
            continue
        last = db.scalar(
            select(ChatMessage)
            .where(ChatMessage.room_id == room.id)
            .order_by(ChatMessage.created_at.desc())
            .limit(1)
        )
        unread_q = select(func.count()).select_from(ChatMessage).where(
            ChatMessage.room_id == room.id, ChatMessage.sender_id != user.id
        )
        if m.last_read_at is not None:
            unread_q = unread_q.where(ChatMessage.created_at > m.last_read_at)
        others = [
            db.get(User, x.user_id)
            for x in db.scalars(
                select(ChatMember).where(ChatMember.room_id == room.id, ChatMember.user_id != user.id)
            ).all()
        ]
        crew = db.get(Crew, room.crew_id)
        out.append(
            {
                "room": room,
                "crew_name": crew.name if crew else "",
                "others": [u.name for u in others if u],
                "last": last,
                "unread": int(db.scalar(unread_q) or 0),
            }
        )
    out.sort(key=lambda r: (r["last"].created_at if r["last"] else r["room"].created_at), reverse=True)
    return out


# --- 내부 가드 ---


def _ensure_member(db: DbSession, room_id: str, user_id: str) -> ChatMember:
    m = db.scalar(select(ChatMember).where(ChatMember.room_id == room_id, ChatMember.user_id == user_id))
    if m is None:
        m = ChatMember(room_id=room_id, user_id=user_id)
        db.add(m)
        db.flush()
    return m


def _require_room_member(db: DbSession, room_id: str, user_id: str) -> ChatMember:
    room = db.get(ChatRoom, room_id)
    if room is None:
        raise ValueError("없는 대화방이에요")
    if room.kind == RoomKind.CREW:
        # 단체방: 크루 멤버면 누구나 (나갔다 들어와도 되게) — 멤버십이 진실
        _require_member(db, room.crew_id, user_id)  # I6
        return _ensure_member(db, room_id, user_id)
    m = db.scalar(select(ChatMember).where(ChatMember.room_id == room_id, ChatMember.user_id == user_id))
    if m is None:
        raise errors.CrewIsolationViolation("이 대화방에 참여하고 있지 않아요")
    return m
