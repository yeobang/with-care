"""불변식 위반 예외. 각 예외는 docs/02-guardrails.md의 I-번호에 대응한다."""


class InvariantViolation(Exception):
    invariant: str = "?"


class HandoffGateViolation(InvariantViolation):
    """I1: 본인인증 + 크루 초대 없이는 인계(및 그 전제인 크루 합류) 불가."""

    invariant = "I1"


class ConsentMissing(InvariantViolation):
    """I2: 포괄 합의 없이는 크루 활동 시작 불가."""

    invariant = "I2"


class CrewIsolationViolation(InvariantViolation):
    """I6: 크루 데이터는 크루 멤버만 조회할 수 있다."""

    invariant = "I6"


class CharterIncomplete(InvariantViolation):
    """I7: 규약 없는 크루는 활성화되지 않는다."""

    invariant = "I7"


class UnlicensedCarePattern(InvariantViolation):
    """I3: 무인가 보육 패턴 금지 — 돌봄자 1인 + 타인 영유아 5인 이상."""

    invariant = "I3"


class HumanChoiceViolation(InvariantViolation):
    """I4: 고르기는 사람 — 배정 확정은 각 가정의 명시적 탭으로만."""

    invariant = "I4"
