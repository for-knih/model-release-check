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

def test_traceability_migration_preserves_historical_reviews():
    engine=create_engine('sqlite://')
    with engine.connect() as connection:
        connection.execute(text('PRAGMA foreign_keys=ON'))
        cfg=Config('alembic.ini');cfg.attributes['connection']=connection
        command.upgrade(cfg,'0002')
        connection.execute(text("INSERT INTO datasets (id,name,version) VALUES ('d','old','hash')"))
        connection.execute(text("INSERT INTO runs (id,dataset_id,idempotency_key,request_hash,status,dispatched,snapshot) VALUES ('r','d','key','hash','succeeded',1,'{}')"))
        connection.execute(text("INSERT INTO reviews (run_id,reviewer,decision,reason,created_at) VALUES ('r','QA','hold','historical reason','2026-01-01')"));connection.commit()
        command.upgrade(cfg,'head')
        assert connection.execute(text('SELECT reason,release_id,evidence FROM reviews')).one()==('historical reason',None,None)
        assert {'policy_versions','requirement_versions','run_requirements','releases','release_exports'}<=set(inspect(connection).get_table_names())
        command.downgrade(cfg,'0002')
        assert connection.execute(text('SELECT reason FROM reviews')).scalar()=='historical reason'
