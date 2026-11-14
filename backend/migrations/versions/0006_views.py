"""A5: üç VIEW — sans.gorev, sans.profil, anomaly.v_measurements

VIEW'lar fiziksel tablo değildir (şema §4); veri kopyalanmaz. Hepsi dbo sahipliğindedir,
astra_app_role yalnız SELECT alır (sahiplik zinciriyle alttaki tablolara ayrıca izin gerekmez).

anomaly.v_measurements → ortak ölçüm DTO'su (contracts/backend-contract.md §3):
- physiological : anomaly.MeasurementRecords (+ sözlük)          record_id physiological:<uuid>
- behavioral    : behavioral.checkins, sayısal alanlar unpivot     record_id checkin:<id>:<metrik>
- behavioral    : behavioral.cognitive_tests, test türüne göre    record_id cognitive:<id>:<kod>
- sans          : sans.test_kaydi + sans.oturum (OD/OS ayrı)       record_id eye:<id>
Hariç: weekly_assessments (model girdisi değil), PVT speed (formül teyitsiz),
checkins.symptoms ve yatış/uyanış saatleri (sayısal ölçüm değil; kaynakta kalır).
Kaynak source=seed → synthetic, test_screen → manual; orijinal değer metadata_json.original_source.
Günlük kayıtlara saat eklenmez (time_precision=date, measured_at NULL); bilişsel testler
gerçek taken_at zamanını taşır (timestamp). protocol_version sözlükten gelir; sözlükte
tanımsız kod NULL döner ve repository bunu açık hata olarak bildirir (sessizce atlanmaz).

Gerekli: SQL Server 2022 (JSON_OBJECT).

Revision ID: 0006
Revises: 0005
"""
from alembic import op

from migrations.helpers import APP_ROLE, grant, revoke

revision = "0006"
down_revision = "0005"
branch_labels = None
depends_on = None

VIEWS = ("sans.gorev", "sans.profil", "anomaly.v_measurements")

SANS_GOREV = """
CREATE VIEW [sans].[gorev] AS
SELECT m.mission_id, m.name, m.scenario, m.start_date, m.length_days
FROM [core].[Missions] AS m
"""

SANS_PROFIL = """
CREATE VIEW [sans].[profil] AS
SELECT a.astronaut_id, a.mission_id, a.age, a.sex, a.weight_kg, a.prior_flight,
       a.prior_sans, a.mtrr66_g, a.shmt1_1420_c, a.b_vit_status, a.optic_cup_vol
FROM [core].[Astronauts] AS a
WHERE a.is_display_only = 0
"""

V_MEASUREMENTS = """
CREATE VIEW [anomaly].[v_measurements] AS
-- 1) Fizyolojik ölçümler
SELECT
    CAST(CONCAT('physiological:', LOWER(CONVERT(varchar(36), r.record_id))) AS varchar(200)) AS record_id,
    r.astronaut_id,
    a.mission_id,
    CAST('physiological' AS varchar(24))       AS module,
    CAST(r.measurement_code AS varchar(60))    AS measurement,
    CAST(r.value_num AS decimal(18,6))         AS value_num,
    CAST(r.value_text AS nvarchar(256))        AS value_text,
    CAST(d.canonical_unit AS nvarchar(32))     AS unit,
    CAST(d.protocol_version AS varchar(40))    AS protocol_version,
    r.measured_date,
    r.measured_at,
    CAST(r.time_precision AS varchar(9))       AS time_precision,
    r.mission_day,
    CAST(NULL AS char(2))                      AS eye,
    CAST(r.source AS varchar(20))              AS source,
    r.valid,
    CAST(r.quality_score AS decimal(7,6))      AS quality_score,
    CAST(NULL AS nvarchar(64))                 AS session_id,
    CAST(r.metadata_json AS nvarchar(max))     AS metadata_json
FROM [anomaly].[MeasurementRecords] AS r
JOIN [core].[Astronauts] AS a ON a.astronaut_id = r.astronaut_id
LEFT JOIN [anomaly].[MeasurementDefinitions] AS d ON d.measurement_code = r.measurement_code

UNION ALL
-- 2) Günlük check-in: sayısal alanlar ayrı ölçüm satırları
SELECT
    CAST(CONCAT('checkin:', c.id, ':', v.code) AS varchar(200)),
    c.astronaut_id,
    a.mission_id,
    CAST('behavioral' AS varchar(24)),
    CAST(v.code AS varchar(60)),
    v.value_num,
    CAST(NULL AS nvarchar(256)),
    CAST(d.canonical_unit AS nvarchar(32)),
    CAST(d.protocol_version AS varchar(40)),
    c.date,
    CAST(NULL AS datetime2(3)),
    CAST('date' AS varchar(9)),
    c.mission_day,
    CAST(NULL AS char(2)),
    CAST(CASE c.source WHEN 'seed' THEN 'synthetic' ELSE 'manual' END AS varchar(20)),
    CAST(1 AS bit),
    CAST(NULL AS decimal(7,6)),
    CAST(NULL AS nvarchar(64)),
    CAST(JSON_OBJECT('original_source': c.source) AS nvarchar(max))
FROM [behavioral].[checkins] AS c
JOIN [core].[Astronauts] AS a ON a.astronaut_id = c.astronaut_id
CROSS APPLY (VALUES
    ('mood',          CAST(c.mood AS decimal(18,6))),
    ('energy',        CAST(c.energy AS decimal(18,6))),
    ('stress',        CAST(c.stress AS decimal(18,6))),
    ('loneliness',    CAST(c.loneliness AS decimal(18,6))),
    ('crew',          CAST(c.crew AS decimal(18,6))),
    ('mood_index',    CAST(c.mood_index AS decimal(18,6))),
    ('sleep_hours',   CAST(c.sleep_hours AS decimal(18,6))),
    ('sleep_quality', CAST(c.sleep_quality AS decimal(18,6)))
) AS v(code, value_num)
LEFT JOIN [anomaly].[MeasurementDefinitions] AS d ON d.measurement_code = v.code

UNION ALL
-- 3) Bilişsel testler: yalnız test türüne uygulanan metrikler (PVT speed hariç)
SELECT
    CAST(CONCAT('cognitive:', t.id, ':', v.code) AS varchar(200)),
    t.astronaut_id,
    a.mission_id,
    CAST('behavioral' AS varchar(24)),
    CAST(v.code AS varchar(60)),
    v.value_num,
    CAST(NULL AS nvarchar(256)),
    CAST(d.canonical_unit AS nvarchar(32)),
    CAST(d.protocol_version AS varchar(40)),
    CONVERT(date, t.taken_at),
    t.taken_at,
    CAST('timestamp' AS varchar(9)),
    t.mission_day,
    CAST(NULL AS char(2)),
    CAST(CASE t.source WHEN 'seed' THEN 'synthetic' ELSE 'manual' END AS varchar(20)),
    t.valid,
    CAST(NULL AS decimal(7,6)),
    CAST(NULL AS nvarchar(64)),
    CAST(JSON_OBJECT('original_source': t.source, 'test_type': t.test_type,
                     'device': t.device, 'duration_s': t.duration_s, 'n_trials': t.n_trials,
                     'invalid_reason': t.invalid_reason ABSENT ON NULL) AS nvarchar(max))
FROM [behavioral].[cognitive_tests] AS t
JOIN [core].[Astronauts] AS a ON a.astronaut_id = t.astronaut_id
CROSS APPLY (VALUES
    ('pvt',      'pvt_mean_rt',        CAST(t.mean_rt_ms AS decimal(18,6))),
    ('pvt',      'pvt_median_rt',      CAST(t.median_rt_ms AS decimal(18,6))),
    ('pvt',      'pvt_lapses',         CAST(t.lapses AS decimal(18,6))),
    ('pvt',      'pvt_false_starts',   CAST(t.false_starts AS decimal(18,6))),
    ('rotation', 'rotation_mean_rt',   CAST(t.mean_rt_ms AS decimal(18,6))),
    ('rotation', 'rotation_accuracy',  CAST(t.accuracy AS decimal(18,6))),
    ('dsst',     'dsst_accuracy',      CAST(t.accuracy AS decimal(18,6))),
    ('dsst',     'dsst_correct_count', CAST(t.correct_count AS decimal(18,6)))
) AS v(test_type, code, value_num)
LEFT JOIN [anomaly].[MeasurementDefinitions] AS d ON d.measurement_code = v.code
WHERE v.test_type = t.test_type
  AND (v.value_num IS NOT NULL OR t.valid = 0)

UNION ALL
-- 4) Göz testleri: üç test × OD/OS; kalite/retest bilgisi oturumdan
SELECT
    CAST(CONCAT('eye:', k.id) AS varchar(200)),
    k.astronaut_id,
    a.mission_id,
    CAST('sans' AS varchar(24)),
    CAST(k.test AS varchar(60)),
    CAST(k.value AS decimal(18,6)),
    CAST(NULL AS nvarchar(256)),
    CAST(k.unit AS nvarchar(32)),
    CAST(d.protocol_version AS varchar(40)),
    o.date,
    CAST(NULL AS datetime2(3)),
    CAST('date' AS varchar(9)),
    o.flight_day,
    CAST(k.eye AS char(2)),
    CAST(CASE o.source WHEN 'synthetic' THEN 'synthetic' ELSE 'manual' END AS varchar(20)),
    CAST(1 AS bit),
    CAST(o.quality_score AS decimal(7,6)),
    CAST(o.session_id AS nvarchar(64)),
    CAST(JSON_OBJECT('original_source': o.source, 'is_retest': o.is_retest,
                     'retest_of': o.retest_of, 'checklist': JSON_QUERY(o.checklist_json),
                     'amsler_cells': JSON_QUERY(k.amsler_cells), 'n_correct': k.n_correct,
                     'n_presented': k.n_presented, 'duration_s': k.duration_s
                     ABSENT ON NULL) AS nvarchar(max))
FROM [sans].[test_kaydi] AS k
JOIN [sans].[oturum] AS o ON o.session_id = k.session_id
JOIN [core].[Astronauts] AS a ON a.astronaut_id = k.astronaut_id
LEFT JOIN [anomaly].[MeasurementDefinitions] AS d ON d.measurement_code = k.test
"""


def upgrade() -> None:
    op.execute(SANS_GOREV)
    op.execute(SANS_PROFIL)
    op.execute(V_MEASUREMENTS)
    for view in VIEWS:
        grant(view, APP_ROLE, "SELECT")


def downgrade() -> None:
    for view in VIEWS:
        revoke(view, APP_ROLE, "SELECT")
    for view in reversed(VIEWS):
        schema, name = view.split(".")
        op.execute(f"DROP VIEW [{schema}].[{name}]")
