"""Isolated IVD document packages; no changes to existing model evaluation records."""
from alembic import op
import sqlalchemy as sa
revision='0004'
down_revision='0003'
def upgrade():
    S=sa.String; I=sa.Integer; J=sa.JSON; T=sa.Text; B=sa.Boolean
    def c(name,type=S,nullable=False,**kw):return sa.Column(name,type(),nullable=nullable,**kw)
    def fk(name,target,nullable=False):return sa.Column(name,S(),sa.ForeignKey(target),nullable=nullable)
    op.create_table('ivd_products',c('id',primary_key=True),c('name'),c('metadata_json',J),c('fictional',B))
    op.create_table('ivd_documents',c('id',primary_key=True),fk('product_id','ivd_products.id'),c('section'),c('revision',I),c('content',T),c('citation'),sa.UniqueConstraint('product_id','section','revision'))
    op.create_table('ivd_evidence',c('id',primary_key=True),fk('product_id','ivd_products.id'),c('evidence_key'),c('revision',I),c('title'),c('summary',T),c('citation'),fk('previous_id','ivd_evidence.id',True),sa.UniqueConstraint('product_id','evidence_key','revision'))
    op.create_table('ivd_packages',c('id',primary_key=True),c('family_id'),fk('product_id','ivd_products.id'),c('market'),c('version',I),fk('parent_id','ivd_packages.id',True),c('status'),c('regulatory_review',J,True),c('created_at'),sa.UniqueConstraint('family_id','version'))
    op.create_table('ivd_mappings',c('id',I,primary_key=True),fk('package_id','ivd_packages.id'),c('requirement_key'),c('section'),fk('document_id','ivd_documents.id',True),c('source',J),c('clause'),c('mandatory',B),c('applicability'),c('state'),c('re_review',B),c('reviewer',nullable=True),c('rationale',nullable=True),sa.UniqueConstraint('package_id','requirement_key'))
    op.create_table('ivd_mapping_evidence',sa.Column('mapping_id',I(),sa.ForeignKey('ivd_mappings.id'),primary_key=True),sa.Column('evidence_id',S(),sa.ForeignKey('ivd_evidence.id'),primary_key=True))
    op.create_table('ivd_requests',c('id',primary_key=True),fk('package_id','ivd_packages.id'),c('origin_id'),c('requirement_key',nullable=True),c('section',nullable=True),c('reason',T),c('owner'),c('due_date'),c('status'),c('answer',T,True),c('evidence_ids',J),c('reviewer',nullable=True),c('closure_reason',T,True))
    op.create_table('ivd_events',c('id',I,primary_key=True),fk('package_id','ivd_packages.id'),c('actor'),c('action'),c('payload',J),c('created_at'))
    op.create_table('ivd_exports',c('id',primary_key=True),fk('package_id','ivd_packages.id'),c('snapshot',J),c('markdown',T),c('created_at'))
def downgrade():
    for name in ['ivd_exports','ivd_events','ivd_requests','ivd_mapping_evidence','ivd_mappings','ivd_packages','ivd_evidence','ivd_documents','ivd_products']:op.drop_table(name)
