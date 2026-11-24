import os
from alembic import context
from sqlalchemy import create_engine
from backend.db import Base
from backend import ivd_models
config = context.config
url = os.getenv('DATABASE_URL', config.get_main_option('sqlalchemy.url'))
def migrate(connection):
    context.configure(connection=connection, target_metadata=Base.metadata)
    with context.begin_transaction():
        context.run_migrations()
if config.attributes.get('connection') is not None:
    migrate(config.attributes['connection'])
else:
    with create_engine(url).connect() as connection:
        migrate(connection)
