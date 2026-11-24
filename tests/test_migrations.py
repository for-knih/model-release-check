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

def test_ivd_migration_preserves_existing_data_and_enforces_evidence_links():
    engine=create_engine('sqlite://')
    with engine.connect() as connection:
        connection.execute(text('PRAGMA foreign_keys=ON'))
        cfg=Config('alembic.ini');cfg.attributes['connection']=connection
        command.upgrade(cfg,'0003')
        connection.execute(text("INSERT INTO datasets (id,name,version) VALUES ('before-ivd','기존 평가','v1')"));connection.commit()
        command.upgrade(cfg,'0004')
        tables=set(inspect(connection).get_table_names())
        assert {'ivd_products','ivd_documents','ivd_evidence','ivd_packages','ivd_mappings','ivd_mapping_evidence','ivd_requests','ivd_events','ivd_exports'}<=tables
        assert len(inspect(connection).get_foreign_keys('ivd_mapping_evidence'))==2
        command.downgrade(cfg,'0003')
        assert connection.execute(text("SELECT name FROM datasets WHERE id='before-ivd'")).scalar()=='기존 평가'
        command.upgrade(cfg,'head')

def test_pms_migration_preserves_ivd_revision_and_roundtrips():
    engine=create_engine('sqlite://')
    with engine.connect() as connection:
        connection.execute(text('PRAGMA foreign_keys=ON'))
        cfg=Config('alembic.ini');cfg.attributes['connection']=connection
        command.upgrade(cfg,'0005')
        connection.execute(text("INSERT INTO ivd_products (id,name,metadata_json,fictional,current_revision) VALUES ('pms-old','가상 제품','{}',1,1)"));connection.commit()
        command.upgrade(cfg,'0006')
        tables=set(inspect(connection).get_table_names())
        assert {'ivd_lots','ivd_complaints','ivd_capas','ivd_effectiveness_plans','ivd_effectiveness_results','ivd_pms_exports'}<=tables
        assert connection.execute(text("SELECT name FROM ivd_products WHERE id='pms-old'")).scalar()=='가상 제품'
        assert len(inspect(connection).get_foreign_keys('ivd_lots'))==3
        command.downgrade(cfg,'0005')
        assert connection.execute(text("SELECT name FROM ivd_products WHERE id='pms-old'")).scalar()=='가상 제품'
        command.upgrade(cfg,'head')

def test_change_migration_backfills_frozen_product_revision():
    engine=create_engine('sqlite://')
    with engine.connect() as connection:
        connection.execute(text('PRAGMA foreign_keys=ON'))
        cfg=Config('alembic.ini');cfg.attributes['connection']=connection
        command.upgrade(cfg,'0004')
        connection.execute(text("INSERT INTO ivd_products (id,name,metadata_json,fictional) VALUES ('legacy','과거 가상 제품','{}',1)"))
        connection.execute(text("INSERT INTO ivd_packages (id,family_id,product_id,market,version,status,created_at) VALUES ('old-pkg','family','legacy','EU',1,'internal_complete','2026-01-01')"));connection.commit()
        command.upgrade(cfg,'0005')
        assert connection.execute(text("SELECT current_revision FROM ivd_products WHERE id='legacy'")).scalar()==1
        revision=connection.execute(text("SELECT product_revision_id FROM ivd_packages WHERE id='old-pkg'")).scalar();assert revision
        import json
        data=json.loads(connection.execute(text('SELECT data FROM ivd_product_revisions WHERE id=:id'),{'id':revision}).scalar())
        assert data['name']=='과거 가상 제품'
        command.downgrade(cfg,'0004')
        assert connection.execute(text("SELECT name FROM ivd_products WHERE id='legacy'")).scalar()=='과거 가상 제품'
        command.upgrade(cfg,'head')
