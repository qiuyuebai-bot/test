"""
pytest 全局配置与共享 fixtures
"""
import pytest
import os
import sys
from typing import Generator, Dict, Any

# 确保项目根目录在 sys.path 中
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from sqlalchemy import create_engine, text
from sqlalchemy.pool import StaticPool
from sqlalchemy.orm import sessionmaker, Session
from fastapi.testclient import TestClient

from app.database import Base, get_db
from app.main import app
from app.models import (
    User, UserRoleEnum,
    LearnerProfile, EducationLevelEnum, LearningStyleEnum,
    KnowledgeDoc, IndustryEnum, DocStatusEnum,
    KnowledgeSlice,
    AgentTask, AgentTypeEnum, TaskStatusEnum,
    LearningResource, ResourceTypeEnum, ResourceDifficultyEnum, ResourceStatusEnum,
    ResourceSection, SectionTypeEnum,
    ResourceExercise, ExerciseLevelEnum, ExerciseTypeEnum,
    ResourceTemplate, TemplateCategoryEnum,
    AnswerRecord, QuestionTypeEnum, AnswerResultEnum, AdaptiveDecisionEnum,
    TestMetrics,
)
from app.utils.auth import (
    hash_password,
    create_access_token,
    create_tokens_for_user,
    get_current_user,
    CurrentUser,
)


# ===========================================
# 测试数据库配置
# ===========================================

TEST_DATABASE_URL = "sqlite:///:memory:"


@pytest.fixture(scope="session")
def engine():
    """创建测试数据库引擎（session级别，整个测试会话共享）"""
    test_engine = create_engine(
        TEST_DATABASE_URL,
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
        echo=False,
    )
    Base.metadata.create_all(bind=test_engine)
    yield test_engine
    # 清理：内存数据库无需删除文件
    Base.metadata.drop_all(bind=test_engine)
    test_engine.dispose()


@pytest.fixture(scope="function")
def db_session(engine) -> Generator[Session, None, None]:
    """创建测试数据库会话（function级别，每个测试函数独立）"""
    TestSession = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    session = TestSession()
    
    # 清空所有表数据（使用原始SQL确保可靠清理）
    # 先启用外键约束（SQLite默认不启用）
    session.execute(text("PRAGMA foreign_keys = ON"))
    for table in reversed(Base.metadata.sorted_tables):
        session.execute(text(f"DELETE FROM {table.name}"))
    session.commit()
    
    yield session
    
    session.rollback()
    session.close()


@pytest.fixture(scope="function")
def client(db_session: Session) -> Generator[TestClient, None, None]:
    """创建FastAPI测试客户端"""
    from unittest.mock import patch
    from contextlib import contextmanager
    from app import database as db_module
    
    def override_get_db():
        try:
            yield db_session
        finally:
            pass
    
    @contextmanager
    def override_get_db_context():
        try:
            yield db_session
            db_session.commit()
        except Exception:
            db_session.rollback()
            raise
    
    app.dependency_overrides[get_db] = override_get_db
    
    # Patch get_db_context 使其使用测试数据库
    original_get_db_context = db_module.get_db_context
    db_module.get_db_context = override_get_db_context
    
    # 同时 patch 所有已经导入 get_db_context 的模块
    import importlib
    modules_to_patch = [
        'app.services.common',
        'app.domains.resource.service',
        'app.services.report_service',
        'app.services.tutoring_service',
        'app.agents.orchestrator',
    ]
    
    patchers = []
    for mod_name in modules_to_patch:
        try:
            mod = importlib.import_module(mod_name)
            if hasattr(mod, 'get_db_context'):
                patcher = patch.object(mod, 'get_db_context', override_get_db_context)
                patcher.start()
                patchers.append(patcher)
        except ImportError:
            pass
    
    with TestClient(app) as test_client:
        yield test_client
    
    # 清理
    for patcher in patchers:
        patcher.stop()
    db_module.get_db_context = original_get_db_context
    app.dependency_overrides.clear()


# ===========================================
# 测试数据 fixtures
# ===========================================

@pytest.fixture
def sample_user(db_session: Session) -> User:
    """创建测试用户（使用唯一用户名避免冲突）"""
    import uuid
    unique_suffix = uuid.uuid4().hex[:8]
    user = User(
        username=f"test_user_{unique_suffix}",
        password_hash=hash_password("test_password"),
        email=f"test_{unique_suffix}@example.com",
        role=UserRoleEnum.LEARNER,
        is_active=True,
        is_verified=True,
    )
    db_session.add(user)
    db_session.commit()
    db_session.refresh(user)
    return user


@pytest.fixture
def sample_admin_user(db_session: Session) -> User:
    """创建测试管理员用户"""
    user = User(
        username="admin_user",
        password_hash=hash_password("admin_password"),
        email="admin@example.com",
        role=UserRoleEnum.ADMIN,
        is_active=True,
        is_verified=True,
    )
    db_session.add(user)
    db_session.commit()
    db_session.refresh(user)
    return user


# ===========================================
# JWT 认证相关 fixtures
# ===========================================

@pytest.fixture
def auth_token(sample_user: User) -> str:
    """生成测试用户的访问Token"""
    token_data = {
        "user_id": sample_user.id,
        "username": sample_user.username,
        "role": sample_user.role.value if hasattr(sample_user.role, 'value') else sample_user.role,
    }
    return create_access_token(token_data)


@pytest.fixture
def admin_auth_token(sample_admin_user: User) -> str:
    """生成测试管理员的访问Token"""
    token_data = {
        "user_id": sample_admin_user.id,
        "username": sample_admin_user.username,
        "role": sample_admin_user.role.value if hasattr(sample_admin_user.role, 'value') else sample_admin_user.role,
    }
    return create_access_token(token_data)


@pytest.fixture
def auth_headers(auth_token: str) -> dict:
    """生成带认证Token的请求头"""
    return {"Authorization": f"Bearer {auth_token}"}


@pytest.fixture
def admin_auth_headers(admin_auth_token: str) -> dict:
    """生成管理员认证Token的请求头"""
    return {"Authorization": f"Bearer {admin_auth_token}"}


@pytest.fixture(autouse=True, scope="session")
def _disable_chroma_for_tests():
    """禁用 ChromaDB，避免测试时下载 79.3MB ONNX 模型。
    search() 会回退到数据库关键词 LIKE 检索路径。"""
    from app.domains.knowledge import service as ks
    original = ks._CHROMA_AVAILABLE
    ks._CHROMA_AVAILABLE = False
    ks._chroma_client = None
    ks._chroma_collection = None
    yield
    ks._CHROMA_AVAILABLE = original


@pytest.fixture
def client_with_auth(client: TestClient, auth_headers: dict) -> TestClient:
    """
    创建带认证的测试客户端
    注意: 需要在每个请求中手动添加headers
    """
    # 存储headers供测试使用
    client._auth_headers = auth_headers
    return client


@pytest.fixture
def current_user_fixture(sample_user: User) -> CurrentUser:
    """创建CurrentUser fixture"""
    return CurrentUser(
        user_id=sample_user.id,
        username=sample_user.username,
        role=sample_user.role.value if hasattr(sample_user.role, 'value') else sample_user.role,
    )


@pytest.fixture
def sample_learner_profile(db_session: Session, sample_user: User) -> LearnerProfile:
    """创建测试学习者画像"""
    profile = LearnerProfile(
        user_id=sample_user.id,
        real_name="测试学习者",
        display_name="Learner001",
        education_level=EducationLevelEnum.MASTER.value,
        major="计算机科学与技术",
        school="测试大学",
        graduation_year=2020,
        current_position="算法工程师",
        years_of_experience=3,
        learning_style=LearningStyleEnum.VISUAL.value,
        preferred_difficulty=3,
        daily_study_time=60,
        theoretical_foundation=75.0,
        programming_ability=80.0,
        algorithm_design=70.0,
        system_architecture=60.0,
        data_analysis=65.0,
        engineering_practice=72.0,
        knowledge_blind_areas=["模型蒸馏", "分布式训练"],
        knowledge_strengths=["Python编程", "机器学习基础"],
        learning_goal="掌握深度学习核心算法",
        target_industry="人工智能",
        target_position="高级算法工程师",
        learning_phase="growth",
        total_questions_answered=50,
        total_correct_rate=0.78,
    )
    db_session.add(profile)
    db_session.commit()
    db_session.refresh(profile)
    return profile


@pytest.fixture
def sample_knowledge_doc(db_session: Session) -> KnowledgeDoc:
    """创建测试知识库文档"""
    doc = KnowledgeDoc(
        title="深度学习基础教程",
        industry=IndustryEnum.AI_TRAINING.value,
        category="机器学习",
        file_name="deep_learning_basics.pdf",
        file_path="/data/test/deep_learning_basics.pdf",
        file_size=1024000,
        file_type="pdf",
        content_preview="深度学习是机器学习的一个分支...",
        total_pages=50,
        word_count=15000,
        slice_count=10,
        indexed_slice_count=10,
        status=DocStatusEnum.READY.value,
        source="学术论文汇编",
        version="1.0",
        author="测试作者",
        tags=["深度学习", "神经网络", "CNN"],
        is_enabled=True,
    )
    db_session.add(doc)
    db_session.commit()
    db_session.refresh(doc)
    return doc


@pytest.fixture
def sample_knowledge_slices(db_session: Session, sample_knowledge_doc: KnowledgeDoc) -> list:
    """创建测试知识库切片"""
    slices = []
    for i in range(3):
        s = KnowledgeSlice(
            doc_id=sample_knowledge_doc.id,
            slice_index=i,
            slice_type="paragraph",
            content=f"测试切片内容 {i}: 卷积神经网络(CNN)是一种前馈神经网络...",
            content_hash=f"hash_test_{i}",
            word_count=100,
            title=f"CNN基础 - 第{i}节",
            keywords=["CNN", "卷积", "神经网络"],
            is_indexed=True,
            quality_score=0.85,
        )
        slices.append(s)
        db_session.add(s)
    db_session.commit()
    for s in slices:
        db_session.refresh(s)
    return slices


@pytest.fixture
def sample_agent_task(db_session: Session, sample_learner_profile: LearnerProfile) -> AgentTask:
    """创建测试Agent任务"""
    task = AgentTask(
        learner_id=sample_learner_profile.id,
        task_name="测试资源生成任务",
        task_type="resource_generation",
        agent_type=AgentTypeEnum.GENERATION.value,
        flow_stage="generation",
        status=TaskStatusEnum.COMPLETED.value,
        progress=100,
        duration_ms=5000,
        result_summary="成功生成3类学习资源",
        needs_validation=True,
        validated=True,
        validation_passed=True,
    )
    db_session.add(task)
    db_session.commit()
    db_session.refresh(task)
    return task


@pytest.fixture
def sample_learning_resource(db_session: Session, sample_learner_profile: LearnerProfile) -> LearningResource:
    """创建测试学习资源"""
    resource = LearningResource(
        learner_id=sample_learner_profile.id,
        title="CNN入门实操指南",
        subtitle="从零开始掌握卷积神经网络",
        resource_type=ResourceTypeEnum.GUIDE.value,
        industry="人工智能",
        difficulty_level=3,
        estimated_duration=45,
        learning_objectives=["理解CNN基本原理", "掌握卷积操作", "实现简单CNN模型"],
        prerequisites=["Python基础", "线性代数"],
        content="# CNN入门指南\n\n## 第一节 卷积操作\n...",
        content_json={"sections": [{"title": "卷积操作", "content": "..."}]},
        summary="本指南帮助你从零开始掌握CNN",
        word_count=3000,
        section_count=5,
        status=ResourceStatusEnum.READY.value,
        version="1.0",
        is_validated=True,
        validation_passed=True,
        validation_score=0.92,
        match_score=0.88,
    )
    db_session.add(resource)
    db_session.commit()
    db_session.refresh(resource)
    return resource


@pytest.fixture
def sample_resource_section(db_session: Session, sample_learning_resource: LearningResource) -> ResourceSection:
    """创建测试资源章节"""
    section = ResourceSection(
        resource_id=sample_learning_resource.id,
        title="卷积操作详解",
        section_type=SectionTypeEnum.SECTION.value,
        sort_order=1,
        level=1,
        section_number="1.1",
        content="卷积操作是CNN的核心操作，通过滑动卷积核在输入特征图上进行运算...",
        word_count=500,
        learning_points=["卷积核", "步长", "填充", "特征图"],
        key_concepts=["卷积", "滤波器"],
        estimated_minutes=10,
    )
    db_session.add(section)
    db_session.commit()
    db_session.refresh(section)
    return section


@pytest.fixture
def sample_resource_exercise(db_session: Session, sample_learning_resource: LearningResource) -> ResourceExercise:
    """创建测试资源习题"""
    exercise = ResourceExercise(
        resource_id=sample_learning_resource.id,
        question_number=1,
        question_title="CNN基础概念",
        question_content="以下哪个不是CNN的常用层类型？",
        question_type=ExerciseTypeEnum.SINGLE_CHOICE.value,
        difficulty_level=ExerciseLevelEnum.BASIC.value,
        options=["卷积层", "池化层", "全连接层", "循环层"],
        correct_answer=[3],
        answer_explanation="循环层(RNN)是循环神经网络的结构，不是CNN的常用层类型。",
        knowledge_points=["CNN架构", "层类型"],
        score=10.0,
        estimated_minutes=3,
    )
    db_session.add(exercise)
    db_session.commit()
    db_session.refresh(exercise)
    return exercise


@pytest.fixture
def sample_resource_template(db_session: Session) -> ResourceTemplate:
    """创建测试资源模板"""
    template = ResourceTemplate(
        name="标准实操指南模板",
        template_code="guide_standard_v1",
        category=TemplateCategoryEnum.GUIDE.value,
        description="适用于生成实操指南的标准模板",
        section_schema=[
            {"name": "概述", "type": "section", "required": True, "order": 1},
            {"name": "核心概念", "type": "section", "required": True, "order": 2},
            {"name": "实操步骤", "type": "step", "required": True, "order": 3},
            {"name": "注意事项", "type": "tip", "required": False, "order": 4},
            {"name": "本章小结", "type": "summary", "required": True, "order": 5},
        ],
        prompt_template="请为{learner_name}生成一份关于{topic}的实操指南，难度等级{difficulty}...",
        output_format={"structure": "markdown", "include_toc": True},
        is_builtin=True,
        is_active=True,
    )
    db_session.add(template)
    db_session.commit()
    db_session.refresh(template)
    return template


@pytest.fixture
def sample_answer_record(db_session: Session, sample_user: User, sample_learner_profile: LearnerProfile) -> AnswerRecord:
    """创建测试答题记录"""
    record = AnswerRecord(
        user_id=sample_user.id,
        learner_id=sample_learner_profile.id,
        question_id=1,
        question_type=QuestionTypeEnum.SINGLE_CHOICE.value,
        question_topic="CNN基础",
        question_difficulty=3,
        question_content="以下哪个不是CNN的常用层类型？",
        user_answer=[3],
        correct_answer=[3],
        result=AnswerResultEnum.CORRECT.value,
        score=10.0,
        time_spent_ms=45000,
        agent_decision=AdaptiveDecisionEnum.ADVANCE.value,
        decision_reason="答题正确率较高，建议进阶",
        decision_confidence=0.85,
        session_id="test-session-001",
        sequence_index=1,
    )
    db_session.add(record)
    db_session.commit()
    db_session.refresh(record)
    return record


@pytest.fixture
def sample_test_metrics(db_session: Session) -> TestMetrics:
    """创建测试指标记录"""
    metrics = TestMetrics(
        record_date="2024-01-15",
        hallucination_rate=2.5,
        resource_match_accuracy=94.0,
        knowledge_coverage_rate=96.0,
        total_generated_content=100,
        hallucination_detected_count=3,
        hallucination_corrected_count=3,
        total_match_attempts=50,
        successful_match_count=47,
        total_knowledge_points=200,
        covered_knowledge_points=192,
        agent_task_count=30,
        agent_success_count=29,
        agent_avg_duration_ms=4500,
        active_learner_count=10,
        total_resources_generated=45,
    )
    db_session.add(metrics)
    db_session.commit()
    db_session.refresh(metrics)
    return metrics


# ===========================================
# 工具函数
# ===========================================

def assert_response_success(response_data: Dict[str, Any]) -> None:
    """断言API返回成功"""
    assert response_data.get("code") == 200, f"期望成功但返回: {response_data}"
    assert "data" in response_data


def assert_response_error(response_data: Dict[str, Any], expected_code: int = None) -> None:
    """断言API返回错误"""
    assert response_data.get("code") != 200, f"期望错误但返回成功: {response_data}"
    if expected_code is not None:
        assert response_data.get("code") == expected_code