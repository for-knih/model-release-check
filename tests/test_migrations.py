from alembic import command
from alembic.config import Config
from sqlalchemy import create_engine, inspect, text

def test_upgrade_preserves_existing_dataset_and_downgrade():
    engine=create_engine('sqlite://')
    with engine.connect() as connection:
        connection.execute(text('PRAGMA foreign_keys=ON'))
        cfg=Config('alembic.ini');cfg.attributes['connection']=connection
        command.upgrade(cfg,'0001')
        connection.execute(text("INSERT INTO datasets (id,name,version) VALUES ('old','기존','v1')"));connection.commit()
        connection.execute(text("INSERT INTO cases (dataset_id,case_id,text,expected_label) VALUES ('old','c1','문의','기타')"));connection.commit()
        command.upgrade(cfg,'head')
        assert connection.execute(text("SELECT name,parent_id FROM datasets WHERE id='old'")).one()==('기존',None)
        assert {'analyses','case_sources'}<=set(inspect(connection).get_table_names())
        assert connection.execute(text('SELECT count(*) FROM cases')).scalar()==1
        command.downgrade(cfg,'0001')
        assert connection.execute(text('SELECT version FROM datasets')).scalar()=='v1'
        command.upgrade(cfg,'head')
        assert 'parent_id' in {c['name'] for c in inspect(connection).get_columns('datasets')}
