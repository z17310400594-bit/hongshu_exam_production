"""WP02 seed fixtures — org units, collections, and ACL entries for testing."""

ORG_SQL = """
INSERT INTO iam.organization_unit (code, name) VALUES
    ('org_teaching_materials', 'Teaching Materials Department'),
    ('org_teaching_aids',      'Teaching Aids Department'),
    ('org_operations',         'Operations Department'),
    ('org_it_support',         'IT Support Team')
ON CONFLICT DO NOTHING;
"""

COLLECTION_SQL = """
INSERT INTO knowledge.collection (code, name, owner_org_id, confidentiality)
SELECT 'coll_public',     'Public Policies',        id, 'public'
  FROM iam.organization_unit WHERE code = 'org_teaching_materials'
UNION ALL
SELECT 'coll_internal',   'Internal Textbooks',     id, 'internal'
  FROM iam.organization_unit WHERE code = 'org_teaching_materials'
UNION ALL
SELECT 'coll_confidential','Confidential Exams',     id, 'confidential'
  FROM iam.organization_unit WHERE code = 'org_teaching_aids'
UNION ALL
SELECT 'coll_restricted', 'Restricted Answer Keys',  id, 'restricted'
  FROM iam.organization_unit WHERE code = 'org_teaching_aids'
ON CONFLICT DO NOTHING;
"""

ACL_SQL = """
INSERT INTO knowledge.collection_acl (collection_id, principal_type, principal_code, permission)
SELECT c.id, 'org', 'org_teaching_materials', 'read'
  FROM knowledge.collection c WHERE c.code = 'coll_internal'
UNION ALL
SELECT c.id, 'org', 'org_teaching_materials', 'read'
  FROM knowledge.collection c WHERE c.code = 'coll_public'
UNION ALL
SELECT c.id, 'org', 'org_operations', 'read'
  FROM knowledge.collection c WHERE c.code = 'coll_public'
UNION ALL
SELECT c.id, 'org', 'org_it_support', 'admin'
  FROM knowledge.collection c WHERE c.code = 'coll_public'
ON CONFLICT DO NOTHING;
"""


def seed_fixtures(engine):
    """Run all WP02 fixture inserts in a single transaction."""
    from sqlalchemy import text
    with engine.connect() as conn, conn.begin():
        conn.execute(text(ORG_SQL))
        conn.execute(text(COLLECTION_SQL))
        conn.execute(text(ACL_SQL))
