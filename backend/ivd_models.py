from sqlalchemy import ForeignKey, UniqueConstraint, JSON, Text
from sqlalchemy.orm import Mapped,mapped_column
from .db import Base

class Product(Base):
    __tablename__='ivd_products'
    id:Mapped[str]=mapped_column(primary_key=True)
    name:Mapped[str]
    metadata_json:Mapped[dict]=mapped_column(JSON)
    fictional:Mapped[bool]=mapped_column(default=True)

class Document(Base):
    __tablename__='ivd_documents'
    id:Mapped[str]=mapped_column(primary_key=True)
    product_id:Mapped[str]=mapped_column(ForeignKey('ivd_products.id'))
    section:Mapped[str]
    revision:Mapped[int]
    content:Mapped[str]=mapped_column(Text)
    citation:Mapped[str]
    __table_args__=(UniqueConstraint('product_id','section','revision'),)

class Evidence(Base):
    __tablename__='ivd_evidence'
    id:Mapped[str]=mapped_column(primary_key=True)
    product_id:Mapped[str]=mapped_column(ForeignKey('ivd_products.id'))
    evidence_key:Mapped[str]
    revision:Mapped[int]
    title:Mapped[str]
    summary:Mapped[str]=mapped_column(Text)
    citation:Mapped[str]
    previous_id:Mapped[str|None]=mapped_column(ForeignKey('ivd_evidence.id'),nullable=True)
    __table_args__=(UniqueConstraint('product_id','evidence_key','revision'),)

class Package(Base):
    __tablename__='ivd_packages'
    id:Mapped[str]=mapped_column(primary_key=True)
    family_id:Mapped[str]
    product_id:Mapped[str]=mapped_column(ForeignKey('ivd_products.id'))
    market:Mapped[str]
    version:Mapped[int]
    parent_id:Mapped[str|None]=mapped_column(ForeignKey('ivd_packages.id'),nullable=True)
    status:Mapped[str]=mapped_column(default='draft')
    regulatory_review:Mapped[dict|None]=mapped_column(JSON,nullable=True)
    created_at:Mapped[str]
    __table_args__=(UniqueConstraint('family_id','version'),)

class Mapping(Base):
    __tablename__='ivd_mappings'
    id:Mapped[int]=mapped_column(primary_key=True)
    package_id:Mapped[str]=mapped_column(ForeignKey('ivd_packages.id'))
    requirement_key:Mapped[str]
    section:Mapped[str]
    document_id:Mapped[str|None]=mapped_column(ForeignKey('ivd_documents.id'),nullable=True)
    source:Mapped[dict]=mapped_column(JSON)
    clause:Mapped[str]
    mandatory:Mapped[bool]=mapped_column(default=True)
    applicability:Mapped[str]=mapped_column(default='unconfirmed')
    state:Mapped[str]=mapped_column(default='review_needed')
    re_review:Mapped[bool]=mapped_column(default=False)
    reviewer:Mapped[str|None]=mapped_column(nullable=True)
    rationale:Mapped[str|None]=mapped_column(nullable=True)
    __table_args__=(UniqueConstraint('package_id','requirement_key'),)

class EvidenceLink(Base):
    __tablename__='ivd_mapping_evidence'
    mapping_id:Mapped[int]=mapped_column(ForeignKey('ivd_mappings.id'),primary_key=True)
    evidence_id:Mapped[str]=mapped_column(ForeignKey('ivd_evidence.id'),primary_key=True)

class Supplement(Base):
    __tablename__='ivd_requests'
    id:Mapped[str]=mapped_column(primary_key=True)
    package_id:Mapped[str]=mapped_column(ForeignKey('ivd_packages.id'))
    origin_id:Mapped[str]
    requirement_key:Mapped[str|None]=mapped_column(nullable=True)
    section:Mapped[str|None]=mapped_column(nullable=True)
    reason:Mapped[str]=mapped_column(Text)
    owner:Mapped[str]
    due_date:Mapped[str]
    status:Mapped[str]=mapped_column(default='requested')
    answer:Mapped[str|None]=mapped_column(Text,nullable=True)
    evidence_ids:Mapped[list]=mapped_column(JSON,default=list)
    reviewer:Mapped[str|None]=mapped_column(nullable=True)
    closure_reason:Mapped[str|None]=mapped_column(Text,nullable=True)

class Event(Base):
    __tablename__='ivd_events'
    id:Mapped[int]=mapped_column(primary_key=True)
    package_id:Mapped[str]=mapped_column(ForeignKey('ivd_packages.id'))
    actor:Mapped[str]
    action:Mapped[str]
    payload:Mapped[dict]=mapped_column(JSON)
    created_at:Mapped[str]

class Export(Base):
    __tablename__='ivd_exports'
    id:Mapped[str]=mapped_column(primary_key=True)
    package_id:Mapped[str]=mapped_column(ForeignKey('ivd_packages.id'))
    snapshot:Mapped[dict]=mapped_column(JSON)
    markdown:Mapped[str]=mapped_column(Text)
    created_at:Mapped[str]
