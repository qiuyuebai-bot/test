"""
领域知识生成 Agent
读取专业知识库向量检索结果，基于学情参数生成初稿学习资源
"""
import hashlib
import json
from uuid import uuid4
from typing import Dict, Any, List
from loguru import logger
from app.agents.base import BaseAgent
from app.agents.llm_generator import LLMGenerator
from app.services.ai_content_service import AIContentService
from app.utils.llm_response import bounded_list, bounded_text, parse_json_object
from app.utils.llm import LLMUtil, LLMUnavailableError
from app.utils.resource_content import (
    build_source_references,
    calculate_source_coverage,
    build_resource_title,
    normalize_resource_topic,
    normalize_source_slice_ids,
    validate_resource_title,
)
from app.config import settings


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

    def respond_to_review(
        self,
        generated_content: str,
        reference_knowledge: List[Dict[str, Any]],
        audit_result: Dict[str, Any],
        round_num: int = 1,
    ) -> Dict[str, Any]:
        """Return the generation agent's independent position in a debate.

        This is deliberately a separate model call from the judge.  When a
        model is unavailable we return an explicit unavailable response rather
        than inventing a defense that was never produced by the agent.
        """
        unavailable = {
            "available": False,
            "status": "unavailable",
            "stance": "unavailable",
            "accepts": None,
            "response": "生成Agent当前不可用，无法提供独立辩护意见。",
            "revisions_made": 0,
            "disputed_issues": [],
            "evidence_citations": [],
            "method": "unavailable",
            "requires_human_review": True,
            "round": round_num,
        }
        if not LLMUtil.is_available():
            return unavailable

        try:
            response, _ = AIContentService.call_with_prompt_template(
                "generation_review",
                {
                    "round_num": round_num,
                    "generated_content": (generated_content or "")[:12000],
                    "reference_knowledge": self._reference_text(reference_knowledge),
                    "audit_result": json.dumps(
                        audit_result.get("issues", [])[:12], ensure_ascii=False
                    ),
                },
                temperature=0.2,
                use_cache=False,
                allow_mock=False,
            )
            payload = parse_json_object(response)
            if payload.get("_meta", {}).get("model") == "mock":
                raise ValueError("LLM returned fallback mock response")
            stance = payload.get("stance")
            if stance not in {"accept", "defend", "mixed"}:
                raise ValueError("invalid generation agent stance")
            issues = []
            for item in bounded_list(payload.get("disputed_issues", []), "disputed_issues", maximum=12):
                if isinstance(item, str):
                    issues.append(bounded_text(item, "disputed_issue", maximum=500))
            citations = []
            for item in bounded_list(payload.get("evidence_citations", []), "evidence_citations", maximum=12):
                if isinstance(item, str):
                    citations.append(bounded_text(item, "evidence_citation", maximum=300))
            return {
                "available": True,
                "status": "available",
                "stance": stance,
                "accepts": bool(payload.get("accepts", stance == "accept")),
                "response": bounded_text(payload.get("response"), "generation_response", maximum=3000),
                "revisions_made": max(0, min(12, int(payload.get("revisions_made", len(issues))))),
                "disputed_issues": issues,
                "evidence_citations": citations,
                "method": "llm",
                "requires_human_review": False,
                "round": round_num,
            }
        except Exception as exc:
            logger.warning(f"[知识生成Agent] 独立审核回应失败，转人工复核: {exc}")
            return {
                **unavailable,
                "status": "error",
                "error_code": "generation_review_failed",
            }

    @staticmethod
    def _reference_text(knowledge: List[Dict[str, Any]]) -> str:
        return "\n\n".join(
            f"[{item.get('slice_id', 'unknown')}] {item.get('title', '知识片段')}: {str(item.get('content', ''))[:2200]}"
            for item in (knowledge or [])[:6]
            if item.get("content")
        ) or "无可用参考资料"
    
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
        target_topic = normalize_resource_topic(input_data.get("target_topic"))
        training_context = input_data.get("training_context") or {}
        base_seed = (
            input_data.get("variation_seed")
            or (context or {}).get("variation_seed")
            or input_data.get("task_id")
            or (context or {}).get("task_id")
            or self.current_task_id
            or "manual"
        )
        variation_seed = f"{base_seed}-{uuid4().hex}"
        
        if not knowledge_results:
            logger.warning("[知识生成Agent] 知识库检索结果为空")
        
        # 根据资源类型调用不同生成方法
        if resource_type == "guide":
            resource_content = self._generate_guide(
                diagnosis_result,
                knowledge_results,
                learner_profile,
                target_topic,
                variation_seed,
                training_context,
            )
        elif resource_type == "exercise":
            resource_content = self._generate_exercises(
                diagnosis_result,
                knowledge_results,
                learner_profile,
                target_topic,
                variation_seed,
                training_context,
            )
        elif resource_type == "lecture":
            resource_content = self._generate_lecture(
                diagnosis_result,
                knowledge_results,
                learner_profile,
                target_topic,
                variation_seed,
                training_context,
            )
        else:
            raise ValueError(f"不支持的资源类型: {resource_type}")
        
        source_references = build_source_references(knowledge_results)
        source_slice_ids = [item["slice_id"] for item in source_references]
        if not source_slice_ids:
            source_slice_ids = normalize_source_slice_ids(resource_content.get("source_slice_ids"))
        source_doc_ids = list({
            item.get("doc_id")
            for item in source_references
            if item.get("doc_id") is not None
        })
        if not source_doc_ids:
            source_doc_ids = normalize_source_slice_ids(resource_content.get("source_doc_ids"))
        source_coverage = resource_content.get("source_coverage") or calculate_source_coverage(
            resource_content.get("content"), source_references
        )
        if not source_coverage.get("passed", True):
            logger.warning(
                "[知识生成Agent] 来源覆盖校验未通过: resource_type={}, coverage={}%, missing={}",
                resource_type,
                source_coverage.get("coverage_rate"),
                source_coverage.get("missing_sources"),
            )

        generated_title = resource_content.get(
            "resource_title", self._generate_title(target_topic, resource_type, diagnosis_result)
        )
        result = {
            "resource_type": resource_type,
            "knowledge_topic": target_topic,
            "resource_title": validate_resource_title(generated_title),
            "difficulty_level": resource_content.get(
                "difficulty_level",
                diagnosis_result.get("recommended_difficulty", {}).get("recommended_difficulty", 3),
            ),
            "content": resource_content["content"],
            "content_json": resource_content.get("content_json", {}),
            "word_count": len(resource_content["content"]),
            "source_slice_ids": source_slice_ids,
            "source_doc_ids": source_doc_ids,
            "source_references": source_references,
            "source_coverage": source_coverage,
            "generation_method": resource_content.get("generation_method", "deterministic_fallback"),
            "training_context": training_context,
        }
        
        logger.debug(f"[知识生成Agent] 生成完成: 类型={resource_type}, 字数={result['word_count']}")
        
        return result
    
    def _generate_guide(
        self,
        diagnosis: Dict[str, Any],
        knowledge: List[Dict],
        profile: Dict[str, Any],
        topic: str,
        variation_seed: str = "",
        training_context: Dict[str, Any] | None = None,
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
                return {
                    **LLMGenerator.generate_guide(
                        diagnosis, knowledge, profile, topic, variation_seed=variation_seed,
                        training_context=training_context,
                    ),
                    "generation_method": "deepseek",
                }
            except Exception as exc:
                if settings.REQUIRE_RESOURCE_LLM or LLMUtil.requires_configured_provider():
                    if isinstance(exc, LLMUnavailableError):
                        raise
                    raise LLMUnavailableError("invalid_generation_response") from exc
                logger.warning(f"[知识生成Agent] LLM 实操指南生成失败，使用规则兜底: {exc}")

        difficulty = diagnosis.get("recommended_difficulty", {}).get("recommended_difficulty", 3)
        learning_style = profile.get("learning_style", "visual")

        # 从知识库提取关键内容
        key_points = self._extract_key_points(knowledge, max_points=5)
        
        # 生成章节结构
        chapters = []
        for i, point in enumerate(key_points):
            chapter = {
                "title": f"第{i+1}章 {point['title']}",
                "content": point["content"],
                "focus": self._chapter_focus(topic, point["title"], point["content"], i, variation_seed),
                "scenario": self._chapter_scenario(topic, point["title"], point["content"], i, variation_seed),
                "steps": self._generate_steps(topic, point["title"], point["content"], difficulty, i, variation_seed),
                "checks": self._chapter_checks(topic, point["title"], point["content"], i, variation_seed),
                "tips": self._generate_tips(topic, point["title"], point["content"], i, variation_seed),
            }
            chapters.append(chapter)
        
        # 生成完整文本
        content_lines = []
        content_lines.append(f"# {topic} 实操指南\n")
        content_lines.append(f"**难度等级**：{'★' * difficulty}（{self._difficulty_text(difficulty)}）\n")
        content_lines.append(f"**适用人群**：{self._audience_text(difficulty)}\n")
        content_lines.append("---\n")
        
        for i, ch in enumerate(chapters):
            content_lines.append(f"\n## {ch['title']}\n")
            content_lines.append(f"**本节看点**：{ch['focus']}")
            content_lines.append(f"**适用场景**：{ch['scenario']}")
            content_lines.append(ch["content"][:220] + "...\n")
            
            if ch["steps"]:
                content_lines.append("\n**实操步骤**：\n")
                for j, step in enumerate(ch["steps"]):
                    content_lines.append(f"{j+1}. {step}")
                content_lines.append("")
            
            if ch["checks"]:
                content_lines.append("**检查点**：")
                for item in ch["checks"]:
                    content_lines.append(f"- {item}")
                content_lines.append("")
            
            if ch["tips"]:
                content_lines.append("\n> 💡 小贴士：" + ch["tips"] + "\n")

        if len("\n".join(content_lines).strip()) < 200:
            content_lines = self._fallback_guide_lines(topic, difficulty, variation_seed)
        
        # 收集来源切片ID
        source_slice_ids = [k.get("slice_id") for k in knowledge if k.get("slice_id")]
        source_doc_ids = list(set([k.get("doc_id") for k in knowledge if k.get("doc_id")]))
        
        return {
            "content": "\n".join(content_lines),
            "content_json": {
                "chapters": chapters,
                "difficulty": difficulty,
                "learning_style": learning_style,
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
        variation_seed: str = "",
        training_context: Dict[str, Any] | None = None,
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
                return {
                    **LLMGenerator.generate_exercises(
                        diagnosis, knowledge, profile, topic, variation_seed=variation_seed,
                        training_context=training_context,
                    ),
                    "generation_method": "deepseek",
                }
            except Exception as exc:
                if settings.REQUIRE_RESOURCE_LLM or LLMUtil.requires_configured_provider():
                    if isinstance(exc, LLMUnavailableError):
                        raise
                    raise LLMUnavailableError("invalid_generation_response") from exc
                logger.warning(f"[知识生成Agent] LLM 测试题生成失败，使用规则兜底: {exc}")

        difficulty = diagnosis.get("recommended_difficulty", {}).get("recommended_difficulty", 3)

        # 生成 10 道从易到难的题目，兜底内容也必须是可用的真实题。
        basic_questions = self._generate_question_set(knowledge, topic, "basic", 6)
        advanced_questions = self._generate_question_set(knowledge, topic, "advanced", 4)
        
        # 生成完整文本
        content_lines = []
        content_lines.append(f"# {topic} 分阶测试题\n")
        content_lines.append(f"**基础题**（{len(basic_questions)}题）\n")
        content_lines.append(f"**进阶挑战**（{len(advanced_questions)}题）\n")
        content_lines.append("---\n")
        
        content_lines.append("\n## 一、基础题\n")
        for i, q in enumerate(basic_questions):
            content_lines.append(f"\n### 第{i+1}题：{q['question']}\n")
            for j, opt in enumerate(q["options"]):
                content_lines.append(f"- {chr(65+j)}. {opt}")
            content_lines.append(f"\n*答案：{q['correct_letter']} | 难度：{'★' * q['difficulty']}*")
            content_lines.append(f"*解析：{q['explanation']}*")
        
        content_lines.append("\n\n## 二、进阶挑战题\n")
        for i, q in enumerate(advanced_questions):
            content_lines.append(f"\n### 第{i+1}题：{q['question']}\n")
            for j, opt in enumerate(q["options"]):
                content_lines.append(f"- {chr(65+j)}. {opt}")
            content_lines.append(f"\n*答案：{q['correct_letter']} | 难度：{'★' * q['difficulty']}*")
            content_lines.append(f"*解析：{q['explanation']}*")
        
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
        variation_seed: str = "",
        training_context: Dict[str, Any] | None = None,
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
                return {
                    **LLMGenerator.generate_lecture(
                        diagnosis, knowledge, profile, topic, variation_seed=variation_seed,
                        training_context=training_context,
                    ),
                    "generation_method": "deepseek",
                }
            except Exception as exc:
                if settings.REQUIRE_RESOURCE_LLM or LLMUtil.requires_configured_provider():
                    if isinstance(exc, LLMUnavailableError):
                        raise
                    raise LLMUnavailableError("invalid_generation_response") from exc
                logger.warning(f"[知识生成Agent] LLM 讲义生成失败，使用规则兜底: {exc}")

        difficulty = diagnosis.get("recommended_difficulty", {}).get("recommended_difficulty", 3)
        blind_areas = diagnosis.get("knowledge_blind_areas", [])

        # 组织章节
        sections = []
        for i, k in enumerate(knowledge[:6]):
            title = k.get("title", f"知识点{i+1}")
            content = k.get("content", "")
            section = {
                "title": f"{i+1}. {title}",
                "content": content,
                "key_points": self._extract_key_points_text(content, 3),
                "frame": self._lecture_frame(topic, title, content, i, variation_seed),
                "application": self._lecture_application(topic, title, content, i, variation_seed),
                "pitfall": self._lecture_pitfall(topic, title, content, i, variation_seed),
                "check": self._lecture_check(topic, title, content, i, variation_seed),
            }
            sections.append(section)
        
        # 生成完整文本
        content_lines = []
        content_lines.append(f"# {topic} 专属知识讲义\n")
        content_lines.append(f"**难度等级**：{'★' * difficulty} | **适用**：{self._audience_text(difficulty)}\n")
        
        # 学习目标
        content_lines.append("\n## 学习目标\n")
        content_lines.append(f"通过本讲义学习，你将掌握{topic}的核心概念与应用方法，")
        content_lines.append(f"弥补在{', '.join([b['name'] for b in blind_areas[:3]]) if blind_areas else '相关领域'}方面的知识盲区。\n")
        
        content_lines.append("---\n")
        
        # 各章节
        for sec in sections:
            content_lines.append(f"\n## {sec['title']}\n")
            content_lines.append(f"**这一节解决什么**：{sec['frame']}")
            content_lines.append(sec["content"][:240] + "...\n")
            if sec["key_points"]:
                content_lines.append("\n**核心要点**：")
                for point in sec["key_points"]:
                    content_lines.append(f"- {point}")
                content_lines.append("")
            content_lines.append(f"**如何应用**：{sec['application']}")
            content_lines.append(f"**常见误区**：{sec['pitfall']}")
            content_lines.append(f"**自测标准**：{sec['check']}")
        
        # 知识盲区专项
        if blind_areas:
            content_lines.append("\n---\n")
            content_lines.append("\n## 🎯 知识盲区专项突破\n")
            for i, blind in enumerate(blind_areas[:3]):
                content_lines.append(f"\n### {i+1}. {blind['name']}\n")
                content_lines.append(f"当前水平：{blind.get('severity', '中')}，建议优先学习提升。\n")

        if len("\n".join(content_lines).strip()) < 200:
            content_lines = self._fallback_lecture_lines(topic, difficulty, blind_areas, variation_seed)
        
        # 收集来源切片ID
        source_slice_ids = [k.get("slice_id") for k in knowledge if k.get("slice_id")]
        source_doc_ids = list(set([k.get("doc_id") for k in knowledge if k.get("doc_id")]))
        
        return {
            "content": "\n".join(content_lines),
            "content_json": {
                "sections": sections,
                "blind_areas": blind_areas,
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
    
    def _generate_steps(self, topic: str, title: str, content: str, difficulty: int, index: int, variation_seed: str = "") -> List[str]:
        """生成分章节且不重复的实操步骤。"""
        patterns = [
            [
                f"先用一句话说明{title}在{topic}中的作用",
                "把输入、处理过程和输出结果分别写出来",
                "找一个最小例子手动走一遍",
            ],
            [
                f"把{title}拆成三个连续动作",
                "逐步检查每一步的依据",
                "记录最容易出错的前提",
            ],
            [
                f"把{title}放进真实场景里理解",
                "比较正确做法和错误做法",
                "验证边界条件下是否仍成立",
            ],
            [
                f"围绕{title}整理一张检查清单",
                "对照资料补齐理解缺口",
                "用变式题确认是否真的会用",
            ],
        ]
        bucket = self._stable_bucket(topic, title, content, str(index), variation_seed, size=len(patterns))
        steps = list(patterns[bucket])
        if difficulty >= 4:
            steps.append(f"尝试把{title}迁移到更复杂的变式场景")
        if difficulty >= 5:
            steps.append("写下一个反例并解释为什么会失败")
        return steps
    
    def _generate_tips(self, topic: str, title: str, content: str, index: int, variation_seed: str = "") -> str:
        """生成分章节且不重复的小贴士。"""
        tips = [
            f"先抓{title}的目标，再看细节。",
            f"把这一节和上一节的差异写出来。",
            "不要直接背结论，先写前提。",
            f"如果解释不出来，就回到{title}的最小例子。",
            f"把{topic}和一个相似但不同的概念做对照。",
        ]
        return tips[self._stable_bucket(topic, title, content, str(index), variation_seed, size=len(tips))]

    def _chapter_focus(self, topic: str, title: str, content: str, index: int, variation_seed: str = "") -> str:
        focuses = [
            f"先建立{title}在{topic}中的位置感，避免只看标题。",
            f"把{title}拆成目标、条件和结果三部分。",
            f"先看{title}解决什么问题，再看怎么做。",
            f"用一个最小例子验证{title}能不能跑通。",
        ]
        return focuses[self._stable_bucket(topic, title, content, str(index), variation_seed, size=len(focuses))]

    def _chapter_scenario(self, topic: str, title: str, content: str, index: int, variation_seed: str = "") -> str:
        scenarios = [
            f"适合在第一次接触{topic}时先读这一章。",
            f"适合已经知道概念，但还不会动手的人。",
            f"适合做练习前快速对照检查。",
            f"适合复盘错误和补齐细节时使用。",
        ]
        return scenarios[self._stable_bucket(title, content, topic, str(index), variation_seed, size=len(scenarios))]

    def _chapter_checks(self, topic: str, title: str, content: str, index: int, variation_seed: str = "") -> List[str]:
        checks = [
            f"我能解释{title}为什么重要。",
            f"我能说出{title}的输入和输出。",
            f"我能举出{title}的一个正确用法。",
            f"我能指出{title}最容易踩的坑。",
        ]
        bucket = self._stable_bucket(topic, title, content, str(index), variation_seed, size=len(checks))
        return [checks[bucket], checks[(bucket + 1) % len(checks)], checks[(bucket + 2) % len(checks)]]

    def _lecture_frame(self, topic: str, title: str, content: str, index: int, variation_seed: str = "") -> str:
        frames = [
            f"先建立{title}的整体地图，知道它解决什么问题。",
            f"先抓住{title}的关键条件，再看处理步骤。",
            f"把{title}放进真实任务里理解，确认适用边界。",
            f"用对照和反例检验{title}，避免只记结论。",
        ]
        return frames[self._stable_bucket(topic, title, content, str(index), variation_seed, size=len(frames))]

    def _lecture_application(self, topic: str, title: str, content: str, index: int, variation_seed: str = "") -> str:
        applications = [
            f"可以把{title}直接转成一个小练习：先写输入，再写处理，再写输出。",
            f"把{title}和一个真实案例对照，确认它什么时候适用、什么时候不适用。",
            f"学习时先画流程，再补文字说明，避免只背名词。",
            f"完成后自己改一个条件，看结论是否还成立。",
        ]
        return applications[self._stable_bucket(title, content, topic, str(index), variation_seed, size=len(applications))]

    def _lecture_pitfall(self, topic: str, title: str, content: str, index: int, variation_seed: str = "") -> str:
        pitfalls = [
            f"最常见的问题是把{title}和相近概念混在一起。",
            f"另一个问题是只记结果，不记前提。",
            f"容易漏掉的是边界条件和例外情况。",
            f"很多人会直接跳过例子，导致会看不会做。",
        ]
        return pitfalls[self._stable_bucket(topic, title, content, str(index), variation_seed, size=len(pitfalls))]

    def _lecture_check(self, topic: str, title: str, content: str, index: int, variation_seed: str = "") -> str:
        checks = [
            f"我能把{title}讲给别人听，并举一个例子。",
            f"我能说出{title}的边界条件。",
            f"我能写出{title}对应的一个变式题。",
            f"我能说明为什么这个结论成立而不是只背答案。",
        ]
        return checks[self._stable_bucket(topic, title, content, str(index), variation_seed, size=len(checks))]

    @staticmethod
    def _stable_bucket(*parts: str, size: int) -> int:
        key = "||".join(part or "" for part in parts)
        digest = hashlib.sha1(key.encode("utf-8")).hexdigest()
        return int(digest[:8], 16) % size

    def _fallback_guide_lines(self, topic: str, difficulty: int, variation_seed: str = "") -> List[str]:
        """Build a complete guide when retrieved slices are too short."""
        label = topic or "目标知识点"
        intro_variants = [
            f"{label}的学习要先分清输入、过程和结果，再决定怎么练。",
            f"{label}适合先做最小例子，再扩展到完整流程。",
            f"学习{label}时，不要只记结论，要把前提和边界一起写下来。",
            f"{label}可以先拆成概念、步骤和验证三层来看。",
        ]
        return [
            f"# {label} 实操指南",
            "",
            f"**难度等级**：{'★' * difficulty}（{self._difficulty_text(difficulty)}）",
            f"**适用人群**：{self._audience_text(difficulty)}",
            "",
            "## 学习目标",
            f"1. 说清楚{label}的核心概念、输入输出和适用边界。",
            f"2. 能把{label}拆成可执行步骤，并在练习中检查结果。",
            f"3. 能识别常见错误，知道如何复盘和修正。",
            "",
            "## 核心原理",
            intro_variants[self._stable_bucket(label, difficulty.__str__(), variation_seed, size=len(intro_variants))],
            "",
            "## 实操步骤",
            "1. 用一句话写出本知识点要解决的问题。",
            "2. 列出完成任务需要的前置概念和关键变量。",
            "3. 找一个最小例子，手动推演一次完整流程。",
            "4. 对照资料或知识库来源检查每一步是否有依据。",
            "5. 独立完成一道变式练习，并记录错误原因。",
            "",
            "## 示例演练",
            f"以{label}为主题，先选择一个简单场景：给出输入条件，写出处理过程，再说明输出结果为什么成立。若中间某一步无法解释，就回到对应概念补学，而不是继续堆答案。",
            "",
            "## 常见错误",
            "- 只记住标题，无法解释适用场景。",
            "- 没有做来源核验，把生成内容直接当结论。",
            "- 练习只看答案，不记录错误原因。",
            "",
            "## 检查清单",
            "- 我能用自己的话解释概念。",
            "- 我能完成一个最小实操例子。",
            "- 我能说明至少两个常见错误和修正方法。",
        ]

    def _fallback_lecture_lines(self, topic: str, difficulty: int, blind_areas: List[Dict], variation_seed: str = "") -> List[str]:
        """Build a complete lecture when retrieved slices are too short."""
        label = topic or "目标知识点"
        blind_names = [item.get("name", "") for item in blind_areas[:3] if item.get("name")]
        blind_text = "、".join(blind_names) if blind_names else "概念理解、步骤迁移、结果验证"
        opening_variants = [
            f"{label}这份讲义先帮你搭框架，再补细节。",
            f"这份讲义会把{label}拆成概念、应用和检查三部分。",
            f"学习{label}时，先理解结构，再看步骤。",
            f"这份讲义围绕{label}的边界、误区和迁移来展开。",
        ]
        return [
            f"# {label} 专属知识讲义",
            "",
            f"**难度等级**：{'★' * difficulty} | **适用**：{self._audience_text(difficulty)}",
            "",
            "## 学习目标",
            opening_variants[self._stable_bucket(label, difficulty.__str__(), variation_seed, size=len(opening_variants))],
            "",
            "## 一、概念框架",
            f"{label}需要先建立整体框架：它面对什么问题，使用哪些关键概念，输出怎样的结果，以及结果如何验证。掌握这些边界后，再进入细节学习会更稳定。",
            "",
            "## 二、关键理解",
            "- 先区分定义、条件、步骤和结论。",
            "- 对每个步骤追问依据，避免只背模板。",
            "- 用例题检查理解，不用主观感觉判断掌握程度。",
            "",
            "## 三、学习路径",
            "1. 阅读核心定义，标出不理解的术语。",
            "2. 根据简单例子复述完整流程。",
            "3. 完成基础练习，记录错误类型。",
            "4. 做一道综合题，验证是否能迁移应用。",
            "",
            "## 四、复盘方法",
            f"复盘{label}时，把错误分成三类：概念不清、步骤遗漏、验证不足。每类错误都要写出一个修正动作，例如补看对应资料、重做推演或增加反例检查。",
        ]
    
    def _generate_question_set(
        self,
        knowledge: List[Dict],
        topic: str,
        level: str,
        count: int,
    ) -> List[Dict]:
        """Generate concrete deterministic questions when LLM output is unavailable."""
        normalized = (topic or "").strip()
        specs = self._topic_question_specs(normalized)
        filtered = [item for item in specs if item[0] <= 3] if level == "basic" else [item for item in specs if item[0] > 3]
        questions = []
        for difficulty, question, options, correct_answer, explanation in filtered[:count]:
            questions.append({
                "question": question,
                "options": options,
                "correct_answer": correct_answer,
                "correct_letter": chr(65 + correct_answer),
                "difficulty": difficulty,
                "explanation": explanation,
                "knowledge_points": [normalized or "目标知识点"],
            })
        return questions

    def _topic_question_specs(self, topic: str) -> List[tuple]:
        """Return 10 concrete questions ordered from easy to hard."""
        if "反向传播" in topic:
            return [
                (1, "反向传播算法主要解决什么问题？", ["计算损失函数对各层参数的梯度", "随机初始化神经网络权重", "把训练数据切分成多个批次", "将连续特征转换为离散标签"], 0, "反向传播的核心作用是用链式法则从输出层向前逐层计算梯度。"),
                (1, "在反向传播开始之前，前向传播需要先得到哪类结果？", ["模型输出和损失值", "数据库索引", "测试集标签分布", "硬件显存容量"], 0, "没有前向传播得到的输出、缓存中间激活和损失值，就无法反向计算梯度。"),
                (2, "链式法则在反向传播中的作用是什么？", ["把复合函数的梯度拆成局部梯度的乘积", "保证每个神经元只输出0或1", "自动删除训练样本中的噪声", "让学习率在训练中保持不变"], 0, "多层网络是复合函数，链式法则把最终损失对参数的影响逐层传回。"),
                (2, "若学习率设置过大，反向传播训练最可能出现什么现象？", ["损失震荡甚至发散", "梯度一定变成零", "模型参数停止更新", "训练数据自动增多"], 0, "学习率过大会让参数更新步长过大，可能越过最优点并导致损失不稳定。"),
                (3, "隐藏层权重的梯度通常依赖哪些信息？", ["后一层传回的误差信号、本层输入和激活函数导数", "仅依赖当前权重的初始值", "仅依赖训练集样本数量", "仅依赖模型保存路径"], 0, "隐藏层梯度由后续层误差通过链式法则传回，并结合本层局部导数计算。"),
                (3, "Sigmoid 在深层网络中容易导致梯度消失，主要原因是什么？", ["饱和区导数接近0，连续相乘后梯度变小", "输出值一定大于1", "它不能用于二分类任务", "它会强制权重全部为正"], 0, "Sigmoid 饱和时局部梯度很小，多层相乘会让早期层梯度迅速衰减。"),
                (4, "梯度检查通常用来验证什么？", ["反向传播实现的梯度是否接近数值差分梯度", "模型是否已经达到最高准确率", "训练集是否没有重复样本", "推理服务是否部署成功"], 0, "梯度检查用有限差分近似梯度，与反向传播结果对比，排查实现错误。"),
                (4, "在小批量训练中，参数更新通常基于什么梯度？", ["一个 batch 内样本损失梯度的平均或总和", "单个随机权重的符号", "验证集准确率的最大值", "测试集标签的排序结果"], 0, "mini-batch 梯度下降会汇总一批样本的梯度，再更新参数。"),
                (5, "残差连接有助于深层网络训练，和反向传播相关的主要原因是什么？", ["提供更直接的梯度传播路径", "让所有层参数完全相同", "取消损失函数计算", "让输入数据不需要归一化"], 0, "残差连接提供跳跃路径，能缓解深层网络梯度难以传回的问题。"),
                (5, "如果某层梯度长期接近0，合理的排查方向是什么？", ["检查激活函数饱和、初始化、归一化和学习率设置", "只增加文件导出次数", "把所有答案标签改成同一类", "删除损失函数中的真实标签"], 0, "梯度接近0常与激活饱和、初始化不当、归一化不足或优化超参数有关。"),
            ]

        label = topic or "目标知识点"
        return [
            (1, f"学习「{label}」时，第一步最应该确认什么？", ["核心概念、输入输出和适用场景", "代码文件的颜色主题", "浏览器窗口的大小", "项目目录的图标样式"], 0, "先确认概念边界和适用场景，后续实操才有依据。"),
            (1, f"判断自己是否理解「{label}」的基础概念，最有效的方法是什么？", ["用自己的话解释概念并举一个例子", "只记住标题", "跳过练习直接看答案", "把资料复制到新文件"], 0, "能解释并举例说明，通常代表已经形成初步理解。"),
            (2, f"围绕「{label}」做练习时，为什么要保留错误记录？", ["便于定位薄弱点并针对性复盘", "为了增加文件大小", "为了减少训练次数", "为了隐藏真实结果"], 0, "错误记录能暴露认知盲点，是后续改进的重要依据。"),
            (2, f"如果对「{label}」只会背定义但不会应用，下一步应该做什么？", ["补充场景化例题和动手任务", "继续只背定义", "删除相关资料", "关闭反馈机制"], 0, "从定义到应用需要通过具体场景和任务建立迁移能力。"),
            (3, f"评价一份「{label}」学习方案是否有效，关键看什么？", ["目标、步骤、练习和反馈是否闭环", "标题是否足够长", "是否只有一个章节", "是否完全没有检测题"], 0, "有效方案应形成学习目标、任务执行和反馈改进的闭环。"),
            (3, f"当「{label}」相关知识点很多时，较合理的学习顺序是什么？", ["先基础概念，再关键方法，最后综合应用", "随机选择章节", "先做最难题再看概念", "只阅读最后一段"], 0, "从基础到应用的顺序更符合认知负荷规律。"),
            (4, f"在进阶学习「{label}」时，如何降低幻觉或错误理解？", ["把生成内容与教材、文档或知识库来源交叉验证", "只相信第一段输出", "不看任何来源", "只关注标题是否正确"], 0, "交叉验证能减少模型生成或个人理解中的错误。"),
            (4, f"把「{label}」用于真实任务前，最应该补充哪类验证？", ["边界条件、反例和实际数据测试", "字体大小测试", "文件名长度测试", "页面背景色测试"], 0, "真实任务需要检验边界、反例和数据适配情况。"),
            (5, f"如果要向别人讲清楚「{label}」，最能体现深度理解的是哪种方式？", ["解释原理、适用条件、限制和常见误区", "只朗读标题", "只展示目录", "只说自己看过资料"], 0, "能说明原理、边界和误区，说明理解不是停留在记忆层面。"),
            (5, f"设计「{label}」综合任务时，为什么要包含评价标准？", ["让学习结果可检查、可比较、可改进", "让任务看起来更复杂", "避免用户提交答案", "替代所有学习内容"], 0, "评价标准能把任务结果转化为可验证反馈。"),
        ]
    
    def _extract_key_points_text(self, content: str, count: int) -> List[str]:
        """从文本中提取要点（模拟）"""
        sentences = [s.strip() for s in content.replace("。", "。\n").split("\n") if s.strip()]
        return sentences[:count]
    
    def _generate_title(self, topic: str, resource_type: str, diagnosis: Dict) -> str:
        """生成资源标题"""
        difficulty = diagnosis.get("recommended_difficulty", {}).get("recommended_difficulty", 3)
        return build_resource_title(topic, resource_type, difficulty)
    
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
