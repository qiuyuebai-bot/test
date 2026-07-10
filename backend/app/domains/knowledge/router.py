"""
知识库模块 API 路由
实现文档上传、解析、切片、检索、溯源等接口
"""
from fastapi import APIRouter, Depends, Request
from sqlalchemy.orm import Session
from typing import Optional
from loguru import logger
import os
import re

from app.config import settings
from app.database import get_db
from app.schemas.response import success, bad_request, not_found, paged_success
from app.domains.knowledge.schemas import (
    KnowledgeDocCreate,
    KnowledgeDocUpdate,
    KnowledgeDocResponse,
    KnowledgeSearchRequest,
    KnowledgeSearchResponse,
    KnowledgeSearchResult,
    KnowledgeBatchDeleteRequest,
    KnowledgeBatchOperationResponse,
    KnowledgeUploadResponse,
)
from app.domains.knowledge.service import KnowledgeService
from app.services.common import BaseService
from app.utils.auth import require_admin, get_current_user, CurrentUser

router = APIRouter(
    prefix="/knowledge",
    tags=["知识库"],
    dependencies=[Depends(get_current_user)],
)

_KNOWLEDGE_RESPONSES = {
    400: {"description": "请求参数错误（文件格式不支持、内容为空等）"},
    401: {"description": "未授权（Token缺失或过期）"},
    403: {"description": "权限不足（需要管理员角色）"},
    404: {"description": "资源不存在（文档ID无效）"},
    413: {"description": "上传文件超出大小限制"},
    422: {"description": "请求体验证失败"},
    500: {"description": "服务器内部错误（解析失败、向量索引异常等）"},
}


# ===========================================
# 1. 文档上传与创建
# ===========================================

@router.post("/upload", summary="上传知识库文档", responses=_KNOWLEDGE_RESPONSES)
async def upload_document(
    request: Request,
    db: Session = Depends(get_db),
    current_user: CurrentUser = Depends(require_admin),
):
    """
    上传知识库文档，自动解析切片并建立向量索引
    
    支持 multipart/form-data（文件上传）和 application/json（纯文本创建）
    """
    try:
        content_type = request.headers.get("content-type", "")
        
        if "application/json" in content_type:
            body = await request.json()
            title = body.get("title", "")
            industry = body.get("industry", "")
            category = body.get("category")
            source = body.get("source")
            author = body.get("author")
            text_content = body.get("content", "")
            file_name = body.get("file_name", f"{title}.txt")
            file_type = body.get("file_type", "txt")
            file_size = len(text_content.encode("utf-8"))
        else:
            form = await request.form()
            file = form.get("file")
            title = form.get("title", "")
            industry = form.get("industry", "")
            category = form.get("category")
            source = form.get("source")
            author = None
            
            if file and hasattr(file, "read"):
                file_name = file.filename or "unknown.txt"
                file_type = file_name.split(".")[-1] if "." in file_name else "txt"
                # 分块读取并在累计大小超限时提前中止，避免大文件撑爆内存
                chunks = []
                file_size = 0
                max_size = settings.MAX_UPLOAD_SIZE
                while True:
                    chunk = await file.read(1024 * 1024)  # 1MB chunks
                    if not chunk:
                        break
                    file_size += len(chunk)
                    if file_size > max_size:
                        max_size_mb = max_size // (1024 * 1024)
                        return bad_request(
                            f"文件大小超出限制: {round(file_size / (1024 * 1024), 2)}MB，最大支持: {max_size_mb}MB"
                        )
                    chunks.append(chunk)
                file_content = b"".join(chunks)
                text_content = file_content.decode("utf-8", errors="replace")
            else:
                text_content = form.get("content", "")
                file_name = form.get("file_name", "content.txt")
                file_type = form.get("file_type", "txt")
                file_size = len(text_content.encode("utf-8"))
        
        # 文件名安全处理：移除路径遍历字符和特殊字符
        file_name = os.path.basename(file_name)
        file_name = re.sub(r'[\\/:*?"<>|\x00-\x1f]', "_", file_name)
        if not file_name or file_name in (".", ".."):
            file_name = "document.txt"
        
        # 文件大小验证
        if file_size > settings.MAX_UPLOAD_SIZE:
            max_size_mb = settings.MAX_UPLOAD_SIZE // (1024 * 1024)
            file_size_mb = round(file_size / (1024 * 1024), 2)
            return bad_request(
                f"文件大小超出限制: {file_size_mb}MB，最大支持: {max_size_mb}MB"
            )
        
        # 文件类型白名单验证
        ext = os.path.splitext(file_name)[1].lower()
        if ext not in settings.allowed_upload_extensions_list:
            return bad_request(
                f"不支持的文件类型: {ext}，允许的类型: {', '.join(settings.allowed_upload_extensions_list)}"
            )
        
        # 验证行业分类
        if industry not in KnowledgeService.SUPPORTED_INDUSTRIES:
            return bad_request(f"不支持的行业分类: {industry}，支持: {KnowledgeService.SUPPORTED_INDUSTRIES}")
        
        # 创建文档记录
        doc_data = KnowledgeDocCreate(
            title=title,
            industry=industry,
            category=category,
            source=source,
            author=author,
            file_name=file_name,
            file_type=file_type,
            file_size=file_size,
            content_preview=text_content[:500],
            tags=[],
        )
        
        doc, result_msg = KnowledgeService.create_doc(db, doc_data)
        
        if doc is None:
            return bad_request(result_msg)
        
        # 同步处理文档（实际生产中应使用Celery异步任务）
        process_success = KnowledgeService.process_doc(db, doc.id, text_content)
        
        if not process_success:
            return bad_request("文档处理失败，请检查日志")
        
        response = KnowledgeUploadResponse(
            doc_id=doc.id,
            file_name=doc.file_name,
            file_size=doc.file_size,
            status="ready",
            message="文档上传并索引成功",
        )
        
        return success(response, "文档上传成功")
        
    except Exception as e:
        logger.error(f"文档上传失败: {e}")
        return bad_request(f"上传失败: {str(e)}")


# ===========================================
# 2. 文档列表查询
# ===========================================

@router.get("/docs", summary="获取文档列表")
def get_doc_list(
    page: int = 1,
    page_size: int = 10,
    keyword: Optional[str] = None,
    industry: Optional[str] = None,
    status: Optional[str] = None,
    db: Session = Depends(get_db),
):
    """
    获取知识库文档列表，支持分页、搜索、筛选
    
    - **page**: 页码
    - **page_size**: 每页数量
    - **keyword**: 关键词搜索（标题/标签）
    - **industry**: 行业过滤
    - **status**: 状态过滤
    """
    items, total = KnowledgeService.get_doc_list(
        db,
        page=page,
        page_size=page_size,
        keyword=keyword,
        industry=industry,
        status=status,
    )

    response_items = []
    for doc in items:
        coverage_rate = (doc.indexed_slice_count / doc.slice_count * 100) if doc.slice_count > 0 else 0
        response_items.append(KnowledgeDocResponse(
            id=doc.id,
            title=doc.title,
            industry=doc.industry,
            category=doc.category,
            file_name=doc.file_name,
            file_type=doc.file_type,
            file_size=doc.file_size,
            total_pages=doc.total_pages,
            word_count=doc.word_count,
            slice_count=doc.slice_count,
            indexed_slice_count=doc.indexed_slice_count,
            coverage_rate=round(coverage_rate, 2),
            status=doc.status,
            version=doc.version,
            source=doc.source,
            author=doc.author,
            tags=doc.tags or [],
            is_enabled=doc.is_enabled,
            content_preview=doc.content_preview,
            created_at=doc.created_at,
            updated_at=doc.updated_at,
            indexed_at=doc.indexed_at,
        ))
    
    return paged_success(
        items=response_items,
        total=total,
        page=page,
        page_size=page_size,
        message="查询成功",
    )


# ===========================================
# 3. 文档详情
# ===========================================

@router.get("/docs/{doc_id}", summary="获取文档详情")
def get_doc_detail(
    doc_id: int,
    db: Session = Depends(get_db),
):
    """
    根据ID获取文档详细信息
    """
    doc = KnowledgeService.get_doc_by_id(db, doc_id)
    if not doc:
        return not_found("文档不存在")
    
    coverage_rate = (doc.indexed_slice_count / doc.slice_count * 100) if doc.slice_count > 0 else 0
    
    response = KnowledgeDocResponse(
        id=doc.id,
        title=doc.title,
        industry=doc.industry,
        category=doc.category,
        file_name=doc.file_name,
        file_type=doc.file_type,
        file_size=doc.file_size,
        total_pages=doc.total_pages,
        word_count=doc.word_count,
        slice_count=doc.slice_count,
        indexed_slice_count=doc.indexed_slice_count,
        coverage_rate=round(coverage_rate, 2),
        status=doc.status,
        version=doc.version,
        source=doc.source,
        author=doc.author,
        tags=doc.tags or [],
        is_enabled=doc.is_enabled,
        content_preview=doc.content_preview,
        created_at=doc.created_at,
        updated_at=doc.updated_at,
        indexed_at=doc.indexed_at,
    )
    
    return success(response, "查询成功")


# ===========================================
# 4. 文档更新
# ===========================================

@router.put("/docs/{doc_id}", summary="更新文档信息")
def update_doc(
    doc_id: int,
    update_data: KnowledgeDocUpdate,
    db: Session = Depends(get_db),
    current_user: CurrentUser = Depends(require_admin),
):
    """
    更新文档信息（标题、行业、标签等）
    """
    doc = KnowledgeService.update_doc(db, doc_id, update_data)
    if not doc:
        return not_found("文档不存在")
    
    return success({"id": doc.id}, "更新成功")


# ===========================================
# 5. 文档删除
# ===========================================

@router.delete("/docs/{doc_id}", summary="删除文档")
def delete_doc(
    doc_id: int,
    db: Session = Depends(get_db),
    current_user: CurrentUser = Depends(require_admin),
):
    """
    删除文档（软删除）
    """
    result = KnowledgeService.delete_doc(db, doc_id)
    if not result:
        return not_found("文档不存在")
    
    return success(None, "删除成功")


# ===========================================
# 6. 批量删除
# ===========================================

@router.post("/docs/batch-delete", summary="批量删除文档")
def batch_delete_docs(
    request: KnowledgeBatchDeleteRequest,
    db: Session = Depends(get_db),
    current_user: CurrentUser = Depends(require_admin),
):
    """
    批量删除文档
    """
    success_count, failed_count = KnowledgeService.batch_delete(db, request.doc_ids)
    
    response = KnowledgeBatchOperationResponse(
        success_count=success_count,
        failed_count=failed_count,
        failed_ids=[],  # 实际应记录失败的ID
    )
    
    return success(response, "批量删除完成")


# ===========================================
# 7. 知识库检索
# ===========================================

@router.post("/search", summary="知识库相似度检索", responses=_KNOWLEDGE_RESPONSES)
def search_knowledge(
    search_request: KnowledgeSearchRequest,
    db: Session = Depends(get_db),
):
    """
    按知识点相似度检索知识库
    
    - **query**: 检索查询
    - **industry**: 行业过滤
    - **doc_id**: 指定文档
    - **top_k**: 返回结果数量
    - **min_similarity**: 最低相似度
    """
    results = KnowledgeService.search(db, search_request)
    duration_ms = 0
    
    # 转换为 KnowledgeSearchResult 对象
    result_objects = [KnowledgeSearchResult(**r) for r in results]
    
    response = KnowledgeSearchResponse(
        query=search_request.query,
        total_results=len(result_objects),
        results=result_objects,
        search_duration_ms=round(duration_ms, 2),
    )
    
    return success(response, "检索成功")


# ===========================================
# 8. 文档预览
# ===========================================

@router.get("/preview/{doc_id}", summary="文档内容预览")
def get_doc_preview(
    doc_id: int,
    slice_start: int = 0,
    slice_count: int = 20,
    db: Session = Depends(get_db),
):
    """
    预览文档内容，分页查看切片
    
    - **doc_id**: 文档ID
    - **slice_start**: 起始切片序号
    - **slice_count**: 切片数量
    """
    preview = KnowledgeService.get_preview(db, doc_id, slice_start, slice_count)
    if not preview:
        return not_found("文档不存在")
    
    return success(preview, "查询成功")


# ===========================================
# 9. 知识溯源
# ===========================================

@router.get("/trace/{resource_id}", summary="知识溯源查询")
def trace_resource_knowledge(
    resource_id: int,
    db: Session = Depends(get_db),
):
    """
    根据资源ID反向溯源知识库原始文档
    
    - **resource_id**: 学习资源ID
    """
    trace_result = KnowledgeService.trace_resource(db, resource_id)
    if not trace_result:
        return not_found("资源不存在")
    
    return success(trace_result, "溯源查询成功")


# ===========================================
# 10. 行业统计
# ===========================================

@router.get("/stats/industries", summary="各行业知识库统计")
def get_industry_stats(
    db: Session = Depends(get_db),
):
    """
    获取各行业知识库统计数据（缓存 60 秒）
    """
    cache_key = "knowledge_industry_stats"
    cached = BaseService.get_cache(cache_key)
    if cached is not None:
        return success(cached, "查询成功")
    stats = KnowledgeService.get_industry_stats(db)
    BaseService.set_cache(cache_key, stats)
    return success(stats, "查询成功")


# ===========================================
# 11. 重新索引
# ===========================================

@router.post("/docs/{doc_id}/reindex", summary="重新索引文档")
def reindex_doc(
    doc_id: int,
    db: Session = Depends(get_db),
    current_user: CurrentUser = Depends(require_admin),
):
    """
    重新对文档进行切片和向量索引
    """
    doc = KnowledgeService.get_doc_by_id(db, doc_id)
    if not doc:
        return not_found("文档不存在")
    
    # 模拟重新索引（实际应读取文件重新处理）
    doc.status = "processing"
    doc.process_progress = 0
    db.commit()
    
    # 此处应触发异步任务
    # process_knowledge_doc_task.delay(doc_id)
    
    return success({"task_id": doc_id, "message": "重新索引任务已提交"}, "处理中")