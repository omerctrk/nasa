"""A3: ops.AnalysisJobs, ops.Alerts, ops.NotificationEvents, ops.EventReceipts

Gövde modellerden Alembic autogenerate ile üretildi; tests/unit/test_migrations.py modelle
birebir aynı olduğunu doğrular. Elle eklenenler: grant()/revoke() satırları.

Şemaya göre farklar (contracts/backend-contract.md §11):
- AnalysisJobs.request_json (NVARCHAR(MAX), ISJSON): işçinin neyi analiz edeceği. ÖNERİ —
  Ömer onaylamazsa yeni bir migration ile kaldırılır.
- IX_AnalysisJobs_state_next_attempt_at: işçinin "sıradaki iş" sorgusu için performans
  indeksi; veri kuralı değildir.

astra_app_role izinleri: işler/alarmlar/olaylar durum değiştirdiği için SELECT/INSERT/UPDATE;
alındılar yalnız eklenir. DELETE yok. astra_eval_role ops'a erişmez.

Revision ID: 0004
Revises: 0003
"""
import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import mssql

from migrations.helpers import APP_ROLE, grant, revoke

revision = "0004"
down_revision = "0003"
branch_labels = None
depends_on = None

APP_PERMS = {
    "ops.AnalysisJobs": "SELECT, INSERT, UPDATE",
    "ops.Alerts": "SELECT, INSERT, UPDATE",
    "ops.NotificationEvents": "SELECT, INSERT, UPDATE",
    "ops.EventReceipts": "SELECT, INSERT",
}


def upgrade() -> None:
    op.create_table('Alerts',
    sa.Column('alert_id', sa.Uuid(), nullable=False),
    sa.Column('status', sa.String(length=40), server_default=sa.text("'OPEN'"), nullable=False),
    sa.Column('acknowledged_by', sa.Uuid(), nullable=True),
    sa.Column('acknowledged_at', mssql.DATETIME2(precision=3), nullable=True),
    sa.Column('resolved_by', sa.Uuid(), nullable=True),
    sa.Column('resolved_at', mssql.DATETIME2(precision=3), nullable=True),
    sa.Column('resolution_note', sa.Unicode(length=1000), nullable=True),
    sa.Column('created_at', mssql.DATETIME2(precision=3), server_default=sa.text('SYSUTCDATETIME()'), nullable=False),
    sa.Column('astronaut_id', sa.Unicode(length=32), nullable=False),
    sa.Column('module', sa.String(length=24), nullable=False),
    sa.Column('anomaly_result_id', sa.Uuid(), nullable=True),
    sa.Column('sans_analysis_id', sa.Integer(), nullable=True),
    sa.Column('severity', sa.String(length=10), nullable=False),
    sa.CheckConstraint("(module='anomaly' AND anomaly_result_id IS NOT NULL AND sans_analysis_id IS NULL) OR (module='sans' AND sans_analysis_id IS NOT NULL AND anomaly_result_id IS NULL)", name=op.f('CK_Alerts_source_by_module')),
    sa.CheckConstraint("(status<>'RESOLVED' AND resolved_by IS NULL AND resolved_at IS NULL AND resolution_note IS NULL) OR (status='RESOLVED' AND resolved_by IS NOT NULL AND resolved_at IS NOT NULL AND resolved_at >= acknowledged_at AND resolution_note IS NOT NULL AND LEN(LTRIM(RTRIM(resolution_note)))>0)", name=op.f('CK_Alerts_resolve_by_status')),
    sa.CheckConstraint("(status='OPEN' AND acknowledged_by IS NULL AND acknowledged_at IS NULL) OR (status IN ('ACKNOWLEDGED','RESOLVED') AND acknowledged_by IS NOT NULL AND acknowledged_at IS NOT NULL)", name=op.f('CK_Alerts_ack_by_status')),
    sa.CheckConstraint("severity IN ('WARNING','CRITICAL')", name=op.f('CK_Alerts_severity_valid')),
    sa.CheckConstraint("status IN ('OPEN','ACKNOWLEDGED','RESOLVED')", name=op.f('CK_Alerts_status_valid')),
    sa.ForeignKeyConstraint(['acknowledged_by'], ['core.Users.user_id'], name=op.f('FK_Alerts_acknowledged_by')),
    sa.ForeignKeyConstraint(['anomaly_result_id'], ['anomaly.anomaly_results.id'], name=op.f('FK_Alerts_anomaly_result_id')),
    sa.ForeignKeyConstraint(['astronaut_id'], ['core.Astronauts.astronaut_id'], name=op.f('FK_Alerts_astronaut_id')),
    sa.ForeignKeyConstraint(['resolved_by'], ['core.Users.user_id'], name=op.f('FK_Alerts_resolved_by')),
    sa.ForeignKeyConstraint(['sans_analysis_id'], ['sans.analiz.analysis_id'], name=op.f('FK_Alerts_sans_analysis_id')),
    sa.PrimaryKeyConstraint('alert_id', name=op.f('PK_Alerts')),
    schema='ops'
    )
    op.create_index('UQ_Alerts_anomaly_result_id', 'Alerts', ['anomaly_result_id'], unique=True, schema='ops', mssql_where=sa.text('anomaly_result_id IS NOT NULL'))
    op.create_index('UQ_Alerts_sans_analysis_id', 'Alerts', ['sans_analysis_id'], unique=True, schema='ops', mssql_where=sa.text('sans_analysis_id IS NOT NULL'))
    op.create_table('AnalysisJobs',
    sa.Column('job_id', sa.Uuid(), nullable=False),
    sa.Column('idempotency_key', sa.Uuid(), nullable=False),
    sa.Column('request_hash', sa.CHAR(length=64), nullable=False),
    sa.Column('module', sa.String(length=24), nullable=False),
    sa.Column('state', sa.String(length=40), server_default=sa.text("'QUEUED'"), nullable=False),
    sa.Column('request_json', sa.UnicodeText(), nullable=False),
    sa.Column('input_snapshot_json', sa.UnicodeText(), nullable=True),
    sa.Column('input_hash', sa.CHAR(length=64), nullable=True),
    sa.Column('provider_metadata_json', sa.UnicodeText(), nullable=True),
    sa.Column('lease_token', sa.Uuid(), nullable=True),
    sa.Column('lease_until', mssql.DATETIME2(precision=3), nullable=True),
    sa.Column('attempts', sa.Integer(), server_default=sa.text('0'), nullable=False),
    sa.Column('retry_cycle', sa.Integer(), server_default=sa.text('0'), nullable=False),
    sa.Column('next_attempt_at', mssql.DATETIME2(precision=3), server_default=sa.text('SYSUTCDATETIME()'), nullable=False),
    sa.Column('evaluation_status', sa.String(length=40), nullable=True),
    sa.Column('outcome_json', sa.UnicodeText(), nullable=True),
    sa.Column('error_code', sa.String(length=40), nullable=True),
    sa.Column('created_at', mssql.DATETIME2(precision=3), server_default=sa.text('SYSUTCDATETIME()'), nullable=False),
    sa.Column('updated_at', mssql.DATETIME2(precision=3), server_default=sa.text('SYSUTCDATETIME()'), nullable=False),
    sa.Column('astronaut_id', sa.Unicode(length=32), nullable=False),
    sa.Column('anomaly_result_id', sa.Uuid(), nullable=True),
    sa.Column('sans_analysis_id', sa.Integer(), nullable=True),
    sa.CheckConstraint("(module='anomaly' AND sans_analysis_id IS NULL) OR (module='sans' AND anomaly_result_id IS NULL)", name=op.f('CK_AnalysisJobs_result_by_module')),
    sa.CheckConstraint("(state IN ('SYNCING','ANALYZING') AND lease_token IS NOT NULL AND lease_until IS NOT NULL) OR (state NOT IN ('SYNCING','ANALYZING') AND lease_token IS NULL AND lease_until IS NULL)", name=op.f('CK_AnalysisJobs_lease_by_state')),
    sa.CheckConstraint("evaluation_status IS NULL OR evaluation_status IN ('evaluated','insufficient_data','invalid_data')", name=op.f('CK_AnalysisJobs_evaluation_status_valid')),
    sa.CheckConstraint("module IN ('anomaly','sans')", name=op.f('CK_AnalysisJobs_module_valid')),
    sa.CheckConstraint("state IN ('QUEUED','SYNCING','ANALYZING','COMPLETED','FAILED')", name=op.f('CK_AnalysisJobs_state_valid')),
    sa.CheckConstraint('ISJSON(request_json)=1', name=op.f('CK_AnalysisJobs_request_json')),
    sa.CheckConstraint('attempts >= 0 AND retry_cycle >= 0', name=op.f('CK_AnalysisJobs_counters_nonneg')),
    sa.CheckConstraint('input_snapshot_json IS NULL OR ISJSON(input_snapshot_json)=1', name=op.f('CK_AnalysisJobs_snapshot_json')),
    sa.CheckConstraint('outcome_json IS NULL OR ISJSON(outcome_json)=1', name=op.f('CK_AnalysisJobs_outcome_json')),
    sa.CheckConstraint('provider_metadata_json IS NULL OR ISJSON(provider_metadata_json)=1', name=op.f('CK_AnalysisJobs_provider_metadata_json')),
    sa.ForeignKeyConstraint(['anomaly_result_id'], ['anomaly.anomaly_results.id'], name=op.f('FK_AnalysisJobs_anomaly_result_id')),
    sa.ForeignKeyConstraint(['astronaut_id'], ['core.Astronauts.astronaut_id'], name=op.f('FK_AnalysisJobs_astronaut_id')),
    sa.ForeignKeyConstraint(['sans_analysis_id'], ['sans.analiz.analysis_id'], name=op.f('FK_AnalysisJobs_sans_analysis_id')),
    sa.PrimaryKeyConstraint('job_id', name=op.f('PK_AnalysisJobs')),
    sa.UniqueConstraint('astronaut_id', 'idempotency_key', name=op.f('UQ_AnalysisJobs_astronaut_id_idempotency_key')),
    schema='ops'
    )
    op.create_index('IX_AnalysisJobs_state_next_attempt_at', 'AnalysisJobs', ['state', 'next_attempt_at'], unique=False, schema='ops')
    op.create_table('NotificationEvents',
    sa.Column('event_id', sa.Uuid(), nullable=False),
    sa.Column('job_id', sa.Uuid(), nullable=True),
    sa.Column('alert_id', sa.Uuid(), nullable=True),
    sa.Column('event_type', sa.String(length=40), nullable=False),
    sa.Column('audience', sa.String(length=40), nullable=False),
    sa.Column('target_user_id', sa.Uuid(), nullable=True),
    sa.Column('payload_json', sa.UnicodeText(), nullable=False),
    sa.Column('created_at', mssql.DATETIME2(precision=3), server_default=sa.text('SYSUTCDATETIME()'), nullable=False),
    sa.Column('first_sent_at', mssql.DATETIME2(precision=3), nullable=True),
    sa.Column('received_at', mssql.DATETIME2(precision=3), nullable=True),
    sa.Column('next_attempt_at', mssql.DATETIME2(precision=3), server_default=sa.text('SYSUTCDATETIME()'), nullable=False),
    sa.Column('attempts', sa.Integer(), server_default=sa.text('0'), nullable=False),
    sa.CheckConstraint("(audience='ASTRONAUT' AND target_user_id IS NOT NULL) OR (audience='GROUND_CONTROL' AND target_user_id IS NULL)", name=op.f('CK_NotificationEvents_target_by_audience')),
    sa.CheckConstraint("(event_type='risk.alert.created' AND alert_id IS NOT NULL) OR (event_type='analysis.completed' AND job_id IS NOT NULL)", name=op.f('CK_NotificationEvents_subject_by_type')),
    sa.CheckConstraint("audience <> 'GROUND_CONTROL' OR event_type='risk.alert.created'", name=op.f('CK_NotificationEvents_ground_only_risk')),
    sa.CheckConstraint("audience IN ('ASTRONAUT','GROUND_CONTROL')", name=op.f('CK_NotificationEvents_audience_valid')),
    sa.CheckConstraint("event_type IN ('analysis.completed','risk.alert.created')", name=op.f('CK_NotificationEvents_event_type_valid')),
    sa.CheckConstraint('(job_id IS NOT NULL AND alert_id IS NULL) OR (job_id IS NULL AND alert_id IS NOT NULL)', name=op.f('CK_NotificationEvents_subject_xor')),
    sa.CheckConstraint('ISJSON(payload_json)=1', name=op.f('CK_NotificationEvents_payload_json')),
    sa.CheckConstraint('attempts >= 0', name=op.f('CK_NotificationEvents_attempts_nonneg')),
    sa.ForeignKeyConstraint(['alert_id'], ['ops.Alerts.alert_id'], name=op.f('FK_NotificationEvents_alert_id')),
    sa.ForeignKeyConstraint(['job_id'], ['ops.AnalysisJobs.job_id'], name=op.f('FK_NotificationEvents_job_id')),
    sa.ForeignKeyConstraint(['target_user_id'], ['core.Users.user_id'], name=op.f('FK_NotificationEvents_target_user_id')),
    sa.PrimaryKeyConstraint('event_id', name=op.f('PK_NotificationEvents')),
    schema='ops'
    )
    op.create_index('UQ_NotificationEvents_alert_id_audience', 'NotificationEvents', ['alert_id', 'audience'], unique=True, schema='ops', mssql_where=sa.text('alert_id IS NOT NULL'))
    op.create_index('UQ_NotificationEvents_job_id_audience', 'NotificationEvents', ['job_id', 'audience'], unique=True, schema='ops', mssql_where=sa.text('job_id IS NOT NULL'))
    op.create_table('EventReceipts',
    sa.Column('event_id', sa.Uuid(), nullable=False),
    sa.Column('user_id', sa.Uuid(), nullable=False),
    sa.Column('received_at', mssql.DATETIME2(precision=3), server_default=sa.text('SYSUTCDATETIME()'), nullable=False),
    sa.ForeignKeyConstraint(['event_id'], ['ops.NotificationEvents.event_id'], name=op.f('FK_EventReceipts_event_id')),
    sa.ForeignKeyConstraint(['user_id'], ['core.Users.user_id'], name=op.f('FK_EventReceipts_user_id')),
    sa.PrimaryKeyConstraint('event_id', 'user_id', name=op.f('PK_EventReceipts')),
    schema='ops'
    )

    for obj, perms in APP_PERMS.items():
        grant(obj, APP_ROLE, perms)


def downgrade() -> None:
    for obj, perms in APP_PERMS.items():
        revoke(obj, APP_ROLE, perms)
    op.drop_table("EventReceipts", schema="ops")
    op.drop_index("UQ_NotificationEvents_alert_id_audience", table_name="NotificationEvents", schema="ops")
    op.drop_index("UQ_NotificationEvents_job_id_audience", table_name="NotificationEvents", schema="ops")
    op.drop_table("NotificationEvents", schema="ops")
    op.drop_index("IX_AnalysisJobs_state_next_attempt_at", table_name="AnalysisJobs", schema="ops")
    op.drop_table("AnalysisJobs", schema="ops")
    op.drop_index("UQ_Alerts_anomaly_result_id", table_name="Alerts", schema="ops")
    op.drop_index("UQ_Alerts_sans_analysis_id", table_name="Alerts", schema="ops")
    op.drop_table("Alerts", schema="ops")
