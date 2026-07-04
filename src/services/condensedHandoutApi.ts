import { apiFetch } from './httpClient'

export type CondensedFeedbackStatus = 'usable' | 'needs_revision' | 'not_usable'

export interface CondensedChapterListItem {
  chapterCode: string
  title: string
  summary: string
  status: 'ready' | 'locked' | string
  feedbackStatus: CondensedFeedbackStatus | null
}

export interface CondensedCorePoint {
  name: string
  content: string
}

export interface CondensedSource {
  sourceType: 'textbook' | 'handout' | string
  sourceTitle: string
  page: string
  quote: string
}

export interface CondensedExamEvidence {
  year: number
  questionNo: string | null
  summary: string
}

export interface CondensedChapterDetail {
  subjectCode: string
  chapterCode: string
  title: string
  summary: string
  status: 'ready' | 'locked' | string
  content: {
    sourceSummary: string[]
    condensedBody: string[]
    learningGoals: string[]
    corePoints: CondensedCorePoint[]
    typicalQuestionPatterns: string[]
    reviewWarnings: string[]
  }
  sources: CondensedSource[]
  examEvidence: CondensedExamEvidence[]
  feedback: {
    status: CondensedFeedbackStatus | null
    note: string
  }
}

export interface CondensedChapterListResponse {
  subjectCode: string
  chapters: CondensedChapterListItem[]
}

export const FALLBACK_CONDENSED_DETAILS: CondensedChapterDetail[] = [
  {
    subjectCode: 'xi_yao_1',
    chapterCode: 'chapter_01',
    title: '第一章 药品与药品质量体系',
    summary: '概念、药品名称、质量标准、稳定性与检验',
    status: 'ready',
    content: {
      sourceSummary: [
        '本章原始材料来自 2026 教材第一章与 2026 深度精讲第一章，内容覆盖药物与药品定义、药品名称、药品质量属性、药典检验和稳定性试验。',
        '历年真题中，药品商品名、药品贮藏术语、稳定性试验等内容出现过直接或变形问法。',
      ],
      condensedBody: [
        '本章不要死背长定义，重点抓“用药目的、质量要求、名称体系、贮藏与检验”四条线。',
        '药品名称中，通用名称用于识别活性成分，化学名称用于准确表达结构，商品名称面向具体产品和企业品牌，可注册和申请保护。',
        '质量标准部分重点区分鉴别、检查、含量测定。稳定性试验常见问法集中在影响因素试验、加速试验、长期试验的目的和条件。',
      ],
      learningGoals: [
        '区分药物、药品、剂型、制剂、通用名称、商品名称和化学名称。',
        '掌握药品质量属性、质量标准、稳定性和药典检验项目的基本判断。',
        '识别“避光/遮光”“密闭/密封”等概念偷换。',
      ],
      corePoints: [
        { name: '药品名称', content: '通用名称、化学名称、商品名称的用途和保护属性。' },
        { name: '药品贮藏', content: '避光、遮光、密闭、密封、阴凉处等术语容易被交换。' },
        { name: '质量检验', content: '鉴别、检查、含量测定各自解决的问题不同。' },
        { name: '稳定性试验', content: '影响因素、加速、长期试验的目的不同。' },
      ],
      typicalQuestionPatterns: [
        '给出药品商品名、通用名、化学名的描述，判断哪项正确。',
        '给出贮藏术语，判断“遮光/避光”“密闭/密封”是否混淆。',
        '给出稳定性试验描述，判断属于影响因素、加速还是长期试验。',
      ],
      reviewWarnings: [
        '部分真题解析来源为回忆版，年份和题号需抽检。',
        '质量标准相关表述需与最新教材页码再核对。',
      ],
    },
    sources: [
      { sourceType: 'textbook', sourceTitle: '2026西药一教材', page: 'p7', quote: '商品名称由制药企业选择，和商标一样可以注册和申请专利保护。' },
      { sourceType: 'handout', sourceTitle: '2026西药一讲义', page: 'p8', quote: '考点：3 大药品名称：通用名称、化学名称和商品名称。' },
      { sourceType: 'handout', sourceTitle: '2026西药一讲义', page: 'p25', quote: '考点：药品稳定性试验。' },
    ],
    examEvidence: [
      { year: 2024, questionNo: 'Q3', summary: '关于药品商品名的说法。' },
      { year: 2023, questionNo: 'Q3', summary: '关于药品稳定性试验方法的说法。' },
      { year: 2022, questionNo: 'Q4', summary: '根据《中国药典》药品贮存规定进行判断。' },
    ],
    feedback: { status: 'needs_revision', note: '' },
  },
  {
    subjectCode: 'xi_yao_1',
    chapterCode: 'chapter_03',
    title: '第三章 药物的体内过程',
    summary: '吸收、分布、代谢、排泄、药动学参数',
    status: 'ready',
    content: {
      sourceSummary: [
        '本章原始材料来自 2026 教材第三章与 2026 深度精讲第三章，内容覆盖 ADME、生物利用度、生物等效性、药动学参数及临床意义。',
        '历年真题中，生物半衰期、生物等效性、清除率、表观分布容积等内容有直接考查。',
      ],
      condensedBody: [
        '药物的体内过程可以按 ADME 理解：吸收决定药物进入体循环的速度与程度，分布决定药物在血液和组织间的去向，代谢和排泄共同影响消除。',
        '生物半衰期是体内药量或血药浓度降低一半所需时间，反映药物从体内消除的快慢。不要理解成药效下降一半、吸收一半或肾脏排出一半。',
        '生物利用度关注药物被吸收入体循环的速度和程度；生物等效性研究常用于评价仿制药与参比制剂在吸收程度和速度上的一致性。',
      ],
      learningGoals: [
        '掌握吸收、分布、代谢、排泄的基本路径和影响因素。',
        '区分生物半衰期、清除率、表观分布容积、生物利用度和生物等效性。',
        '识别真题中对“定义换说法”和“参数临床意义”的考查。',
      ],
      corePoints: [
        { name: '生物半衰期', content: '血药浓度降低一半所需时间，反映消除快慢。' },
        { name: '清除率', content: '单位时间内从机体清除的含药血浆体积。' },
        { name: '表观分布容积', content: '体内药量与血药浓度之间的比例常数。' },
        { name: '生物等效性', content: '重点看研究设计、参比制剂和 PK 参数判断。' },
      ],
      typicalQuestionPatterns: [
        '给出某药半衰期，问其含义。',
        '给出一致性评价或仿制药情境，判断生物等效性研究要求。',
        '给出药动学参数描述，判断清除率、表观分布容积、米氏常数。',
      ],
      reviewWarnings: [
        '生物等效性研究要求需确认与当前考试教材表述一致。',
        '真题佐证可说明“曾考查”，不能直接说明“高频必考”。',
      ],
    },
    sources: [
      { sourceType: 'textbook', sourceTitle: '2026西药一教材', page: 'p78', quote: '生物半衰期指体内药量或血药浓度降低一半所需要的时间。' },
      { sourceType: 'handout', sourceTitle: '2026西药一讲义', page: 'p56', quote: '考点：生物半衰期 t1/2 及临床意义。' },
      { sourceType: 'handout', sourceTitle: '2026西药一讲义', page: 'p66', quote: '考点：生物等效性研究的基本要求。' },
    ],
    examEvidence: [
      { year: 2025, questionNo: 'Q2', summary: '关于瑞舒伐他汀钙生物半衰期为 19 小时的说法。' },
      { year: 2025, questionNo: 'Q3', summary: '关于生物等效性研究基本要求的说法。' },
      { year: 2022, questionNo: 'Q20', summary: '关于药物动力学参数的说法。' },
    ],
    feedback: { status: 'usable', note: '' },
  },
  {
    subjectCode: 'xi_yao_1',
    chapterCode: 'chapter_09',
    title: '第九章 皮肤和黏膜给药途径制剂与临床应用',
    summary: '气雾剂、贴剂、眼用制剂、栓剂、灌肠剂',
    status: 'locked',
    content: {
      sourceSummary: [],
      condensedBody: [],
      learningGoals: [],
      corePoints: [],
      typicalQuestionPatterns: [],
      reviewWarnings: ['备选章节，第一轮 MVP 不要求交付。'],
    },
    sources: [],
    examEvidence: [],
    feedback: { status: null, note: '' },
  },
]

export const FALLBACK_CONDENSED_CHAPTERS: CondensedChapterListItem[] = FALLBACK_CONDENSED_DETAILS.map(item => ({
  chapterCode: item.chapterCode,
  title: item.title,
  summary: item.summary,
  status: item.status,
  feedbackStatus: item.feedback.status,
}))

export function getFallbackCondensedDetail(chapterCode: string): CondensedChapterDetail {
  return FALLBACK_CONDENSED_DETAILS.find(item => item.chapterCode === chapterCode) ?? FALLBACK_CONDENSED_DETAILS[1]
}

function withTimeout<T>(promise: Promise<T>, ms = 1500): Promise<T> {
  return Promise.race([
    promise,
    new Promise<T>((_, reject) => {
      window.setTimeout(() => reject(new Error('API 请求超时，已使用本地样稿')), ms)
    }),
  ])
}

export function fetchCondensedChapters(): Promise<CondensedChapterListResponse> {
  return withTimeout(apiFetch<CondensedChapterListResponse>('/api/condensed-handouts/xi-yao-1/chapters'))
}

export function fetchCondensedChapterDetail(chapterCode: string): Promise<CondensedChapterDetail> {
  return withTimeout(apiFetch<CondensedChapterDetail>(`/api/condensed-handouts/xi-yao-1/chapters/${chapterCode}`))
}

export function submitCondensedFeedback(
  chapterCode: string,
  payload: { status: CondensedFeedbackStatus; note: string },
): Promise<{ chapterCode: string; feedback: CondensedChapterDetail['feedback'] }> {
  return apiFetch(`/api/condensed-handouts/xi-yao-1/chapters/${chapterCode}/feedback`, {
    method: 'POST',
    body: JSON.stringify(payload),
  })
}
