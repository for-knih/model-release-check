"""Product revision baseline, deterministic impact review and atomic release outcome."""
from alembic import op
import sqlalchemy as sa
from uuid import uuid4
from datetime import datetime,timezone
revision='0005'
down_revision='0004'

def upgrade():
    S=sa.String;I=sa.Integer;J=sa.JSON
    def c(name,type=S,nullable=False,**kw):return sa.Column(name,type(),nullable=nullable,**kw)
    def fk(name,target,nullable=False):return sa.Column(name,S(),sa.ForeignKey(target),nullable=nullable)
    op.add_column('ivd_products',sa.Column('current_revision',I(),server_default='1',nullable=False))
    op.create_table('ivd_product_revisions',c('id',primary_key=True),fk('product_id','ivd_products.id'),c('revision',I),c('data',J),c('created_by_change',nullable=True,unique=True),c('created_at'),sa.UniqueConstraint('product_id','revision'))
    op.create_table('ivd_impact_rules',c('id',primary_key=True),c('field'),c('market'),c('section'),c('version',I),c('reason'),sa.UniqueConstraint('field','market','section','version'))
    op.create_table('ivd_changes',c('id',primary_key=True),fk('product_id','ivd_products.id'),fk('base_revision_id','ivd_product_revisions.id'),c('changes',J),c('evidence_replacements',J),c('reason'),c('requester'),c('status'),c('created_at'),c('result',J,True))
    for name,target in [('product_revision_id','ivd_product_revisions.id'),('work_for_change_id','ivd_changes.id')]:
        if op.get_bind().dialect.name=='sqlite':op.execute(f'ALTER TABLE ivd_packages ADD COLUMN {name} VARCHAR REFERENCES {target.replace(".","(")})')
        else:
            op.add_column('ivd_packages',c(name,nullable=True))
            table,column=target.split('.');op.create_foreign_key('fk_package_'+name,'ivd_packages',table,[name],[column])
    op.create_table('ivd_change_markets',c('id',primary_key=True),fk('change_id','ivd_changes.id'),c('market'),fk('baseline_package_id','ivd_packages.id'),c('baseline_snapshot',J),c('judgment',J,True),fk('work_package_id','ivd_packages.id',True),fk('final_package_id','ivd_packages.id',True),sa.UniqueConstraint('change_id','market'))
    op.create_table('ivd_impact_items',c('id',primary_key=True),fk('change_id','ivd_changes.id'),fk('market_id','ivd_change_markets.id'),c('candidate_key'),c('snapshot',J),c('decision',J,True),sa.UniqueConstraint('market_id','candidate_key'))
    op.create_table('ivd_change_corrections',c('id',primary_key=True),fk('change_id','ivd_changes.id'),c('reviewer'),c('reason'),c('created_at'),c('response',J,True))
    op.create_table('ivd_change_events',c('id',I,primary_key=True),fk('change_id','ivd_changes.id'),c('actor'),c('action'),c('payload',J),c('created_at'))
    op.create_table('ivd_change_exports',c('id',primary_key=True),fk('change_id','ivd_changes.id'),c('snapshot',J),c('markdown',sa.Text),c('created_at'))
    connection=op.get_bind()
    products=sa.table('ivd_products',sa.column('id',S),sa.column('name',S),sa.column('metadata_json',J),sa.column('fictional',sa.Boolean))
    revisions=sa.table('ivd_product_revisions',sa.column('id',S),sa.column('product_id',S),sa.column('revision',I),sa.column('data',J),sa.column('created_at',S))
    for p in connection.execute(sa.select(products)).mappings():
        id=str(uuid4());connection.execute(revisions.insert().values(id=id,product_id=p['id'],revision=1,data={'name':p['name'],'metadata':p['metadata_json'],'fictional':p['fictional']},created_at=datetime.now(timezone.utc).isoformat()))
        connection.execute(sa.text('UPDATE ivd_packages SET product_revision_id=:revision WHERE product_id=:product'),{'revision':id,'product':p['id']})

def downgrade():
    for name in ['ivd_change_exports','ivd_change_events','ivd_change_corrections','ivd_impact_items','ivd_change_markets']:op.drop_table(name)
    for name in ['work_for_change_id','product_revision_id']:
        if op.get_bind().dialect.name=='sqlite':op.execute(f'ALTER TABLE ivd_packages DROP COLUMN {name}')
        else:
            op.drop_constraint('fk_package_'+name,'ivd_packages',type_='foreignkey');op.drop_column('ivd_packages',name)
    for name in ['ivd_changes','ivd_impact_rules','ivd_product_revisions']:op.drop_table(name)
    op.drop_column('ivd_products','current_revision')
