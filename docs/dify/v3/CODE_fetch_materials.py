"""
CODE_素材检索 — Dify Workflow 节点 ②

职责：根据选题参数查询 policy_fact 数据库，获取：
  1. 结构化政策事实（报考条件 / 考试时间 / 合格标准 / 注册政策 / 免考）
  2. 可引用政策条款原文
  3. 高频考点 + 真题（知识注入，提升文章干货密度）
  4. 爆款样本（few-shot 风格参考）

输出：结构化 JSON，供后续标题生成 + 正文生成 + 事实校验节点使用。

使用方式：
  将本文件全部内容粘贴到 Dify Workflow 的 Code 节点中。
  Code 节点配置：
  - 输入变量：cert_id, topic, audience, article_count
  - 输出变量：policy_json (str), knowledge_json (str), viral_samples_json (str), brief_json (str)

依赖：无外部 pip 包。通过 Python 内置 urllib 调用 policy-api 桥接服务。
     Dify Worker 容器需能访问 policy-api:8400（docker network connect 打通）。
"""

import json
import urllib.error
import urllib.request

# ── API 地址（Dify Worker 容器内部 DNS）──
API_BASE = "http://policy-api:8400"


def _api_post(endpoint: str, data: dict) -> dict:
    """调用 policy-api HTTP 接口。失败返回空结构，不抛异常。"""
    try:
        body = json.dumps(data).encode("utf-8")
        req = urllib.request.Request(
            f"{API_BASE}{endpoint}",
            data=body,
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        with urllib.request.urlopen(req, timeout=15) as resp:
            return json.loads(resp.read().decode("utf-8"))
    except (urllib.error.URLError, urllib.error.HTTPError, json.JSONDecodeError, OSError):
        return {}


def query_policy_facts(cert_id: str) -> dict:
    """查询指定证书的所有政策事实（通过 HTTP API）。"""
    result = _api_post("/query/policy", {"cert_id": cert_id})
    if not result:
        return {
            "cert_id": cert_id,
            "cert_name": cert_id,
            "short_name": cert_id,
            "issuing_authority": "",
            "profession_category": "",
            "exam_conditions": [],
            "exam_schedules": [],
            "score_rules": [],
            "registration_policies": [],
            "exemptions": [],
            "policy_clauses": [],
        }
    return result


def query_viral_samples(cert_id: str, limit: int = 8) -> list[dict]:
    """查询指定证书的爆款笔记样本（通过 HTTP API）。"""
    result = _api_post("/query/viral", {"cert_id": cert_id, "limit": limit})
    if not result:
        return []
    return result.get("samples", [])


def query_knowledge(cert_id: str, kp_limit: int = 10, q_limit: int = 5) -> dict:
    """查询考试科目 + 高频考点 + 真题（通过 HTTP API）。"""
    result = _api_post(
        "/query/knowledge",
        {"cert_id": cert_id, "kp_limit": kp_limit, "question_limit": q_limit},
    )
    if not result:
        return {
            "subjects": [],
            "knowledge_points": [],
            "exam_questions": [],
            "subject_count": 0,
            "kp_count": 0,
            "question_count": 0,
        }
    return result


def build_brief(policy: dict, knowledge: dict | None = None) -> str:
    """将政策事实 + 知识数据压缩为一段摘要文本，注入到标题/正文生成 prompt 中。"""

    parts = []

    cert_name = policy.get("cert_name", "")
    short_name = policy.get("short_name", "")
    parts.append(f"证书：{cert_name}（{short_name}）")
    parts.append(f"颁发机构：{policy.get('issuing_authority', '')}")

    # ── 报考条件摘要 ──
    conditions = policy.get("exam_conditions", [])
    if conditions:
        lines = ["报考条件："]
        for c in conditions:
            degree = c.get("degree_level", "")
            major = c.get("major_category", "")
            work = c.get("work_years_construction", "")
            total = c.get("total_work_years", "")
            note = c.get("note", "")
            entry = f"  {degree}·{major}"
            if work:
                entry += f"·从事相关工作满{work}年"
            if total:
                entry += f"·工作满{total}年"
            if note:
                entry += f"（{note}）"
            lines.append(entry)
        parts.append("\n".join(lines))

    # ── 考试时间 ──
    schedules = policy.get("exam_schedules", [])
    if schedules:
        s = schedules[0]
        year = s.get("year", "")
        exam_d = s.get("exam_date", "")
        reg_s = s.get("registration_start", "")
        reg_e = s.get("registration_end", "")
        if exam_d:
            parts.append(f"最新考试时间：{exam_d}（{year}年）")
        if reg_s and reg_e:
            parts.append(f"报名时间：{reg_s} 至 {reg_e}")

    # ── 合格标准 ──
    scores = policy.get("score_rules", [])
    if scores:
        for sc in scores:
            parts.append(
                f"合格标准：{sc.get('rule_description', '')}"
                f"（{sc.get('rolling_period', '')}）"
            )

    # ── 政策条款引用（⚠ 必须在正文中标注文件名+条款号）──
    clauses = policy.get("policy_clauses", [])
    if clauses:
        lines = ["【必须在正文中引用的政策依据——标注文件名+条款号】"]
        for c in clauses[:5]:
            doc_title = c.get("doc_title", "")
            section = c.get("clause_section", "")
            summary = c.get("clause_summary", "")
            lines.append(f"  《{doc_title}》{section}：{summary}")
        parts.append("\n".join(lines))

    # ── ★ P0 新增：高频考点 + 真题（知识注入）──
    if knowledge:
        kps = knowledge.get("knowledge_points", [])
        questions = knowledge.get("exam_questions", [])
        subjects = knowledge.get("subjects", [])

        # 考试科目概览
        if subjects:
            lines = ["【考试科目——分值分布】"]
            for s in subjects:
                lines.append(
                    f"  {s.get('subject_name', '')}（{s.get('full_mark', '')}分）"
                    f"——{s.get('question_types', '')}"
                )
            parts.append("\n".join(lines))

        # 高频考点（按频次排序，告诉 LLM 哪些是重点）
        if kps:
            lines = ["【高频考点——正文中优先覆盖这些内容】"]
            for k in kps:
                freq = k.get("frequency", "")
                name = k.get("kp_name", "")
                note = k.get("note", "")
                chapter = k.get("kp_chapter", "")
                line = f"  [{freq}] {name}"
                if chapter:
                    line += f"（{chapter}）"
                if note:
                    line += f"——{note}"
                lines.append(line)
            parts.append("\n".join(lines))

        # 真题示例（展示出题角度，帮助 LLM 写出"像考过的"的内容）
        if questions:
            lines = ["【真题示例——参考出题角度，不要照抄】"]
            for q in questions:
                qtype = q.get("question_type", "")
                year = q.get("exam_year", "")
                content = q.get("content", "")[:80]
                analysis = q.get("analysis", "")[:80]
                lines.append(
                    f"  [{qtype}·{year}] {content}"
                )
                if analysis:
                    lines.append(f"    解析：{analysis}")
            parts.append("\n".join(lines))

        # 使用指南
        parts.append(
            "【使用指南】"
            "1. 正文中至少覆盖 3 个高频考点, 提到时用考点原名(如「心血管系统疾病」) "
            "2. 每个政策性结论后面标【依据: 《XX法》第X条】 "
            "3. 真题只用于参考出题角度, 不要在正文中照搬题目 "
            "4. 高频考点之间要有逻辑过渡, 不要像列清单"
        )

    return "\n\n".join(parts)


def main(
    cert_id: str,
    topic: str = "",
    audience: str = "在职备考",
    article_count: int = 1,
) -> dict:
    """
    素材检索主函数。

    参数：
      cert_id:      证书 ID（如 physician_licensed / pharmacist_licensed / nle）
      topic:        选题方向（如 "技能考试备考" "报名条件解读" "冲刺攻略"）
      audience:     目标受众（在职备考 / 宝妈备考 / 零基础 / 非科班）
      article_count: 生成文章数量（默认 1）

    返回：
      policy_json:        政策事实 JSON 字符串
      knowledge_json:     知识点 JSON 字符串（P0 新增）
      viral_samples_json: 爆款样本 JSON 字符串
      brief_json:         政策 + 知识摘要文本（供 LLM prompt 注入）
      cert_name:          证书中文名
    """

    try:
        # 1. 查政策事实（通过 HTTP API → policy-api:8400）
        policy = query_policy_facts(cert_id)

        # 2. 查知识点 + 真题（P0 新增）
        knowledge = query_knowledge(cert_id)

        # 3. 查爆款样本（按 article_count 动态调整，最少 3 篇）
        sample_limit = max(3, article_count * 3)
        viral_samples = query_viral_samples(cert_id, sample_limit)

        # 4. 构造摘要（政策 + 知识合并）
        brief = build_brief(policy, knowledge)

        return {
            "policy_json": json.dumps(policy, ensure_ascii=False, default=str),
            "knowledge_json": json.dumps(knowledge, ensure_ascii=False, default=str),
            "viral_samples_json": json.dumps(viral_samples, ensure_ascii=False, default=str),
            "brief_json": brief,
            "cert_name": policy.get("cert_name", cert_id),
        }

    except Exception as e:
        # API 调用失败 → 降级为空数据，让 LLM 用训练知识自由生成
        error_msg = (
            f"⚠️ 无法连接政策数据库 API（{e}）。"
            f"本次生成将使用 LLM 训练知识，政策数据可能不准确。"
        )
        return {
            "policy_json": "{}",
            "knowledge_json": "{}",
            "viral_samples_json": "[]",
            "brief_json": error_msg,
            "cert_name": cert_id,
        }
