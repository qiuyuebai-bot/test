"""讲义增量增补：答错触发的新盲区章节生成与追加。

与 full_pipeline 的关系：full_pipeline 负责初始生成（诊断→检索→生成→审核→辩论）；
增量增补只处理"学习者已有讲义、答题暴露出讲义未覆盖的新盲区"这一增量场景——
检索该盲区知识 → 生成补充章节 → 落地校验 → 追加到现有讲义并记录版本溯源。
资源 ID 保持不变，答题记录/推荐中的引用不受影响。
"""

from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional, Tuple

from loguru import logger

from app.database import get_db_context
from app.models import AgentTask, LearnerProfile, LearningResource
from app.domains.knowledge.service import KnowledgeService
from app.services.ai_content_service import AIContentService
from app.utils.resource_content import build_source_references, calculate_source_coverage

# 同一学习者两次增补的最小间隔；防止连续答错触发生成风暴
COOLDOWN_HOURS = 2
# 触发增补的讲义资源类型（exercise 是题目集，不追加讲解章节）
SUPPLEMENTABLE_RESOURCE_TYPES = ("guide", "lecture")
_ACTIVE_PIPELINE_STATUSES = ("pending", "running")


class LectureSupplementService:
    """为答错的新盲区向现有讲义追加补充章节。"""

    @staticmethod
    def evaluate_trigger(
        learner: LearnerProfile,
        topic: str,
        latest_resource: Optional[LearningResource],
        last_supplement_at: Optional[datetime],
        active_pipeline_exists: bool,
    ) -> Tuple[bool, str]:
        """Pure trigger decision, separated for testability."""
        topic = str(topic or "").strip()
        if not topic:
            return False, "empty_topic"

        blind_areas = learner.knowledge_blind_areas or []
        if any(topic in str(area) for area in blind_areas):
            # 已声明的盲区在初始生成时已通过盲区注入覆盖，重复增补无增益
            return False, "already_declared_blind_area"

        if latest_resource is None:
            # 没有可追加的讲义；初始生成仍由 full_pipeline 负责
            return False, "no_lecture_to_supplement"

        if topic in (latest_resource.content or ""):
            return False, "already_covered_by_lecture"

        if last_supplement_at is not None:
            cooldown_edge = last_supplement_at + timedelta(hours=COOLDOWN_HOURS)
            if datetime.utcnow() < cooldown_edge:
                return False, "cooldown_active"

        if active_pipeline_exists:
            return False, "pipeline_running"

        return True, "triggered"

    @classmethod
    def _load_context(
        cls, learner_id: int, topic: str
    ) -> Tuple[Optional[LearnerProfile], Optional[LearningResource], Optional[datetime], bool]:
        with get_db_context() as db:
            learner = db.query(LearnerProfile).filter(LearnerProfile.id == learner_id).first()
            if not learner:
                return None, None, None, False
            latest_resource = (
                db.query(LearningResource)
                .filter(
                    LearningResource.learner_id == learner_id,
                    LearningResource.is_latest == True,  # noqa: E712
                    LearningResource.is_enabled == True,  # noqa: E712
                    LearningResource.status == "ready",
                    LearningResource.resource_type.in_(SUPPLEMENTABLE_RESOURCE_TYPES),
                )
                .order_by(LearningResource.created_at.desc(), LearningResource.id.desc())
                .first()
            )
            last_supplement_at = None
            if latest_resource is not None:
                supplements = (latest_resource.content_json or {}).get("supplements") or []
                timestamps = [
                    item.get("added_at")
                    for item in supplements
                    if isinstance(item, dict) and item.get("added_at")
                ]
                if timestamps:
                    try:
                        last_supplement_at = max(
                            datetime.fromisoformat(value) for value in timestamps
                        )
                    except (TypeError, ValueError):
                        last_supplement_at = None
            active_pipeline = (
                db.query(AgentTask.id)
                .filter(
                    AgentTask.learner_id == learner_id,
                    AgentTask.task_type == "full_pipeline",
                    AgentTask.status.in_(_ACTIVE_PIPELINE_STATUSES),
                )
                .first()
                is not None
            )
            return learner, latest_resource, last_supplement_at, active_pipeline

    @classmethod
    def run(
        cls,
        learner_id: int,
        topic: str,
        question_summary: str = "",
        difficulty_level: int = 3,
    ) -> Dict[str, Any]:
        """Execute one supplement; callers run this off the request path."""
        # 执行期复检触发条件：入队到执行之间画像/讲义可能已变化
        learner, latest_resource, last_supplement_at, active_pipeline = cls._load_context(
            learner_id, topic
        )
        if learner is None:
            return {"status": "skipped", "reason": "learner_not_found"}
        should, reason = cls.evaluate_trigger(
            learner, topic, latest_resource, last_supplement_at, active_pipeline
        )
        if not should or latest_resource is None:
            logger.info(f"[讲义增补] 跳过: learner={learner_id}, topic={topic}, reason={reason}")
            return {"status": "skipped", "reason": reason}

        with get_db_context() as db:
            kb_results = KnowledgeService.search(
                db=db,
                query=topic,
                industry=learner.target_industry,
                top_k=5,
            )
        if not kb_results:
            logger.info(f"[讲义增补] 无参考切片，拒绝生成: learner={learner_id}, topic={topic}")
            return {"status": "skipped", "reason": "no_knowledge_results"}

        references = build_source_references(kb_results)
        reference_knowledge = "\n\n".join(
            f"【{item.get('title') or item.get('doc_title') or '参考'}】{item.get('content', '')}"
            for item in kb_results[:5]
        )

        try:
            supplement = AIContentService.generate(
                "lecture_supplement",
                {
                    "learner_summary": {
                        "target_industry": learner.target_industry,
                        "preferred_difficulty": learner.preferred_difficulty,
                        "ability_assessments": learner.ability_assessments or {},
                    },
                    "blind_topic": topic,
                    "question_summary": question_summary,
                    "difficulty_level": difficulty_level,
                    "reference_knowledge": reference_knowledge,
                },
            )
        except Exception as exc:
            logger.warning(f"[讲义增补] 章节生成失败: learner={learner_id}, topic={topic}, error={exc}")
            return {"status": "failed", "reason": f"generation_error: {exc}"}

        section_title = supplement.get("section_title") or f"补充：{topic}"
        section_content = supplement.get("section_content") or ""
        section_markdown = f"## {section_title}\n\n{section_content}".strip()
        if not section_content.strip():
            return {"status": "failed", "reason": "empty_section_content"}

        # 落地校验：补充章节必须命中至少一个参考切片的术语，否则视为
        # 未落地内容，宁可不追加也不让幻觉进入讲义
        coverage = calculate_source_coverage(section_markdown, references)
        if int(coverage.get("covered_slice_count", 0) or 0) < 1:
            logger.warning(
                f"[讲义增补] 章节未命中任何参考切片，拒绝追加: "
                f"learner={learner_id}, topic={topic}"
            )
            return {"status": "failed", "reason": "section_not_grounded"}

        return cls._append_section(
            latest_resource.id,
            topic,
            section_markdown,
            references,
            coverage,
        )

    @staticmethod
    def _bump_version(raw_version: Any) -> str:
        try:
            major, minor = str(raw_version or "1.0").split(".")
            return f"{int(major)}.{int(minor) + 1}"
        except (TypeError, ValueError):
            return "1.1"

    @classmethod
    def _append_section(
        cls,
        resource_id: int,
        topic: str,
        section_markdown: str,
        references: List[Dict[str, Any]],
        coverage: Dict[str, Any],
    ) -> Dict[str, Any]:
        with get_db_context() as db:
            resource = (
                db.query(LearningResource)
                .filter(LearningResource.id == resource_id)
                .with_for_update()
                .first()
            )
            if resource is None:
                return {"status": "skipped", "reason": "resource_deleted"}

            # 行锁内复检：并发增补/重生成可能已改变讲义内容
            if topic in (resource.content or ""):
                return {"status": "skipped", "reason": "already_covered_by_lecture"}

            new_version = cls._bump_version(resource.version)
            resource.content = f"{(resource.content or '').rstrip()}\n\n{section_markdown}\n"
            resource.word_count = len(resource.content)
            resource.section_count = int(resource.section_count or 0) + 1
            resource.version = new_version
            resource.version_notes = (
                f"{resource.version_notes + chr(10) if resource.version_notes else ''}"
                f"[{datetime.utcnow().isoformat(timespec='seconds')}] 增补章节：{topic}"
            )
            content_json = dict(resource.content_json or {})
            supplements = list(content_json.get("supplements") or [])
            supplements.append({
                "topic": topic,
                "added_at": datetime.utcnow().isoformat(timespec="seconds"),
                "version": new_version,
                "source_slice_ids": [
                    int(item["slice_id"]) for item in references if item.get("slice_id")
                ],
                "source_doc_ids": sorted({
                    item.get("doc_id") for item in references if item.get("doc_id") is not None
                }),
                "coverage_rate": coverage.get("coverage_rate"),
                "covered_slice_count": coverage.get("covered_slice_count"),
                "trigger": "wrong_answer",
            })
            content_json["supplements"] = supplements
            resource.content_json = content_json
            # 合并来源切片，保证讲义溯源覆盖增补章节
            merged_slice_ids = list(dict.fromkeys(
                list(resource.source_slice_ids or [])
                + [int(item["slice_id"]) for item in references if item.get("slice_id")]
            ))
            resource.source_slice_ids = merged_slice_ids
            db.commit()

        logger.info(
            f"[讲义增补] 已追加: resource={resource_id}, topic={topic}, version={new_version}"
        )
        return {
            "status": "supplemented",
            "resource_id": resource_id,
            "topic": topic,
            "version": new_version,
            "coverage_rate": coverage.get("coverage_rate"),
        }
