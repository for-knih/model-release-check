"""Initial immutable datasets, runs, predictions and review history."""
from alembic import op
import sqlalchemy as sa
revision = '0001'
down_revision = None

def upgrade():
    op.create_table('datasets', sa.Column('id', sa.String(), primary_key=True), sa.Column('name', sa.String(), nullable=False), sa.Column('version', sa.String(), nullable=False), sa.UniqueConstraint('name', 'version'))
    op.create_table('cases', sa.Column('id', sa.Integer(), primary_key=True), sa.Column('dataset_id', sa.String(), sa.ForeignKey('datasets.id'), nullable=False), sa.Column('case_id', sa.String(), nullable=False), sa.Column('text', sa.String(), nullable=False), sa.Column('expected_label', sa.String(), nullable=False), sa.UniqueConstraint('dataset_id', 'case_id'))
    op.create_table('runs', sa.Column('id', sa.String(), primary_key=True), sa.Column('dataset_id', sa.String(), sa.ForeignKey('datasets.id'), nullable=False), sa.Column('idempotency_key', sa.String(), nullable=False, unique=True), sa.Column('request_hash', sa.String(), nullable=False), sa.Column('status', sa.String(), nullable=False), sa.Column('dispatched', sa.Boolean(), nullable=False), sa.Column('snapshot', sa.JSON(), nullable=False), sa.Column('result', sa.JSON()), sa.Column('error', sa.String()), sa.CheckConstraint("status in ('queued','running','succeeded','failed')"))
    op.create_table('predictions', sa.Column('id', sa.Integer(), primary_key=True), sa.Column('run_id', sa.String(), sa.ForeignKey('runs.id'), nullable=False), sa.Column('case_id', sa.Integer(), sa.ForeignKey('cases.id'), nullable=False), sa.Column('model_role', sa.String(), nullable=False), sa.Column('label', sa.String(), nullable=False), sa.UniqueConstraint('run_id', 'case_id', 'model_role'))
    op.create_table('reviews', sa.Column('id', sa.Integer(), primary_key=True), sa.Column('run_id', sa.String(), sa.ForeignKey('runs.id'), nullable=False), sa.Column('reviewer', sa.String(), nullable=False), sa.Column('decision', sa.String(), nullable=False), sa.Column('reason', sa.String(), nullable=False), sa.Column('created_at', sa.String(), nullable=False))

def downgrade():
    for name in ['reviews', 'predictions', 'runs', 'cases', 'datasets']:
        op.drop_table(name)
