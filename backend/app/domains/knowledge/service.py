"""
知识库服务层
实现文档管理、切片、向量索引、检索、溯源等业务逻辑
"""
import os
import re
import time
import uuid
import threading
import hashlib
from typing import List, Dict, Any, Optional, Tuple
from datetime import datetime
from pathlib import Path
from sqlalchemy.orm import Session
from sqlalchemy import func as sa_func, or_
from loguru import logger

from app.config import settings
from app.models import KnowledgeDoc, KnowledgeSlice, LearningResource, IndustryEnum
from app.utils.text_slice import TextSliceUtil
from app.utils.logger import LoggerUtil
from app.domains.knowledge.parser import KnowledgeDocumentParser
from app.services.common import ResourceServiceHelper
from app.domains.knowledge.schemas import (
    KnowledgeDocCreate,
    KnowledgeDocUpdate,
    KnowledgeSearchRequest,
    KnowledgePreviewResponse,
    KnowledgeTraceResult,
    KnowledgeSliceResponse,
)

# Chroma 可选依赖（未安装或版本不兼容时自动降级为数据库检索）
try:
    import chromadb
    from chromadb.config import Settings as ChromaSettings
    _CHROMA_AVAILABLE = True
except Exception:
    _CHROMA_AVAILABLE = False
    logger.warning("chromadb 不可用，向量检索将降级为数据库关键词检索")


def _escape_like(value: str) -> str:
    """转义 LIKE 模式中的特殊字符，避免用户输入的 % 和 _ 被当作通配符"""
    return value.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")


DEFAULT_MIN_SIMILARITY = 0.6


def _query_terms(query: str) -> List[str]:
    """Build stable word/bigram terms for keyword fallback scoring."""
    terms = [query.strip().casefold()]
    for token in re.findall(r"[A-Za-z0-9_]+|[\u4e00-\u9fff]+", query.casefold()):
        terms.append(token)
        if re.fullmatch(r"[\u4e00-\u9fff]+", token):
            terms.extend(token[index:index + 2] for index in range(len(token) - 1))
    return list(dict.fromkeys(term for term in terms if term))[:24]


def _keyword_match_score(query: str, content: str, title: str = "", keywords: Any = None) -> float:
    terms = _query_terms(query)
    if not terms:
        return 0.0
    haystack = " ".join(
        [str(content or ""), str(title or ""), " ".join(str(item) for item in (keywords or []))]
    ).casefold()
    if query.strip().casefold() in haystack:
        return 1.0
    matched = sum(term in haystack for term in terms if term != query.strip().casefold())
    comparable = max(1, len([term for term in terms if term != query.strip().casefold()]))
    return round(matched / comparable, 4)

# Chroma 全局客户端（懒加载）
_chroma_client: Optional[Any] = None
_chroma_collection: Optional[Any] = None
_chroma_warmed = False
_chroma_lock = threading.Lock()


def _get_chroma_collection():
    """获取或创建 Chroma 集合（单例模式，线程安全）"""
    global _chroma_client, _chroma_collection

    if not _CHROMA_AVAILABLE:
        return None

    if _chroma_collection is None:
        with _chroma_lock:
            if _chroma_collection is None:
                _chroma_client = chromadb.PersistentClient(
                    path=settings.CHROMA_DB_PATH,
                    settings=ChromaSettings(anonymized_telemetry=False),
                )
                _chroma_collection = _chroma_client.get_or_create_collection(
                    name=settings.CHROMA_COLLECTION_NAME,
                    metadata={"hnsw:space": "cosine"},
                )
                logger.info(f"Chroma 初始化完成: collection={settings.CHROMA_COLLECTION_NAME}")

    return _chroma_collection


def is_chroma_available() -> bool:
    """检查 Chroma 是否可用"""
    return _CHROMA_AVAILABLE


class KnowledgeService:
    """知识库服务类"""
    
    # 支持的行业分类（从 IndustryEnum 派生，保持与枚举定义一致）
    SUPPORTED_INDUSTRIES = [e.value for e in IndustryEnum]

    @staticmethod
    def warmup() -> Dict[str, Any]:
        """Initialize Chroma and its embedding function before user traffic."""
        global _chroma_warmed
        started_at = time.perf_counter()
        if not _CHROMA_AVAILABLE:
            return {"ready": False, "vector_count": 0, "duration_ms": 0.0}
        try:
            collection = _get_chroma_collection()
            vector_count = collection.count() if collection is not None else 0
            # A real query initializes the embedding provider as well as the
            # persistent collection. Skip it only when there is no index yet.
            if collection is not None and vector_count:
                collection.query(query_texts=["knowledge system warmup"], n_results=1)
            _chroma_warmed = True
            duration_ms = round((time.perf_counter() - started_at) * 1000, 1)
            logger.info(
                f"知识库预热完成: vectors={vector_count}, duration={duration_ms}ms"
            )
            return {"ready": True, "vector_count": vector_count, "duration_ms": duration_ms}
        except Exception as exc:
            _chroma_warmed = False
            duration_ms = round((time.perf_counter() - started_at) * 1000, 1)
            logger.warning(f"知识库预热失败: duration={duration_ms}ms, error={exc}")
            return {"ready": False, "vector_count": 0, "duration_ms": duration_ms, "error": str(exc)[:200]}

    @staticmethod
    def is_warmed() -> bool:
        return _chroma_warmed

    @staticmethod
    def _keyword_fallback(
        db: Session,
        query: str,
        k: int,
        min_similarity: float,
        industry: Optional[str] = None,
        doc_id: Optional[int] = None,
        existing_ids: Optional[set[int]] = None,
    ) -> List[Dict[str, Any]]:
        sql_query = db.query(KnowledgeSlice).join(KnowledgeDoc).filter(
            KnowledgeDoc.is_enabled == True,
            KnowledgeDoc.status == "ready",
        )
        if industry:
            sql_query = sql_query.filter(KnowledgeDoc.industry == industry)
        if doc_id:
            sql_query = sql_query.filter(KnowledgeSlice.doc_id == doc_id)
        if existing_ids:
            sql_query = sql_query.filter(~KnowledgeSlice.id.in_(existing_ids))

        terms = _query_terms(query)
        if not terms:
            return []
        sql_query = sql_query.filter(or_(*[
            or_(
                KnowledgeSlice.content.like(f"%{_escape_like(term)}%", escape="\\"),
                KnowledgeSlice.title.like(f"%{_escape_like(term)}%", escape="\\"),
            )
            for term in terms
        ]))
        candidates = sql_query.limit(max(k * 5, 20)).all()
        scored = []
        for item in candidates:
            score = _keyword_match_score(query, item.content, item.title, item.keywords)
            if score >= min_similarity:
                scored.append((score, item))
        scored.sort(key=lambda pair: (-pair[0], pair[1].id))
        selected = scored[:k]

        doc_ids = {item.doc_id for _, item in selected}
        docs = {
            doc.id: doc
            for doc in db.query(KnowledgeDoc).filter(
                KnowledgeDoc.id.in_(doc_ids), KnowledgeDoc.is_enabled == True
            ).all()
        } if doc_ids else {}
        return [
            {
                "slice_id": item.id,
                "doc_id": item.doc_id,
                "doc_title": docs[item.doc_id].title if item.doc_id in docs else "",
                "industry": docs[item.doc_id].industry if item.doc_id in docs else "",
                "origin_type": docs[item.doc_id].origin_type if item.doc_id in docs else None,
                "origin_resource_id": docs[item.doc_id].origin_resource_id if item.doc_id in docs else None,
                "title": item.title,
                "content": item.content,
                "similarity": score,
                "slice_index": item.slice_index,
                "keywords": item.keywords or [],
                "highlighted_content": item.content[:200] + "..." if len(item.content) > 200 else item.content,
            }
            for score, item in selected
        ]
    
    @staticmethod
    def create_doc(db: Session, doc_data: KnowledgeDocCreate) -> Tuple[Optional[KnowledgeDoc], str]:
        """
        创建知识库文档记录
        
        Args:
            db: 数据库会话
            doc_data: 文档创建数据
            
        Returns:
            Tuple[文档对象或None, 文件存储路径或错误消息]
        """
        existing = db.query(KnowledgeDoc).filter(
            KnowledgeDoc.title == doc_data.title,
            KnowledgeDoc.is_enabled == True
        ).first()
        if existing:
            logger.warning(f"文档标题已存在: {doc_data.title}")
            return None, "文档标题已存在"
        
        # 生成文件存储路径
        timestamp = datetime.now().strftime("%Y%m%d")
        unique_id = str(uuid.uuid4())[:8]
        file_ext = os.path.splitext(doc_data.file_name)[1]
        stored_filename = f"{timestamp}_{unique_id}{file_ext}"
        file_path = os.path.join(settings.KNOWLEDGE_DOC_DIR, stored_filename)
        
        # 确保目录存在
        Path(settings.KNOWLEDGE_DOC_DIR).mkdir(parents=True, exist_ok=True)
        
        # 创建文档记录
        doc = KnowledgeDoc(
            title=doc_data.title,
            industry=doc_data.industry,
            category=doc_data.category,
            file_name=doc_data.file_name,
            file_path=file_path,
            file_size=doc_data.file_size,
            file_type=doc_data.file_type,
            content_preview=doc_data.content_preview,
            source=doc_data.source,
            author=doc_data.author,
            tags=doc_data.tags,
            status="uploading",
            process_progress=0,
        )
        
        db.add(doc)
        # 持久化上传记录后再开始解析/索引，处理失败时才能保留 error 状态供前端查看。
        db.commit()
        db.refresh(doc)
        
        LoggerUtil.log_api_request("POST", f"/knowledge/docs/{doc.id}", None, doc_data.model_dump())
        logger.info(f"创建知识库文档: id={doc.id}, title={doc.title}")
        
        return doc, file_path
    
    @staticmethod
    def process_doc(db: Session, doc_id: int, file_content: str) -> bool:
        """
        处理文档：解析、切片、入库
        
        Args:
            db: 数据库会话
            doc_id: 文档ID
            file_content: 文件文本内容
            
        Returns:
            是否处理成功
        """
        start_time = time.time()
        
        try:
            doc = db.query(KnowledgeDoc).filter(KnowledgeDoc.id == doc_id).first()
            if not doc:
                logger.error(f"文档不存在: doc_id={doc_id}")
                return False
            
            # 更新状态为处理中
            doc.status = "processing"
            doc.process_progress = 10
            db.flush()
            
            # 1. 文档解析（提取字数、页数等基本信息）
            word_count = len(file_content)
            doc.word_count = word_count
            doc.content_preview = file_content[:500]
            doc.process_progress = 30
            db.flush()
            
            # 2. 文本切片
            slices = TextSliceUtil.slice_by_paragraph(
                file_content,
                max_length=500,
                overlap=50,
            )
            if not slices or not any(item.get("content", "").strip() for item in slices):
                raise ValueError("文档内容为空，无法建立知识索引")
            doc.slice_count = len(slices)
            doc.process_progress = 60
            db.flush()
            
            logger.info(f"文档切片完成: doc_id={doc_id}, slices={len(slices)}")
            
            # 3. 重建数据库切片（重新索引时先清理旧切片）
            db.query(KnowledgeSlice).filter(
                KnowledgeSlice.doc_id == doc_id
            ).delete(synchronize_session=False)
            db.flush()

            # 4. 存储切片到数据库
            slice_objects = []
            for i, slice_data in enumerate(slices):
                content = slice_data["content"]
                content_hash = hashlib.sha256(content.encode('utf-8')).hexdigest()
                slice_obj = KnowledgeSlice(
                    doc_id=doc_id,
                    slice_index=slice_data.get("index", i),
                    slice_type=slice_data.get("slice_type", "paragraph"),
                    title=slice_data.get("title", ""),
                    content=content,
                    content_hash=content_hash,
                    word_count=slice_data.get("word_count", len(content)),
                    keywords=slice_data.get("keywords", []),
                    context_before=slice_data.get("context_before", ""),
                    context_after=slice_data.get("context_after", ""),
                    is_indexed=False,
                )
                db.add(slice_obj)
                slice_objects.append(slice_obj)
            
            db.flush()
            doc.process_progress = 80
            
            # 5. 向量入库。任何失败都必须让文档进入 error，不能伪装成 ready。
            vector_ids = KnowledgeService._index_slices_to_chroma(doc_id, doc.industry, slices)
            for slice_obj, vector_id in zip(slice_objects, vector_ids):
                slice_obj.vector_id = vector_id
                slice_obj.is_indexed = True
            doc.indexed_slice_count = len(vector_ids)
            if len(vector_ids) != len(slice_objects):
                raise RuntimeError(
                    f"向量索引数量不一致: slices={len(slice_objects)}, vectors={len(vector_ids)}"
                )
            
            # 更新文档状态
            doc.status = "ready"
            doc.process_progress = 100
            doc.indexed_at = datetime.now()
            
            db.commit()
            
            duration_ms = (time.time() - start_time) * 1000
            logger.info(f"文档处理完成: doc_id={doc_id}, duration={duration_ms}ms")
            
            return True
            
        except Exception as e:
            logger.error(f"文档处理失败: doc_id={doc_id}, error={e}")
            db.rollback()

            # 更新状态为失败
            doc = db.query(KnowledgeDoc).filter(KnowledgeDoc.id == doc_id).first()
            if doc:
                doc.status = "error"
                doc.process_progress = 0
                doc.indexed_slice_count = 0
                doc.error_message = str(e)
                db.commit()
            
            return False
    
    @staticmethod
    def _index_slices_to_chroma(doc_id: int, industry: str, slices: List[Dict]) -> List[str]:
        """
        将切片索引到Chroma向量数据库（真实接入）
        
        Args:
            doc_id: 文档ID
            industry: 文档所属行业（写入 metadata 支持 Chroma 原生 where 过滤）
            slices: 切片列表
        """
        if not _CHROMA_AVAILABLE:
            raise RuntimeError("Chroma 不可用，无法建立知识索引")
        
        collection = _get_chroma_collection()
        if collection is None:
            raise RuntimeError("Chroma 集合不可用，无法建立知识索引")
        
        # 批量构建向量入库数据
        ids = []
        documents = []
        metadatas = []
        
        for slice_data in slices:
            slice_idx = slice_data.get("slice_index", slice_data.get("index", 0))
            vector_id = f"doc_{doc_id}_slice_{slice_idx}"
            ids.append(vector_id)
            documents.append(slice_data["content"])
            metadatas.append({
                "doc_id": str(doc_id),
                "slice_index": str(slice_idx),
                "industry": industry or "",
                "slice_type": slice_data.get("slice_type", "paragraph"),
                "keywords": ",".join(slice_data.get("keywords", [])),
                "title": slice_data.get("title", ""),
            })
        
        # 使用 upsert，保证重新索引不会因相同 vector_id 重复写入失败。
        if ids:
            collection.upsert(
                ids=ids,
                documents=documents,
                metadatas=metadatas,
            )
        
        logger.info(f"Chroma 向量索引完成: doc_id={doc_id}, slices={len(slices)}")
        return ids
    
    @staticmethod
    def get_doc_list(
        db: Session,
        page: int = 1,
        page_size: int = 10,
        keyword: Optional[str] = None,
        industry: Optional[str] = None,
        status: Optional[str] = None,
    ) -> Tuple[List[KnowledgeDoc], int]:
        """
        获取文档列表
        
        Args:
            db: 数据库会话
            page: 页码
            page_size: 每页数量
            keyword: 关键词搜索
            industry: 行业过滤
            status: 状态过滤
            
        Returns:
            Tuple[文档列表, 总数]
        """
        query = db.query(KnowledgeDoc)
        
        # 关键词搜索
        if keyword:
            escaped_kw = _escape_like(keyword)
            query = query.filter(
                or_(
                    KnowledgeDoc.title.like(f"%{escaped_kw}%", escape="\\"),
                    KnowledgeDoc.category.like(f"%{escaped_kw}%", escape="\\"),
                    KnowledgeDoc.tags.like(f"%{escaped_kw}%", escape="\\"),
                )
            )
        
        # 行业过滤
        if industry:
            query = query.filter(KnowledgeDoc.industry == industry)
        
        # 状态过滤
        if status:
            query = query.filter(KnowledgeDoc.status == status)
        
        # 只显示启用的文档
        query = query.filter(KnowledgeDoc.is_enabled == True)
        
        # 计算总数
        total = query.count()
        
        # 分页
        items = query.order_by(KnowledgeDoc.created_at.desc()).offset(
            (page - 1) * page_size
        ).limit(page_size).all()
        
        return items, total

    @staticmethod
    def get_summary_stats(db: Session) -> Dict[str, int]:
        """获取启用文档的全库汇总，避免页面统计受当前分页影响。"""
        rows = db.query(
            KnowledgeDoc.status,
            sa_func.count(KnowledgeDoc.id).label("doc_count"),
            sa_func.coalesce(sa_func.sum(KnowledgeDoc.slice_count), 0).label("total_slices"),
            sa_func.coalesce(sa_func.sum(KnowledgeDoc.indexed_slice_count), 0).label("indexed_slices"),
        ).filter(
            KnowledgeDoc.is_enabled == True,
        ).group_by(KnowledgeDoc.status).all()

        summary = {
            "total_docs": 0,
            "indexed_docs": 0,
            "pending_docs": 0,
            "error_docs": 0,
            "total_slices": 0,
            "indexed_slices": 0,
        }
        for status, doc_count, total_slices, indexed_slices in rows:
            summary["total_docs"] += doc_count
            summary["total_slices"] += total_slices
            summary["indexed_slices"] += indexed_slices
            if status == "ready":
                summary["indexed_docs"] += doc_count
            elif status == "error":
                summary["error_docs"] += doc_count
            else:
                summary["pending_docs"] += doc_count

        return summary
    
    @staticmethod
    def get_doc_by_id(db: Session, doc_id: int) -> Optional[KnowledgeDoc]:
        """
        根据ID获取文档
        
        Args:
            db: 数据库会话
            doc_id: 文档ID
            
        Returns:
            文档对象或None
        """
        return db.query(KnowledgeDoc).filter(KnowledgeDoc.id == doc_id).first()
    
    @staticmethod
    def update_doc(db: Session, doc_id: int, update_data: KnowledgeDocUpdate) -> Optional[KnowledgeDoc]:
        """
        更新文档信息
        
        Args:
            db: 数据库会话
            doc_id: 文档ID
            update_data: 更新数据
            
        Returns:
            更新后的文档对象或None
        """
        doc = db.query(KnowledgeDoc).filter(KnowledgeDoc.id == doc_id).first()
        if not doc:
            return None
        
        # 更新可修改字段
        if update_data.title is not None:
            doc.title = update_data.title
        if update_data.industry is not None:
            doc.industry = update_data.industry
        if update_data.category is not None:
            doc.category = update_data.category
        if update_data.tags is not None:
            doc.tags = update_data.tags
        if update_data.is_enabled is not None:
            doc.is_enabled = update_data.is_enabled
        
        db.commit()
        db.refresh(doc)
        
        logger.info(f"更新文档: doc_id={doc_id}")
        
        return doc
    
    @staticmethod
    def delete_doc(db: Session, doc_id: int) -> bool:
        """
        删除文档（软删除）

        执行顺序：先删 Chroma 向量索引（外部资源），后软删 DB。
        若向量删除失败，仍软删 DB 以保证用户体验，但向量残留可通过
        reconcile_orphaned_vectors() 补偿清理。

        Args:
            db: 数据库会话
            doc_id: 文档ID

        Returns:
            是否删除成功
        """
        doc = db.query(KnowledgeDoc).filter(KnowledgeDoc.id == doc_id).first()
        if not doc:
            return False

        # 1. 先删向量索引（外部资源，更易失败）
        vector_deleted = KnowledgeService._delete_vectors_for_doc(doc_id)
        if not vector_deleted:
            logger.warning(
                f"文档 doc_id={doc_id} 向量索引删除失败，"
                f"DB 将软删但向量可能残留，可调用 reconcile_orphaned_vectors 清理"
            )

        # 2. 软删 DB（无论向量删除结果如何，都软删以保证用户体验）
        doc.is_enabled = False
        db.commit()

        logger.info(f"删除文档: doc_id={doc_id}, vector_deleted={vector_deleted}")

        return True

    @staticmethod
    def _delete_vectors_for_doc(doc_id: int) -> bool:
        """删除文档对应的 Chroma 向量索引

        Returns:
            True 表示成功删除或向量本不存在/Chroma 不可用；False 表示删除失败（异常）
        """
        if not _CHROMA_AVAILABLE:
            return True

        try:
            collection = _get_chroma_collection()
            if collection is None:
                return True
            collection.delete(where={"doc_id": str(doc_id)})
            logger.info(f"Chroma 向量索引已删除: doc_id={doc_id}")
            return True
        except Exception as e:
            logger.warning(f"Chroma 删除向量索引失败: doc_id={doc_id}, error={e}")
            return False

    @staticmethod
    def reindex_doc(db: Session, doc_id: int) -> Tuple[bool, str]:
        """Re-parse the persisted source document and rebuild its DB/vector slices."""
        doc = db.query(KnowledgeDoc).filter(
            KnowledgeDoc.id == doc_id,
            KnowledgeDoc.is_enabled == True,
        ).first()
        if not doc:
            return False, "文档不存在或已停用"

        source_path = Path(doc.file_path or "")
        if not source_path.is_absolute():
            source_path = Path(settings.KNOWLEDGE_DOC_DIR) / source_path.name
        if not source_path.exists():
            doc.status = "error"
            doc.error_message = "原始文档不存在，无法重新索引"
            db.commit()
            return False, doc.error_message

        try:
            raw_bytes = source_path.read_bytes()
            text_content = KnowledgeDocumentParser.extract(doc.file_name, raw_bytes)
            if not KnowledgeService._delete_vectors_for_doc(doc.id):
                return False, "旧向量索引删除失败，请稍后重试"
            if not KnowledgeService.process_doc(db, doc.id, text_content):
                return False, doc.error_message or "文档处理失败，请检查日志"
            return True, "重新索引完成"
        except Exception as exc:
            logger.error(f"重新索引失败: doc_id={doc_id}, error={exc}")
            doc.status = "error"
            doc.error_message = str(exc)
            db.commit()
            return False, str(exc)

    @staticmethod
    def reconcile_orphaned_vectors(db: Session) -> Dict[str, int]:
        """补偿对账：扫描所有已软删的文档，重试删除其可能残留的向量索引

        用于 delete_doc 时向量删除失败后的后续清理。
        可由定时任务或手动调用触发。

        Returns:
            {"scanned": N, "cleaned": M, "failed": K}
        """
        if not _CHROMA_AVAILABLE:
            return {"scanned": 0, "cleaned": 0, "failed": 0}

        deleted_docs = db.query(KnowledgeDoc).filter(KnowledgeDoc.is_enabled == False).all()

        scanned = len(deleted_docs)
        cleaned = 0
        failed = 0

        for doc in deleted_docs:
            if KnowledgeService._delete_vectors_for_doc(doc.id):
                cleaned += 1
            else:
                failed += 1

        logger.info(
            f"[补偿对账] 扫描 {scanned} 个软删文档，"
            f"清理 {cleaned} 个，失败 {failed} 个"
        )

        return {"scanned": scanned, "cleaned": cleaned, "failed": failed}
    
    @staticmethod
    def batch_delete(db: Session, doc_ids: List[int]) -> Tuple[int, int]:
        """
        批量删除文档
        
        Args:
            db: 数据库会话
            doc_ids: 文档ID列表
            
        Returns:
            Tuple[成功数量, 失败数量]
        """
        success_count = 0
        failed_count = 0
        
        for doc_id in doc_ids:
            if KnowledgeService.delete_doc(db, doc_id):
                success_count += 1
            else:
                failed_count += 1
        
        logger.info(f"批量删除: success={success_count}, failed={failed_count}")
        
        return success_count, failed_count
    
    @staticmethod
    def search(
        db: Session = None,
        search_request: KnowledgeSearchRequest = None,
        query: str = None,
        industry: str = None,
        top_k: int = 10,
        doc_id: int = None,
    ) -> List[Dict]:
        """
        知识库语义检索（Chroma 向量检索 + 数据库回填）
        
        支持两种调用方式：
        1. 旧版: search(db, search_request) → 返回 Tuple[List[KnowledgeSearchResult], float]
        2. 新版: search(db=db, query=..., industry=..., top_k=...) → 返回 List[Dict]
        
        Returns:
            检索结果列表
        """
        start_time = time.time()
        results = []
        
        # 解析参数：兼容两种调用方式
        if search_request is not None:
            query_text = search_request.query
            filter_industry = search_request.industry
            k = search_request.top_k
            filter_doc_id = search_request.doc_id
            min_similarity = search_request.min_similarity
            search_type = search_request.search_type
        else:
            query_text = query
            filter_industry = industry
            k = top_k
            filter_doc_id = doc_id
            min_similarity = DEFAULT_MIN_SIMILARITY
            search_type = "hybrid"
        
        if not query_text:
            return results
        
        try:
            has_indexed_slices = False
            if db:
                indexed_query = db.query(KnowledgeSlice.id).join(KnowledgeDoc).filter(
                    KnowledgeDoc.is_enabled == True,
                    KnowledgeDoc.status == "ready",
                    KnowledgeSlice.is_indexed == True,
                )
                if filter_industry:
                    indexed_query = indexed_query.filter(KnowledgeDoc.industry == filter_industry)
                if filter_doc_id:
                    indexed_query = indexed_query.filter(KnowledgeSlice.doc_id == filter_doc_id)
                has_indexed_slices = indexed_query.first() is not None

            # 1. Chroma 向量语义检索（如果可用）
            if (
                search_type in ("vector", "hybrid")
                and _CHROMA_AVAILABLE
                and has_indexed_slices
                and _chroma_warmed
            ):
                collection = _get_chroma_collection()
                
                if collection is not None:
                    # 构建 Chroma where 过滤（直接利用 metadata 原生过滤，省去 DB 查询）
                    where_conditions: List[Dict[str, Any]] = []
                    if filter_industry:
                        where_conditions.append({"industry": filter_industry})
                    if filter_doc_id:
                        where_conditions.append({"doc_id": str(filter_doc_id)})
                    
                    where_filter = None
                    if len(where_conditions) == 1:
                        where_filter = where_conditions[0]
                    elif len(where_conditions) > 1:
                        where_filter = {"$and": where_conditions}
                    
                    chroma_results = collection.query(
                        query_texts=[query_text],
                        n_results=k,
                        where=where_filter,
                    )
                    
                    # 2. 从数据库回填完整信息（批量查询避免 N+1）
                    if chroma_results and chroma_results.get("ids") and chroma_results["ids"][0]:
                        result_ids = chroma_results["ids"][0]
                        result_distances = chroma_results.get("distances", [[]])[0]
                        result_metadatas = chroma_results.get("metadatas", [[]])[0]
                        result_documents = chroma_results.get("documents", [[]])[0]

                        parsed_hits: List[Tuple[int, int, int, float, str, Dict]] = []
                        doc_id_set = set()
                        for i, vec_id in enumerate(result_ids):
                            parts = vec_id.split("_")
                            if len(parts) < 4:
                                continue
                            try:
                                slice_doc_id = int(parts[1])
                                slice_index = int(parts[3])
                            except ValueError:
                                continue
                            distance = result_distances[i] if i < len(result_distances) else 1.0
                            similarity = max(0, 1.0 - distance)
                            if similarity < min_similarity:
                                continue
                            content = result_documents[i] if i < len(result_documents) else ""
                            metadata = result_metadatas[i] if i < len(result_metadatas) else {}
                            parsed_hits.append((i, slice_doc_id, slice_index, similarity, content, metadata))
                            doc_id_set.add(slice_doc_id)

                        doc_map: Dict[int, KnowledgeDoc] = {}
                        slice_map: Dict[Tuple[int, int], KnowledgeSlice] = {}
                        if db and doc_id_set:
                            for d in db.query(KnowledgeDoc).filter(
                                KnowledgeDoc.id.in_(doc_id_set),
                                KnowledgeDoc.is_enabled == True,
                            ).all():
                                doc_map[d.id] = d

                            slice_pairs = [(doc_id, idx) for (_, doc_id, idx, _, _, _) in parsed_hits]
                            if slice_pairs:
                                for s in db.query(KnowledgeSlice).filter(
                                    KnowledgeSlice.doc_id.in_(doc_id_set)
                                ).all():
                                    key = (s.doc_id, s.slice_index)
                                    if key in set(slice_pairs):
                                        slice_map[key] = s

                        for i, slice_doc_id, slice_index, similarity, content, metadata in parsed_hits:
                            doc = doc_map.get(slice_doc_id)
                            slice_obj = slice_map.get((slice_doc_id, slice_index))
                            if doc is None or slice_obj is None:
                                logger.warning(
                                    f"跳过无法回填的向量: doc_id={slice_doc_id}, slice_index={slice_index}"
                                )
                                continue
                            keywords_raw = metadata.get("keywords", "")
                            keywords = keywords_raw.split(",") if keywords_raw else []

                            results.append({
                                "slice_id": slice_obj.id if slice_obj else None,
                                "doc_id": slice_doc_id,
                                "doc_title": doc.title if doc else metadata.get("title", ""),
                                "industry": doc.industry if doc else "",
                                "origin_type": doc.origin_type if doc else None,
                                "origin_resource_id": doc.origin_resource_id if doc else None,
                                "title": metadata.get("title", ""),
                                "content": content,
                                "similarity": round(similarity, 4),
                                "slice_index": slice_index,
                                "keywords": keywords,
                                "highlighted_content": content[:200] + "..." if len(content) > 200 else content,
                            })
            elif search_type in ("vector", "hybrid") and _CHROMA_AVAILABLE and not _chroma_warmed:
                logger.warning("Chroma 尚未预热，跳过向量检索并使用关键词降级")
            elif search_type in ("vector", "hybrid") and _CHROMA_AVAILABLE and db:
                logger.debug("没有已索引知识切片，跳过 Chroma 检索")
            elif search_type == "hybrid":
                logger.debug("Chroma 不可用，使用数据库关键词检索")
            
            # 3. 如果 Chroma 检索结果不足，fallback 到数据库关键词检索
            if search_type in ("keyword", "hybrid") and len(results) < k and db:
                remaining = k - len(results)
                existing_ids = {r["slice_id"] for r in results if r["slice_id"]}
                results.extend(
                    KnowledgeService._keyword_fallback(
                        db,
                        query_text,
                        remaining,
                        min_similarity,
                        industry=filter_industry,
                        doc_id=filter_doc_id,
                        existing_ids=existing_ids,
                    )
                )
            
        except Exception as e:
            logger.warning(f"Chroma 检索异常，降级为数据库检索: {e}")
            # 降级：纯数据库关键词检索
            if db and search_type in ("keyword", "hybrid"):
                results.extend(
                    KnowledgeService._keyword_fallback(
                        db,
                        query_text,
                        k,
                        min_similarity,
                        industry=filter_industry,
                        doc_id=filter_doc_id,
                    )
                )
        
        duration_ms = (time.time() - start_time) * 1000
        logger.info(f"知识库检索: query={query_text[:50]}..., results={len(results)}, duration={duration_ms:.0f}ms")
        
        return results
    
    @staticmethod
    def get_preview(
        db: Session,
        doc_id: int,
        slice_start: int = 0,
        slice_count: int = 20,
    ) -> Optional[KnowledgePreviewResponse]:
        """
        获取文档预览
        
        Args:
            db: 数据库会话
            doc_id: 文档ID
            slice_start: 起始切片序号
            slice_count: 切片数量
            
        Returns:
            预览响应或None
        """
        doc = KnowledgeService.get_doc_by_id(db, doc_id)
        if not doc:
            return None
        
        # 获取切片
        slices = db.query(KnowledgeSlice).filter(
            KnowledgeSlice.doc_id == doc_id
        ).order_by(KnowledgeSlice.slice_index).offset(
            slice_start
        ).limit(slice_count).all()
        
        slice_responses = [
            KnowledgeSliceResponse(
                id=s.id,
                doc_id=s.doc_id,
                slice_index=s.slice_index,
                slice_type=s.slice_type,
                title=s.title,
                content=s.content,
                word_count=s.word_count,
                is_indexed=s.is_indexed,
                quality_score=s.quality_score,
                keywords=s.keywords or [],
                reference_count=s.reference_count,
                created_at=s.created_at,
            )
            for s in slices
        ]
        
        return KnowledgePreviewResponse(
            doc_id=doc.id,
            title=doc.title,
            industry=doc.industry,
            total_slices=doc.slice_count,
            current_slice_start=slice_start,
            slices=slice_responses,
        )
    
    @staticmethod
    def trace_resource(db: Session, resource_id: int) -> Optional[KnowledgeTraceResult]:
        """
        知识溯源：根据资源ID反向查询来源知识库
        
        Args:
            db: 数据库会话
            resource_id: 资源ID
            
        Returns:
            溯源结果或None
        """
        resource = db.query(LearningResource).filter(
            LearningResource.id == resource_id
        ).first()
        
        if not resource:
            return None
        
        # 获取来源切片ID列表
        source_slice_ids = resource.source_slice_ids or []
        source_doc_ids = resource.source_doc_ids or []
        
        # 查询来源切片详情
        source_slices = []
        if source_slice_ids:
            slices = db.query(KnowledgeSlice).filter(
                KnowledgeSlice.id.in_(source_slice_ids)
            ).all()
            source_slices = [
                {
                    "id": s.id,
                    "doc_id": s.doc_id,
                    "content_preview": s.content[:100] + "...",
                    "relevance": "高",
                }
                for s in slices
            ]
        
        # 查询来源文档详情
        source_docs = []
        if source_doc_ids:
            docs = db.query(KnowledgeDoc).filter(
                KnowledgeDoc.id.in_(source_doc_ids)
            ).all()
            source_docs = [
                {
                    "id": d.id,
                    "title": d.title,
                    "industry": d.industry,
                    "author": d.author,
                    "version": d.version,
                }
                for d in docs
            ]
        
        # 构建溯源路径
        trace_path = [
            {
                "step": 1,
                "name": "学习资源",
                "id": resource_id,
                "type": "resource",
                "title": ResourceServiceHelper.safe_resource_title(resource),
            },
            {
                "step": 2,
                "name": "知识库切片",
                "count": len(source_slices),
                "type": "slices",
            },
            {
                "step": 3,
                "name": "原始文档",
                "count": len(source_docs),
                "type": "documents",
            },
        ]
        
        logger.info(f"知识溯源: resource_id={resource_id}, slices={len(source_slices)}, docs={len(source_docs)}")
        
        return {
            "resource": {
                "id": resource.id,
                "title": ResourceServiceHelper.safe_resource_title(resource),
                "type": resource.resource_type,
            },
            "source_slices": source_slices,
            "source_docs": source_docs,
            "trace_path": trace_path,
        }
    
    @staticmethod
    def get_industry_stats(db: Session) -> List[Dict[str, Any]]:
        """
        获取各行业知识库统计
        
        Args:
            db: 数据库会话
            
        Returns:
            各行业统计数据
        """
        # Single query with aggregation to avoid N+1
        from sqlalchemy import func as sa_func
        rows = db.query(
            KnowledgeDoc.industry,
            sa_func.count(KnowledgeDoc.id).label("doc_count"),
            sa_func.coalesce(sa_func.sum(KnowledgeDoc.slice_count), 0).label("total_slices"),
            sa_func.coalesce(sa_func.sum(KnowledgeDoc.indexed_slice_count), 0).label("indexed_slices"),
        ).filter(
            KnowledgeDoc.is_enabled == True,
        ).group_by(KnowledgeDoc.industry).all()
        
        stats_map = {}
        for industry, doc_count, total_slices, indexed_slices in rows:
            coverage_rate = (indexed_slices / total_slices * 100) if total_slices > 0 else 0
            stats_map[industry] = {
                "industry": industry,
                "doc_count": doc_count,
                "slice_count": total_slices,
                "indexed_count": indexed_slices,
                "coverage_rate": round(coverage_rate, 2),
            }
        
        stats = []
        for industry in KnowledgeService.SUPPORTED_INDUSTRIES:
            if industry in stats_map:
                stats.append(stats_map[industry])
            else:
                stats.append({
                    "industry": industry,
                    "doc_count": 0,
                    "slice_count": 0,
                    "indexed_count": 0,
                    "coverage_rate": 0,
                })
        
        return stats
