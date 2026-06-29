"""WP03 seed fixtures — certificates, aliases, subjects."""

from sqlalchemy import text

CERT_SQL = """
INSERT INTO core.certificate (code, name, category_code, issuing_authority, nationwide) VALUES
    ('c_constructor_1', 'First-Class Constructor', 'construction', 'MOHURD', true),
    ('c_cost_engineer_1', 'First-Class Cost Engineer', 'construction', 'MOHURD', true),
    ('c_fire_engineer_1', 'First-Class Fire Engineer', 'fire', 'MEM', true),
    ('c_pharmacist_licensed', 'Licensed Pharmacist', 'pharma', 'NMPA', true),
    ('c_physician_licensed', 'Licensed Physician', 'medical', 'NHFPC', true)
ON CONFLICT DO NOTHING;
"""

ALIAS_SQL = """
INSERT INTO core.certificate_alias (certificate_id, alias, normalized_alias, alias_type)
SELECT c.id, '一建', 'cls1_constructor', 'common' FROM core.certificate c WHERE c.code = 'c_constructor_1'
UNION ALL
SELECT c.id, 'First-Class Constructor', 'c_constructor_1', 'short' FROM core.certificate c WHERE c.code = 'c_constructor_1'
UNION ALL
SELECT c.id, '一造', 'cls1_costengineer', 'common' FROM core.certificate c WHERE c.code = 'c_cost_engineer_1'
UNION ALL
SELECT c.id, '一消', 'cls1_fireporengineer', 'common' FROM core.certificate c WHERE c.code = 'c_fire_engineer_1'
UNION ALL
SELECT c.id, '执业药师', 'pharmacist_licensed', 'common' FROM core.certificate c WHERE c.code = 'c_pharmacist_licensed'
ON CONFLICT DO NOTHING;
"""

SUBJECT_SQL = """
INSERT INTO core.exam_subject (certificate_id, code, name)
SELECT c.id, 'subj_constructor_econ', 'Construction Economics' FROM core.certificate c WHERE c.code = 'c_constructor_1'
UNION ALL
SELECT c.id, 'subj_constructor_mgmt', 'Project Management' FROM core.certificate c WHERE c.code = 'c_constructor_1'
UNION ALL
SELECT c.id, 'subj_constructor_practice', 'Professional Practice' FROM core.certificate c WHERE c.code = 'c_constructor_1'
UNION ALL
SELECT c.id, 'subj_pharma_1', 'Pharmacy Knowledge I' FROM core.certificate c WHERE c.code = 'c_pharmacist_licensed'
ON CONFLICT DO NOTHING;
"""


def seed_fixtures(engine):
    with engine.connect() as conn, conn.begin():
        conn.execute(text(CERT_SQL))
        conn.execute(text(ALIAS_SQL))
        conn.execute(text(SUBJECT_SQL))
