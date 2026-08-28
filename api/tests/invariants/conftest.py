import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from app.domain.models import Base, User


@pytest.fixture
def db():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    with Session(engine) as session:
        yield session


@pytest.fixture
def verified_user(db):
    def _make(name="부모"):
        u = User(name=name, identity_verified=True)
        db.add(u)
        db.flush()
        return u

    return _make


@pytest.fixture
def active_crew(db, verified_user):
    """규약 확정 + 전원 합의까지 끝난 크루 한 벌."""
    from app.domain import crew_service as svc

    owner = verified_user("오너")
    crew = svc.create_crew(db, owner, "테스트크루")
    svc.submit_consent(db, crew.id, owner, liability_ack=True, photo_consent=True, guardian_consent=True)
    svc.confirm_charter(db, crew.id, owner)
    svc.activate_crew(db, crew.id, owner)
    return crew, owner
