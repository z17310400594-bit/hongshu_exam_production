"""
CODE_0_db — 数据库注入预处理（卡片生成 Workflow 新增节点）

职责：
  1. 接收前端 exam_name → 调 policy-api 做模糊查找 → 解析 cert_id
  2. 命中 → 调 policy / knowledge / viral 获取全量数据
  3. 未命中 → 返回空 JSON，后续节点走旧逻辑（LLM 自由生成）

使用方式：
  将本文件全部内容粘贴到 Dify Workflow 的 Code 节点。
  Code 节点配置：
  - 输入变量：exam_name
  - 输出变量：db_data_json (str), db_matched (str), resolved_cert_id (str)

依赖：无外部 pip 包。通过 Python 内置 urllib 调用 policy-api 桥接服务。
      Dify Worker 容器需能访问 policy-api:8400。
"""

import json
import urllib.error
import urllib.request

API_BASE = "http://policy-api:8400"


def _api_post(endpoint, data):
    """调 policy-api POST 接口。失败返回空结构，不抛异常。"""
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


def lookup_cert(exam_name):
    """exam_name → cert_id 查找。返回 {matched, cert_id, cert_name} 或 None。"""
    result = _api_post("/query/cert_lookup", {"exam_name": exam_name})
    if not result or not result.get("matched"):
        return None
    return result


def query_all(cert_id, exam_name):
    """查询指定证书的全部可用数据（不再丢弃任何 API 返回字段）。"""
    policy = _api_post("/query/policy", {"cert_id": cert_id})
    knowledge = _api_post("/query/knowledge", {"cert_id": cert_id})
    viral = _api_post("/query/viral", {"cert_id": cert_id, "limit": 5})

    # ── 政策数据 ──
    schedule = (
        policy.get("exam_schedules", [None])[0]
        if policy.get("exam_schedules")
        else None
    )

    # ── 爆款数据：不只取 tags，保留标题/正文/封面/类型/互动数据 ──
    viral_samples = []
    viral_tags = []
    for v in viral.get("samples", []):
        tags = v.get("tags", [])
        if isinstance(tags, list):
            viral_tags.extend(tags)
        viral_samples.append({
            "title": v.get("title", ""),
            "content": (v.get("content", "") or "")[:300],  # 截断，避免 prompt 爆炸
            "cover_text": v.get("cover_text", ""),
            "topic_type": v.get("topic_type", ""),
            "views": v.get("views", 0),
            "likes": v.get("likes", 0),
            "collects": v.get("collects", 0),
            "note": v.get("note", ""),
        })
    viral_tags = list(set(viral_tags))[:10]

    # ── 真题数据 ──
    exam_questions = knowledge.get("exam_questions", [])

    db_data = {
        # 基础信息
        "cert_name": policy.get("cert_name", exam_name),
        "short_name": policy.get("short_name", ""),
        "issuing_authority": policy.get("issuing_authority", ""),
        "profession_category": policy.get("profession_category", ""),

        # 考试安排
        "schedule": schedule,

        # 科目 & 考点 & 真题
        "subjects": knowledge.get("subjects", []),
        "knowledge_points": knowledge.get("knowledge_points", []),
        "exam_questions": exam_questions,

        # 政策规则
        "score_rules": policy.get("score_rules", []),
        "policy_clauses": policy.get("policy_clauses", []),
        "exam_conditions": policy.get("exam_conditions", []),
        "exemptions": policy.get("exemptions", []),
        "registration_policies": policy.get("registration_policies", []),

        # 爆款
        "viral_tags": viral_tags,
        "viral_samples": viral_samples,
        "viral_count": len(viral_samples),
        "question_count": len(exam_questions),
    }

    return db_data


def summarize_for_llm(db_data):
    """将结构化 db_data 提炼为 LLM 友好的事实摘要（纯文本，≤1500 字）。

    策略：
      - 事实类数据（日期、分数线）→ 直接转自然语句
      - 真题 → 提取考法特征 + 保留关键原文
      - 爆款 → 只提取规律和模式，不堆砌原文
      - 考点 → 按频率分层，标注考法方向
    """
    lines = []

    # ── 1. 基本信息 ──
    cert_name = db_data.get("cert_name", "")
    short = db_data.get("short_name", "")
    authority = db_data.get("issuing_authority", "")
    category = db_data.get("profession_category", "")
    lines.append(f"## 考试基本信息")
    lines.append(f"- 证书全称：{cert_name}" + (f"（简称：{short}）" if short else ""))
    if authority:
        lines.append(f"- 发证机关：{authority}")
    if category:
        lines.append(f"- 行业分类：{category}")

    # ── 2. 关键数字（必须准确）──
    schedule = db_data.get("schedule")
    score_rules = db_data.get("score_rules", [])
    conditions = db_data.get("exam_conditions", [])

    lines.append(f"\n## 关键数字（必须准确）")

    if schedule:
        exam_date = schedule.get("exam_date", "")
        reg_start = schedule.get("registration_start", "")
        reg_end = schedule.get("registration_end", "")
        result_date = schedule.get("result_date", "")
        if exam_date:
            lines.append(f"- 考试日期：{exam_date}")
        if reg_start and reg_end:
            lines.append(f"- 报名时间：{reg_start} 至 {reg_end}")
        if result_date:
            lines.append(f"- 成绩公布：{result_date}")

    for s in score_rules:
        period = s.get("rolling_period", "")
        desc = s.get("rule_description", "")
        if period or desc:
            lines.append(f"- 合格标准：{period}，{desc}")

    for c in conditions:
        degree = c.get("degree_level", "")
        major = c.get("major_category", "")
        wy = c.get("work_years_construction", 0)
        twy = c.get("total_work_years", 0)
        if degree:
            parts = [degree]
            if major:
                parts.append(major)
            if wy and int(wy) > 0:
                parts.append(f"相关工作 {wy} 年")
            if twy and int(twy) > 0:
                parts.append(f"总工作年限 {twy} 年")
            lines.append(f"- 报考条件：{'·'.join(parts)}")

    # 免考
    exemptions = db_data.get("exemptions", [])
    for e in exemptions:
        cond = e.get("condition_description", "")
        exempt = e.get("exempt_subjects", "")
        if cond:
            line = f"- 免考：{cond}"
            if exempt:
                line += f" → 免考 {exempt}"
            lines.append(line)

    # 注册政策
    regs = db_data.get("registration_policies", [])
    for r in regs:
        init_reg = r.get("initial_reg_period", "")
        renewal = r.get("renewal_period", "")
        ce = r.get("ce_hours", "")
        if init_reg:
            line = f"- 注册：初始有效期 {init_reg}"
            if renewal:
                line += f"，续证周期 {renewal}"
            if ce:
                line += f"，继续教育 {ce} 学时"
            lines.append(line)

    # ── 3. 高频考点（分层 + 考法方向）──
    kps = db_data.get("knowledge_points", [])
    if kps:
        lines.append(f"\n## 高频考点 TOP {min(len(kps), 8)}")
        high = [k for k in kps if k.get("frequency") == "高频"]
        mid = [k for k in kps if k.get("frequency") == "中频"]
        others = [k for k in kps if k.get("frequency") not in ("高频", "中频")]
        for label, group in [("高频", high), ("中频", mid), ("其他", others)]:
            if not group:
                continue
            for k in group[:5]:
                kp_name = k.get("kp_name", "")
                subject = k.get("subject_name", "")
                note = k.get("note", "")
                parts = [f"- [{label}] {kp_name}"]
                if subject:
                    parts.append(f"（{subject}）")
                if note:
                    parts.append(f"→ {note}")
                lines.append("".join(parts))
            if len(group) > 5:
                lines.append(f"  ... 还有 {len(group) - 5} 个{label}考点")

    # ── 4. 真题特征 ──
    questions = db_data.get("exam_questions", [])
    if questions:
        lines.append(f"\n## 真题特征（共 {len(questions)} 道）")
        # 统计题型分布
        qtype_count = {}
        subject_count = {}
        years = set()
        for q in questions:
            qt = q.get("question_type", "未知")
            qtype_count[qt] = qtype_count.get(qt, 0) + 1
            subj = q.get("subject_name", "未知")
            subject_count[subj] = subject_count.get(subj, 0) + 1
            yr = q.get("exam_year", "")
            if yr:
                years.add(str(yr))
        if qtype_count:
            qtype_str = " / ".join(f"{t} {c}道" for t, c in sorted(qtype_count.items(), key=lambda x: -x[1]))
            lines.append(f"- 题型分布：{qtype_str}")
        if subject_count:
            top_subjects = sorted(subject_count.items(), key=lambda x: -x[1])[:3]
            lines.append(f"- 高频科目：{' > '.join(f'{s}({c}道)' for s, c in top_subjects)}")
        if years:
            lines.append(f"- 覆盖年份：{min(years)}-{max(years)}")

        # 挑 3 道代表性真题，附考法提炼
        lines.append(f"\n代表性真题（附考法提示）：")
        for q in questions[:3]:
            qt = q.get("question_type", "")
            year = q.get("exam_year", "")
            subject = q.get("subject_name", "")
            content = (q.get("content", "") or "")[:120]
            analysis = (q.get("analysis", "") or "")[:80]
            lines.append(f"- [{year}年][{qt}][{subject}] {content}")
            if analysis:
                lines.append(f"  考法提示：{analysis}")

    # ── 5. 爆款规律 ──
    viral = db_data.get("viral_samples", [])
    viral_tags = db_data.get("viral_tags", [])
    if viral:
        lines.append(f"\n## 爆款内容规律（{len(viral)} 条样本）")
        # 统计互动数据
        avg_likes = sum(v.get("likes", 0) for v in viral) // max(len(viral), 1)
        avg_collects = sum(v.get("collects", 0) for v in viral) // max(len(viral), 1)
        types = set(v.get("topic_type", "") for v in viral if v.get("topic_type"))
        lines.append(f"- 平均互动：{avg_likes} 赞 / {avg_collects} 收藏")
        if types:
            lines.append(f"- 选题类型分布：{'、'.join(types)}")
        if viral_tags:
            lines.append(f"- 常用标签：{'、'.join(viral_tags[:8])}")

        lines.append(f"\n代表性爆款标题：")
        for v in viral[:3]:
            title = v.get("title", "")
            likes = v.get("likes", 0)
            collects = v.get("collects", 0)
            if title:
                lines.append(f"- {title}（{likes}赞 {collects}收藏）")

        # 提取标题模式规律
        title_patterns = []
        for v in viral:
            t = v.get("title", "")
            if "天" in t and any(c.isdigit() for c in t):
                title_patterns.append("数字+时间紧迫感")
                break
        for v in viral:
            t = v.get("title", "")
            if any(kw in t for kw in ("0基础", "零基础", "小白", "新手")):
                title_patterns.append("身份标签+痛点")
                break
        for v in viral:
            t = v.get("title", "")
            if any(kw in t for kw in ("一次", "上岸", "通过", "拿证", "过考")):
                title_patterns.append("成果承诺")
                break
        if title_patterns:
            lines.append(f"- 标题模式：{' + '.join(title_patterns)}")

    return "\n".join(lines)


def main(exam_name: str = "") -> dict:
    """
    参数：
      exam_name:  考试类型名称（来自 START.exam_name），如 "执业医师资格证"

    返回：
      db_data_json:     命中 → 完整 JSON 字符串；未命中 → "{}"
      db_matched:       "true" / "false"
      resolved_cert_id:  解析到的 cert_id（未命中为空串）
      facts_brief:       LLM 友好的纯文本事实摘要（≤1500字）
    """
    # 空输入直接降级
    if not exam_name or not exam_name.strip():
        return {
            "db_data_json": "{}",
            "db_matched": "false",
            "resolved_cert_id": "",
            "facts_brief": "",
        }

    # 1. 查找 cert_id
    cert = lookup_cert(exam_name.strip())

    if not cert:
        return {
            "db_data_json": "{}",
            "db_matched": "false",
            "resolved_cert_id": "",
            "facts_brief": "",
        }

    cert_id = cert.get("cert_id", "")

    # 2. 查询全量数据
    db_data = query_all(cert_id, exam_name)

    # 3. 提炼 LLM 友好摘要
    facts_brief = summarize_for_llm(db_data)

    return {
        "db_data_json": json.dumps(db_data, ensure_ascii=False),
        "db_matched": "true",
        "resolved_cert_id": cert_id,
        "facts_brief": facts_brief,
    }
