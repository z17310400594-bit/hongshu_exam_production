"""
policy_api.py — 政策事实库 HTTP API 桥接层

为 Dify Code 节点提供 PostgreSQL 政策数据的 HTTP 查询接口。
Dify Worker 容器无法装 pip 包，Code 节点只用 Python 内置 urllib 调本 API。

运行方式:
  docker build -t policy-api -f Dockerfile.api .
  docker run -d --name policy-api --network docker_default -p 8400:8400 policy-api

接口:
  GET  /health               健康检查
  GET  /query/certs          返回所有证书列表（供前端下拉框）
  POST /query/cert_lookup    exam_name → cert_id 模糊匹配
  POST /query/policy         查政策事实（报考条件/时间/合格标准/注册/免考/条款）
  POST /query/viral          查爆款样本
  POST /query/knowledge      查考试科目 + 高频考点 + 真题
  POST /query/fact_check     事实校验（正文 vs 数据库比对）
"""

from __future__ import annotations

import json
import os
import re
from contextlib import contextmanager
from datetime import date, datetime
from typing import Any

import pg8000
from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

# ── 配置 ──────────────────────────────────────────────
DB_CONFIG = {
    "host": os.getenv("DB_HOST", "policy-db"),
    "port": int(os.getenv("DB_PORT", "5432")),
    "database": os.getenv("DB_NAME", "policy_fact"),
    "user": os.getenv("DB_USER", "policy"),
    "password": os.getenv("DB_PASSWORD", "policy123"),
}
API_PORT = int(os.getenv("API_PORT", "8400"))

app = FastAPI(title="Policy Fact API", version="1.0.0")
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])


# ── 数据库连接 ────────────────────────────────────────
_conn_pool: list[Any] = []


@contextmanager
def get_conn():
    """获取数据库连接。优先复用，失败则新建。"""
    conn = None
    try:
        if _conn_pool:
            conn = _conn_pool.pop()
            try:
                conn.execute_simple("SELECT 1")
            except Exception:
                conn.close()
                conn = None
        if conn is None:
            conn = pg8000.connect(**DB_CONFIG)
        yield conn
    except pg8000.Error as e:
        raise HTTPException(status_code=503, detail=f"数据库不可用: {e}")
    finally:
        if conn and len(_conn_pool) < 5:
            _conn_pool.append(conn)
        elif conn:
            conn.close()


def _query(conn, sql: str, params: tuple = ()) -> list[dict]:
    """执行查询，返回 dict 列表。"""
    try:
        cur = conn.cursor()
        cur.execute(sql, params)
        columns = [d[0] for d in cur.description] if cur.description else []
        rows = []
        for row in cur.fetchall():
            rows.append(dict(zip(columns, [str(v) if isinstance(v, (date, datetime)) else v for v in row])))
        cur.close()
        return rows
    except Exception as e:
        import traceback, sys
        print(f"[_query ERROR] {e}", file=sys.stderr)
        traceback.print_exc(file=sys.stderr)
        return []


# ── 请求/响应模型 ─────────────────────────────────────
class CertRequest(BaseModel):
    cert_id: str


class ViralRequest(BaseModel):
    cert_id: str
    limit: int = 8


class FactCheckRequest(BaseModel):
    body_text: str
    cert_id: str


class KnowledgeRequest(BaseModel):
    cert_id: str
    kp_limit: int = 10
    question_limit: int = 5


class CertLookupRequest(BaseModel):
    exam_name: str


# ── 接口 ──────────────────────────────────────────────

@app.get("/health")
def health():
    try:
        with get_conn() as conn:
            conn.execute_simple("SELECT 1")
        return {"status": "ok", "database": "connected"}
    except Exception as e:
        return {"status": "error", "detail": str(e)}


@app.post("/query/policy")
def query_policy(req: CertRequest):
    """查询指定证书的全部政策事实。"""
    with get_conn() as conn:
        cert_info = _query(
            conn,
            "SELECT cert_id, cert_name, short_name, issuing_authority, "
            "exam_authority, profession_category FROM cert_basic WHERE cert_id = %s",
            (req.cert_id,),
        )
        if not cert_info:
            raise HTTPException(status_code=404, detail=f"未找到证书: {req.cert_id}")

        conditions = _query(
            conn,
            "SELECT degree_level, major_category, work_years_construction, "
            "total_work_years, note, source_clause_id "
            "FROM exam_condition WHERE cert_id = %s ORDER BY degree_level",
            (req.cert_id,),
        )
        schedules = _query(
            conn,
            "SELECT year, registration_start, registration_end, exam_date, "
            "result_date, region_note "
            "FROM exam_schedule WHERE cert_id = %s ORDER BY year DESC LIMIT 2",
            (req.cert_id,),
        )
        scores = _query(
            conn,
            "SELECT rolling_period, rule_description, source_clause_id "
            "FROM score_management WHERE cert_id = %s",
            (req.cert_id,),
        )
        regs = _query(
            conn,
            "SELECT initial_reg_period, renewal_period, ce_hours, ce_note, source_clause_id "
            "FROM registration_policy WHERE cert_id = %s",
            (req.cert_id,),
        )
        exemptions = _query(
            conn,
            "SELECT condition_description, exempt_subjects, remaining_subjects, source_clause_id "
            "FROM exemption WHERE cert_id = %s",
            (req.cert_id,),
        )
        clauses = _query(
            conn,
            "SELECT DISTINCT pc.clause_section, pc.clause_text, pc.clause_summary, "
            "pd.doc_title, pd.doc_number, pd.publish_date "
            "FROM policy_clause pc "
            "LEFT JOIN policy_doc pd ON pc.doc_id = pd.doc_id "
            "WHERE (pc.relates_to_type = 'cert' AND pc.relates_to_id = %s) "
            "   OR (pc.relates_to_type = 'condition' AND pc.relates_to_id IN "
            "       (SELECT condition_id FROM exam_condition WHERE cert_id = %s)) "
            "LIMIT 10",
            (req.cert_id, req.cert_id),
        )

    cert = cert_info[0]

    return {
        "cert_id": cert.get("cert_id", ""),
        "cert_name": cert.get("cert_name", ""),
        "short_name": cert.get("short_name", ""),
        "issuing_authority": cert.get("issuing_authority", ""),
        "profession_category": cert.get("profession_category", ""),
        "exam_conditions": conditions,
        "exam_schedules": schedules,
        "score_rules": scores,
        "registration_policies": regs,
        "exemptions": exemptions,
        "policy_clauses": clauses,
    }


@app.post("/query/viral")
def query_viral(req: ViralRequest):
    """查询指定证书的爆款笔记样本。"""
    limit = min(req.limit, 20)
    with get_conn() as conn:
        rows = _query(
            conn,
            "SELECT post_id, title, content, cover_text, tags, topic_type, "
            "views, likes, collects, comments, is_viral, note "
            "FROM viral_post WHERE cert_id = %s AND is_viral = TRUE "
            "ORDER BY likes DESC, collects DESC LIMIT %s",
            (req.cert_id, limit),
        )
    # tags 是 JSONB 文本，尝试解析
    for r in rows:
        tags_val = r.get("tags", "[]")
        if isinstance(tags_val, str):
            try:
                r["tags"] = json.loads(tags_val)
            except json.JSONDecodeError:
                r["tags"] = []
    return {"samples": rows, "count": len(rows)}


@app.post("/query/knowledge")
def query_knowledge(req: KnowledgeRequest):
    """查询指定证书的考试科目 + 高频考点 + 真题。"""
    with get_conn() as conn:
        subjects = _query(
            conn,
            "SELECT subject_name, full_mark, pass_mark, question_types, exam_duration "
            "FROM exam_subject WHERE cert_id = %s ORDER BY full_mark DESC",
            (req.cert_id,),
        )
        kps = _query(
            conn,
            "SELECT kp.kp_name, kp.frequency, kp.kp_chapter, kp.note, s.subject_name "
            "FROM knowledge_point kp "
            "LEFT JOIN exam_subject s ON kp.subject_id = s.subject_id "
            "WHERE kp.cert_id = %s "
            "ORDER BY CASE kp.frequency WHEN '高频' THEN 1 WHEN '中频' THEN 2 ELSE 3 END "
            "LIMIT %s",
            (req.cert_id, req.kp_limit),
        )
        questions = _query(
            conn,
            "SELECT eq.question_type, eq.exam_year, eq.content, eq.analysis, es.subject_name "
            "FROM exam_question eq "
            "LEFT JOIN exam_subject es ON eq.subject_id = es.subject_id "
            "WHERE eq.cert_id = %s "
            "ORDER BY eq.difficulty DESC, eq.exam_year DESC "
            "LIMIT %s",
            (req.cert_id, req.question_limit),
        )

    return {
        "subjects": subjects,
        "knowledge_points": kps,
        "exam_questions": questions,
        "subject_count": len(subjects),
        "kp_count": len(kps),
        "question_count": len(questions),
    }


@app.get("/query/certs")
def query_certs():
    """返回所有可用证书列表（供前端下拉框填充），含最近一次未来考试日期。"""
    with get_conn() as conn:
        rows = _query(
            conn,
            "SELECT cb.cert_id, cb.cert_name, cb.short_name, cb.issuing_authority, "
            "cb.profession_category, "
            "MIN(es.exam_date) FILTER (WHERE es.exam_date >= CURRENT_DATE) AS exam_date "
            "FROM cert_basic cb "
            "LEFT JOIN exam_schedule es ON cb.cert_id = es.cert_id "
            "GROUP BY cb.cert_id, cb.cert_name, cb.short_name, cb.issuing_authority, cb.profession_category "
            "ORDER BY cb.cert_id",
        )
    return {"certs": rows, "count": len(rows)}


@app.post("/query/cert_lookup")
async def cert_lookup(request: Request):
    """
    考试名 → cert_id 查找。三级匹配：精确 → 包含 → 未命中。
    命中返回 cert_id，未命中返回 matched=false。
    额外处理 Windows GBK 终端乱码。
    """
    # 从原始 body 解析，避免 FastAPI 自动 UTF-8 解码吞掉 GBK 字节
    body = await request.body()
    try:
        data = json.loads(body)
    except json.JSONDecodeError:
        # JSON 解析失败，尝试 GBK 解码后重试
        try:
            data = json.loads(body.decode("gbk"))
        except Exception:
            return {"matched": False, "cert_id": "", "cert_name": "", "short_name": ""}

    exam_name = data.get("exam_name", "").strip()
    if not exam_name:
        return {"matched": False, "cert_id": "", "cert_name": "", "short_name": ""}

    # 构建候选名列表——处理 GBK 终端发送的乱码
    candidates = [exam_name]
    # 尝试将字符串当 GBK 字节解释为 UTF-8 恢复
    try:
        recovered = exam_name.encode("raw_unicode_escape").decode("raw_unicode_escape")
        if recovered != exam_name:
            candidates.append(recovered)
    except Exception:
        pass
    # 直接尝试 GBK 解码原始 body
    try:
        alt_body = body.decode("gbk")
        alt_data = json.loads(alt_body)
        alt_name = alt_data.get("exam_name", "").strip()
        if alt_name and alt_name != exam_name:
            candidates.append(alt_name)
    except Exception:
        pass

    with get_conn() as conn:
        for name in candidates:
            # 1. 精确匹配 cert_name 或 short_name
            rows = _query(
                conn,
                "SELECT cert_id, cert_name, short_name FROM cert_basic "
                "WHERE cert_name = %s OR short_name = %s LIMIT 1",
                (name, name),
            )
            if rows:
                r = rows[0]
                print(f"[cert_lookup] MATCHED exact: '{name}' → {r['cert_id']}", flush=True)
                return {"matched": True, "cert_id": r["cert_id"], "cert_name": r["cert_name"], "short_name": r.get("short_name", "")}

            # 2. 双向包含匹配
            rows = _query(
                conn,
                "SELECT cert_id, cert_name, short_name FROM cert_basic "
                "WHERE %s LIKE '%%' || cert_name || '%%' "
                "   OR cert_name LIKE '%%' || %s || '%%' "
                "LIMIT 1",
                (name, name),
            )
            if rows:
                r = rows[0]
                print(f"[cert_lookup] MATCHED like: '{name}' → {r['cert_id']}", flush=True)
                return {"matched": True, "cert_id": r["cert_id"], "cert_name": r["cert_name"], "short_name": r.get("short_name", "")}

    # 3. 未命中
    print(f"[cert_lookup] NO MATCH: tried {candidates}", flush=True)
    return {"matched": False, "cert_id": "", "cert_name": "", "short_name": ""}


@app.post("/query/fact_check")
def fact_check(req: FactCheckRequest):
    """
    事实校验：将正文中的日期/数字/条件与数据库比对。
    返回逐条校验结果，status: pass / warning / fail / uncheckable。
    """
    with get_conn() as conn:
        schedules = _query(
            conn,
            "SELECT year, registration_start, registration_end, exam_date, result_date "
            "FROM exam_schedule WHERE cert_id = %s ORDER BY year DESC LIMIT 1",
            (req.cert_id,),
        )
        conditions = _query(
            conn,
            "SELECT degree_level, major_category, work_years_construction, total_work_years "
            "FROM exam_condition WHERE cert_id = %s",
            (req.cert_id,),
        )
        scores = _query(
            conn,
            "SELECT rolling_period, rule_description "
            "FROM score_management WHERE cert_id = %s",
            (req.cert_id,),
        )

    results: list[dict] = []
    text = req.body_text

    # 1. 考试日期
    if schedules:
        s = schedules[0]
        for label, field in [("考试日期", "exam_date"), ("报名开始", "registration_start"), ("报名截止", "registration_end")]:
            val = s.get(field, "")
            if val:
                _check_date(results, text, str(val), label)

    # 2. 工作年限
    for c in conditions:
        wy = c.get("work_years_construction", 0)
        if wy and int(wy) > 0:
            _check_number(results, text, str(wy), f"工作年限·{c.get('degree_level','')}·{c.get('major_category','')}", "年")

    # 3. 合格标准
    for sc in scores:
        rule = sc.get("rule_description", "")
        for match in re.findall(r"(\d+)\s*(分|%|年|次)", rule):
            _check_number(results, text, f"{match[0]}{match[1]}", f"合格标准·{match[0]}{match[1]}", match[1])

    warning_count = sum(1 for r in results if r["status"] in ("warning", "fail"))
    return {"results": results, "warning_count": warning_count, "checked_count": len(results)}


# ── 校验辅助 ──────────────────────────────────────────

def _check_date(results: list, text: str, expected: str, label: str):
    """检查日期是否在正文中出现。"""
    try:
        d = datetime.strptime(expected[:10], "%Y-%m-%d")
        variants = [
            d.strftime("%Y-%m-%d"), d.strftime("%Y年%m月%d日"),
            d.strftime("%m月%d日"), f"{d.month}.{d.day}", f"{d.month}月{d.day}日",
        ]
    except (ValueError, IndexError):
        return

    if any(v in text for v in variants):
        results.append({"claim_type": label, "policy_value": expected, "status": "pass", "note": f"{label}正确"})
    else:
        found = re.findall(r"(\d{4}[-/年]\d{1,2}[-/月]\d{1,2}[日]?)", text)
        results.append({
            "claim_type": label,
            "text_snippet": found[0] if found else "未提及",
            "policy_value": expected,
            "status": "warning" if found else "uncheckable",
            "note": f"{label}需核对" if found else f"{label}正文未提及",
        })


def _check_number(results: list, text: str, correct: str, label: str, unit: str):
    """检查数值是否匹配。"""
    nums = re.findall(rf"(\d+)\s*{re.escape(unit)}", text)
    correct_num = re.findall(r"\d+", correct)[0] if re.findall(r"\d+", correct) else correct
    if correct_num in nums:
        results.append({"claim_type": label, "policy_value": correct, "status": "pass", "note": f"{label}一致"})
    elif nums:
        results.append({"claim_type": label, "text_snippet": f"{nums[0]}{unit}", "policy_value": correct, "status": "warning", "note": f"{label}偏差，DB={correct}"})


# ── 启动 ──────────────────────────────────────────────

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=API_PORT)
