"""
学情诊断 Agent
接收学习者画像数据，输出标准化知识盲区、能力层级、适配资源难度参数
"""
from typing import Dict, Any, List
from loguru import logger
from app.agents.base import BaseAgent


class DiagnosisAgent(BaseAgent):
    """
    学情诊断 Agent
    
    职责：
    - 分析学习者画像数据
    - 识别知识盲区与能力优势
    - 计算能力层级
    - 推荐适配的资源难度参数
    """
    
    # 能力维度配置
    ABILITY_DIMENSIONS = [
        ("theoretical_foundation", "理论基础"),
        ("programming_ability", "编程能力"),
        ("algorithm_design", "算法设计"),
        ("system_architecture", "系统架构"),
        ("data_analysis", "数据分析"),
        ("engineering_practice", "工程实践"),
    ]
    
    def __init__(self):
        super().__init__(
            agent_type="diagnosis",
            agent_name="学情诊断Agent",
        )
    
    def execute(self, input_data: Dict[str, Any], context: Dict[str, Any] = None) -> Dict[str, Any]:
        """
        执行学情诊断
        
        Args:
            input_data: 输入数据，包含 learner_profile
            context: 上下文数据
            
        Returns:
            诊断结果
        """
        learner_profile = input_data.get("learner_profile")
        if not learner_profile:
            raise ValueError("缺少学习者画像数据")
        
        # 1. 提取能力评分
        ability_scores = self._extract_ability_scores(learner_profile)
        
        # 2. 分析能力层级
        ability_levels = self._analyze_ability_levels(ability_scores)
        
        # 3. 识别知识盲区
        blind_areas = self._identify_blind_areas(learner_profile, ability_scores)
        
        # 4. 识别能力优势
        strengths = self._identify_strengths(ability_scores)
        
        # 5. 计算资源难度推荐
        difficulty_params = self._calculate_difficulty_params(ability_scores, learner_profile)
        
        # 6. 生成学习建议
        recommendations = self._generate_recommendations(
            ability_scores,
            blind_areas,
            learner_profile,
        )
        
        result = {
            "learner_id": input_data.get("learner_id"),
            "ability_scores": ability_scores,
            "ability_levels": ability_levels,
            "overall_score": sum(ability_scores.values()) / len(ability_scores),
            "overall_level": self._get_overall_level(ability_scores),
            "knowledge_blind_areas": blind_areas,
            "knowledge_strengths": strengths,
            "recommended_difficulty": difficulty_params,
            "recommendations": recommendations,
            "learning_style": learner_profile.get("learning_style", "visual"),
            "target_industry": learner_profile.get("target_industry"),
        }
        
        logger.debug(f"[学情诊断Agent] 诊断完成: 综合得分={result['overall_score']:.1f}")
        
        return result
    
    def _extract_ability_scores(self, profile: Dict[str, Any]) -> Dict[str, float]:
        """
        提取六维能力评分
        
        Args:
            profile: 学习者画像
            
        Returns:
            能力评分字典
        """
        scores = {}
        for field_key, field_name in self.ABILITY_DIMENSIONS:
            scores[field_key] = profile.get(field_key, 0) or 0
        return scores
    
    def _analyze_ability_levels(self, scores: Dict[str, float]) -> Dict[str, Dict[str, Any]]:
        """
        分析各维度能力层级
        
        Args:
            scores: 能力评分
            
        Returns:
            能力层级字典
        """
        levels = {}
        for field_key, field_name in self.ABILITY_DIMENSIONS:
            score = scores.get(field_key, 0)
            level = self._score_to_level(score)
            levels[field_key] = {
                "name": field_name,
                "score": score,
                "level": level,
                "description": self._get_level_description(field_key, level),
            }
        return levels
    
    def _score_to_level(self, score: float) -> str:
        """
        分数转等级
        
        Args:
            score: 分数(0-100)
            
        Returns:
            等级名称
        """
        if score >= 90:
            return "精通"
        elif score >= 75:
            return "熟练"
        elif score >= 60:
            return "掌握"
        elif score >= 40:
            return "了解"
        else:
            return "薄弱"
    
    def _get_level_description(self, dimension: str, level: str) -> str:
        """
        获取能力等级描述
        
        Args:
            dimension: 维度key
            level: 等级
            
        Returns:
            描述文本
        """
        descriptions = {
            "精通": "深入掌握，能够独立解决复杂问题并指导他人",
            "熟练": "熟练掌握，能够处理常见问题并进行一定优化",
            "掌握": "基本掌握，能够完成常规任务",
            "了解": "有初步了解，需要进一步学习和实践",
            "薄弱": "基础薄弱，需要从入门开始系统学习",
        }
        return descriptions.get(level, "")
    
    def _identify_blind_areas(
        self,
        profile: Dict[str, Any],
        ability_scores: Dict[str, float],
    ) -> List[Dict[str, Any]]:
        """
        识别知识盲区
        
        Args:
            profile: 学习者画像
            ability_scores: 能力评分
            
        Returns:
            盲区列表
        """
        blind_areas = []
        
        # 1. 从画像中获取已标注的盲区
        profile_blind_areas = profile.get("knowledge_blind_areas", []) or []
        for area in profile_blind_areas:
            blind_areas.append({
                "name": area,
                "type": "tag",
                "severity": "high",
                "source": "user_profile",
            })
        
        # 2. 从能力评分识别低分区
        for field_key, field_name in self.ABILITY_DIMENSIONS:
            score = ability_scores.get(field_key, 0)
            if score < 60:
                severity = "high" if score < 40 else "medium"
                blind_areas.append({
                    "name": field_name,
                    "type": "ability",
                    "severity": severity,
                    "score": score,
                    "source": "ability_analysis",
                })
        
        # 按严重程度排序
        blind_areas.sort(key=lambda x: 0 if x["severity"] == "high" else 1)
        
        return blind_areas
    
    def _identify_strengths(self, scores: Dict[str, float]) -> List[Dict[str, Any]]:
        """
        识别能力优势
        
        Args:
            scores: 能力评分
            
        Returns:
            优势列表
        """
        strengths = []
        for field_key, field_name in self.ABILITY_DIMENSIONS:
            score = scores.get(field_key, 0)
            if score >= 75:
                strengths.append({
                    "name": field_name,
                    "score": score,
                    "level": self._score_to_level(score),
                })
        
        # 按分数降序
        strengths.sort(key=lambda x: x["score"], reverse=True)
        
        return strengths
    
    def _calculate_difficulty_params(
        self,
        scores: Dict[str, float],
        profile: Dict[str, Any],
    ) -> Dict[str, Any]:
        """
        计算推荐的资源难度参数
        
        Args:
            scores: 能力评分
            profile: 学习者画像
            
        Returns:
            难度参数字典
        """
        avg_score = sum(scores.values()) / len(scores) if scores else 50
        
        # 根据平均分计算推荐难度等级(1-5)
        if avg_score >= 85:
            base_difficulty = 5
        elif avg_score >= 70:
            base_difficulty = 4
        elif avg_score >= 55:
            base_difficulty = 3
        elif avg_score >= 40:
            base_difficulty = 2
        else:
            base_difficulty = 1
        
        # 用户偏好调整
        preferred_difficulty = profile.get("preferred_difficulty", 3)
        adjusted_difficulty = (base_difficulty + preferred_difficulty) / 2
        adjusted_difficulty = max(1, min(5, round(adjusted_difficulty)))
        
        return {
            "base_difficulty": base_difficulty,
            "preferred_difficulty": preferred_difficulty,
            "recommended_difficulty": adjusted_difficulty,
            "avg_score": round(avg_score, 1),
        }
    
    def _generate_recommendations(
        self,
        scores: Dict[str, float],
        blind_areas: List[Dict[str, Any]],
        profile: Dict[str, Any],
    ) -> List[str]:
        """
        生成学习建议
        
        Args:
            scores: 能力评分
            blind_areas: 盲区列表
            profile: 学习者画像
            
        Returns:
            建议列表
        """
        recommendations = []
        
        # 找出最大盲区
        high_severity = [b for b in blind_areas if b["severity"] == "high"]
        if high_severity:
            top_blind = high_severity[0]
            recommendations.append(
                f"重点提升「{top_blind['name']}」能力，当前处于{top_blind.get('level', '薄弱')}水平"
            )
            recommendations.append(
                "建议从基础概念开始，循序渐进，配合实操练习巩固"
            )
        
        # 根据整体水平建议
        avg_score = sum(scores.values()) / len(scores) if scores else 0
        if avg_score < 40:
            recommendations.append("整体基础偏弱，建议从入门级资源开始系统学习")
            recommendations.append("每日学习时间建议控制在45-60分钟，避免信息过载")
        elif avg_score < 60:
            recommendations.append("基础一般，建议重点突破薄弱环节")
            recommendations.append("可尝试进阶级内容，但需配合基础回顾")
        elif avg_score < 80:
            recommendations.append("能力中等，可挑战进阶难度的学习资源")
            recommendations.append("建议增加项目实战，提升综合应用能力")
        else:
            recommendations.append("基础扎实，建议挑战高阶实战项目和前沿内容")
            recommendations.append("可尝试参与开源项目或技术竞赛，以练代学")
        
        # 学习风格建议
        learning_style = profile.get("learning_style", "visual")
        style_suggestions = {
            "visual": "推荐使用图表、流程图、思维导图等可视化学习方式",
            "auditory": "推荐视频课程、技术分享、播客等听觉学习方式",
            "reading": "推荐技术文档、专业书籍、技术博客等阅读学习方式",
            "kinesthetic": "推荐实操项目、编程练习、动手实验等实践学习方式",
        }
        if learning_style in style_suggestions:
            recommendations.append(style_suggestions[learning_style])
        
        return recommendations
    
    def _get_overall_level(self, scores: Dict[str, float]) -> str:
        """
        获取综合能力等级
        
        Args:
            scores: 各维度评分
            
        Returns:
            综合等级
        """
        avg = sum(scores.values()) / len(scores) if scores else 0
        return self._score_to_level(avg)
    
    def validate(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """
        校验诊断结果
        
        Args:
            data: 诊断结果数据
            
        Returns:
            校验结果
        """
        result = super().validate(data)
        
        issues = []
        score = 100
        
        # 检查必要字段
        required_fields = ["ability_scores", "knowledge_blind_areas", "recommended_difficulty"]
        for field in required_fields:
            if field not in data:
                issues.append(f"缺少必要字段: {field}")
                score -= 15
        
        # 检查分数范围
        if "ability_scores" in data:
            for dim, s in data["ability_scores"].items():
                if s < 0 or s > 100:
                    issues.append(f"能力分数超出范围: {dim}={s}")
                    score -= 5
        
        result["issues"].extend(issues)
        result["score"] = max(0, score)
        result["passed"] = len(issues) == 0
        
        return result