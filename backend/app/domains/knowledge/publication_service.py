"""Publication workflow for generated lecture resources."""

from __future__ import annotations

import hashlib
import re
from datetime import datetime
from pathlib import Path
from typing import Any, Optional, Tuple

from loguru import logger
from sqlalchemy.orm import Session

from app.config import settings
from app.domains.knowledge.models import KnowledgeDoc, KnowledgePublicationRequest
from app.domains.knowledge.service import KnowledgeService
from app.domains.learner.models import LearnerProfile
from app.domains.resource.models import LearningResource
from app.services.common import ResourceServiceHelper
from app.utils.auth import CurrentUser


PENDING = "pending"
PUBLISHING = "publishing"
PUBLISHED = "published"
REJECTED = "rejected"
PUBLISH_FAILED = "publish_failed"
ACTIVE_STATUSES = (PENDING, PUBLISHING, PUBLISHED, PUBLISH_FAILED)


class PublicationError(ValueError):
    def __init__(self, message: str, code: str = "publication_invalid"):
        super().__init__(message)
        self.code = code


def _can_access_resource(db: Session, current_user: CurrentUser, resource: LearningResource) -> bool:
    if current_user.is_admin:
        return True
    learner = db.query(LearnerProfile).filter(LearnerProfile.id == resource.learner_id).first()
    if not learner:
        return False
    # Teacher access follows the existing teacher learner-list boundary. The
    # application currently exposes all learner profiles through that list.
    if current_user.is_teacher:
        return True
    return current_user.is_learner and learner.user_id == current_user.user_id


def _safe_version(value: Any) -> str:
    return re.sub(r"[^A-Za-z0-9._-]", "_", str(value or "1.0"))[:32] or "1.0"


def _snapshot(resource: LearningResource) -> tuple[dict[str, Any], str]:
    content = resource.content or ""
    content_hash = hashlib.sha256(content.encode("utf-8")).hexdigest()
    snapshot = {
        "title": ResourceServiceHelper.safe_resource_title(resource),
        "content": content,
        "summary": resource.summary,
        "industry": resource.industry or "通用",
        "knowledge_topic": resource.knowledge_topic,
        "category": "生成讲义",
        "keywords": ResourceServiceHelper.parse_json_field(resource.keywords, []),
        "source_slice_ids": ResourceServiceHelper.parse_json_field(resource.source_slice_ids, []),
        "source_doc_ids": ResourceServiceHelper.parse_json_field(resource.source_doc_ids, []),
        "reference_urls": ResourceServiceHelper.parse_json_field(resource.reference_urls, []),
        "validation_score": resource.validation_score,
        "validation_passed": resource.validation_passed,
        "hallucination_detected": resource.hallucination_detected,
    }
    return snapshot, content_hash


def _serialize(request: KnowledgePublicationRequest) -> dict[str, Any]:
    return {
        "id": request.id,
        "resource_id": request.resource_id,
        "resource_version": request.resource_version,
        "content_hash": request.content_hash,
        "status": request.status,
        "snapshot": request.snapshot or {},
        "submitted_by": request.submitted_by,
        "reviewed_by": request.reviewed_by,
        "review_note": request.review_note,
        "knowledge_doc_id": request.knowledge_doc_id,
        "error_message": request.error_message,
        "submitted_at": request.submitted_at,
        "reviewed_at": request.reviewed_at,
        "published_at": request.published_at,
        "updated_at": request.updated_at,
    }


class KnowledgePublicationService:
    """Validate, review, and publish immutable generated lecture snapshots."""

    @staticmethod
    def get_request(db: Session, request_id: int, current_user: CurrentUser) -> Optional[KnowledgePublicationRequest]:
        request = db.query(KnowledgePublicationRequest).filter(
            KnowledgePublicationRequest.id == request_id
        ).first()
        if not request:
            return None
        resource = db.query(LearningResource).filter(LearningResource.id == request.resource_id).first()
        if current_user.is_admin or (resource and _can_access_resource(db, current_user, resource)):
            return request
        raise PublicationError("无权查看该入库申请", "forbidden")

    @staticmethod
    def get_resource_request(db: Session, resource_id: int, current_user: CurrentUser) -> Optional[KnowledgePublicationRequest]:
        resource = db.query(LearningResource).filter(LearningResource.id == resource_id).first()
        if not resource:
            raise PublicationError("资源不存在", "resource_not_found")
        if not _can_access_resource(db, current_user, resource):
            raise PublicationError("无权查看该资源的入库申请", "forbidden")
        return db.query(KnowledgePublicationRequest).filter(
            KnowledgePublicationRequest.resource_id == resource_id
        ).order_by(KnowledgePublicationRequest.id.desc()).first()

    @staticmethod
    def create_request(db: Session, resource_id: int, current_user: CurrentUser) -> KnowledgePublicationRequest:
        resource = db.query(LearningResource).filter(LearningResource.id == resource_id).first()
        if not resource:
            raise PublicationError("资源不存在", "resource_not_found")
        if not _can_access_resource(db, current_user, resource):
            raise PublicationError("无权提交该讲义", "forbidden")
        if resource.resource_type != "lecture":
            raise PublicationError("只有专属讲义可以申请加入知识库", "resource_type_not_allowed")
        if not resource.is_latest:
            raise PublicationError("仅最新版本讲义可以申请入库", "resource_not_latest")
        if resource.status != "ready":
            raise PublicationError("讲义尚未处于可发布状态", "resource_not_ready")
        if not (resource.content or "").strip():
            raise PublicationError("讲义正文不能为空", "content_empty")
        if (resource.format_type or "md") not in ("md", "text", "html"):
            raise PublicationError("讲义格式不支持入库", "format_invalid")
        if not resource.validation_passed:
            raise PublicationError("讲义质量校验未通过", "validation_failed")
        if resource.hallucination_detected:
            raise PublicationError("讲义检测到幻觉内容，不能入库", "hallucination_detected")

        snapshot, content_hash = _snapshot(resource)
        active_version = db.query(KnowledgePublicationRequest).filter(
            KnowledgePublicationRequest.resource_id == resource_id,
            KnowledgePublicationRequest.resource_version == str(resource.version or "1.0"),
            KnowledgePublicationRequest.status.in_(ACTIVE_STATUSES),
        ).order_by(KnowledgePublicationRequest.id.desc()).first()
        if active_version and active_version.content_hash == content_hash:
            raise PublicationError("该讲义版本已有有效入库申请", "duplicate_request")
        if active_version:
            raise PublicationError("讲义内容已变更，请生成新版本后重新申请", "content_changed")

        request = KnowledgePublicationRequest(
            resource_id=resource.id,
            resource_version=str(resource.version or "1.0"),
            content_hash=content_hash,
            snapshot=snapshot,
            status=PENDING,
            submitted_by=current_user.user_id,
        )
        db.add(request)
        db.commit()
        db.refresh(request)
        logger.info("创建讲义入库申请: request_id={}, resource_id={}, user_id={}", request.id, resource_id, current_user.user_id)
        return request

    @staticmethod
    def list_requests(
        db: Session,
        page: int = 1,
        page_size: int = 20,
        status: Optional[str] = None,
        industry: Optional[str] = None,
    ) -> Tuple[list[dict[str, Any]], int]:
        query = db.query(KnowledgePublicationRequest).join(
            LearningResource, KnowledgePublicationRequest.resource_id == LearningResource.id
        )
        if status:
            query = query.filter(KnowledgePublicationRequest.status == status)
        if industry:
            query = query.filter(LearningResource.industry == industry)
        total = query.count()
        items = query.order_by(KnowledgePublicationRequest.submitted_at.desc()).offset(
            (page - 1) * page_size
        ).limit(page_size).all()
        return [_serialize(item) for item in items], total

    @staticmethod
    def reject_request(db: Session, request_id: int, current_user: CurrentUser, reason: str) -> KnowledgePublicationRequest:
        request = db.query(KnowledgePublicationRequest).filter(
            KnowledgePublicationRequest.id == request_id
        ).with_for_update().first()
        if not request:
            raise PublicationError("入库申请不存在", "request_not_found")
        if request.status != PENDING:
            raise PublicationError("只有待审核申请可以驳回", "status_conflict")
        request.status = REJECTED
        request.reviewed_by = current_user.user_id
        request.review_note = reason.strip()
        request.reviewed_at = datetime.now()
        db.commit()
        db.refresh(request)
        return request

    @staticmethod
    def approve_request(db: Session, request_id: int, current_user: CurrentUser) -> KnowledgePublicationRequest:
        request = db.query(KnowledgePublicationRequest).filter(
            KnowledgePublicationRequest.id == request_id
        ).with_for_update().first()
        if not request:
            raise PublicationError("入库申请不存在", "request_not_found")
        if request.status not in (PENDING, PUBLISHING):
            raise PublicationError("当前申请状态不允许批准", "status_conflict")
        if request.status == PENDING:
            request.status = PUBLISHING
            request.reviewed_by = current_user.user_id
            request.reviewed_at = datetime.now()
            request.error_message = None
            db.commit()
        else:
            db.commit()
        return KnowledgePublicationService._publish(db, request.id)

    @staticmethod
    def retry_request(db: Session, request_id: int, current_user: CurrentUser) -> KnowledgePublicationRequest:
        request = db.query(KnowledgePublicationRequest).filter(
            KnowledgePublicationRequest.id == request_id
        ).with_for_update().first()
        if not request:
            raise PublicationError("入库申请不存在", "request_not_found")
        if request.status != PUBLISH_FAILED:
            raise PublicationError("只有发布失败申请可以重试", "status_conflict")
        request.status = PUBLISHING
        request.error_message = None
        request.reviewed_by = current_user.user_id
        request.reviewed_at = datetime.now()
        db.commit()
        return KnowledgePublicationService._publish(db, request.id)

    @staticmethod
    def _publish(db: Session, request_id: int) -> KnowledgePublicationRequest:
        request = db.query(KnowledgePublicationRequest).filter(
            KnowledgePublicationRequest.id == request_id
        ).first()
        if not request:
            raise PublicationError("入库申请不存在", "request_not_found")
        if request.status == PUBLISHED:
            return request

        snapshot = request.snapshot or {}
        content = str(snapshot.get("content") or "")
        if not content.strip():
            return KnowledgePublicationService._mark_failed(db, request, "申请快照正文为空")

        version = _safe_version(request.resource_version)
        filename = f"generated_lecture_{request.resource_id}_v{version}_{request.content_hash[:16]}.md"
        file_path = Path(settings.KNOWLEDGE_DOC_DIR) / filename
        title = str(snapshot.get("title") or f"资源 {request.resource_id} 专属讲义")
        doc = db.query(KnowledgeDoc).filter(KnowledgeDoc.id == request.knowledge_doc_id).first() if request.knowledge_doc_id else None
        if not doc:
            doc = KnowledgeDoc(
                title=title,
                industry=str(snapshot.get("industry") or "通用"),
                category=str(snapshot.get("category") or "生成讲义"),
                file_name=filename,
                file_path=str(file_path),
                file_size=len(content.encode("utf-8")),
                file_type="md",
                content_preview=content[:500],
                source="审核生成讲义",
                origin_type="generated_lecture",
                origin_resource_id=request.resource_id,
                version=version,
                author=f"user:{request.submitted_by}",
                tags=["generated_lecture", str(snapshot.get("knowledge_topic") or "")],
                status="uploading",
                process_progress=0,
            )
            db.add(doc)
            db.flush()
            request.knowledge_doc_id = doc.id
            db.commit()

        try:
            file_path.parent.mkdir(parents=True, exist_ok=True)
            file_path.write_text(content, encoding="utf-8")
            doc.file_path = str(file_path)
            doc.file_size = len(content.encode("utf-8"))
            doc.status = "uploading"
            doc.error_message = None
            db.commit()
            if not KnowledgeService.process_doc(db, doc.id, content):
                return KnowledgePublicationService._mark_failed(db, request, "知识库文档索引失败")
            request = db.query(KnowledgePublicationRequest).filter(
                KnowledgePublicationRequest.id == request_id
            ).first()
            request.status = PUBLISHED
            request.published_at = datetime.now()
            request.error_message = None
            db.commit()
            db.refresh(request)
            return request
        except Exception as exc:
            logger.exception("讲义入库失败: request_id={}", request_id)
            return KnowledgePublicationService._mark_failed(db, request, "知识库发布失败，请检查索引服务后重试")

    @staticmethod
    def _mark_failed(db: Session, request: KnowledgePublicationRequest, message: str) -> KnowledgePublicationRequest:
        request.status = PUBLISH_FAILED
        request.error_message = message[:200]
        db.commit()
        db.refresh(request)
        return request


__all__ = [
    "KnowledgePublicationService",
    "PublicationError",
    "PENDING",
    "PUBLISHING",
    "PUBLISHED",
    "REJECTED",
    "PUBLISH_FAILED",
]
