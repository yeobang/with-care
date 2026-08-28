"""불변식 테스트 하네스 골격.

CLAUDE.md 룰: 모든 불변식은 자동 테스트로 강제한다.
문서에만 있는 불변식은 죽은 불변식이다.

각 불변식은 해당 기능이 구현되는 단계(P1~P4)에서 '위반 시도' 테스트로 채워진다.
그 전까지는 xfail 마커로 존재만 등록해둔다 — 골격이 비면 잊혀지기 때문.
"""

import pytest

PENDING = pytest.mark.xfail(reason="구현 단계 도달 전 (docs/03-dev-plan.md)", strict=False)


@PENDING
def test_i1_no_handoff_without_identity_and_invite():
    """I1: 본인인증 + 크루 초대 없이는 어떤 경로로도 아이 인계 불가. (P1)"""
    raise NotImplementedError


@PENDING
def test_i2_no_activity_without_blanket_consent():
    """I2: 포괄 합의 없이는 크루 활동 시작 불가. (P1)"""
    raise NotImplementedError


@PENDING
def test_i3_unlicensed_care_pattern_blocked():
    """I3: 돌봄자 1인 + 타인 영유아 5인 이상 세션 생성 불가 (이웃 트랙). (P2)"""
    raise NotImplementedError


@PENDING
def test_i4_humans_choose():
    """I4: 배정·시터 선택은 복수 후보 중 명시적 확정 탭. 자동 확정 API 부재 검증. (P2)"""
    raise NotImplementedError


@PENDING
def test_i5_no_money_in_neighbor_track():
    """I5: 크레딧 환급·이체 실행 코드가 존재하지 않음을 검증. (P4)"""
    raise NotImplementedError


@PENDING
def test_i6_crew_data_isolation():
    """I6: 크루 밖 멤버는 사진·장부·아이 정보 조회 불가. (P1)"""
    raise NotImplementedError


@PENDING
def test_i7_no_crew_without_charter():
    """I7: 규약 미완성 크루는 세션 생성 불가. (P1)"""
    raise NotImplementedError


@PENDING
def test_i8_no_age_branching():
    """I8: 도메인 모델에 연령 분기 부재 (0~2세 플래그·I3 카운트 제외). (P1)"""
    raise NotImplementedError
