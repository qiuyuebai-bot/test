"""
学习者画像模块 API 路由
实现画像管理、学情分析、数据脱敏、批量导入导出等接口
"""
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from typing import Optional
from loguru import logger

from app.database import get_db
from app.schemas.response import success, bad_request, not_found, paged_success, unauthorized
from app.domains.learner.schemas import (
    LearnerProfileCreate,
    LearnerProfileUpdate,
    LearnerProfileResponse,
    LearnerBatchImportRequest,
    LearnerBatchExportRequest,
    AnonymizeRequest,
    AnswerRecordCreate,
    AnswerRecordResponse,
)
from app.domains.learner.service import LearnerService
from app.utils.auth import get_current_user, CurrentUser, require_admin, require_teacher

router = APIRouter(prefix="/learners", tags=["学习者画像"])


# ===========================================
# 1. 新增学习者
# ===========================================

@router.post("", summary="创建学习者画像")
def create_learner(
    learner_data: LearnerProfileCreate,
    db: Session = Depends(get_db),
    current_user: CurrentUser = Depends(get_current_user),
):
    """
    创建新的学习者画像
    
    - **user_id**: 关联用户ID
    - **real_name**: 真实姓名
    - **education_level**: 学历层次
    - **major**: 专业方向
    - **theoretical_foundation**: 理论基础(0-100)
    - 以及其他能力维度、知识盲区等
    """
    try:
        learner = LearnerService.create_learner(db, learner_data)
        if learner is None:
            return bad_request("用户已存在学习者画像")
        return success({"id": learner.id}, "创建成功")
    except Exception as e:
        logger.error(f"创建学习者失败: {e}")
        return bad_request(f"创建失败: {str(e)}")


# ===========================================
# 2. 学习者列表
# ===========================================

@router.get("", summary="获取学习者列表")
def get_learner_list(
    page: int = 1,
    page_size: int = 10,
    keyword: Optional[str] = None,
    education_level: Optional[str] = None,
    target_industry: Optional[str] = None,
    learning_style: Optional[str] = None,
    is_anonymized: Optional[bool] = None,
    db: Session = Depends(get_db),
    current_user: CurrentUser = Depends(require_teacher),
):
    """
    获取学习者列表，支持分页、搜索、筛选
    
    - **page**: 页码
    - **page_size**: 每页数量
    - **keyword**: 关键词搜索（姓名/专业/职位）
    - **education_level**: 学历过滤
    - **target_industry**: 目标行业
    - **learning_style**: 学习风格
    - **is_anonymized**: 是否脱敏
    """
    items, total = LearnerService.get_learner_list(
        db,
        page=page,
        page_size=page_size,
        keyword=keyword,
        education_level=education_level,
        target_industry=target_industry,
        learning_style=learning_style,
        is_anonymized=is_anonymized,
    )
    
    response_items = []
    for learner in items:
        response_items.append(LearnerProfileResponse(
            id=learner.id,
            user_id=learner.user_id,
            real_name=learner.real_name,
            education_level=learner.education_level,
            major=learner.major,
            graduation_year=learner.graduation_year,
            current_position=learner.current_position,
            learning_style=learner.learning_style,
            preferred_difficulty=learner.preferred_difficulty,
            daily_study_time=learner.daily_study_time,
            target_industry=learner.target_industry,
            target_position=learner.target_position,
            learning_goal=learner.learning_goal,
            theoretical_foundation=learner.theoretical_foundation,
            programming_ability=learner.programming_ability,
            algorithm_design=learner.algorithm_design,
            system_architecture=learner.system_architecture,
            data_analysis=learner.data_analysis,
            engineering_practice=learner.engineering_practice,
            average_ability=learner.average_ability,
            knowledge_blind_areas=learner.knowledge_blind_areas or [],
            is_data_anonymized=learner.is_data_anonymized,
            created_at=learner.created_at,
            updated_at=learner.updated_at,
        ))
    
    return paged_success(
        items=response_items,
        total=total,
        page=page,
        page_size=page_size,
        message="查询成功",
    )


# ===========================================
# 3. 学习者详情
# ===========================================

@router.get("/{learner_id}", summary="获取学习者详情")
def get_learner_detail(
    learner_id: int,
    db: Session = Depends(get_db),
    current_user: CurrentUser = Depends(get_current_user),
):
    """
    根据ID获取学习者详细信息
    
    - **learner_id**: 学习者ID
    """
    learner = LearnerService.get_learner_by_id(db, learner_id)
    if not learner:
        return not_found("学习者不存在")
    
    # 权限校验：非管理员只能查看自己的数据
    if not current_user.is_admin:
        if not LearnerService.check_data_permission(db, current_user.user_id, learner_id):
            return unauthorized("无权限访问该学习者数据")
    
    response = LearnerProfileResponse(
        id=learner.id,
        user_id=learner.user_id,
        real_name=learner.real_name,
        education_level=learner.education_level,
        major=learner.major,
        graduation_year=learner.graduation_year,
        current_position=learner.current_position,
        learning_style=learner.learning_style,
        preferred_difficulty=learner.preferred_difficulty,
        daily_study_time=learner.daily_study_time,
        target_industry=learner.target_industry,
        target_position=learner.target_position,
        learning_goal=learner.learning_goal,
        theoretical_foundation=learner.theoretical_foundation,
        programming_ability=learner.programming_ability,
        algorithm_design=learner.algorithm_design,
        system_architecture=learner.system_architecture,
        data_analysis=learner.data_analysis,
        engineering_practice=learner.engineering_practice,
        average_ability=learner.average_ability,
        knowledge_blind_areas=learner.knowledge_blind_areas or [],
        is_data_anonymized=learner.is_data_anonymized,
        created_at=learner.created_at,
        updated_at=learner.updated_at,
    )
    
    return success(response, "查询成功")


# ===========================================
# 4. 更新学习者
# ===========================================

@router.put("/{learner_id}", summary="更新学习者画像")
def update_learner(
    learner_id: int,
    update_data: LearnerProfileUpdate,
    db: Session = Depends(get_db),
    current_user: CurrentUser = Depends(get_current_user),
):
    """
    更新学习者画像信息
    """
    if not current_user.is_admin:
        if not LearnerService.check_data_permission(db, current_user.user_id, learner_id):
            return unauthorized("无权限修改该学习者数据")
    learner = LearnerService.update_learner(db, learner_id, update_data)
    if not learner:
        return not_found("学习者不存在")
    
    return success({"id": learner.id}, "更新成功")


# ===========================================
# 5. 删除学习者
# ===========================================

@router.delete("/{learner_id}", summary="删除学习者画像")
def delete_learner(
    learner_id: int,
    db: Session = Depends(get_db),
    current_user: CurrentUser = Depends(get_current_user),
):
    """
    删除学习者画像
    """
    if not current_user.is_admin:
        if not LearnerService.check_data_permission(db, current_user.user_id, learner_id):
            return unauthorized("无权限删除该学习者数据")
    result = LearnerService.delete_learner(db, learner_id)
    if not result:
        return not_found("学习者不存在")
    
    return success(None, "删除成功")


# ===========================================
# 6. 批量导入
# ===========================================

@router.post("/batch-import", summary="批量导入学习者")
def batch_import_learners(
    import_data: LearnerBatchImportRequest,
    db: Session = Depends(get_db),
    current_user: CurrentUser = Depends(require_admin),
):
    """
    批量导入多组差异化学情数据
    
    - **learners**: 学习者列表
    """
    result = LearnerService.batch_import(db, import_data)
    return success(result, "批量导入完成")


# ===========================================
# 7. 批量导出
# ===========================================

@router.post("/batch-export", summary="批量导出学习者")
def batch_export_learners(
    export_request: LearnerBatchExportRequest,
    db: Session = Depends(get_db),
    current_user: CurrentUser = Depends(require_admin),
):
    """
    批量导出学习者画像，支持JSON/CSV格式
    
    - **learner_ids**: 指定导出的ID，为空则导出全部
    - **export_format**: 导出格式(json/csv)
    - **include_sensitive**: 是否包含敏感数据
    """
    export_data = LearnerService.batch_export(db, export_request)
    
    return success({
        "format": export_request.export_format,
        "total_count": len(export_data),
        "data": export_data,
    }, "导出成功")


# ===========================================
# 8. 学情分析
# ===========================================

@router.post("/{learner_id}/analyze", summary="学情分析")
def analyze_learning(
    learner_id: int,
    db: Session = Depends(get_db),
    current_user: CurrentUser = Depends(get_current_user),
):
    """
    自动解析测试答题记录，提取理论强项、技能盲区

    - **learner_id**: 学习者ID
    """
    if not current_user.is_admin:
        if not LearnerService.check_data_permission(db, current_user.user_id, learner_id):
            return unauthorized("无权限分析该学习者数据")
    analysis = LearnerService.analyze_learning(db, learner_id)
    if not analysis:
        return not_found("学习者不存在")
    
    return success(analysis, "分析完成")


# ===========================================
# 9. 数据脱敏
# ===========================================

@router.post("/{learner_id}/anonymize", summary="数据脱敏")
def anonymize_learner(
    learner_id: int,
    anonymize_request: AnonymizeRequest = None,
    db: Session = Depends(get_db),
    current_user: CurrentUser = Depends(get_current_user),
):
    """
    一键对指定学习者敏感信息进行掩码处理
    
    - **learner_id**: 学习者ID
    - **fields**: 指定脱敏字段，为空则脱敏所有敏感字段
    """
    if not current_user.is_admin:
        if not LearnerService.check_data_permission(db, current_user.user_id, learner_id):
            return unauthorized("无权限脱敏该学习者数据")
    if anonymize_request is None:
        anonymize_request = AnonymizeRequest(learner_id=learner_id)
    else:
        anonymize_request.learner_id = learner_id
    
    result = LearnerService.anonymize_learner(db, anonymize_request)
    if not result:
        return not_found("学习者不存在")
    
    return success(result, "脱敏处理完成")


# ===========================================
# 10. 答题记录
# ===========================================

@router.post("/{learner_id}/answers", summary="添加答题记录")
def add_answer_record(
    learner_id: int,
    answer_data: AnswerRecordCreate,
    db: Session = Depends(get_db),
    current_user: CurrentUser = Depends(get_current_user),
):
    """
    添加学习者答题记录（用于学情分析）
    """
    if not current_user.is_admin:
        if not LearnerService.check_data_permission(db, current_user.user_id, learner_id):
            return unauthorized("无权限为该学习者添加答题记录")
    answer_data.learner_id = learner_id
    answer_data.user_id = current_user.user_id
    record = LearnerService.add_answer_record(db, answer_data)
    
    return success({"id": record.id}, "记录成功")


@router.get("/{learner_id}/answers", summary="获取答题记录")
def get_answer_records(
    learner_id: int,
    page: int = 1,
    page_size: int = 20,
    db: Session = Depends(get_db),
    current_user: CurrentUser = Depends(get_current_user),
):
    """
    获取学习者答题记录列表
    """
    if not current_user.is_admin:
        if not LearnerService.check_data_permission(db, current_user.user_id, learner_id):
            return unauthorized("无权限查看该学习者答题记录")
    records, total = LearnerService.get_answer_records(db, learner_id, page, page_size)
    
    response_items = [
        AnswerRecordResponse(
            id=r.id,
            learner_id=r.learner_id,
            question_type=r.question_type,
            question_topic=r.question_topic,
            question_difficulty=r.question_difficulty,
            result=r.result,
            score=r.score,
            time_spent_ms=r.time_spent_ms,
            agent_decision=r.agent_decision,
            decision_reason=r.decision_reason,
            created_at=r.created_at,
        )
        for r in records
    ]
    
    return paged_success(
        items=response_items,
        total=total,
        page=page,
        page_size=page_size,
        message="查询成功",
    )


# ===========================================
# 11. 知识盲区标签云
# ===========================================

@router.get("/{learner_id}/blind-areas", summary="获取知识盲区标签云")
def get_blind_areas(
    learner_id: int,
    db: Session = Depends(get_db),
    current_user: CurrentUser = Depends(get_current_user),
):
    """
    获取学习者知识盲区标签云数据
    """
    if not current_user.is_admin:
        if not LearnerService.check_data_permission(db, current_user.user_id, learner_id):
            return unauthorized("无权限查看该学习者盲区数据")
    learner = LearnerService.get_learner_by_id(db, learner_id)
    if not learner:
        return not_found("学习者不存在")
    
    analysis = LearnerService.analyze_learning(db, learner_id)
    
    return success({
        "blind_areas": learner.knowledge_blind_areas or [],
        "weak_dimensions": analysis.blind_area_details if analysis else [],
    }, "查询成功")