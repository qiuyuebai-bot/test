"""Industry-specific grounding rules for industrial robotics content."""

import re
from typing import Any, Dict, List, Set


class IndustrialRoboticsRules:
    """Small, auditable rule pack for common robotics training concepts."""

    TOPICS = {
        "coordinate_system": ("机器人坐标系", "笛卡尔坐标", "关节坐标", "世界坐标", "坐标变换"),
        "tool_tcp": ("工具坐标", "工具中心点", "TCP", "工具坐标系"),
        "base_coordinate": ("基坐标", "基坐标系", "用户坐标", "用户坐标系"),
        "payload": ("负载", "有效载荷", "额定载荷", "payload"),
        "repeatability": ("重复定位精度", "重复精度", "定位精度"),
        "safety": ("安全规范", "安全围栏", "急停", "安全回路", "ISO 10218", "ISO/TS 15066"),
        "maintenance": ("减速机保养", "设备维护", "润滑", "保养周期", "维护"),
    }

    @classmethod
    def topics(cls, text: str) -> Set[str]:
        value = str(text or "").casefold()
        return {
            topic
            for topic, terms in cls.TOPICS.items()
            if any(str(term).casefold() in value for term in terms)
        }

    @classmethod
    def evaluate(cls, content: str, reference_content: str = "") -> Dict[str, Any]:
        content_topics = cls.topics(content)
        reference_topics = cls.topics(reference_content)
        issues: List[Dict[str, Any]] = []

        coordinate_topics = {"coordinate_system", "tool_tcp", "base_coordinate"}
        if content_topics & coordinate_topics and "maintenance" in reference_topics and not (
            reference_topics & coordinate_topics
        ):
            issues.append({
                "type": "industry_topic_confusion",
                "severity": "high",
                "domain": "industrial_robotics",
                "description": "生成内容讨论机器人坐标/TCP，但参考资料仅覆盖设备维护主题。",
                "content_topics": sorted(content_topics),
                "reference_topics": sorted(reference_topics),
            })
        elif "maintenance" in content_topics and reference_topics & coordinate_topics and not (
            reference_topics & {"maintenance"}
        ):
            issues.append({
                "type": "industry_topic_confusion",
                "severity": "high",
                "domain": "industrial_robotics",
                "description": "生成内容讨论设备维护，但参考资料仅覆盖坐标/TCP主题。",
                "content_topics": sorted(content_topics),
                "reference_topics": sorted(reference_topics),
            })

        if "payload" in content_topics and re.search(r"负载|有效载荷|payload", content, re.I):
            if not re.search(r"\d+(?:\.\d+)?\s*(?:kg|千克|公斤|n|牛顿)", content, re.I):
                issues.append({
                    "type": "industry_unit_missing",
                    "severity": "medium",
                    "domain": "industrial_robotics",
                    "description": "负载表述缺少可核查的质量或力单位。",
                })

        if "repeatability" in content_topics:
            if not re.search(r"\d+(?:\.\d+)?\s*(?:mm|毫米|μm|微米)", content, re.I):
                issues.append({
                    "type": "industry_unit_missing",
                    "severity": "low",
                    "domain": "industrial_robotics",
                    "description": "重复定位精度表述缺少毫米或微米单位。",
                })

        if "safety" in content_topics and re.search(r"无需急停|可以跳过安全|不必设置围栏|绝对安全", content):
            issues.append({
                "type": "industry_safety_violation",
                "severity": "high",
                "domain": "industrial_robotics",
                "description": "内容包含可能导致跳过安全控制的表述。",
            })

        return {
            "domain": "industrial_robotics",
            "content_topics": sorted(content_topics),
            "reference_topics": sorted(reference_topics),
            "issues": issues,
        }

    @classmethod
    def terms_missing_from_reference(
        cls, content: str, reference_content: str
    ) -> List[Dict[str, str]]:
        """Return domain terms used by content but absent from its evidence."""
        if not reference_content:
            return []
        ref = str(reference_content).casefold()
        missing = []
        for topic, terms in cls.TOPICS.items():
            used = [term for term in terms if str(term).casefold() in str(content or "").casefold()]
            if used and not any(str(term).casefold() in ref for term in terms):
                missing.append({"topic": topic, "terms": ", ".join(used)})
        return missing
