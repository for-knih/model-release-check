"""Complaint, lot traceability, CAPA and frozen effectiveness evidence."""
from alembic import op
import sqlalchemy as sa
revision='0006'
down_revision='0005'
def upgrade():
    S=sa.String;I=sa.Integer;J=sa.JSON;T=sa.Text;B=sa.Boolean
    def c(n,t=S,null=False,**kw):return sa.Column(n,t(),nullable=null,**kw)
    def fk(n,target,null=False,pk=False):return sa.Column(n,S(),sa.ForeignKey(target),nullable=null,primary_key=pk)
    op.create_table('ivd_lots',c('id',primary_key=True),fk('product_id','ivd_products.id'),c('market'),c('number'),fk('product_revision_id','ivd_product_revisions.id'),fk('package_id','ivd_packages.id'),c('snapshot',J),c('registered_by'),c('created_at'),sa.UniqueConstraint('product_id','market','number'))
    op.create_table('ivd_complaints',c('id',primary_key=True),c('received_on'),fk('product_id','ivd_products.id'),c('market'),c('claimed_lot',null=True),fk('lot_id','ivd_lots.id',True),c('problem_type'),c('description',T),c('evidence_ids',J),c('owner'),c('due_date'),c('status'),c('observed_facts',T),c('hypothesis',T,True),c('confirmed_cause',J,True),c('reporting_review',J,True),fk('duplicate_of','ivd_complaints.id',True),c('synthetic',B),c('created_at'))
    op.create_table('ivd_complaint_events',c('id',I,primary_key=True),fk('complaint_id','ivd_complaints.id'),c('actor'),c('action'),c('payload',J),c('created_at'))
    op.create_table('ivd_capas',c('id',primary_key=True),fk('product_id','ivd_products.id'),c('market'),c('problem_type'),c('title'),c('owner'),c('due_date'),c('status'),c('closed_review',J,True),c('created_at'))
    op.create_table('ivd_complaint_capas',fk('complaint_id','ivd_complaints.id',pk=True),fk('capa_id','ivd_capas.id',pk=True))
    op.create_table('ivd_capa_actions',c('id',primary_key=True),fk('capa_id','ivd_capas.id'),c('kind'),c('description'),c('owner'),c('due_date'),c('mandatory',B),c('trigger_evaluation_id',null=True,unique=True),c('execution',J,True))
    op.create_table('ivd_effectiveness_plans',c('id',primary_key=True),fk('capa_id','ivd_capas.id'),c('version',I),c('definition',J),c('covered_action_ids',J),c('registered_by'),c('created_at'),sa.UniqueConstraint('capa_id','version'))
    op.create_table('ivd_distributions',c('id',primary_key=True),fk('capa_id','ivd_capas.id'),c('lot_ids',J),c('period_start'),c('period_end'),c('quantity',I,True),c('source'),c('evidence_ids',J),c('registered_by'),c('created_at'))
    op.create_table('ivd_effectiveness_results',c('id',primary_key=True),fk('capa_id','ivd_capas.id'),fk('plan_id','ivd_effectiveness_plans.id'),c('idempotency_key'),c('request_hash'),c('status'),c('snapshot',J),c('created_at'),sa.UniqueConstraint('capa_id','idempotency_key'))
    op.create_table('ivd_capa_changes',fk('capa_id','ivd_capas.id',pk=True),fk('change_id','ivd_changes.id',pk=True))
    op.create_table('ivd_capa_events',c('id',I,primary_key=True),fk('capa_id','ivd_capas.id'),c('actor'),c('action'),c('payload',J),c('created_at'))
    op.create_table('ivd_pms_exports',c('id',primary_key=True),fk('complaint_id','ivd_complaints.id'),c('snapshot',J),c('markdown',T),c('created_at'))
def downgrade():
    for name in ['ivd_pms_exports','ivd_capa_events','ivd_capa_changes','ivd_effectiveness_results','ivd_distributions','ivd_effectiveness_plans','ivd_capa_actions','ivd_complaint_capas','ivd_capas','ivd_complaint_events','ivd_complaints','ivd_lots']:op.drop_table(name)
