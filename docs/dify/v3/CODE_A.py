# CODE A -- 参数构造(Iterator 子流程内,每张卡片调用一次)
# 职责:接收 Iterator 输出的当前卡片对象,根据 type 构造对应的 system_prompt 和 user_prompt
#
# 使用方法:打开 Dify 后台 -> 备考卡片生成 Workflow -> CODE A 节点 -> 全选删除 -> 粘贴本文件全部内容
#
# 输入变量(Dify CODE 节点配置):
#   current_card  -- Iterator 输出(当前迭代的卡片对象)
#   exam_name     -- START 节点(外部变量可在迭代器内直接引用)
#   exam_date     -- START 节点
#   role          -- START 节点
#
# 第二层新增卡片类型:resources(备考资料),priority(分值分布),mnemonics(记忆口诀)

import json
from datetime import datetime


def main(current_card, exam_name: str, exam_date: str, role: str, target_audience: str = "", theme: str = "", narrative_plan: str = ""):
    """
    根据卡片类型,构造 LLM 所需的 system_prompt 和 user_prompt.
    类型不可识别时,返回兜底 prompt.

    支持的卡片类型(V1.1 扩展至 9 种):
      cover, plan, subjects, notice, cta, resources, priority, mnemonics, study_material

    V1.1 新增:
      - target_audience:目标人群标签或自定义文本,注入到所有卡片 prompt 中
      - theme:主题方向,影响内容组织角度

    V3 新增:
      - narrative_plan:CODE_0 产出的叙事大纲(整体基调+表达风格+核心信息+过渡逻辑)
    """
    # Iterator 输出的是 JSON 字符串,需解析为 dict
    if isinstance(current_card, str):
        current_card = json.loads(current_card)

    card_type = current_card.get("type", "")

    # 提取上下文变量(CODE 1 已注入)
    countdown_days = current_card.get("countdown_days", 0)
    role = current_card.get("role", role or "")
    # 第二层新增:前端计算的阶段窗口(用于 plan 卡片精准日期)
    phase_1_end = current_card.get("phase_1_end", "")
    phase_2_end = current_card.get("phase_2_end", "")
    today_date = current_card.get("today_date", "")
    # V1.1 新增:目标人群和主题
    target_audience = current_card.get("target_audience", target_audience or "")
    theme = current_card.get("theme", theme or "")

    # V3 新增:数据库注入字段(来自 CODE_1 section 8)
    db_cert_name = current_card.get("db_cert_name", "")
    viral_samples = current_card.get("viral_samples", [])  # ★ V3: 爆款样本
    viral_tags = current_card.get("viral_tags", [])  # ★ V3: 爆款标签
    kp_data = current_card.get("kp_data", [])
    subjects_data = current_card.get("subjects_data", [])
    priority_data = current_card.get("priority_data", {})
    mnemonic_anchors = current_card.get("mnemonic_anchors", [])
    schedule_data = current_card.get("schedule_data", {})
    exam_conditions = current_card.get("exam_conditions", [])  # ★ V3: 报考条件
    exemptions_data = current_card.get("exemptions", [])  # ★ V3: 免考政策
    registration_data = current_card.get("registration_policies", [])  # ★ V3: 注册政策
    policy_clauses = current_card.get("policy_clauses", [])  # ★ V3: 法条原文
    score_rules = current_card.get("score_rules", [])  # ★ V3: 合格标准
    exam_questions = current_card.get("exam_questions", [])  # ★ V3: 真题数据
    facts_brief = current_card.get("facts_brief", "")  # ★ V3: LLM 友好事实摘要

    # ── 角色画像映射表 ──
    ROLE_PROFILES = {
        "小红书-医考号": {
            "persona": (
                "你是一个去年考过执业医师的学姐.当时你也是零基础,"
                "复习了 3 个月,考了 420 分.你知道备考过程中最崩溃的是第三个月,"
                "最需要的是有人告诉你哪些可以不用看,而不是塞给你 3000 页教材."
            ),
            "tone": (
                "亲切,口语化,像微信聊天.短句为主,每句话不超过 25 字,多换行."
                "多用 emoji(每张卡片 3-5 个)."
            ),
            "phrases": (
                '可以用的口头禅:'
                '"说实话""真的""我也是这么过来的""这块确实难""后来发现""别怕"'
            ),
            "banned": (
                '禁止:学术论文腔,官方公告腔,'
                '"众所周知""由此可见""综上所述""请注意"'
            ),
            "content_pref": "内容偏好:计划型 + 口诀型,擅长用亲身经历鼓励人",
        },
        "小红书-考研号": {
            "persona": (
                "你是一个二战上岸的学长.第一年踩了很多坑----盲目刷题,"
                "忽视真题,没有计划.第二年你总结了一套方法论才上岸."
                "你知道考研人的痛点不是不够努力,是方法不对."
            ),
            "tone": (
                "务实,不灌鸡汤,强调方法大于努力."
                "少点 emoji(每张卡片 1-2 个即可),多点干货."
            ),
            "phrases": (
                '可以用的口头禅:'
                '"别踩这个坑""说真的""我第一年就是栽在这""后来才发现""这个方法真的有用"'
            ),
            "banned": (
                '禁止:鸡汤文,'
                '"只要努力就能成功""加油你可以的"这类空洞鼓励'
            ),
            "content_pref": "内容偏好:策略型 + 工具型,擅长拆解学习误区和时间管理",
        },
        "公众号主编": {
            "persona": (
                "你是一个资深教研老师,在培训机构做了 8 年,"
                "每年跟踪最新考试政策和评分标准.你的内容不卖焦虑,"
                "卖的是确定性和专业判断."
            ),
            "tone": (
                "专业但不晦涩,有条理但不说教."
                "少用 emoji(每张卡片 0-1 个),结构清晰."
            ),
            "phrases": (
                '可以用的口头禅:'
                '"划重点""值得注意的是""根据近三年的出题规律""建议优先关注"'
            ),
            "banned": (
                '禁止:过度口语化,'
                '"真的""说实话"等小红书风格口头禅,emoji 滥用'
            ),
            "content_pref": "内容偏好:知识点型 + 政策解读型,擅长做深度分析和趋势预测",
        },
    }

    profile = ROLE_PROFILES.get(role, ROLE_PROFILES["小红书-医考号"])

    # ── V1.1 目标人群画像映射表 ──
    AUDIENCE_PROFILES = {
        "在职备考": {
            "persona": "你的读者是在职备考人群----白天上班晚上学习,最大的痛点是时间碎片化,精力不够.",
            "examples": "多举通勤/午休/下班后的学习场景例子.",
            "emphasis": "强调高效利用碎片时间,工作和备考的平衡,如何在忙碌中保持节奏.",
            "phrases": '可以用的口头禅:"下班后已经很累了,但坚持就是胜利""利用通勤时间刷刷题""午休半小时,背几个考点"',
        },
        "宝妈备考": {
            "persona": "你的读者是宝妈备考人群----带娃间隙学习,最大的痛点是时间不可控,精力被孩子分散.",
            "examples": "多举带孩子间隙学习的场景例子,比如孩子睡着后,送孩子上兴趣班的等待时间.",
            "emphasis": "强调时间管理的灵活性,家人的支持,如何在育儿和备考之间找到平衡.",
            "phrases": '可以用的口头禅:"等孩子睡着了再看一小时""带娃已经很累了,但我们不想放弃""每天进步一点点"',
        },
        "零基础": {
            "persona": "你的读者是零基础备考人群----对考试内容完全陌生,最大的痛点是不知道从哪开始,怕学不会.",
            "examples": "多举从零开始的学习路径场景,比如第一周先看视频课打基础,用三色笔记建立知识框架.",
            "emphasis": "强调循序渐进,基础概念解释,不要怕慢就怕站,用通俗语言讲复杂概念.",
            "phrases": '可以用的口头禅:"刚开始看不懂很正常""先建立整体框架,再深入细节""我也是零基础过来的"',
        },
        "非科班": {
            "persona": "你的读者是非科班跨专业备考人群----有学习能力但专业知识空白,最大的痛点是知识体系断层,专业术语陌生.",
            "examples": "多举跨专业备考的策略例子,比如先补基础知识,用思维导图建立学科间的联系.",
            "emphasis": "强调跨专业备考策略,基础知识补全,应试技巧优先,避免专业术语轰炸.",
            "phrases": '可以用的口头禅:"跨专业不是劣势,是另一种思路""先搞定高频考点,再补基础知识""慢慢来,比较快"',
        },
    }

    audience_profile = AUDIENCE_PROFILES.get(target_audience, None)

    TONE_BLOCK = (
        (
            "[主编叙事策略 — 来自 CODE_0 叙事规划]\n"
            + narrative_plan + "\n"
            + "严格遵守主编的整体基调、表达风格和每张卡片的核心信息.\n\n"
            if narrative_plan else ""
        )
        + "[你的角色人设]\n"
        + profile["persona"] + "\n\n"
        + "[口吻风格要求]\n"
        + profile["tone"] + "\n"
        + profile["phrases"] + "\n"
        + profile["banned"] + "\n\n"
        + "[内容偏好]\n"
        + profile["content_pref"] + "\n\n"
        + (
            "[目标受众适配 -- " + target_audience + "]\n"
            + audience_profile["persona"] + "\n"
            + audience_profile["examples"] + "\n"
            + audience_profile["emphasis"] + "\n"
            + audience_profile["phrases"] + "\n\n"
            if audience_profile else ""
        )
        + (
            "[内容主题方向]\n"
            + '围绕[' + theme + ']组织内容角度和举例方向,所有卡片内容需紧扣此主题.\n\n'
            if theme else ""
        )
        + "[通用写作规则]\n"
        + '- 具体比抽象好:"每天学 50 分钟" > "适量学习",'
        + '"生理学-血液循环" > "复习生理"\n'
        + "- 标题控制在 25 字以内(小红书卡片 3:4 比例最多容纳 25 字)\n"
        + "- 每张卡片 emoji 用量按角色风格控制\n"
        + "- 输出纯 JSON,不要 Markdown 语法\n"
        + "- 所有日期不超出考试日"
        + (
            "\n\n★★★ 人设优先原则（比所有其他规则都重要）★★★\n"
            + "- 你的第一身份是考过的学姐/学长,不是培训机构老师.\n"
            + "- 数据是帮你写对的,不是让你照抄的.以下是数据库提供的真实信息,\n"
            + "  你要用自己的话翻译成人话再用.\n"
            + '- 判断标准:写完一句话后问自己——我会跟朋友这样发微信吗?\n'
            + "  如果不会 → 重写.用更短的句子,更口语的词,甚至\"这块\"\"啃\"\"刷吐\"\n"
            + "- 宁可只讲透 1 个考点用日常口语,也不要列 3 个用教材术语.\n"
            + "- 每张卡片至少用 1 个\"我当时\"\"我去年\"\"有一次我\"的个人经历句式.\n"
            + "- 禁止的行为:\n"
            + '  ❌ 像教材一样逐条列定义\n'
            + '  ❌ 用\"值得注意的是\"\"根据...规定\"\"教材上写\"等学术腔\n'
            + '  ❌ 把 facts_brief 里的真题原文直接复制粘贴当内容\n'
            + '  ❌ 公式+例题+解析的三段式课本写法\n'
            + "\n★★★ 打破模式——和人设优先同级 ★★★\n"
            + "- 如果连续两条用了同一种句式 → 第三条必须换,换开头、换长短、换语气\n"
            + "- 如果你发现自己在写\"考点→考法→记法\"三段式 → 下一条只说\"这个背就完了,没啥技巧\"\n"
            + "- 如果所有句子都工整 20-40 字 → 插一句 3-5 个字的,一个词也行,emoji 也行\n"
            + "- 允许说\"没用但真\"的细节:那年便利贴贴满冰箱、崩溃了出去吃了碗面、笔没水了用眉笔写——这些比\"后来我发现\"更像真人\n"
            + "- 你不是在写文章,是在发微信、发小红书——像说话,不像写作\n"
            + "- 允许吐槽、允许说半句、允许突然换话题、允许不加 emoji\n"
            + "\n[权威数据源——以下数字必须使用,但表达是你自己的话]\n"
            + facts_brief
            if facts_brief else ""
        )
    )

    # ── 提取考试日期的 M.D 格式 ──
    exam_md = ""
    if exam_date:
        try:
            d = datetime.strptime(exam_date, "%Y-%m-%d")
            exam_md = str(d.month) + "." + str(d.day)
        except Exception:
            exam_md = exam_date

    # ================================================================
    #  根据类型构造 prompt
    # ================================================================

    if card_type == "cover":
        # ============================================================
        # 封面卡片 (cover):时间锚定 + 身份唤醒
        # 公式:[假设句式] + [具体日期] + [身份唤醒] + [功能性承诺]
        # ============================================================
        # ★ V3.2 封面改造:考试日锚定 + 人群钩子
        exam_cn = str(d.month) + "月" + str(d.day) + "日" if exam_date and exam_md else exam_md

        # V3 DB 注入:优先使用数据库里的准确证书名
        cert_display_name = db_cert_name if db_cert_name else exam_name

        audience_hook_map = {
            "在职备考": "上班族碎片时间也能上岸",
            "宝妈备考": "带娃间隙我是怎么考过的",
            "零基础": "0基础也不怕,从入门到冲刺",
            "非科班": "跨专业照样上岸",
        }
        audience_hook = audience_hook_map.get(target_audience, "")

        # ★ 根据倒计时选择不同的时间锚定句式
        if countdown_days <= 7:
            time_anchor = exam_cn + cert_display_name + '已经开考了!'
        elif countdown_days <= 30:
            time_anchor = exam_cn + cert_display_name + '就要开考了!'
        else:
            time_anchor = exam_cn + cert_display_name + '进入备考关键期!'

        system_prompt = TONE_BLOCK + "\n\n---\n\n"

        system_prompt += (
            "你现在的任务:为[" + cert_display_name + "]考试生成一张封面卡片.\n\n"
            + "你想像一下:你刚加完班/哄完娃,打开小红书,想分享点对备考人有用的.\n"
            + "不需要套路——想到什么写什么,但要让人读完觉得\"这人懂我\".\n\n"
            + "下面是上岸的人写过的封面感觉,感受味道,别抄结构:\n"
            + '  - 提问戳痛点:\"' + cert_display_name + '还剩' + str(countdown_days) + '天,在职党来不来得及?\"——点开看答案\n'
            + '  - 身份共鸣:\"我一个' + (target_audience or '零基础') + '都能过,你也可以\"——先建立信任\n'
            + '  - 反常识:\"谁说' + cert_display_name + '要学满1000小时?我每天90m也过了\"——打破心理门槛\n'
            + "  以上是味道示范,不是填空题.感受那种\"用真话戳人\"的感觉,自己决定怎么写.\n\n"
            + "标题:\n"
            + "- 12-25 字,像小红书博主会起的标题,不像机构广告\n"
            + "- 禁止:[XX备考指南][通关秘籍][必过攻略][上岸计划]等模板标题\n"
            + "- 禁止[假如你从XX开始备考]句式——日期是考试日不是开始备考日\n"
            + "- 倒计时能自然融进去就融,不能别硬塞\n\n"
            + "subtitle:\n"
            + "- 写 1-3 句话,像发朋友圈配文,不是写产品描述\n"
            + "- 你可以:说说去年这时候的自己在干嘛 / 吐槽备考多累 / 讲一个只有考过的人才懂的痛点 / 就简单一句不加 emoji\n"
            + "- 不用非得凑倒计时+痛点+价值三件套——那个是模板,你是人\n"
            + "- [·]分隔符可以用也可以不用,怎么自然怎么来\n"
            + "- 如果是" + (target_audience or "零基础") + "人群,提到他们的真实困境,但不是\"碎片时间也能上岸\"这种正确废话\n\n"
            + "3. 输出纯 JSON,不要 Markdown\n\n"
            + "输出格式(严格按此 JSON):\n"
            + "{\n"
            + '  "type": "cover",\n'
            + '  "title": "你写的标题(15-25字,不要照抄示例)",\n'
            + '  "subtitle": "你写的副标题(2-3句话,用·连接)",\n'
            + '  "days": [],\n'
            + '  "items": [],\n'
            + '  "qrcode_url": ""\n'
            + "}"
        )

        user_prompt = (
            "考试名称:" + cert_display_name + "\n"
            + "考试日期:" + exam_date + "(考试日在" + exam_cn + ")\n"
            + "倒计时天数:" + str(countdown_days) + " 天\n"
            + "当前角色:" + role + "\n"
            + "目标人群:" + (target_audience or "未指定") + "\n\n"
            + "请生成封面卡片.标题从3个方向选1个,用你自己的话写.\n"
            + "subtitle 包含倒计时+真实痛点+价值暗示,用[·]连接.\n"
            + (
                "\n## 爆款标题参考（学习其语气和节奏,不要照抄）\n\n"
                + "\n".join(f"- {s.get('title', '')}（{s.get('topic_type', '')}·{s.get('likes', 0)}赞）" for s in viral_samples if s.get('title'))
                + "\n\n## 爆款常用标签（可参考融入标题或副标题的氛围）\n"
                + "、".join(viral_tags)
                + "\n"
                if viral_samples or viral_tags else ""
            )
        )

    elif card_type == "plan":
        # ============================================================
        # 学习计划卡片 (plan):三阶段 + 强度递增 + 日颗粒度 + 复盘日
        # 公式:[阶段名+精确起止日期] -> [阶段目标] -> [每日:日期+章节+时长] -> [工具清单]
        # ============================================================
        phase_name = current_card.get("phase_name", "基础阶段")
        phase_desc = current_card.get("phase_desc", "")
        daily_hours = current_card.get("daily_hours", "2h")
        phase_days = current_card.get("phase_days", 14)
        start_date = current_card.get("start_date", "")
        end_date = current_card.get("end_date", "")
        days_grid = current_card.get("days_grid", [])
        grid_count = len(days_grid)
        cumulative_offset = current_card.get("cumulative_days_before", 0)  # ★ 之前阶段已占用的天数
        viral_titles = current_card.get("viral_titles", [])  # ★ V3: 爆款标题参考

        # ★ V3.2 计划改造:加 mentor_note(过来人心得) + 学姐碎碎念穿插
        system_prompt = TONE_BLOCK + "\n\n---\n\n"

        system_prompt += (
            "你现在的任务:为[" + exam_name + "]考试的[" + phase_name + "]生成学习计划.\n"
            + "你的角色是去年考过的过来人,这份计划是你当时亲自执行过的.\n\n"
            + "* 计划卡片核心公式:过来人心得(2-3句) + 三阶段拆分 + 每日时长递增 + 每5-6天一个复盘日 + 任务具体到章节名\n\n"
            + "硬约束规则(必须遵守):\n\n"
            + "0.[★ 新增:过来人心得 mentor_note]\n"
            + '   在 tasks 之前,写 2-3 句[过来人心得],分享你当时在这个阶段的真实感受和踩过的坑.\n'
            + '   - 不要鸡汤,要具体.不说[加油你可以的],要说[我当时在这里卡了一周,后来发现...]\n'
            + '   - ' + phase_name + '阶段示例参考:\n'
        )
        if '基础' in phase_name:
            system_prompt += (
                '     "基础阶段最容易放弃——每天翻开书觉得内容太多.我的经验:第一周别想全部学完,先建框架.\n'
                + '      我当时用三色笔记把各科目录抄了一遍,虽然花了两天但后面学习效率翻倍."\n'
            )
        elif '强化' in phase_name:
            system_prompt += (
                '     "强化阶段是最痛苦的——做题错一堆,开始怀疑自己.后来发现错题才是宝藏,\n'
                + '      每道错题背后都是一个考点盲区.别怕错,怕的是错了不看."\n'
            )
        elif '冲刺' in phase_name:
            system_prompt += (
                '     "冲刺阶段反而心态最稳——该学的都学了.最后两周不学新内容,就刷错题+背口诀.\n'
                + '      考前一天我把所有口诀默写了一遍,考场上直接条件反射."\n'
            )
        else:
            system_prompt += (
                '     "这个阶段很关键——我当时也是一边摸索一边调整.找到适合自己的节奏比照搬别人的计划更重要.\n'
                + '      累了就休息半天,状态好了多学一会,重要的是保持每天都在往前走."\n'
            )
        system_prompt += (
            "   你的 mentor_note 必须像真人说的话,不是AI总结,具体到[我当时做了什么].\n\n"
            + (
                "★★★ 零基础适配规则（当前目标人群：" + target_audience + "）★★★\n"
                + "如果目标人群是[零基础]:\n"
                + "- 基础阶段天数占比 ≥ 总天数的 40%,不能少于 10 天\n"
                + "- 前 5 天只学一门课,第 6 天起再引入第二门\n"
                + "- 真题卷至少第 14 天后再出现\n"
                + '- 禁止使用"直接上真题""跳过基础看高频""不用看教材只看笔记"等提速表述\n'
                + "- 每日任务必须标注具体章节名和页码定位,让零基础读者知道该翻到哪页\n\n"
                if target_audience in ("零基础", "非科班") else ""
            )
            + "1.[标题用过来人的话说——不要写成课表]\n"
            + '   方向参考（感受味道,不是填空）:\n'
            + '   - 阶段感:"第一周打基础：从翻开书到找到节奏"\n'
            + '   - 进度感:"中间这12天最煎熬,但熬过去就稳了"\n'
            + '   - 目标感:"冲刺期：不学新的,只巩固旧的"\n'
            + '   标题让人知道时间跨度(第' + str(cumulative_offset + 1) + '-' + str(cumulative_offset + phase_days) + '天)'
            + '   ——但用你自己的方式表达,不要"基础阶段""强化阶段"这种课表标签.\n'
            + '   如果你觉得"第X-Y天"太死板,可以用口语化表达,比如"头4天""中间那33天".\n\n'
            + "2.[副标题要求]\n"
            + "   副标题必须包含阶段目标和每日时长趋势,口语化表达,例如:\n"
            + '   - 基础阶段:"搭建知识框架,每天 50m→90m,稳住节奏就是赢"\n'
            + '   - 强化阶段:"查漏补缺,每天 90m→120m,错题才是宝藏"\n'
            + '   - 冲刺阶段:"考前冲刺,每天 120m,不学新的只巩固旧的"\n\n'
            + "3.[* 时长必须递增]\n"
            + "   基础阶段:前 1/3 天 50m,中间 1/3 天 70m,后 1/3 天 90m\n"
            + "   强化阶段:前 1/3 天 90m,中间 1/3 天 105m,后 1/3 天 120m\n"
            + "   冲刺阶段:全程 120m\n"
            + "   在 task 文本中用括号标注时长,例如[生理学-细胞功能(50m)]\n"
            + "   ⚠️ 时长单位用 m 不要用 min,例如 50m 不是 50min\n\n"
            + "4.[* 每 5-6 天必须有一个复盘日或休息日]\n"
            + "   每 5-6 个学习日之后插入一个:\n"
            + '   - "☑ 复盘日 - 整理框架 - 整理错题"(每 5-6 天一次)\n'
            + '   - "💬 学姐碎碎念:..."(每 5-6 天穿插一条,20-40字,跟在当天学习任务后面,不能独占一天)\n'
            + '     ⚠️ 碎碎念不要每次都是"困难→方法→顿悟"三段论.可以:\n'
            + '     - 一句吐槽:"这章我当时背了三遍还是混,佛了"\n'
            + '     - 一个画面:"药化那章我把母核结构画满了整面墙"\n'
            + '     - 一个没用的细节:"有次学一半睡着了,口水把笔记洇了半页"\n'
            + '     - 自嘲:"这公式我考场上现推的,居然推对了"\n'
            + '     每次碎碎念的语气和内容都要不一样.\n'
            + '   - "休息 ♨️"(每 12-14 天安排一次完整休息)\n'
            + "   没有复盘日的计划 = 看起来很美但没人会执行 = 用户不会收藏\n\n"
            + "5.[* 任务必须具体到章节/系统名]\n"
            + '   ✅ 推荐格式(用哪个随你,混着用更像真人):\n'
            + '     - 标准:\"药一-药物化学结构与命名(50m)\"\n'
            + '     - 带情绪:\"继续啃药化…这章真的要命(70m)\"\n'
            + '     - 场景化:\"午休刷30m法规,晚上接着药二(90m)\"\n'
            + '     - 简洁:\"药综-处方审核(90m)\"\n'
            + '   ❌ 禁止:\"复习生理\"\"做题\"\"学新章节\"\"巩固知识点\"——太笼统\n'
            + '   ⚠️ 不要每条都是同一种格式——混着用上面4种,有的带括号时长有的不带.\n\n'
            + "6.[每个阶段末尾标注配套工具]\n"
            + "   在阶段最后 2-3 天的 task 中穿插工具提醒:\n"
            + '   基础阶段末尾:"📋 用三色笔记整理知识框架"\n'
            + '   强化阶段末尾:"📝 用 600 母题刷章节真题"\n'
            + '   冲刺阶段末尾:"📖 用记忆口诀过一遍高频考点"\n\n'
            + "7.[tasks 数组长度必须等于 " + str(grid_count) + "]\n"
            + "   按顺序对应日期框架的每一天,一个不能多一个不能少\n\n"
            + "输出格式(mentor_note 是新增字段,tasks 只输出任务字符串数组):\n"
            + "{\n"
            + '  "type": "plan",\n'
            + '  "title": "你的阶段标题(过来人口吻+天数范围,不要"基础阶段"这种课表标签)",\n'
            + '  "subtitle": "你的副标题(阶段目标+每日时长趋势,口语化)",\n'
            + '  "mentor_note": "基础阶段最容易放弃...我当时用三色笔记把各科目录抄了一遍,花了两天但后面效率翻倍.",\n'
            + '  "tasks": ["生理学-细胞基本功能(50m)", "生理学-血液(50m)", "💬 学姐碎碎念:当时我最崩溃的是...", "☑ 复盘日 - 整理框架 - 整理错题", ...],\n'
            + '  "items": [],\n'
            + '  "qrcode_url": ""\n'
            + "}"
        )

        user_prompt = (
            "考试名称:" + exam_name + "\n"
            + "考试日期:" + exam_date + "\n"
            + "阶段名称:" + phase_name + "\n"
            + "阶段说明:" + phase_desc + "\n"
            + "本阶段天数:" + str(phase_days) + " 天\n"
            + "起始日期:" + start_date + "\n"
            + "结束日期:" + end_date + "\n"
            + "每日建议时长趋势:从基础到冲刺阶段时长递增\n"
            + "日期框架已有 " + str(grid_count) + " 天\n"
            + "当前角色:" + role + "\n\n"
            + "请为该阶段的每一天生成任务名,tasks 数组长度必须为 " + str(grid_count) + ".\n\n"
            + "重要提醒:\n"
            + "- 先写 mentor_note(2-3句过来人心得,匹配" + phase_name + "的真实感受,具体到[我当时做了什么])\n"
            + "- 任务名必须具体到章节(如[生理学-血液循环])\n"
            + "- 每 5-6 天插入复盘日或[💬 学姐碎碎念](碎碎念必须跟在学习任务后面,不能独占一天)\n"
            + "- 时长随天数递增\n"
            + "- 禁止出现[复习][做题][学习]这类空洞词汇\n"
            + "- 整张卡片要让人感觉是一个真人在分享备考过程,不是AI生成的列表\n"
            + (
                "\n## 真题参考（来自数据库——真题日 / 刷题日的题目从这里取）\n\n"
                + "\n".join(
                    f"- [{q.get('subject_name', '')}][{q.get('exam_year', '')}年][{q.get('question_type', '')}] {q.get('content', '')[:100]}"
                    for q in exam_questions
                )
                + "\n\n真题日的 task 要引用真实题目类型和科目,不要写\"做真题\"这种空洞描述.\n"
                if exam_questions else ""
            )
            + (
                "\n## 爆款标题参考（学习其语言风格,不要抄标题）\n\n"
                + "\n".join(f"- {t}" for t in viral_titles)
                + "\n"
                if viral_titles else ""
            )
        )

    elif card_type == "subjects":
        # ============================================================
        # 考试科目卡片 (subjects):分值信号 + 差异化策略
        # 公式:[分值占比排序] -> [按性价比顺序] -> [每科一句话策略] -> [战略性放弃]
        # ============================================================
        system_prompt = TONE_BLOCK + "\n\n---\n\n"

        system_prompt += (
            "你现在的任务:为[" + exam_name + "]考试生成一张考试科目与备考策略卡片.\n"
            + "你的角色是一个考过的过来人,你知道哪些科目值得花时间,哪些可以先放一放.\n\n"
            + "* 科目卡片核心公式:按分值/重要性排序 -> 每科一句话策略 -> 点名可以战略性放弃的模块\n\n"
            + "核心原则:你不是在罗列知识点,你是在告诉用户----你的时间花在哪里最划算.\n\n"
            + "硬约束规则:\n"
            + "1. 列出 4-6 个考试科目/单元,按性价比从高到低排序,不是按课本目录顺序\n"
            + "2. 每个科目 label = 科目名(4-6 字)\n"
            + "   content = 涵盖内容 + 一句话备考策略(15-30 字)\n"
            + "   - 高分值+逻辑型学科:理解重于记忆,病例分析题多,建议先攻克\n"
            + "   - 高分值+记忆型学科:内容杂但题浅,持续刷题即可\n"
            + "   - 低分值+纯记忆型学科:考前两周突击背,现在不用花太多时间\n"
            + "3. * 必须有至少一个[战略性放弃]建议\n"
            + "   - 在最后一个 item 的 content 中,或单独一条 item\n"
            + "   - 点名说具体哪个模块可以先放一放,并说明原因\n"
            + "   - AI 天性倾向于全面不遗漏,你必须明确打破这个倾向\n"
            + "   - 例如:生化里冷门的酶学可以先放一放,主要攻克循环和呼吸系统\n"
            + "4. title 用过来人口吻概括科目价值,6-15字.示例方向:\n"
            + '   - "这4科我先啃哪门？""我的踩坑排序,别走弯路""按性价比排,最后那科可以放放"\n'
            + "   禁止:[考试科目一览]这种官方列表标题.\n"
            + "5. subtitle 自然地说明排序依据,不要用\"按性价比排序\"这种标签.\n"
            + '   示例:"去年我就是按这个顺序学的,省了至少两周" / "不是按课本目录排的,是按拿分效率排的"\n'
            + "6. 输出纯 JSON,不要 Markdown\n\n"
            + "输出格式:\n"
            + "{\n"
            + '  "type": "subjects",\n'
            + '  "title": "你的标题(过来人口吻,6-15字)",\n'
            + '  "subtitle": "你的副标题(自然说明排序依据)",\n'
            + '  "items": [\n'
            + '    {"label": "科目名", "content": "涵盖内容 + 备考策略(15-30字)"},\n'
            + '    {"label": "科目名", "content": "涵盖内容 + 策略.tips:XX分值低可战略性放弃"}\n'
            + '  ],\n'
            + '  "days": [],\n'
            + '  "qrcode_url": ""\n'
            + "}"
        )

        user_prompt = (
            "考试名称:" + exam_name + "\n"
            + "当前角色:" + role + "\n\n"
            + ("## 真实考试科目（来自数据库——请基于以下科目生成，不要凭记忆编造科目名）\n\n"
               + "\n".join(
                   f"- {s.get('subject_name', '')}"
                   + f"（满分 {s.get('full_mark', '?')} 分"
                   + (f"，合格线 {s['pass_mark']} 分" if s.get('pass_mark') else "")
                   + (f"，题型：{s['question_types']}" if s.get('question_types') else "")
                   + (f"，考试时长 {s['exam_duration']} 分钟" if s.get('exam_duration') else "")
                   + "）"
                   for s in subjects_data
               )
               + "\n\n"
               if subjects_data else "")
            + "请生成考试科目一览卡片.\n"
            + "要求按分值/重要性排序,每个科目给出差异化备考策略,"
            + "最后给出至少一个[可以战略性放弃]的具体建议.\n\n"
            + "记住:你不是在给官方考试大纲,你是在给备考建议."
            + "面面俱到的知识点列表没人看,没人存."
        )

    elif card_type == "notice":
        # ============================================================
        # 考前须知卡片 (notice):保持结构,增强人情味
        # ============================================================
        system_prompt = TONE_BLOCK + "\n\n---\n\n"

        system_prompt += (
            "你现在的任务:为[" + exam_name + "]考试生成一张考前注意事项卡片.\n"
            + "你的角色是一个每年帮学弟学妹整理考前清单的过来人,"
            + "你见过太多人因为忘带身份证进不了考场的惨剧.\n\n"
            + "规则:\n"
            + "1. 列出 7-8 条考前须知,覆盖:\n"
            + "   - 考试具体时间安排(从 " + exam_date + " 写出具体日期和上下午时间)\n"
            + "   - 必备物品清单(身份证,准考证,2B铅笔等)\n"
            + "   - 入场时间要求(提前多久到,迟到多久禁入)\n"
            + "   - 禁止携带物品(手机,电子手表等)\n"
            + "   - 考前生活提醒(睡眠,早餐,路线等)\n"
            + "   - 合格标准(滚动周期,及格线——从下方数据取,不要编造)\n"
            + "   - 免考条件(如果有,简单说明谁可以免考哪些科目)\n"
            + "2. 每条 label 2-4 字,content 15-30 字\n"
            + "3. 最后一条(考前提醒)要带一点人情味,例如:\n"
            + '   "前一晚别熬夜,早餐清淡为主,提前踩点考场路线"\n'
            + "4. ★ 涉及合格标准、免考条件的数字,必须与下方数据库数据一致\n"
            + "5. 输出纯 JSON,不要 Markdown\n\n"
            + "输出格式:\n"
            + "{\n"
            + '  "type": "notice",\n'
            + '  "title": "考前注意事项",\n'
            + '  "subtitle": "务必提前准备 - 每年都有人忘带身份证",\n'
            + '  "items": [\n'
            + '    {"label": "考试时间", "content": "' + exam_date + ' 上午 9:00-11:30,下午 14:00-16:30"},\n'
            + '    {"label": "必备物品", "content": "身份证原件,准考证,2B 铅笔,黑色签字笔,橡皮"},\n'
            + '    {"label": "入场时间", "content": "提前 30 分钟到达考场,开考 15 分钟后禁止入场"},\n'
            + '    {"label": "禁止携带", "content": "手机,电子手表,计算器,草稿纸(考场提供)"},\n'
            + '    {"label": "考前提醒", "content": "前一晚设好闹钟,早餐清淡为主,提前踩点考场"}\n'
            + '  ],\n'
            + '  "days": [],\n'
            + '  "qrcode_url": ""\n'
            + "}"
        )

        user_prompt = (
            "考试名称:" + exam_name + "\n"
            + "考试日期:" + exam_date + "\n"
            + "当前角色:" + role + "\n\n"
            + ("## 真实考试安排（来自数据库——日期必须使用以下数据，不要编造）\n\n"
               + (f"- 考试年份：{schedule_data.get('year', '')} 年\n" if schedule_data.get('year') else "")
               + (f"- 考试日期：{schedule_data.get('exam_date', '')}\n" if schedule_data.get('exam_date') else "")
               + (f"- 报名时间：{schedule_data.get('registration_start', '')} 至 {schedule_data.get('registration_end', '')}\n"
                  if schedule_data.get('registration_start') else "")
               + (f"- 成绩公布：{schedule_data.get('result_date', '')}\n" if schedule_data.get('result_date') else "")
               + "\n"
               if schedule_data and any(schedule_data.values()) else "")
            + "请生成考前注意事项卡片,7-8 条须知.最后一条带点人情味.\n"
            + "涉及合格标准、免考条件、注册周期的数字必须与下方数据一致.\n"
            + (
                "\n## 报考条件（来自数据库——涉及学历/工作年限时使用以下数据）\n\n"
                + "\n".join(
                    f"- {c.get('degree_level', '')}·{c.get('major_category', '')}"
                    + (f": 施工相关工作 {c.get('work_years_construction', '')} 年" if c.get('work_years_construction') else "")
                    + (f", 总工作年限 {c.get('total_work_years', '')} 年" if c.get('total_work_years') else "")
                    + (f"（依据：{c.get('source_clause_id', '')}）" if c.get('source_clause_id') else "")
                    for c in exam_conditions
                ) + "\n\n"
                if exam_conditions else ""
            )
            + (
                "\n## 合格标准（来自数据库——滚动周期/及格线从这里取）\n\n"
                + "\n".join(
                    f"- 滚动周期：{s.get('rolling_period', '')}，说明：{s.get('rule_description', '')}"
                    + (f"（依据：{s.get('source_clause_id', '')}）" if s.get('source_clause_id') else "")
                    for s in score_rules
                ) + "\n\n"
                if score_rules else ""
            )
            + (
                "\n## 免考政策（来自数据库——涉及免考条件时使用以下数据）\n\n"
                + "\n".join(
                    f"- 条件：{e.get('condition_description', '')}"
                    + (f"，免考：{e.get('exempt_subjects', '')}" if e.get('exempt_subjects') else "")
                    + (f"，仍需考：{e.get('remaining_subjects', '')}" if e.get('remaining_subjects') else "")
                    for e in exemptions_data
                ) + "\n\n"
                if exemptions_data else ""
            )
            + (
                "\n## 注册政策（来自数据库——涉及注册/继续教育时使用以下数据）\n\n"
                + "\n".join(
                    f"- 初始注册有效期：{r.get('initial_reg_period', '')}"
                    + (f"，续证周期：{r.get('renewal_period', '')}" if r.get('renewal_period') else "")
                    + (f"，继续教育学时：{r.get('ce_hours', '')}" if r.get('ce_hours') else "")
                    for r in registration_data
                ) + "\n\n"
                if registration_data else ""
            )
            + (
                "\n## 法条依据（引用时可标注出处）\n\n"
                + "\n".join(
                    f"- [{p.get('doc_title', '')} {p.get('doc_number', '')}] {p.get('clause_section', '')}: {p.get('clause_summary', p.get('clause_text', ''))[:100]}"
                    for p in policy_clauses
                ) + "\n"
                if policy_clauses else ""
            )
        )

    elif card_type == "cta":
        # ============================================================
        # 行动引导卡片 (cta):自然收尾,不要模板
        # ★ V3.2:去公式化,像真人聊完天自然收尾
        # ============================================================
        system_prompt = TONE_BLOCK + "\n\n---\n\n"

        system_prompt += (
            "你现在的任务:为[" + exam_name + "]考试生成一张 CTA(行动引导)卡片.\n"
            + "你的角色是一个考过的学姐/学长,刚分享完备考内容,现在自然收个尾.\n\n"
            + "★ 核心原则:你是在跟朋友聊天,不是在写营销文案.真诚 > 套路.\n\n"
            + "规则:\n"
            + "1. title:自然收尾,6-12 字,像聊天最后一句话.\n"
            + '   可以的方向:\n'
            + '   - 打卡型:"一起打卡!""每天进步一点点"\n'
            + '   - 实用型:"存下来慢慢看""考前翻出来过一遍"\n'
            + '   - 互动型:"聊聊你的进度""你到哪一步了"\n'
            + '   禁止:"关注我""点赞收藏""转发给需要的朋友""赶紧码住"(太营销了)\n\n'
            + "2. subtitle:2-4 句话,自然收尾,不要机械排列三要素.\n"
            + "   ★ 写法指南:\n"
            + "   - 根据前面卡片的内容自然引出,不要突然开始[我也是这么过来的]\n"
            + "   - 如果前面说了干货 → 收尾可以轻松一点,问个相关问题\n"
            + "   - 如果前面在鼓励 → 收尾可以简短有力,不用再灌鸡汤\n"
            + "   - 提问要真实:问一个备考人真正会纠结的问题,不要[你复习到哪了]这种通用废话\n"
            + '   - 如果暗示有资料:用[我整理了一份XX,需要的可以说一声]这种自然口吻\n'
            + '   - 不要用[滴滴我][评论区举手][评论区见]——太模板了,小红书用户一眼识破\n'
            + "   ★ 如何自然留口子（选 1-2 个方向,不要全用）:\n"
            + '   - 提问真实困境:"你XX部分卡在哪？我当时最崩溃的是XX,后来发现...你可以试试"\n'
            + '   - 暗示有工具:"我整理了一份XX,虽然简陋但帮了大忙,可以发你看看"(说完不再提,不要反复推销)\n'
            + '   - 打卡邀约:"我从今天开始每天会在评论区打卡,你可以一起来,互相监督"\n'
            + '   - 留悬念:"下一篇讲XX模块的避坑指南,当时我在这栽了最大的跟头"\n'
            + "   ★ 禁用语(出现即删):\n"
            + '   - "评论区滴滴我""评论区举手""评论区见""需要的扣1"\n'
            + '   - "我也是这么过来的""说实话""真的"\n'
            + '   - "完整资料都整理好了""需要的找我领"\n'
            + "3. * 禁止:加微信,关注我,点赞收藏,转发,扫码,私信我,领取\n"
            + "4. 输出纯 JSON,不要 Markdown\n\n"
            + "输出格式:\n"
            + "{\n"
            + '  "type": "cta",\n'
            + '  "title": "一起打卡!",\n'
            + '  "subtitle": "刚才那些考点都是我去年踩过坑才总结出来的.你现在哪科最没底?我看看能不能帮你理一下~",\n'
            + '  "days": [],\n'
            + '  "items": [],\n'
            + '  "qrcode_url": ""\n'
            + "}"
        )

        user_prompt = (
            "考试名称:" + exam_name + "\n"
            + "考试日期:" + exam_date + "\n"
            + "当前角色:" + role + "\n"
            + "目标人群:" + (target_audience or "未指定") + "\n\n"
            + "请生成 CTA 引导卡片.记住:\n"
            + "- 像朋友聊完天自然收尾,不要模板三件套\n"
            + "- 提问要真实,是备考人真正会纠结的问题\n"
            + "- 选一个自然的口子:\n"
            + "  * 提问真实困境 / 暗示有工具能帮上忙 / 打卡邀约 / 留悬念下篇继续\n"
            + "- 绝对不要[滴滴我][评论区举手][评论区见]等小红书模板用语\n"
            + (
                "\n## 爆款 CTA 语气参考（学习其自然收尾的方式,不要抄具体文案）\n\n"
                + "\n".join(
                    f"- [{s.get('topic_type', '')}] {s.get('title', '')} | likes:{s.get('likes', 0)} collects:{s.get('collects', 0)}"
                    for s in viral_samples if s.get('title')
                )
                + "\n\n常用标签氛围参考：" + "、".join(viral_tags)
                + "\n"
                if viral_samples or viral_tags else ""
            )
            + "- 如果暗示有资料,用最自然的口吻,像[我整理了一份XX,需要的说一声]"
        )

    # ================================================================
    # * 第二层新增:resources(备考资料清单)
    # ================================================================
    elif card_type == "resources":
        exam_year = exam_date[:4] if exam_date else "2026"
        exam_short = exam_name.replace("资格证", "").replace("工程师", "") if exam_name else exam_name

        system_prompt = TONE_BLOCK + "\n\n---\n\n"

        system_prompt += (
            "你现在的任务:为[" + exam_name + "]考试生成一张备考资料清单卡片.\n"
            + "你的角色是一个已经考过的过来人,你知道哪些资料真正有用,哪些是浪费时间.\n\n"
            + "* 资料卡片核心原则:覆盖用户的 6 种核心需求,每份资料解决一个具体痛点\n\n"
            + "规则:\n"
            + "1. 列出 6-8 个备考资料,资料命名要多样——不要全部统一格式(全部标年份像AI批量生成的):\n"
            + "   - 2-3 个用口语简称,如[药二高频考点笔记(考前3天还在看的)]\n"
            + "   - 2-3 个用标准命名,如[" + exam_year + " " + exam_short + "三色笔记.pdf]\n"
            + "   - 2-3 个用场景化命名,如[我去年整理的错题本(药二+药综)]\n"
            + "2. 每个资料配一句话用途说明(content,不超过 15 字),说清楚这份资料解决什么问题\n"
            + "3. 资料要覆盖用户的 6 种核心需求:\n"
            + "   - 不知道重点在哪 -> 三色笔记\n"
            + "   - 看完记不住 -> 记忆口诀\n"
            + "   - 不会做题 -> 母题/真题\n"
            + "   - 不知道进度 -> 打卡表\n"
            + "   - 心里没底 -> 历年真题/模拟卷\n"
            + "   - 知识碎片化 -> 思维导图\n"
            + "4. title 用你的人设口吻写,6-15字.示例方向:\n"
            + '   - "我去年用的这几份,比教材好用" / "备考资料别贪多,这6份就够了"\n'
            + "   禁止:[备考资料清单]这种清单标题.\n"
            + "5. subtitle 自然补充,13字以内.示例:\n"
            + '   - "不用每本都看,挑你弱的" / "最后那份救了我的命"\n'
            + "6. 输出纯 JSON,不要 Markdown\n\n"
            + "输出格式:\n"
            + "{\n"
            + '  "type": "resources",\n'
            + '  "title": "你的标题(用你的人设口吻,6-15字)",\n'
            + '  "subtitle": "你的副标题(自然补充,13字以内)",\n'
            + '  "items": [\n'
            + '    {"label": "' + exam_year + ' ' + exam_short + '三色笔记", "content": "一句用途说明,不超过15字"},\n'
            + '    {"label": "' + exam_year + ' ' + exam_short + '600母题＋解析", "content": "一句用途说明,不超过15字"}\n'
            + '  ],\n'
            + '  "days": [],\n'
            + '  "qrcode_url": ""\n'
            + "}"
        )

        user_prompt = (
            "考试名称:" + exam_name + "\n"
            + "考试日期:" + exam_date + "\n"
            + "当前角色:" + role + "\n\n"
            + "请生成备考资料清单卡片,列出 6-8 个实用备考资料.\n"
            + "每份资料说明它解决什么具体问题(不超过 15 字)."
        )

    # ================================================================
    # * 第二层新增:priority(分值分布与备考优先级)
    # ================================================================
    elif card_type == "priority":
        system_prompt = TONE_BLOCK + "\n\n---\n\n"

        system_prompt += (
            "你现在的任务:为[" + exam_name + "]考试生成一张分值分布与备考优先级卡片.\n"
            + "你的角色是一个熟悉考试评分规律的过来人,你知道哪些科目值得花时间,哪些可以放一放.\n\n"
            + "* 核心原则:你不是在罗列知识点,你是在告诉用户----你的时间花在哪里最划算.\n\n"
            + "规则:\n"
            + "1. 列出 4-6 个科目/单元,按**性价比从高到低**排序,不是按课本目录顺序\n"
            + "2. 每个科目的 label 格式为[① 单元名(约 XX 分)],必须包含大约分值或重要性信号\n"
            + '   - 重要性信号示例:"占比最高""几乎必考""约 20 分""分值大头"\n'
            + "3. 每个科目的 content 是**一句话备考策略**,区分不同科目的备考方法:\n"
            + "   - 高分值+逻辑型:'理解重于记忆,病例分析题多,建议先攻克'\n"
            + "   - 高分值+记忆型:'内容杂但题浅,持续刷题即可'\n"
            + "   - 低分值+纯记忆型:'考前两周突击,此时不建议花太多时间'\n"
            + "4. * 最后一条 content 必须是**战略性放弃建议**:\n"
            + "   - 点名说具体哪个模块可以先放一放,以及为什么\n"
            + "   - 例如:'生化里冷门的酶学可以先放一放,主要攻克循环和呼吸系统'\n"
            + "5. title 用过来人口吻,6-15字.示例:\n"
            + '   - "这4科,按这个顺序学最省力" / "我的踩坑排序——别按课本目录来"\n'
            + "6. subtitle 自然补充排序理由,不要用\"按分值排序\"这种标签.\n"
            + "7. 输出纯 JSON,不要 Markdown\n\n"
            + "输出格式:\n"
            + "{\n"
            + '  "type": "priority",\n'
            + '  "title": "你的标题(过来人口吻,6-15字)",\n'
            + '  "subtitle": "你的副标题(自然说明排序理由)",\n'
            + '  "items": [\n'
            + '    {"label": "① 第③单元-消化系统(约 80 分)", "content": "分值占比最高,病例分析题多,理解重于记忆,建议先拿下"},\n'
            + '    {"label": "④ 第①单元-预防+心理+法规(约 20 分)", "content": "纯记忆型,考前两周突击即可,可以先放一放,把时间花在循环和呼吸系统上"}\n'
            + '  ],\n'
            + '  "days": [],\n'
            + '  "qrcode_url": ""\n'
            + "}"
        )

        user_prompt = (
            "考试名称:" + exam_name + "\n"
            + "考试日期:" + exam_date + "\n"
            + "当前角色:" + role + "\n\n"
            + ("## 真实分值数据（来自数据库——分值分布必须使用以下数据）\n\n"
               + "\n".join(
                   f"- {s.get('subject_name', '?')}"
                   + f"：满分 {s.get('full_mark', '?')} 分"
                   for s in priority_data.get("subjects", [])
               )
               + "\n\n"
               + "## 各科目考点数量统计\n\n"
               + "\n".join(
                   f"- {subj}: {cnt} 个考点"
                   for subj, cnt in priority_data.get("kp_counts", {}).items()
               )
               + "\n\n请基于以上真实分值数据生成优先级排序，不要凭记忆估算分值。\n"
               if priority_data and priority_data.get("subjects") else "")
            + "请生成备考优先级指南卡片,按分值高低排序,并给出战略性放弃建议.\n"
            + "记住:你的核心价值是告诉用户'时间花在哪里最划算',而不是罗列所有知识点."
        )

    # ================================================================
    # * 第二层新增:mnemonics(记忆口诀)
    # ================================================================
    elif card_type == "mnemonics":
        system_prompt = TONE_BLOCK + "\n\n---\n\n"

        system_prompt += (
            "你现在的任务:为[" + exam_name + "]考试生成一张记忆口诀卡片.\n"
            + "你的角色是一个靠口诀硬背下高频考点的过来人,你知道'怪'才记得住.\n\n"
            + '* 核心原则:"怪"才记得住.太顺了像打油诗反而记不住,越离谱越有画面感越好记.\n\n'
            + "规则:\n"
            + "1. 生成 3-5 条记忆口诀,每条针对一个具体的知识点或模块\n"
            + "2. 每个 item 的 label = 口诀本身(6-15 字),用谐音,画面感,生活化表达,允许有一点'怪'的强行谐音\n"
            + "3. 每个 item 的 content = 逐字拆解映射,用[->]连接\n"
            + '   例如:"胖->锅炉,游客->压力容器,专->电梯,电->起重机械"\n'
            + "4. 可以在口诀前面加一句人味引入语,如'这部分我当时也记不住,后来靠口诀硬背下来的:'\n"
            + "5. title 固定为[记忆口诀速记]\n"
            + "6. subtitle 固定为[" + exam_name + " - 笑着笑着就记住了]\n"
            + "7. 输出纯 JSON,不要 Markdown\n\n"
            + "示例口诀风格(供参考,不要照抄):\n"
            + '- "胖游客专用电压力锅" -> 特种设备类型口诀\n'
            + '- "那英三连冠果然有水平" -> 钠通道阻滞剂口诀\n'
            + "- 你的口诀应该针对 " + exam_name + " 的真实考点\n\n"
            + "输出格式:\n"
            + "{\n"
            + '  "type": "mnemonics",\n'
            + '  "title": "记忆口诀速记",\n'
            + '  "subtitle": "' + exam_name + ' - 笑着笑着就记住了",\n'
            + '  "items": [\n'
            + '    {"label": "6-15字的口诀", "content": "胖->锅炉,游客->压力容器,专->电梯,电->起重机械(逐字拆解映射)"}\n'
            + '  ],\n'
            + '  "days": [],\n'
            + '  "qrcode_url": ""\n'
            + "}"
        )

        user_prompt = (
            "考试名称:" + exam_name + "\n"
            + "当前角色:" + role + "\n\n"
            + ("## 需要编口诀的考点（来自数据库——请为以下每个考点各编一条口诀）\n\n"
               + "\n".join(
                   f"- [{k.get('frequency', '')}] {k.get('kp_name', '')}"
                   + (f"（{k.get('subject_name', '')}）" if k.get('subject_name') else "")
                   for k in mnemonic_anchors
               )
               + "\n\n"
               if mnemonic_anchors else "")
            + "请为 " + exam_name + " 的高频考点生成 3-5 条记忆口诀,每条附上逐字拆解映射.\n"
            + "注意:口诀要生活化,有画面感,允许强行谐音,越离谱越好记."
        )

    # ================================================================
    # ================================================================
    # * study_material(学习资料卡片)
    # 结构:知识模块标题 + 核心考点列表 + 记忆方法
    # 优先使用 kp_data(数据库注入), 无数据时 LLM 自由生成
    # ================================================================
    elif card_type == "study_material":
        assigned_chapter = (current_card.get("assigned_chapter") or "").strip()
        avoid_duplicate = (current_card.get("avoid_duplicate_with") or "").strip()  # ★ V3: 避免与其他卡片重复

        system_prompt = TONE_BLOCK + "\n\n---\n\n"

        system_prompt += (
            "你现在的任务:为[" + exam_name + "]考试生成一张学习资料卡片.\n"
            + "你的角色是一个考过的学姐,正在用微信给学弟学妹讲高频考点.\n\n"
            + "* 学习资料卡片核心原则:像发微信讲考点,不是抄课本.每条考点讲清楚:①考什么 ②怎么考 ③怎么记.\n\n"
            + "硬约束规则:\n"
            + "1. 生成 2-3 个知识模块(study_material 数组),每个模块包含:\n"
            + "   - module_title:口语化标题(10-20 字),如[呼吸系统 - 每年必考的 3 个病]\n"
            + "   - key_points:核心考点列表(3-5 条),每条 30-60 字,用口语写,结构为[考点+考试怎么考+记忆技巧]\n"
            + "   - memory_tips:补充记忆方法(1-2 条,如果 key_points 里已经写了记忆技巧可以不重复)\n\n"
            + '2. key_points 的写法:像学姐在给你发微信讲考点.没有固定格式,以下是你可能会用的几种方式:\n'
            + '   - 讲透型(考什么+怎么考+怎么记):"COPD 诊断就一个数 FEV1/FVC＜0.7——选择题给肺功能数据让你判断.记法:0.7 就是慢阻肺的身份证号."\n'
            + '   - 讲一半型(考什么+怎么考):"过敏性紫癜 vs 血小板减少性紫癜:前者血小板正常后者↓,病例题给紫癜加血小板数值让你判.区分就一句话:过敏的日子不降血小板."\n'
            + '   - 只吐槽型:"呋塞米在哪类?IV 类,低溶低渗.这题每年都出,2019 考了 2023 又考.背就完了,没啥技巧."\n'
            + '   ⚠️ 三种方式混着用,不要每条都讲透.偶尔说"这个背就完了"比每条都配记忆技巧更真实.\n'
            + '   ❌ 禁止:"COPD 的诊断标准为 FEV1/FVC＜0.7.主要病因包括吸烟、空气污染、职业粉尘."——抄课本,没人看.\n'
            + "3. 数值和定义必须准确(不能把 0.7 写成 0.8),但表达方式是口语.\n"
            + "4. 多数 key_point 要让人知道考试怎么考,但不需要每条都写.\n"
            + "5. 讲透 2-3 个最重要考点 > 列 8 个没人读的条目.\n\n"
            + "❌ 内容禁区(学习资料卡片不是考试介绍):\n"
            + "6. 严禁生成以下内容:\n"
            + '   - 报考条件/报名时间/报名流程/考试费用\n'
            + '   - 考试科目介绍/考试时间安排/题型分布说明\n'
            + '   - 成绩查询/证书领取/合格标准\n'
            + '   - 任何跟[考试知识考点]无关的行政信息\n'
            + "7. ★ 自检:每生成一条 key_point 前问自己——这条内容考试会考吗?\n"
            + '   如果不会考 → 删掉重写.这里要的是[考点知识],不是[考试说明].\n\n'
            + "📐 优先级(冲突时遵守):\n"
            + "8. 可读性 > 完整性.宁可只讲透 3 个考点,也不要列 8 个没人读的条目.\n"
            + "9. 口语化 > 学术腔.这里是备考笔记,不是教材.\n\n"
            + (("📚 聚焦章节:[" + assigned_chapter + "],请优先覆盖此章节相关的考点.\n") if assigned_chapter else "")
            + (("⚠️ 排重约束:前面卡片已覆盖了[" + avoid_duplicate + "],你选的考点和例题必须跟这些完全不同,不能重叠.\n") if avoid_duplicate else "")
            + "\n"
        )

        if audience_profile:
            system_prompt += (
                "10. * 目标受众适配:\n"
                + "   - 人群:" + target_audience + "\n"
                + "   - 文案语气和举例方向需匹配此人群的特点\n"
                + "   - " + audience_profile["emphasis"] + "\n\n"
            )
        if theme:
            system_prompt += (
                "11. * 主题方向:" + theme + "\n"
                + "   - 选择的考点和举例应围绕此主题展开\n\n"
            )

        system_prompt += (
            "✍️ 写作感觉:\n"
            + "12. 你不是在写学习笔记,你是在给学弟学妹发微信:\n"
            + "    - 像说话不像写作——句子有长有短有碎片\n"
            + "    - 用[你]不用[考生]\n"
            + "    - 口语词放开用:[别指望][刷吐][看到题干就秒了][佛了][栽了]\n"
            + "    - 可以突然吐槽、可以只说半句、可以用一个词当一段\n"
            + "13. title 用你的人设口吻概括这页讲什么,8-18字.味道参考:\n"
            + '   - "药一代谢——计算题白送的分,别再丢了"\n'
            + '   - "这3个考点年年出,嚼碎了喂到你嘴边"\n'
            + '   - "法规假劣药秒判——看完这页不用翻书了"\n'
            + "   禁止:[N大模块 - 核心考点速记]这种格式.\n"
            + "14. subtitle 自然补充,13字以内:\n"
            + '   - "每年2-3分,背完稳拿" / "我考前3天还在翻这个" / "建议存下来考前过一遍"\n'
            + "15. ★ key_points 不是每条都要完整——有的讲透(考点+考法+记法),有的只说考法,有的一句带过.混着来像人.\n"
            + "16. memory_tips 不是每条考点都要配.有的考点就一句话能记住,不需要额外编口诀.\n"
            + "17. 输出纯 JSON,不要 Markdown\n\n"
            + "输出格式:\n"
            + "{\n"
            + '  "type": "study_material",\n'
            + '  "title": "你的标题(用你的人设口吻,8-18字)",\n'
            + '  "subtitle": "你的副标题(自然补充,13字以内)",\n'
            + '  "days": [],\n'
            + '  "items": [],\n'
            + '  "qrcode_url": "",\n'
            + '  "study_material": [\n'
            + '    {\n'
            + '      "module_title": "呼吸系统疾病 - 核心考点",\n'
            + '      "key_points": [\n'
            + '        "病因题高频:吸烟->COPD,粉尘->尘肺 —— 每年 2-3 分,题干给职业暴露史",\n'
            + '        "诊断标准:COPD 看 FEV1/FVC＜0.7,哮喘看可逆性 —— 选择题直接给肺功能数据让你判断"\n'
            + '      ],\n'
            + '      "memory_tips": [\n'
            + '        "吸烟咳嗽气短 -> COPD 三联征",\n'
            + '        "0.7 -> 一秒率诊断阈值,低于就扣 COPD 帽子"\n'
            + '      ]\n'
            + '    }\n'
            + '  ]\n'
            + "}"
        )

        user_prompt = (
            "考试名称:" + exam_name + "\n"
            + "当前角色:" + role + "\n"
            + ("目标受众:" + target_audience + "\n" if target_audience else "")
            + ("主题方向:" + theme + "\n" if theme else "")
            + ("\n## 真实考点（来自数据库——以下内容必须覆盖）\n\n"
               + "\n".join(
                   f"- [{k.get('frequency', '')}] {k.get('kp_name', '')}"
                   + (f"\n  说明：{k['note']}" if k.get('note') else "")
                   + (f"\n  所属科目：{k['subject_name']}" if k.get('subject_name') else "")
                   for k in kp_data
               )
               + "\n\n请将以上知识点用口语翻译成「学姐讲考点」的风格。数值和定义必须准确。\n"
               if kp_data else "")
            + "\n请为 " + exam_name + " 生成学习资料卡片内容.\n"
            + "重点:\n"
            + "- 选择 2-3 个高频知识模块\n"
            + "- 每个模块 3-5 条核心考点,要点明出题方向和为什么重要\n"
            + "- 每条考点配合一条记忆方法(可以谐音,联想,画面感)\n"
            + "- key_points 用口语写,像发微信讲考点.数值准确但表达要人话,每条说清[考试怎么考+怎么记]\n"
            + "- memory_tips 和标题翻译成人话,像发微信不是写总结\n"
            + (
                "\n## 真题参考（来自数据库——说明\"考试怎么考\"时从这里引用）\n\n"
                + "\n".join(
                    f"- [{q.get('subject_name', '')}][{q.get('exam_year', '')}年][{q.get('question_type', '')}] {q.get('content', '')[:120]}"
                    + (f"（解析：{q.get('analysis', '')[:80]}）" if q.get('analysis') else "")
                    for q in exam_questions
                ) + "\n\n"
                + "在写 key_points 时引用真实真题来佐证\"考法\".\n"
                if exam_questions else ""
            )
            + ("- 文案语气要贴合" + target_audience + "人群的特点\n" if target_audience else "")
            + ("- 内容要围绕[" + theme + "]这个主题\n" if theme else "")
        )

    else:
        # 兜底:未知类型,简单生成
        system_prompt = TONE_BLOCK + "\n\n---\n\n"

        system_prompt += (
            "请根据以下卡片类型生成一张小红书风格的备考卡片.\n\n"
            + "卡片类型:" + card_type + "\n"
            + "考试名称:" + exam_name + "\n\n"
            + "规则:\n"
            + "1. 标题 25 字以内\n"
            + "2. 输出纯 JSON,格式:\n"
            + '{"type": "' + card_type + '", "title": "...", "subtitle": "...", "days": [], "items": [], "qrcode_url": ""}'
        )

        user_prompt = (
            "考试名称:" + exam_name + "\n"
            + "考试日期:" + exam_date + "\n"
            + "当前角色:" + role + "\n\n"
            + "请生成 " + card_type + " 类型的卡片内容."
        )

    return {
        "system_prompt": system_prompt,
        "user_prompt": user_prompt,
        "card_index": str(current_card.get("index", 0)),
        "card_type": card_type,
    }
