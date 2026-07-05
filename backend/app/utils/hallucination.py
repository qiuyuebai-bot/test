"""
幻觉识别双层检测工具
Layer 1: 规则快速预检（关键词 + 数值比对 + 技术概念校验）— 毫秒级，零成本
Layer 2: LLM深度事实核查（语义一致性校验）— 仅在Layer 1检测到高风险时触发，节省Token
"""
from typing import List, Dict, Any, Tuple, Optional
import re
import threading
from loguru import logger
from app.config import settings


class HallucinationUtil:
    """幻觉识别与检测工具类（双层检测机制）"""
    
    HALLUCINATION_KEYWORDS = {
        "fake_markers": ["据说", "传闻", "未经证实", "不可靠来源", "网络上说"],
        "over_confident": ["绝对", "一定", "毫无疑问", "百分百", "必然"],
        "ambiguous": ["某种程度上", "大概", "可能", "或许", "好像"],
        "contradiction": ["相反", "实际上", "事实上", "但是实际上"],
    }

    # Layer 2 触发阈值：Layer 1 得分超过此值时才调用LLM深度核查
    DEEP_CHECK_TRIGGER_SCORE = 5.0
    
    # LLM深度核查结果缓存（避免重复调用）
    _deep_check_cache: Dict[str, Dict] = {}
    _CACHE_MAX_SIZE = 200
    _cache_lock = threading.Lock()

    @staticmethod
    def detect_hallucination(
        content: str,
        reference_content: Optional[str] = None,
        reference_knowledge: Optional[List[Dict]] = None,
        threshold: float = None,
        use_deep_check: bool = True,
    ) -> Tuple[bool, Dict[str, Any]]:
        """
        双层幻觉检测
        
        Args:
            content: 待检测内容
            reference_content: 参考文本（拼接后的）
            reference_knowledge: 参考知识库切片列表（用于LLM深度核查）
            threshold: 幻觉评分阈值
            use_deep_check: 是否启用Layer 2深度核查
            
        Returns:
            Tuple[是否幻觉, 检测详情]
        """
        if not content:
            return False, {"score": 0, "keywords": [], "reason": "内容为空", "layer": "none"}
        
        threshold = threshold or settings.HALLUCINATION_THRESHOLD
        
        # ========== Layer 1: 规则快速预检 ==========
        keyword_score, detected_keywords = HallucinationUtil._check_keywords(content)
        contradiction_score, contradictions = HallucinationUtil._check_contradiction(content, reference_content)
        tech_score, tech_issues = HallucinationUtil._check_technical_concepts(content, reference_content)
        rule_score = keyword_score + contradiction_score + tech_score
        
        layer1_result = {
            "is_hallucination": rule_score >= threshold,
            "score": rule_score,
            "threshold": threshold,
            "keyword_score": keyword_score,
            "contradiction_score": contradiction_score,
            "tech_score": tech_score,
            "detected_keywords": detected_keywords,
            "contradictions": contradictions,
            "tech_issues": tech_issues,
            "layer": "rule",
        }
        
        # 如果规则层已明确判定为无幻觉且得分极低，直接返回（节省LLM调用）
        if rule_score == 0 and not contradictions and not tech_issues:
            return False, layer1_result
        
        # ========== Layer 2: LLM深度核查（条件触发） ==========
        deep_result = None
        if use_deep_check and rule_score >= HallucinationUtil.DEEP_CHECK_TRIGGER_SCORE:
            deep_result = HallucinationUtil._llm_deep_check(
                content=content,
                rule_result=layer1_result,
                reference_knowledge=reference_knowledge,
                reference_content=reference_content,
            )
        
        # 综合评分：规则分(0~60) + LLM分(0~40)
        final_score = rule_score
        hallucination_points = list(detected_keywords)
        
        if deep_result:
            llm_score = deep_result.get("score", 0)
            final_score = min(100, rule_score * 0.6 + llm_score * 0.4)
            if deep_result.get("hallucination_points"):
                hallucination_points.extend(deep_result["hallucination_points"])
            layer1_result["deep_check"] = deep_result
            layer1_result["layer"] = "rule+llm"
        
        is_hallucination = final_score >= threshold
        layer1_result["score"] = round(final_score, 2)
        layer1_result["is_hallucination"] = is_hallucination
        
        if is_hallucination:
            logger.warning(
                f"[幻觉检测] 检出幻觉: score={final_score:.1f}, "
                f"layer={layer1_result['layer']}, keywords={hallucination_points[:5]}"
            )
        
        return is_hallucination, layer1_result

    @staticmethod
    def _llm_deep_check(
        content: str,
        rule_result: Dict[str, Any],
        reference_knowledge: Optional[List[Dict]] = None,
        reference_content: Optional[str] = None,
    ) -> Optional[Dict[str, Any]]:
        """
        Layer 2: 使用LLM做语义级事实核查
        
        当规则检测发现可疑内容时，调用LLM判断是否存在：
        1. 无来源支撑的事实声称
        2. 与参考知识相悖的表述
        3. 编造的专业术语/数据/引用
        
        Args:
            content: 待检测内容
            rule_result: 规则层检测结果
            reference_knowledge: 参考知识库
            reference_content: 参考文本
            
        Returns:
            LLM核查结果或None（LLM不可用时）
        """
        from app.utils.llm import LLMUtil
        
        if not LLMUtil.is_available():
            return None
        
        # 缓存key（内容+参考前200字的哈希摘要简化）
        import hashlib
        ref_excerpt = (reference_content or "")[:200]
        cache_key = hashlib.md5(
            (content[:500] + "||" + ref_excerpt).encode("utf-8")
        ).hexdigest()
        
        if cache_key in HallucinationUtil._deep_check_cache:
            return HallucinationUtil._deep_check_cache[cache_key]
        
        try:
            ref_text = reference_content or ""
            if not ref_text and reference_knowledge:
                ref_parts = []
                for k in reference_knowledge[:5]:
                    title = k.get("title", "")
                    c = k.get("content", "")
                    ref_parts.append(f"[{title}] {c[:300]}")
                ref_text = "\n".join(ref_parts)
            
            if not ref_text:
                return None
            
            # 规则层发现的可疑点提示
            suspicious_points = []
            if rule_result.get("detected_keywords"):
                suspicious_points.extend(rule_result["detected_keywords"])
            if rule_result.get("contradictions"):
                for c in rule_result["contradictions"][:3]:
                    suspicious_points.append(f"数值偏差: {c.get('content_value')} vs 参考值{c.get('reference_value')}")
            
            system_prompt = (
                "你是一位严格的事实核查专家。你的任务是判断生成内容是否存在幻觉"
                "（即：无依据的事实声称、与参考知识矛盾、编造的信息等）。"
                "请严格依据提供的参考知识进行判断，不要使用参考知识之外的信息。"
                "输出必须是严格的JSON格式，不要添加任何其他文字。"
            )
            
            user_prompt = (
                f"## 参考知识\n{ref_text[:2000]}\n\n"
                f"## 待检测内容\n{content[:2000]}\n\n"
                f"## 规则层初检发现的可疑点\n{'; '.join(suspicious_points[:8]) if suspicious_points else '无'}\n\n"
                f"请判断待检测内容中是否存在幻觉，输出JSON：\n"
                f'{{"has_hallucination": true/false, '
                f'"score": 0-100的幻觉评分(0=无幻觉,100=严重幻觉), '
                f'"hallucination_points": ["具体幻觉描述1", "具体幻觉描述2"], '
                f'"confidence": 0-1的置信度}}'
            )
            
            response_text, _ = LLMUtil.sync_call(
                prompt=user_prompt,
                system_prompt=system_prompt,
                temperature=0.1,
            )
            
            # 解析JSON
            json_match = re.search(r'\{[\s\S]*\}', response_text)
            if not json_match:
                return None
            
            import json as _json
            result = _json.loads(json_match.group())
            
            deep_result = {
                "has_hallucination": result.get("has_hallucination", False),
                "score": float(result.get("score", 0)),
                "hallucination_points": result.get("hallucination_points", []),
                "confidence": float(result.get("confidence", 0.5)),
            }
            
            # 写入缓存
            with HallucinationUtil._cache_lock:
                HallucinationUtil._deep_check_cache[cache_key] = deep_result
                if len(HallucinationUtil._deep_check_cache) > HallucinationUtil._CACHE_MAX_SIZE:
                    # 简单清理：删除最早的1/3
                    keys = list(HallucinationUtil._deep_check_cache.keys())
                    for k in keys[:len(keys) // 3]:
                        del HallucinationUtil._deep_check_cache[k]
            
            return deep_result
            
        except Exception as e:
            logger.debug(f"[幻觉检测] LLM深度核查失败，回退到规则结果: {e}")
            return None

    @staticmethod
    def _check_keywords(content: str) -> Tuple[float, List[str]]:
        detected = []
        score = 0
        
        for category, keywords in HallucinationUtil.HALLUCINATION_KEYWORDS.items():
            for kw in keywords:
                if kw in content:
                    detected.append(kw)
                    weight = {
                        "fake_markers": 15,
                        "over_confident": 10,
                        "ambiguous": 5,
                        "contradiction": 20,
                    }.get(category, 5)
                    score += weight
        
        return score, detected

    @staticmethod
    def _check_contradiction(
        content: str,
        reference_content: Optional[str],
    ) -> Tuple[float, List[Dict]]:
        if not reference_content:
            return 0, []
        
        contradictions = []
        score = 0
        
        content_numbers = HallucinationUtil._extract_numbers(content)
        reference_numbers = HallucinationUtil._extract_numbers(reference_content)
        
        for num_type, value in content_numbers.items():
            if num_type in reference_numbers:
                ref_value = reference_numbers[num_type]
                if value != ref_value:
                    deviation = abs(value - ref_value) / max(ref_value, 1) * 100
                    if deviation > 10:
                        contradictions.append({
                            "type": "number_deviation",
                            "content_value": value,
                            "reference_value": ref_value,
                            "deviation": round(deviation, 1),
                        })
                        score += min(deviation, 30)
        
        return score, contradictions

    @staticmethod
    def _check_technical_concepts(
        content: str,
        reference_content: Optional[str],
    ) -> Tuple[float, List[Dict]]:
        issues = []
        score = 0
        
        version_pattern = r'v?\d+\.\d+(\.\d+)?'
        versions_in_content = set(re.findall(version_pattern, content))
        
        if versions_in_content and reference_content:
            versions_in_ref = set(re.findall(version_pattern, reference_content))
            for v in versions_in_content:
                if v not in versions_in_ref:
                    issues.append({
                        "type": "version_mismatch",
                        "value": v,
                        "reason": "版本号在参考内容中未找到",
                    })
                    score += 15
        
        api_pattern = r'[a-zA-Z_][a-zA-Z0-9_]*\(\)'
        apis_in_content = set(re.findall(api_pattern, content))
        
        if apis_in_content and reference_content:
            apis_in_ref = set(re.findall(api_pattern, reference_content))
            for api in apis_in_content:
                if api not in apis_in_ref and len(api) > 4:
                    issues.append({
                        "type": "api_mismatch",
                        "value": api,
                        "reason": "API/函数在参考内容中未找到",
                    })
                    score += 10
        
        return score, issues

    @staticmethod
    def _extract_numbers(text: str) -> Dict[str, float]:
        numbers = {}
        
        percentages = re.findall(r'(\d+(?:\.\d+)?)%', text)
        for p in percentages:
            key = f"pct_{p}"
            if key not in numbers:
                numbers[key] = float(p)
        
        integers = re.findall(r'(?<!\d)(\d{2,5})(?!\d)', text)
        for i in integers:
            key = f"int_{i}"
            if key not in numbers:
                numbers[key] = float(i)
        
        return numbers

    @staticmethod
    def suggest_correction(
        content: str,
        hallucination_info: Dict,
        reference_content: Optional[str] = None,
    ) -> str:
        suggestions = []
        
        if hallucination_info.get("detected_keywords"):
            suggestions.append(f"建议移除或替换以下不确定表述: {hallucination_info['detected_keywords']}")
        
        if hallucination_info.get("contradictions"):
            for c in hallucination_info["contradictions"]:
                suggestions.append(
                    f"数值偏差: 内容中为{c.get('content_value')}，参考值为{c.get('reference_value')}（偏差{c.get('deviation', 0):.1f}%）"
                )
        
        if hallucination_info.get("tech_issues"):
            for t in hallucination_info["tech_issues"]:
                suggestions.append(f"技术概念核实: {t.get('value')} - {t.get('reason')}")
        
        deep = hallucination_info.get("deep_check")
        if deep and deep.get("hallucination_points"):
            for p in deep["hallucination_points"]:
                suggestions.append(f"[LLM核查] {p}")
        
        return "\n".join(suggestions) if suggestions else "无明显幻觉"

    @staticmethod
    def batch_detect(
        contents: List[str],
        reference_contents: List[str] = None,
        use_deep_check: bool = False,
    ) -> List[Dict]:
        """
        批量幻觉检测（默认不启用LLM深度核查，避免大量Token消耗）
        """
        results = []
        
        for i, content in enumerate(contents):
            ref = reference_contents[i] if reference_contents and i < len(reference_contents) else None
            is_hallucination, info = HallucinationUtil.detect_hallucination(
                content, ref, use_deep_check=use_deep_check,
            )
            results.append({
                "index": i,
                "is_hallucination": is_hallucination,
                "info": info,
            })
        
        hallucination_count = sum(1 for r in results if r["is_hallucination"])
        logger.info(f"[幻觉检测] 批量检测完成: 总数={len(contents)}, 幻觉数={hallucination_count}")
        
        return results

    @classmethod
    def clear_cache(cls) -> None:
        """清空LLM深度核查结果缓存"""
        cls._deep_check_cache.clear()
