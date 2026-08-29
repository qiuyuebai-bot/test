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
from app.utils.resource_content import strip_fallback_disclosure


PENDING = "pending"
WAITING_VALIDATION = "waiting_validation"
PUBLISHING = "publishing"
PUBLISHED = "published"
REJECTED = "rejected"
PUBLISH_FAILED = "publish_failed"
ACTIVE_STATUSES = (PENDING, WAITING_VALIDATION, PUBLISHING, PUBLISHED, PUBLISH_FAILED)
AUTOMATED_PUBLICATION_NOTE = "系统自动入库"
_AUTO_TITLE_PLACEHOLDERS = {"none", "null", "undefined", "未命名", "未命名资源"}
# 知识库入库最低正文长度；低于该值的讲义正文视为占位内容，禁止入库落盘
_MIN_PUBLISHABLE_CONTENT_CHARS = 200
_STUB_CONTENT_RE = re.compile(
    r"^(?:#.*\n+)*\s*(?:完整内容。?|正文|this is complete content\.?|placeholder|待补充|todo)\s*$",
    re.IGNORECASE,
)


def _content_stub_reason(content: Any) -> Optional[str]:
    """Return a diagnostic reason when lecture content is placeholder-grade."""
    text = str(content or "").strip()
    if not text:
        return "讲义正文为空"
    if _STUB_CONTENT_RE.match(text):
        return "讲义正文为占位文本"
    if len(text) < _MIN_PUBLISHABLE_CONTENT_CHARS:
        return "讲义正文过短，疑似占位内容"
    return None


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
    def _automatic_publication_reason(resource: LearningResource) -> Optional[str]:
        """Return a diagnostic reason when a newly generated lecture is ineligible."""
        if resource.resource_type != "lecture":
            return "只有专属讲义可以自动加入知识库"
        if not resource.is_latest:
            return "仅最新版本讲义可以自动入库"
        if resource.status != "ready":
            return "讲义尚未完成生成"
        if not resource.validation_passed:
            return "讲义质量校验未通过"
        if resource.hallucination_detected:
            return "讲义检测到未经证实的内容"
        title = str(resource.title or "").strip()
        if not title or title.lower() in _AUTO_TITLE_PLACEHOLDERS:
            return "讲义标题为空或为占位标题"
        if not str(resource.industry or "").strip():
            return "讲义未绑定领域"
        content_reason = _content_stub_reason(resource.content)
        if content_reason:
            return content_reason
        if (resource.format_type or "md") not in ("md", "text", "html"):
            return "讲义格式不支持入库"
        if resource.review_status != "approved":
            return "讲义审核状态未通过"
        return None

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
    def auto_publish_resource(db: Session, resource_id: int) -> Optional[KnowledgePublicationRequest]:
        """Publish one newly generated, validated lecture without manual approval.

        This entry point is intentionally explicit. Callers use it only for a
        resource created by the current generation transaction; historical
        resources are never discovered or changed by this method.
        """
        resource = db.query(LearningResource).filter(LearningResource.id == resource_id).first()
        if not resource:
            logger.warning("自动入库跳过：资源不存在 resource_id={}", resource_id)
            return None

        reason = KnowledgePublicationService._automatic_publication_reason(resource)
        if reason:
            logger.info("自动入库跳过：resource_id={}, reason={}", resource_id, reason)
            return None

        learner = db.query(LearnerProfile).filter(LearnerProfile.id == resource.learner_id).first()
        if not learner or not learner.user_id:
            logger.warning("自动入库跳过：资源缺少有效学习者 resource_id={}", resource_id)
            return None

        snapshot, content_hash = _snapshot(resource)
        resource_version = str(resource.version or "1.0")
        existing = db.query(KnowledgePublicationRequest).filter(
            KnowledgePublicationRequest.resource_id == resource.id,
            KnowledgePublicationRequest.resource_version == resource_version,
            KnowledgePublicationRequest.content_hash == content_hash,
            KnowledgePublicationRequest.status.in_(ACTIVE_STATUSES),
        ).order_by(KnowledgePublicationRequest.id.desc()).first()
        if existing:
            return existing

        request = KnowledgePublicationRequest(
            resource_id=resource.id,
            resource_version=resource_version,
            content_hash=content_hash,
            snapshot=snapshot,
            status=PUBLISHING,
            submitted_by=learner.user_id,
            review_note=AUTOMATED_PUBLICATION_NOTE,
        )
        db.add(request)
        db.commit()
        db.refresh(request)
        try:
            return KnowledgePublicationService._continue_publication(db, request.id)
        except Exception:
            logger.exception("自动入库失败: request_id={}, resource_id={}", request.id, resource.id)
            request = db.query(KnowledgePublicationRequest).filter(
                KnowledgePublicationRequest.id == request.id
            ).first()
            if request:
                request.status = PUBLISH_FAILED
                request.error_message = "知识库自动发布失败，请由管理员重试"
                db.commit()
                db.refresh(request)
            return request

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
        if resource.status in ("failed", "archived"):
            raise PublicationError("讲义生成失败或已归档，暂不能申请入库", "resource_not_publishable")
        content_reason = _content_stub_reason(resource.content)
        if content_reason:
            raise PublicationError(content_reason, "content_stub")
        if (resource.format_type or "md") not in ("md", "text", "html"):
            raise PublicationError("讲义格式不支持入库", "format_invalid")

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
        return KnowledgePublicationService._continue_publication(db, request.id)

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
        return KnowledgePublicationService._continue_publication(db, request.id)

    @staticmethod
    def sync_resource_generation_state(db: Session, resource_id: int) -> None:
        """Resume approved requests when a resource finishes generation.

        Pending requests still require administrator approval. Requests already
        approved while the resource was processing are resumed automatically.
        """
        resource = db.query(LearningResource).filter(LearningResource.id == resource_id).first()
        if not resource:
            return

        requests = db.query(KnowledgePublicationRequest).filter(
            KnowledgePublicationRequest.resource_id == resource_id,
            KnowledgePublicationRequest.status.in_((PENDING, WAITING_VALIDATION, PUBLISHING)),
        ).order_by(KnowledgePublicationRequest.id.asc()).all()
        if not requests:
            return

        if resource.status in ("failed", "archived"):
            for request in requests:
                request.status = PUBLISH_FAILED
                request.error_message = "讲义生成失败，无法发布到知识库"
            db.commit()
            return

        if resource.status != "ready":
            return

        for request in requests:
            if request.status == PENDING:
                if not resource.validation_passed or resource.hallucination_detected:
                    request.status = PUBLISH_FAILED
                    request.error_message = "讲义质量校验未通过，无法发布到知识库"
                continue
            KnowledgePublicationService._continue_publication(db, request.id)
        db.commit()

    @staticmethod
    def _continue_publication(db: Session, request_id: int) -> KnowledgePublicationRequest:
        request = db.query(KnowledgePublicationRequest).filter(
            KnowledgePublicationRequest.id == request_id
        ).first()
        if not request:
            raise PublicationError("入库申请不存在", "request_not_found")
        if request.status == PUBLISHED:
            return request

        resource = db.query(LearningResource).filter(LearningResource.id == request.resource_id).first()
        if not resource:
            return KnowledgePublicationService._mark_failed(db, request, "原讲义资源不存在")
        if resource.status in ("generating", "validating"):
            request.status = WAITING_VALIDATION
            request.error_message = None
            db.commit()
            db.refresh(request)
            return request
        if resource.status in ("failed", "archived"):
            return KnowledgePublicationService._mark_failed(db, request, "讲义生成失败，无法发布到知识库")
        if resource.status != "ready":
            return KnowledgePublicationService._mark_failed(db, request, "讲义状态不允许发布")
        if not resource.validation_passed or resource.hallucination_detected:
            return KnowledgePublicationService._mark_failed(db, request, "讲义质量校验未通过，无法发布到知识库")
        if request.status == WAITING_VALIDATION:
            request.status = PUBLISHING
            request.error_message = None
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

        resource = db.query(LearningResource).filter(LearningResource.id == request.resource_id).first()
        if not resource:
            return KnowledgePublicationService._mark_failed(db, request, "原讲义资源不存在")
        if resource.status in ("generating", "validating"):
            request.status = WAITING_VALIDATION
            request.error_message = None
            db.commit()
            db.refresh(request)
            return request
        if resource.status != "ready":
            return KnowledgePublicationService._mark_failed(db, request, "讲义状态不允许发布")
        if not resource.validation_passed or resource.hallucination_detected:
            return KnowledgePublicationService._mark_failed(db, request, "讲义质量校验未通过，无法发布到知识库")

        snapshot = request.snapshot or {}
        # 知识库只收录知识内容本身；“参考知识库资料不足”是面向学习者的运维
        # 声明（保留在资源原文），发布前剥离，防止话术被切片当作知识证据。
        content = strip_fallback_disclosure(snapshot.get("content"))
        content_reason = _content_stub_reason(content)
        if content_reason:
            return KnowledgePublicationService._mark_failed(db, request, f"申请快照{content_reason}")

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
    "WAITING_VALIDATION",
    "PUBLISHING",
    "PUBLISHED",
    "REJECTED",
    "PUBLISH_FAILED",
]
