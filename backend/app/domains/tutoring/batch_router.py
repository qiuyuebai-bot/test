"""Batch practice endpoints kept separate from the adaptive answer flow."""
from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.database import get_db
from app.domains.learner.service import LearnerService
from app.models import LearnerProfile
from app.schemas.core import SubmitBatchRequest
from app.schemas.response import BaseResponse, error, forbidden, not_found, success
from app.services.tutoring_service import AdaptiveTutoringService
from app.utils.auth import CurrentUser, get_current_user
from app.utils.logger import LoggerUtil


router = APIRouter(prefix="", tags=["batch practice"])


def _can_access(db: Session, current_user: CurrentUser, learner_id: int) -> bool:
    return current_user.is_admin or LearnerService.check_data_permission(db, current_user.user_id, learner_id)


@router.post("/tutoring/answers/batch", summary="Submit a batch practice session")
def submit_batch(
    request: SubmitBatchRequest,
    db: Session = Depends(get_db),
    current_user: CurrentUser = Depends(get_current_user),
) -> BaseResponse:
    learner = db.query(LearnerProfile).filter(LearnerProfile.id == request.learner_id).first()
    if not learner:
        return not_found("batch session not found")
    if not _can_access(db, current_user, request.learner_id):
        return forbidden("batch session access denied")

    try:
        result = AdaptiveTutoringService.submit_batch(
            user_id=learner.user_id,
            learner_id=request.learner_id,
            session_id=request.session_id,
            answers=[item.model_dump() for item in request.answers],
        )
        if result.get("success"):
            return success(data=result, message="Batch submission completed")
        return error(
            code=int(result.get("status_code", 409)),
            message=result.get("error", "Batch submission failed"),
        )
    except Exception as exc:
        LoggerUtil.log_error("Batch submission failed", exc)
        return error(message="Batch submission failed; please retry")


@router.get("/tutoring/answers/batch/{session_id}", summary="Get a batch practice result")
def get_batch_result(
    session_id: str,
    learner_id: int = Query(..., gt=0),
    db: Session = Depends(get_db),
    current_user: CurrentUser = Depends(get_current_user),
) -> BaseResponse:
    learner = db.query(LearnerProfile).filter(LearnerProfile.id == learner_id).first()
    if not learner:
        return not_found("batch result not found")
    if not _can_access(db, current_user, learner_id):
        return forbidden("batch result access denied")

    result = AdaptiveTutoringService.get_batch_result(
        user_id=learner.user_id,
        learner_id=learner_id,
        session_id=session_id,
    )
    if result is None:
        return not_found("batch result not found")
    return success(data=result, message="Batch result loaded")
