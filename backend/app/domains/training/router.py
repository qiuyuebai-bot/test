"""
培训项目域 API 路由
"""
from typing import Optional
from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.database import get_db
from app.schemas.response import BaseResponse
from app.domains.training.schemas import (
    TrainingProjectCreate, TrainingProjectUpdate,
    EnrollRequest, GeneratePlanRequest, UpdateProgressRequest,
    TaskPackageCreate, TaskPackageUpdate, SubmissionCreate, SubmissionReview,
)
from app.domains.training.service import TrainingService
from app.models.user import UserRoleEnum
from app.utils.auth import get_current_user, CurrentUser, require_teacher

router = APIRouter(tags=["培训项目"])


# ===========================================
# 培训项目路由
# ===========================================

@router.get("/training-projects", summary="培训项目列表")
def get_projects(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    status: Optional[str] = Query(None),
    keyword: Optional[str] = Query(None),
    position_id: Optional[int] = Query(None),
    db: Session = Depends(get_db),
    current_user: CurrentUser = Depends(get_current_user),
) -> BaseResponse:
    is_staff = current_user.role in (UserRoleEnum.ADMIN.value, UserRoleEnum.TEACHER.value)
    return TrainingService.get_project_list(db, page, page_size, status, keyword, position_id, is_staff=is_staff)


@router.post("/training-projects", summary="创建培训项目")
def create_project(
    data: TrainingProjectCreate,
    db: Session = Depends(get_db),
    current_user: CurrentUser = Depends(require_teacher),
) -> BaseResponse:
    return TrainingService.create_project(db, data, current_user.user_id)


@router.get("/training-projects/{project_id}", summary="培训项目详情")
def get_project_detail(
    project_id: int,
    db: Session = Depends(get_db),
    current_user: CurrentUser = Depends(get_current_user),
) -> BaseResponse:
    is_staff = current_user.role in (UserRoleEnum.ADMIN.value, UserRoleEnum.TEACHER.value)
    return TrainingService.get_project_by_id(db, project_id, is_staff=is_staff)


@router.put("/training-projects/{project_id}", summary="更新培训项目")
def update_project(
    project_id: int,
    data: TrainingProjectUpdate,
    db: Session = Depends(get_db),
    current_user: CurrentUser = Depends(require_teacher),
) -> BaseResponse:
    return TrainingService.update_project(db, project_id, data)


@router.delete("/training-projects/{project_id}", summary="删除培训项目")
def delete_project(
    project_id: int,
    db: Session = Depends(get_db),
    current_user: CurrentUser = Depends(require_teacher),
) -> BaseResponse:
    return TrainingService.delete_project(db, project_id)


@router.post("/training-projects/{project_id}/enroll", summary="报名培训项目")
def enroll(
    project_id: int,
    data: EnrollRequest,
    db: Session = Depends(get_db),
    current_user: CurrentUser = Depends(get_current_user),
) -> BaseResponse:
    is_staff = current_user.role in (UserRoleEnum.ADMIN.value, UserRoleEnum.TEACHER.value)
    return TrainingService.enroll(db, project_id, current_user.user_id, data.learner_id, is_staff=is_staff)


@router.get("/training-projects/{project_id}/enrollment", summary="查询当前用户报名状态")
def get_enrollment(
    project_id: int,
    learner_id: Optional[int] = Query(None),
    db: Session = Depends(get_db),
    current_user: CurrentUser = Depends(get_current_user),
) -> BaseResponse:
    is_staff = current_user.role in (UserRoleEnum.ADMIN.value, UserRoleEnum.TEACHER.value)
    return TrainingService.get_enrollment(db, project_id, current_user.user_id, learner_id, is_staff=is_staff)


@router.get("/training-projects/{project_id}/enrollments", summary="项目学员列表")
def get_enrollments(
    project_id: int,
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    db: Session = Depends(get_db),
    current_user: CurrentUser = Depends(require_teacher),
) -> BaseResponse:
    return TrainingService.get_enrollments(db, project_id, page, page_size)


# ===========================================
# 培训计划路由
# ===========================================

@router.post("/training-enrollments/{enrollment_id}/generate-plan", summary="AI生成学习计划")
def generate_plan(
    enrollment_id: int,
    data: GeneratePlanRequest,
    db: Session = Depends(get_db),
    current_user: CurrentUser = Depends(get_current_user),
) -> BaseResponse:
    is_staff = current_user.role in (UserRoleEnum.ADMIN.value, UserRoleEnum.TEACHER.value)
    return TrainingService.generate_plan(db, enrollment_id, current_user.user_id, data.assessment_record_id, is_staff=is_staff)


@router.get("/training-enrollments/{enrollment_id}/plan", summary="获取学习计划")
def get_plan(
    enrollment_id: int,
    db: Session = Depends(get_db),
    current_user: CurrentUser = Depends(get_current_user),
) -> BaseResponse:
    is_staff = current_user.role in (UserRoleEnum.ADMIN.value, UserRoleEnum.TEACHER.value)
    return TrainingService.get_plan(db, enrollment_id, current_user.user_id, is_staff=is_staff)


@router.put("/training-plans/{plan_id}/progress", summary="更新学习进度")
def update_progress(
    plan_id: int,
    data: UpdateProgressRequest,
    db: Session = Depends(get_db),
    current_user: CurrentUser = Depends(get_current_user),
) -> BaseResponse:
    is_staff = current_user.role in (UserRoleEnum.ADMIN.value, UserRoleEnum.TEACHER.value)
    return TrainingService.update_progress(db, plan_id, data.completed_stages, current_user.user_id, is_staff=is_staff)


@router.post("/training-enrollments/{enrollment_id}/complete", summary="完成培训")
def complete_enrollment(
    enrollment_id: int,
    db: Session = Depends(get_db),
    current_user: CurrentUser = Depends(get_current_user),
) -> BaseResponse:
    is_staff = current_user.role in (UserRoleEnum.ADMIN.value, UserRoleEnum.TEACHER.value)
    return TrainingService.complete_enrollment(db, enrollment_id, current_user.user_id, is_staff=is_staff)


# ===========================================
# 任务包、实操提交与效果看板
# ===========================================

@router.get("/training-projects/{project_id}/task-packages", summary="培训任务包列表")
def list_task_packages(
    project_id: int,
    db: Session = Depends(get_db),
    current_user: CurrentUser = Depends(get_current_user),
) -> BaseResponse:
    is_staff = current_user.role in (UserRoleEnum.ADMIN.value, UserRoleEnum.TEACHER.value)
    return TrainingService.list_task_packages(db, project_id, is_staff=is_staff)


@router.post("/training-projects/{project_id}/task-packages", summary="创建培训任务包")
def create_task_package(
    project_id: int,
    data: TaskPackageCreate,
    db: Session = Depends(get_db),
    current_user: CurrentUser = Depends(require_teacher),
) -> BaseResponse:
    return TrainingService.create_task_package(db, project_id, data, current_user.user_id)


@router.put("/training-task-packages/{package_id}", summary="更新培训任务包")
def update_task_package(
    package_id: int,
    data: TaskPackageUpdate,
    db: Session = Depends(get_db),
    current_user: CurrentUser = Depends(require_teacher),
) -> BaseResponse:
    return TrainingService.update_task_package(db, package_id, data)


@router.delete("/training-task-packages/{package_id}", summary="删除培训任务包")
def delete_task_package(
    package_id: int,
    db: Session = Depends(get_db),
    current_user: CurrentUser = Depends(require_teacher),
) -> BaseResponse:
    return TrainingService.delete_task_package(db, package_id)


@router.get("/training-task-packages/{package_id}/submissions", summary="任务包提交记录")
def list_submissions(
    package_id: int,
    enrollment_id: Optional[int] = Query(None),
    db: Session = Depends(get_db),
    current_user: CurrentUser = Depends(get_current_user),
) -> BaseResponse:
    is_staff = current_user.role in (UserRoleEnum.ADMIN.value, UserRoleEnum.TEACHER.value)
    return TrainingService.list_submissions(db, package_id, enrollment_id, current_user.user_id, is_staff=is_staff)


@router.post("/training-task-packages/{package_id}/submissions", summary="提交实操任务")
def create_submission(
    package_id: int,
    data: SubmissionCreate,
    enrollment_id: Optional[int] = Query(None),
    db: Session = Depends(get_db),
    current_user: CurrentUser = Depends(get_current_user),
) -> BaseResponse:
    is_staff = current_user.role in (UserRoleEnum.ADMIN.value, UserRoleEnum.TEACHER.value)
    resolved_enrollment_id = enrollment_id or data.enrollment_id
    if not resolved_enrollment_id:
        from app.schemas.response import bad_request
        return bad_request(message="请提供报名记录ID")
    return TrainingService.create_submission(db, package_id, resolved_enrollment_id, current_user.user_id, data, is_staff=is_staff)


@router.post("/training-submissions/{submission_id}/review", summary="教师评分实操提交")
def review_submission(
    submission_id: int,
    data: SubmissionReview,
    db: Session = Depends(get_db),
    current_user: CurrentUser = Depends(require_teacher),
) -> BaseResponse:
    return TrainingService.review_submission(db, submission_id, current_user.user_id, data)


@router.get("/training-dashboard/overview", summary="培训效果看板")
def dashboard_overview(
    db: Session = Depends(get_db),
    current_user: CurrentUser = Depends(get_current_user),
) -> BaseResponse:
    is_staff = current_user.role in (UserRoleEnum.ADMIN.value, UserRoleEnum.TEACHER.value)
    return TrainingService.dashboard_overview(db, current_user.user_id, is_staff=is_staff)
