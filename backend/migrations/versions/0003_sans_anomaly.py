"""A2: sans (6 tablo) + anomaly (MeasurementDefinitions, MeasurementRecords, anomaly_results)

Gövde, modellerden Alembic autogenerate ile üretildi (tests/unit/test_migrations.py modelle
birebir aynı olduğunu doğrular). Elle eklenenler: grant()/revoke() satırları.

Kurallar (şema v5.0 §7):
- sans.oturum: retest self-FK; is_retest=1 ise retest_of dolu ve kendisi değil.
- sans.test_kaydi: (session_id, eye, test) tekil; test/birim eşleşmesi CHECK.
- flight_day/day/mission_day negatif olabilir (uçuş öncesi).
- MeasurementRecords: yalnız fizyolojik (eye_code='NA'); (astronaut_id, client_request_id) tekil.
- anomaly_results: data_cutoff_at <= created_at; anomaly_score NULL kalır.

astra_app_role izinleri: kaynak/sonuç kayıtları ekle-oku (değişmez). Güncellenen tek
durum tablosu sans.durum; seed'in güncelleyebilmesi için MeasurementDefinitions.
DELETE hiçbir tabloda yok. astra_eval_role bu şemalara erişmez.

Revision ID: 0003
Revises: 0002
"""
import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import mssql

from migrations.helpers import APP_ROLE, grant, revoke

revision = "0003"
down_revision = "0002"
branch_labels = None
depends_on = None

APP_PERMS = {
    "anomaly.MeasurementDefinitions": "SELECT, INSERT, UPDATE",
    "anomaly.MeasurementRecords": "SELECT, INSERT",
    "anomaly.anomaly_results": "SELECT, INSERT",
    "sans.oturum": "SELECT, INSERT",
    "sans.test_kaydi": "SELECT, INSERT",
    "sans.ortam": "SELECT, INSERT",
    "sans.semptom": "SELECT, INSERT",
    "sans.analiz": "SELECT, INSERT",
    "sans.durum": "SELECT, INSERT, UPDATE",
}


def upgrade() -> None:
    op.create_table('MeasurementDefinitions',
    sa.Column('measurement_code', sa.String(length=60), nullable=False),
    sa.Column('module', sa.String(length=24), nullable=False),
    sa.Column('canonical_unit', sa.Unicode(length=32), nullable=False),
    sa.Column('value_kind', sa.String(length=40), nullable=False),
    sa.Column('protocol_version', sa.String(length=40), nullable=False),
    sa.Column('worsening_direction', sa.String(length=40), nullable=False),
    sa.CheckConstraint("module IN ('physiological','behavioral','sans')", name=op.f('CK_MeasurementDefinitions_module_valid')),
    sa.CheckConstraint("value_kind IN ('numeric','integer','category')", name=op.f('CK_MeasurementDefinitions_value_kind_valid')),
    sa.PrimaryKeyConstraint('measurement_code', name=op.f('PK_MeasurementDefinitions')),
    sa.UniqueConstraint('module', 'measurement_code', name=op.f('UQ_MeasurementDefinitions_module_measurement_code')),
    schema='anomaly'
    )
    op.create_table('ortam',
    sa.Column('mission_id', sa.Unicode(length=32), nullable=False),
    sa.Column('day', sa.Integer(), autoincrement=False, nullable=False),
    sa.Column('co2_mmhg', sa.Numeric(precision=7, scale=4), nullable=False),
    sa.Column('source', sa.String(length=20), nullable=False),
    sa.CheckConstraint("source IN ('synthetic','osdr')", name=op.f('CK_ortam_source_valid')),
    sa.CheckConstraint('co2_mmhg BETWEEN 0 AND 15', name=op.f('CK_ortam_co2_range')),
    sa.ForeignKeyConstraint(['mission_id'], ['core.Missions.mission_id'], name=op.f('FK_ortam_mission_id')),
    sa.PrimaryKeyConstraint('mission_id', 'day', name=op.f('PK_ortam')),
    schema='sans'
    )
    op.create_table('MeasurementRecords',
    sa.Column('record_id', sa.Uuid(), nullable=False),
    sa.Column('measurement_code', sa.String(length=60), nullable=False),
    sa.Column('eye_code', sa.CHAR(length=2), nullable=False),
    sa.Column('value_num', sa.Numeric(precision=18, scale=6), nullable=True),
    sa.Column('value_text', sa.Unicode(length=256), nullable=True),
    sa.Column('valid', sa.Boolean(), nullable=False),
    sa.Column('quality_score', sa.Numeric(precision=7, scale=6), nullable=True),
    sa.Column('metadata_json', sa.UnicodeText(), nullable=True),
    sa.Column('astronaut_id', sa.Unicode(length=32), nullable=False),
    sa.Column('client_request_id', sa.Uuid(), nullable=False),
    sa.Column('measured_date', sa.Date(), nullable=False),
    sa.Column('measured_at', mssql.DATETIME2(precision=3), nullable=True),
    sa.Column('time_precision', sa.String(length=9), nullable=False),
    sa.Column('mission_day', sa.Integer(), nullable=True),
    sa.Column('source', sa.String(length=20), nullable=False),
    sa.Column('created_at', mssql.DATETIME2(precision=3), server_default=sa.text('SYSUTCDATETIME()'), nullable=False),
    sa.CheckConstraint("(time_precision='date' AND measured_at IS NULL) OR (time_precision='timestamp' AND measured_at IS NOT NULL AND measured_date=CONVERT(date,measured_at))", name=op.f('CK_MeasurementRecords_time_precision')),
    sa.CheckConstraint("eye_code IN ('OD','OS','NA')", name=op.f('CK_MeasurementRecords_eye_code_valid')),
    sa.CheckConstraint("eye_code='NA'", name=op.f('CK_MeasurementRecords_eye_code_na')),
    sa.CheckConstraint("source IN ('manual','synthetic')", name=op.f('CK_MeasurementRecords_source_valid')),
    sa.CheckConstraint('metadata_json IS NULL OR ISJSON(metadata_json)=1', name=op.f('CK_MeasurementRecords_metadata_json')),
    sa.CheckConstraint('quality_score IS NULL OR quality_score BETWEEN 0 AND 1', name=op.f('CK_MeasurementRecords_quality_score_range')),
    sa.CheckConstraint('valid=0 OR value_num IS NOT NULL OR value_text IS NOT NULL', name=op.f('CK_MeasurementRecords_valid_has_value')),
    sa.CheckConstraint('value_num IS NULL OR value_text IS NULL', name=op.f('CK_MeasurementRecords_single_value')),
    sa.ForeignKeyConstraint(['astronaut_id'], ['core.Astronauts.astronaut_id'], name=op.f('FK_MeasurementRecords_astronaut_id')),
    sa.ForeignKeyConstraint(['measurement_code'], ['anomaly.MeasurementDefinitions.measurement_code'], name=op.f('FK_MeasurementRecords_measurement_code')),
    sa.PrimaryKeyConstraint('record_id', name=op.f('PK_MeasurementRecords')),
    sa.UniqueConstraint('astronaut_id', 'client_request_id', name=op.f('UQ_MeasurementRecords_astronaut_id_client_request_id')),
    schema='anomaly'
    )
    op.create_table('anomaly_results',
    sa.Column('id', sa.Uuid(), nullable=False),
    sa.Column('astronaut_id', sa.Unicode(length=32), nullable=False),
    sa.Column('mission_day', sa.Integer(), nullable=True),
    sa.Column('created_at', mssql.DATETIME2(precision=3), server_default=sa.text('SYSUTCDATETIME()'), nullable=False),
    sa.Column('module_scope', sa.String(length=24), nullable=False),
    sa.Column('measurement', sa.String(length=60), nullable=True),
    sa.Column('eye', sa.CHAR(length=2), nullable=True),
    sa.Column('algorithm', sa.String(length=40), nullable=False),
    sa.Column('model_version', sa.Unicode(length=100), nullable=True),
    sa.Column('anomaly_score', sa.Float(precision=53), nullable=True),
    sa.Column('is_anomaly', sa.Boolean(), nullable=False),
    sa.Column('level', sa.String(length=40), nullable=False),
    sa.Column('summary', sa.Unicode(length=4000), nullable=False),
    sa.Column('drivers_json', sa.UnicodeText(), nullable=False),
    sa.Column('baseline_status', sa.String(length=40), nullable=False),
    sa.Column('data_quality_status', sa.String(length=40), nullable=False),
    sa.Column('recommendation', sa.Unicode(length=2000), nullable=False),
    sa.Column('data_cutoff_at', mssql.DATETIME2(precision=3), nullable=False),
    sa.CheckConstraint("baseline_status IN ('insufficient_data','provisional','ready')", name=op.f('CK_anomaly_results_baseline_status_valid')),
    sa.CheckConstraint("data_quality_status IN ('valid','low_quality','missing_data')", name=op.f('CK_anomaly_results_data_quality_status_valid')),
    sa.CheckConstraint("eye IS NULL OR eye IN ('OD','OS')", name=op.f('CK_anomaly_results_eye_valid')),
    sa.CheckConstraint("level IN ('normal','watch','review')", name=op.f('CK_anomaly_results_level_valid')),
    sa.CheckConstraint("module_scope IN ('physiological','behavioral','sans','combined')", name=op.f('CK_anomaly_results_module_scope_valid')),
    sa.CheckConstraint('ISJSON(drivers_json)=1', name=op.f('CK_anomaly_results_drivers_json')),
    sa.CheckConstraint('data_cutoff_at <= created_at', name=op.f('CK_anomaly_results_cutoff_before_created')),
    sa.ForeignKeyConstraint(['astronaut_id'], ['core.Astronauts.astronaut_id'], name=op.f('FK_anomaly_results_astronaut_id')),
    sa.ForeignKeyConstraint(['measurement'], ['anomaly.MeasurementDefinitions.measurement_code'], name=op.f('FK_anomaly_results_measurement')),
    sa.PrimaryKeyConstraint('id', name=op.f('PK_anomaly_results')),
    schema='anomaly'
    )
    op.create_table('oturum',
    sa.Column('session_id', sa.Unicode(length=64), nullable=False),
    sa.Column('astronaut_id', sa.Unicode(length=32), nullable=False),
    sa.Column('date', sa.Date(), nullable=False),
    sa.Column('flight_day', sa.Integer(), nullable=False),
    sa.Column('is_retest', sa.Boolean(), nullable=False),
    sa.Column('retest_of', sa.Unicode(length=64), nullable=True),
    sa.Column('quality_score', sa.Numeric(precision=7, scale=6), nullable=False),
    sa.Column('checklist_json', sa.UnicodeText(), nullable=True),
    sa.Column('source', sa.String(length=20), nullable=False),
    sa.CheckConstraint("source IN ('synthetic','test_screen','manual')", name=op.f('CK_oturum_source_valid')),
    sa.CheckConstraint('(is_retest=0 AND retest_of IS NULL) OR (is_retest=1 AND retest_of IS NOT NULL AND retest_of<>session_id)', name=op.f('CK_oturum_retest_link')),
    sa.CheckConstraint('checklist_json IS NULL OR ISJSON(checklist_json)=1', name=op.f('CK_oturum_checklist_json')),
    sa.CheckConstraint('quality_score BETWEEN 0 AND 1', name=op.f('CK_oturum_quality_score_range')),
    sa.ForeignKeyConstraint(['astronaut_id'], ['core.Astronauts.astronaut_id'], name=op.f('FK_oturum_astronaut_id')),
    sa.ForeignKeyConstraint(['retest_of'], ['sans.oturum.session_id'], name=op.f('FK_oturum_retest_of')),
    sa.PrimaryKeyConstraint('session_id', name=op.f('PK_oturum')),
    schema='sans'
    )
    op.create_table('semptom',
    sa.Column('astronaut_id', sa.Unicode(length=32), nullable=False),
    sa.Column('flight_day', sa.Integer(), autoincrement=False, nullable=False),
    sa.Column('headache', sa.Boolean(), nullable=False),
    sa.ForeignKeyConstraint(['astronaut_id'], ['core.Astronauts.astronaut_id'], name=op.f('FK_semptom_astronaut_id')),
    sa.PrimaryKeyConstraint('astronaut_id', 'flight_day', name=op.f('PK_semptom')),
    schema='sans'
    )
    op.create_table('analiz',
    sa.Column('analysis_id', sa.Integer(), autoincrement=True, nullable=False),
    sa.Column('astronaut_id', sa.Unicode(length=32), nullable=False),
    sa.Column('session_id', sa.Unicode(length=64), nullable=True),
    sa.Column('flight_day', sa.Integer(), nullable=False),
    sa.Column('created_at', mssql.DATETIME2(precision=3), nullable=False),
    sa.Column('module', sa.String(length=24), nullable=False),
    sa.Column('risk', sa.Numeric(precision=7, scale=6), nullable=False),
    sa.Column('level', sa.String(length=10), nullable=False),
    sa.Column('state', sa.String(length=12), nullable=False),
    sa.Column('summary', sa.Unicode(length=4000), nullable=True),
    sa.Column('recommendation', sa.Unicode(length=2000), nullable=True),
    sa.Column('drivers_json', sa.UnicodeText(), nullable=True),
    sa.Column('trend_json', sa.UnicodeText(), nullable=True),
    sa.Column('model_version', sa.Unicode(length=100), nullable=True),
    sa.CheckConstraint("level IN ('green','yellow','red')", name=op.f('CK_analiz_level_valid')),
    sa.CheckConstraint("module='sans'", name=op.f('CK_analiz_module_sans')),
    sa.CheckConstraint("state IN ('normal','suspect','confirmed')", name=op.f('CK_analiz_state_valid')),
    sa.CheckConstraint('drivers_json IS NULL OR ISJSON(drivers_json)=1', name=op.f('CK_analiz_drivers_json')),
    sa.CheckConstraint('risk BETWEEN 0 AND 1', name=op.f('CK_analiz_risk_range')),
    sa.CheckConstraint('trend_json IS NULL OR ISJSON(trend_json)=1', name=op.f('CK_analiz_trend_json')),
    sa.ForeignKeyConstraint(['astronaut_id'], ['core.Astronauts.astronaut_id'], name=op.f('FK_analiz_astronaut_id')),
    sa.ForeignKeyConstraint(['session_id'], ['sans.oturum.session_id'], name=op.f('FK_analiz_session_id')),
    sa.PrimaryKeyConstraint('analysis_id', name=op.f('PK_analiz')),
    schema='sans'
    )
    op.create_table('test_kaydi',
    sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
    sa.Column('session_id', sa.Unicode(length=64), nullable=False),
    sa.Column('astronaut_id', sa.Unicode(length=32), nullable=False),
    sa.Column('flight_day', sa.Integer(), nullable=False),
    sa.Column('eye', sa.CHAR(length=2), nullable=False),
    sa.Column('test', sa.String(length=20), nullable=False),
    sa.Column('value', sa.Numeric(precision=18, scale=6), nullable=False),
    sa.Column('unit', sa.String(length=10), nullable=False),
    sa.Column('amsler_cells', sa.UnicodeText(), nullable=True),
    sa.Column('n_correct', sa.Integer(), nullable=True),
    sa.Column('n_presented', sa.Integer(), nullable=True),
    sa.Column('duration_s', sa.Numeric(precision=12, scale=3), nullable=True),
    sa.CheckConstraint("(test='near_acuity' AND unit='logMAR') OR (test='contrast' AND unit='logCS') OR (test='amsler' AND unit='cells')", name=op.f('CK_test_kaydi_test_unit')),
    sa.CheckConstraint("eye IN ('OD','OS')", name=op.f('CK_test_kaydi_eye_valid')),
    sa.CheckConstraint('(n_correct IS NULL AND n_presented IS NULL) OR (n_correct IS NOT NULL AND n_presented IS NOT NULL AND n_correct>=0 AND n_correct<=n_presented)', name=op.f('CK_test_kaydi_counts')),
    sa.CheckConstraint('amsler_cells IS NULL OR ISJSON(amsler_cells)=1', name=op.f('CK_test_kaydi_amsler_cells_json')),
    sa.CheckConstraint('duration_s IS NULL OR duration_s>=0', name=op.f('CK_test_kaydi_duration_nonneg')),
    sa.ForeignKeyConstraint(['astronaut_id'], ['core.Astronauts.astronaut_id'], name=op.f('FK_test_kaydi_astronaut_id')),
    sa.ForeignKeyConstraint(['session_id'], ['sans.oturum.session_id'], name=op.f('FK_test_kaydi_session_id')),
    sa.PrimaryKeyConstraint('id', name=op.f('PK_test_kaydi')),
    sa.UniqueConstraint('session_id', 'eye', 'test', name=op.f('UQ_test_kaydi_session_id_eye_test')),
    schema='sans'
    )
    op.create_table('durum',
    sa.Column('astronaut_id', sa.Unicode(length=32), nullable=False),
    sa.Column('state', sa.String(length=12), nullable=False),
    sa.Column('since_flight_day', sa.Integer(), nullable=False),
    sa.Column('retest_due_day', sa.Integer(), nullable=True),
    sa.Column('last_analysis_id', sa.Integer(), nullable=True),
    sa.CheckConstraint("state IN ('normal','suspect','confirmed')", name=op.f('CK_durum_state_valid')),
    sa.ForeignKeyConstraint(['astronaut_id'], ['core.Astronauts.astronaut_id'], name=op.f('FK_durum_astronaut_id')),
    sa.ForeignKeyConstraint(['last_analysis_id'], ['sans.analiz.analysis_id'], name=op.f('FK_durum_last_analysis_id')),
    sa.PrimaryKeyConstraint('astronaut_id', name=op.f('PK_durum')),
    schema='sans'
    )

    for obj, perms in APP_PERMS.items():
        grant(obj, APP_ROLE, perms)


def downgrade() -> None:
    for obj, perms in APP_PERMS.items():
        revoke(obj, APP_ROLE, perms)
    op.drop_table("durum", schema="sans")
    op.drop_table("test_kaydi", schema="sans")
    op.drop_table("analiz", schema="sans")
    op.drop_table("semptom", schema="sans")
    op.drop_table("oturum", schema="sans")
    op.drop_table("anomaly_results", schema="anomaly")
    op.drop_table("MeasurementRecords", schema="anomaly")
    op.drop_table("ortam", schema="sans")
    op.drop_table("MeasurementDefinitions", schema="anomaly")
