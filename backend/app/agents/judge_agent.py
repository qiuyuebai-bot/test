"""
审核裁判 Agent
接收生成Agent输出内容，调取原始知识库做交叉比对，识别专业幻觉、行业规范错误
实现辩论交叉验证机制
"""
import re
from typing import Dict, Any, List
from loguru import logger
from app.agents.base import BaseAgent, AgentStatus
from app.utils.hallucination import HallucinationUtil


class JudgeAgent(BaseAgent):
    """
    审核裁判 Agent
    
    职责：
    - 接收生成Agent输出内容
    - 调取原始知识库做交叉比对
    - 识别专业幻觉、行业规范错误
    - 与生成Agent双向辩论，验证内容准确性
    - 生成修正方案
    - 统计幻觉率
    """
    
    def __init__(self):
        super().__init__(
            agent_type="judge",
            agent_name="审核裁判Agent",
        )
    
    def execute(self, input_data: Dict[str, Any], context: Dict[str, Any] = None) -> Dict[str, Any]:
        """
        执行审核校验
        
        Args:
            input_data: 输入数据，包含 generated_content, reference_knowledge
            context: 上下文数据
            
        Returns:
            审核结果
        """
        generated_content = input_data.get("generated_content", "")
        reference_knowledge = input_data.get("reference_knowledge", [])
        debate_round = input_data.get("debate_round", 1)
        
        if not generated_content:
            raise ValueError("缺少待审核的生成内容")
        
        # 1. 关键词幻觉检测
        keyword_result = HallucinationUtil.detect_hallucination(
            generated_content,
            reference_content=self._extract_reference_text(reference_knowledge),
        )
        is_hallucination, hallucination_info = keyword_result
        
        # 2. 事实一致性校验
        consistency_result = self._check_fact_consistency(
            generated_content,
            reference_knowledge,
        )
        
        # 3. 行业规范校验
        standard_result = self._check_industry_standards(
            generated_content,
            reference_knowledge,
        )
        
        # 4. 综合评估
        issues = []
        if hallucination_info.get("detected_keywords"):
            issues.append({
                "type": "hallucination_keyword",
                "severity": "high",
                "description": "检测到疑似幻觉关键词",
                "details": hallucination_info["detected_keywords"],
            })
        
        issues.extend(consistency_result["issues"])
        issues.extend(standard_result["issues"])
        
        # 5. 计算总体评分
        total_score = self._calculate_validation_score(
            hallucination_info,
            consistency_result,
            standard_result,
        )
        
        # 6. 生成修正建议
        correction_suggestions = self._generate_corrections(
            generated_content,
            reference_knowledge,
            issues,
        )
        
        # 7. 辩论结果记录
        debate_record = {
            "round": debate_round,
            "judge_view": {
                "has_issue": len(issues) > 0,
                "issues": issues,
                "score": total_score,
                "decision": "approved" if total_score >= 85 else "needs_revision" if total_score >= 60 else "rejected",
            },
            "corrections": correction_suggestions,
        }
        
        result = {
            "passed": total_score >= 85,
            "overall_score": total_score,
            "issue_count": len(issues),
            "hallucination_detected": is_hallucination,
            "hallucination_score": hallucination_info.get("score", 0),
            "consistency_score": consistency_result.get("score", 100),
            "standard_score": standard_result.get("score", 100),
            "issues": issues,
            "corrections": correction_suggestions,
            "debate_record": debate_record,
            "source_slice_ids": [k.get("slice_id") for k in reference_knowledge if k.get("slice_id")],
            "source_doc_ids": list(set([k.get("doc_id") for k in reference_knowledge if k.get("doc_id")])),
        }
        
        logger.debug(
            f"[审核裁判Agent] 审核完成: 得分={total_score}, "
            f"问题数={len(issues)}, 幻觉={is_hallucination}"
        )
        
        return result
    
    def debate_with_generation(
        self,
        generated_content: str,
        reference_knowledge: List[Dict],
        previous_debates: List[Dict] = None,
        max_rounds: int = 3,
    ) -> Dict[str, Any]:
        """
        与生成Agent进行辩论交叉验证（核心创新机制）
        
        Args:
            generated_content: 生成内容
            reference_knowledge: 参考知识库
            previous_debates: 之前的辩论记录
            
        Returns:
            辩论结果
        """
        self.status = AgentStatus.VALIDATING
        
        previous_debates = previous_debates or []
        current_round = len(previous_debates) + 1
        
        logger.info(f"[审核裁判Agent] 第{current_round}轮辩论开始")
        
        # 执行校验
        audit_result = self.execute({
            "generated_content": generated_content,
            "reference_knowledge": reference_knowledge,
            "debate_round": current_round,
        })
        
        # 辩论结果
        debate_result = {
            "round": current_round,
            "judge_standpoint": audit_result["debate_record"]["judge_view"],
            "generation_counterargument": self._generate_counterargument(
                generated_content,
                audit_result,
                current_round,
            ),
            "final_decision": audit_result["debate_record"]["judge_view"]["decision"],
            "corrections": audit_result["corrections"],
            "conflict_points": [
                i for i in audit_result["issues"]
                if i["severity"] in ("high", "medium")
            ],
            "confidence": audit_result.get("overall_score", 0) / 100,
        }
        
        if current_round >= max_rounds:
            debate_result["final_decision"] = "final_decision"
            debate_result["debate_ended"] = True
            debate_result["reason"] = "达到最大辩论轮次"
        
        self.status = AgentStatus.IDLE
        
        return debate_result
    
    def _check_fact_consistency(
        self,
        generated_content: str,
        reference_knowledge: List[Dict],
    ) -> Dict[str, Any]:
        """
        校验事实一致性
        
        Args:
            generated_content: 生成内容
            reference_knowledge: 参考知识库
            
        Returns:
            一致性校验结果
        """
        issues = []
        score = 100
        
        # 提取参考文本
        ref_text = self._extract_reference_text(reference_knowledge)
        
        if not ref_text:
            return {
                "score": 70,
                "issues": [{
                    "type": "no_reference",
                    "severity": "medium",
                    "description": "缺少参考知识库，无法进行事实校验",
                }],
            }
        
        # 数字/数值一致性检测
        # 检查关键技术术语一致性
        tech_terms = [
            "API", "SDK", "REST", "JSON", "HTTP", "TCP", "UDP",
            "CPU", "GPU", "RAM", "ROM", "SSD", "HDD",
            "TCP/IP", "UDP", "DNS", "SSL", "TLS",
        ]
        
        for term in tech_terms:
            # 检查是否有无中生有的技术术语使用错误
            gen_count = generated_content.count(term)
            ref_count = ref_text.count(term)
            if gen_count > 0 and ref_count == 0 and len(generated_content) > 500:
                # 可能是幻觉，减分但不直接判定
                score -= 2
                issues.append({
                    "type": "uncertain_term",
                    "severity": "low",
                    "description": f"术语'{term}'在参考资料中未找到对应内容，需人工确认",
                    "term": term,
                })
        
        return {
            "score": max(0, score),
            "issues": issues,
        }
    
    def _check_industry_standards(
        self,
        generated_content: str,
        reference_knowledge: List[Dict],
    ) -> Dict[str, Any]:
        """
        校验行业规范
        
        Args:
            generated_content: 生成内容
            reference_knowledge: 参考知识库
            
        Returns:
            规范校验结果
        """
        issues = []
        score = 100
        
        # 常见行业规范错误模式
        error_patterns = [
            # 数字单位错误
            (r'\d+\s*Gbps?', '数据速率单位使用需谨慎'),
            # 夸大绝对化表述
            (r'百分百|百分之百|一定|绝对保证', '避免绝对化表述'),
            # 技术版本错误
            (r'v?\d+\.\d+\.\d+', '技术版本号需核实'),
        ]
        
        for pattern, description in error_patterns:
            matches = re.findall(pattern, generated_content)
            if matches:
                score -= len(matches) * 3
                issues.append({
                    "type": "standard_issue",
                    "severity": "low",
                    "description": description,
                    "matches": matches[:5],
                })
        
        return {
            "score": max(0, min(100, score)),
            "issues": issues,
        }
    
    def _calculate_validation_score(
        self,
        hallucination_info: Dict,
        consistency_result: Dict,
        standard_result: Dict,
    ) -> float:
        """
        计算综合校验得分
        
        Args:
            hallucination_info: 幻觉检测信息
            consistency_result: 一致性校验结果
            standard_result: 规范校验结果
            
        Returns:
            综合得分(0-100)
        """
        # 权重分配
        hallucination_weight = 0.4  # 幻觉检测权重
        consistency_weight = 0.35   # 事实一致性权重
        standard_weight = 0.25      # 规范校验权重
        
        # 幻觉得分（越高越安全，所以取反）
        hallucination_score = max(0, 100 - hallucination_info.get("score", 0))
        
        consistency_score = consistency_result.get("score", 100)
        standard_score = standard_result.get("score", 100)
        
        total_score = (
            hallucination_score * hallucination_weight +
            consistency_score * consistency_weight +
            standard_score * standard_weight
        )
        
        return round(total_score, 2)
    
    def _generate_corrections(
        self,
        generated_content: str,
        reference_knowledge: List[Dict],
        issues: List[Dict],
    ) -> List[Dict]:
        """
        生成修正方案
        
        Args:
            generated_content: 生成内容
            reference_knowledge: 参考知识库
            issues: 问题列表
            
        Returns:
            修正方案列表
        """
        corrections = []
        
        for issue in issues:
            correction = {
                "issue_type": issue.get("type", "unknown"),
                "severity": issue.get("severity", "medium"),
                "description": issue.get("description", ""),
                "original_content": issue.get("details", ""),
                "suggested_fix": self._get_suggested_fix(issue, reference_knowledge),
                "source_ref": issue.get("source", ""),
                "confidence": "high" if issue.get("severity") == "high" else "medium",
            }
            corrections.append(correction)
        
        # 按严重程度排序
        severity_order = {"high": 0, "medium": 1, "low": 2}
        corrections.sort(key=lambda x: severity_order.get(x["severity"], 3))
        
        return corrections
    
    def _get_suggested_fix(self, issue: Dict, reference_knowledge: List[Dict]) -> str:
        """
        获取建议修正内容
        
        Args:
            issue: 问题
            reference_knowledge: 参考知识库
            
        Returns:
            建议修正内容
        """
        issue_type = issue.get("type", "")
        
        if issue_type == "hallucination_keyword":
            return f"建议删除或替换疑似幻觉表述：{issue.get('description', '')}"
        
        elif issue_type == "no_reference":
            return "建议补充对应的知识库文档，或人工审核确认内容准确性"
        
        elif issue_type == "standard_issue":
            return f"建议核实相关表述：{issue.get('description', '')}"
        
        else:
            # 尝试从参考知识库中找相关内容
            for ref in reference_knowledge:
                if ref.get("content"):
                    return f"参考知识库文档：{ref.get('title', '未知标题')}"
            
            return "建议人工审核确认"
    
    def _generate_counterargument(
        self,
        generated_content: str,
        audit_result: Dict,
        round_num: int,
    ) -> Dict[str, Any]:
        """
        生成（模拟）生成Agent的辩论回应
        
        Args:
            generated_content: 生成内容
            audit_result: 审核结果
            round_num: 当前轮次
            
        Returns:
            生成Agent的回应
        """
        # 模拟生成Agent的辩护
        passed = audit_result.get("passed", False)
        issues = audit_result.get("issues", [])
        
        if passed:
            return {
                "accepts": True,
                "response": "内容已通过审核，确认无误。",
                "revisions_made": 0,
            }
        else:
            high_severity = [i for i in issues if i["severity"] == "high"]
            return {
                "accepts": len(high_severity) > 0,  # 高严重度问题接受修正
                "response": f"收到第{round_num}轮审核意见，{len(high_severity)}个高优先级问题将修正，其余问题可商榷。",
                "revisions_made": len(high_severity),
                "disputed_issues": [i for i in issues if i["severity"] == "low"],
            }
    
    def _extract_reference_text(self, reference_knowledge: List[Dict]) -> str:
        """提取参考文本"""
        texts = [k.get("content", "") for k in reference_knowledge]
        return "\n".join(texts)
    
    def _extract_numbers(self, text: str) -> List[str]:
        """提取文本中的数字"""
        return re.findall(r'\d+\.?\d*%?', text)
    
    def calculate_hallucination_rate(
        self,
        audit_results: List[Dict],
    ) -> Dict[str, Any]:
        """
        计算幻觉率统计
        
        Args:
            audit_results: 审核结果列表
            
        Returns:
            统计结果
        """
        total = len(audit_results)
        if total == 0:
            return {
                "total_count": 0,
                "hallucination_count": 0,
                "hallucination_rate": 0,
                "avg_score": 0,
            }
        
        hallucination_count = sum(
            1 for r in audit_results if r.get("hallucination_detected", False)
        )
        
        avg_score = sum(r.get("overall_score", 0) for r in audit_results) / total
        
        rate = (hallucination_count / total) * 100
        
        return {
            "total_count": total,
            "hallucination_count": hallucination_count,
            "hallucination_rate": round(rate, 2),
            "avg_score": round(avg_score, 2),
            "pass_rate": round(sum(1 for r in audit_results if r.get("passed", False)) / total * 100, 2),
        }
    
    def validate(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """
        校验审核结果
        
        Args:
            data: 审核结果数据
            
        Returns:
            校验结果
        """
        result = super().validate(data)
        
        issues = []
        score = 100
        
        required_fields = ["passed", "overall_score", "issues"]
        for field in required_fields:
            if field not in data:
                issues.append(f"缺少必要字段: {field}")
                score -= 20
        
        if "overall_score" in data:
            s = data["overall_score"]
            if s < 0 or s > 100:
                issues.append(f"校验分数超出范围: {s}")
                score -= 10
        
        result["issues"].extend(issues)
        result["score"] = max(0, score)
        result["passed"] = len(issues) == 0
        
        return result