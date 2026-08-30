"""Unified metric calculation, policy, and result service.

Calculators only read business facts and produce numerator/denominator/value.
Policies own applicability, sample gates, freshness, and error states.
"""

import json
from datetime import datetime, timedelta
from typing import Any, Dict, Iterable, Optional

from sqlalchemy import or_
from sqlalchemy.orm import Session

from app.models import (
    AgentTask,
    AnswerRecord,
    DebateRecord,
    KnowledgeSlice,
    LearnerProfile,
    LearningResource,
    TestMetrics,
)
from app.utils.datetime import utcnow_naive
from app.utils.metrics import MetricsUtil
from app.utils.resource_content import normalize_source_keywords

from .metric_registry import (
    METRIC_REGISTRY,
    MetricDefinition,
    get_metric_definition,
    normalize_scope,
    serialize_metric_definitions,
)


class MetricCalculator:
    """Calculate raw metric facts without deciding how they should be displayed."""

    COMPLETED_ANSWER_RESULTS = {"correct", "wrong", "partial"}

    # 诊断会话（能力摸底）不反映学习效果，学习效果指标口径排除之
    DIAGNOSTIC_SESSION_PREFIX = "diag_"

    @classmethod
    def _practice_answer_query(cls, db: Session, scope: str, scope_id: int | None):
        query = db.query(AnswerRecord).filter(
            or_(
                AnswerRecord.session_id.is_(None),
                ~AnswerRecord.session_id.like(f"{cls.DIAGNOSTIC_SESSION_PREFIX}%"),
            )
        )
        learner_id = cls._scope_learner_id(scope, scope_id)
        if learner_id is not None:
            query = query.filter(AnswerRecord.learner_id == learner_id)
        return query

    @staticmethod
    def _enum_value(value: Any) -> Any:
        return getattr(value, "value", value)

    @classmethod
    def _scope_learner_id(cls, scope: str, scope_id: int | None) -> int | None:
        return scope_id if scope == "learner" else None

    @classmethod
    def resource_match_score(
        cls, db: Session, scope: str, scope_id: int | None
    ) -> Dict[str, Any]:
        query = db.query(LearningResource.match_score).filter(
            LearningResource.match_score.isnot(None),
            LearningResource.is_enabled.is_(True),
        )
        learner_id = cls._scope_learner_id(scope, scope_id)
        if learner_id is not None:
            query = query.filter(LearningResource.learner_id == learner_id)

        scores = []
        for (raw_score,) in query.all():
            try:
                score = float(raw_score)
            except (TypeError, ValueError):
                continue
            scores.append(score * 100 if 0 <= score <= 1 else score)

        denominator = len(scores)
        numerator = round(sum(scores), 2)
        return {
            "numerator": numerator,
            "denominator": denominator,
            "sample_count": denominator,
            "value": round(numerator / denominator, 2) if denominator else None,
            "has_data": denominator > 0,
        }

    @classmethod
    def resource_match_effectiveness(
        cls, db: Session, scope: str, scope_id: int | None
    ) -> Dict[str, Any]:
        """推荐资源关联的"下一次答题"正确率。

        触发集 = 练习口径（排除诊断会话）且带 next_resource_id 的答题记录；
        对每条触发记录，取同一学习者按 id 顺序的下一条答题记录（可以是练习
        下一题，也可以是随后再测/摸底的首题），统计该记录的判分结果。
        """
        learner_id = cls._scope_learner_id(scope, scope_id)
        rows_query = db.query(
            AnswerRecord.id,
            AnswerRecord.learner_id,
            AnswerRecord.result,
            AnswerRecord.session_id,
            AnswerRecord.next_resource_id,
        ).order_by(AnswerRecord.learner_id, AnswerRecord.id)
        if learner_id is not None:
            rows_query = rows_query.filter(AnswerRecord.learner_id == learner_id)
        rows = rows_query.all()

        numerator = denominator = 0
        total = len(rows)
        for index, row in enumerate(rows):
            if row.next_resource_id is None:
                continue
            if row.session_id and str(row.session_id).startswith(cls.DIAGNOSTIC_SESSION_PREFIX):
                continue
            if index + 1 >= total or rows[index + 1].learner_id != row.learner_id:
                continue
            next_result = cls._enum_value(rows[index + 1].result)
            if next_result in cls.COMPLETED_ANSWER_RESULTS:
                denominator += 1
                if next_result == "correct":
                    numerator += 1

        return {
            "numerator": numerator,
            "denominator": denominator,
            "sample_count": denominator,
            "value": round(numerator / denominator * 100, 2) if denominator else None,
            "has_data": denominator > 0,
        }

    @classmethod
    def knowledge_index_coverage(
        cls, db: Session, scope: str, scope_id: int | None
    ) -> Dict[str, Any]:
        # Knowledge slices are global facts.  A learner scope still receives
        # the same index health because the index is shared by all learners.
        total = db.query(KnowledgeSlice).count()
        indexed = db.query(KnowledgeSlice).filter(KnowledgeSlice.is_indexed == True).count()
        return {
            "numerator": indexed,
            "denominator": total,
            "sample_count": total,
            "value": round(indexed / total * 100, 2) if total else None,
            "has_data": total > 0,
            "metadata": {
                "coverage_type": "index",
                "definition": "indexed knowledge slices / total knowledge slices",
                "warning": (
                    "This is vector-index coverage, not generated-content knowledge-point coverage"
                ),
            },
        }

    @classmethod
    def generated_content_coverage(
        cls, db: Session, scope: str, scope_id: int | None
    ) -> Dict[str, Any]:
        """Measure coverage of source slices by persisted generated content."""
        query = db.query(LearningResource).filter(
            LearningResource.status == "ready",
            LearningResource.validation_passed.is_(True),
        )
        learner_id = cls._scope_learner_id(scope, scope_id)
        if learner_id is not None:
            query = query.filter(LearningResource.learner_id == learner_id)

        resources = query.all()
        source_ids: set[int] = set()
        resource_sources: list[tuple[LearningResource, list[int]]] = []
        for resource in resources:
            raw_ids = resource.source_slice_ids or []
            if isinstance(raw_ids, str):
                try:
                    raw_ids = json.loads(raw_ids)
                except (TypeError, ValueError, json.JSONDecodeError):
                    raw_ids = []
            ids = []
            for value in raw_ids if isinstance(raw_ids, list) else []:
                try:
                    ids.append(int(value))
                except (TypeError, ValueError):
                    continue
            if ids:
                source_ids.update(ids)
                resource_sources.append((resource, ids))

        if not source_ids:
            return {
                "numerator": 0,
                "denominator": 0,
                "sample_count": len(resources),
                "value": None,
                "has_data": False,
                "metadata": {"coverage_type": "generated_content", "resources_evaluated": 0},
            }

        slices = {
            item.id: item
            for item in db.query(KnowledgeSlice).filter(KnowledgeSlice.id.in_(source_ids)).all()
        }
        covered = 0
        denominator = 0
        for resource, ids in resource_sources:
            content = str(resource.content or "").casefold()
            for slice_id in ids:
                source_slice = slices.get(slice_id)
                if not source_slice:
                    continue
                denominator += 1
                keywords = [
                    item.casefold()
                    for item in normalize_source_keywords(
                        source_slice.keywords,
                        title=source_slice.title,
                        content=source_slice.content,
                    )
                    if item.strip()
                ]
                if any(keyword in content for keyword in keywords):
                    covered += 1

        return {
            "numerator": covered,
            "denominator": denominator,
            "sample_count": len(resource_sources),
            "value": round(covered / denominator * 100, 2) if denominator else None,
            "has_data": denominator > 0,
            "metadata": {
                "coverage_type": "generated_content",
                "resources_evaluated": len(resource_sources),
                "source_slice_count": len(source_ids),
                "definition": "source slices referenced by ready resources and represented in resource content",
            },
        }

    @classmethod
    def blind_spot_resource_coverage(
        cls, db: Session, scope: str, scope_id: int | None
    ) -> Dict[str, Any]:
        if scope == "learner":
            profiles: Iterable[LearnerProfile] = db.query(LearnerProfile).filter(
                LearnerProfile.id == scope_id
            ).all()
        else:
            profiles = db.query(LearnerProfile).all()

        profiles = list(profiles)
        if not profiles:
            return {
                "numerator": 0,
                "denominator": 0,
                "sample_count": 0,
                "value": None,
                "applicable": True,
                "has_data": False,
            }

        resources_query = db.query(
            LearningResource.learner_id,
            LearningResource.content,
            LearningResource.knowledge_topic,
            LearningResource.keywords,
        )
        if scope == "learner":
            resources_query = resources_query.filter(LearningResource.learner_id == scope_id)
        resources_by_learner: Dict[int, list[str]] = {}
        for learner_id, content, topic, keywords in resources_query.all():
            parts = [content or "", topic or ""]
            if isinstance(keywords, list):
                parts.extend(str(item) for item in keywords)
            resources_by_learner.setdefault(learner_id, []).append(" ".join(parts).lower())

        areas: list[tuple[int, str]] = []
        for profile in profiles:
            raw_areas = profile.knowledge_blind_areas or []
            if isinstance(raw_areas, str):
                raw_areas = [raw_areas]
            areas.extend(
                (profile.id, str(area).strip())
                for area in raw_areas
                if str(area).strip()
            )

        if not areas:
            return {
                "numerator": 0,
                "denominator": 0,
                "sample_count": 0,
                "value": None,
                "applicable": False,
                "has_data": True,
                "message": "No identified blind spots",
            }

        covered = sum(
            any(area.lower() in content for content in resources_by_learner.get(learner_id, []))
            for learner_id, area in areas
        )
        resource_count = sum(len(resources_by_learner.get(profile.id, [])) for profile in profiles)
        return {
            "numerator": covered,
            "denominator": len(areas),
            "sample_count": resource_count,
            "value": round(covered / len(areas) * 100, 2),
            # Identified blind spots are facts even before a resource exists;
            # policy then reports the metric as collecting instead of no_data.
            "has_data": True,
            "message": "Blind spots identified; resources are still being collected"
            if resource_count == 0
            else None,
        }

    @classmethod
    def answer_accuracy(
        cls, db: Session, scope: str, scope_id: int | None
    ) -> Dict[str, Any]:
        query = cls._practice_answer_query(db, scope, scope_id)

        completed = []
        for record in query.all():
            result = cls._enum_value(record.result)
            if result in cls.COMPLETED_ANSWER_RESULTS:
                completed.append(result)
        denominator = len(completed)
        numerator = sum(result == "correct" for result in completed)
        return {
            "numerator": numerator,
            "denominator": denominator,
            "sample_count": denominator,
            "value": round(numerator / denominator * 100, 2) if denominator else None,
            "has_data": denominator > 0,
        }

    @classmethod
    def hallucination_rate(
        cls, db: Session, scope: str, scope_id: int | None
    ) -> Dict[str, Any]:
        details = MetricsUtil.calculate_hallucination_metrics(
            db,
            learner_id=scope_id if scope == "learner" else None,
        )
        rolling = MetricsUtil.calculate_hallucination_metrics(
            db,
            learner_id=scope_id if scope == "learner" else None,
            window_days=MetricsUtil.RECENT_WINDOW_DAYS,
        )
        evaluated = details["evaluated_checks"]
        total_checks = details["total_checks"]
        metadata = {
            key: details[key]
            for key in (
                "total_checks",
                "evaluated_checks",
                "pending_checks",
                "confirmed_hallucinations",
                "evidence_gaps",
                "invalid_records",
                "state_counts",
                "high_risk_checks",
                "high_risk_reviewed",
                "high_risk_review_coverage",
                "pass_rate",
                "policy_version",
                "formal_minimum_sample_size",
                "target_percent",
            )
        }
        metadata.update({
            "operator": "<",
            "rolling_30d": rolling,
        })
        return {
            "numerator": details["confirmed_hallucinations"],
            "denominator": evaluated,
            "sample_count": evaluated,
            "value": details["hallucination_rate"],
            "has_data": total_checks > 0,
            "message": "Evidence reviews are still below the minimum sample size"
            if total_checks > 0 and evaluated < details["minimum_sample_size"]
            else None,
            "metadata": metadata,
        }

    @classmethod
    def calculate(
        cls, metric_id: str, db: Session, scope: str, scope_id: int | None
    ) -> Dict[str, Any]:
        calculators = {
            "resource_match_score": cls.resource_match_score,
            "resource_match_effectiveness": cls.resource_match_effectiveness,
            "knowledge_index_coverage": cls.knowledge_index_coverage,
            "generated_content_coverage": cls.generated_content_coverage,
            "blind_spot_resource_coverage": cls.blind_spot_resource_coverage,
            "answer_accuracy": cls.answer_accuracy,
            "hallucination_rate": cls.hallucination_rate,
        }
        return calculators[metric_id](db, scope, scope_id)


class MetricPolicy:
    """Apply reporting policy after facts have been calculated."""

    @staticmethod
    def apply(
        definition: MetricDefinition,
        facts: Dict[str, Any],
        *,
        scope: str,
        scope_id: int | None,
        calculated_at: datetime,
        error: str | None = None,
        now: datetime | None = None,
    ) -> Dict[str, Any]:
        value = facts.get("value")
        numerator = facts.get("numerator", 0)
        denominator = facts.get("denominator", 0)
        sample_count = facts.get("sample_count", 0)
        metadata = facts.get("metadata")
        message = facts.get("message")

        if error:
            status = "error"
            value = None
            message = "Metric calculation failed"
        elif facts.get("applicable") is False:
            status = "not_applicable"
            value = None
            message = message or "Metric is not applicable to this scope"
        elif facts.get("has_data") is not True:
            status = "no_data"
            value = None
            message = message or "No data available"
        elif sample_count < definition.minimum_sample_size:
            status = "collecting"
            value = None
            message = message or (
                f"{sample_count} samples collected; {definition.minimum_sample_size} required"
            )
        else:
            status = "ready"
            if value is None:
                status = "error"
                message = message or "Metric value is unavailable"

        if (
            status == "ready"
            and definition.freshness_seconds is not None
            and now is not None
            and calculated_at < now - timedelta(seconds=definition.freshness_seconds)
        ):
            status = "stale"
            value = None
            message = "Metric snapshot is stale"

        return {
            "metric_id": definition.metric_id,
            "display_name": definition.display_name,
            "scope": scope,
            "scope_id": scope_id,
            "value": round(float(value), 2) if isinstance(value, (int, float)) else value,
            "unit": definition.unit,
            "status": status,
            "numerator": numerator,
            "denominator": denominator,
            "sample_count": sample_count,
            "minimum_sample_size": definition.minimum_sample_size,
            "formula": definition.formula,
            "source": list(definition.source),
            "calculated_at": calculated_at.isoformat(),
            "message": message,
            "metadata": metadata,
        }


class MetricService:
    """Single entry point for real-time metrics and daily snapshots."""

    @classmethod
    def calculate_metrics(
        cls,
        db: Session,
        *,
        scope: str = "global",
        scope_id: int | None = None,
        metric_ids: Optional[Iterable[str]] = None,
        calculated_at: datetime | None = None,
        now: datetime | None = None,
    ) -> list[dict]:
        normalized_scope = normalize_scope(scope)
        if normalized_scope not in ("global", "learner"):
            raise ValueError(f"Unsupported metric scope: {scope}")
        if normalized_scope == "learner" and scope_id is None:
            raise ValueError("learner scope requires scope_id")

        calculated_at = calculated_at or utcnow_naive()
        selected = list(metric_ids or METRIC_REGISTRY.keys())
        results = []
        for metric_id in selected:
            definition = get_metric_definition(metric_id)
            if normalized_scope not in definition.scopes:
                continue
            error = None
            try:
                facts = MetricCalculator.calculate(metric_id, db, normalized_scope, scope_id)
            except Exception as exc:  # Keep one broken metric from hiding the others.
                facts = {}
                error = str(exc)
            results.append(
                MetricPolicy.apply(
                    definition,
                    facts,
                    scope=normalized_scope,
                    scope_id=scope_id,
                    calculated_at=calculated_at,
                    now=now,
                    error=error,
                )
            )
        return results

    @classmethod
    def registry(cls) -> list[dict]:
        return serialize_metric_definitions()

    @staticmethod
    def by_id(results: Iterable[dict]) -> dict[str, dict]:
        return {result["metric_id"]: result for result in results}

    @classmethod
    def persist_daily_snapshot(cls, db: Session, results: list[dict]) -> TestMetrics:
        now = utcnow_naive()
        day_start = now.replace(hour=0, minute=0, second=0, microsecond=0)
        record = (
            db.query(TestMetrics)
            .filter(TestMetrics.record_period == "daily")
            .filter(TestMetrics.record_date >= day_start)
            .filter(TestMetrics.record_date < day_start + timedelta(days=1))
            .order_by(TestMetrics.record_date.desc())
            .first()
        )
        if record is None:
            record = TestMetrics(record_date=day_start, record_period="daily")
            db.add(record)
            db.flush()

        values = cls.by_id(results)
        record.hallucination_rate = values.get("hallucination_rate", {}).get("value")
        record.resource_match_accuracy = values.get("resource_match_score", {}).get("value")
        record.knowledge_coverage_rate = values.get("knowledge_index_coverage", {}).get("value")
        record.detailed_metrics = {
            "metric_results": results,
            "snapshot_calculated_at": now.isoformat(),
        }
        db.commit()
        db.refresh(record)
        return record
