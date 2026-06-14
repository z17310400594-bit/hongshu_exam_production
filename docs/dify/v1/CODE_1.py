import json
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
):
    """
    cards: 前端传入的卡片骨架数组.
           可能是 list(Dify 自动解析 JSON)或 str(需手动解析).

    本节点负责:
    1. 解析 cards(兼容 str/list)
    2. 计算倒计时天数(优先使用前端传入的精确值)
    3. 统计 plan 卡片数量,为每个 plan 分配阶段信息
       (如果前端传入了 phase_1_end / phase_2_end,使用精确的阶段窗口)
    4. 将上下文注入到每张卡片中,输出 enriched_cards
    """
    # ── 1. 解析 cards(兼容 str / list) ──
    if isinstance(cards, str):
        cards = json.loads(cards)

    # ── 2. 计算倒计时 ──
    # * 优先使用前端传入的精确值(前端确定性计算,不受 Dify 服务器时区影响)
    if countdown_days is None or countdown_days == 0:
        today = datetime.now().date()
        exam_d = datetime.strptime(exam_date, "%Y-%m-%d").date()
        countdown_days = max(0, (exam_d - today).days)
    else:
        # 前端已传入精确值,直接使用
        pass

    # * 优先使用前端传入的 today_date
    if today_date:
        today = datetime.strptime(today_date, "%Y-%m-%d").date()
    else:
        today = datetime.now().date()

    if countdown_days < 0:
        countdown_days = 0  # 考试已过期,兜底

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
    # * 如果前端传入了阶段窗口日期(phase_1_end / phase_2_end),
    #    使用精确的三阶段窗口；否则 fallback 到均分逻辑
    total_days = max(countdown_days, 14)  # 至少 14 天兜底
    plan_phases = []

    has_frontend_phases = bool(phase_1_end) and plan_count >= 2

    if plan_count >= 1:
        if has_frontend_phases:
            # ── 使用前端传入的精确阶段窗口 ──
            for idx in range(plan_count):
                if idx == 0:
                    # 基础阶段:today -> phase_1_end
                    start_d = today
                    end_d = datetime.strptime(phase_1_end, "%Y-%m-%d").date()
                    phase_name = "基础阶段"
                    phase_desc = "打牢地基,逐科系统复习"
                    daily_hours = "2h"
                elif idx == 1 and phase_2_end:
                    # 强化阶段:phase_1_end + 1day -> phase_2_end
                    p1_end_date = datetime.strptime(phase_1_end, "%Y-%m-%d").date()
                    start_d = p1_end_date + timedelta(days=1)
                    end_d = datetime.strptime(phase_2_end, "%Y-%m-%d").date()
                    phase_name = "强化阶段"
                    phase_desc = "查漏补缺,真题试水 + 错题整理"
                    daily_hours = "2.5h"
                elif idx == plan_count - 1:
                    # 冲刺阶段:phase_2_end + 1day -> exam_date
                    p2_end_date = datetime.strptime(phase_2_end, "%Y-%m-%d").date() if phase_2_end else today
                    start_d = p2_end_date + timedelta(days=1)
                    end_d = datetime.strptime(exam_date, "%Y-%m-%d").date()
                    phase_name = "强化冲刺"
                    phase_desc = "考前冲刺,模拟卷 + 背口诀,保持手感"
                    daily_hours = "3h"
                else:
                    # 多余 plan 卡片:均分剩余天数
                    remaining_start = datetime.strptime(phase_2_end, "%Y-%m-%d").date() + timedelta(days=1) if phase_2_end else today
                    remaining_end = datetime.strptime(exam_date, "%Y-%m-%d").date()
                    remaining_days = max(1, (remaining_end - remaining_start).days)
                    start_d = remaining_start
                    end_d = remaining_end
                    phase_name = "强化冲刺"
                    phase_desc = "查漏补缺,高频考点 + 模拟卷"
                    daily_hours = "3h"

                phase_days = max(1, (end_d - start_d).days + 1)

                plan_phases.append(
                    {
                        "phase_name": phase_name,
                        "phase_desc": phase_desc,
                        "daily_hours": daily_hours,
                        "phase_days": phase_days,
                        "start_date": start_d.strftime("%Y-%m-%d"),
                        "end_date": end_d.strftime("%Y-%m-%d"),
                    }
                )
        else:
            # ── Fallback:均分逻辑(前端未传阶段窗口时使用) ──
            segment = total_days // plan_count
            for idx in range(plan_count):
                start_offset = idx * segment
                if idx < plan_count - 1:
                    end_offset = (idx + 1) * segment - 1
                else:
                    end_offset = total_days - 1  # 最后一个 plan 吃完剩余天数

                start_d = today + timedelta(days=start_offset)
                end_d = today + timedelta(days=end_offset)

                # 按位置命名阶段
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

                plan_phases.append(
                    {
                        "phase_name": phase_name,
                        "phase_desc": phase_desc,
                        "daily_hours": daily_hours,
                        "phase_days": end_offset - start_offset + 1,
                        "start_date": start_d.strftime("%Y-%m-%d"),
                        "end_date": end_d.strftime("%Y-%m-%d"),
                    }
                )

    # ── 6. 为每张卡片注入上下文,输出 enriched_cards ──
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

        # 为 plan 类型注入阶段信息 + 预生成日期框架
        if card.get("type") == "plan" and plan_phase_idx < len(plan_phases):
            ph = plan_phases[plan_phase_idx]
            item["phase_name"] = ph["phase_name"]
            item["phase_desc"] = ph["phase_desc"]
            item["daily_hours"] = ph["daily_hours"]
            item["phase_days"] = ph["phase_days"]
            item["start_date"] = ph["start_date"]
            item["end_date"] = ph["end_date"]

            # * 预生成日期框架:日期 + 周几 + 时长(task 留空给 LLM 填)
            start_d = datetime.strptime(ph["start_date"], "%Y-%m-%d").date()
            end_d = datetime.strptime(ph["end_date"], "%Y-%m-%d").date()
            days_grid = []
            current = start_d
            while current <= end_d:
                days_grid.append(
                    {
                        "date": f"{current.month}.{current.day}",
                        "weekday": weekday_names[current.weekday()],
                        "task": "",
                        "duration": ph["daily_hours"],
                    }
                )
                current += timedelta(days=1)
            item["days_grid"] = days_grid

            plan_phase_idx += 1

        enriched.append(item)

    return {
        "enriched_cards": [json.dumps(item, ensure_ascii=False) for item in enriched],
        "plan_count": str(plan_count),
        "countdown_days": str(countdown_days),
    }
