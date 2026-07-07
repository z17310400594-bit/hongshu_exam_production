"""P2 batch 001 real-data seed.

This script is intentionally a repeatable data migration, not an Alembic schema
migration.  It reads the legacy `policy_fact` backup, creates the V2 certificate
catalog from `cert_basic`, then deep-seeds a small MVP slice:

- pharmacist_licensed: subjects, 2026 official CPTA exam date, policy evidence,
  eligibility rules, knowledge points, private fragments, and questions.
- cls1_constructor: subjects and 2026 official CPTA exam date.

Run:
    py scripts/p2_batch_001_seed.py --dry-run
    py scripts/p2_batch_001_seed.py --apply
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import io
import json
import sys
from dataclasses import dataclass
from datetime import date
from pathlib import Path
from typing import Any

from sqlalchemy import create_engine, text
from sqlalchemy.engine import Connection, Engine

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from api.config import settings  # noqa: E402

LEGACY_BACKUP = ROOT / "backups" / "policy_fact_baseline_20260629.sql"

CPTA_2026_PLAN_URL = "http://www.cpta.com.cn/testPlan/2127.html"
CPTA_2026_PLAN_TITLE = "2026年度专业技术人员职业资格考试工作计划"

SELECTED_CERT_CODES = {"pharmacist_licensed", "cls1_constructor"}

CPTA_2026_EXAM_DATES = {
    "pharmacist_licensed": {
        "event_code": "P2_CPTA_2026_PHARMACIST",
        "exam_start": date(2026, 10, 31),
        "exam_end": date(2026, 11, 1),
        "source_note": "CPTA 2026 plan image page 3: 执业药师（药学、中药学）10月31日、11月1日",
    },
    "cls1_constructor": {
        "event_code": "P2_CPTA_2026_CONSTRUCTOR_1",
        "exam_start": date(2026, 9, 12),
        "exam_end": date(2026, 9, 13),
        "source_note": "CPTA 2026 plan image page 3: 建造师（一级）9月12日、13日",
    },
}

DEGREE_MAP = {
    "大专": "associate",
    "本科": "bachelor",
    "硕士": "master",
    "博士": "doctor",
}
MAJOR_MAP = {
    "本专业": "pharmacy",
    "相关专业": "related",
    "其他专业": "other",
    "不限": "any",
}


@dataclass(frozen=True)
class SeedStats:
    certificates: int
    aliases: int
    subjects: int
    exam_events: int
    knowledge_points: int
    eligibility_rules: int
    questions: int


def parse_copy_table(path: Path, table_name: str) -> list[dict[str, str | None]]:
    """Parse one PostgreSQL COPY block from the legacy plain SQL dump."""
    marker = f"COPY public.{table_name} ("
    lines = path.read_text(encoding="utf-8").splitlines()
    for index, line in enumerate(lines):
        if not line.startswith(marker):
            continue
        columns_text = line.removeprefix(marker).split(") FROM stdin;", 1)[0]
        columns = [column.strip() for column in columns_text.split(",")]
        data_lines: list[str] = []
        for data_line in lines[index + 1 :]:
            if data_line == r"\.":
                break
            data_lines.append(data_line)
        reader = csv.reader(io.StringIO("\n".join(data_lines)), delimiter="\t")
        rows: list[dict[str, str | None]] = []
        for values in reader:
            rows.append(
                {
                    column: None if value == r"\N" else value.replace(r"\n", "\n")
                    for column, value in zip(columns, values, strict=True)
                }
            )
        return rows
    raise ValueError(f"COPY block not found: {table_name}")


def _sha256(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def _scalar_id(conn: Connection, sql: str, params: dict[str, Any]) -> int:
    return int(conn.execute(text(sql), params).scalar_one())


def ensure_org(conn: Connection, *, code: str, name: str) -> int:
    return _scalar_id(
        conn,
        """
        INSERT INTO iam.organization_unit (code, name)
        VALUES (:code, :name)
        ON CONFLICT (code) DO UPDATE SET name = EXCLUDED.name
        RETURNING id
        """,
        {"code": code, "name": name},
    )


def ensure_collection(
    conn: Connection,
    *,
    code: str,
    name: str,
    owner_org_id: int,
    confidentiality: str,
) -> int:
    return _scalar_id(
        conn,
        """
        INSERT INTO knowledge.collection (
            code, name, owner_org_id, confidentiality, default_allowed_use, status
        )
        VALUES (:code, :name, :owner_org_id, :confidentiality, ARRAY['retrieval'], 'active')
        ON CONFLICT (code) DO UPDATE SET
            name = EXCLUDED.name,
            owner_org_id = EXCLUDED.owner_org_id,
            confidentiality = EXCLUDED.confidentiality
        RETURNING id
        """,
        {
            "code": code,
            "name": name,
            "owner_org_id": owner_org_id,
            "confidentiality": confidentiality,
        },
    )


def grant_collection_read(conn: Connection, *, collection_id: int, principal_code: str) -> None:
    conn.execute(
        text("""
            INSERT INTO knowledge.collection_acl (
                collection_id, principal_type, principal_code, permission
            )
            VALUES (:collection_id, 'org', :principal_code, 'read')
            ON CONFLICT DO NOTHING
        """),
        {"collection_id": collection_id, "principal_code": principal_code},
    )


def ensure_asset(
    conn: Connection,
    *,
    code: str,
    asset_type: str,
    title: str,
    collection_id: int,
    owner_org_id: int,
    confidentiality: str,
) -> int:
    return _scalar_id(
        conn,
        """
        INSERT INTO knowledge.asset (
            code, asset_type, title, collection_id, owner_org_id,
            confidentiality, copyright_owner, allowed_use, status
        )
        VALUES (
            :code, :asset_type, :title, :collection_id, :owner_org_id,
            :confidentiality, 'legacy_policy_fact', ARRAY['retrieval','citation'], 'published'
        )
        ON CONFLICT (code) DO UPDATE SET
            title = EXCLUDED.title,
            collection_id = EXCLUDED.collection_id,
            owner_org_id = EXCLUDED.owner_org_id,
            confidentiality = EXCLUDED.confidentiality,
            status = EXCLUDED.status
        RETURNING id
        """,
        {
            "code": code,
            "asset_type": asset_type,
            "title": title,
            "collection_id": collection_id,
            "owner_org_id": owner_org_id,
            "confidentiality": confidentiality,
        },
    )


def ensure_asset_version(
    conn: Connection,
    *,
    asset_id: int,
    content: str,
    valid_from: str = "2019-03-05",
) -> int:
    digest = _sha256(content)
    conn.execute(
        text("""
            INSERT INTO knowledge.asset_version (
                asset_id, version_no, object_key, mime_type, extracted_text,
                content_sha256, valid_during, review_status, reviewed_by, reviewed_at
            )
            VALUES (
                :asset_id, 1, NULL, 'text/plain', :content,
                :digest, daterange(CAST(:valid_from AS date), NULL, '[)'),
                'approved', 'p2_batch_001', now()
            )
            ON CONFLICT (asset_id, version_no) DO NOTHING
        """),
        {"asset_id": asset_id, "content": content, "digest": digest, "valid_from": valid_from},
    )
    return _scalar_id(
        conn,
        "SELECT id FROM knowledge.asset_version WHERE asset_id = :asset_id AND version_no = 1",
        {"asset_id": asset_id},
    )


def ensure_fragment(
    conn: Connection,
    *,
    asset_version_id: int,
    fragment_code: str,
    fragment_type: str,
    heading: str,
    content: str,
    sequence_no: int = 0,
) -> int:
    return _scalar_id(
        conn,
        """
        INSERT INTO knowledge.fragment (
            asset_version_id, fragment_code, fragment_type, heading, content, sequence_no
        )
        VALUES (:asset_version_id, :fragment_code, :fragment_type, :heading, :content, :sequence_no)
        ON CONFLICT (asset_version_id, fragment_code) DO UPDATE SET
            heading = EXCLUDED.heading,
            content = EXCLUDED.content,
            sequence_no = EXCLUDED.sequence_no
        RETURNING id
        """,
        {
            "asset_version_id": asset_version_id,
            "fragment_code": fragment_code,
            "fragment_type": fragment_type,
            "heading": heading,
            "content": content,
            "sequence_no": sequence_no,
        },
    )


def seed_catalog(conn: Connection, cert_rows: list[dict[str, str | None]]) -> tuple[dict[str, int], int]:
    certificate_ids: dict[str, int] = {}
    alias_count = 0
    for row in cert_rows:
        code = str(row["cert_id"])
        certificate_id = _scalar_id(
            conn,
            """
            INSERT INTO core.certificate (
                code, name, category_code, issuing_authority, exam_authority, nationwide, status
            )
            VALUES (
                :code, :name, :category_code, :issuing_authority, :exam_authority, :nationwide, 'active'
            )
            ON CONFLICT (code) DO UPDATE SET
                name = EXCLUDED.name,
                category_code = EXCLUDED.category_code,
                issuing_authority = EXCLUDED.issuing_authority,
                exam_authority = EXCLUDED.exam_authority,
                nationwide = EXCLUDED.nationwide,
                status = 'active'
            RETURNING id
            """,
            {
                "code": code,
                "name": row["cert_name"],
                "category_code": row["profession_category"],
                "issuing_authority": row["issuing_authority"],
                "exam_authority": row["exam_authority"],
                "nationwide": row["valid_nationwide"] == "t",
            },
        )
        certificate_ids[code] = certificate_id

        alias_items = [
            (row["cert_name"], code, "common"),
            (row["short_name"], f"{code}:short", "short"),
        ]
        for alias, normalized_alias, alias_type in alias_items:
            if not alias:
                continue
            conn.execute(
                text("""
                    INSERT INTO core.certificate_alias (
                        certificate_id, alias, normalized_alias, alias_type
                    )
                    VALUES (:certificate_id, :alias, :normalized_alias, :alias_type)
                    ON CONFLICT (normalized_alias) DO UPDATE SET
                        certificate_id = EXCLUDED.certificate_id,
                        alias = EXCLUDED.alias,
                        alias_type = EXCLUDED.alias_type
                """),
                {
                    "certificate_id": certificate_id,
                    "alias": alias,
                    "normalized_alias": normalized_alias,
                    "alias_type": alias_type,
                },
            )
            alias_count += 1
    return certificate_ids, alias_count


def seed_subjects(
    conn: Connection,
    *,
    certificate_ids: dict[str, int],
    subject_rows: list[dict[str, str | None]],
) -> dict[str, int]:
    subject_ids: dict[str, int] = {}
    for row in subject_rows:
        cert_code = str(row["cert_id"])
        if cert_code not in SELECTED_CERT_CODES:
            continue
        subject_id = _scalar_id(
            conn,
            """
            INSERT INTO core.exam_subject (certificate_id, code, name)
            VALUES (:certificate_id, :code, :name)
            ON CONFLICT (code) DO UPDATE SET
                certificate_id = EXCLUDED.certificate_id,
                name = EXCLUDED.name
            RETURNING id
            """,
            {
                "certificate_id": certificate_ids[cert_code],
                "code": row["subject_id"],
                "name": row["subject_name"],
            },
        )
        subject_ids[str(row["subject_id"])] = subject_id
    return subject_ids


def seed_exam_events(
    conn: Connection,
    *,
    certificate_ids: dict[str, int],
    subject_ids: dict[str, int],
    subject_rows: list[dict[str, str | None]],
) -> int:
    count = 0
    for cert_code, data in CPTA_2026_EXAM_DATES.items():
        event_id = _scalar_id(
            conn,
            """
            INSERT INTO assessment.exam_event (
                code, certificate_id, exam_year, region_code, status
            )
            VALUES (:code, :certificate_id, 2026, 'CN', 'published')
            ON CONFLICT (code) DO UPDATE SET
                certificate_id = EXCLUDED.certificate_id,
                exam_year = EXCLUDED.exam_year,
                status = EXCLUDED.status
            RETURNING id
            """,
            {"code": data["event_code"], "certificate_id": certificate_ids[cert_code]},
        )
        conn.execute(
            text("""
                INSERT INTO assessment.exam_phase (
                    exam_event_id, phase_type, starts_on, ends_on, note
                )
                VALUES (:event_id, 'written', :starts_on, :ends_on, :note)
                ON CONFLICT (exam_event_id, phase_type, starts_on) DO UPDATE SET
                    ends_on = EXCLUDED.ends_on,
                    note = EXCLUDED.note
            """),
            {
                "event_id": event_id,
                "starts_on": data["exam_start"],
                "ends_on": data["exam_end"],
                "note": f"{data['source_note']}; source={CPTA_2026_PLAN_URL}",
            },
        )
        for subject in subject_rows:
            if subject["cert_id"] != cert_code:
                continue
            conn.execute(
                text("""
                    INSERT INTO assessment.subject_score_rule (
                        exam_event_id, subject_id, full_mark, pass_mark
                    )
                    VALUES (:event_id, :subject_id, :full_mark, :pass_mark)
                    ON CONFLICT (exam_event_id, subject_id) DO UPDATE SET
                        full_mark = EXCLUDED.full_mark,
                        pass_mark = EXCLUDED.pass_mark
                """),
                {
                    "event_id": event_id,
                    "subject_id": subject_ids[str(subject["subject_id"])],
                    "full_mark": int(str(subject["full_mark"])),
                    "pass_mark": int(str(subject["pass_mark"])),
                },
            )
        count += 1
    return count


def seed_official_plan_asset(
    conn: Connection,
    *,
    public_collection_id: int,
    owner_org_id: int,
) -> None:
    content = (
        f"{CPTA_2026_PLAN_TITLE}\n"
        f"source: {CPTA_2026_PLAN_URL}\n"
        "建造师（一级）：9月12日、13日。\n"
        "执业药师（药学、中药学）：10月31日、11月1日。"
    )
    asset_id = ensure_asset(
        conn,
        code="P2_CPTA_2026_EXAM_PLAN",
        asset_type="manual",
        title=CPTA_2026_PLAN_TITLE,
        collection_id=public_collection_id,
        owner_org_id=owner_org_id,
        confidentiality="public",
    )
    version_id = ensure_asset_version(conn, asset_id=asset_id, content=content, valid_from="2026-02-03")
    ensure_fragment(
        conn,
        asset_version_id=version_id,
        fragment_code="P2_CPTA_2026_CONSTRUCTOR_1",
        fragment_type="section",
        heading="一级建造师 2026 考试日期",
        content="中国人事考试网 2026年度专业技术人员职业资格考试工作计划：建造师（一级）9月12日、13日。",
        sequence_no=1,
    )
    ensure_fragment(
        conn,
        asset_version_id=version_id,
        fragment_code="P2_CPTA_2026_PHARMACIST",
        fragment_type="section",
        heading="执业药师 2026 考试日期",
        content="中国人事考试网 2026年度专业技术人员职业资格考试工作计划：执业药师（药学、中药学）10月31日、11月1日。",
        sequence_no=2,
    )


def seed_knowledge_points(
    conn: Connection,
    *,
    certificate_ids: dict[str, int],
    kp_rows: list[dict[str, str | None]],
    internal_collection_id: int,
    owner_org_id: int,
) -> dict[str, int]:
    kp_ids: dict[str, int] = {}
    for row in kp_rows:
        if row["cert_id"] != "pharmacist_licensed":
            continue
        kp_id = _scalar_id(
            conn,
            """
            INSERT INTO knowledge.knowledge_point (
                code, name, domain_code, cognitive_level, description, status
            )
            VALUES (:code, :name, 'assessment', 'understand', :description, 'active')
            ON CONFLICT (code) DO UPDATE SET
                name = EXCLUDED.name,
                description = EXCLUDED.description,
                status = 'active'
            RETURNING id
            """,
            {
                "code": row["kp_id"],
                "name": row["kp_name"],
                "description": f"{row.get('kp_chapter') or ''}；{row.get('note') or ''}",
            },
        )
        kp_ids[str(row["kp_id"])] = kp_id
        for scope_type, scope_code in (
            ("certificate", "pharmacist_licensed"),
            ("exam_subject", row["subject_id"]),
        ):
            if not scope_code:
                continue
            conn.execute(
                text("""
                    INSERT INTO knowledge.knowledge_point_scope (kp_id, scope_type, scope_code)
                    VALUES (:kp_id, :scope_type, :scope_code)
                    ON CONFLICT DO NOTHING
                """),
                {"kp_id": kp_id, "scope_type": scope_type, "scope_code": scope_code},
            )

    policy_kp_id = _scalar_id(
        conn,
        """
        INSERT INTO knowledge.knowledge_point (
            code, name, domain_code, cognitive_level, description, status
        )
        VALUES (
            'P2_KP_PHARMACIST_ELIGIBILITY',
            '执业药师报考条件',
            'policy',
            'understand',
            '执业药师学历、专业、岗位工作年限条件。',
            'active'
        )
        ON CONFLICT (code) DO UPDATE SET
            name = EXCLUDED.name,
            description = EXCLUDED.description,
            status = 'active'
        RETURNING id
        """,
        {},
    )
    kp_ids["P2_KP_PHARMACIST_ELIGIBILITY"] = policy_kp_id
    conn.execute(
        text("""
            INSERT INTO knowledge.knowledge_point_scope (kp_id, scope_type, scope_code)
            VALUES (:kp_id, 'certificate', 'pharmacist_licensed')
            ON CONFLICT DO NOTHING
        """),
        {"kp_id": policy_kp_id},
    )

    content = "\n".join(
        f"{row['kp_id']} {row['kp_name']} {row.get('kp_chapter') or ''} {row.get('note') or ''}"
        for row in kp_rows
        if row["cert_id"] == "pharmacist_licensed"
    )
    asset_id = ensure_asset(
        conn,
        code="P2_PHARMACIST_INTERNAL_KP_NOTES",
        asset_type="textbook",
        title="P2 执业药师内部教辅考点摘录",
        collection_id=internal_collection_id,
        owner_org_id=owner_org_id,
        confidentiality="internal",
    )
    version_id = ensure_asset_version(conn, asset_id=asset_id, content=content, valid_from="2026-06-25")
    for index, row in enumerate([row for row in kp_rows if row["cert_id"] == "pharmacist_licensed"], start=1):
        fragment_id = ensure_fragment(
            conn,
            asset_version_id=version_id,
            fragment_code=str(row["kp_id"]),
            fragment_type="section",
            heading=str(row["kp_name"]),
            content=f"{row['kp_name']}：{row.get('kp_chapter') or ''}。{row.get('note') or ''}",
            sequence_no=index,
        )
        conn.execute(
            text("""
                INSERT INTO knowledge.fragment_knowledge_point (
                    fragment_id, kp_id, relation_role, confidence, review_status, reviewed_by
                )
                VALUES (:fragment_id, :kp_id, 'explanation', 0.950, 'approved', 'p2_batch_001')
                ON CONFLICT (fragment_id, kp_id, relation_role) DO UPDATE SET
                    confidence = EXCLUDED.confidence,
                    review_status = EXCLUDED.review_status,
                    reviewed_by = EXCLUDED.reviewed_by
            """),
            {"fragment_id": fragment_id, "kp_id": kp_ids[str(row["kp_id"])]},
        )
    return kp_ids


def seed_policy(
    conn: Connection,
    *,
    policy_doc_rows: list[dict[str, str | None]],
    policy_clause_rows: list[dict[str, str | None]],
    public_collection_id: int,
    owner_org_id: int,
) -> dict[str, int]:
    clause_ids: dict[str, int] = {}
    docs = {str(row["doc_id"]): row for row in policy_doc_rows}
    clauses = {str(row["clause_id"]): row for row in policy_clause_rows}
    wanted_clause_codes = ["clause_pharmacist_03"]
    for doc_code in ["doc_pharmacist_rule", "doc_pharmacist_exam"]:
        doc = docs[doc_code]
        asset_id = ensure_asset(
            conn,
            code=f"P2_POLICY_ASSET_{doc_code}",
            asset_type="policy",
            title=str(doc["doc_title"]),
            collection_id=public_collection_id,
            owner_org_id=owner_org_id,
            confidentiality="public",
        )
        version_id = ensure_asset_version(
            conn,
            asset_id=asset_id,
            content=str(doc["raw_text"] or doc["doc_title"]),
            valid_from=str(doc["effective_date"] or doc["publish_date"] or "2019-03-05"),
        )
        document_id = _scalar_id(
            conn,
            """
            INSERT INTO policy.document (
                asset_id, document_code, doc_number, issuing_authority, official_url
            )
            VALUES (:asset_id, :document_code, :doc_number, :issuing_authority, :official_url)
            ON CONFLICT (document_code) DO UPDATE SET
                asset_id = EXCLUDED.asset_id,
                doc_number = EXCLUDED.doc_number,
                issuing_authority = EXCLUDED.issuing_authority,
                official_url = EXCLUDED.official_url
            RETURNING id
            """,
            {
                "asset_id": asset_id,
                "document_code": doc_code,
                "doc_number": doc["doc_number"],
                "issuing_authority": doc["issuing_authority"] or "unknown",
                "official_url": doc["source_url"],
            },
        )
        doc_version_id = _scalar_id(
            conn,
            """
            INSERT INTO policy.document_version (
                document_id, asset_version_id, version_no, published_on,
                valid_during, status
            )
            VALUES (
                :document_id, :asset_version_id, 1, :published_on,
                daterange(CAST(:valid_from AS date), NULL, '[)'), 'published'
            )
            ON CONFLICT (document_id, version_no) DO UPDATE SET
                asset_version_id = EXCLUDED.asset_version_id,
                published_on = EXCLUDED.published_on,
                valid_during = EXCLUDED.valid_during,
                status = EXCLUDED.status
            RETURNING id
            """,
            {
                "document_id": document_id,
                "asset_version_id": version_id,
                "published_on": doc["publish_date"],
                "valid_from": doc["effective_date"] or doc["publish_date"] or "2019-03-05",
            },
        )

        if doc_code == "doc_pharmacist_rule":
            for clause_code in wanted_clause_codes:
                clause = clauses[clause_code]
                fragment_id = ensure_fragment(
                    conn,
                    asset_version_id=version_id,
                    fragment_code=clause_code,
                    fragment_type="clause",
                    heading=str(clause["clause_section"]),
                    content=str(clause["clause_text"]),
                    sequence_no=1,
                )
                clause_ids[clause_code] = _scalar_id(
                    conn,
                    """
                    INSERT INTO policy.clause (
                        document_version_id, fragment_id, clause_code, section_path, summary
                    )
                    VALUES (
                        :document_version_id, :fragment_id, :clause_code, :section_path, :summary
                    )
                    ON CONFLICT (document_version_id, clause_code) DO UPDATE SET
                        fragment_id = EXCLUDED.fragment_id,
                        section_path = EXCLUDED.section_path,
                        summary = EXCLUDED.summary
                    RETURNING id
                    """,
                    {
                        "document_version_id": doc_version_id,
                        "fragment_id": fragment_id,
                        "clause_code": clause_code,
                        "section_path": clause["clause_section"],
                        "summary": clause["clause_summary"],
                    },
                )
        if doc_code == "doc_pharmacist_exam":
            site_text = "考点原则上设在地级以上城市的大、中专院校或者高考定点学校。"
            fragment_id = ensure_fragment(
                conn,
                asset_version_id=version_id,
                fragment_code="clause_pharmacist_exam_site_07",
                fragment_type="clause",
                heading="第七条",
                content=site_text,
                sequence_no=7,
            )
            clause_ids["clause_pharmacist_exam_site_07"] = _scalar_id(
                conn,
                """
                INSERT INTO policy.clause (
                    document_version_id, fragment_id, clause_code, section_path, summary
                )
                VALUES (
                    :document_version_id, :fragment_id,
                    'clause_pharmacist_exam_site_07', '第七条',
                    '执业药师考点设置原则'
                )
                ON CONFLICT (document_version_id, clause_code) DO UPDATE SET
                    fragment_id = EXCLUDED.fragment_id,
                    section_path = EXCLUDED.section_path,
                    summary = EXCLUDED.summary
                RETURNING id
                """,
                {"document_version_id": doc_version_id, "fragment_id": fragment_id},
            )
    return clause_ids


def seed_eligibility_rules(
    conn: Connection,
    *,
    certificate_ids: dict[str, int],
    kp_ids: dict[str, int],
    clause_ids: dict[str, int],
    condition_rows: list[dict[str, str | None]],
) -> int:
    count = 0
    for row in condition_rows:
        if row["cert_id"] != "pharmacist_licensed":
            continue
        degree_code = DEGREE_MAP.get(str(row["degree_level"]))
        major_code = MAJOR_MAP.get(str(row["major_category"]))
        if degree_code is None or major_code is None:
            continue
        work_years = int(str(row["total_work_years"] or "0"))
        rule_id = _scalar_id(
            conn,
            """
            INSERT INTO policy.eligibility_rule (
                code, certificate_id, knowledge_point_id, qualification_level,
                route_code, degree_level_code, major_category_code, education_type_code,
                min_total_work_months, min_relevant_work_months, region_code,
                extra_conditions, valid_during, status, review_status, reviewed_by, reviewed_at
            )
            VALUES (
                :code, :certificate_id, :knowledge_point_id, NULL,
                'normal', :degree_code, :major_code, 'any',
                :months, :months, 'CN',
                CAST(:extra_conditions AS jsonb),
                daterange('2026-01-01'::date, NULL, '[)'),
                'published', 'approved', 'p2_batch_001', now()
            )
            ON CONFLICT (code) DO UPDATE SET
                certificate_id = EXCLUDED.certificate_id,
                knowledge_point_id = EXCLUDED.knowledge_point_id,
                qualification_level = EXCLUDED.qualification_level,
                degree_level_code = EXCLUDED.degree_level_code,
                major_category_code = EXCLUDED.major_category_code,
                min_total_work_months = EXCLUDED.min_total_work_months,
                min_relevant_work_months = EXCLUDED.min_relevant_work_months,
                status = EXCLUDED.status,
                review_status = EXCLUDED.review_status,
                reviewed_by = EXCLUDED.reviewed_by,
                reviewed_at = EXCLUDED.reviewed_at
            RETURNING id
            """,
            {
                "code": row["condition_id"],
                "certificate_id": certificate_ids["pharmacist_licensed"],
                "knowledge_point_id": kp_ids["P2_KP_PHARMACIST_ELIGIBILITY"],
                "degree_code": degree_code,
                "major_code": major_code,
                "months": work_years * 12,
                "extra_conditions": json.dumps(
                    {
                        "legacy_condition_id": row["condition_id"],
                        "legacy_note": row["note"],
                        "source_status": "legacy_structured_needs_latest_official_recheck",
                    },
                    ensure_ascii=False,
                ),
            },
        )
        conn.execute(
            text("""
                INSERT INTO policy.eligibility_rule_evidence (
                    eligibility_rule_id, clause_id, evidence_role
                )
                VALUES (:rule_id, :clause_id, 'primary')
                ON CONFLICT DO NOTHING
            """),
            {"rule_id": rule_id, "clause_id": clause_ids["clause_pharmacist_03"]},
        )
        count += 1
    return count


def seed_questions(
    conn: Connection,
    *,
    certificate_ids: dict[str, int],
    subject_ids: dict[str, int],
    kp_ids: dict[str, int],
    question_rows: list[dict[str, str | None]],
    question_kp_rows: list[dict[str, str | None]],
    internal_collection_id: int,
    owner_org_id: int,
) -> int:
    selected_questions = [row for row in question_rows if row["cert_id"] == "pharmacist_licensed"]
    content = "\n\n".join(f"{row['question_id']} {row['content']}" for row in selected_questions)
    asset_id = ensure_asset(
        conn,
        code="P2_PHARMACIST_QUESTION_ASSET",
        asset_type="paper",
        title="P2 执业药师药学专业知识（一）真题样例",
        collection_id=internal_collection_id,
        owner_org_id=owner_org_id,
        confidentiality="internal",
    )
    version_id = ensure_asset_version(conn, asset_id=asset_id, content=content, valid_from="2026-06-25")
    paper_id = _scalar_id(
        conn,
        """
        INSERT INTO assessment.paper (
            code, paper_type, certificate_id, subject_id, exam_year,
            source_asset_version_id, owner_org_id, title, status, review_status, reviewed_by
        )
        VALUES (
            'P2_PHARMACIST_YAO1_SAMPLE', 'official', :certificate_id, :subject_id, 2026,
            :version_id, :owner_org_id, 'P2 执业药师药学专业知识（一）真题样例',
            'published', 'approved', 'p2_batch_001'
        )
        ON CONFLICT (code) DO UPDATE SET
            certificate_id = EXCLUDED.certificate_id,
            subject_id = EXCLUDED.subject_id,
            source_asset_version_id = EXCLUDED.source_asset_version_id,
            owner_org_id = EXCLUDED.owner_org_id,
            status = EXCLUDED.status,
            review_status = EXCLUDED.review_status,
            reviewed_by = EXCLUDED.reviewed_by
        RETURNING id
        """,
        {
            "certificate_id": certificate_ids["pharmacist_licensed"],
            "subject_id": subject_ids["pharmacist_licensed_yao1"],
            "version_id": version_id,
            "owner_org_id": owner_org_id,
        },
    )
    kp_by_question: dict[str, list[str]] = {}
    for row in question_kp_rows:
        kp_by_question.setdefault(str(row["question_id"]), []).append(str(row["kp_id"]))

    count = 0
    for index, row in enumerate(selected_questions, start=1):
        fragment_id = ensure_fragment(
            conn,
            asset_version_id=version_id,
            fragment_code=str(row["question_id"]),
            fragment_type="section",
            heading=f"题目 {row['question_id']}",
            content=f"{row['content']}\n解析：{row['analysis']}",
            sequence_no=index,
        )
        question_type = "single" if row["question_type"] == "单选" else "multiple"
        question_id = _scalar_id(
            conn,
            """
            INSERT INTO assessment.question (
                paper_id, source_fragment_id, question_no, question_type,
                content, options, answer, analysis, difficulty, review_status
            )
            VALUES (
                :paper_id, :fragment_id, :question_no, :question_type,
                :content, CAST(:options AS jsonb), CAST(:answer AS jsonb),
                :analysis, :difficulty, 'approved'
            )
            ON CONFLICT (paper_id, question_no) DO UPDATE SET
                source_fragment_id = EXCLUDED.source_fragment_id,
                question_type = EXCLUDED.question_type,
                content = EXCLUDED.content,
                options = EXCLUDED.options,
                answer = EXCLUDED.answer,
                analysis = EXCLUDED.analysis,
                difficulty = EXCLUDED.difficulty,
                review_status = EXCLUDED.review_status
            RETURNING id
            """,
            {
                "paper_id": paper_id,
                "fragment_id": fragment_id,
                "question_no": row["question_id"],
                "question_type": question_type,
                "content": row["content"],
                "options": row["options"] or "{}",
                "answer": json.dumps(row["answer"], ensure_ascii=False),
                "analysis": row["analysis"],
                "difficulty": int(str(row["difficulty"] or "3")),
            },
        )
        for kp_code in kp_by_question.get(str(row["question_id"]), []):
            if kp_code not in kp_ids:
                continue
            conn.execute(
                text("""
                    INSERT INTO assessment.question_knowledge_point (
                        question_id, kp_id, role, score_weight
                    )
                    VALUES (:question_id, :kp_id, 'primary', 1.000)
                    ON CONFLICT DO NOTHING
                """),
                {"question_id": question_id, "kp_id": kp_ids[kp_code]},
            )
        count += 1
    return count


def seed(engine: Engine, *, legacy_backup: Path = LEGACY_BACKUP) -> SeedStats:
    cert_rows = parse_copy_table(legacy_backup, "cert_basic")
    subject_rows = parse_copy_table(legacy_backup, "exam_subject")
    kp_rows = parse_copy_table(legacy_backup, "knowledge_point")
    policy_doc_rows = parse_copy_table(legacy_backup, "policy_doc")
    policy_clause_rows = parse_copy_table(legacy_backup, "policy_clause")
    condition_rows = parse_copy_table(legacy_backup, "exam_condition")
    question_rows = parse_copy_table(legacy_backup, "exam_question")
    question_kp_rows = parse_copy_table(legacy_backup, "exam_question_kp")

    with engine.begin() as conn:
        company_id = ensure_org(conn, code="org_company", name="公司")
        teaching_id = ensure_org(conn, code="org_teaching_materials", name="教材部")
        ensure_org(conn, code="org_operations", name="运营部")
        public_collection_id = ensure_collection(
            conn,
            code="coll_public",
            name="公开政策资料",
            owner_org_id=company_id,
            confidentiality="public",
        )
        internal_collection_id = ensure_collection(
            conn,
            code="coll_internal",
            name="公司内部教材教辅资料",
            owner_org_id=teaching_id,
            confidentiality="internal",
        )
        for principal in ("org_teaching_materials", "org_operations"):
            grant_collection_read(conn, collection_id=public_collection_id, principal_code=principal)
        grant_collection_read(conn, collection_id=internal_collection_id, principal_code="org_teaching_materials")

        certificate_ids, alias_count = seed_catalog(conn, cert_rows)
        subject_ids = seed_subjects(conn, certificate_ids=certificate_ids, subject_rows=subject_rows)
        exam_event_count = seed_exam_events(
            conn,
            certificate_ids=certificate_ids,
            subject_ids=subject_ids,
            subject_rows=subject_rows,
        )
        seed_official_plan_asset(
            conn,
            public_collection_id=public_collection_id,
            owner_org_id=company_id,
        )
        kp_ids = seed_knowledge_points(
            conn,
            certificate_ids=certificate_ids,
            kp_rows=kp_rows,
            internal_collection_id=internal_collection_id,
            owner_org_id=teaching_id,
        )
        clause_ids = seed_policy(
            conn,
            policy_doc_rows=policy_doc_rows,
            policy_clause_rows=policy_clause_rows,
            public_collection_id=public_collection_id,
            owner_org_id=company_id,
        )
        eligibility_rule_count = seed_eligibility_rules(
            conn,
            certificate_ids=certificate_ids,
            kp_ids=kp_ids,
            clause_ids=clause_ids,
            condition_rows=condition_rows,
        )
        question_count = seed_questions(
            conn,
            certificate_ids=certificate_ids,
            subject_ids=subject_ids,
            kp_ids=kp_ids,
            question_rows=question_rows,
            question_kp_rows=question_kp_rows,
            internal_collection_id=internal_collection_id,
            owner_org_id=teaching_id,
        )

    return SeedStats(
        certificates=len(cert_rows),
        aliases=alias_count,
        subjects=len(subject_ids),
        exam_events=exam_event_count,
        knowledge_points=len(kp_ids),
        eligibility_rules=eligibility_rule_count,
        questions=question_count,
    )


def dry_run(*, legacy_backup: Path = LEGACY_BACKUP) -> SeedStats:
    cert_rows = parse_copy_table(legacy_backup, "cert_basic")
    subject_rows = [
        row for row in parse_copy_table(legacy_backup, "exam_subject") if row["cert_id"] in SELECTED_CERT_CODES
    ]
    kp_rows = [
        row for row in parse_copy_table(legacy_backup, "knowledge_point") if row["cert_id"] == "pharmacist_licensed"
    ]
    condition_rows = [
        row for row in parse_copy_table(legacy_backup, "exam_condition") if row["cert_id"] == "pharmacist_licensed"
    ]
    question_rows = [
        row for row in parse_copy_table(legacy_backup, "exam_question") if row["cert_id"] == "pharmacist_licensed"
    ]
    return SeedStats(
        certificates=len(cert_rows),
        aliases=len(cert_rows) * 2,
        subjects=len(subject_rows),
        exam_events=len(CPTA_2026_EXAM_DATES),
        knowledge_points=len(kp_rows) + 1,
        eligibility_rules=len(condition_rows),
        questions=len(question_rows),
    )


def main() -> None:
    parser = argparse.ArgumentParser(description="Seed P2 batch 001 real data into V2.")
    parser.add_argument("--apply", action="store_true", help="write data to the configured V2 database")
    parser.add_argument("--dry-run", action="store_true", help="only print planned row counts")
    parser.add_argument("--database-url", default=settings.database_url, help="override database URL")
    args = parser.parse_args()

    if args.apply == args.dry_run:
        raise SystemExit("Choose exactly one of --apply or --dry-run.")

    stats = dry_run() if args.dry_run else seed(create_engine(args.database_url))
    print(json.dumps(stats.__dict__, ensure_ascii=False, sort_keys=True))


if __name__ == "__main__":
    main()
