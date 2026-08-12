"""Dashboard 聚合查询与引导状态服务。"""

from collections import Counter
from datetime import datetime
from typing import Any, Optional

from sqlalchemy import func
from sqlalchemy.orm import Session

from app.domains.agent.models import AgentTask
from app.domains.learner.models import AnswerRecord, LearnerProfile
from app.domains.learner.service import LearnerService
from app.domains.resource.models import LearningResource
from app.services.common import ResourceServiceHelper
from app.utils.datetime import utcnow_naive

from .models import DashboardGuidanceState


def _iso(value: Optional[datetime]) -> Optional[str]:
    return value.isoformat() if value else None


def serialize_profile(profile: Optional[LearnerProfile]) -> Optional[dict[str, Any]]:
    if profile is None:
        return None
    return {
        "id": profile.id,
        "user_id": profile.user_id,
        "real_name": profile.real_name,
        "education_level": profile.education_level,
        "major": profile.major,
        "current_position": profile.current_position,
        "learning_style": profile.learning_style,
        "preferred_difficulty": profile.preferred_difficulty,
        "daily_study_time": profile.daily_study_time,
        "target_industry": profile.target_industry,
        "target_position": profile.target_position,
        "learning_goal": profile.learning_goal,
        "theoretical_foundation": profile.theoretical_foundation or 0,
        "programming_ability": profile.programming_ability or 0,
        "algorithm_design": profile.algorithm_design or 0,
        "system_architecture": profile.system_architecture or 0,
        "data_analysis": profile.data_analysis or 0,
        "engineering_practice": profile.engineering_practice or 0,
        "average_ability": profile.average_ability,
        "knowledge_blind_areas": profile.knowledge_blind_areas or [],
        "learning_phase": profile.learning_phase or "entry",
        "learning_phase_score": profile.learning_phase_score or 0,
        "consecutive_study_days": profile.consecutive_study_days or 0,
        "total_study_hours": profile.total_study_hours or 0,
        "completion_rate": profile.completion_rate or 0,
        "is_data_anonymized": profile.is_data_anonymized,
        "created_at": _iso(profile.created_at),
        "updated_at": _iso(profile.updated_at),
        "last_active_at": _iso(profile.last_active_at),
    }


def serialize_resource(resource: LearningResource) -> dict[str, Any]:
    return ResourceServiceHelper.format_resource(resource)


def serialize_task(task: AgentTask) -> dict[str, Any]:
    return {
        "task_id": task.id,
        "task_name": task.task_name,
        "task_type": task.task_type,
        "agent_type": task.agent_type,
        "status": task.status,
        "progress": task.progress or 0,
        "flow_stage": task.flow_stage,
        "flow_description": task.flow_description,
        "learner_id": task.learner_id,
        "created_at": _iso(task.created_at),
        "completed_at": _iso(task.completed_at),
        "duration_ms": task.duration_ms or 0,
        "error_message": task.error_message,
    }


def serialize_feedback(record: AnswerRecord) -> dict[str, Any]:
    result = record.result.value if hasattr(record.result, "value") else record.result
    decision = record.agent_decision.value if hasattr(record.agent_decision, "value") else record.agent_decision
    return {
        "record_id": record.id,
        "question_topic": record.question_topic,
        "result": result,
        "score": record.score or 0,
        "feedback_content": record.feedback_content,
        "decision_reason": record.decision_reason,
        "created_at": _iso(record.created_at),
        "agent_decision": decision,
    }


def get_guidance_state(db: Session, user_id: int) -> Optional[DashboardGuidanceState]:
    return (
        db.query(DashboardGuidanceState)
        .filter(DashboardGuidanceState.user_id == user_id)
        .first()
    )


def get_or_create_guidance_state(db: Session, user_id: int) -> DashboardGuidanceState:
    state = get_guidance_state(db, user_id)
    if state is not None:
        return state
    state = DashboardGuidanceState(user_id=user_id)
    db.add(state)
    db.flush()
    return state


def serialize_guidance_state(state: Optional[DashboardGuidanceState]) -> dict[str, Optional[str]]:
    return {
        "onboarding_completed_at": _iso(state.onboarding_completed_at if state else None),
        "dashboard_guidance_dismissed_at": _iso(state.dashboard_guidance_dismissed_at if state else None),
    }


def profile_is_complete(profile: Optional[LearnerProfile]) -> bool:
    if profile is None:
        return False
    return all((profile.real_name, profile.education_level, profile.major))


def get_guidance_stage(
    profile: Optional[LearnerProfile],
    diagnosis_count: int,
    resource_count: int,
    answer_count: int,
) -> str:
    if not profile_is_complete(profile):
        return "profile"
    if diagnosis_count == 0:
        return "diagnosis"
    if resource_count == 0:
        return "resource"
    if answer_count == 0:
        return "guidance"
    return "feedback"


def _learner_dashboard_payload(
    db: Session,
    profile: Optional[LearnerProfile],
    user_id: int,
) -> dict[str, Any]:
    state = get_guidance_state(db, user_id)
    if profile is None:
        return {
            "profile": None,
            "summary": None,
            "recent_resources": [],
            "current_tasks": [],
            "recent_feedback": [],
            "facts": {
                "has_diagnosis": False,
                "resource_count": 0,
                "answer_count": 0,
                "completed_learning_round": False,
            },
            "guidance": {
                "stage": "profile",
                **serialize_guidance_state(state),
            },
            "module_errors": {},
        }

    resources = (
        db.query(LearningResource)
        .filter(LearningResource.learner_id == profile.id)
        .order_by(LearningResource.created_at.desc())
        .limit(5)
        .all()
    )
    resource_count = db.query(func.count(LearningResource.id)).filter(
        LearningResource.learner_id == profile.id,
    ).scalar() or 0
    tasks = (
        db.query(AgentTask)
        .filter(AgentTask.learner_id == profile.id)
        .order_by(AgentTask.created_at.desc())
        .limit(5)
        .all()
    )
    diagnosis_count = db.query(func.count(AgentTask.id)).filter(
        AgentTask.learner_id == profile.id,
        AgentTask.task_type.in_(("learner_diagnosis", "full_pipeline")),
        AgentTask.status == "completed",
    ).scalar() or 0
    answer_count = db.query(func.count(AnswerRecord.id)).filter(
        AnswerRecord.learner_id == profile.id,
    ).scalar() or 0
    correct_count = db.query(func.count(AnswerRecord.id)).filter(
        AnswerRecord.learner_id == profile.id,
        AnswerRecord.result == "correct",
    ).scalar() or 0
    feedback = (
        db.query(AnswerRecord)
        .filter(AnswerRecord.learner_id == profile.id)
        .order_by(AnswerRecord.created_at.desc())
        .limit(5)
        .all()
    )
    accuracy = round(correct_count / answer_count * 100, 1) if answer_count else None
    stage = get_guidance_stage(profile, diagnosis_count, resource_count, answer_count)

    return {
        "profile": serialize_profile(profile),
        "summary": {
            "learning_phase": profile.learning_phase or "entry",
            "learning_phase_score": profile.learning_phase_score or 0,
            "progress": profile.completion_rate or 0,
            "average_ability": round(profile.average_ability, 1),
            "total_answers": answer_count,
            "correct_answers": correct_count,
            "accuracy": accuracy,
            "streak_days": profile.consecutive_study_days or 0,
            "total_study_hours": profile.total_study_hours or 0,
            "last_active_at": _iso(profile.last_active_at),
        },
        "recent_resources": [serialize_resource(resource) for resource in resources],
        "current_tasks": [serialize_task(task) for task in tasks],
        "recent_feedback": [serialize_feedback(record) for record in feedback],
        "facts": {
            "has_diagnosis": diagnosis_count > 0,
            "resource_count": resource_count,
            "answer_count": answer_count,
            "completed_learning_round": answer_count > 0,
        },
        "guidance": {
            "stage": stage,
            **serialize_guidance_state(state),
        },
        "module_errors": {},
    }


def get_learner_dashboard(db: Session, user_id: int) -> dict[str, Any]:
    profile = LearnerService.get_learner_by_user_id(db, user_id)
    return _learner_dashboard_payload(db, profile, user_id)


def _teacher_scope(
    db: Session,
    page: int,
    page_size: int,
    keyword: Optional[str],
) -> tuple[list[LearnerProfile], int]:
    # 当前系统的教师授权边界由 require_teacher + 学习者列表接口定义；
    # 当班级成员模型接入后，只需替换此查询，不改变 Dashboard 响应契约。
    return LearnerService.get_learner_list(
        db,
        page=page,
        page_size=page_size,
        keyword=keyword,
    )


def get_teacher_dashboard(
    db: Session,
    page: int,
    page_size: int,
    keyword: Optional[str],
) -> dict[str, Any]:
    learners, total = _teacher_scope(db, page, page_size, keyword)
    learner_ids = [learner.id for learner in learners]
    if not learner_ids:
        return {
            "summary": {
                "total_learners": total,
                "average_progress": None,
                "at_risk_count": 0,
                "pending_task_count": 0,
            },
            "learners": [],
            "at_risk_learners": [],
            "stalled_tasks": [],
            "blind_area_distribution": [],
            "pagination": {
                "page": page,
                "page_size": page_size,
                "total": total,
                "total_pages": (total + page_size - 1) // page_size if page_size else 0,
            },
            "scope": {"type": "teacher_learner_list", "learner_count": total},
            "module_errors": {},
        }

    tasks = (
        db.query(AgentTask)
        .filter(
            AgentTask.learner_id.in_(learner_ids),
            AgentTask.status.in_(("pending", "running", "failed")),
        )
        .order_by(AgentTask.created_at.desc())
        .limit(10)
        .all()
    )
    progress_values = [
        learner.completion_rate
        for learner in learners
        if learner.completion_rate is not None
    ]
    at_risk = [
        learner
        for learner in learners
        if (learner.knowledge_blind_areas or []) or (learner.completion_rate or 0) < 20
    ]
    distribution = Counter(
        area
        for learner in learners
        for area in (learner.knowledge_blind_areas or [])
    )

    learner_items = [
        {
            **(serialize_profile(learner) or {}),
            "progress": learner.completion_rate or 0,
            "pending_task_count": sum(task.learner_id == learner.id for task in tasks),
        }
        for learner in learners
    ]
    return {
        "summary": {
            "total_learners": total,
            "average_progress": round(sum(progress_values) / len(progress_values), 1)
            if progress_values
            else None,
            "at_risk_count": len(at_risk),
            "pending_task_count": len(tasks),
        },
        "learners": learner_items,
        "at_risk_learners": [
            {
                "id": learner.id,
                "name": learner.real_name,
                "progress": learner.completion_rate or 0,
                "blind_areas": (learner.knowledge_blind_areas or [])[:3],
                "last_active_at": _iso(learner.last_active_at),
            }
            for learner in at_risk[:5]
        ],
        "stalled_tasks": [serialize_task(task) for task in tasks],
        "blind_area_distribution": [
            {"topic": topic, "count": count}
            for topic, count in distribution.most_common(8)
        ],
        "pagination": {
            "page": page,
            "page_size": page_size,
            "total": total,
            "total_pages": (total + page_size - 1) // page_size if page_size else 0,
        },
        "scope": {"type": "teacher_learner_list", "learner_count": total},
        "module_errors": {},
    }


def update_guidance_state(
    db: Session,
    user_id: int,
    action: str,
) -> dict[str, Optional[str]]:
    state = get_or_create_guidance_state(db, user_id)
    now = utcnow_naive()
    if action == "complete":
        state.onboarding_completed_at = now
        state.dashboard_guidance_dismissed_at = None
    elif action == "snooze":
        state.dashboard_guidance_dismissed_at = now
    elif action == "resume":
        state.dashboard_guidance_dismissed_at = None
    else:
        raise ValueError("不支持的引导状态操作")
    db.commit()
    db.refresh(state)
    return serialize_guidance_state(state)
