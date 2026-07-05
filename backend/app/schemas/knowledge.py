"""
知识库相关数据验证 Schema
"""
from pydantic import BaseModel, Field, ConfigDict
from typing import Optional, List, Dict, Any
from datetime import datetime


# ===========================================
# 基础 Schema
# ===========================================

class KnowledgeDocBase(BaseModel):
    """知识库文档基础信息"""
    title: str = Field(..., min_length=1, max_length=200, description="文档标题")
    industry: str = Field(..., description="所属行业领域")
    category: Optional[str] = Field(None, max_length=100, description="分类标签")
    source: Optional[str] = Field(None, max_length=100, description="文档来源")
    author: Optional[str] = Field(None, max_length=100, description="作者")
    tags: List[str] = Field(default_factory=list, description="标签列表")


class KnowledgeDocCreate(KnowledgeDocBase):
    """创建文档请求"""
    file_name: str = Field(..., description="原始文件名")
    file_type: str = Field(..., description="文件类型")
    file_size: int = Field(..., gt=0, description="文件大小(字节)")
    content_preview: Optional[str] = Field(None, description="内容预览")


class KnowledgeDocUpdate(BaseModel):
    """更新文档请求"""
    title: Optional[str] = Field(None, min_length=1, max_length=200)
    industry: Optional[str] = None
    category: Optional[str] = None
    tags: Optional[List[str]] = None
    is_enabled: Optional[bool] = None


class KnowledgeDocResponse(BaseModel):
    """文档响应"""
    id: int
    title: str
    industry: str
    category: Optional[str] = None
    file_name: str
    file_type: Optional[str] = None
    file_size: Optional[int] = None
    total_pages: int = 0
    word_count: int = 0
    slice_count: int = 0
    indexed_slice_count: int = 0
    coverage_rate: float = 0.0
    status: str
    version: str
    source: Optional[str] = None
    author: Optional[str] = None
    tags: List[str] = []
    is_enabled: bool
    content_preview: Optional[str] = None
    created_at: datetime
    updated_at: datetime
    indexed_at: Optional[datetime] = None

    model_config = ConfigDict(from_attributes=True)


class KnowledgeDocListResponse(BaseModel):
    """文档列表响应"""
    items: List[KnowledgeDocResponse]
    total: int
    page: int
    page_size: int
    total_pages: int


# ===========================================
# 切片相关 Schema
# ===========================================

class KnowledgeSliceBase(BaseModel):
    """知识库切片基础信息"""
    doc_id: int = Field(..., description="关联文档ID")
    content: str = Field(..., min_length=1, description="切片内容")
    title: Optional[str] = Field(None, max_length=200, description="切片标题")
    parent_section: Optional[str] = Field(None, max_length=200, description="父级章节")
    slice_type: str = Field(default="paragraph", description="切片类型")


class KnowledgeSliceCreate(KnowledgeSliceBase):
    """创建切片请求"""
    slice_index: int = Field(..., ge=0, description="切片序号")
    keywords: List[str] = Field(default_factory=list, description="关键词列表")
    content_hash: Optional[str] = None


class KnowledgeSliceResponse(BaseModel):
    """切片响应"""
    id: int
    doc_id: int
    slice_index: int
    slice_type: str
    title: Optional[str] = None
    content: str
    word_count: int = 0
    is_indexed: bool
    quality_score: float = 0.0
    keywords: List[str] = []
    reference_count: int = 0
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


# ===========================================
# 检索相关 Schema
# ===========================================

class KnowledgeSearchRequest(BaseModel):
    """知识库检索请求"""
    query: str = Field(..., min_length=1, max_length=500, description="检索查询")
    industry: Optional[str] = Field(None, description="行业过滤")
    doc_id: Optional[int] = Field(None, description="指定文档ID")
    top_k: int = Field(default=5, ge=1, le=50, description="返回结果数量")
    min_similarity: float = Field(default=0.6, ge=0, le=1, description="最低相似度")
    search_type: str = Field(default="hybrid", description="检索类型(vector/keyword/hybrid)")


class KnowledgeSearchResult(BaseModel):
    """检索结果"""
    slice_id: int
    doc_id: int
    doc_title: str
    industry: str
    title: Optional[str] = None
    content: str
    similarity: float = Field(..., ge=0, le=1, description="相似度")
    slice_index: int
    keywords: List[str] = []
    highlighted_content: Optional[str] = None


class KnowledgeSearchResponse(BaseModel):
    """检索响应"""
    query: str
    total_results: int
    results: List[KnowledgeSearchResult]
    search_duration_ms: float


# ===========================================
# 知识溯源 Schema
# ===========================================

class KnowledgeTraceRequest(BaseModel):
    """知识溯源请求"""
    resource_id: int = Field(..., description="资源ID")


class KnowledgeTraceResult(BaseModel):
    """溯源结果"""
    resource_id: int
    resource_title: str
    resource_type: str
    source_slices: List[Dict[str, Any]]
    source_docs: List[Dict[str, Any]]
    trace_path: List[Dict[str, Any]]


# ===========================================
# 文档预览 Schema
# ===========================================

class KnowledgePreviewRequest(BaseModel):
    """文档预览请求"""
    doc_id: int
    slice_start: int = 0
    slice_count: int = 20


class KnowledgePreviewResponse(BaseModel):
    """文档预览响应"""
    doc_id: int
    title: str
    industry: str
    total_slices: int
    current_slice_start: int
    slices: List[KnowledgeSliceResponse]


# ===========================================
# 版本相关 Schema
# ===========================================

class KnowledgeVersionInfo(BaseModel):
    """版本信息"""
    version: str
    slice_count: int
    indexed_count: int
    created_at: datetime


# ===========================================
# 批量操作 Schema
# ===========================================

class KnowledgeBatchDeleteRequest(BaseModel):
    """批量删除请求"""
    doc_ids: List[int] = Field(..., min_length=1, max_length=100)


class KnowledgeBatchOperationResponse(BaseModel):
    """批量操作响应"""
    success_count: int
    failed_count: int
    failed_ids: List[int] = []


# ===========================================
# 文档上传响应 Schema
# ===========================================

class KnowledgeUploadResponse(BaseModel):
    """文档上传响应"""
    doc_id: int
    file_name: str
    file_size: int
    status: str
    message: str
    task_id: Optional[int] = None