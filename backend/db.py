import os
from sqlalchemy import create_engine, String, ForeignKey, UniqueConstraint, JSON, CheckConstraint
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, sessionmaker

class Base(DeclarativeBase):
    pass

class Dataset(Base):
    __tablename__ = 'datasets'
    id: Mapped[str] = mapped_column(String, primary_key=True)
    name: Mapped[str]
    version: Mapped[str]
    parent_id: Mapped[str | None] = mapped_column(ForeignKey('datasets.id'), nullable=True)
    __table_args__ = (UniqueConstraint('name', 'version'),)

class Case(Base):
    __tablename__ = 'cases'
    id: Mapped[int] = mapped_column(primary_key=True)
    dataset_id: Mapped[str] = mapped_column(ForeignKey('datasets.id'))
    case_id: Mapped[str]
    text: Mapped[str]
    expected_label: Mapped[str]
    __table_args__ = (UniqueConstraint('dataset_id', 'case_id'),)

class Run(Base):
    __tablename__ = 'runs'
    id: Mapped[str] = mapped_column(String, primary_key=True)
    dataset_id: Mapped[str] = mapped_column(ForeignKey('datasets.id'))
    idempotency_key: Mapped[str] = mapped_column(String, unique=True)
    request_hash: Mapped[str]
    status: Mapped[str] = mapped_column(default='queued')
    dispatched: Mapped[bool] = mapped_column(default=False)
    snapshot: Mapped[dict] = mapped_column(JSON)
    result: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    error: Mapped[str | None] = mapped_column(nullable=True)
    __table_args__ = (CheckConstraint("status in ('queued','running','succeeded','failed')"),)

class Prediction(Base):
    __tablename__ = 'predictions'
    id: Mapped[int] = mapped_column(primary_key=True)
    run_id: Mapped[str] = mapped_column(ForeignKey('runs.id'))
    case_id: Mapped[int] = mapped_column(ForeignKey('cases.id'))
    model_role: Mapped[str]
    label: Mapped[str]
    __table_args__ = (UniqueConstraint('run_id', 'case_id', 'model_role'),)

class Review(Base):
    __tablename__ = 'reviews'
    id: Mapped[int] = mapped_column(primary_key=True)
    run_id: Mapped[str] = mapped_column(ForeignKey('runs.id'))
    reviewer: Mapped[str]
    decision: Mapped[str]
    reason: Mapped[str]
    created_at: Mapped[str]

class Analysis(Base):
    __tablename__ = 'analyses'
    id: Mapped[str] = mapped_column(String, primary_key=True)
    run_id: Mapped[str] = mapped_column(ForeignKey('runs.id'))
    config_hash: Mapped[str]
    config: Mapped[dict] = mapped_column(JSON)
    status: Mapped[str] = mapped_column(default='queued')
    dispatched: Mapped[bool] = mapped_column(default=False)
    result: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    error: Mapped[str | None] = mapped_column(nullable=True)
    created_at: Mapped[str]
    __table_args__ = (UniqueConstraint('run_id', 'config_hash'), CheckConstraint("status in ('queued','running','succeeded','failed')"))

class CaseSource(Base):
    __tablename__ = 'case_sources'
    id: Mapped[int] = mapped_column(primary_key=True)
    dataset_id: Mapped[str] = mapped_column(ForeignKey('datasets.id'))
    case_id: Mapped[int] = mapped_column(ForeignKey('cases.id'))
    source_run_id: Mapped[str] = mapped_column(ForeignKey('runs.id'))
    source_case_id: Mapped[str]
    __table_args__ = (UniqueConstraint('dataset_id', 'source_run_id', 'source_case_id'),)

engine = create_engine(os.getenv('DATABASE_URL', 'sqlite:///./local.db'))
if engine.dialect.name == 'sqlite':
    from sqlalchemy import event
    @event.listens_for(engine, 'connect')
    def sqlite_foreign_keys(connection, _):
        connection.execute('PRAGMA foreign_keys=ON')
        connection.execute('PRAGMA busy_timeout=10000')
Session = sessionmaker(engine, expire_on_commit=False)
