"""A4: behavioral (checkins, weekly_assessments, cognitive_tests) + evaluation.gercek_durum

Gövde modellerden Alembic autogenerate ile üretildi; tests/unit/test_migrations.py modelle
birebir aynı olduğunu doğrular. Elle eklenenler: grant()/revoke() satırları.

İzinler:
- astra_app_role: check-in güncellenebilir (PUT); haftalık ölçek ve bilişsel test yalnız eklenir.
- astra_eval_role: yalnız evaluation.gercek_durum (SELECT/INSERT/UPDATE). Operasyonel tablolara
  erişimi yoktur.
- astra_app_role evaluation şemasına A0'daki açık DENY ile erişemez; burada izin VERİLMEZ.
DELETE hiçbir rolde yok.

Revision ID: 0005
Revises: 0004
"""
import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import mssql

from migrations.helpers import APP_ROLE, EVAL_ROLE, grant, revoke

revision = "0005"
down_revision = "0004"
branch_labels = None
depends_on = None

APP_PERMS = {
    "behavioral.checkins": "SELECT, INSERT, UPDATE",
    "behavioral.weekly_assessments": "SELECT, INSERT",
    "behavioral.cognitive_tests": "SELECT, INSERT",
}
EVAL_PERMS = {
    "evaluation.gercek_durum": "SELECT, INSERT, UPDATE",
}


def upgrade() -> None:
    op.create_table('gercek_durum',
    sa.Column('astronaut_id', sa.Unicode(length=32), nullable=False),
    sa.Column('sans_label', sa.Boolean(), nullable=False),
    sa.Column('onset_day', sa.Integer(), nullable=True),
    sa.Column('s_max', sa.Float(precision=53), nullable=True),
    sa.Column('tau_days', sa.Float(precision=53), nullable=True),
    sa.Column('eye_pattern', sa.String(length=12), nullable=True),
    sa.Column('dominant_eye', sa.CHAR(length=2), nullable=True),
    sa.Column('d_max', sa.Float(precision=53), nullable=True),
    sa.Column('k', sa.Float(precision=53), nullable=True),
    sa.Column('c', sa.Float(precision=53), nullable=True),
    sa.Column('m', sa.Float(precision=53), nullable=True),
    sa.Column('oct_detect_day', sa.Integer(), nullable=True),
    sa.PrimaryKeyConstraint('astronaut_id', name=op.f('PK_gercek_durum')),
    schema='evaluation'
    )
    op.create_table('checkins',
    sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
    sa.Column('date', sa.Date(), nullable=False),
    sa.Column('mission_day', sa.Integer(), nullable=False),
    sa.Column('mood', sa.Integer(), nullable=False),
    sa.Column('energy', sa.Integer(), nullable=False),
    sa.Column('stress', sa.Integer(), nullable=False),
    sa.Column('loneliness', sa.Integer(), nullable=False),
    sa.Column('crew', sa.Integer(), nullable=False),
    sa.Column('mood_index', sa.Float(precision=53), nullable=False),
    sa.Column('bed_time', mssql.TIME(precision=0), nullable=False),
    sa.Column('wake_time', mssql.TIME(precision=0), nullable=False),
    sa.Column('sleep_hours', sa.Float(precision=53), nullable=False),
    sa.Column('sleep_quality', sa.Integer(), nullable=False),
    sa.Column('symptoms', sa.UnicodeText(), nullable=True),
    sa.Column('source', sa.Unicode(length=200), nullable=False),
    sa.Column('created_at', mssql.DATETIME2(precision=3), nullable=False),
    sa.Column('updated_at', mssql.DATETIME2(precision=3), nullable=False),
    sa.Column('astronaut_id', sa.Unicode(length=32), nullable=False),
    sa.CheckConstraint("source IN ('manual','seed')", name=op.f('CK_checkins_source_valid')),
    sa.CheckConstraint('crew BETWEEN 0 AND 4', name=op.f('CK_checkins_crew_range')),
    sa.CheckConstraint('energy BETWEEN 0 AND 10', name=op.f('CK_checkins_energy_range')),
    sa.CheckConstraint('loneliness BETWEEN 0 AND 4', name=op.f('CK_checkins_loneliness_range')),
    sa.CheckConstraint('mood BETWEEN 0 AND 10', name=op.f('CK_checkins_mood_range')),
    sa.CheckConstraint('mood_index BETWEEN 0 AND 100', name=op.f('CK_checkins_mood_index_range')),
    sa.CheckConstraint('sleep_hours >= 0', name=op.f('CK_checkins_sleep_hours_nonneg')),
    sa.CheckConstraint('sleep_quality BETWEEN 1 AND 5', name=op.f('CK_checkins_sleep_quality_range')),
    sa.CheckConstraint('stress BETWEEN 0 AND 10', name=op.f('CK_checkins_stress_range')),
    sa.CheckConstraint('symptoms IS NULL OR ISJSON(symptoms)=1', name=op.f('CK_checkins_symptoms_json')),
    sa.ForeignKeyConstraint(['astronaut_id'], ['core.Astronauts.astronaut_id'], name=op.f('FK_checkins_astronaut_id')),
    sa.PrimaryKeyConstraint('id', name=op.f('PK_checkins')),
    sa.UniqueConstraint('astronaut_id', 'date', name=op.f('UQ_checkins_astronaut_id_date')),
    schema='behavioral'
    )
    op.create_table('cognitive_tests',
    sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
    sa.Column('taken_at', mssql.DATETIME2(precision=3), nullable=False),
    sa.Column('mission_day', sa.Integer(), nullable=False),
    sa.Column('test_type', sa.Unicode(length=200), nullable=False),
    sa.Column('duration_s', sa.Integer(), nullable=False),
    sa.Column('n_trials', sa.Integer(), nullable=False),
    sa.Column('mean_rt_ms', sa.Float(precision=53), nullable=True),
    sa.Column('median_rt_ms', sa.Float(precision=53), nullable=True),
    sa.Column('speed', sa.Float(precision=53), nullable=True),
    sa.Column('lapses', sa.Integer(), nullable=True),
    sa.Column('false_starts', sa.Integer(), nullable=True),
    sa.Column('accuracy', sa.Float(precision=53), nullable=True),
    sa.Column('correct_count', sa.Integer(), nullable=True),
    sa.Column('valid', sa.Boolean(), nullable=False),
    sa.Column('invalid_reason', sa.Unicode(length=500), nullable=True),
    sa.Column('device', sa.Unicode(length=200), nullable=False),
    sa.Column('raw', sa.UnicodeText(), nullable=False),
    sa.Column('source', sa.Unicode(length=200), nullable=False),
    sa.Column('astronaut_id', sa.Unicode(length=32), nullable=False),
    sa.Column('client_request_id', sa.Uuid(), nullable=False),
    sa.CheckConstraint("(test_type='pvt' AND accuracy IS NULL AND correct_count IS NULL) OR (test_type='rotation' AND median_rt_ms IS NULL AND speed IS NULL AND lapses IS NULL AND false_starts IS NULL AND correct_count IS NULL) OR (test_type='dsst' AND mean_rt_ms IS NULL AND median_rt_ms IS NULL AND speed IS NULL AND lapses IS NULL AND false_starts IS NULL)", name=op.f('CK_cognitive_tests_metrics_by_type')),
    sa.CheckConstraint("test_type IN ('pvt','rotation','dsst')", name=op.f('CK_cognitive_tests_test_type_valid')),
    sa.CheckConstraint('(valid=1 AND invalid_reason IS NULL) OR (valid=0 AND invalid_reason IS NOT NULL)', name=op.f('CK_cognitive_tests_invalid_reason')),
    sa.CheckConstraint('ISJSON(raw)=1', name=op.f('CK_cognitive_tests_raw_json')),
    sa.CheckConstraint('accuracy IS NULL OR accuracy BETWEEN 0 AND 1', name=op.f('CK_cognitive_tests_accuracy_range')),
    sa.CheckConstraint('duration_s > 0 AND n_trials >= 0', name=op.f('CK_cognitive_tests_duration_trials')),
    sa.ForeignKeyConstraint(['astronaut_id'], ['core.Astronauts.astronaut_id'], name=op.f('FK_cognitive_tests_astronaut_id')),
    sa.PrimaryKeyConstraint('id', name=op.f('PK_cognitive_tests')),
    sa.UniqueConstraint('astronaut_id', 'client_request_id', name=op.f('UQ_cognitive_tests_astronaut_id_client_request_id')),
    schema='behavioral'
    )
    op.create_table('weekly_assessments',
    sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
    sa.Column('taken_at', mssql.DATETIME2(precision=3), nullable=False),
    sa.Column('mission_day', sa.Integer(), nullable=False),
    sa.Column('answers', sa.UnicodeText(), nullable=False),
    sa.Column('who5_score', sa.Integer(), nullable=False),
    sa.Column('phq2_score', sa.Integer(), nullable=False),
    sa.Column('gad2_score', sa.Integer(), nullable=False),
    sa.Column('share_with_crew_medical', sa.Boolean(), server_default=sa.text('0'), nullable=False),
    sa.Column('source', sa.Unicode(length=200), nullable=False),
    sa.Column('astronaut_id', sa.Unicode(length=32), nullable=False),
    sa.Column('client_request_id', sa.Uuid(), nullable=False),
    sa.CheckConstraint('ISJSON(answers)=1', name=op.f('CK_weekly_assessments_answers_json')),
    sa.CheckConstraint('gad2_score BETWEEN 0 AND 6', name=op.f('CK_weekly_assessments_gad2_range')),
    sa.CheckConstraint('phq2_score BETWEEN 0 AND 6', name=op.f('CK_weekly_assessments_phq2_range')),
    sa.CheckConstraint('who5_score BETWEEN 0 AND 100', name=op.f('CK_weekly_assessments_who5_range')),
    sa.ForeignKeyConstraint(['astronaut_id'], ['core.Astronauts.astronaut_id'], name=op.f('FK_weekly_assessments_astronaut_id')),
    sa.PrimaryKeyConstraint('id', name=op.f('PK_weekly_assessments')),
    sa.UniqueConstraint('astronaut_id', 'client_request_id', name=op.f('UQ_weekly_assessments_astronaut_id_client_request_id')),
    schema='behavioral'
    )

    for obj, perms in APP_PERMS.items():
        grant(obj, APP_ROLE, perms)
    for obj, perms in EVAL_PERMS.items():
        grant(obj, EVAL_ROLE, perms)


def downgrade() -> None:
    for obj, perms in EVAL_PERMS.items():
        revoke(obj, EVAL_ROLE, perms)
    for obj, perms in APP_PERMS.items():
        revoke(obj, APP_ROLE, perms)
    op.drop_table("weekly_assessments", schema="behavioral")
    op.drop_table("cognitive_tests", schema="behavioral")
    op.drop_table("checkins", schema="behavioral")
    op.drop_table("gercek_durum", schema="evaluation")
