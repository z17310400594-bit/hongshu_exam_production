import json
import re


def extract_duration_from_task(task_name, default_duration):
    """
    * V3.2:从 LLM 生成的 task 名中提取时长+清洗.
    例如 "生理学-细胞功能(50m)" -> "50m"
    例如 "生理学-血液循环(1.5h)" -> "1.5h"
    提取不到则返回默认值.
    """
    if not task_name or task_name == "...":
        return default_duration

    # 匹配 (XXm) — V3.2 新格式
    match = re.search(r'[((](\d+\.?\d*\s*m)[))]', task_name)
    if match:
        return match.group(1).replace(" ", "")

    # 兼容旧格式 (XXmin)
    match = re.search(r'[((](\d+\.?\d*\s*min)[))]', task_name)
    if match:
        return match.group(1).replace(" ", "").replace("min", "m")

    # 匹配 (X.Xh) 或 (XXh)
    match = re.search(r'[((](\d+\.?\d*\s*h)[))]', task_name)
    if match:
        return match.group(1).replace(" ", "")

    # 匹配 (XX分钟)
    match = re.search(r'[((](\d+\.?\d*\s*分钟)[))]', task_name)
    if match:
        return match.group(1).replace(" ", "")

    return default_duration


def strip_duration_from_task(task_name):
    """
    V3.2:从 task 名中移除时长后缀,避免渲染时出现双重时长.
    例如 "生理学-细胞功能(50m)" -> "生理学-细胞功能"
    例如 "生理学-血液循环(1.5h)" -> "生理学-血液循环"
    """
    if not task_name:
        return task_name
    # 移除末尾的 (XXm), (XXmin), (X.Xh), (XX分钟)
    cleaned = re.sub(r'\s*[((]\d+\.?\d*\s*(?:m|min|h|分钟)[))]\s*$', '', task_name)
    return cleaned.strip()


def main(llm_outputs, original_cards, exam_name: str = ""):
    """
    llm_outputs: Iterator 自动收集的 LLM 输出数组.
    original_cards: CODE_1 输出的 enriched_cards,用于校验.

    V2 改动:
    1. 修复 duration 被默认值覆盖的 bug:从 task 名中提取 LLM 生成的时长
    2. 摘要模式 days 中保留省略标记
    3. 增强兜底标题(含考试名)
    4. 清洗 DeepSeek <think> 标签

    V3 改动:
    5. study_material 模块强制 source 字段补全(默认 "knowledge_base")
    6. source 字段格式校验
    """
    # ── 1. 解析 LLM 输出 ──
    generated = []
    if isinstance(llm_outputs, str):
        try:
            llm_outputs = json.loads(llm_outputs)
        except json.JSONDecodeError:
            return {"cards": [], "error": "llm_outputs JSON 解析失败"}

    for item in llm_outputs:
        if isinstance(item, str):
            try:
                text = item.strip()

                # * 清洗 DeepSeek <think> 思考标签
                text = re.sub(r'<think>.*?</think>\s*', '', text, flags=re.DOTALL)

                if text.startswith("```"):
                    lines = text.split("\n")
                    text = "\n".join(
                        lines[1:-1] if lines[-1].strip() == "```" else lines[1:]
                    )
                parsed = json.loads(text)
                generated.append(parsed)
            except json.JSONDecodeError:
                generated.append({
                    "type": "unknown", "title": "", "subtitle": "",
                    "days": [], "items": [], "qrcode_url": "",
                    "_raw": item, "_error": "JSON parse failed",
                })
        elif isinstance(item, dict):
            generated.append(item)
        else:
            generated.append({
                "type": "unknown", "title": "", "subtitle": "",
                "days": [], "items": [], "qrcode_url": "",
                "_error": f"unexpected type: {type(item)}",
            })

    # ── 2. 解析原始卡片顺序 ──
    if isinstance(original_cards, str):
        original_cards = json.loads(original_cards)

    parsed_originals = []
    for c in original_cards:
        if isinstance(c, str):
            parsed_originals.append(json.loads(c))
        elif isinstance(c, dict):
            parsed_originals.append(c)
        else:
            parsed_originals.append({"type": "", "_error": f"unexpected type: {type(c)}"})

    expected_types = [c.get("type", "") for c in parsed_originals]
    expected_count = len(expected_types)

    # ── 3. 数量校验 ──
    if len(generated) != expected_count:
        pass

    # ── 4. 逐张校验 & 补全 ──
    cards = []
    for i in range(expected_count):
        expected_type = expected_types[i]
        original_card = parsed_originals[i] if i < len(parsed_originals) else {}

        if i < len(generated):
            card = generated[i]
        else:
            card = {"type": expected_type}

        # 校验 type
        actual_type = card.get("type", "")
        if actual_type != expected_type and actual_type != "":
            card["type"] = expected_type
        if not card.get("type"):
            card["type"] = expected_type

        # * V2 plan 类型:合并 LLM tasks 与 days_grid,修复 duration
        if expected_type == "plan":
            llm_tasks = card.get("tasks", [])
            days_grid = original_card.get("days_grid", [])

            if isinstance(llm_tasks, list) and len(llm_tasks) > 0 and len(days_grid) > 0:
                merged_days = []
                for j, day in enumerate(days_grid):
                    # * V2:保留省略标记
                    is_ellipsis = day.get("is_ellipsis", False) or day.get("task") == "..."

                    if is_ellipsis:
                        merged_days.append({
                            "date": "...",
                            "weekday": "",
                            "task": "...",
                            "duration": "",
                        })
                        continue

                    task_name = llm_tasks[j] if j < len(llm_tasks) else "复习"
                    is_rest = "休息" in task_name

                    # * V3.2:从 task 名中提取时长并清洗 task 文本,避免双重显示
                    default_dur = day.get("duration", "2h")
                    extracted_dur = extract_duration_from_task(task_name, default_dur)
                    clean_task = strip_duration_from_task(task_name)

                    merged_days.append({
                        "date": day.get("date", ""),
                        "weekday": day.get("weekday", ""),
                        "task": clean_task,
                        "duration": "休息" if is_rest else extracted_dur,
                    })
                card["days"] = merged_days
            elif isinstance(card.get("days"), list) and len(card.get("days", [])) > 0:
                # LLM 输出了旧格式 days(兜底)-> 修复 duration + 清洗 task
                for d in card["days"]:
                    task = d.get("task", "")
                    if d.get("duration") in (None, "", "2h"):
                        d["duration"] = extract_duration_from_task(task, "2h")
                    d["task"] = strip_duration_from_task(task)
            else:
                card["days"] = days_grid if days_grid else []

            card.pop("tasks", None)
        else:
            if not isinstance(card.get("days"), list):
                card["days"] = []

        # 补全缺失字段
        card.setdefault("title", "")
        card.setdefault("subtitle", "")
        card.setdefault("days", [])
        card.setdefault("items", [])
        card.setdefault("qrcode_url", "")

        # * V3 学习资料卡片:确保 study_material 字段存在 + source 补全
        if card.get("type") == "study_material":
            if "study_material" not in card or not isinstance(card.get("study_material"), list):
                card["study_material"] = []
            else:
                # V3: 每个 module 确保 source 字段存在并格式正确
                VALID_SOURCES = ("knowledge_base", "llm_search")
                for mod in card["study_material"]:
                    if not isinstance(mod, dict):
                        continue
                    source = mod.get("source", "")
                    if not source or source not in VALID_SOURCES:
                        mod["source"] = "knowledge_base"  # 默认知识库来源

        # * V2 兜底标题:含考试名
        if not card.get("title"):
            fallback_titles = {
                "cover": f"{exam_name}已经开考了!" if exam_name else "备考计划",
                "plan": "学习计划",
                "subjects": "考试科目一览",
                "notice": "考前注意事项",
                "cta": "觉得有用?收藏起来!",
                "resources": "备考资料清单",
                "priority": "备考优先级指南",
                "mnemonics": "记忆口诀速记",
                "study_material": "核心考点速记",
            }
            card["title"] = fallback_titles.get(card["type"], "备考卡片")

        cards.append(card)

    # ── 5. 最终校验 ──
    VALID_TYPES = [
        "cover", "plan", "subjects", "notice", "cta",
        "resources", "priority", "mnemonics", "study_material",
    ]
    for i, card in enumerate(cards):
        assert card["type"] in VALID_TYPES, f"Invalid type '{card['type']}' at index {i}"
        assert isinstance(card["title"], str) and card["title"], f"title is empty at index {i}"
        assert isinstance(card["days"], list), f"days must be list at index {i}"
        assert isinstance(card["items"], list), f"items must be list at index {i}"
        assert isinstance(card["qrcode_url"], str), f"qrcode_url must be string at index {i}"

        if card.get("type") == "study_material":
            sm = card.get("study_material", [])
            assert isinstance(sm, list), f"study_material must be list at index {i}"
            for mi, mod in enumerate(sm):
                assert isinstance(mod.get("module_title"), str) and mod["module_title"], \
                    f"study_material[{mi}].module_title is empty at index {i}"
                assert isinstance(mod.get("key_points"), list), \
                    f"study_material[{mi}].key_points must be list at index {i}"
                assert isinstance(mod.get("memory_tips"), list), \
                    f"study_material[{mi}].memory_tips must be list at index {i}"

    return {"cards": cards}
