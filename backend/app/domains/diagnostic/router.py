from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.database import get_db
from app.domains.diagnostic.schemas import DiagnosticAnswerCreate, DiagnosticSessionCreate
from app.domains.diagnostic.service import DiagnosticService
from app.domains.learner.models import DiagnosticSession
from app.domains.learner.service import LearnerService
from app.schemas.response import BaseResponse, bad_request, not_found, success, unauthorized
from app.utils.auth import CurrentUser, get_current_user


router = APIRouter(prefix="/diagnostic", tags=["能力诊断"])


def _check_access(db: Session, current_user: CurrentUser, learner_id: int) -> bool:
    return current_user.is_admin or LearnerService.check_data_permission(db, current_user.user_id, learner_id)


@router.post("/sessions", summary="创建或恢复能力诊断会话")
def create_session(
    request: DiagnosticSessionCreate,
    db: Session = Depends(get_db),
    current_user: CurrentUser = Depends(get_current_user),
) -> BaseResponse:
    if not _check_access(db, current_user, request.learner_id):
        return unauthorized("无权创建该学习者的能力诊断")
    try:
        data = DiagnosticService.create_or_resume(
            db,
            current_user.user_id,
            request.learner_id,
            request.questions_per_dimension,
        )
        return success(data=data, message="能力诊断已准备")
    except ValueError as exc:
        return not_found(message=str(exc))
    except Exception as exc:
        db.rollback()
        return bad_request(message=f"能力诊断准备失败: {exc}")


@router.get("/sessions/{session_id}", summary="读取能力诊断会话")
def get_session(
    session_id: str,
    db: Session = Depends(get_db),
    current_user: CurrentUser = Depends(get_current_user),
) -> BaseResponse:
    session = db.query(DiagnosticSession).filter(DiagnosticSession.id == session_id).first()
    if not session or not _check_access(db, current_user, session.learner_id):
        return not_found("能力诊断会话不存在")
    return success(data=DiagnosticService.serialize_session(db, session))


@router.post("/sessions/{session_id}/answers", summary="提交能力诊断答案")
def submit_answer(
    session_id: str,
    request: DiagnosticAnswerCreate,
    db: Session = Depends(get_db),
    current_user: CurrentUser = Depends(get_current_user),
) -> BaseResponse:
    session = db.query(DiagnosticSession).filter(DiagnosticSession.id == session_id).first()
    if not session or not _check_access(db, current_user, session.learner_id):
        return not_found("能力诊断会话不存在")
    try:
        data = DiagnosticService.submit_answer(
            db,
            current_user.user_id if not current_user.is_admin else session.user_id,
            session.learner_id,
            session_id,
            request.question_id,
            request.user_answer,
            request.time_spent_ms,
        )
        return success(data=data, message="诊断答案已记录")
    except ValueError as exc:
        return bad_request(message=str(exc))
    except Exception as exc:
        db.rollback()
        return bad_request(message=f"诊断答案提交失败: {exc}")
