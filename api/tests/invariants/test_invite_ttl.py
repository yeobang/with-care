"""초대 토큰 만료 — 가정: 7일 TTL (요구사항에 없는 기본값, crew_service.INVITE_TTL).

카톡방에 방치된 초대 링크가 영구 관문(I1 우회 통로)이 되지 않게 한다.
"""

from datetime import timedelta

import pytest

from app.domain import crew_service as svc
from app.domain import errors


def test_expired_invite_rejected(db, verified_user):
    owner = verified_user("오너")
    crew = svc.create_crew(db, owner, "크루")
    invite = svc.create_invite(db, crew.id, owner)
    invite.created_at = invite.created_at - timedelta(days=8)
    db.flush()
    joiner = verified_user("늦은사람")
    with pytest.raises(errors.HandoffGateViolation):
        svc.join_crew(db, joiner, invite.token)


def test_fresh_invite_ok(db, verified_user):
    owner = verified_user("오너")
    crew = svc.create_crew(db, owner, "크루")
    invite = svc.create_invite(db, crew.id, owner)
    joiner = verified_user("바로온사람")
    assert svc.join_crew(db, joiner, invite.token) is not None
