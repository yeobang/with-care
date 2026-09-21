"""테스트 전용 헬퍼.

§29 이후 합류는 2단계다 (요청 → 부모 멤버 승인). 대부분의 테스트는 "이 사람을 멤버로
만든다"만 필요하므로 두 단계를 여기서 묶는다. 승인 관문 자체의 테스트는
test_join_approval.py에서 단계를 풀어서 검증한다.
"""

from sqlalchemy import select

from app.domain import crew_service as svc
from app.domain.models import CrewMember


def join_via(db, user, token, approver):
    """초대 링크로 요청하고 승인까지 끝내 멤버를 만든다."""
    req = svc.request_join(db, user, token)
    svc.decide_join(db, req.id, approver, approve=True)
    return db.scalar(
        select(CrewMember).where(
            CrewMember.crew_id == req.crew_id, CrewMember.user_id == user.id
        )
    )
