"""
CODE_KB — 知识库整合节点
位置: Iterator 内 → Knowledge_Retrieval 之后, LLM 之前
作用: 解析 KB 返回的 JSON 数组, 提取 content, 与 CODE_A 的 user_prompt 合并

Dify 配置:
  输入变量:
    user_prompt   (string) — {{CODE_A.user_prompt}}
    kb_result     (array)  — {{Knowledge_Retrieval.result}}
  输出变量:
    final_user_prompt (string) — 注入到 LLM 节点的 User Prompt
"""

import json


def main(user_prompt: str, kb_result):
    """
    user_prompt: CODE_A 输出的卡片专属 prompt
    kb_result:   Knowledge Retrieval 节点返回的结果(可能是 list/dict/JSON string)
    """
    # ── 1. 解析 kb_result ──
    chunks = []

    if isinstance(kb_result, str):
        try:
            kb_result = json.loads(kb_result)
        except (json.JSONDecodeError, TypeError):
            kb_result = []

    if isinstance(kb_result, dict):
        # Dify 有时把数组包在 {"result": [...]} 里
        kb_result = kb_result.get("result", kb_result)

    if isinstance(kb_result, list):
        chunks = kb_result
    else:
        chunks = []

    # ── 2. 拼接知识库内容 ──
    if chunks:
        kb_lines = []
        kb_lines.append("---")
        kb_lines.append("📚 **以下内容来自权威备考教材，请严格基于以下内容生成卡片：**")
        kb_lines.append("")

        for i, chunk in enumerate(chunks):
            if not isinstance(chunk, dict):
                continue

            title = chunk.get("title", f"知识点{i+1}")
            content = chunk.get("content", "")

            if not content:
                continue

            # 清理 title 中的文件后缀
            clean_title = title.replace(".txt", "").replace("__", " > ")

            kb_lines.append("---")
            kb_lines.append(f"📚 来源: {clean_title}")
            kb_lines.append(content)
            kb_lines.append("")

        kb_lines.append("---")
        kb_lines.append("")
        kb_lines.append("⚠️ **引用规则（必须遵守）：**")
        kb_lines.append("1. key_points 中的具体数值、定义、诊断标准 —— **原文照搬，不得改写、不得调整语序、不得替换同义词**。教材怎么说就怎么引用。")
        kb_lines.append("2. 长段落无法照搬时，提取关键数值和定义原样保留，解释性文字由你压缩拼装。")
        kb_lines.append("3. 从上述内容中选 2-3 个最相关的知识点作为 module，每个知识点一个 module。")
        kb_lines.append("4. module_title 从来源文件名中的知识点名简化提取（10-20 字）。")
        kb_lines.append("5. 教材中没有的考点不要编造 —— 宁可少写。")
        kb_lines.append("")
        kb_lines.append("📐 **优先级（冲突时遵守）：**")
        kb_lines.append("6. key_points：**原文准确性 > 口语化**。宁可句式学术，也不能改变数值/定义/诊断标准。")
        kb_lines.append("7. memory_tips / module_title / 模块衔接语：**口语化 > 学术精确**。考点内核严守原文，包装外壳自由发挥。")
        kb_lines.append("")
        kb_lines.append("✍️ **写作风格：**")
        kb_lines.append("8. 像真人发微信不是写总结 —— 句子长短交错，用「你」不用「考生」。")
        kb_lines.append("9. 口语词自然用：「别指望」「刷到吐」「看到题干就秒」「卡住就跳过」。")
        kb_lines.append("10. 禁止模板化句式：「值得注意的是」「综上所述」「建议」「应当」。")

        kb_context = "\n".join(kb_lines)
    else:
        kb_context = (
            "---\n"
            "⚠️ 本次未检索到教材资料，请基于你的训练知识生成内容。\n"
            "不确定的考点数据用模糊表述，不要编造具体数字。\n"
            "source 字段标记为 \"llm_search\"。"
        )

    # ── 3. 合并输出 ──
    final_user_prompt = user_prompt + "\n\n" + kb_context

    return {
        "final_user_prompt": final_user_prompt,
        "kb_chunk_count": str(len(chunks)),
    }
