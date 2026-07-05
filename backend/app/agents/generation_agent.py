"""
领域知识生成 Agent
读取专业知识库向量检索结果，基于学情参数生成初稿学习资源
"""
from typing import Dict, Any, List
from loguru import logger
from app.agents.base import BaseAgent


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
        
        if not knowledge_results:
            logger.warning("[知识生成Agent] 知识库检索结果为空")
        
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
            "resource_title": self._generate_title(target_topic, resource_type, diagnosis_result),
            "difficulty_level": diagnosis_result.get("recommended_difficulty", {}).get("recommended_difficulty", 3),
            "content": resource_content["content"],
            "content_json": resource_content.get("content_json", {}),
            "word_count": len(resource_content["content"]),
            "source_slice_ids": resource_content.get("source_slice_ids", []),
            "source_doc_ids": resource_content.get("source_doc_ids", []),
            "generation_method": "knowledge_based_generation",
        }
        
        logger.debug(f"[知识生成Agent] 生成完成: 类型={resource_type}, 字数={result['word_count']}")
        
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
                "steps": self._generate_steps(point["content"], difficulty),
                "tips": self._generate_tips(point["content"]),
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
            content_lines.append(ch["content"][:300] + "...\n")
            
            if ch["steps"]:
                content_lines.append("\n**实操步骤**：\n")
                for j, step in enumerate(ch["steps"]):
                    content_lines.append(f"{j+1}. {step}")
                content_lines.append("")
            
            if ch["tips"]:
                content_lines.append("\n> 💡 小贴士：" + ch["tips"] + "\n")
        
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
        difficulty = diagnosis.get("recommended_difficulty", {}).get("recommended_difficulty", 3)
        
        # 生成不同难度的题目
        basic_questions = self._generate_question_set(knowledge, topic, "basic", min(3, difficulty))
        advanced_questions = self._generate_question_set(knowledge, topic, "advanced", max(0, 5 - difficulty))
        
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
            content_lines.append(f"\n*难度：{'★' * q['difficulty']}*")
        
        content_lines.append("\n\n## 二、进阶挑战题\n")
        for i, q in enumerate(advanced_questions):
            content_lines.append(f"\n### 第{i+1}题：{q['question']}\n")
            for j, opt in enumerate(q["options"]):
                content_lines.append(f"- {chr(65+j)}. {opt}")
            content_lines.append(f"\n*难度：{'★' * q['difficulty']}*")
        
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
        difficulty = diagnosis.get("recommended_difficulty", {}).get("recommended_difficulty", 3)
        blind_areas = diagnosis.get("knowledge_blind_areas", [])
        
        # 组织章节
        sections = []
        for i, k in enumerate(knowledge[:6]):
            section = {
                "title": f"{i+1}. {k.get('title', f'知识点{i+1}')}",
                "content": k.get("content", ""),
                "key_points": self._extract_key_points_text(k.get("content", ""), 3),
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
            content_lines.append(sec["content"][:400] + "...\n")
            if sec["key_points"]:
                content_lines.append("\n**核心要点**：")
                for point in sec["key_points"]:
                    content_lines.append(f"- {point}")
                content_lines.append("")
        
        # 知识盲区专项
        if blind_areas:
            content_lines.append("\n---\n")
            content_lines.append("\n## 🎯 知识盲区专项突破\n")
            for i, blind in enumerate(blind_areas[:3]):
                content_lines.append(f"\n### {i+1}. {blind['name']}\n")
                content_lines.append(f"当前水平：{blind.get('severity', '中')}，建议优先学习提升。\n")
        
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
    
    def _generate_question_set(
        self,
        knowledge: List[Dict],
        topic: str,
        level: str,
        count: int,
    ) -> List[Dict]:
        """生成题目集（模拟）"""
        questions = []
        difficulty_map = {"basic": [1, 2, 3], "advanced": [3, 4, 5]}
        diff_levels = difficulty_map.get(level, [3])
        
        for i in range(count):
            diff = diff_levels[i % len(diff_levels)]
            q = {
                "question": f"关于{topic}的第{i+1}道{level}题",
                "options": [
                    "选项A（正确答案）",
                    "选项B（干扰项）",
                    "选项C（干扰项）",
                    "选项D（干扰项）",
                ],
                "correct_answer": 0,
                "difficulty": diff,
                "explanation": f"本题考查{topic}的核心概念，正确答案为A。",
            }
            questions.append(q)
        
        return questions
    
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