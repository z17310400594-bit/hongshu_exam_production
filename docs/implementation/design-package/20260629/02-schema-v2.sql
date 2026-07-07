-- PostgreSQL 15+ implementation skeleton.
-- Split into ordered migrations before production use.
CREATE SCHEMA IF NOT EXISTS iam;
CREATE SCHEMA IF NOT EXISTS core;
CREATE SCHEMA IF NOT EXISTS knowledge;
CREATE SCHEMA IF NOT EXISTS policy;
CREATE SCHEMA IF NOT EXISTS content;
CREATE SCHEMA IF NOT EXISTS assessment;
CREATE SCHEMA IF NOT EXISTS generation;
CREATE SCHEMA IF NOT EXISTS analytics;
CREATE SCHEMA IF NOT EXISTS ingestion;
CREATE SCHEMA IF NOT EXISTS audit;

CREATE EXTENSION IF NOT EXISTS pg_trgm;
-- pgvector extension name is vector, not pgvector. Enable only when installed:
-- CREATE EXTENSION IF NOT EXISTS vector;

CREATE TABLE iam.organization_unit (
  id bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
  code text NOT NULL UNIQUE,
  name text NOT NULL,
  parent_id bigint REFERENCES iam.organization_unit(id),
  status text NOT NULL DEFAULT 'active' CHECK (status IN ('active','inactive')),
  created_at timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE core.certificate (
  id bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
  code text NOT NULL UNIQUE,
  name text NOT NULL UNIQUE,
  category_code text,
  issuing_authority text,
  exam_authority text,
  nationwide boolean NOT NULL DEFAULT true,
  status text NOT NULL DEFAULT 'active' CHECK (status IN ('active','inactive')),
  created_at timestamptz NOT NULL DEFAULT now(),
  updated_at timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE core.certificate_alias (
  id bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
  certificate_id bigint NOT NULL REFERENCES core.certificate(id) ON DELETE CASCADE,
  alias text NOT NULL,
  normalized_alias text NOT NULL UNIQUE,
  alias_type text NOT NULL CHECK (alias_type IN ('short','common','legacy'))
);

CREATE TABLE core.exam_subject (
  id bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
  certificate_id bigint NOT NULL REFERENCES core.certificate(id),
  code text NOT NULL UNIQUE,
  name text NOT NULL,
  UNIQUE (certificate_id, name)
);

CREATE TABLE knowledge.collection (
  id bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
  code text NOT NULL UNIQUE,
  name text NOT NULL,
  owner_org_id bigint NOT NULL REFERENCES iam.organization_unit(id),
  confidentiality text NOT NULL CHECK (confidentiality IN ('public','internal','confidential','restricted')),
  default_allowed_use text[] NOT NULL DEFAULT ARRAY['retrieval']::text[],
  status text NOT NULL DEFAULT 'active'
);

CREATE TABLE knowledge.collection_acl (
  collection_id bigint NOT NULL REFERENCES knowledge.collection(id) ON DELETE CASCADE,
  principal_type text NOT NULL CHECK (principal_type IN ('user','role','org')),
  principal_code text NOT NULL,
  permission text NOT NULL CHECK (permission IN ('read','contribute','review','admin')),
  PRIMARY KEY (collection_id, principal_type, principal_code, permission)
);

CREATE TABLE knowledge.asset (
  id bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
  code text NOT NULL UNIQUE,
  asset_type text NOT NULL,
  title text NOT NULL,
  collection_id bigint NOT NULL REFERENCES knowledge.collection(id),
  owner_org_id bigint NOT NULL REFERENCES iam.organization_unit(id),
  confidentiality text NOT NULL CHECK (confidentiality IN ('public','internal','confidential','restricted')),
  copyright_owner text,
  allowed_use text[] NOT NULL DEFAULT ARRAY['retrieval']::text[],
  status text NOT NULL DEFAULT 'draft' CHECK (status IN ('draft','reviewed','published','deprecated')),
  created_at timestamptz NOT NULL DEFAULT now(),
  updated_at timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE knowledge.asset_version (
  id bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
  asset_id bigint NOT NULL REFERENCES knowledge.asset(id),
  version_no integer NOT NULL CHECK (version_no > 0),
  object_key text,
  mime_type text,
  extracted_text text,
  content_sha256 text NOT NULL,
  valid_during daterange,
  review_status text NOT NULL DEFAULT 'pending' CHECK (review_status IN ('pending','approved','rejected')),
  reviewed_by text,
  reviewed_at timestamptz,
  created_at timestamptz NOT NULL DEFAULT now(),
  UNIQUE (asset_id, version_no),
  UNIQUE (content_sha256)
);

CREATE TABLE knowledge.fragment (
  id bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
  asset_version_id bigint NOT NULL REFERENCES knowledge.asset_version(id) ON DELETE CASCADE,
  fragment_code text NOT NULL,
  fragment_type text NOT NULL,
  parent_id bigint REFERENCES knowledge.fragment(id),
  sequence_no integer NOT NULL DEFAULT 0,
  heading text,
  content text NOT NULL,
  page_from integer,
  page_to integer,
  search_tsv tsvector GENERATED ALWAYS AS (to_tsvector('simple', coalesce(heading,'') || ' ' || content)) STORED,
  UNIQUE (asset_version_id, fragment_code),
  CHECK (page_from IS NULL OR page_from > 0),
  CHECK (page_to IS NULL OR page_from IS NULL OR page_to >= page_from)
);
CREATE INDEX idx_fragment_search ON knowledge.fragment USING gin(search_tsv);
CREATE INDEX idx_fragment_content_trgm ON knowledge.fragment USING gin(content gin_trgm_ops);

CREATE TABLE knowledge.knowledge_point (
  id bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
  code text NOT NULL UNIQUE,
  name text NOT NULL,
  parent_id bigint REFERENCES knowledge.knowledge_point(id),
  domain_code text NOT NULL,
  cognitive_level text CHECK (cognitive_level IN ('remember','understand','apply','analyze','evaluate','create')),
  description text,
  status text NOT NULL DEFAULT 'active'
);

CREATE TABLE knowledge.knowledge_point_relation (
  from_kp_id bigint NOT NULL REFERENCES knowledge.knowledge_point(id) ON DELETE CASCADE,
  to_kp_id bigint NOT NULL REFERENCES knowledge.knowledge_point(id) ON DELETE CASCADE,
  relation_type text NOT NULL CHECK (relation_type IN ('prerequisite','related','contains','similar')),
  PRIMARY KEY (from_kp_id, to_kp_id, relation_type),
  CHECK (from_kp_id <> to_kp_id)
);

CREATE TABLE knowledge.fragment_knowledge_point (
  fragment_id bigint NOT NULL REFERENCES knowledge.fragment(id) ON DELETE CASCADE,
  kp_id bigint NOT NULL REFERENCES knowledge.knowledge_point(id) ON DELETE CASCADE,
  relation_role text NOT NULL CHECK (relation_role IN ('definition','evidence','explanation','example','exercise')),
  confidence numeric(4,3) NOT NULL DEFAULT 1 CHECK (confidence BETWEEN 0 AND 1),
  review_status text NOT NULL DEFAULT 'pending' CHECK (review_status IN ('pending','approved','rejected')),
  reviewed_by text,
  PRIMARY KEY (fragment_id, kp_id, relation_role)
);

CREATE TABLE policy.document (
  id bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
  asset_id bigint NOT NULL UNIQUE REFERENCES knowledge.asset(id),
  document_code text NOT NULL UNIQUE,
  doc_number text,
  issuing_authority text NOT NULL,
  official_url text
);

CREATE TABLE policy.document_version (
  id bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
  document_id bigint NOT NULL REFERENCES policy.document(id),
  asset_version_id bigint NOT NULL UNIQUE REFERENCES knowledge.asset_version(id),
  version_no integer NOT NULL,
  published_on date,
  valid_during daterange NOT NULL,
  status text NOT NULL CHECK (status IN ('draft','reviewed','published','superseded','repealed')),
  supersedes_version_id bigint REFERENCES policy.document_version(id),
  UNIQUE (document_id, version_no)
);

CREATE TABLE policy.clause (
  id bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
  document_version_id bigint NOT NULL REFERENCES policy.document_version(id) ON DELETE CASCADE,
  fragment_id bigint NOT NULL UNIQUE REFERENCES knowledge.fragment(id),
  clause_code text NOT NULL,
  section_path text,
  summary text,
  UNIQUE (document_version_id, clause_code)
);

CREATE TABLE policy.eligibility_rule (
  id bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
  code text NOT NULL UNIQUE,
  certificate_id bigint NOT NULL REFERENCES core.certificate(id),
  qualification_level text,
  route_code text NOT NULL DEFAULT 'normal',
  degree_level_code text,
  major_category_code text,
  education_type_code text,
  min_total_work_months integer NOT NULL DEFAULT 0 CHECK (min_total_work_months >= 0),
  min_relevant_work_months integer NOT NULL DEFAULT 0 CHECK (min_relevant_work_months >= 0),
  admission_before date,
  region_code text NOT NULL DEFAULT 'CN',
  extra_conditions jsonb NOT NULL DEFAULT '{}'::jsonb CHECK (jsonb_typeof(extra_conditions) = 'object'),
  valid_during daterange NOT NULL,
  status text NOT NULL DEFAULT 'draft',
  review_status text NOT NULL DEFAULT 'pending' CHECK (review_status IN ('pending','approved','rejected')),
  reviewed_by text,
  reviewed_at timestamptz,
  created_at timestamptz NOT NULL DEFAULT now(),
  CHECK (lower(valid_during) < upper(valid_during) OR upper_inf(valid_during))
);
CREATE INDEX idx_eligibility_lookup ON policy.eligibility_rule
  (certificate_id, region_code, degree_level_code, major_category_code)
  WHERE status = 'published' AND review_status = 'approved';

CREATE TABLE policy.eligibility_rule_evidence (
  eligibility_rule_id bigint NOT NULL REFERENCES policy.eligibility_rule(id) ON DELETE CASCADE,
  clause_id bigint NOT NULL REFERENCES policy.clause(id),
  evidence_role text NOT NULL CHECK (evidence_role IN ('primary','supporting','exception')),
  PRIMARY KEY (eligibility_rule_id, clause_id)
);

CREATE TABLE assessment.exam_event (
  id bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
  code text NOT NULL UNIQUE,
  certificate_id bigint NOT NULL REFERENCES core.certificate(id),
  exam_year integer NOT NULL CHECK (exam_year BETWEEN 2000 AND 2100),
  region_code text NOT NULL DEFAULT 'CN',
  status text NOT NULL DEFAULT 'scheduled',
  UNIQUE (certificate_id, exam_year, region_code)
);

CREATE TABLE assessment.exam_phase (
  id bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
  exam_event_id bigint NOT NULL REFERENCES assessment.exam_event(id) ON DELETE CASCADE,
  phase_type text NOT NULL CHECK (phase_type IN ('registration','practical','written','interview','result')),
  starts_on date NOT NULL,
  ends_on date,
  note text,
  UNIQUE (exam_event_id, phase_type, starts_on),
  CHECK (ends_on IS NULL OR starts_on <= ends_on)
);

CREATE TABLE assessment.subject_score_rule (
  id bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
  exam_event_id bigint NOT NULL REFERENCES assessment.exam_event(id) ON DELETE CASCADE,
  subject_id bigint NOT NULL REFERENCES core.exam_subject(id),
  full_mark numeric(8,2) NOT NULL CHECK (full_mark > 0),
  pass_mark numeric(8,2) NOT NULL CHECK (pass_mark BETWEEN 0 AND full_mark),
  UNIQUE (exam_event_id, subject_id)
);

CREATE TABLE assessment.paper (
  id bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
  code text NOT NULL UNIQUE,
  paper_type text NOT NULL CHECK (paper_type IN ('official','mock','chapter_test')),
  certificate_id bigint NOT NULL REFERENCES core.certificate(id),
  subject_id bigint REFERENCES core.exam_subject(id),
  exam_year integer,
  source_asset_id bigint REFERENCES knowledge.asset(id),
  owner_org_id bigint NOT NULL REFERENCES iam.organization_unit(id),
  review_status text NOT NULL DEFAULT 'pending'
);

CREATE TABLE assessment.question (
  id bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
  paper_id bigint NOT NULL REFERENCES assessment.paper(id) ON DELETE CASCADE,
  question_no text NOT NULL,
  question_type text NOT NULL CHECK (question_type IN ('single','multiple','true_false','case','essay')),
  content text NOT NULL,
  options jsonb,
  answer jsonb NOT NULL,
  analysis text,
  difficulty smallint CHECK (difficulty BETWEEN 1 AND 5),
  review_status text NOT NULL DEFAULT 'pending',
  UNIQUE (paper_id, question_no),
  CHECK (options IS NULL OR jsonb_typeof(options) = 'object'),
  CHECK (jsonb_typeof(answer) IN ('array','string','object'))
);

CREATE TABLE assessment.question_knowledge_point (
  question_id bigint NOT NULL REFERENCES assessment.question(id) ON DELETE CASCADE,
  kp_id bigint NOT NULL REFERENCES knowledge.knowledge_point(id),
  role text NOT NULL CHECK (role IN ('primary','secondary')),
  score_weight numeric(6,3) CHECK (score_weight IS NULL OR score_weight BETWEEN 0 AND 1),
  PRIMARY KEY (question_id, kp_id)
);

CREATE TABLE generation.run (
  id bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
  application_code text NOT NULL,
  user_code text NOT NULL,
  model_provider text NOT NULL,
  model_name text NOT NULL,
  prompt_version text NOT NULL,
  confidentiality text NOT NULL,
  status text NOT NULL,
  created_at timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE generation.citation (
  generation_run_id bigint NOT NULL REFERENCES generation.run(id) ON DELETE CASCADE,
  fragment_id bigint NOT NULL REFERENCES knowledge.fragment(id),
  citation_order integer NOT NULL,
  usage_type text NOT NULL DEFAULT 'reference',
  PRIMARY KEY (generation_run_id, fragment_id)
);

CREATE TABLE generation.output (
  id bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
  generation_run_id bigint NOT NULL REFERENCES generation.run(id),
  output_type text NOT NULL,
  content jsonb NOT NULL,
  confidentiality text NOT NULL,
  status text NOT NULL DEFAULT 'draft' CHECK (status IN ('draft','reviewed','approved','rejected')),
  approved_by text,
  approved_at timestamptz,
  created_at timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE analytics.post (
  id bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
  platform text NOT NULL,
  external_post_id text NOT NULL,
  certificate_id bigint REFERENCES core.certificate(id),
  title text NOT NULL,
  content text,
  published_at timestamptz,
  url text,
  UNIQUE (platform, external_post_id)
);

CREATE TABLE analytics.post_metric_snapshot (
  post_id bigint NOT NULL REFERENCES analytics.post(id) ON DELETE CASCADE,
  collected_at timestamptz NOT NULL,
  views bigint NOT NULL DEFAULT 0 CHECK (views >= 0),
  likes bigint NOT NULL DEFAULT 0 CHECK (likes >= 0),
  collects bigint NOT NULL DEFAULT 0 CHECK (collects >= 0),
  comments bigint NOT NULL DEFAULT 0 CHECK (comments >= 0),
  leads bigint NOT NULL DEFAULT 0 CHECK (leads >= 0),
  PRIMARY KEY (post_id, collected_at)
);

CREATE TABLE ingestion.import_batch (
  id bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
  filename text NOT NULL,
  content_sha256 text NOT NULL,
  imported_by text NOT NULL,
  status text NOT NULL CHECK (status IN ('uploaded','validating','failed','committed')),
  total_rows integer NOT NULL DEFAULT 0,
  success_rows integer NOT NULL DEFAULT 0,
  failed_rows integer NOT NULL DEFAULT 0,
  imported_at timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE ingestion.validation_error (
  id bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
  batch_id bigint NOT NULL REFERENCES ingestion.import_batch(id) ON DELETE CASCADE,
  row_number integer,
  field_name text,
  error_code text NOT NULL,
  error_message text NOT NULL
);
