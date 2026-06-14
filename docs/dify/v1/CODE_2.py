import json


def main(llm_outputs, original_cards):
    """
    llm_outputs: Iterator 自动收集的 LLM 输出数组.
                 每个元素是 LLM 生成的一行 JSON 文本,或已经是 dict.
    original_cards: CODE 1 输出的 enriched_cards,用于校验.

    返回最终的 cards 数组.
    """
    # ── 1. 解析 LLM 输出 ──
    generated = []
    if isinstance(llm_outputs, str):
        # 兜底:整个输出被序列化为字符串
        try:
            llm_outputs = json.loads(llm_outputs)
        except json.JSONDecodeError:
            return {"cards": [], "error": "llm_outputs JSON 解析失败"}

    for item in llm_outputs:
        if isinstance(item, str):
            # LLM 输出的是 JSON 文本,尝试解析
            try:
                # 清洗可能的 Markdown 代码块包裹
                text = item.strip()
                if text.startswith("```"):
                    lines = text.split("\n")
                    text = "\n".join(
                        lines[1:-1] if lines[-1].strip() == "```" else lines[1:]
                    )
                parsed = json.loads(text)
                generated.append(parsed)
            except json.JSONDecodeError:
                generated.append(
                    {
                        "type": "unknown",
                        "title": "",
                        "subtitle": "",
                        "days": [],
                        "items": [],
                        "qrcode_url": "",
                        "_raw": item,
                        "_error": "JSON parse failed",
                    }
                )
        elif isinstance(item, dict):
            generated.append(item)
        else:
            generated.append(
                {
                    "type": "unknown",
                    "title": "",
                    "subtitle": "",
                    "days": [],
                    "items": [],
                    "qrcode_url": "",
                    "_error": f"unexpected type: {type(item)}",
                }
            )

    # ── 2. 解析原始卡片顺序 ──
    if isinstance(original_cards, str):
        original_cards = json.loads(original_cards)

    # 逐元素解析:original_cards 是 Array[String],每个元素是 JSON 字符串
    parsed_originals = []
    for c in original_cards:
        if isinstance(c, str):
            parsed_originals.append(json.loads(c))
        elif isinstance(c, dict):
            parsed_originals.append(c)
        else:
            parsed_originals.append(
                {"type": "", "_error": f"unexpected type: {type(c)}"}
            )

    # 从 parsed_originals 提取 type 列表作为基准
    expected_types = [c.get("type", "") for c in parsed_originals]
    expected_count = len(expected_types)

    # ── 3. 数量校验 ──
    if len(generated) != expected_count:
        # 数量不匹配:记录告警,但不阻断
        pass  # 下面按实际数量处理

    # ── 4. 逐张校验 & 补全 ──
    cards = []
    for i in range(expected_count):
        expected_type = expected_types[i]
        original_card = parsed_originals[i] if i < len(parsed_originals) else {}

        if i < len(generated):
            card = generated[i]
        else:
            # 生成数量不足,补空卡片
            card = {"type": expected_type}

        # 校验 type 是否正确(LLM 可能改动了 type)
        actual_type = card.get("type", "")
        if actual_type != expected_type and actual_type != "":
            # LLM 改了 type,强制恢复
            card["type"] = expected_type

        if not card.get("type"):
            card["type"] = expected_type

        # * plan 类型:将 LLM 输出的 tasks 与 CODE 1 预生成的 days_grid 合并
        if expected_type == "plan":
            llm_tasks = card.get("tasks", [])
            days_grid = original_card.get("days_grid", [])

            if (
                isinstance(llm_tasks, list)
                and len(llm_tasks) > 0
                and len(days_grid) > 0
            ):
                # 用 LLM 的任务名填充预生成的日期框架
                merged_days = []
                for j, day in enumerate(days_grid):
                    task_name = llm_tasks[j] if j < len(llm_tasks) else "复习"
                    is_rest = "休息" in task_name
                    merged_days.append(
                        {
                            "date": day.get("date", ""),
                            "weekday": day.get("weekday", ""),
                            "task": task_name,
                            "duration": (
                                "休息" if is_rest else day.get("duration", "2h")
                            ),
                        }
                    )
                card["days"] = merged_days
            elif isinstance(card.get("days"), list) and len(card.get("days", [])) > 0:
                # LLM 仍输出了旧格式 days(兜底),保持不变
                pass
            else:
                # 无 tasks 也无 days,用 days_grid 兜底
                card["days"] = days_grid if days_grid else []

            # 清理 tasks 字段(不输出到最终结果)
            card.pop("tasks", None)
        else:
            # 非 plan 类型:确保 days 为空数组
            if not isinstance(card.get("days"), list):
                card["days"] = []

        # 补全缺失字段,确保所有字段存在且不为 null
        card.setdefault("title", "")
        card.setdefault("subtitle", "")
        card.setdefault("days", [])
        card.setdefault("items", [])
        card.setdefault("qrcode_url", "")

        # * V1.1 学习资料卡片:确保 study_material 字段存在且是列表
        if card.get("type") == "study_material":
            if "study_material" not in card or not isinstance(card.get("study_material"), list):
                card["study_material"] = []

        # 确保 title 不为空
        if not card.get("title"):
            # 根据类型给个兜底标题(含第二层新增的 3 种类型 + V1.1 study_material)
            fallback_titles = {
                "cover": "备考计划",
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
    for i, card in enumerate(cards):
        # * 扩展类型校验白名单(含第二层新增的 3 种类型 + V1.1 study_material)
        assert card["type"] in [
            "cover",
            "plan",
            "subjects",
            "notice",
            "cta",
            "resources",
            "priority",
            "mnemonics",
            "study_material",
        ], f"Invalid type '{card['type']}' at index {i}"
        assert (
            isinstance(card["title"], str) and card["title"]
        ), f"title is empty at index {i}"
        assert isinstance(card["days"], list), f"days must be list at index {i}"
        assert isinstance(card["items"], list), f"items must be list at index {i}"
        assert isinstance(
            card["qrcode_url"], str
        ), f"qrcode_url must be string at index {i}"

        # * V1.1:study_material 卡片额外校验
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

    return {
        "cards": cards,
    }
