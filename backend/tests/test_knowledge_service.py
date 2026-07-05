"""
知识库服务层单元测试
测试范围：文档CRUD、切片管理、检索、溯源
"""
import pytest
from sqlalchemy.orm import Session

from app.services.knowledge_service import KnowledgeService
from app.schemas.knowledge import (
    KnowledgeDocCreate,
    KnowledgeDocUpdate,
    KnowledgeSearchRequest,
)
from app.models import KnowledgeDoc, KnowledgeSlice, DocStatusEnum, IndustryEnum


class TestKnowledgeDocCRUD:
    """知识库文档 CRUD 测试"""

    def test_create_doc_success(self, db_session: Session):
        """测试创建文档成功"""
        doc_data = KnowledgeDocCreate(
            title="测试文档",
            industry="人工智能训练",
            category="深度学习",
            source="测试来源",
            author="测试作者",
            tags=["测试", "AI"],
            file_name="test_doc.pdf",
            file_type="pdf",
            file_size=102400,
        )
        doc, file_path = KnowledgeService.create_doc(db_session, doc_data)
        
        assert doc is not None
        assert doc.title == "测试文档"
        assert doc.industry == "人工智能训练"
        assert doc.status == DocStatusEnum.UPLOADING.value
        assert file_path is not None

    def test_create_doc_duplicate_title(self, db_session: Session, sample_knowledge_doc: KnowledgeDoc):
        """测试创建重复标题文档"""
        doc_data = KnowledgeDocCreate(
            title="深度学习基础教程",  # 与 sample_knowledge_doc 相同
            industry="人工智能训练",
            category="深度学习",
            file_name="test_dup.pdf",
            file_type="pdf",
            file_size=102400,
        )
        doc, file_path = KnowledgeService.create_doc(db_session, doc_data)
        
        assert doc is None
        assert "已存在" in file_path

    def test_get_doc_list(self, db_session: Session, sample_knowledge_doc: KnowledgeDoc):
        """测试获取文档列表"""
        docs, total = KnowledgeService.get_doc_list(db_session, page=1, page_size=10)
        
        assert total >= 1
        assert any(d.id == sample_knowledge_doc.id for d in docs)

    def test_get_doc_list_by_industry(self, db_session: Session, sample_knowledge_doc: KnowledgeDoc):
        """测试按行业筛选文档"""
        docs, total = KnowledgeService.get_doc_list(
            db_session, page=1, page_size=10, industry="人工智能训练"
        )
        
        assert total >= 1
        for doc in docs:
            assert doc.industry == "人工智能训练"

    def test_get_doc_list_by_status(self, db_session: Session, sample_knowledge_doc: KnowledgeDoc):
        """测试按状态筛选文档"""
        docs, total = KnowledgeService.get_doc_list(
            db_session, page=1, page_size=10, status="ready"
        )
        
        assert total >= 1
        for doc in docs:
            assert doc.status == "ready"

    def test_get_doc_by_id(self, db_session: Session, sample_knowledge_doc: KnowledgeDoc):
        """测试根据ID获取文档"""
        doc = KnowledgeService.get_doc_by_id(db_session, sample_knowledge_doc.id)
        
        assert doc is not None
        assert doc.id == sample_knowledge_doc.id
        assert doc.title == sample_knowledge_doc.title

    def test_get_doc_not_found(self, db_session: Session):
        """测试获取不存在的文档"""
        doc = KnowledgeService.get_doc_by_id(db_session, 99999)
        assert doc is None

    def test_update_doc(self, db_session: Session, sample_knowledge_doc: KnowledgeDoc):
        """测试更新文档"""
        update_data = KnowledgeDocUpdate(
            title="更新后的标题",
            tags=["更新", "测试"],
        )
        doc = KnowledgeService.update_doc(db_session, sample_knowledge_doc.id, update_data)
        
        assert doc is not None
        assert doc.title == "更新后的标题"

    def test_update_doc_not_found(self, db_session: Session):
        """测试更新不存在的文档"""
        update_data = KnowledgeDocUpdate(title="无")
        doc = KnowledgeService.update_doc(db_session, 99999, update_data)
        
        assert doc is None

    def test_delete_doc(self, db_session: Session, sample_knowledge_doc: KnowledgeDoc):
        """测试删除文档（软删除）"""
        result = KnowledgeService.delete_doc(db_session, sample_knowledge_doc.id)
        
        assert result is True
        # 验证软删除：文档被标记为禁用
        doc = KnowledgeService.get_doc_by_id(db_session, sample_knowledge_doc.id)
        assert doc is not None
        assert doc.is_enabled is False

    def test_batch_delete(self, db_session: Session, sample_knowledge_doc: KnowledgeDoc):
        """测试批量删除"""
        success_count, failed_count = KnowledgeService.batch_delete(db_session, [sample_knowledge_doc.id])
        
        assert success_count >= 1
        assert failed_count == 0


class TestKnowledgeSearch:
    """知识库检索测试"""

    def test_search_by_keyword(self, db_session: Session, sample_knowledge_slices: list):
        """测试按关键词检索"""
        request = KnowledgeSearchRequest(
            query="卷积神经网络",
            top_k=5,
        )
        results = KnowledgeService.search(db_session, request)
        
        assert isinstance(results, list)
        assert len(results) > 0

    def test_search_by_industry(self, db_session: Session, sample_knowledge_slices: list):
        """测试按行业检索"""
        request = KnowledgeSearchRequest(
            query="CNN",
            top_k=5,
            industry="人工智能训练",
        )
        results = KnowledgeService.search(db_session, request)
        
        assert isinstance(results, list)

    def test_search_empty_result(self, db_session: Session):
        """测试无结果检索"""
        request = KnowledgeSearchRequest(
            query="不存在的关键词xyzabc123",
            top_k=5,
        )
        results = KnowledgeService.search(db_session, request)
        
        assert len(results) == 0


class TestKnowledgePreview:
    """知识库预览测试"""

    def test_get_preview(self, db_session: Session, sample_knowledge_doc: KnowledgeDoc):
        """测试获取文档预览"""
        preview = KnowledgeService.get_preview(db_session, sample_knowledge_doc.id)
        
        assert preview is not None
        assert preview.doc_id == sample_knowledge_doc.id
        assert preview.slices is not None

    def test_get_preview_not_found(self, db_session: Session):
        """测试预览不存在的文档"""
        preview = KnowledgeService.get_preview(db_session, 99999)
        assert preview is None


class TestKnowledgeTrace:
    """知识溯源测试"""

    def test_trace_resource(self, db_session: Session, sample_knowledge_doc: KnowledgeDoc):
        """测试资源溯源"""
        # 创建关联资源
        from app.models import LearningResource, ResourceTypeEnum, ResourceStatusEnum
        from app.models.learner_profile import LearnerProfile
        
        # 使用已有学习者或创建
        profile = db_session.query(LearnerProfile).first()
        if not profile:
            from app.models.user import User, UserRoleEnum
            user = User(
                username="trace_test",
                password_hash="hash",
                email="trace@test.com",
                role=UserRoleEnum.LEARNER,
            )
            db_session.add(user)
            db_session.flush()
            profile = LearnerProfile(
                user_id=user.id,
                real_name="溯源测试",
                education_level="本科",
                major="计算机",
            )
            db_session.add(profile)
            db_session.flush()
        
        resource = LearningResource(
            learner_id=profile.id,
            title="溯源测试资源",
            resource_type=ResourceTypeEnum.GUIDE.value,
            content="测试内容",
            source_doc_ids=[sample_knowledge_doc.id],
            source_slice_ids=[1],
            status=ResourceStatusEnum.READY.value,
        )
        db_session.add(resource)
        db_session.commit()
        
        result = KnowledgeService.trace_resource(db_session, resource.id)
        
        assert result is not None
        assert "resource" in result
        assert "source_docs" in result
        assert len(result["source_docs"]) >= 1

    def test_trace_resource_not_found(self, db_session: Session):
        """测试溯源不存在的资源"""
        result = KnowledgeService.trace_resource(db_session, 99999)
        assert result is None


class TestIndustryStats:
    """行业统计测试"""

    def test_get_industry_stats(self, db_session: Session, sample_knowledge_doc: KnowledgeDoc):
        """测试获取行业统计"""
        stats = KnowledgeService.get_industry_stats(db_session)
        
        assert isinstance(stats, list)
        assert len(stats) > 0
        
        # 验证统计结构
        for stat in stats:
            assert "industry" in stat
            assert "doc_count" in stat
            assert "slice_count" in stat