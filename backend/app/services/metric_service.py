"""Unified metric calculation, policy, and result service.

Calculators only read business facts and produce numerator/denominator/value.
Policies own applicability, sample gates, freshness, and error states.
"""

from datetime import datetime, timedelta
from typing import Any, Dict, Iterable, Optional

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
            LearningResource.match_score.isnot(None)
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
        query = db.query(AnswerRecord).filter(
            AnswerRecord.next_resource_id.isnot(None),
        )
        learner_id = cls._scope_learner_id(scope, scope_id)
        if learner_id is not None:
            query = query.filter(AnswerRecord.learner_id == learner_id)

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
        query = db.query(AnswerRecord)
        learner_id = cls._scope_learner_id(scope, scope_id)
        if learner_id is not None:
            query = query.filter(AnswerRecord.learner_id == learner_id)

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
        evaluated = details["evaluated_checks"]
        total_checks = details["total_checks"]
        return {
            "numerator": details["confirmed_hallucinations"],
            "denominator": evaluated,
            "sample_count": evaluated,
            "value": details["hallucination_rate"],
            "has_data": total_checks > 0,
            "message": "Evidence reviews are still below the minimum sample size"
            if total_checks > 0 and evaluated < details["minimum_sample_size"]
            else None,
            "metadata": {
                "total_checks": total_checks,
                "evaluated_checks": evaluated,
                "pending_checks": details["pending_checks"],
                "confirmed_hallucinations": details["confirmed_hallucinations"],
                "evidence_gaps": details["evidence_gaps"],
                "pass_rate": details["pass_rate"],
            },
        }

    @classmethod
    def calculate(
        cls, metric_id: str, db: Session, scope: str, scope_id: int | None
    ) -> Dict[str, Any]:
        calculators = {
            "resource_match_score": cls.resource_match_score,
            "resource_match_effectiveness": cls.resource_match_effectiveness,
            "knowledge_index_coverage": cls.knowledge_index_coverage,
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
