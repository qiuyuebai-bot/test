"""
交互式自适应导学 API 路由
包含：题库获取、答题提交、交互历史、决策逻辑说明
"""
from typing import Optional
from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.database import get_db
from app.schemas.response import (
    success,
    error,
    not_found,
    paged_success,
    unauthorized,
    BaseResponse,
)
from app.schemas.core import GenerateTutoringQuestionsRequest, SubmitAnswerRequest
from app.services.tutoring_service import AdaptiveTutoringService
from app.domains.learner.service import LearnerService
from app.models import LearnerProfile
from app.utils.logger import LoggerUtil
from app.utils.auth import get_current_user, CurrentUser

router = APIRouter(prefix="", tags=["自适应导学"])


@router.get("/tutoring/questions", summary="获取导学题库")
def get_tutoring_questions(
    learner_id: int = Query(..., gt=0, description="学习者ID"),
    db: Session = Depends(get_db),
    current_user: CurrentUser = Depends(get_current_user),
) -> BaseResponse:
    """获取当前学习者尚未作答的导学题目。"""
    if not current_user.is_admin:
        if not LearnerService.check_data_permission(db, current_user.user_id, learner_id):
            return unauthorized("无权限查看该学习者导学题目")
    try:
        questions = AdaptiveTutoringService.get_issued_questions(learner_id)
        return success(data=questions)
    except Exception as e:
        LoggerUtil.log_error("获取题库失败", e)
        return error(message=f"获取题库失败: {str(e)}")


@router.post("/tutoring/questions/generate", summary="动态生成练习题")
def generate_tutoring_questions(
    request: GenerateTutoringQuestionsRequest,
    db: Session = Depends(get_db),
    current_user: CurrentUser = Depends(get_current_user),
) -> BaseResponse:
    """生成服务端保存的练习题；浏览器不会收到正确答案。"""
    if not current_user.is_admin and not LearnerService.check_data_permission(db, current_user.user_id, request.learner_id):
        return unauthorized("无权限为该学习者生成题目")
    try:
        questions = AdaptiveTutoringService.generate_dynamic_questions(
            current_user.user_id,
            request.learner_id,
            request.topic,
            request.difficulty,
            request.question_count,
        )
        return success(data={"questions": questions, "generation_method": questions[0].get("generationMethod", "deterministic_fallback") if questions else "deterministic_fallback"})
    except Exception as e:
        LoggerUtil.log_error("动态生成题目失败", e)
        return error(message=f"动态生成题目失败: {str(e)}")


@router.post("/tutoring/answer", summary="提交答题结果")
def submit_answer(
    request: SubmitAnswerRequest,
    db: Session = Depends(get_db),
    current_user: CurrentUser = Depends(get_current_user),
) -> BaseResponse:
    """
    提交答题结果，触发多Agent协同自适应决策

    双分支逻辑：
    - 正确率≥70% → 生成高阶进阶挑战任务
    - 正确率<70% → 生成简化通俗知识点解释

    完整留存交互记录，支持历史回溯
    """
    learner = db.query(LearnerProfile).filter(LearnerProfile.id == request.learner_id).first()
    if not learner:
        return not_found("学习者不存在")
    # 管理员可代任意学习者作答；普通用户仅能操作本人名下的学习者
    if not current_user.is_admin and learner.user_id != current_user.user_id:
        return unauthorized("导学题目必须由对应学习者本人作答")
    try:
        result = AdaptiveTutoringService.process_answer(
            # 传学习者的归属 user_id（题目下发时存的就是 learner.user_id），
            # 而非操作者 ID——管理员代答时两者不同，否则题目归属查询会匹配不到
            user_id=learner.user_id,
            learner_id=request.learner_id,
            question_id=request.question_id,
            user_answer=request.user_answer,
            time_spent_ms=request.time_spent_ms,
            hints_used=request.hints_used,
        )

        if result.get("success"):
            return success(data=result, message="答题处理完成")
        else:
            return not_found(message=result.get("error", "答题处理失败"))
    except Exception as e:
        LoggerUtil.log_error("处理答题失败", e)
        return error(message=f"处理答题失败: {str(e)}")


@router.get("/tutoring/history/{learner_id}", summary="获取交互历史记录")
def get_interaction_history(
    learner_id: int,
    session_id: Optional[str] = Query(None, description="会话ID"),
    page: int = Query(1, ge=1, description="页码"),
    page_size: int = Query(20, ge=1, le=100, description="每页大小"),
    db: Session = Depends(get_db),
    current_user: CurrentUser = Depends(get_current_user),
) -> BaseResponse:
    """
    获取历史交互记录（支持回溯查询）

    - 返回每轮答题、Agent决策、新生成资源的完整记录
    - 支持按会话筛选
    """
    # IDOR 防护：校验学习者数据归属
    if not current_user.is_admin:
        if not LearnerService.check_data_permission(db, current_user.user_id, learner_id):
            return unauthorized("无权限查看该学习者交互历史")
    try:
        result = AdaptiveTutoringService.get_interaction_history(
            learner_id=learner_id,
            session_id=session_id,
            page=page,
            page_size=page_size,
        )

        return paged_success(
            items=result["history"],
            total=result["total"],
            page=page,
            page_size=page_size,
        )
    except Exception as e:
        LoggerUtil.log_error("获取交互历史失败", e)
        return error(message=f"获取交互历史失败: {str(e)}")


@router.get("/tutoring/decision-logic", summary="获取自适应决策逻辑说明")
def get_decision_logic(db: Session = Depends(get_db)) -> BaseResponse:
    """获取自适应决策逻辑说明（双分支触发条件、Agent协同流程）"""
    try:
        logic = {
            "decision_threshold": AdaptiveTutoringService.DECISION_THRESHOLD,
            "branches": [
                {
                    "condition": "答题正确率 >= 70%",
                    "action": "advance",
                    "description": "生成高阶进阶挑战任务，提升能力",
                },
                {
                    "condition": "答题正确率 < 70%",
                    "action": "simplify",
                    "description": "生成简化通俗知识点解释，帮助理解",
                },
                {
                    "condition": "正确率达标但存在知识盲区",
                    "action": "consolidate",
                    "description": "巩固当前知识点，建议复习基础内容",
                },
            ],
            "agent_coordination": [
                "学情诊断Agent：分析当前知识点掌握情况",
                "领域知识生成Agent：判断是否需要调整资源难度",
                "审核裁判Agent：确认决策合理性",
            ],
            "record_retention": [
                "答题记录（答案、得分、耗时）",
                "Agent决策记录（决策类型、原因、置信度）",
                "生成内容记录（简化解释/进阶挑战）",
                "后续动作记录（推荐资源、下一题目难度）",
            ],
        }

        return success(data=logic)
    except Exception as e:
        LoggerUtil.log_error("获取决策逻辑失败", e)
        return error(message=f"获取决策逻辑失败: {str(e)}")
