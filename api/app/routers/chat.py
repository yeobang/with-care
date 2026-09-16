"""채팅 API (§28). 실시간은 폴링 기반 — 실패해도 본 흐름을 막지 않는다."""

from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app import notifications
from app.deps import get_current_user, get_db
from app.domain import chat_service as chat
from app.domain.models import ChatMessage, ChatRoom, User

router = APIRouter(tags=["chat"])


class SendIn(BaseModel):
    body: str = Field(min_length=1, max_length=2000)


@router.get("/chat/rooms")
def my_rooms(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    return [
        {
            "id": r["room"].id,
            "kind": str(r["room"].kind),
            "crew_id": r["room"].crew_id,
            "crew_name": r["crew_name"],
            "title": ", ".join(r["others"]) if r["others"] else r["crew_name"],
            "context_kind": r["room"].context_kind,
            "last_body": r["last"].body if r["last"] and r["last"].deleted_at is None else ("삭제된 메시지" if r["last"] else None),
            "last_at": r["last"].created_at.isoformat() if r["last"] else None,
            "unread": r["unread"],
        }
        for r in chat.my_rooms(db, user)
    ]


@router.post("/crews/{crew_id}/chat")
def open_crew_room(crew_id: str, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    return _room_out(db, chat.crew_room(db, crew_id, user), user)


@router.post("/crews/{crew_id}/chat/{kind}/{target_id}")
def open_context_room(
    crew_id: str, kind: str, target_id: str,
    user: User = Depends(get_current_user), db: Session = Depends(get_db),
):
    """세션·후보·정산 건에 붙는 대화방 (§28의 차별점)."""
    return _room_out(db, chat.context_room(db, crew_id, user, kind, target_id), user)


@router.post("/chat/dm/{other_id}")
def open_dm(other_id: str, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    return _room_out(db, chat.dm_room(db, user, other_id), user)


@router.get("/chat/rooms/{room_id}/messages")
def messages(room_id: str, limit: int = 50, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    rows = chat.history(db, room_id, user, limit)
    chat.mark_read(db, room_id, user)
    return [_msg_out(db, m, user) for m in rows]


@router.post("/chat/rooms/{room_id}/messages")
def send(room_id: str, body: SendIn, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    msg = chat.send(db, room_id, user, body.body)
    notifications.notify_chat(db, msg, user)  # best-effort
    return _msg_out(db, msg, user)


@router.delete("/chat/messages/{message_id}")
def delete_message(message_id: str, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    chat.delete_message(db, message_id, user)
    return {"ok": True}


def _room_out(db: Session, room: ChatRoom, me: User) -> dict:
    return {
        "id": room.id,
        "kind": str(room.kind),
        "crew_id": room.crew_id,
        "context_kind": room.context_kind,
        "context_id": room.context_id,
    }


def _msg_out(db: Session, m: ChatMessage, me: User) -> dict:
    sender = db.get(User, m.sender_id)
    return {
        "id": m.id,
        "body": "삭제된 메시지예요" if m.deleted_at else m.body,
        "deleted": m.deleted_at is not None,
        "sender": {"id": m.sender_id, "name": sender.name if sender else "알 수 없음", "is_me": m.sender_id == me.id},
        "created_at": m.created_at.isoformat(),
    }
