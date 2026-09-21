"""채팅 (§28) — 번복의 조건으로 건 안전 경계를 코드로 강제한다."""

import pytest

from app.domain import chat_service as chat
from app.domain import crew_service as svc
from .helpers import join_via
from app.domain import errors


@pytest.fixture
def two_crews(db, verified_user):
    """서로 다른 크루 2개 + 각 멤버 (교차 접근 테스트용)."""
    a_owner = verified_user("A오너")
    crew_a = svc.create_crew(db, a_owner, "A크루")
    a_member = verified_user("A멤버")
    join_via(db, a_member, svc.create_invite(db, crew_a.id, a_owner).token, a_owner)

    b_owner = verified_user("B오너")
    crew_b = svc.create_crew(db, b_owner, "B크루")
    return crew_a, a_owner, a_member, crew_b, b_owner


# --- I6: 단체방은 크루 멤버만 ---


def test_crew_room_blocks_outsider(db, two_crews):
    crew_a, a_owner, _, _, b_owner = two_crews
    room = chat.crew_room(db, crew_a.id, a_owner)
    chat.send(db, room.id, a_owner, "우리끼리 이야기")
    with pytest.raises(errors.CrewIsolationViolation):
        chat.crew_room(db, crew_a.id, b_owner)
    with pytest.raises(errors.CrewIsolationViolation):
        chat.history(db, room.id, b_owner)
    with pytest.raises(errors.CrewIsolationViolation):
        chat.send(db, room.id, b_owner, "끼어들기")


def test_crew_room_is_single_per_crew(db, two_crews):
    crew_a, a_owner, a_member, _, _ = two_crews
    r1 = chat.crew_room(db, crew_a.id, a_owner)
    r2 = chat.crew_room(db, crew_a.id, a_member)
    assert r1.id == r2.id  # 멤버 누구가 열어도 같은 방


# --- §28 안전 경계: 1:1은 같은 모임 멤버끼리만 ---


def test_dm_blocked_between_strangers(db, two_crews):
    """낯선 사람이 아이 보호자에게 1:1로 접근하는 경로를 만들지 않는다."""
    _, a_owner, _, _, b_owner = two_crews
    with pytest.raises(errors.CrewIsolationViolation):
        chat.dm_room(db, b_owner, a_owner.id)


def test_dm_allowed_within_same_crew_and_reused(db, two_crews):
    _, a_owner, a_member, _, _ = two_crews
    r1 = chat.dm_room(db, a_owner, a_member.id)
    r2 = chat.dm_room(db, a_member, a_owner.id)  # 반대 방향도 같은 방
    assert r1.id == r2.id


def test_dm_is_private_to_the_two(db, verified_user):
    owner = verified_user("오너")
    crew = svc.create_crew(db, owner, "크루")
    m1 = verified_user("멤버1")
    m2 = verified_user("멤버2")
    for m in (m1, m2):
        join_via(db, m, svc.create_invite(db, crew.id, owner).token, owner)
    room = chat.dm_room(db, owner, m1.id)
    chat.send(db, room.id, owner, "둘만의 대화")
    with pytest.raises(errors.CrewIsolationViolation):
        chat.history(db, room.id, m2)  # 같은 크루라도 남의 DM은 못 본다


def test_cannot_dm_self(db, two_crews):
    _, a_owner, _, _, _ = two_crews
    with pytest.raises(ValueError):
        chat.dm_room(db, a_owner, a_owner.id)


# --- §28 차별점: 대상이 붙은 대화 ---


def test_context_room_is_shared_per_target(db, two_crews):
    """같은 건을 여는 사람은 같은 대화를 본다 — 카톡에서 흘러가는 맥락이 여기 남는다."""
    crew_a, a_owner, a_member, _, _ = two_crews
    r1 = chat.context_room(db, crew_a.id, a_owner, "session", "sess-1")
    r2 = chat.context_room(db, crew_a.id, a_member, "session", "sess-1")
    assert r1.id == r2.id and r1.context_kind == "session"
    other = chat.context_room(db, crew_a.id, a_owner, "session", "sess-2")
    assert other.id != r1.id


def test_context_room_rejects_unknown_kind(db, two_crews):
    crew_a, a_owner, _, _, _ = two_crews
    with pytest.raises(ValueError):
        chat.context_room(db, crew_a.id, a_owner, "무엇인가", "x")


def test_context_room_blocks_outsider(db, two_crews):
    crew_a, _, _, _, b_owner = two_crews
    with pytest.raises(errors.CrewIsolationViolation):
        chat.context_room(db, crew_a.id, b_owner, "session", "sess-1")


# --- 기록 무결성·읽음 ---


def test_delete_is_author_only_and_soft(db, two_crews):
    crew_a, a_owner, a_member, _, _ = two_crews
    room = chat.crew_room(db, crew_a.id, a_owner)
    msg = chat.send(db, room.id, a_owner, "지울 메시지")
    with pytest.raises(errors.HumanChoiceViolation):
        chat.delete_message(db, msg.id, a_member)
    chat.delete_message(db, msg.id, a_owner)
    assert msg.deleted_at is not None
    assert len(chat.history(db, room.id, a_owner)) == 1  # 행은 남는다 (표시만 '삭제됨')


def test_unread_count_and_mark_read(db, two_crews):
    crew_a, a_owner, a_member, _, _ = two_crews
    room = chat.crew_room(db, crew_a.id, a_owner)
    chat.crew_room(db, crew_a.id, a_member)  # 멤버 합류
    chat.send(db, room.id, a_owner, "안녕")
    chat.send(db, room.id, a_owner, "오늘 어때요")

    rooms = {r["room"].id: r for r in chat.my_rooms(db, a_member)}
    assert rooms[room.id]["unread"] == 2
    assert rooms[room.id]["last"].body == "오늘 어때요"

    chat.mark_read(db, room.id, a_member)
    rooms = {r["room"].id: r for r in chat.my_rooms(db, a_member)}
    assert rooms[room.id]["unread"] == 0


def test_history_has_upper_bound(db, two_crews):
    crew_a, a_owner, _, _, _ = two_crews
    room = chat.crew_room(db, crew_a.id, a_owner)
    for i in range(6):
        chat.send(db, room.id, a_owner, f"메시지{i}")
    assert len(chat.history(db, room.id, a_owner, limit=3)) == 3
    assert len(chat.history(db, room.id, a_owner, limit=999)) <= chat.MAX_PAGE


def test_empty_message_rejected(db, two_crews):
    crew_a, a_owner, _, _, _ = two_crews
    room = chat.crew_room(db, crew_a.id, a_owner)
    with pytest.raises(ValueError):
        chat.send(db, room.id, a_owner, "   ")


def test_chat_notifies_crew_members_who_never_opened_room(db, two_crews, monkeypatch):
    """단체방 알림은 '방에 들어와 본 적 없는' 크루 멤버에게도 가야 한다.

    (chat_members는 열어본 사람 목록일 뿐 — 그것만 보면 첫 메시지가 아무에게도 안 간다.)
    """
    from app import notifications
    from app.domain.models import Notification
    from sqlalchemy import select as sel

    monkeypatch.setattr("app.infra.push.send", lambda msgs: [{"status": "ok"} for _ in msgs])
    crew_a, a_owner, a_member, _, _ = two_crews
    room = chat.crew_room(db, crew_a.id, a_owner)  # a_member는 아직 연 적 없음
    msg = chat.send(db, room.id, a_owner, "첫 메시지")
    notifications.notify_chat(db, msg, a_owner)

    got = db.scalars(sel(Notification).where(Notification.user_id == a_member.id)).all()
    assert len(got) == 1 and "첫 메시지" in got[0].body
    assert db.scalars(sel(Notification).where(Notification.user_id == a_owner.id)).all() == []


def test_dm_notification_stays_between_the_two(db, verified_user, monkeypatch):
    from app import notifications
    from app.domain.models import Notification
    from sqlalchemy import select as sel

    monkeypatch.setattr("app.infra.push.send", lambda msgs: [{"status": "ok"} for _ in msgs])
    owner = verified_user("오너")
    crew = svc.create_crew(db, owner, "크루")
    m1, m2 = verified_user("멤버1"), verified_user("멤버2")
    for m in (m1, m2):
        join_via(db, m, svc.create_invite(db, crew.id, owner).token, owner)
    room = chat.dm_room(db, owner, m1.id)
    msg = chat.send(db, room.id, owner, "둘만의 메시지")
    notifications.notify_chat(db, msg, owner)

    assert len(db.scalars(sel(Notification).where(Notification.user_id == m1.id)).all()) == 1
    assert db.scalars(sel(Notification).where(Notification.user_id == m2.id)).all() == []  # 제3자에겐 안 감
