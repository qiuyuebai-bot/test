"""
内容修正器

根据审核意见修正生成内容，支持两种策略：
1. LLM 智能修正（优先，当 LLM 可用时）
2. 规则-based 修正（兜底，LLM 不可用或修正失败时）
"""
import re
from typing import Any, Dict, List, Optional

from loguru import logger

from app.utils.llm import LLMUtil


class ContentCorrector:
    """根据审核意见修正内容"""

    def apply_corrections(
        self,
        content: str,
        corrections: List[Dict[str, Any]],
        reference_knowledge: List[Dict] = None,
    ) -> str:
        """
        应用修正到内容，生成修正后的版本

        策略：优先 LLM 智能修正，失败则回退到规则修正
        """
        if not corrections:
            return content

        reference_knowledge = reference_knowledge or []

        high_corrections = [c for c in corrections if c.get("severity") == "high"]
        medium_corrections = [c for c in corrections if c.get("severity") == "medium"]

        if not high_corrections and not medium_corrections:
            return content

        if LLMUtil.is_available():
            revised = self._llm_correct(content, corrections, reference_knowledge)
            if revised and len(revised) > 50:
                logger.info(f"[内容修正] LLM修正完成: 原长度={len(content)}, 修正后长度={len(revised)}")
                return revised

        return self._rule_based_correct(content, corrections)

    def _llm_correct(
        self,
        content: str,
        corrections: List[Dict[str, Any]],
        reference_knowledge: List[Dict],
    ) -> Optional[str]:
        """使用 LLM 智能修正内容"""
        try:
            correction_text = "\n".join([
                f"- [{c.get('severity', 'medium').upper()}] {c.get('issue_type', 'unknown')}: "
                f"{c.get('description', '')} | 建议: {c.get('suggested_fix', '')}"
                for c in corrections
            ])

            ref_text = "\n".join([
                f"[参考] {k.get('title', '')}: {k.get('content', '')[:300]}"
                for k in reference_knowledge[:3]
            ])

            system_prompt = (
                "你是一位严谨的专业内容审校专家。你的任务是根据审核意见修正学习资源内容中的问题。"
                "请遵循以下规则：\n"
                "1. 删除或修正疑似幻觉/不实的表述\n"
                "2. 将绝对化表述改为更严谨的表述\n"
                "3. 核实技术术语和数据的准确性\n"
                "4. 保持原文的整体结构和风格\n"
                "5. 只输出修正后的完整内容，不要添加任何解释、标记或前言\n"
                "6. 不要使用markdown代码块包裹输出"
            )

            user_prompt = (
                f"## 待修正内容\n{content}\n\n"
                f"## 审核修正意见\n{correction_text}\n\n"
                f"## 参考知识\n{ref_text}\n\n"
                f"请根据以上审核意见修正内容，直接输出修正后的完整文本："
            )

            revised, _ = LLMUtil.sync_call(
                prompt=user_prompt,
                system_prompt=system_prompt,
                temperature=0.3,
            )

            revised = revised.strip()
            if revised.startswith("```"):
                revised = re.sub(r'^```\w*\n?', '', revised)
                revised = re.sub(r'\n?```$', '', revised)

            return revised.strip()

        except Exception as e:
            logger.warning(f"[内容修正] LLM修正失败，回退到规则修正: {e}")
            return None

    def _rule_based_correct(
        self,
        content: str,
        corrections: List[Dict[str, Any]],
    ) -> str:
        """基于规则的内容修正（LLM不可用时的兜底方案）"""
        modified = content

        absolute_phrases = {
            "一定": "通常",
            "绝对": "一般情况下",
            "百分百": "大概率",
            "百分之百": "在大多数情况下",
            "必须": "建议",
            "肯定": "很可能",
            "必然": "往往",
        }

        for old, new in absolute_phrases.items():
            modified = modified.replace(old, new)

        for c in corrections:
            if c.get("issue_type") == "hallucination_keyword":
                details = c.get("original_content", "")
                if isinstance(details, list) and details:
                    for keyword in details[:3]:
                        if isinstance(keyword, str) and keyword in modified:
                            modified = modified.replace(
                                keyword,
                                f"{keyword}（注：此表述需进一步核实）",
                                1
                            )

            elif c.get("issue_type") == "standard_issue":
                suggested = c.get("suggested_fix", "")
                if suggested and suggested not in modified:
                    modified += f"\n\n> [审核修正] {suggested}"

        version_pattern = r'v?\d+\.\d+\.\d+'
        matches = re.findall(version_pattern, modified)
        if matches:
            for ver in set(matches):
                if f"{ver}（版本号需核实）" not in modified:
                    modified = modified.replace(ver, f"{ver}（版本号需核实）", 1)

        correction_count = len([c for c in corrections if c.get('severity') in ('high', 'medium')])
        marker = f"\n\n---\n*[系统提示：内容经过{correction_count}项审核修正]*"
        if marker not in modified:
            modified += marker

        logger.debug(f"[内容修正] 规则修正完成: 修正项={len(corrections)}")
        return modified
