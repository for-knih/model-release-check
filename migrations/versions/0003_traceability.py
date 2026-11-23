"""Versioned requirements, stored evidence and release review exports."""
from alembic import op
import sqlalchemy as sa
revision = '0003'
down_revision = '0002'

def upgrade():
    op.create_table('policy_versions', sa.Column('id',sa.Integer(),primary_key=True), sa.Column('identifier',sa.String(),nullable=False), sa.Column('version',sa.Integer(),nullable=False), sa.Column('config',sa.JSON(),nullable=False), sa.UniqueConstraint('identifier','version'))
    op.create_table('requirement_versions',sa.Column('id',sa.Integer(),primary_key=True),sa.Column('identifier',sa.String(),nullable=False),sa.Column('version',sa.Integer(),nullable=False),sa.Column('title',sa.String(),nullable=False),sa.Column('verification_condition',sa.String(),nullable=False),sa.Column('owner',sa.String(),nullable=False),sa.Column('status',sa.String(),nullable=False),sa.Column('mandatory',sa.Boolean(),nullable=False),sa.Column('policy_id',sa.Integer(),sa.ForeignKey('policy_versions.id'),nullable=False),sa.UniqueConstraint('identifier','version'))
    op.create_table('run_requirements',sa.Column('run_id',sa.String(),sa.ForeignKey('runs.id'),primary_key=True),sa.Column('requirement_id',sa.Integer(),sa.ForeignKey('requirement_versions.id'),primary_key=True),sa.Column('snapshot',sa.JSON(),nullable=False),sa.Column('result',sa.JSON()))
    op.create_table('releases',sa.Column('id',sa.String(),primary_key=True),sa.Column('name',sa.String(),nullable=False),sa.Column('initial_run_id',sa.String(),sa.ForeignKey('runs.id')),sa.Column('candidate_run_id',sa.String(),sa.ForeignKey('runs.id')),sa.Column('holdout_run_id',sa.String(),sa.ForeignKey('runs.id')),sa.Column('requirements',sa.JSON(),nullable=False),sa.Column('reproduction_sources',sa.JSON(),nullable=False),sa.Column('created_at',sa.String(),nullable=False))
    # Nullable inline references preserve existing review rows on SQLite.
    if op.get_bind().dialect.name=='sqlite':
        op.execute('ALTER TABLE reviews ADD COLUMN release_id VARCHAR REFERENCES releases(id)')
    else:
        op.add_column('reviews',sa.Column('release_id',sa.String(),nullable=True))
        op.create_foreign_key('fk_review_release','reviews','releases',['release_id'],['id'])
    op.add_column('reviews',sa.Column('evidence',sa.JSON(),nullable=True))
    op.create_table('release_exports',sa.Column('id',sa.String(),primary_key=True),sa.Column('release_id',sa.String(),sa.ForeignKey('releases.id'),nullable=False),sa.Column('snapshot',sa.JSON(),nullable=False),sa.Column('markdown',sa.Text(),nullable=False),sa.Column('created_at',sa.String(),nullable=False))

def downgrade():
    op.drop_table('release_exports')
    op.drop_column('reviews','evidence')
    if op.get_bind().dialect.name=='sqlite':
        op.execute('ALTER TABLE reviews DROP COLUMN release_id')
    else:
        op.drop_constraint('fk_review_release','reviews',type_='foreignkey')
        op.drop_column('reviews','release_id')
    for table in ['releases','run_requirements','requirement_versions','policy_versions']:
        op.drop_table(table)
