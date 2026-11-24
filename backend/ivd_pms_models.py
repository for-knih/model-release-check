from sqlalchemy import ForeignKey,UniqueConstraint,JSON,Text
from sqlalchemy.orm import Mapped,mapped_column
from .db import Base

class Lot(Base):
    __tablename__='ivd_lots'
    id:Mapped[str]=mapped_column(primary_key=True)
    product_id:Mapped[str]=mapped_column(ForeignKey('ivd_products.id'))
    market:Mapped[str]
    number:Mapped[str]
    product_revision_id:Mapped[str]=mapped_column(ForeignKey('ivd_product_revisions.id'))
    package_id:Mapped[str]=mapped_column(ForeignKey('ivd_packages.id'))
    snapshot:Mapped[dict]=mapped_column(JSON)
    registered_by:Mapped[str]
    created_at:Mapped[str]
    __table_args__=(UniqueConstraint('product_id','market','number'),)

class Complaint(Base):
    __tablename__='ivd_complaints'
    id:Mapped[str]=mapped_column(primary_key=True)
    received_on:Mapped[str]
    product_id:Mapped[str]=mapped_column(ForeignKey('ivd_products.id'))
    market:Mapped[str]
    claimed_lot:Mapped[str|None]=mapped_column(nullable=True)
    lot_id:Mapped[str|None]=mapped_column(ForeignKey('ivd_lots.id'),nullable=True)
    problem_type:Mapped[str]
    description:Mapped[str]=mapped_column(Text)
    evidence_ids:Mapped[list]=mapped_column(JSON)
    owner:Mapped[str]
    due_date:Mapped[str]
    status:Mapped[str]
    observed_facts:Mapped[str]=mapped_column(Text)
    hypothesis:Mapped[str|None]=mapped_column(Text,nullable=True)
    confirmed_cause:Mapped[dict|None]=mapped_column(JSON,nullable=True)
    reporting_review:Mapped[dict|None]=mapped_column(JSON,nullable=True)
    duplicate_of:Mapped[str|None]=mapped_column(ForeignKey('ivd_complaints.id'),nullable=True)
    synthetic:Mapped[bool]
    created_at:Mapped[str]

class ComplaintEvent(Base):
    __tablename__='ivd_complaint_events'
    id:Mapped[int]=mapped_column(primary_key=True)
    complaint_id:Mapped[str]=mapped_column(ForeignKey('ivd_complaints.id'))
    actor:Mapped[str]
    action:Mapped[str]
    payload:Mapped[dict]=mapped_column(JSON)
    created_at:Mapped[str]

class Capa(Base):
    __tablename__='ivd_capas'
    id:Mapped[str]=mapped_column(primary_key=True)
    product_id:Mapped[str]=mapped_column(ForeignKey('ivd_products.id'))
    market:Mapped[str]
    problem_type:Mapped[str]
    title:Mapped[str]
    owner:Mapped[str]
    due_date:Mapped[str]
    status:Mapped[str]=mapped_column(default='open')
    closed_review:Mapped[dict|None]=mapped_column(JSON,nullable=True)
    created_at:Mapped[str]

class ComplaintCapa(Base):
    __tablename__='ivd_complaint_capas'
    complaint_id:Mapped[str]=mapped_column(ForeignKey('ivd_complaints.id'),primary_key=True)
    capa_id:Mapped[str]=mapped_column(ForeignKey('ivd_capas.id'),primary_key=True)

class CapaAction(Base):
    __tablename__='ivd_capa_actions'
    id:Mapped[str]=mapped_column(primary_key=True)
    capa_id:Mapped[str]=mapped_column(ForeignKey('ivd_capas.id'))
    kind:Mapped[str]
    description:Mapped[str]
    owner:Mapped[str]
    due_date:Mapped[str]
    mandatory:Mapped[bool]
    trigger_evaluation_id:Mapped[str|None]=mapped_column(unique=True,nullable=True)
    execution:Mapped[dict|None]=mapped_column(JSON,nullable=True)

class EffectivenessPlan(Base):
    __tablename__='ivd_effectiveness_plans'
    id:Mapped[str]=mapped_column(primary_key=True)
    capa_id:Mapped[str]=mapped_column(ForeignKey('ivd_capas.id'))
    version:Mapped[int]
    definition:Mapped[dict]=mapped_column(JSON)
    covered_action_ids:Mapped[list]=mapped_column(JSON)
    registered_by:Mapped[str]
    created_at:Mapped[str]
    __table_args__=(UniqueConstraint('capa_id','version'),)

class Distribution(Base):
    __tablename__='ivd_distributions'
    id:Mapped[str]=mapped_column(primary_key=True)
    capa_id:Mapped[str]=mapped_column(ForeignKey('ivd_capas.id'))
    lot_ids:Mapped[list]=mapped_column(JSON)
    period_start:Mapped[str]
    period_end:Mapped[str]
    quantity:Mapped[int|None]=mapped_column(nullable=True)
    source:Mapped[str]
    evidence_ids:Mapped[list]=mapped_column(JSON)
    registered_by:Mapped[str]
    created_at:Mapped[str]

class Effectiveness(Base):
    __tablename__='ivd_effectiveness_results'
    id:Mapped[str]=mapped_column(primary_key=True)
    capa_id:Mapped[str]=mapped_column(ForeignKey('ivd_capas.id'))
    plan_id:Mapped[str]=mapped_column(ForeignKey('ivd_effectiveness_plans.id'))
    idempotency_key:Mapped[str]
    request_hash:Mapped[str]
    status:Mapped[str]
    snapshot:Mapped[dict]=mapped_column(JSON)
    created_at:Mapped[str]
    __table_args__=(UniqueConstraint('capa_id','idempotency_key'),)

class CapaChange(Base):
    __tablename__='ivd_capa_changes'
    capa_id:Mapped[str]=mapped_column(ForeignKey('ivd_capas.id'),primary_key=True)
    change_id:Mapped[str]=mapped_column(ForeignKey('ivd_changes.id'),primary_key=True)

class CapaEvent(Base):
    __tablename__='ivd_capa_events'
    id:Mapped[int]=mapped_column(primary_key=True)
    capa_id:Mapped[str]=mapped_column(ForeignKey('ivd_capas.id'))
    actor:Mapped[str]
    action:Mapped[str]
    payload:Mapped[dict]=mapped_column(JSON)
    created_at:Mapped[str]

class PmsExport(Base):
    __tablename__='ivd_pms_exports'
    id:Mapped[str]=mapped_column(primary_key=True)
    complaint_id:Mapped[str]=mapped_column(ForeignKey('ivd_complaints.id'))
    snapshot:Mapped[dict]=mapped_column(JSON)
    markdown:Mapped[str]=mapped_column(Text)
    created_at:Mapped[str]
