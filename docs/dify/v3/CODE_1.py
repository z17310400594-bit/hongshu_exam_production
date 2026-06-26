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
    db_data_json: str = "",  # V3: 来自 CODE_0_db 的数据库注入数据
    facts_brief: str = "",  # V3: CODE_0_db 产出的 LLM 友好纯文本摘要
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
    5. study_material 从 chapter_index 随机分配章节 → 用于匹配 DB 知识点
    6. 接收 CODE_0_db.db_data_json，按卡片类型注入真实数据库内容
    """
    # ── 1. 解析 cards(兼容 str / list) ──
    if isinstance(cards, str):
        if cards.strip():
            try:
                cards = json.loads(cards)
            except json.JSONDecodeError:
                cards = []
        else:
            cards = []

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
        cumulative_days_before = 0  # ★ 累计已分配天数，用于阶段标题正确编号
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
                    # ★ 修复:如果只有 2 张 plan 卡片，第二张必须覆盖到考试日
                    if plan_count == 2:
                        end_d = datetime.strptime(exam_date, "%Y-%m-%d").date()
                        phase_name = "强化冲刺"
                        phase_desc = "查漏补缺,真题试水 + 错题整理 + 考前冲刺,背口诀保持手感"
                        daily_hours = "2.5h→3h"
                    else:
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
                    "cumulative_days_before": cumulative_days_before,
                })
                cumulative_days_before += phase_days
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
                    "cumulative_days_before": cumulative_days_before,
                })
                cumulative_days_before += end_offset - start_offset + 1

    # ── 6. * V3:study_material 章节随机分配（排重版）──
    sm_indices = [i for i, c in enumerate(cards) if c.get("type") == "study_material"]
    sm_chapter_assignments = {}

    if chapter_index and sm_indices:
        try:
            index = json.loads(chapter_index)
            chapters = index.get("chapters", [])
            if chapters:
                random.shuffle(chapters)
                pool = list(chapters)
                assigned_names = set()  # ★ 排重：已分配的章节名

                for pos, card_idx in enumerate(sm_indices):
                    # 优先从 pool 取（保证不重复）
                    ch = None
                    while pool:
                        candidate = pool.pop(0)
                        name = candidate.get("name", "")
                        if name not in assigned_names:
                            ch = candidate
                            break
                    # pool 耗尽但还有未用的章节——从全部章节中找个没分配过的
                    if ch is None and len(assigned_names) < len(chapters):
                        for c in chapters:
                            if c.get("name", "") not in assigned_names:
                                ch = c
                                break
                    # 所有章节都已分配过——标记为"综合复习"，提示 LLM 避免重复
                    if ch is None:
                        prev = "、".join(assigned_names)
                        ch = {
                            "name": f"综合复习（已覆盖：{prev}）",
                            "file": "",
                        }

                    name = ch.get("name", "")
                    assigned_names.add(name)
                    sm_chapter_assignments[card_idx] = {
                        "assigned_chapter": name,
                        "sm_index": pos,
                        "total_sm_cards": len(sm_indices),
                        "avoid_duplicate_with": prev if ch is None and pos > 0 else "",
                    }
        except json.JSONDecodeError:
            # chapter_index 解析失败时降级为空
            pass

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
        item["facts_brief"] = facts_brief  # ★ V3: LLM 友好摘要（所有卡片共享）

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
            item["cumulative_days_before"] = ph.get("cumulative_days_before", 0)  # ★ 用于阶段标题正确编号

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

        enriched.append(item)

    # ── 8. * V3:注入数据库数据 ──
    db_data = {}
    if db_data_json and db_data_json != "{}":
        try:
            db_data = json.loads(db_data_json)
        except json.JSONDecodeError:
            pass

    if db_data:
        kps = db_data.get("knowledge_points", [])
        subjects = db_data.get("subjects", [])
        schedule = db_data.get("schedule")
        cert_name = db_data.get("cert_name", "")
        policy_clauses = db_data.get("policy_clauses", [])
        exam_questions = db_data.get("exam_questions", [])
        viral_samples = db_data.get("viral_samples", [])
        viral_tags = db_data.get("viral_tags", [])
        exam_conditions = db_data.get("exam_conditions", [])
        exemptions = db_data.get("exemptions", [])
        registration_policies = db_data.get("registration_policies", [])
        score_rules = db_data.get("score_rules", [])
        viral_count = db_data.get("viral_count", 0)
        question_count = db_data.get("question_count", 0)

        for i, item in enumerate(enriched):
            card_type = item.get("type", "")

            # ★ 所有卡片注入 cert_name（来自数据库的准确证书名）
            if cert_name:
                item["db_cert_name"] = cert_name

            if card_type == "cover":
                # 封面：注入爆款样本作风格参考 + 标签
                if viral_samples:
                    item["viral_samples"] = viral_samples[:3]  # 取 top 3 作风格标杆
                if viral_tags:
                    item["viral_tags"] = viral_tags

            elif card_type == "plan":
                # 学习计划：注入真题（真题日有真题目）+ 爆款标题参考
                if exam_questions:
                    item["exam_questions"] = exam_questions
                if viral_samples:
                    item["viral_titles"] = [v["title"] for v in viral_samples[:5] if v.get("title")]
                if question_count > 0:
                    item["question_count"] = question_count

            elif card_type == "study_material":
                # 按 assigned_chapter 匹配知识点 + 真题
                chapter = item.get("assigned_chapter", "")
                if chapter and kps:
                    matched = [k for k in kps if chapter in k.get("kp_name", "")]
                    if not matched:
                        matched = kps[:3]
                    item["kp_data"] = matched
                elif kps:
                    item["kp_data"] = kps[:5]
                # 注入相关真题
                if exam_questions:
                    item["exam_questions"] = exam_questions

            elif card_type == "subjects":
                if subjects:
                    item["subjects_data"] = subjects

            elif card_type == "priority":
                if subjects and kps:
                    kp_by_subject = {}
                    for k in kps:
                        s = k.get("subject_name", "未知")
                        kp_by_subject[s] = kp_by_subject.get(s, 0) + 1
                    item["priority_data"] = {
                        "subjects": subjects,
                        "kp_counts": kp_by_subject,
                    }

            elif card_type == "mnemonics":
                high_kps = [k for k in kps if k.get("frequency") == "高频"]
                item["mnemonic_anchors"] = high_kps[:5] if high_kps else kps[:5]
                if viral_samples:
                    item["viral_samples"] = viral_samples[:3]

            elif card_type == "notice":
                if schedule:
                    item["schedule_data"] = {
                        "exam_date": schedule.get("exam_date", ""),
                        "registration_start": schedule.get("registration_start", ""),
                        "registration_end": schedule.get("registration_end", ""),
                        "result_date": schedule.get("result_date", ""),
                        "year": schedule.get("year", ""),
                    }
                # 注入报考条件 + 免考 + 注册政策 + 法条依据
                if exam_conditions:
                    item["exam_conditions"] = exam_conditions
                if exemptions:
                    item["exemptions"] = exemptions
                if registration_policies:
                    item["registration_policies"] = registration_policies
                if policy_clauses:
                    item["policy_clauses"] = policy_clauses
                if score_rules:
                    item["score_rules"] = score_rules

            elif card_type == "resources":
                if subjects and kps:
                    item["resources_data"] = {
                        "subject_names": [s.get("subject_name", "") for s in subjects],
                        "top_kp_names": [k.get("kp_name", "") for k in kps[:5]],
                    }

            elif card_type == "cta":
                # CTA：注入爆款样本作语气参考
                if viral_samples:
                    item["viral_samples"] = viral_samples[:3]
                if viral_tags:
                    item["viral_tags"] = viral_tags

    return {
        "enriched_cards": [json.dumps(item, ensure_ascii=False) for item in enriched],
        "plan_count": str(plan_count),
        "countdown_days": str(countdown_days),
    }
