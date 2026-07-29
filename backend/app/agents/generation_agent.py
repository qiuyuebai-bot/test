"""
领域知识生成 Agent
读取专业知识库向量检索结果，基于学情参数生成初稿学习资源
"""
import random
from typing import Dict, Any, List, Tuple
from loguru import logger
from app.agents.base import BaseAgent
from app.agents.llm_generator import LLMGenerator
from app.utils.llm import LLMUtil


class GenerationAgent(BaseAgent):
    """
    领域知识生成 Agent
    
    职责：
    - 读取知识库向量检索结果
    - 根据学情诊断参数（难度、盲区、风格）定制内容
    - 生成三类学习资源：实操指南、分阶测试题、专属讲义
    - 输出结构化的初稿资源
    """
    
    # 资源类型配置
    RESOURCE_TYPES = [
        ("guide", "实操指南"),
        ("exercise", "分阶测试题"),
        ("lecture", "专属知识讲义"),
    ]
    
    def __init__(self):
        super().__init__(
            agent_type="generation",
            agent_name="领域知识生成Agent",
        )
    
    def execute(self, input_data: Dict[str, Any], context: Dict[str, Any] = None) -> Dict[str, Any]:
        """
        执行资源生成

        Args:
            input_data: 输入数据，包含 diagnosis_result, knowledge_results, learner_profile
            context: 上下文数据

        Returns:
            生成结果
        """
        diagnosis_result = input_data.get("diagnosis_result", {})
        knowledge_results = input_data.get("knowledge_results", [])
        learner_profile = input_data.get("learner_profile", {})
        resource_type = input_data.get("resource_type", "guide")
        target_topic = input_data.get("target_topic", "")

        llm_available = LLMUtil.is_available()
        kb_count = len(knowledge_results) if knowledge_results else 0
        logger.info(
            f"[知识生成Agent] 开始生成: resource_type={resource_type}, topic={target_topic}, "
            f"llm_available={llm_available}, knowledge_items={kb_count}"
        )

        if not knowledge_results:
            logger.warning("[知识生成Agent] 知识库检索结果为空，LLM将基于自身训练知识生成")

        # 根据资源类型调用不同生成方法
        if resource_type == "guide":
            resource_content = self._generate_guide(
                diagnosis_result,
                knowledge_results,
                learner_profile,
                target_topic,
            )
        elif resource_type == "exercise":
            resource_content = self._generate_exercises(
                diagnosis_result,
                knowledge_results,
                learner_profile,
                target_topic,
            )
        elif resource_type == "lecture":
            resource_content = self._generate_lecture(
                diagnosis_result,
                knowledge_results,
                learner_profile,
                target_topic,
            )
        else:
            raise ValueError(f"不支持的资源类型: {resource_type}")
        
        result = {
            "resource_type": resource_type,
            "resource_title": resource_content.get(
                "resource_title", self._generate_title(target_topic, resource_type, diagnosis_result)
            ),
            "difficulty_level": resource_content.get(
                "difficulty_level",
                diagnosis_result.get("recommended_difficulty", {}).get("recommended_difficulty", 3),
            ),
            "content": resource_content["content"],
            "content_json": resource_content.get("content_json", {}),
            "word_count": len(resource_content["content"]),
            "source_slice_ids": resource_content.get("source_slice_ids", []),
            "source_doc_ids": resource_content.get("source_doc_ids", []),
            "generation_method": resource_content.get("generation_method", "deterministic_fallback"),
        }
        
        logger.info(
            f"[知识生成Agent] 生成完成: resource_type={resource_type}, "
            f"generation_method={result.get('generation_method', 'unknown')}, "
            f"word_count={result['word_count']}, content_preview={result['content'][:80]}..."
        )

        return result
    
    def _generate_guide(
        self,
        diagnosis: Dict[str, Any],
        knowledge: List[Dict],
        profile: Dict[str, Any],
        topic: str,
    ) -> Dict[str, Any]:
        """
        生成实操指南

        Args:
            diagnosis: 诊断结果
            knowledge: 知识库检索结果
            profile: 学习者画像
            topic: 主题

        Returns:
            指南内容
        """
        if LLMUtil.is_available():
            try:
                logger.info(f"[知识生成Agent] 调用 DeepSeek 生成 实操指南: topic={topic}")
                return {**LLMGenerator.generate_guide(diagnosis, knowledge, profile, topic), "generation_method": "llm"}
            except Exception as exc:
                logger.warning(f"[知识生成Agent] LLM 实操指南生成失败，使用规则兜底: {exc}")

        difficulty = diagnosis.get("recommended_difficulty", {}).get("recommended_difficulty", 3)
        learning_style = profile.get("learning_style", "visual")
        blind_areas = diagnosis.get("knowledge_blind_areas", [])

        # 生成完整文本
        content_lines = []
        content_lines.append(f"# {topic} 实操指南\n")
        content_lines.append(f"**难度等级**：{'★' * difficulty}（{self._difficulty_text(difficulty)}）\n")
        content_lines.append(f"**适用人群**：{self._audience_text(difficulty)}\n")

        # 学习目标——基于知识盲区
        if blind_areas:
            blind_names = [b.get('name', '') for b in blind_areas[:3]]
            content_lines.append(f"\n## 🎯 学习目标\n")
            content_lines.append(f"通过本指南的学习，你将掌握 **{topic}** 的核心概念与实操方法。")
            if blind_names:
                content_lines.append(f"重点补强：{'、'.join(blind_names)}。\n")
        content_lines.append("\n---\n")

        if knowledge:
            # 从知识库提取关键内容构建章节（使用完整内容，不再截断）
            for i, k in enumerate(knowledge[:8]):
                k_title = k.get("title", "") or k.get("doc_title", "") or f"知识点{i+1}"
                k_content = k.get("content", "").strip()
                if not k_content:
                    continue

                content_lines.append(f"\n## 第{i+1}章 {k_title}\n")
                # 如果是长内容，保留完整（最多2000字，足够详实）
                display_content = k_content[:2000]
                content_lines.append(display_content)
                if len(k_content) > 2000:
                    content_lines.append("\n\n*（完整内容请参见知识库原文）*")
                content_lines.append("")

                # 添加实操建议
                steps = self._generate_steps(k_content, difficulty)
                if steps:
                    content_lines.append("\n**实操步骤**：\n")
                    for j, step in enumerate(steps):
                        content_lines.append(f"{j+1}. {step}")
                    content_lines.append("")

                tips = self._generate_tips(k_content)
                if tips:
                    content_lines.append(f"\n> 💡 小贴士：{tips}\n")
        else:
            # 知识库为空时给出有用提示
            content_lines.append("\n## ⚠️ 知识库暂未收录相关内容\n")
            content_lines.append(f"当前知识库中未检索到与 **{topic}** 相关的资料。\n")
            content_lines.append("\n**建议操作**：\n")
            content_lines.append("1. 前往「知识库管理」上传相关文档\n")
            content_lines.append("2. 上传后可重新生成包含丰富内容的个性化资源\n")
            content_lines.append(f"\n> 系统已记录你的学习需求，管理员可据此补充知识库内容。\n")

        # 盲区专项突破建议
        if blind_areas:
            content_lines.append("\n---\n")
            content_lines.append("\n## 🎯 知识盲区专项突破\n")
            for i, blind in enumerate(blind_areas[:5]):
                severity = blind.get("severity", "中")
                desc = blind.get("description", "")
                bname = blind.get("name", f"盲区{i+1}")
                content_lines.append(f"\n### {i+1}. {bname}（严重程度：{severity}）\n")
                if desc:
                    content_lines.append(f"{desc}\n")
                content_lines.append(f"建议花额外时间专项学习此领域内容。\n")

        # 收集来源切片ID
        source_slice_ids = [k.get("slice_id") for k in knowledge if k.get("slice_id")]
        source_doc_ids = list(set([k.get("doc_id") for k in knowledge if k.get("doc_id")]))

        return {
            "content": "\n".join(content_lines),
            "content_json": {
                "difficulty": difficulty,
                "learning_style": learning_style,
                "knowledge_items_used": len(knowledge),
            },
            "source_slice_ids": source_slice_ids,
            "source_doc_ids": source_doc_ids,
        }
    
    def _generate_exercises(
        self,
        diagnosis: Dict[str, Any],
        knowledge: List[Dict],
        profile: Dict[str, Any],
        topic: str,
    ) -> Dict[str, Any]:
        """
        生成分阶测试题

        Args:
            diagnosis: 诊断结果
            knowledge: 知识库检索结果
            profile: 学习者画像
            topic: 主题

        Returns:
            测试题内容
        """
        if LLMUtil.is_available():
            try:
                logger.info(f"[知识生成Agent] 调用 DeepSeek 生成 测试题: topic={topic}")
                return {**LLMGenerator.generate_exercises(diagnosis, knowledge, profile, topic), "generation_method": "llm"}
            except Exception as exc:
                logger.warning(f"[知识生成Agent] LLM 测试题生成失败，使用规则兜底: {exc}")

        difficulty = diagnosis.get("recommended_difficulty", {}).get("recommended_difficulty", 3)

        # 基于知识库内容生成题目
        basic_questions, advanced_questions = self._generate_questions_from_knowledge(
            knowledge, topic, difficulty
        )

        # 生成完整文本
        content_lines = []
        content_lines.append(f"# {topic} 分阶测试题\n")
        content_lines.append(f"**基础题**（{len(basic_questions)}题） | **进阶挑战**（{len(advanced_questions)}题）\n")
        content_lines.append("---\n")

        if basic_questions:
            content_lines.append("\n## 一、基础题\n")
            for i, q in enumerate(basic_questions):
                content_lines.append(f"\n### 第{i+1}题：{q['question']}\n")
                for j, opt in enumerate(q["options"]):
                    content_lines.append(f"- {chr(65+j)}. {opt}")
                content_lines.append(f"\n*答案：{q['correct_letter']} | 难度：{'★' * q['difficulty']}*\n")
                content_lines.append(f"*解析：{q['explanation']}*\n")

        if advanced_questions:
            content_lines.append("\n## 二、进阶挑战题\n")
            for i, q in enumerate(advanced_questions):
                content_lines.append(f"\n### 第{i+1}题：{q['question']}\n")
                for j, opt in enumerate(q["options"]):
                    content_lines.append(f"- {chr(65+j)}. {opt}")
                content_lines.append(f"\n*答案：{q['correct_letter']} | 难度：{'★' * q['difficulty']}*\n")
                content_lines.append(f"*解析：{q['explanation']}*\n")

        if not basic_questions and not advanced_questions:
            content_lines.append("\n## ⚠️ 知识库内容不足\n")
            content_lines.append(f"当前知识库中未检索到足够内容来生成与 **{topic}** 相关的测试题。\n")
            content_lines.append("\n**建议**：上传包含测试题或知识要点的文档到知识库，然后重新生成。\n")

        # 收集来源切片ID
        source_slice_ids = [k.get("slice_id") for k in knowledge if k.get("slice_id")]
        source_doc_ids = list(set([k.get("doc_id") for k in knowledge if k.get("doc_id")]))

        return {
            "content": "\n".join(content_lines),
            "content_json": {
                "basic_questions": basic_questions,
                "advanced_questions": advanced_questions,
                "total_questions": len(basic_questions) + len(advanced_questions),
            },
            "source_slice_ids": source_slice_ids,
            "source_doc_ids": source_doc_ids,
        }
    
    def _generate_lecture(
        self,
        diagnosis: Dict[str, Any],
        knowledge: List[Dict],
        profile: Dict[str, Any],
        topic: str,
    ) -> Dict[str, Any]:
        """
        生成专属知识讲义

        Args:
            diagnosis: 诊断结果
            knowledge: 知识库检索结果
            profile: 学习者画像
            topic: 主题

        Returns:
            讲义内容
        """
        if LLMUtil.is_available():
            try:
                logger.info(f"[知识生成Agent] 调用 DeepSeek 生成 讲义: topic={topic}")
                return {**LLMGenerator.generate_lecture(diagnosis, knowledge, profile, topic), "generation_method": "llm"}
            except Exception as exc:
                logger.warning(f"[知识生成Agent] LLM 讲义生成失败，使用规则兜底: {exc}")

        difficulty = diagnosis.get("recommended_difficulty", {}).get("recommended_difficulty", 3)
        blind_areas = diagnosis.get("knowledge_blind_areas", [])

        # 生成完整文本
        content_lines = []
        content_lines.append(f"# {topic} 专属知识讲义\n")
        content_lines.append(f"**难度等级**：{'★' * difficulty} | **适用**：{self._audience_text(difficulty)}\n")

        # 学习目标
        content_lines.append("\n## 📋 学习目标\n")
        content_lines.append(f"通过本讲义学习，你将掌握 **{topic}** 的核心概念与应用方法。")
        if blind_areas:
            blind_names = [b.get('name', '') for b in blind_areas[:3]]
            content_lines.append(f"\n重点补强领域：{'、'.join(blind_names)}。")
        content_lines.append("\n")

        content_lines.append("---\n")

        if knowledge:
            # 组织章节，使用完整知识库内容
            for i, k in enumerate(knowledge[:10]):
                section_title = k.get("title", "") or k.get("doc_title", "") or f"知识点{i+1}"
                section_content = k.get("content", "").strip()
                if not section_content:
                    continue

                content_lines.append(f"\n## {i+1}. {section_title}\n")
                # 完整内容（最多3000字，足够详实）
                display_content = section_content[:3000]
                content_lines.append(display_content)
                if len(section_content) > 3000:
                    content_lines.append("\n\n*（完整内容请参见知识库原文）*\n")

                # 核心要点提取
                key_points = self._extract_key_points_text(section_content, 3)
                if key_points:
                    content_lines.append("\n**📌 核心要点**：\n")
                    for point in key_points:
                        content_lines.append(f"- {point}")
                    content_lines.append("")
        else:
            content_lines.append("\n## ⚠️ 知识库暂无相关内容\n")
            content_lines.append(f"当前知识库中未检索到与 **{topic}** 相关的学习资料。\n")
            content_lines.append("\n**下一步操作**：\n")
            content_lines.append("1. 前往「知识库管理」上传 {topic} 相关的文档、教材或资料\n")
            content_lines.append("2. 上传并处理完成后，重新生成讲义即可获得完整内容\n")
            content_lines.append("\n> 💡 提示：支持上传 PDF、Word、Markdown、TXT 等多种格式的文档。\n")

        # 知识盲区专项
        if blind_areas:
            content_lines.append("\n---\n")
            content_lines.append("\n## 🎯 知识盲区专项突破计划\n")
            for i, blind in enumerate(blind_areas[:5]):
                bname = blind.get("name", f"盲区{i+1}")
                severity = blind.get("severity", "中")
                desc = blind.get("description", "")
                priority_icon = {"高": "🔴", "中": "🟡", "低": "🟢"}.get(severity, "🟡")
                content_lines.append(f"\n### {priority_icon} {i+1}. {bname}\n")
                content_lines.append(f"- **严重程度**：{severity}\n")
                if desc:
                    content_lines.append(f"- **描述**：{desc}\n")
                content_lines.append(f"- **建议**：将本讲义中与「{bname}」相关的章节作为优先学习内容\n")

        # 学习建议
        content_lines.append("\n---\n")
        content_lines.append("\n## 📖 学习建议\n")
        style_name = profile.get("learning_style", "visual")
        style_tips = {
            "visual": "建议使用思维导图整理本讲义的知识结构，配合图表加深理解。",
            "auditory": "建议朗读关键概念，或将讲义内容录制成音频反复收听。",
            "reading": "建议逐章精读并做笔记，每学完一章尝试用自己的话总结。",
            "kinesthetic": "建议边学边动手实践，将讲义中的示例代码或操作步骤亲自运行一遍。",
        }
        content_lines.append(f"你的学习风格：**{style_name}**\n")
        content_lines.append(f"\n{style_tips.get(style_name, '建议按照自己的节奏循序渐进地学习。')}\n")

        # 收集来源切片ID
        source_slice_ids = [k.get("slice_id") for k in knowledge if k.get("slice_id")]
        source_doc_ids = list(set([k.get("doc_id") for k in knowledge if k.get("doc_id")]))

        return {
            "content": "\n".join(content_lines),
            "content_json": {
                "blind_areas": blind_areas,
                "knowledge_items_used": len(knowledge),
                "learning_style": style_name,
            },
            "source_slice_ids": source_slice_ids,
            "source_doc_ids": source_doc_ids,
        }
    
    def _extract_key_points(self, knowledge: List[Dict], max_points: int = 5) -> List[Dict]:
        """
        从知识库结果中提取关键点
        
        Args:
            knowledge: 知识库结果
            max_points: 最大点数
            
        Returns:
            关键点列表
        """
        points = []
        for k in knowledge[:max_points]:
            content = k.get("content", "")
            title = k.get("title", "") or content[:20]
            
            points.append({
                "title": title,
                "content": content,
                "similarity": k.get("similarity", 0),
                "slice_id": k.get("slice_id"),
            })
        
        return points
    
    def _generate_steps(self, content: str, difficulty: int) -> List[str]:
        """生成实操步骤（模拟）"""
        steps = [
            "理解基本概念和原理",
            "查看示例代码/操作演示",
            "动手完成基础练习",
            "尝试独立完成综合任务",
            "回顾总结并记录心得",
        ]
        
        # 根据难度调整步骤数量和深度
        if difficulty <= 2:
            return steps[:3]
        elif difficulty <= 4:
            return steps
        else:
            steps.append("拓展研究相关高级特性")
            return steps
    
    def _generate_tips(self, content: str) -> str:
        """生成小贴士（模拟）"""
        tips = [
            "动手实践是最好的学习方式",
            "遇到问题先查文档，再问同学/老师",
            "定期复习巩固，避免遗忘",
        ]
        return tips[hash(content) % len(tips)]
    
    def _generate_questions_from_knowledge(
        self,
        knowledge: List[Dict],
        topic: str,
        base_difficulty: int,
    ) -> Tuple[List[Dict], List[Dict]]:
        """
        基于知识库内容生成有意义的题目（确定性兜底）

        相比原来的纯模板题目，此方法从知识库中提取关键信息来构造
        有实际内容的题干和选项，大幅提升可用性。

        Returns:
            (basic_questions, advanced_questions)
        """
        basic_questions = []
        advanced_questions = []

        if not knowledge:
            return basic_questions, advanced_questions

        for i, k in enumerate(knowledge[:6]):
            k_content = k.get("content", "").strip()
            k_title = k.get("title", "") or k.get("doc_title", "") or f"知识片段{i+1}"
            if not k_content:
                continue

            # 从知识库内容中提取句子作为题干基础
            sentences = [s.strip() for s in k_content.replace("。", "。\n").replace("！", "！\n").replace("？", "？\n").split("\n") if len(s.strip()) > 10]
            if len(sentences) < 2:
                continue

            # 用第一个有效句子构建题干
            fact_sentence = sentences[0][:120]
            # 判断难度分配
            diff = min(base_difficulty + (i % 3), 5)

            # 构建有意义的选项
            correct_opt = sentences[0][:80] if len(sentences) > 0 else f"正确理解{topic}"
            # 用其他句子片段构建干扰项
            distractors = []
            for s in sentences[1:]:
                short = s[:60]
                if short and short != correct_opt[:60]:
                    distractors.append(short)
                if len(distractors) >= 3:
                    break
            while len(distractors) < 3:
                distractors.append(f"关于{topic}的常见误解选项{len(distractors)+1}")

            options = [correct_opt] + distractors
            # 打乱选项顺序（简单随机）
            correct_idx = 0
            shuffled = list(enumerate(options))
            random.shuffle(shuffled)
            new_correct_idx = next(j for j, (orig_idx, _) in enumerate(shuffled) if orig_idx == 0)
            shuffled_options = [opt for _, opt in shuffled]

            q = {
                "question": f"关于「{k_title}」，以下说法正确的是？",
                "options": shuffled_options,
                "correct_answer": new_correct_idx,
                "correct_letter": chr(65 + new_correct_idx),
                "difficulty": diff,
                "explanation": f"根据知识库资料：{correct_opt[:100]}",
                "knowledge_points": [k_title],
            }

            if diff <= 3:
                basic_questions.append(q)
            else:
                advanced_questions.append(q)

        return basic_questions, advanced_questions
    
    def _extract_key_points_text(self, content: str, count: int) -> List[str]:
        """从文本中提取要点（模拟）"""
        sentences = [s.strip() for s in content.replace("。", "。\n").split("\n") if s.strip()]
        return sentences[:count]
    
    def _generate_title(self, topic: str, resource_type: str, diagnosis: Dict) -> str:
        """生成资源标题"""
        type_names = {
            "guide": "实操指南",
            "exercise": "分阶测试题",
            "lecture": "专属知识讲义",
        }
        type_name = type_names.get(resource_type, "学习资源")
        
        difficulty = diagnosis.get("recommended_difficulty", {}).get("recommended_difficulty", 3)
        level_text = ["入门级", "基础级", "进阶级", "精通级", "专家级"][difficulty - 1]
        
        return f"{topic} - {level_text}{type_name}"
    
    def _difficulty_text(self, difficulty: int) -> str:
        """难度文字描述"""
        texts = ["入门", "基础", "进阶", "精通", "专家"]
        return texts[difficulty - 1] if 1 <= difficulty <= 5 else "进阶"
    
    def _audience_text(self, difficulty: int) -> str:
        """适用人群描述"""
        texts = [
            "零基础初学者",
            "有一定基础的学习者",
            "具备中等基础的开发者",
            "有丰富经验的工程师",
            "资深技术专家",
        ]
        return texts[difficulty - 1] if 1 <= difficulty <= 5 else "中级学习者"
    
    def validate(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """
        校验生成结果
        
        Args:
            data: 生成结果数据
            
        Returns:
            校验结果
        """
        result = super().validate(data)
        
        issues = []
        score = 100
        
        # 检查必要字段
        required_fields = ["resource_type", "content", "source_slice_ids"]
        for field in required_fields:
            if field not in data:
                issues.append(f"缺少必要字段: {field}")
                score -= 20
        
        # 检查内容是否为空
        if not data.get("content"):
            issues.append("生成内容为空")
            score -= 30
        
        # 检查字数
        word_count = len(data.get("content", ""))
        if word_count < 100:
            issues.append("内容字数过少")
            score -= 15
        
        result["issues"].extend(issues)
        result["score"] = max(0, score)
        result["passed"] = len(issues) == 0
        
        return result