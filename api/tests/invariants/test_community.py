"""커뮤니티 (§27) — I6 경계와 공개 레이어 조건을 코드로 강제한다.

§27이 번복의 조건으로 건 것들이 실제로 지켜지는지가 이 파일의 전부다.
"""

import pytest

from app.domain import community_service as cs
from app.domain import crew_service as svc
from .helpers import join_via
from app.domain import errors
from app.domain.models import PostCategory, PostScope, User


@pytest.fixture
def town_user(db, verified_user):
    def _make(name="이웃", town="1168053000", tname="역삼1동", verified=True):
        u = verified_user(name)
        u.identity_verified = verified
        u.town_code = town
        u.town_name = tname
        db.flush()
        return u

    return _make


@pytest.fixture
def crew_with_members(db, verified_user):
    owner = verified_user("오너")
    crew = svc.create_crew(db, owner, "이야기크루")
    member = verified_user("멤버")
    join_via(db, member, svc.create_invite(db, crew.id, owner).token, owner)
    return crew, owner, member


# --- I6: 모임 글은 모임 밖으로 나가지 않는다 ---


def test_crew_post_invisible_to_outsider(db, crew_with_members, town_user):
    crew, owner, _ = crew_with_members
    post = cs.create_post(db, owner, scope=PostScope.CREW, category=PostCategory.NOTICE,
                          title="이번 주 공지", body="토요일 모임해요", crew_id=crew.id)
    outsider = town_user("외부인")
    with pytest.raises(errors.CrewIsolationViolation):
        cs.get_post(db, post.id, outsider)
    with pytest.raises(errors.CrewIsolationViolation):
        cs.crew_feed(db, crew.id, outsider)


def test_outsider_cannot_write_to_crew(db, crew_with_members, town_user):
    crew, _, _ = crew_with_members
    outsider = town_user("외부인")
    with pytest.raises(errors.CrewIsolationViolation):
        cs.create_post(db, outsider, scope=PostScope.CREW, category=PostCategory.TIP,
                       title="끼어들기", body="본문", crew_id=crew.id)


def test_crew_post_never_leaks_into_town_feed(db, crew_with_members, town_user):
    """모임 글이 동네 피드에 섞이지 않는다 — §27 번복의 핵심 조건."""
    crew, owner, _ = crew_with_members
    owner.town_code = "1168053000"
    db.flush()
    cs.create_post(db, owner, scope=PostScope.CREW, category=PostCategory.NOTICE,
                   title="모임 비밀 공지", body="우리끼리", crew_id=crew.id)
    reader = town_user("동네사람")
    titles = [p.title for p in cs.town_feed(db, reader)]
    assert "모임 비밀 공지" not in titles


# --- 동네 경계 ---


def test_other_town_feed_is_separate(db, town_user):
    a = town_user("A", town="1168053000", tname="역삼1동")
    b = town_user("B", town="1174010900", tname="송파1동")
    cs.create_post(db, a, scope=PostScope.TOWN, category=PostCategory.TIP, title="역삼 글", body="내용")
    assert [p.title for p in cs.town_feed(db, a)] == ["역삼 글"]
    assert cs.town_feed(db, b) == []


def test_cannot_read_other_town_post(db, town_user):
    a = town_user("A", town="1168053000")
    b = town_user("B", town="1174010900")
    post = cs.create_post(db, a, scope=PostScope.TOWN, category=PostCategory.TIP, title="글", body="내용")
    with pytest.raises(errors.CrewIsolationViolation):
        cs.get_post(db, post.id, b)


def test_town_required_before_posting(db, town_user):
    u = town_user("동네없음", town=None, tname=None)
    with pytest.raises(ValueError):
        cs.create_post(db, u, scope=PostScope.TOWN, category=PostCategory.TIP, title="글", body="내용")


# --- 공개 글 작성 조건 ---


def test_unverified_cannot_write_public(db, town_user):
    u = town_user("미인증", verified=False)
    with pytest.raises(errors.HandoffGateViolation):
        cs.create_post(db, u, scope=PostScope.TOWN, category=PostCategory.QUESTION, title="질문", body="내용")


def test_unverified_cannot_comment_public(db, town_user):
    writer = town_user("작성자")
    post = cs.create_post(db, writer, scope=PostScope.TOWN, category=PostCategory.QUESTION, title="질문", body="내용")
    lurker = town_user("미인증", verified=False)
    with pytest.raises(errors.HandoffGateViolation):
        cs.add_comment(db, post.id, lurker, "댓글")


def test_notice_category_is_crew_only(db, town_user):
    u = town_user("작성자")
    with pytest.raises(ValueError):
        cs.create_post(db, u, scope=PostScope.TOWN, category=PostCategory.NOTICE, title="공지", body="내용")


# --- 익명 ---


def test_anonymous_keeps_author_for_audit(db, town_user):
    """익명 글도 서버는 작성자를 안다 — 신고·분쟁 대비 (가리는 건 응답 계층)."""
    u = town_user("익명러")
    post = cs.create_post(db, u, scope=PostScope.TOWN, category=PostCategory.QUESTION,
                          title="고민", body="내용", anonymous=True)
    assert post.anonymous is True and post.author_id == u.id


def test_crew_post_cannot_be_anonymous(db, crew_with_members):
    """아는 사이끼리는 익명이 책임 소재를 흐린다 — 강제로 실명."""
    crew, owner, _ = crew_with_members
    post = cs.create_post(db, owner, scope=PostScope.CREW, category=PostCategory.TIP,
                          title="글", body="내용", crew_id=crew.id, anonymous=True)
    assert post.anonymous is False


# --- 좋아요·삭제 ---


def test_like_is_idempotent_toggle(db, town_user):
    u = town_user("A")
    post = cs.create_post(db, u, scope=PostScope.TOWN, category=PostCategory.TIP, title="글", body="내용")
    assert cs.toggle_like(db, post.id, u) == (1, True)
    assert cs.toggle_like(db, post.id, u) == (0, False)
    assert cs.toggle_like(db, post.id, u) == (1, True)


def test_delete_is_author_only_and_soft(db, town_user):
    a = town_user("작성자")
    b = town_user("남")
    post = cs.create_post(db, a, scope=PostScope.TOWN, category=PostCategory.TIP, title="글", body="내용")
    with pytest.raises(errors.HumanChoiceViolation):
        cs.delete_post(db, post.id, b)
    cs.delete_post(db, post.id, a)
    assert post.deleted_at is not None          # 무효화 — 행은 남는다 (감사 추적)
    assert cs.town_feed(db, a) == []            # 피드에서는 사라진다
    with pytest.raises(ValueError):
        cs.get_post(db, post.id, a)


def test_feed_has_upper_bound(db, town_user):
    u = town_user("A")
    for i in range(5):
        cs.create_post(db, u, scope=PostScope.TOWN, category=PostCategory.TIP, title=f"글{i}", body="내용")
    assert len(cs.town_feed(db, u, limit=3)) == 3
    assert len(cs.town_feed(db, u, limit=999)) <= cs.MAX_FEED
