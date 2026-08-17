import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.database import Base
from app.models import Employee


@pytest.fixture()
def db_session():
    # Fresh in-memory SQLite DB per test -- fast, and fully isolated.
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(bind=engine)
    TestingSessionLocal = sessionmaker(bind=engine)
    session = TestingSessionLocal()
    try:
        yield session
    finally:
        session.close()


@pytest.fixture()
def sample_employee(db_session):
    employee = Employee(name="Jahnavi Patel", email="jahnavi.patel@intuitive.ai")
    db_session.add(employee)
    db_session.commit()
    db_session.refresh(employee)
    return employee
