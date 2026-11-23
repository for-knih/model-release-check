"""Independent review-only analysis and immutable dataset lineage."""
from alembic import op
import sqlalchemy as sa
revision = '0002'
down_revision = '0001'

def upgrade():
    if op.get_bind().dialect.name == 'sqlite':
        # SQLite accepts a nullable inline reference without rebuilding a parent
        # table already referenced by historical cases/runs.
        op.execute('ALTER TABLE datasets ADD COLUMN parent_id VARCHAR REFERENCES datasets(id)')
    else:
        op.add_column('datasets', sa.Column('parent_id', sa.String(), nullable=True))
        op.create_foreign_key('fk_dataset_parent', 'datasets', 'datasets', ['parent_id'], ['id'])
    op.create_table('analyses', sa.Column('id', sa.String(), primary_key=True), sa.Column('run_id', sa.String(), sa.ForeignKey('runs.id'), nullable=False), sa.Column('config_hash', sa.String(), nullable=False), sa.Column('config', sa.JSON(), nullable=False), sa.Column('status', sa.String(), nullable=False), sa.Column('dispatched', sa.Boolean(), nullable=False), sa.Column('result', sa.JSON()), sa.Column('error', sa.String()), sa.Column('created_at', sa.String(), nullable=False), sa.UniqueConstraint('run_id', 'config_hash'), sa.CheckConstraint("status in ('queued','running','succeeded','failed')"))
    op.create_table('case_sources', sa.Column('id', sa.Integer(), primary_key=True), sa.Column('dataset_id', sa.String(), sa.ForeignKey('datasets.id'), nullable=False), sa.Column('case_id', sa.Integer(), sa.ForeignKey('cases.id'), nullable=False), sa.Column('source_run_id', sa.String(), sa.ForeignKey('runs.id'), nullable=False), sa.Column('source_case_id', sa.String(), nullable=False), sa.UniqueConstraint('dataset_id', 'source_run_id', 'source_case_id'))

def downgrade():
    op.drop_table('case_sources')
    op.drop_table('analyses')
    if op.get_bind().dialect.name == 'sqlite':
        op.execute('ALTER TABLE datasets DROP COLUMN parent_id')
    else:
        op.drop_constraint('fk_dataset_parent', 'datasets', type_='foreignkey')
        op.drop_column('datasets', 'parent_id')
