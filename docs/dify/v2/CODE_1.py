import json
import random
from datetime import datetime, timedelta


def main(
    exam_name: str,
    exam_date: str,
    cards,
    role: str = "",
    countdown_days: int = 0,
    phase_1_end: str = "",
    phase_2_end: str = "",
    today_date: str = "",
    target_audience: str = "",
    theme: str = "",
    include_study_material: bool = False,
    narrative_plan: str = "",  # V2: 来自 CODE_0 的叙事大纲
    chapter_index: str = "",  # V3: chapter_index.json 内容（JSON 字符串）
):
    """
    cards: 前端传入的卡片骨架数组.
           可能是 list(Dify 自动解析 JSON)或 str(需手动解析).

    V2 改动:
    1. 注入 narrative_plan 到每张卡片
    2. 注入 card_position + total_cards
    3. study_material 话题分派(避免多张 study_material 覆盖相同器官系统)
    4. plan_count=1 且天数>30 时标记为摘要模式

    V3 改动:
    5. study_material 改为从 chapter_index 随机分配章节 → kb_query
    6. 每张卡片注入 kb_query（study_material 用章节名，其他卡片用固定短语或不检索）
    """
    # ── 1. 解析 cards(兼容 str / list) ──
    if isinstance(cards, str):
        cards = json.loads(cards)

    total_cards = len(cards)

    # ── 2. 计算倒计时 ──
    if countdown_days is None or countdown_days == 0:
        today = datetime.now().date()
        exam_d = datetime.strptime(exam_date, "%Y-%m-%d").date()
        countdown_days = max(0, (exam_d - today).days)
    else:
        pass

    if today_date:
        today = datetime.strptime(today_date, "%Y-%m-%d").date()
    else:
        today = datetime.now().date()

    if countdown_days < 0:
        countdown_days = 0

    # ── 3. 按 countdown 判定整体阶段 ──
    if countdown_days > 60:
        overall_phase = "备考早期"
    elif countdown_days > 30:
        overall_phase = "备考中期"
    elif countdown_days > 14:
        overall_phase = "冲刺期"
    elif countdown_days > 0:
        overall_phase = "考前"
    else:
        overall_phase = "考后"

    # ── 4. 找出所有 plan 卡片的位置 ──
    plan_indices = [i for i, c in enumerate(cards) if c.get("type") == "plan"]
    plan_count = len(plan_indices)

    # ── 5. 为每个 plan 分配阶段日期范围 ──
    total_days = max(countdown_days, 14)
    plan_phases = []

    has_frontend_phases = bool(phase_1_end) and plan_count >= 2

    # * V2:单张 plan 卡且天数 > 30,标记为摘要模式
    single_plan_summary_mode = (plan_count == 1 and total_days > 30)

    if plan_count >= 1:
        if has_frontend_phases:
            for idx in range(plan_count):
                if idx == 0:
                    start_d = today
                    end_d = datetime.strptime(phase_1_end, "%Y-%m-%d").date()
                    phase_name = "基础阶段"
                    phase_desc = "打牢地基,逐科系统复习"
                    daily_hours = "2h"
                elif idx == 1 and phase_2_end:
                    p1_end_date = datetime.strptime(phase_1_end, "%Y-%m-%d").date()
                    start_d = p1_end_date + timedelta(days=1)
                    end_d = datetime.strptime(phase_2_end, "%Y-%m-%d").date()
                    phase_name = "强化阶段"
                    phase_desc = "查漏补缺,真题试水 + 错题整理"
                    daily_hours = "2.5h"
                elif idx == plan_count - 1:
                    p2_end_date = datetime.strptime(phase_2_end, "%Y-%m-%d").date() if phase_2_end else today
                    start_d = p2_end_date + timedelta(days=1)
                    end_d = datetime.strptime(exam_date, "%Y-%m-%d").date()
                    phase_name = "强化冲刺"
                    phase_desc = "考前冲刺,模拟卷 + 背口诀,保持手感"
                    daily_hours = "3h"
                else:
                    remaining_start = datetime.strptime(phase_2_end, "%Y-%m-%d").date() + timedelta(days=1) if phase_2_end else today
                    remaining_end = datetime.strptime(exam_date, "%Y-%m-%d").date()
                    remaining_days = max(1, (remaining_end - remaining_start).days)
                    start_d = remaining_start
                    end_d = remaining_end
                    phase_name = "强化冲刺"
                    phase_desc = "查漏补缺,高频考点 + 模拟卷"
                    daily_hours = "3h"

                phase_days = max(1, (end_d - start_d).days + 1)

                plan_phases.append({
                    "phase_name": phase_name,
                    "phase_desc": phase_desc,
                    "daily_hours": daily_hours,
                    "phase_days": phase_days,
                    "start_date": start_d.strftime("%Y-%m-%d"),
                    "end_date": end_d.strftime("%Y-%m-%d"),
                    "summary_mode": False,
                })
        else:
            segment = total_days // plan_count
            for idx in range(plan_count):
                start_offset = idx * segment
                if idx < plan_count - 1:
                    end_offset = (idx + 1) * segment - 1
                else:
                    end_offset = total_days - 1

                start_d = today + timedelta(days=start_offset)
                end_d = today + timedelta(days=end_offset)

                if plan_count == 1:
                    phase_name = "全程备考"
                    phase_desc = f"距离考试还有 {countdown_days} 天,按计划稳步推进"
                    daily_hours = "2h"
                elif idx == 0:
                    phase_name = "基础阶段"
                    phase_desc = "打牢地基,逐科系统复习"
                    daily_hours = "2h"
                elif idx == plan_count - 1:
                    phase_name = "强化冲刺"
                    phase_desc = "查漏补缺,高频考点 + 模拟卷"
                    daily_hours = "3h"
                else:
                    phase_name = f"第 {idx + 1} 阶段"
                    phase_desc = "稳步推进,强化薄弱环节"
                    daily_hours = "2.5h"

                plan_phases.append({
                    "phase_name": phase_name,
                    "phase_desc": phase_desc,
                    "daily_hours": daily_hours,
                    "phase_days": end_offset - start_offset + 1,
                    "start_date": start_d.strftime("%Y-%m-%d"),
                    "end_date": end_d.strftime("%Y-%m-%d"),
                    "summary_mode": single_plan_summary_mode and idx == 0,
                })

    # ── 6. * V3:study_material 章节随机分配 + kb_query 构造 ──
    sm_indices = [i for i, c in enumerate(cards) if c.get("type") == "study_material"]
    sm_chapter_assignments = {}

    if chapter_index and sm_indices:
        try:
            index = json.loads(chapter_index)
            chapters = index.get("chapters", [])
            random.shuffle(chapters)
            pool = list(chapters)

            for pos, card_idx in enumerate(sm_indices):
                if pool:
                    ch = pool.pop(0)
                elif chapters:
                    ch = random.choice(chapters)
                else:
                    ch = {"name": "", "file": ""}

                sm_chapter_assignments[card_idx] = {
                    "assigned_chapter": ch.get("name", ""),
                    "kb_query": f"{exam_name}__{ch.get('file', ch.get('name', ''))}",
                    "sm_index": pos,
                    "total_sm_cards": len(sm_indices),
                }
        except json.JSONDecodeError:
            # chapter_index 解析失败时降级为空
            pass

    # 其他卡片类型的 kb_query 模板
    KB_QUERY_TEMPLATES = {
        "subjects": f"{exam_name} 考试科目 分值分布 备考策略",
        "priority": f"{exam_name} 各科目分值占比 高频考点 历年真题统计",
        "mnemonics": f"{exam_name} 记忆口诀 高频考点 谐音记忆",
        "plan": f"{exam_name} 复习顺序 阶段规划",
    }

    # ── 7. 为每张卡片注入上下文,输出 enriched_cards ──
    plan_phase_idx = 0
    enriched = []
    weekday_names = ["周一", "周二", "周三", "周四", "周五", "周六", "周日"]

    for i, card in enumerate(cards):
        item = {
            "index": i,
            "type": card.get("type", ""),
        }

        # 注入共享信息
        item["exam_name"] = exam_name
        item["exam_date"] = exam_date
        item["role"] = role
        item["countdown_days"] = countdown_days
        item["today_date"] = today.strftime("%Y-%m-%d")
        item["overall_phase"] = overall_phase
        item["target_audience"] = target_audience
        item["theme"] = theme
        item["include_study_material"] = include_study_material

        # * V2:注入叙事上下文 + 卡片位置
        item["narrative_plan"] = narrative_plan
        item["total_cards"] = total_cards
        item["card_position"] = f"第{i+1}张,共{total_cards}张"

        # 为 plan 类型注入阶段信息 + 预生成日期框架
        if card.get("type") == "plan" and plan_phase_idx < len(plan_phases):
            ph = plan_phases[plan_phase_idx]
            item["phase_name"] = ph["phase_name"]
            item["phase_desc"] = ph["phase_desc"]
            item["daily_hours"] = ph["daily_hours"]
            item["phase_days"] = ph["phase_days"]
            item["start_date"] = ph["start_date"]
            item["end_date"] = ph["end_date"]
            item["summary_mode"] = ph.get("summary_mode", False)

            # 生成日期框架
            start_d = datetime.strptime(ph["start_date"], "%Y-%m-%d").date()
            end_d = datetime.strptime(ph["end_date"], "%Y-%m-%d").date()
            days_grid = []
            current = start_d

            # * V2:摘要模式下均匀采样(每 N 天取 1 天 + 保留所有复盘日占位)
            MAX_GRID_DAYS = 25  # 单张卡片日期条目上限
            total_phase_days = (end_d - start_d).days + 1

            if total_phase_days > MAX_GRID_DAYS:
                # 均匀采样:计算步长
                step = max(1, total_phase_days // MAX_GRID_DAYS)
                sampled_days = []
                day_idx = 0
                while current <= end_d:
                    # 每 step 天取 1 天,或当天是"关键日"(月末/月初/每7天)
                    is_key_day = (
                        day_idx % 7 == 0 or
                        current.day == 1 or
                        current.day == 15
                    )
                    if day_idx % step == 0 or is_key_day:
                        sampled_days.append({
                            "date": f"{current.month}.{current.day}",
                            "weekday": weekday_names[current.weekday()],
                            "task": "",
                            "duration": ph["daily_hours"],
                        })
                    else:
                        # 插入省略标记
                        if len(sampled_days) > 0 and sampled_days[-1].get("task") != "...":
                            sampled_days.append({
                                "date": "...",
                                "weekday": "",
                                "task": "...",
                                "duration": "",
                                "is_ellipsis": True,
                            })
                    current += timedelta(days=1)
                    day_idx += 1

                # 清理连续的省略号
                days_grid = []
                prev_was_ellipsis = False
                for d in sampled_days:
                    if d.get("is_ellipsis"):
                        if not prev_was_ellipsis:
                            days_grid.append(d)
                        prev_was_ellipsis = True
                    else:
                        days_grid.append(d)
                        prev_was_ellipsis = False
            else:
                while current <= end_d:
                    days_grid.append({
                        "date": f"{current.month}.{current.day}",
                        "weekday": weekday_names[current.weekday()],
                        "task": "",
                        "duration": ph["daily_hours"],
                    })
                    current += timedelta(days=1)

            item["days_grid"] = days_grid
            item["grid_count"] = len(days_grid)

            # * V2:摘要模式额外标记
            if ph.get("summary_mode"):
                item["summary_mode"] = True
                item["total_phase_days"] = total_phase_days
                item["actual_output_days"] = len([d for d in days_grid if not d.get("is_ellipsis")])

            plan_phase_idx += 1

        # * V3:study_material 章节分配
        if card.get("type") == "study_material" and i in sm_chapter_assignments:
            item.update(sm_chapter_assignments[i])

        # * V3:所有卡片注入 kb_query
        if card.get("type") == "study_material":
            # kb_query 已在 sm_chapter_assignments 中设置,此处兜底
            if "kb_query" not in item:
                item["kb_query"] = f"{exam_name}__核心考点"
        elif card.get("type") in KB_QUERY_TEMPLATES:
            item["kb_query"] = KB_QUERY_TEMPLATES[card.get("type")]
        else:
            item["kb_query"] = ""  # cover / notice / cta / resources 不检索

        enriched.append(item)

    return {
        "enriched_cards": [json.dumps(item, ensure_ascii=False) for item in enriched],
        "plan_count": str(plan_count),
        "countdown_days": str(countdown_days),
    }
