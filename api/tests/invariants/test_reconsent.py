"""아이 프로필 수정 → 보호자 재동의 (I2, §19-5: "아이 프로필 변경 시 재확인")."""

import pytest

from app.domain import board_service as board
from app.domain import crew_service as svc
from app.domain import errors
from app.domain.models import Child, SlotKind


@pytest.fixture
def family_crew(db, verified_user):
    owner = verified_user("오너")
    crew = svc.create_crew(db, owner, "크루")
    mom = verified_user("부모")
    svc.join_crew(db, mom, svc.create_invite(db, crew.id, owner).token)
    for u in (owner, mom):
        svc.submit_consent(db, crew.id, u, liability_ack=True, photo_consent=True, guardian_consent=True)
    svc.confirm_charter(db, crew.id, owner)
    svc.activate_crew(db, crew.id, owner)
    child = Child(guardian_id=mom.id, name="아이", birth_year_month="2022-05", emergency_contact="010")
    db.add(child)
    db.flush()
    return crew, owner, mom, child


def test_child_edit_blocks_board_until_reconsent(db, family_crew):
    crew, owner, mom, child = family_crew
    board.add_slot(db, crew.id, mom, kind=SlotKind.NEED, date="2026-09-07",
                   start_hour=15, end_hour=17, child_id=child.id)  # 수정 전엔 가능

    svc.update_child(db, mom, child.id, allergies="땅콩")

    with pytest.raises(errors.ConsentMissing):
        board.add_slot(db, crew.id, mom, kind=SlotKind.NEED, date="2026-09-08",
                       start_hour=15, end_hour=17, child_id=child.id)

    # 재동의 후 복구
    svc.submit_consent(db, crew.id, mom, liability_ack=True, photo_consent=True, guardian_consent=True)
    board.add_slot(db, crew.id, mom, kind=SlotKind.NEED, date="2026-09-08",
                   start_hour=15, end_hour=17, child_id=child.id)


def test_child_edit_only_touches_editors_consent(db, family_crew):
    crew, owner, mom, child = family_crew
    svc.update_child(db, mom, child.id, medication="해열제")
    # 오너의 합의는 그대로 — 보드 사용 가능
    board.add_slot(db, crew.id, owner, kind=SlotKind.AVAILABLE, date="2026-09-07",
                   start_hour=15, end_hour=17)


def test_cannot_edit_others_child(db, family_crew):
    crew, owner, mom, child = family_crew
    with pytest.raises(ValueError):
        svc.update_child(db, owner, child.id, name="바꿈")
