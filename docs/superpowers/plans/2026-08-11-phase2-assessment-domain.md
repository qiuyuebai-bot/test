# Phase 2: Assessment 评估域实现计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 实现 Assessment 评估域，提供评估模板管理、评估记录创建/提交、胜任力评分明细计算和差距分析功能，与 Phase 1 的 Position/Competency 域联动。

**Architecture:** 遵循项目现有 DDD 分层结构（models → schemas → service → router），新域放在 `backend/app/domains/assessment/`。通过 Alembic 管理数据库迁移，通过 `models/__init__.py` 统一导出模型。评估流程基于规则引擎计算差距（AI 诊断报告作为后续 Phase 增强，本 Phase 仅实现结构化差距数据）。

**Tech Stack:** FastAPI, SQLAlchemy, Pydantic, Alembic, SQLite (开发) / PostgreSQL (生产)

## Global Constraints

- Python 3.12+, 使用项目现有 venv (`backend/venv/`)
- 遵循现有代码风格：loguru 日志、统一响应包装 (`success/error/bad_request/not_found`)、`get_current_user` 鉴权
- 数据库迁移通过 Alembic 管理，不手动改表
- 所有新模型必须在 `backend/app/models/__init__.py` 中导出
- 路由注册在 `backend/app/main.py` 中完成
- API 统一前缀 `/api/v1`
- 使用 `snake_case` 数据库字段名，API 响应通过现有 `keysToCamel` 中间件自动转换
- Service 层返回 `Dict[str, Any]`（与 Phase 1 Position 域保持一致，通过 service.py 顶部的包装函数解包 JSONResponse）
- 鉴权：读操作用 `get_current_user`，写操作用 `require_teacher`
- 评估状态机：`draft → in_progress → completed`（不可回退）

---

## File Structure

### 新建的文件

```
backend/app/domains/assessment/__init__.py      ← 空包初始化
backend/app/domains/assessment/models.py        ← AssessmentTemplate, AssessmentRecord, CompetencyScore ORM 模型
backend/app/domains/assessment/schemas.py       ← Pydantic 请求/响应 Schema
backend/app/domains/assessment/service.py       ← 业务逻辑层（含差距计算引擎）
backend/app/domains/assessment/router.py        ← API 路由定义
backend/tests/test_assessment_service.py        ← 单元测试
backend/alembic/versions/xxxx_add_assessment_domain_tables.py  ← Alembic 迁移
```

### 修改的文件

```
backend/app/main.py                           ← 注册 assessment_router
backend/app/models/__init__.py                ← 新增 Assessment 域模型导出
backend/app/middleware/audit.py               ← 新增 /assessments 资源类型映射
```

---

### Task 1: 创建 Assessment 域 ORM 模型

**Files:**
- Create: `backend/app/domains/assessment/__init__.py`
- Create: `backend/app/domains/assessment/models.py`
- Modify: `backend/app/models/__init__.py`

**Interfaces:**
- Consumes: `app.database.Base`, `app.models.user.User`, `app.domains.position.models.Position`, `app.domains.position.models.Competency`
- Produces: `AssessmentTemplate`, `AssessmentRecord`, `CompetencyScore` 模型类，供后续 schemas/service/router 使用

- [ ] **Step 1: 创建 `assessment/__init__.py`**

```python
# 空包初始化文件
```

- [ ] **Step 2: 创建 `assessment/models.py`**

```python
"""
评估域 ORM 模型
包含：评估模板、评估记录、胜任力评分明细
"""
from sqlalchemy import Column, Integer, String, Boolean, DateTime, Float, Text, JSON, ForeignKey, UniqueConstraint, Enum as SQLEnum
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from app.database import Base
import enum


class AssessmentStatusEnum(enum.Enum):
    """评估记录状态枚举"""
    DRAFT = "draft"              # 草稿（未开始）
    IN_PROGRESS = "in_progress"  # 进行中
    COMPLETED = "completed"      # 已完成
    EXPIRED = "expired"          # 已过期


class AssessmentMethodEnum(enum.Enum):
    """评估方式枚举"""
    QUIZ = "quiz"                # 测验
    SELF_REPORT = "self_report"  # 自评
    INTERVIEW = "interview"      # 面试
    PROJECT = "project"          # 项目


class AssessmentTemplate(Base):
    """评估模板表"""

    __tablename__ = "assessment_templates"

    id = Column(Integer, primary_key=True, autoincrement=True, comment="模板ID")
    position_id = Column(Integer, ForeignKey("positions.id", ondelete="CASCADE"), nullable=False, index=True, comment="关联岗位ID")
    name = Column(String(200), nullable=False, comment="模板名称")
    description = Column(Text, nullable=True, comment="模板描述")
    competency_configs = Column(JSON, default=list, comment="胜任力配置列表 [{competency_id, question_count, difficulty, assessment_method}]")
    pass_threshold = Column(Float, default=60.0, comment="通过分数线")
    duration_minutes = Column(Integer, nullable=True, comment="评估时长(分钟)")
    is_active = Column(Boolean, default=True, comment="是否启用")
    created_at = Column(DateTime, server_default=func.now(), comment="创建时间")
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now(), comment="更新时间")

    # 关联关系
    position = relationship("Position", backref="assessment_templates")
    records = relationship("AssessmentRecord", back_populates="template", cascade="all, delete-orphan")

    def __repr__(self) -> str:
        return f"<AssessmentTemplate(id={self.id}, name={self.name})>"


class AssessmentRecord(Base):
    """评估记录表"""

    __tablename__ = "assessment_records"

    id = Column(Integer, primary_key=True, autoincrement=True, comment="记录ID")
    template_id = Column(Integer, ForeignKey("assessment_templates.id", ondelete="CASCADE"), nullable=False, index=True, comment="模板ID")
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True, comment="用户ID")
    learner_id = Column(Integer, ForeignKey("learner_profiles.id", ondelete="SET NULL"), nullable=True, index=True, comment="学习者画像ID")
    position_id = Column(Integer, ForeignKey("positions.id", ondelete="CASCADE"), nullable=False, index=True, comment="岗位ID")
    status = Column(String(20), default=AssessmentStatusEnum.DRAFT.value, comment="评估状态")
    overall_score = Column(Float, nullable=True, comment="综合得分")
    overall_level = Column(Integer, nullable=True, comment="综合能力等级(1-5)")
    gap_summary = Column(JSON, default=list, comment="差距摘要 [{competency_id, competency_name, current_level, required_level, gap}]")
    ai_diagnosis = Column(Text, nullable=True, comment="AI生成的诊断报告")
    started_at = Column(DateTime, nullable=True, comment="开始时间")
    completed_at = Column(DateTime, nullable=True, comment="完成时间")
    created_at = Column(DateTime, server_default=func.now(), comment="创建时间")
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now(), comment="更新时间")

    # 关联关系
    template = relationship("AssessmentTemplate", back_populates="records")
    position = relationship("Position", backref="assessment_records")
    competency_scores = relationship("CompetencyScore", back_populates="record", cascade="all, delete-orphan")

    def __repr__(self) -> str:
        return f"<AssessmentRecord(id={self.id}, status={self.status})>"


class CompetencyScore(Base):
    """胜任力评分明细表"""

    __tablename__ = "competency_scores"
    __table_args__ = (
        UniqueConstraint("assessment_record_id", "competency_id", name="uq_record_competency"),
    )

    id = Column(Integer, primary_key=True, autoincrement=True, comment="评分ID")
    assessment_record_id = Column(Integer, ForeignKey("assessment_records.id", ondelete="CASCADE"), nullable=False, index=True, comment="评估记录ID")
    competency_id = Column(Integer, ForeignKey("competencies.id", ondelete="CASCADE"), nullable=False, index=True, comment="胜任力ID")
    current_level = Column(Integer, nullable=True, comment="当前等级(1-5)")
    current_score = Column(Float, nullable=True, comment="当前得分(0-100)")
    required_level = Column(Integer, nullable=False, comment="要求等级(1-5) 快照")
    gap = Column(Integer, nullable=True, comment="差距 = required_level - current_level")
    assessment_method = Column(String(20), nullable=True, comment="评估方式")
    evidence = Column(JSON, default=list, comment="评估依据(答题记录ID列表等)")
    created_at = Column(DateTime, server_default=func.now(), comment="创建时间")

    # 关联关系
    record = relationship("AssessmentRecord", back_populates="competency_scores")
    competency = relationship("Competency")

    def __repr__(self) -> str:
        return f"<CompetencyScore(record_id={self.assessment_record_id}, competency_id={self.competency_id}, gap={self.gap})>"
```

- [ ] **Step 3: 在 `models/__init__.py` 中导出新模型**

在 `backend/app/models/__init__.py` 中，在 Position 域导出之后添加：

```python
# 评估相关模型
from app.domains.assessment.models import AssessmentTemplate, AssessmentRecord, CompetencyScore
from app.domains.assessment.models import AssessmentStatusEnum, AssessmentMethodEnum
```

并在 `__all__` 中添加（在 PositionCompetency 之后）：
```python
"AssessmentTemplate",
"AssessmentRecord",
"CompetencyScore",
"AssessmentStatusEnum",
"AssessmentMethodEnum",
```

- [ ] **Step 4: 验证模型能正确导入**

```bash
cd backend
.\venv\Scripts\python.exe -c "from app.models import AssessmentTemplate, AssessmentRecord, CompetencyScore; print('OK')"
```

Expected: 输出 `OK`

- [ ] **Step 5: 提交**

```bash
git add backend/app/domains/assessment/ backend/app/models/__init__.py
git commit -m "feat(assessment): add AssessmentTemplate, AssessmentRecord, CompetencyScore ORM models"
```

---

### Task 2: 创建 Alembic 迁移脚本

**Files:**
- Create: `backend/alembic/versions/xxxx_add_assessment_domain_tables.py` (通过 alembic autogenerate)

**Interfaces:**
- Consumes: Task 1 的模型变更
- Produces: 数据库中 `assessment_templates`、`assessment_records`、`competency_scores` 三张表被创建

- [ ] **Step 1: 生成迁移脚本**

```bash
cd backend
.\venv\Scripts\python.exe -m alembic revision --autogenerate -m "add assessment domain tables"
```

- [ ] **Step 2: 检查生成的迁移脚本**

打开生成的迁移脚本，确认：
1. `upgrade()` 中包含创建 `assessment_templates`、`assessment_records`、`competency_scores` 三张表
2. 三张表的外键、唯一约束、索引正确
3. `downgrade()` 中包含 `op.drop_table('competency_scores')`、`op.drop_table('assessment_records')`、`op.drop_table('assessment_templates')`（注意删除顺序：先子表后父表）

如果 autogenerate 遗漏了某些内容，手动补充。

- [ ] **Step 3: 执行迁移**

```bash
cd backend
.\venv\Scripts\python.exe -m alembic upgrade head
```

Expected: 输出 `Running upgrade ... -> xxxx, add assessment domain tables`

- [ ] **Step 4: 验证表结构**

```bash
cd backend
.\venv\Scripts\python.exe -c "
from app.database import engine
from sqlalchemy import inspect
insp = inspect(engine)
tables = insp.get_table_names()
print('assessment_templates' in tables, 'assessment_records' in tables, 'competency_scores' in tables)
"
```

Expected: `True True True`

- [ ] **Step 5: 提交**

```bash
git add backend/alembic/versions/
git commit -m "db: add assessment domain tables migration"
```

---

### Task 3: 创建 Pydantic Schemas

**Files:**
- Create: `backend/app/domains/assessment/schemas.py`

**Interfaces:**
- Consumes: `app.domains.assessment.models` 中的模型类
- Produces: `AssessmentTemplateCreate`, `AssessmentTemplateUpdate`, `AssessmentTemplateResponse`, `AssessmentRecordResponse`, `CompetencyScoreResponse`, `GapAnalysisResponse` 等 Schema

- [ ] **Step 1: 创建 `schemas.py`**

```python
"""
评估域 Pydantic Schemas
"""
from typing import Optional, List, Any
from datetime import datetime
from pydantic import BaseModel, Field


# ===========================================
# 评估模板 Schemas
# ===========================================

class CompetencyConfig(BaseModel):
    """胜任力配置项（模板内的元素）"""
    competency_id: int = Field(..., description="胜任力ID")
    question_count: int = Field(5, ge=1, description="题目数量")
    difficulty: int = Field(3, ge=1, le=5, description="难度等级(1-5)")
    assessment_method: str = Field("quiz", description="评估方式: quiz/self_report/interview/project")


class AssessmentTemplateBase(BaseModel):
    position_id: int = Field(..., description="关联岗位ID")
    name: str = Field(..., max_length=200, description="模板名称")
    description: Optional[str] = None
    competency_configs: List[CompetencyConfig] = Field(default_factory=list, description="胜任力配置列表")
    pass_threshold: float = Field(60.0, ge=0, le=100, description="通过分数线")
    duration_minutes: Optional[int] = Field(None, ge=1, description="评估时长(分钟)")


class AssessmentTemplateCreate(AssessmentTemplateBase):
    pass


class AssessmentTemplateUpdate(BaseModel):
    name: Optional[str] = Field(None, max_length=200)
    description: Optional[str] = None
    competency_configs: Optional[List[CompetencyConfig]] = None
    pass_threshold: Optional[float] = Field(None, ge=0, le=100)
    duration_minutes: Optional[int] = Field(None, ge=1)
    is_active: Optional[bool] = None


class AssessmentTemplateResponse(AssessmentTemplateBase):
    id: int
    is_active: bool
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


# ===========================================
# 胜任力评分 Schemas
# ===========================================

class CompetencyScoreResponse(BaseModel):
    id: int
    assessment_record_id: int
    competency_id: int
    competency_name: Optional[str] = None
    competency_code: Optional[str] = None
    current_level: Optional[int] = None
    current_score: Optional[float] = None
    required_level: int
    gap: Optional[int] = None
    assessment_method: Optional[str] = None
    evidence: Optional[List[Any]] = None
    created_at: datetime

    class Config:
        from_attributes = True


# ===========================================
# 评估记录 Schemas
# ===========================================

class AssessmentStartRequest(BaseModel):
    """开始评估请求"""
    template_id: int = Field(..., description="评估模板ID")
    learner_id: Optional[int] = Field(None, description="学习者画像ID")


class AssessmentSubmitRequest(BaseModel):
    """提交评估请求"""
    scores: List[dict] = Field(..., description="评分列表 [{competency_id, current_level, current_score, assessment_method, evidence}]")


class AssessmentRecordResponse(BaseModel):
    id: int
    template_id: int
    user_id: int
    learner_id: Optional[int] = None
    position_id: int
    status: str
    overall_score: Optional[float] = None
    overall_level: Optional[int] = None
    gap_summary: Optional[List[dict]] = None
    ai_diagnosis: Optional[str] = None
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class AssessmentRecordDetailResponse(AssessmentRecordResponse):
    """评估记录详情（含评分明细和模板信息）"""
    competency_scores: List[CompetencyScoreResponse] = Field(default_factory=list)
    template_name: Optional[str] = None
    position_name: Optional[str] = None


# ===========================================
# 差距分析响应
# ===========================================

class GapItem(BaseModel):
    """单项差距"""
    competency_id: int
    competency_name: str
    competency_code: Optional[str] = None
    current_level: Optional[int] = None
    required_level: int
    gap: int
    is_met: bool


class GapAnalysisResponse(BaseModel):
    """差距分析响应"""
    record_id: int
    overall_score: Optional[float] = None
    overall_level: Optional[int] = None
    pass_threshold: float
    is_passed: bool
    total_competencies: int
    met_count: int
    gap_count: int
    gaps: List[GapItem]
```

- [ ] **Step 2: 验证 Schema 能正确导入**

```bash
cd backend
.\venv\Scripts\python.exe -c "from app.domains.assessment.schemas import AssessmentTemplateCreate, AssessmentStartRequest, GapAnalysisResponse; print('OK')"
```

Expected: `OK`

- [ ] **Step 3: 提交**

```bash
git add backend/app/domains/assessment/schemas.py
git commit -m "feat(assessment): add Pydantic schemas for assessment domain"
```

---

### Task 4: 创建 Service 层

**Files:**
- Create: `backend/app/domains/assessment/service.py`
- Create: `backend/tests/test_assessment_service.py`

**Interfaces:**
- Consumes: `app.domains.assessment.models`, `app.domains.assessment.schemas`, `app.database.get_db`, `app.domains.position.models.Position/Competency/PositionCompetency`
- Produces: `AssessmentService` 类（静态方法），供 router 调用

- [ ] **Step 1: 编写 Service 单元测试**

创建 `backend/tests/test_assessment_service.py`：

```python
"""Assessment 域 Service 单元测试"""
import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.database import Base
from app.domains.position.models import Position, Competency, PositionCompetency
from app.domains.assessment.models import (
    AssessmentTemplate, AssessmentRecord, CompetencyScore,
    AssessmentStatusEnum,
)
from app.domains.assessment.schemas import (
    AssessmentTemplateCreate, AssessmentTemplateUpdate,
    AssessmentStartRequest, AssessmentSubmitRequest,
)
from app.domains.assessment.service import AssessmentService


@pytest.fixture
def db():
    """内存 SQLite 测试数据库"""
    engine = create_engine("sqlite:///:memory:", echo=False)
    Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine)
    session = Session()
    yield session
    session.close()


@pytest.fixture
def position_with_competencies(db):
    """创建带胜任力的岗位，返回 (position_id, [competency_id, ...])"""
    pos = Position(code="FE-001", name="前端工程师", category="technical", level="junior")
    db.add(pos)
    db.commit()
    db.refresh(pos)

    comp_ids = []
    for code, name in [("HTML", "HTML基础"), ("CSS", "CSS样式"), ("JS", "JavaScript编程")]:
        comp = Competency(code=code, name=name, category="technical")
        db.add(comp)
        db.commit()
        db.refresh(comp)
        pc = PositionCompetency(position_id=pos.id, competency_id=comp.id, required_level=3)
        db.add(pc)
        comp_ids.append(comp.id)
    db.commit()
    return pos.id, comp_ids


class TestAssessmentTemplateService:
    def test_create_template(self, db, position_with_competencies):
        pos_id, comp_ids = position_with_competencies
        data = AssessmentTemplateCreate(
            position_id=pos_id,
            name="前端初级评估",
            competency_configs=[
                {"competency_id": comp_ids[0], "question_count": 5, "difficulty": 2, "assessment_method": "quiz"},
                {"competency_id": comp_ids[1], "question_count": 3, "difficulty": 2, "assessment_method": "quiz"},
            ],
            pass_threshold=60.0,
        )
        result = AssessmentService.create_template(db, data)
        assert result["code"] == 200
        assert result["data"]["name"] == "前端初级评估"
        assert result["data"]["position_id"] == pos_id
        assert len(result["data"]["competency_configs"]) == 2

    def test_create_template_invalid_position(self, db):
        data = AssessmentTemplateCreate(position_id=999, name="无效模板")
        result = AssessmentService.create_template(db, data)
        assert result["code"] == 404

    def test_get_template_list(self, db, position_with_competencies):
        pos_id, _ = position_with_competencies
        AssessmentService.create_template(db, AssessmentTemplateCreate(position_id=pos_id, name="模板1"))
        AssessmentService.create_template(db, AssessmentTemplateCreate(position_id=pos_id, name="模板2"))
        result = AssessmentService.get_template_list(db, page=1, page_size=10)
        assert result["code"] == 200
        assert result["data"]["total"] == 2

    def test_get_template_list_by_position(self, db, position_with_competencies):
        pos_id, _ = position_with_competencies
        # 创建另一个岗位
        pos2 = Position(code="BE-001", name="后端工程师")
        db.add(pos2)
        db.commit()
        db.refresh(pos2)

        AssessmentService.create_template(db, AssessmentTemplateCreate(position_id=pos_id, name="前端模板"))
        AssessmentService.create_template(db, AssessmentTemplateCreate(position_id=pos2.id, name="后端模板"))
        result = AssessmentService.get_template_list(db, page=1, page_size=10, position_id=pos_id)
        assert result["data"]["total"] == 1

    def test_get_template_by_id(self, db, position_with_competencies):
        pos_id, _ = position_with_competencies
        create_result = AssessmentService.create_template(db, AssessmentTemplateCreate(position_id=pos_id, name="模板"))
        tid = create_result["data"]["id"]
        result = AssessmentService.get_template_by_id(db, tid)
        assert result["code"] == 200
        assert result["data"]["name"] == "模板"

    def test_update_template(self, db, position_with_competencies):
        pos_id, _ = position_with_competencies
        create_result = AssessmentService.create_template(db, AssessmentTemplateCreate(position_id=pos_id, name="旧名称"))
        tid = create_result["data"]["id"]
        result = AssessmentService.update_template(db, tid, AssessmentTemplateUpdate(name="新名称", pass_threshold=75.0))
        assert result["code"] == 200
        assert result["data"]["name"] == "新名称"
        assert result["data"]["pass_threshold"] == 75.0

    def test_delete_template(self, db, position_with_competencies):
        pos_id, _ = position_with_competencies
        create_result = AssessmentService.create_template(db, AssessmentTemplateCreate(position_id=pos_id, name="模板"))
        tid = create_result["data"]["id"]
        result = AssessmentService.delete_template(db, tid)
        assert result["code"] == 200


class TestAssessmentRecordService:
    def test_start_assessment(self, db, position_with_competencies):
        pos_id, comp_ids = position_with_competencies
        tpl_result = AssessmentService.create_template(db, AssessmentTemplateCreate(
            position_id=pos_id,
            name="评估模板",
            competency_configs=[{"competency_id": cid, "question_count": 3} for cid in comp_ids],
        ))
        tid = tpl_result["data"]["id"]
        result = AssessmentService.start_assessment(db, user_id=1, template_id=tid, learner_id=None)
        assert result["code"] == 200
        assert result["data"]["status"] == "in_progress"
        assert result["data"]["position_id"] == pos_id

    def test_start_assessment_invalid_template(self, db):
        result = AssessmentService.start_assessment(db, user_id=1, template_id=999, learner_id=None)
        assert result["code"] == 404

    def test_submit_assessment(self, db, position_with_competencies):
        pos_id, comp_ids = position_with_competencies
        tpl_result = AssessmentService.create_template(db, AssessmentTemplateCreate(
            position_id=pos_id,
            name="评估模板",
            competency_configs=[{"competency_id": cid, "question_count": 3} for cid in comp_ids],
        ))
        tid = tpl_result["data"]["id"]
        start_result = AssessmentService.start_assessment(db, user_id=1, template_id=tid)
        rid = start_result["data"]["id"]

        scores = [
            {"competency_id": comp_ids[0], "current_level": 3, "current_score": 75, "assessment_method": "quiz"},
            {"competency_id": comp_ids[1], "current_level": 2, "current_score": 50, "assessment_method": "quiz"},
            {"competency_id": comp_ids[2], "current_level": 4, "current_score": 90, "assessment_method": "quiz"},
        ]
        result = AssessmentService.submit_assessment(db, rid, AssessmentSubmitRequest(scores=scores))
        assert result["code"] == 200
        assert result["data"]["status"] == "completed"
        assert result["data"]["overall_score"] is not None
        assert len(result["data"]["competency_scores"]) == 3

    def test_submit_assessment_invalid_record(self, db):
        result = AssessmentService.submit_assessment(db, 999, AssessmentSubmitRequest(scores=[]))
        assert result["code"] == 404

    def test_get_record_detail(self, db, position_with_competencies):
        pos_id, comp_ids = position_with_competencies
        tpl_result = AssessmentService.create_template(db, AssessmentTemplateCreate(
            position_id=pos_id, name="模板",
            competency_configs=[{"competency_id": comp_ids[0], "question_count": 3}],
        ))
        tid = tpl_result["data"]["id"]
        start_result = AssessmentService.start_assessment(db, user_id=1, template_id=tid)
        rid = start_result["data"]["id"]
        result = AssessmentService.get_record_detail(db, rid)
        assert result["code"] == 200
        assert result["data"]["id"] == rid

    def test_get_record_list(self, db, position_with_competencies):
        pos_id, _ = position_with_competencies
        tpl_result = AssessmentService.create_template(db, AssessmentTemplateCreate(position_id=pos_id, name="模板"))
        tid = tpl_result["data"]["id"]
        AssessmentService.start_assessment(db, user_id=1, template_id=tid)
        AssessmentService.start_assessment(db, user_id=2, template_id=tid)
        result = AssessmentService.get_record_list(db, page=1, page_size=10)
        assert result["data"]["total"] == 2

    def test_get_record_list_by_user(self, db, position_with_competencies):
        pos_id, _ = position_with_competencies
        tpl_result = AssessmentService.create_template(db, AssessmentTemplateCreate(position_id=pos_id, name="模板"))
        tid = tpl_result["data"]["id"]
        AssessmentService.start_assessment(db, user_id=1, template_id=tid)
        AssessmentService.start_assessment(db, user_id=2, template_id=tid)
        result = AssessmentService.get_record_list(db, page=1, page_size=10, user_id=1)
        assert result["data"]["total"] == 1


class TestGapAnalysisService:
    def test_gap_analysis_all_met(self, db, position_with_competencies):
        pos_id, comp_ids = position_with_competencies
        tpl_result = AssessmentService.create_template(db, AssessmentTemplateCreate(
            position_id=pos_id, name="模板", pass_threshold=60.0,
            competency_configs=[{"competency_id": cid, "question_count": 3} for cid in comp_ids],
        ))
        tid = tpl_result["data"]["id"]
        start_result = AssessmentService.start_assessment(db, user_id=1, template_id=tid)
        rid = start_result["data"]["id"]
        # 全部达到 required_level=3
        scores = [{"competency_id": cid, "current_level": 4, "current_score": 85} for cid in comp_ids]
        AssessmentService.submit_assessment(db, rid, AssessmentSubmitRequest(scores=scores))

        result = AssessmentService.get_gap_analysis(db, rid)
        assert result["code"] == 200
        assert result["data"]["met_count"] == 3
        assert result["data"]["gap_count"] == 0
        assert result["data"]["is_passed"] is True

    def test_gap_analysis_with_gaps(self, db, position_with_competencies):
        pos_id, comp_ids = position_with_competencies
        tpl_result = AssessmentService.create_template(db, AssessmentTemplateCreate(
            position_id=pos_id, name="模板", pass_threshold=60.0,
            competency_configs=[{"competency_id": cid, "question_count": 3} for cid in comp_ids],
        ))
        tid = tpl_result["data"]["id"]
        start_result = AssessmentService.start_assessment(db, user_id=1, template_id=tid)
        rid = start_result["data"]["id"]
        # 第一个达标，第二个差1级，第三个差2级
        scores = [
            {"competency_id": comp_ids[0], "current_level": 3, "current_score": 70},
            {"competency_id": comp_ids[1], "current_level": 2, "current_score": 45},
            {"competency_id": comp_ids[2], "current_level": 1, "current_score": 30},
        ]
        AssessmentService.submit_assessment(db, rid, AssessmentSubmitRequest(scores=scores))

        result = AssessmentService.get_gap_analysis(db, rid)
        assert result["code"] == 200
        assert result["data"]["met_count"] == 1
        assert result["data"]["gap_count"] == 2
        gaps = {g["competency_id"]: g for g in result["data"]["gaps"]}
        assert gaps[comp_ids[1]]["gap"] == 1
        assert gaps[comp_ids[2]]["gap"] == 2
        assert gaps[comp_ids[1]]["is_met"] is False

    def test_gap_analysis_not_completed(self, db, position_with_competencies):
        pos_id, _ = position_with_competencies
        tpl_result = AssessmentService.create_template(db, AssessmentTemplateCreate(position_id=pos_id, name="模板"))
        tid = tpl_result["data"]["id"]
        start_result = AssessmentService.start_assessment(db, user_id=1, template_id=tid)
        rid = start_result["data"]["id"]
        # 未提交，状态为 in_progress
        result = AssessmentService.get_gap_analysis(db, rid)
        assert result["code"] == 400
```

- [ ] **Step 2: 运行测试验证全部失败**

```bash
cd backend
.\venv\Scripts\python.exe -m pytest tests/test_assessment_service.py -v
```

Expected: 全部 FAIL（因为 `AssessmentService` 尚未实现）

- [ ] **Step 3: 创建 `service.py` 实现**

```python
"""
评估域 Service 层
"""
import json
from typing import Optional, Dict, Any, List
from datetime import datetime
from sqlalchemy.orm import Session
from sqlalchemy import or_

from app.domains.assessment.models import (
    AssessmentTemplate, AssessmentRecord, CompetencyScore,
    AssessmentStatusEnum,
)
from app.domains.assessment.schemas import (
    AssessmentTemplateCreate, AssessmentTemplateUpdate,
    AssessmentStartRequest, AssessmentSubmitRequest,
)
from app.domains.position.models import Position, Competency, PositionCompetency
from app.schemas.response import (
    success as _success,
    bad_request as _bad_request,
    not_found as _not_found,
)
from app.utils.logger import LoggerUtil


def _unwrap(resp) -> Dict[str, Any]:
    """将 JSONResponse 解包为 dict"""
    return json.loads(resp.body)


def success(data: Any = None, message: str = "操作成功") -> Dict[str, Any]:
    return _unwrap(_success(data=data, message=message))


def bad_request(message: str = "请求参数错误", data: Any = None) -> Dict[str, Any]:
    return _unwrap(_bad_request(message=message, data=data))


def not_found(message: str = "资源不存在") -> Dict[str, Any]:
    return _unwrap(_not_found(message=message))


class AssessmentService:
    """评估域服务"""

    # ===========================================
    # 评估模板 CRUD
    # ===========================================

    @staticmethod
    def create_template(db: Session, data: AssessmentTemplateCreate) -> Dict[str, Any]:
        position = db.query(Position).filter(Position.id == data.position_id).first()
        if not position:
            return not_found(message="岗位不存在")

        # 验证 competency_configs 中的胜任力ID存在
        for cfg in data.competency_configs:
            comp = db.query(Competency).filter(Competency.id == cfg.competency_id).first()
            if not comp:
                return bad_request(message=f"胜任力不存在: ID={cfg.competency_id}")

        tpl = AssessmentTemplate(
            position_id=data.position_id,
            name=data.name,
            description=data.description,
            competency_configs=[c.model_dump() for c in data.competency_configs],
            pass_threshold=data.pass_threshold,
            duration_minutes=data.duration_minutes,
        )
        db.add(tpl)
        db.commit()
        db.refresh(tpl)
        return success(data=AssessmentService._template_to_response(tpl), message="评估模板创建成功")

    @staticmethod
    def get_template_list(
        db: Session, page: int = 1, page_size: int = 20,
        position_id: Optional[int] = None, keyword: Optional[str] = None
    ) -> Dict[str, Any]:
        query = db.query(AssessmentTemplate)
        if position_id:
            query = query.filter(AssessmentTemplate.position_id == position_id)
        if keyword:
            query = query.filter(AssessmentTemplate.name.contains(keyword))
        total = query.count()
        items = query.offset((page - 1) * page_size).limit(page_size).all()
        return success(data={
            "items": [AssessmentService._template_to_response(t) for t in items],
            "total": total,
            "page": page,
            "page_size": page_size,
        })

    @staticmethod
    def get_template_by_id(db: Session, template_id: int) -> Dict[str, Any]:
        tpl = db.query(AssessmentTemplate).filter(AssessmentTemplate.id == template_id).first()
        if not tpl:
            return not_found(message="评估模板不存在")
        return success(data=AssessmentService._template_to_response(tpl))

    @staticmethod
    def update_template(db: Session, template_id: int, data: AssessmentTemplateUpdate) -> Dict[str, Any]:
        tpl = db.query(AssessmentTemplate).filter(AssessmentTemplate.id == template_id).first()
        if not tpl:
            return not_found(message="评估模板不存在")
        update_data = data.model_dump(exclude_unset=True)
        if "competency_configs" in update_data and update_data["competency_configs"]:
            update_data["competency_configs"] = [c.model_dump() if hasattr(c, "model_dump") else c for c in update_data["competency_configs"]]
        for key, value in update_data.items():
            setattr(tpl, key, value)
        db.commit()
        db.refresh(tpl)
        return success(data=AssessmentService._template_to_response(tpl), message="更新成功")

    @staticmethod
    def delete_template(db: Session, template_id: int) -> Dict[str, Any]:
        tpl = db.query(AssessmentTemplate).filter(AssessmentTemplate.id == template_id).first()
        if not tpl:
            return not_found(message="评估模板不存在")
        db.delete(tpl)
        db.commit()
        return success(message="删除成功")

    # ===========================================
    # 评估记录管理
    # ===========================================

    @staticmethod
    def start_assessment(
        db: Session, user_id: int, template_id: int, learner_id: Optional[int] = None
    ) -> Dict[str, Any]:
        tpl = db.query(AssessmentTemplate).filter(AssessmentTemplate.id == template_id).first()
        if not tpl:
            return not_found(message="评估模板不存在")
        if not tpl.is_active:
            return bad_request(message="评估模板已停用")

        record = AssessmentRecord(
            template_id=template_id,
            user_id=user_id,
            learner_id=learner_id,
            position_id=tpl.position_id,
            status=AssessmentStatusEnum.IN_PROGRESS.value,
            started_at=datetime.now(),
        )
        db.add(record)
        db.commit()
        db.refresh(record)
        return success(data=AssessmentService._record_to_response(record), message="评估已开始")

    @staticmethod
    def submit_assessment(
        db: Session, record_id: int, data: AssessmentSubmitRequest
    ) -> Dict[str, Any]:
        record = db.query(AssessmentRecord).filter(AssessmentRecord.id == record_id).first()
        if not record:
            return not_found(message="评估记录不存在")
        if record.status != AssessmentStatusEnum.IN_PROGRESS.value:
            return bad_request(message=f"评估记录状态不允许提交: {record.status}")

        # 获取岗位的胜任力要求（required_level 快照）
        position_competencies = db.query(PositionCompetency).filter(
            PositionCompetency.position_id == record.position_id
        ).all()
        required_map = {pc.competency_id: pc.required_level for pc in position_competencies}

        # 创建评分明细
        total_score = 0.0
        score_count = 0
        for score_data in data.scores:
            comp_id = score_data.get("competency_id")
            current_level = score_data.get("current_level")
            current_score = score_data.get("current_score")
            required_level = required_map.get(comp_id, 3)
            gap = (required_level - current_level) if current_level is not None else None

            cs = CompetencyScore(
                assessment_record_id=record_id,
                competency_id=comp_id,
                current_level=current_level,
                current_score=current_score,
                required_level=required_level,
                gap=gap,
                assessment_method=score_data.get("assessment_method", "quiz"),
                evidence=score_data.get("evidence", []),
            )
            db.add(cs)
            if current_score is not None:
                total_score += current_score
                score_count += 1

        # 计算综合得分和等级
        overall_score = round(total_score / score_count, 2) if score_count > 0 else 0.0
        overall_level = AssessmentService._score_to_level(overall_score)

        # 生成差距摘要
        gap_summary = AssessmentService._build_gap_summary(db, record_id, required_map)

        record.status = AssessmentStatusEnum.COMPLETED.value
        record.overall_score = overall_score
        record.overall_level = overall_level
        record.gap_summary = gap_summary
        record.completed_at = datetime.now()

        db.commit()
        db.refresh(record)
        return success(data=AssessmentService._record_detail_to_response(db, record), message="评估已提交")

    @staticmethod
    def get_record_detail(db: Session, record_id: int) -> Dict[str, Any]:
        record = db.query(AssessmentRecord).filter(AssessmentRecord.id == record_id).first()
        if not record:
            return not_found(message="评估记录不存在")
        return success(data=AssessmentService._record_detail_to_response(db, record))

    @staticmethod
    def get_record_list(
        db: Session, page: int = 1, page_size: int = 20,
        user_id: Optional[int] = None, position_id: Optional[int] = None,
        status: Optional[str] = None
    ) -> Dict[str, Any]:
        query = db.query(AssessmentRecord)
        if user_id:
            query = query.filter(AssessmentRecord.user_id == user_id)
        if position_id:
            query = query.filter(AssessmentRecord.position_id == position_id)
        if status:
            query = query.filter(AssessmentRecord.status == status)
        total = query.count()
        items = query.order_by(AssessmentRecord.created_at.desc()).offset((page - 1) * page_size).limit(page_size).all()
        return success(data={
            "items": [AssessmentService._record_to_response(r) for r in items],
            "total": total,
            "page": page,
            "page_size": page_size,
        })

    # ===========================================
    # 差距分析
    # ===========================================

    @staticmethod
    def get_gap_analysis(db: Session, record_id: int) -> Dict[str, Any]:
        record = db.query(AssessmentRecord).filter(AssessmentRecord.id == record_id).first()
        if not record:
            return not_found(message="评估记录不存在")
        if record.status != AssessmentStatusEnum.COMPLETED.value:
            return bad_request(message="评估尚未完成，无法生成差距分析")

        tpl = db.query(AssessmentTemplate).filter(AssessmentTemplate.id == record.template_id).first()
        pass_threshold = tpl.pass_threshold if tpl else 60.0

        scores = db.query(CompetencyScore).filter(
            CompetencyScore.assessment_record_id == record_id
        ).all()

        gaps = []
        met_count = 0
        for cs in scores:
            comp = db.query(Competency).filter(Competency.id == cs.competency_id).first()
            gap_val = cs.gap if cs.gap is not None else 0
            is_met = gap_val <= 0
            if is_met:
                met_count += 1
            gaps.append({
                "competency_id": cs.competency_id,
                "competency_name": comp.name if comp else None,
                "competency_code": comp.code if comp else None,
                "current_level": cs.current_level,
                "required_level": cs.required_level,
                "gap": gap_val,
                "is_met": is_met,
            })

        return success(data={
            "record_id": record_id,
            "overall_score": record.overall_score,
            "overall_level": record.overall_level,
            "pass_threshold": pass_threshold,
            "is_passed": (record.overall_score or 0) >= pass_threshold,
            "total_competencies": len(scores),
            "met_count": met_count,
            "gap_count": len(scores) - met_count,
            "gaps": gaps,
        })

    # ===========================================
    # 私有辅助方法
    # ===========================================

    @staticmethod
    def _score_to_level(score: float) -> int:
        """得分转等级(1-5)"""
        if score >= 90:
            return 5
        elif score >= 75:
            return 4
        elif score >= 60:
            return 3
        elif score >= 40:
            return 2
        else:
            return 1

    @staticmethod
    def _build_gap_summary(db: Session, record_id: int, required_map: Dict[int, int]) -> List[Dict]:
        """构建差距摘要"""
        scores = db.query(CompetencyScore).filter(
            CompetencyScore.assessment_record_id == record_id
        ).all()
        summary = []
        for cs in scores:
            comp = db.query(Competency).filter(Competency.id == cs.competency_id).first()
            summary.append({
                "competency_id": cs.competency_id,
                "competency_name": comp.name if comp else None,
                "current_level": cs.current_level,
                "required_level": cs.required_level,
                "gap": cs.gap,
            })
        return summary

    @staticmethod
    def _template_to_response(tpl: AssessmentTemplate) -> Dict[str, Any]:
        return {
            "id": tpl.id,
            "position_id": tpl.position_id,
            "name": tpl.name,
            "description": tpl.description,
            "competency_configs": tpl.competency_configs,
            "pass_threshold": tpl.pass_threshold,
            "duration_minutes": tpl.duration_minutes,
            "is_active": tpl.is_active,
            "created_at": tpl.created_at.isoformat() if tpl.created_at else None,
            "updated_at": tpl.updated_at.isoformat() if tpl.updated_at else None,
        }

    @staticmethod
    def _record_to_response(record: AssessmentRecord) -> Dict[str, Any]:
        return {
            "id": record.id,
            "template_id": record.template_id,
            "user_id": record.user_id,
            "learner_id": record.learner_id,
            "position_id": record.position_id,
            "status": record.status,
            "overall_score": record.overall_score,
            "overall_level": record.overall_level,
            "gap_summary": record.gap_summary,
            "ai_diagnosis": record.ai_diagnosis,
            "started_at": record.started_at.isoformat() if record.started_at else None,
            "completed_at": record.completed_at.isoformat() if record.completed_at else None,
            "created_at": record.created_at.isoformat() if record.created_at else None,
            "updated_at": record.updated_at.isoformat() if record.updated_at else None,
        }

    @staticmethod
    def _record_detail_to_response(db: Session, record: AssessmentRecord) -> Dict[str, Any]:
        result = AssessmentService._record_to_response(record)
        scores = db.query(CompetencyScore).filter(
            CompetencyScore.assessment_record_id == record.id
        ).all()
        result["competency_scores"] = [
            AssessmentService._score_to_response(db, cs) for cs in scores
        ]
        tpl = db.query(AssessmentTemplate).filter(AssessmentTemplate.id == record.template_id).first()
        result["template_name"] = tpl.name if tpl else None
        pos = db.query(Position).filter(Position.id == record.position_id).first()
        result["position_name"] = pos.name if pos else None
        return result

    @staticmethod
    def _score_to_response(db: Session, cs: CompetencyScore) -> Dict[str, Any]:
        comp = db.query(Competency).filter(Competency.id == cs.competency_id).first()
        return {
            "id": cs.id,
            "assessment_record_id": cs.assessment_record_id,
            "competency_id": cs.competency_id,
            "competency_name": comp.name if comp else None,
            "competency_code": comp.code if comp else None,
            "current_level": cs.current_level,
            "current_score": cs.current_score,
            "required_level": cs.required_level,
            "gap": cs.gap,
            "assessment_method": cs.assessment_method,
            "evidence": cs.evidence,
            "created_at": cs.created_at.isoformat() if cs.created_at else None,
        }
```

- [ ] **Step 4: 运行测试验证全部通过**

```bash
cd backend
.\venv\Scripts\python.exe -m pytest tests/test_assessment_service.py -v
```

Expected: 全部 PASS

- [ ] **Step 5: 提交**

```bash
git add backend/app/domains/assessment/service.py backend/tests/test_assessment_service.py
git commit -m "feat(assessment): add AssessmentService with template CRUD, record flow, and gap analysis

- AssessmentTemplate CRUD (create/list/get/update/delete)
- AssessmentRecord lifecycle (start/submit with status machine)
- CompetencyScore auto-calculation with gap computation
- Gap analysis with met/gap counts and pass/fail判定
- Full unit test coverage (17 tests)"
```

---

### Task 5: 创建 Router 并注册

**Files:**
- Create: `backend/app/domains/assessment/router.py`
- Modify: `backend/app/main.py`
- Modify: `backend/app/middleware/audit.py`

**Interfaces:**
- Consumes: `AssessmentService`, `get_current_user`, `require_teacher`
- Produces: 已注册的 `/api/v1/assessments` 路由

- [ ] **Step 1: 创建 `router.py`**

```python
"""
评估域 API 路由
"""
from typing import Optional
from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.database import get_db
from app.schemas.response import BaseResponse
from app.domains.assessment.schemas import (
    AssessmentTemplateCreate, AssessmentTemplateUpdate,
    AssessmentStartRequest, AssessmentSubmitRequest,
)
from app.domains.assessment.service import AssessmentService
from app.utils.auth import get_current_user, CurrentUser, require_teacher

router = APIRouter(prefix="/assessments", tags=["能力评估"])


# ===========================================
# 评估模板路由
# ===========================================

@router.get("/templates", summary="评估模板列表")
def get_templates(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    position_id: Optional[int] = Query(None),
    keyword: Optional[str] = Query(None),
    db: Session = Depends(get_db),
    current_user: CurrentUser = Depends(get_current_user),
) -> BaseResponse:
    return AssessmentService.get_template_list(db, page, page_size, position_id, keyword)


@router.post("/templates", summary="创建评估模板")
def create_template(
    data: AssessmentTemplateCreate,
    db: Session = Depends(get_db),
    current_user: CurrentUser = Depends(require_teacher),
) -> BaseResponse:
    return AssessmentService.create_template(db, data)


@router.get("/templates/{template_id}", summary="评估模板详情")
def get_template_detail(
    template_id: int,
    db: Session = Depends(get_db),
    current_user: CurrentUser = Depends(get_current_user),
) -> BaseResponse:
    return AssessmentService.get_template_by_id(db, template_id)


@router.put("/templates/{template_id}", summary="更新评估模板")
def update_template(
    template_id: int,
    data: AssessmentTemplateUpdate,
    db: Session = Depends(get_db),
    current_user: CurrentUser = Depends(require_teacher),
) -> BaseResponse:
    return AssessmentService.update_template(db, template_id, data)


@router.delete("/templates/{template_id}", summary="删除评估模板")
def delete_template(
    template_id: int,
    db: Session = Depends(get_db),
    current_user: CurrentUser = Depends(require_teacher),
) -> BaseResponse:
    return AssessmentService.delete_template(db, template_id)


# ===========================================
# 评估记录路由
# ===========================================

@router.post("/start", summary="开始评估")
def start_assessment(
    data: AssessmentStartRequest,
    db: Session = Depends(get_db),
    current_user: CurrentUser = Depends(get_current_user),
) -> BaseResponse:
    return AssessmentService.start_assessment(db, current_user.user_id, data.template_id, data.learner_id)


@router.get("/records", summary="评估记录列表")
def get_records(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    user_id: Optional[int] = Query(None),
    position_id: Optional[int] = Query(None),
    status: Optional[str] = Query(None),
    db: Session = Depends(get_db),
    current_user: CurrentUser = Depends(get_current_user),
) -> BaseResponse:
    return AssessmentService.get_record_list(db, page, page_size, user_id, position_id, status)


@router.get("/records/{record_id}", summary="评估记录详情（含评分明细）")
def get_record_detail(
    record_id: int,
    db: Session = Depends(get_db),
    current_user: CurrentUser = Depends(get_current_user),
) -> BaseResponse:
    return AssessmentService.get_record_detail(db, record_id)


@router.post("/records/{record_id}/submit", summary="提交评估答案")
def submit_assessment(
    record_id: int,
    data: AssessmentSubmitRequest,
    db: Session = Depends(get_db),
    current_user: CurrentUser = Depends(get_current_user),
) -> BaseResponse:
    return AssessmentService.submit_assessment(db, record_id, data)


@router.get("/records/{record_id}/gaps", summary="获取差距分析结果")
def get_gap_analysis(
    record_id: int,
    db: Session = Depends(get_db),
    current_user: CurrentUser = Depends(get_current_user),
) -> BaseResponse:
    return AssessmentService.get_gap_analysis(db, record_id)
```

- [ ] **Step 2: 在 `main.py` 中注册路由**

在 `backend/app/main.py` 中，在 position_router 注册之后添加：

```python
# 评估域路由
from app.domains.assessment.router import router as assessment_router
app.include_router(assessment_router, prefix=settings.API_PREFIX)
```

- [ ] **Step 3: 在 `audit.py` 中添加资源类型映射**

在 `backend/app/middleware/audit.py` 的 `_PATH_PREFIX_TO_RESOURCE` 字典中，在 `"/competencies": "competency"` 之后添加：

```python
"/assessments": "assessment",
```

- [ ] **Step 4: 验证路由注册**

```bash
cd backend
.\venv\Scripts\python.exe -c "
from app.main import app
paths = list(app.openapi()['paths'].keys())
asp = [p for p in paths if '/assessments' in p]
print(len(asp) > 0)
print(asp)
"
```

Expected: 输出 `True` 和所有 assessment 相关路由路径（8 个唯一路径）

- [ ] **Step 5: 提交**

```bash
git add backend/app/domains/assessment/router.py backend/app/main.py backend/app/middleware/audit.py
git commit -m "feat(assessment): add API routes and register in main app

- GET/POST/PUT/DELETE /assessments/templates[/{id}]
- POST /assessments/start
- GET /assessments/records
- GET /assessments/records/{id}
- POST /assessments/records/{id}/submit
- GET /assessments/records/{id}/gaps
- Register /assessments in audit middleware"
```

---

### Task 6: 端到端验证

**Files:**
- 无新文件，仅验证

- [ ] **Step 1: 启动后端**

```bash
cd backend
.\venv\Scripts\python.exe -m uvicorn app.main:app --host 127.0.0.1 --port 8000
```

- [ ] **Step 2: 验证 API 可用**

使用 Python urllib 脚本验证完整评估流程：

```python
import json
import urllib.request

BASE = "http://127.0.0.1:8000/api/v1"

def post(path, body, token=None):
    data = json.dumps(body).encode("utf-8")
    req = urllib.request.Request(f"{BASE}{path}", data=data, method="POST")
    req.add_header("Content-Type", "application/json")
    if token:
        req.add_header("Authorization", f"Bearer {token}")
    with urllib.request.urlopen(req) as resp:
        return json.loads(resp.read().decode("utf-8"))

def get(path, token=None):
    req = urllib.request.Request(f"{BASE}{path}", method="GET")
    if token:
        req.add_header("Authorization", f"Bearer {token}")
    with urllib.request.urlopen(req) as resp:
        return json.loads(resp.read().decode("utf-8"))

# 1. 登录
login = post("/auth/login", {"username": "admin", "password": "admin123"})
token = login["data"]["access_token"]

# 2. 创建胜任力（复用 Phase 1）
comp = post("/competencies", {"code": "HTML-E2E", "name": "HTML基础", "category": "technical"}, token)
comp_id = comp["data"]["id"]

# 3. 创建岗位（复用 Phase 1）
pos = post("/positions", {"code": "FE-E2E2", "name": "前端工程师", "category": "technical", "level": "junior"}, token)
pos_id = pos["data"]["id"]

# 4. 添加胜任力到岗位（required_level=3）
post(f"/positions/{pos_id}/competencies", {"competency_id": comp_id, "required_level": 3}, token)

# 5. 创建评估模板
tpl = post("/assessments/templates", {
    "position_id": pos_id,
    "name": "前端初级评估E2E",
    "competency_configs": [{"competency_id": comp_id, "question_count": 3, "difficulty": 2}],
    "pass_threshold": 60.0,
}, token)
tpl_id = tpl["data"]["id"]

# 6. 开始评估
start = post("/assessments/start", {"template_id": tpl_id}, token)
record_id = start["data"]["id"]

# 7. 提交评估（current_level=2, 差距1级）
submit = post(f"/assessments/records/{record_id}/submit", {
    "scores": [{"competency_id": comp_id, "current_level": 2, "current_score": 50, "assessment_method": "quiz"}],
}, token)

# 8. 查看差距分析
gaps = get(f"/assessments/records/{record_id}/gaps", token)
print(f"差距分析: met={gaps['data']['met_count']}, gap={gaps['data']['gap_count']}, is_passed={gaps['data']['is_passed']}")
```

Expected: 所有请求返回 `code: 200`，差距分析显示 `met=0, gap=1, is_passed=False`

- [ ] **Step 3: 停止后端，提交**

```bash
git commit --allow-empty -m "test: verify assessment domain API end-to-end"
```
