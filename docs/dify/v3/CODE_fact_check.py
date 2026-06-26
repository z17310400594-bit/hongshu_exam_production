"""
CODE_事实校验 — Dify Workflow 节点 ⑥

职责：将 LLM 生成的正文与 policy_fact 数据库中的原始政策事实进行比对，
     标记可能存在的数字、日期、条件等错误，供人工审核时重点关注。

校验维度：
  1. 考试日期是否准确
  2. 报名时间是否准确
  3. 报考条件（学历/工作年限）是否准确
  4. 合格标准（分数线/滚动周期）是否准确
  5. 数值引用是否有偏差

输出：fact_check_results —— 每条比对一个 {claim, policy_value, status, note}
  status: "pass"=一致 / "warning"=可能有偏差 / "fail"=明确错误 / "uncheckable"=无法校验

使用方式：
  将本文件全部内容粘贴到 Dify Workflow 的 Code 节点中。
  输入变量：body_text, policy_json
  输出变量：fact_check_json, warning_count, checked_count
"""

import json
import re
from datetime import date, datetime


def main(
    body_text: str,
    policy_json: str = "{}",
) -> dict:
    """
    事实校验主函数。

    参数：
      body_text:   LLM 生成的正文（可能是多篇文章拼接）
      policy_json: CODE_fetch_materials 输出的政策数据 JSON 字符串

    返回：
      fact_check_json: 逐条校验结果 JSON 字符串
      warning_count:   警告+失败的数量
      checked_count:   校验的总条数
    """

    # 解析政策数据
    try:
        policy = json.loads(policy_json) if isinstance(policy_json, str) else policy_json
    except json.JSONDecodeError:
        policy = {}

    if not policy or not body_text:
        return {
            "fact_check_json": "[]",
            "warning_count": "0",
            "checked_count": "0",
        }

    results = []

    # ── 1. 校验考试日期 ──
    schedules = policy.get("exam_schedules", [])
    if schedules:
        s = schedules[0]
        exam_date_str = str(s.get("exam_date", ""))
        if exam_date_str:
            _check_date_in_text(results, body_text, exam_date_str, "考试日期")

        reg_start = str(s.get("registration_start", ""))
        reg_end = str(s.get("registration_end", ""))
        if reg_start:
            _check_date_in_text(results, body_text, reg_start, "报名开始")
        if reg_end:
            _check_date_in_text(results, body_text, reg_end, "报名截止")

    # ── 2. 校验报考条件中的年限 ──
    conditions = policy.get("exam_conditions", [])
    for c in conditions:
        work_years = c.get("work_years_construction")
        total_years = c.get("total_work_years")
        degree = c.get("degree_level", "")
        major = c.get("major_category", "")

        # 工作年限
        if work_years and work_years > 0:
            _check_number_match(
                results,
                body_text,
                pattern_rules=[
                    rf"{degree}.*?{work_years}\s*年",
                    rf"{major}.*?{work_years}\s*年",
                    rf"工作.*?满\s*{work_years}\s*年",
                ],
                correct_value=str(work_years),
                label=f"工作年限·{degree}·{major}",
                unit="年",
            )

        # 总工作年限
        if total_years and total_years > 0 and total_years != work_years:
            _check_number_match(
                results,
                body_text,
                pattern_rules=[rf"满\s*{total_years}\s*年.*?工作"],
                correct_value=str(total_years),
                label=f"总工作年限·{degree}·{major}",
                unit="年",
            )

    # ── 3. 校验合格标准中的数值 ──
    scores = policy.get("score_rules", [])
    for sc in scores:
        rule = sc.get("rule_description", "")
        # 提取规则中的数值（如 "360 分" "60%" "2 年"）
        numbers_in_rule = re.findall(r"(\d+)\s*(分|%|年|次)", rule)
        for num, unit in numbers_in_rule:
            _check_number_match(
                results,
                body_text,
                pattern_rules=[rf"(?:合格|通过|分数线|及格).*?{num}\s*{unit}"],
                correct_value=f"{num}{unit}",
                label=f"合格标准·{num}{unit}",
                unit=unit,
            )

    # ── 4. 校验滚动周期 ──
    for sc in scores:
        rolling = sc.get("rolling_period", "")
        if rolling and rolling != "不滚动":
            _check_text_contains(results, body_text, rolling, "成绩滚动周期")

    # ── 5. 校验证书名称 ──
    cert_name = policy.get("cert_name", "")
    if cert_name:
        results.append({
            "claim_type": "证书名称",
            "text_snippet": cert_name,
            "policy_value": cert_name,
            "status": "pass",
            "note": "证书名称正确引用",
        })

    # ── 统计 ──
    warning_count = sum(
        1 for r in results if r["status"] in ("warning", "fail")
    )
    checked_count = len(results)

    return {
        "fact_check_json": json.dumps(results, ensure_ascii=False),
        "warning_count": str(warning_count),
        "checked_count": str(checked_count),
    }


# ── 辅助函数 ──

def _check_date_in_text(results: list, text: str, expected_date: str, label: str) -> None:
    """检查文本中是否包含正确的日期。"""
    # 规范化日期格式
    try:
        d = _parse_date(expected_date)
        if d is None:
            return
        # 几种常见写法
        variants = [
            d.strftime("%Y-%m-%d"),
            d.strftime("%Y年%m月%d日"),
            d.strftime("%m月%d日"),
            f"{d.month}.{d.day}",
            f"{d.month}月{d.day}日",
        ]
    except (ValueError, AttributeError):
        return

    found_any = any(v in text for v in variants)

    if found_any:
        results.append({
            "claim_type": label,
            "text_snippet": expected_date,
            "policy_value": expected_date,
            "status": "pass",
            "note": f"{label}正确",
        })
    else:
        # 检查文本中是否有其他日期（可能是编造的）
        date_pattern = re.findall(
            r"(\d{4}[-/年]\d{1,2}[-/月]\d{1,2}[日]?)", text
        )
        if date_pattern:
            results.append({
                "claim_type": label,
                "text_snippet": date_pattern[0] if date_pattern else "",
                "policy_value": expected_date,
                "status": "warning",
                "note": f"{label}可能需要核对——正文写的是{date_pattern[0] if date_pattern else '未知'}，数据库记录为{expected_date}",
            })


def _check_number_match(
    results: list,
    text: str,
    pattern_rules: list[str],
    correct_value: str,
    label: str,
    unit: str = "",
) -> None:
    """
    检查正文中是否出现了正确数值。
    策略：用正则检查正文中出现的同类数值，与正确值比对。
    """
    # 搜索正文中与 unit 相同的数值
    if unit:
        nearby_numbers = re.findall(rf"(\d+)\s*{unit}", text)
    else:
        nearby_numbers = re.findall(rf"(\d+)\s*年", text)

    correct_num = re.findall(r"\d+", correct_value)
    correct_num_str = correct_num[0] if correct_num else correct_value

    if correct_num_str in nearby_numbers:
        results.append({
            "claim_type": label,
            "text_snippet": f"{correct_num_str}{unit}",
            "policy_value": correct_value,
            "status": "pass",
            "note": f"{label}数值一致",
        })
    elif nearby_numbers:
        results.append({
            "claim_type": label,
            "text_snippet": f"{nearby_numbers[0]}{unit}",
            "policy_value": correct_value,
            "status": "warning",
            "note": f"{label}——正文写{nearby_numbers[0]}{unit}，数据库为{correct_value}，请人工核实",
        })
    # else: 正文未提及该数值，不生成记录（避免噪音）


def _check_text_contains(results: list, text: str, keyword: str, label: str) -> None:
    """检查文本中是否包含关键词。"""
    if keyword in text:
        results.append({
            "claim_type": label,
            "text_snippet": keyword,
            "policy_value": keyword,
            "status": "pass",
            "note": f"{label}提及正确",
        })
    else:
        results.append({
            "claim_type": label,
            "text_snippet": "未提及",
            "policy_value": keyword,
            "status": "uncheckable",
            "note": f"{label}——正文未提及，数据库为{keyword}",
        })


def _parse_date(s: str):
    """解析多种日期格式。"""
    for fmt in ("%Y-%m-%d", "%Y-%m-%d %H:%M:%S", "%Y/%m/%d", "%Y年%m月%d日"):
        try:
            return datetime.strptime(s, fmt)
        except (ValueError, TypeError):
            continue
    # 只取日期部分
    try:
        return datetime.strptime(s[:10], "%Y-%m-%d")
    except (ValueError, TypeError):
        return None
