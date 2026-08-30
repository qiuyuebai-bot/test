"""
幻觉识别双层检测工具
Layer 1: 规则快速预检（关键词 + 数值比对 + 技术概念校验）— 毫秒级，零成本
Layer 2: LLM深度事实核查（语义一致性校验）— 仅在Layer 1检测到高风险时触发，节省Token
"""
from typing import List, Dict, Any, Tuple, Optional
import re
import threading
import logging
from loguru import logger
from app.config import settings
from app.services.ai_content_service import AIContentService
from app.utils.llm import LLMUtil
from app.utils.industry_rules import IndustrialRoboticsRules


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

    STRONG_RELEVANCE_THRESHOLD = settings.EVIDENCE_STRONG_THRESHOLD
    WEAK_RELEVANCE_THRESHOLD = settings.EVIDENCE_WEAK_THRESHOLD

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
            return False, {
                "score": 0,
                "keywords": [],
                "reason": "内容为空",
                "layer": "none",
                "is_hallucination": False,
                "confidence": 0.0,
                "credibility": "no_evidence",
                "evidence_coverage": 0.0,
                "method": "knowledge_gap",
                "evidence_status": "gap",
                "review_outcome": "pending",
                "review_source": "none",
                "risk_flags": [],
                "claims": [],
                "citations": [],
                "knowledge_gap": HallucinationUtil._knowledge_gap([], []),
            }
        
        # Knowledge-grounded detection is authoritative whenever the caller
        # supplies a knowledge result list. Rule and keyword checks remain
        # diagnostic compatibility signals only.
        if reference_knowledge is not None:
            return HallucinationUtil._detect_against_knowledge(content, reference_knowledge)

        threshold = threshold or settings.HALLUCINATION_THRESHOLD
        
        # ========== Layer 1: 规则快速预检 ==========
        keyword_score, detected_keywords = HallucinationUtil._check_keywords(content)
        contradiction_score, contradictions = HallucinationUtil._check_contradiction(content, reference_content)
        tech_score, tech_issues = HallucinationUtil._check_technical_concepts(content, reference_content)
        rule_score = keyword_score + contradiction_score + tech_score
        
        layer1_result = {
            "is_hallucination": False,
            "score": rule_score,
            "threshold": threshold,
            "keyword_score": keyword_score,
            "contradiction_score": contradiction_score,
            "tech_score": tech_score,
            "detected_keywords": detected_keywords,
            "contradictions": contradictions,
            "tech_issues": tech_issues,
            "evidence_status": "sufficient" if reference_content else "gap",
            "review_outcome": "pending",
            "review_source": "rules_fallback",
            "risk_flags": [*contradictions, *tech_issues],
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
        
        is_hallucination = bool(
            contradictions
            or (
                reference_content
                and deep_result
                and deep_result.get("has_hallucination", False)
            )
        )
        layer1_result["score"] = round(final_score, 2)
        layer1_result["is_hallucination"] = is_hallucination
        layer1_result["review_outcome"] = "hallucination" if is_hallucination else "pending"
        
        if is_hallucination:
            logger.warning(
                f"[幻觉检测] 检出幻觉: score={final_score:.1f}, "
                f"layer={layer1_result['layer']}, keywords={hallucination_points[:5]}"
            )
        
        return is_hallucination, layer1_result

    @staticmethod
    def _split_claims(content: str) -> List[str]:
        fragments = re.split(r"(?:\r?\n+|(?<=[。！？；;])|(?<=[.!?])\s+)", content)
        claims = []
        for fragment in fragments:
            claim = re.sub(r"^\s*(?:[-*•]|\d+[.)])\s*", "", fragment).strip()
            if claim and len(re.sub(r"[^\w\u4e00-\u9fff]", "", claim)) >= 4:
                claims.append(claim)
        return claims or [content.strip()]

    @staticmethod
    def _extract_entities(claim: str) -> List[str]:
        matches = re.finditer(
            r"\b[A-Z][A-Za-z0-9_-]{2,}\b|\b\d+(?:\.\d+)?%?\b|[《“「\"][^》”」\"]{2,30}[》”」\"]|[\u4e00-\u9fff]{2,12}",
            claim,
        )
        entities = [match.group(0).strip('《》“”「」\"') for match in matches]
        seen = set()
        result = []
        for entity in entities:
            key = entity.lower()
            if key not in seen:
                seen.add(key)
                result.append(entity)
        return result

    @staticmethod
    def _similarity(candidate: Dict[str, Any]) -> float:
        try:
            value = float(candidate.get("similarity", 0.0))
        except (TypeError, ValueError):
            return 0.0
        return max(0.0, min(1.0, value))

    @staticmethod
    def _entity_overlap(entities: List[str], candidate: Dict[str, Any]) -> List[str]:
        haystack = str(candidate.get("content", "")).lower()
        return [entity for entity in entities if entity.lower() in haystack]

    @staticmethod
    def _normalize_numeric_facts(text: str) -> List[Dict[str, Any]]:
        """Extract numbers with a light-weight entity and relation context."""
        relation_terms = {
            "released": "release",
            "release": "release",
            "published": "release",
            "founded": "founded",
            "introduced": "introduced",
            "version": "version",
            "版本": "version",
            "发布": "release",
            "上线": "release",
            "成立": "founded",
            "引入": "introduced",
        }
        value_pattern = re.compile(r"(?P<raw>v?\d+(?:\.\d+){0,2})(?P<unit>%|kg|千克|公斤|mm|毫米|μm|微米)?", re.I)
        entities = HallucinationUtil._extract_entities(text)
        facts = []
        for match in value_pattern.finditer(str(text or "")):
            raw = match.group("raw")
            unit = (match.group("unit") or "").lower()
            normalized_raw = raw.lstrip("vV")
            parts = normalized_raw.split(".")
            if len(parts) >= 2 and raw.lower().startswith("v"):
                kind = "version"
            elif len(parts) >= 2 and 1900 <= float(normalized_raw) <= 2099:
                kind = "year"
            elif len(parts) >= 2 and "版本" in str(text[max(0, match.start() - 8):match.end() + 8]):
                kind = "version"
            elif len(parts) >= 2 and len(parts) <= 3 and any(
                term in str(text[max(0, match.start() - 16):match.end() + 16]).lower()
                for term in ("python", "api", "协议", "型号")
            ):
                kind = "version"
            elif len(parts) == 1 and 1900 <= float(normalized_raw) <= 2099:
                kind = "year"
            else:
                kind = "number"

            window = str(text[max(0, match.start() - 32):match.end() + 32]).lower()
            relation = next(
                (normalized for term, normalized in relation_terms.items() if term in window),
                "",
            )
            nearby_entities = [
                entity
                for entity in entities
                if entity.lower() != raw.lower()
                and entity.lower() in window
                and not re.fullmatch(r"v?\d+(?:\.\d+){0,2}%?", entity, flags=re.I)
            ]
            try:
                value = float(normalized_raw)
            except ValueError:
                continue
            facts.append({
                "value": value,
                "raw": raw,
                "kind": kind,
                "unit": unit,
                "relation": relation,
                "entities": nearby_entities,
            })
        return facts

    @staticmethod
    def _claim_conflict(claim: str, candidate: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """Detect a conflict only when both numbers describe the same fact."""
        reference = str(candidate.get("content", ""))
        claim_facts = HallucinationUtil._normalize_numeric_facts(claim)
        reference_facts = HallucinationUtil._normalize_numeric_facts(reference)
        for claim_fact in claim_facts:
            for reference_fact in reference_facts:
                if claim_fact["kind"] != reference_fact["kind"]:
                    continue
                if claim_fact["unit"] != reference_fact["unit"]:
                    continue
                shared_entities = set(entity.lower() for entity in claim_fact["entities"]) & set(
                    entity.lower() for entity in reference_fact["entities"]
                )
                # A shared relation such as "released" is not enough: two
                # different products can share the same relation while
                # carrying unrelated values. Require a shared entity before
                # treating a numeric fact as contradictory.
                if not shared_entities:
                    continue
                if claim_fact["value"] == reference_fact["value"]:
                    continue
                conflict_type = "version_conflict" if claim_fact["kind"] == "version" else "numeric_conflict"
                return {
                    "type": conflict_type,
                    "claim_value": claim_fact["raw"],
                    "reference_value": reference_fact["raw"],
                }
        return None

    @staticmethod
    def _citation(candidate: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        title = str(candidate.get("title", "")).strip()
        paragraph = candidate.get("paragraph", candidate.get("slice_index"))
        if not title or paragraph is None:
            return None
        try:
            paragraph = int(paragraph) + (0 if candidate.get("paragraph") is not None else 1)
        except (TypeError, ValueError):
            return None
        return {
            "label": f"[{title}-Paragraph {paragraph}]",
            "title": title,
            "paragraph": paragraph,
            "doc_id": candidate.get("doc_id"),
            "slice_id": candidate.get("slice_id"),
        }

    @staticmethod
    def _knowledge_gap(claims: List[str], entities: List[str]) -> Dict[str, Any]:
        attributes = []
        for claim in claims:
            attributes.extend(re.findall(r"\b(?:supports?|has|contains?|uses?|adds?|released?)\s+([\w-]+)", claim, flags=re.I))
            attributes.extend(re.findall(r"(?:支持|包含|使用|新增|发布)([\u4e00-\u9fffA-Za-z0-9_-]{1,12})", claim))
        return {
            "present": bool(claims),
            "claims": claims,
            "entities": list(dict.fromkeys(entities)),
            "attributes": list(dict.fromkeys(attributes)),
            "upload_prompt": "上传相关资料以提升证据覆盖率。",
        }

    @staticmethod
    def _detect_against_knowledge(content: str, reference_knowledge: List[Dict]) -> Tuple[bool, Dict[str, Any]]:
        claims = HallucinationUtil._split_claims(content)
        candidates = [item for item in (reference_knowledge or []) if isinstance(item, dict)]
        reference_text = "\n".join(str(item.get("content", "")) for item in candidates)
        industry_result = IndustrialRoboticsRules.evaluate(content, reference_text)
        claim_results = []
        citations = []
        contradictions = []

        for claim in claims:
            entities = HallucinationUtil._extract_entities(claim)
            ranked = sorted(
                candidates,
                key=lambda item: (HallucinationUtil._similarity(item), len(HallucinationUtil._entity_overlap(entities, item))),
                reverse=True,
            )
            candidate = ranked[0] if ranked else None
            similarity = HallucinationUtil._similarity(candidate) if candidate else 0.0
            overlap = HallucinationUtil._entity_overlap(entities, candidate) if candidate else []
            conflict = HallucinationUtil._claim_conflict(claim, candidate) if candidate else None
            citation = HallucinationUtil._citation(candidate) if candidate and similarity >= HallucinationUtil.WEAK_RELEVANCE_THRESHOLD else None

            if conflict:
                status = "contradicted"
                reason = "The claim conflicts with a retrieved knowledge-base value."
                contradictions.append({**conflict, "claim": claim})
            elif similarity >= HallucinationUtil.STRONG_RELEVANCE_THRESHOLD:
                status = "supported"
                reason = "A strongly relevant knowledge-base slice supports this claim."
            elif similarity >= HallucinationUtil.WEAK_RELEVANCE_THRESHOLD or overlap:
                status = "weak_support"
                reason = "Only background evidence or an entity match was found."
            else:
                status = "insufficient_evidence"
                reason = "No sufficiently relevant knowledge-base evidence was found."

            claim_citations = [citation["label"]] if citation and status == "supported" else []
            if citation and status == "supported" and citation not in citations:
                citations.append(citation)
            claim_results.append({
                "text": claim,
                "status": status,
                "similarity": similarity if candidate else None,
                "entities": entities,
                "citations": claim_citations,
                "reason": reason,
            })

        gaps = [item["text"] for item in claim_results if item["status"] == "insufficient_evidence"]
        gap_entities = [entity for item in claim_results if item["status"] == "insufficient_evidence" for entity in item["entities"]]
        if gaps:
            message = "[EVIDENCE_GAP] No sufficiently relevant knowledge-base evidence for claims: " + " | ".join(gaps[:3])
            logger.warning(message)
            logging.getLogger(__name__).warning(message)

        supported = sum(item["status"] in {"supported", "weak_support"} for item in claim_results)
        strong = bool(claim_results) and all(item["status"] == "supported" for item in claim_results)
        has_weak = any(item["status"] == "weak_support" for item in claim_results)
        has_evidence = supported > 0
        if not has_evidence:
            credibility = "no_evidence"
        elif strong:
            credibility = "high"
        elif has_weak and not gaps:
            credibility = "medium"
        else:
            credibility = "low"

        evidence_coverage = supported / len(claim_results) if claim_results else 0.0
        industry_high_risk = [
            item for item in industry_result["issues"] if item.get("severity") == "high"
        ]
        detected = bool(contradictions or industry_high_risk)
        risk_flags = [
            {**item, "severity": item.get("severity", "high")}
            for item in contradictions
        ] + list(industry_result["issues"])
        industry_score = sum(
            {"high": 60, "medium": 15, "low": 5}.get(item.get("severity", "low"), 5)
            for item in industry_result["issues"]
        )
        review_outcome = (
            "hallucination"
            if detected
            else "pending"
            if gaps or has_weak or not strong
            else "clean"
        )
        evidence_status = "sufficient" if claim_results and not gaps and not has_weak else "gap"
        info = {
            "is_hallucination": detected,
            "score": round(min(100.0, len(contradictions) * 80.0 + len(gaps) * 10.0 + industry_score), 2),
            "threshold": settings.HALLUCINATION_THRESHOLD,
            "confidence": round(evidence_coverage if not contradictions else 0.9, 3),
            "credibility": credibility,
            "evidence_coverage": round(evidence_coverage, 3),
            "method": "knowledge_grounded" if candidates else "knowledge_gap",
            "evidence_status": evidence_status,
            "review_outcome": review_outcome,
            "review_source": "knowledge_grounded" if candidates else "knowledge_gap",
            "risk_flags": risk_flags,
            "claims": claim_results,
            "citations": citations,
            "knowledge_gap": HallucinationUtil._knowledge_gap(gaps, gap_entities),
            "detected_keywords": [],
            "contradictions": contradictions,
            "industry_rules": industry_result,
            "layer": "knowledge",
        }
        return detected, info

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
        if not LLMUtil.is_available():
            return None
        
        # 缓存key（内容+参考前200字的哈希摘要简化）
        import hashlib
        ref_excerpt = (reference_content or "")[:200]
        cache_key = hashlib.md5(
            (content[:500] + "||" + ref_excerpt).encode("utf-8"),
            usedforsecurity=False,
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
            
            response_text, _ = AIContentService.sync_call(
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
                weight = {
                    "fake_markers": 15,
                    "over_confident": 10,
                    "ambiguous": 1,
                    "contradiction": 1,
                }.get(category, 5)

                index = content.find(kw)
                while index != -1:
                    if category == "over_confident" and HallucinationUtil._is_harmless_overconfident_context(content, kw, index):
                        index = content.find(kw, index + len(kw))
                        continue

                    detected.append(kw)
                    score += weight
                    break
        
        return score, detected

    @staticmethod
    def _is_negated_keyword(content: str, keyword: str) -> bool:
        negation_markers = ("不", "无", "没有", "并非", "并不", "未必", "非")
        start = 0
        while True:
            index = content.find(keyword, start)
            if index == -1:
                return False
            prefix = content[max(0, index - 6):index]
            if any(marker in prefix for marker in negation_markers):
                return True
            start = index + len(keyword)

    @staticmethod
    def _is_harmless_overconfident_context(content: str, keyword: str, index: int) -> bool:
        local_window = content[max(0, index - 4): min(len(content), index + len(keyword) + 6)]

        line_start = content.rfind("\n", 0, index) + 1
        line_end = content.find("\n", index)
        if line_end == -1:
            line_end = len(content)
        current_line = content[line_start:line_end].strip()
        if re.match(r"^-\s*[A-D][.．、]", current_line):
            return True

        if keyword == "绝对":
            harmless_phrases = (
                "绝对值",
                "绝对误差",
                "绝对位置",
                "绝对位置编码",
                "绝对坐标",
                "绝对路径",
            )
            if any(phrase in local_window for phrase in harmless_phrases):
                return True

        if keyword == "一定":
            harmless_phrases = (
                "不一定",
                "并不一定",
                "并非一定",
                "未必一定",
                "一定程度",
                "一定要",
                "一定的",
                "有一定",
                "一定帮助",
            )
            if any(phrase in local_window for phrase in harmless_phrases):
                return True

        return HallucinationUtil._is_negated_keyword(local_window, keyword)

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
                content, ref, reference_knowledge=[], use_deep_check=use_deep_check,
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
