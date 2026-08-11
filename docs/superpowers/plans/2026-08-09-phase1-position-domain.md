# Phase 1: 删除旧 Training 域 + Position 域实现计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 删除旧 EnterpriseTraining 相关代码，新建 Position 域（岗位定义、胜任力项、岗位-胜任力关联），提供完整的 CRUD API。

**Architecture:** 遵循项目现有 DDD 分层结构（models → schemas → service → router），新域放在 `backend/app/domains/position/`。通过 Alembic 管理数据库迁移，通过 `models/__init__.py` 统一导出模型。旧 training 域的删除和新 Position 域的创建在同一个迁移周期内完成。

**Tech Stack:** FastAPI, SQLAlchemy, Pydantic, Alembic, SQLite (开发) / PostgreSQL (生产)

## Global Constraints

- Python 3.12+, 使用项目现有 venv (`backend/venv/`)
- 遵循现有代码风格：loguru 日志、统一响应包装 (`success/error/bad_request/not_found`)、`get_current_user` 鉴权
- 数据库迁移通过 Alembic 管理，不手动改表
- 所有新模型必须在 `backend/app/models/__init__.py` 中导出
- 路由注册在 `backend/app/main.py` 中完成
- API 统一前缀 `/api/v1`
- 使用 `snake_case` 数据库字段名，API 响应通过现有 `keysToCamel` 中间件自动转换

---

## File Structure

### 删除的文件

```
backend/app/domains/training/models.py       ← 旧 EnterpriseTraining
backend/app/domains/training/router.py        ← 旧 CRUD 路由
backend/app/domains/training/schemas.py       ← 旧 Schema
backend/app/domains/training/service.py       ← 旧 Service
backend/app/data/trainings.json               ← 旧种子数据
backend/tests/test_training_service.py        ← 旧单元测试
e2e/enterprise-training-import.spec.ts        ← 旧 E2E 测试
e2e/fixtures/sample-training.csv              ← 旧测试夹具
```

### 新建的文件

```
backend/app/domains/position/__init__.py      ← 空包初始化
backend/app/domains/position/models.py        ← Position, Competency, PositionCompetency ORM 模型
backend/app/domains/position/schemas.py       ← Pydantic 请求/响应 Schema
backend/app/domains/position/service.py       ← 业务逻辑层
backend/app/domains/position/router.py        ← API 路由定义
backend/tests/test_position_service.py        ← 单元测试
backend/alembic/versions/xxxx_remove_training_add_position.py  ← Alembic 迁移
```

### 修改的文件

```
backend/app/main.py                           ← 移除旧 training_router，注册 position_router
backend/app/models/__init__.py                ← 移除旧导出，新增 Position 域模型导出
```

---

### Task 1: 删除旧 Training 域代码

**Files:**
- Delete: `backend/app/domains/training/models.py`
- Delete: `backend/app/domains/training/router.py`
- Delete: `backend/app/domains/training/schemas.py`
- Delete: `backend/app/domains/training/service.py`
- Delete: `backend/app/data/trainings.json`
- Delete: `backend/tests/test_training_service.py`
- Delete: `e2e/enterprise-training-import.spec.ts`
- Delete: `e2e/fixtures/sample-training.csv`
- Modify: `backend/app/models/__init__.py`
- Modify: `backend/app/main.py`

**Interfaces:**
- Consumes: 无
- Produces: 清理后的 `models/__init__.py`（不再导出 `EnterpriseTraining` 等）和 `main.py`（不再注册旧 training_router）

- [ ] **Step 1: 删除旧 training 域文件**

删除以下文件：
```
backend/app/domains/training/models.py
backend/app/domains/training/router.py
backend/app/domains/training/schemas.py
backend/app/domains/training/service.py
backend/app/data/trainings.json
backend/tests/test_training_service.py
e2e/enterprise-training-import.spec.ts
e2e/fixtures/sample-training.csv
```

保留 `backend/app/domains/training/__init__.py`（空文件），后续 Phase 4 重建 training 域时复用。

- [ ] **Step 2: 清理 `models/__init__.py` 中的旧导出**

打开 `backend/app/models/__init__.py`，移除以下导入和导出：
```python
# 删除这些行
from app.domains.training.models import EnterpriseTraining, TrainingStatusEnum, TransferStatusEnum
```

以及在 `__all__` 列表中移除 `"EnterpriseTraining"`, `"TrainingStatusEnum"`, `"TransferStatusEnum"`。

- [ ] **Step 3: 清理 `main.py` 中的旧路由注册和种子初始化**

打开 `backend/app/main.py`，移除以下内容：

1. 移除 import：
```python
# 删除这行
from app.domains.training.router import router as training_router
```

2. 移除路由注册：
```python
# 删除这行
app.include_router(training_router, prefix=settings.API_PREFIX)
```

3. 移除种子数据初始化调用（在 `lifespan` 函数中）：
```python
# 删除这行
init_training_seed_data()
```

以及对应的 import（如有）：
```python
# 删除
from app.seed_data import init_training_seed_data
```

注意：检查 `backend/app/seed_data.py` 中是否有 `init_training_seed_data` 函数，如果有，也需要移除该函数（但保留文件中其他函数）。

- [ ] **Step 4: 验证后端能正常启动（无导入错误）**

```bash
cd backend
.\venv\Scripts\python.exe -c "from app.main import app; print('OK')"
```

Expected: 输出 `OK`，无 ImportError

- [ ] **Step 5: 提交**

```bash
git add -A
git commit -m "refactor: remove legacy EnterpriseTraining domain

Remove old training models, router, schemas, service, seed data,
and tests. These will be replaced by the new Position/Assessment/
Certification/Training domain architecture."
```

---

### Task 2: 创建 Position 域 ORM 模型

**Files:**
- Create: `backend/app/domains/position/__init__.py`
- Create: `backend/app/domains/position/models.py`
- Modify: `backend/app/models/__init__.py`

**Interfaces:**
- Consumes: `app.database.Base`, `app.models.user.User`
- Produces: `Position`, `Competency`, `PositionCompetency` 模型类，供后续 schemas/service/router 使用

- [ ] **Step 1: 创建 `position/__init__.py`**

```python
# 空包初始化文件
```

- [ ] **Step 2: 创建 `position/models.py`**

```python
"""
岗位与胜任力域 ORM 模型
包含：岗位定义、胜任力项、岗位-胜任力关联
"""
from sqlalchemy import Column, Integer, String, Boolean, DateTime, Float, Text, JSON, ForeignKey, UniqueConstraint, Enum as SQLEnum
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from app.database import Base
import enum


class PositionCategoryEnum(enum.Enum):
    """岗位类别枚举"""
    TECHNICAL = "technical"    # 技术类
    MANAGEMENT = "management"  # 管理类
    OPERATION = "operation"    # 运营类
    DESIGN = "design"          # 设计类
    OTHER = "other"            # 其他


class PositionLevelEnum(enum.Enum):
    """岗位层级枚举"""
    JUNIOR = "junior"
    MID = "mid"
    SENIOR = "senior"
    EXPERT = "expert"


class CompetencyCategoryEnum(enum.Enum):
    """胜任力类别枚举"""
    TECHNICAL = "technical"        # 技术能力
    SOFT_SKILL = "soft_skill"      # 软技能
    DOMAIN_KNOWLEDGE = "domain"    # 领域知识
    ENGINEERING = "engineering"    # 工程实践


class Position(Base):
    """岗位定义表"""

    __tablename__ = "positions"

    id = Column(Integer, primary_key=True, autoincrement=True, comment="岗位ID")
    code = Column(String(50), unique=True, nullable=False, index=True, comment="岗位编码")
    name = Column(String(100), nullable=False, index=True, comment="岗位名称")
    category = Column(String(50), nullable=True, index=True, comment="岗位类别")
    industry = Column(String(50), nullable=True, comment="所属行业")
    level = Column(String(20), nullable=True, comment="岗位层级")
    description = Column(Text, nullable=True, comment="岗位描述")
    responsibilities = Column(JSON, default=list, comment="岗位职责列表")
    prerequisites = Column(JSON, default=list, comment="前置要求")
    career_path = Column(JSON, default=list, comment="职业发展路径")
    is_active = Column(Boolean, default=True, comment="是否启用")
    created_at = Column(DateTime, server_default=func.now(), comment="创建时间")
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now(), comment="更新时间")

    # 关联关系
    competencies = relationship("PositionCompetency", back_populates="position", cascade="all, delete-orphan")

    def __repr__(self) -> str:
        return f"<Position(id={self.id}, code={self.code}, name={self.name})>"


class Competency(Base):
    """胜任力项表"""

    __tablename__ = "competencies"

    id = Column(Integer, primary_key=True, autoincrement=True, comment="胜任力ID")
    code = Column(String(50), unique=True, nullable=False, index=True, comment="胜任力编码")
    name = Column(String(100), nullable=False, index=True, comment="胜任力名称")
    category = Column(String(50), nullable=True, index=True, comment="胜任力类别")
    description = Column(Text, nullable=True, comment="胜任力描述")
    level_descriptions = Column(JSON, default=dict, comment="各等级描述 {1: '了解', 2: '能使用', ...}")
    is_active = Column(Boolean, default=True, comment="是否启用")
    created_at = Column(DateTime, server_default=func.now(), comment="创建时间")
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now(), comment="更新时间")

    # 关联关系
    positions = relationship("PositionCompetency", back_populates="competency", cascade="all, delete-orphan")

    def __repr__(self) -> str:
        return f"<Competency(id={self.id}, code={self.code}, name={self.name})>"


class PositionCompetency(Base):
    """岗位-胜任力关联表"""

    __tablename__ = "position_competencies"
    __table_args__ = (
        UniqueConstraint("position_id", "competency_id", name="uq_position_competency"),
    )

    id = Column(Integer, primary_key=True, autoincrement=True, comment="关联ID")
    position_id = Column(Integer, ForeignKey("positions.id", ondelete="CASCADE"), nullable=False, index=True, comment="岗位ID")
    competency_id = Column(Integer, ForeignKey("competencies.id", ondelete="CASCADE"), nullable=False, index=True, comment="胜任力ID")
    required_level = Column(Integer, nullable=False, comment="要求等级(1-5)")
    weight = Column(Float, default=1.0, comment="权重")
    is_mandatory = Column(Boolean, default=True, comment="是否必修")
    created_at = Column(DateTime, server_default=func.now(), comment="创建时间")

    # 关联关系
    position = relationship("Position", back_populates="competencies")
    competency = relationship("Competency", back_populates="positions")

    def __repr__(self) -> str:
        return f"<PositionCompetency(position_id={self.position_id}, competency_id={self.competency_id}, level={self.required_level})>"
```

- [ ] **Step 3: 在 `models/__init__.py` 中导出新模型**

在 `backend/app/models/__init__.py` 中添加：

```python
from app.domains.position.models import (
    Position,
    PositionCategoryEnum,
    PositionLevelEnum,
    Competency,
    CompetencyCategoryEnum,
    PositionCompetency,
)
```

并在 `__all__` 中添加：
```python
"Position",
"PositionCategoryEnum",
"PositionLevelEnum",
"Competency",
"CompetencyCategoryEnum",
"PositionCompetency",
```

- [ ] **Step 4: 验证模型能正确导入**

```bash
cd backend
.\venv\Scripts\python.exe -c "from app.models import Position, Competency, PositionCompetency; print('OK')"
```

Expected: 输出 `OK`

- [ ] **Step 5: 提交**

```bash
git add backend/app/domains/position/ backend/app/models/__init__.py
git commit -m "feat(position): add Position, Competency, PositionCompetency ORM models"
```

---

### Task 3: 创建 Alembic 迁移脚本

**Files:**
- Create: `backend/alembic/versions/xxxx_remove_training_add_position.py` (通过 alembic autogenerate)

**Interfaces:**
- Consumes: Task 1 和 Task 2 的模型变更
- Produces: 数据库中 `enterprise_trainings` 表被删除，`positions`/`competencies`/`position_competencies` 表被创建

- [ ] **Step 1: 生成迁移脚本**

```bash
cd backend
.\venv\Scripts\python.exe -m alembic revision --autogenerate -m "remove enterprise_trainings, add position domain tables"
```

- [ ] **Step 2: 检查生成的迁移脚本**

打开生成的迁移脚本（`backend/alembic/versions/`下的新文件），确认：
1. `upgrade()` 中包含 `op.drop_table('enterprise_trainings')`
2. `upgrade()` 中包含创建 `positions`、`competencies`、`position_competencies` 三张表
3. `downgrade()` 中包含反向操作

如果 autogenerate 遗漏了某些内容，手动补充。

- [ ] **Step 3: 执行迁移**

```bash
cd backend
.\venv\Scripts\python.exe -m alembic upgrade head
```

Expected: 输出 `Running upgrade ... -> xxxx, remove enterprise_trainings, add position domain tables`

- [ ] **Step 4: 验证表结构**

```bash
cd backend
.\venv\Scripts\python.exe -c "
from app.database import engine
from sqlalchemy import inspect
insp = inspect(engine)
tables = insp.get_table_names()
print('positions' in tables, 'competencies' in tables, 'position_competencies' in tables)
print('enterprise_trainings' not in tables)
"
```

Expected: `True True True True`

- [ ] **Step 5: 提交**

```bash
git add backend/alembic/versions/
git commit -m "db: migrate - drop enterprise_trainings, create position domain tables"
```

---

### Task 4: 创建 Pydantic Schemas

**Files:**
- Create: `backend/app/domains/position/schemas.py`

**Interfaces:**
- Consumes: `app.domains.position.models` 中的模型类
- Produces: `PositionCreate`, `PositionUpdate`, `PositionResponse`, `CompetencyCreate`, `CompetencyUpdate`, `CompetencyResponse`, `PositionCompetencyCreate`, `PositionCompetencyResponse` 等 Schema

- [ ] **Step 1: 创建 `schemas.py`**

```python
"""
岗位与胜任力域 Pydantic Schemas
"""
from typing import Optional, List
from datetime import datetime
from pydantic import BaseModel, Field, field_validator


# ===========================================
# Competency Schemas
# ===========================================

class CompetencyBase(BaseModel):
    code: str = Field(..., max_length=50, description="胜任力编码")
    name: str = Field(..., max_length=100, description="胜任力名称")
    category: Optional[str] = Field(None, description="胜任力类别")
    description: Optional[str] = None
    level_descriptions: Optional[dict] = Field(None, description="各等级描述")

class CompetencyCreate(CompetencyBase):
    pass

class CompetencyUpdate(BaseModel):
    name: Optional[str] = Field(None, max_length=100)
    category: Optional[str] = None
    description: Optional[str] = None
    level_descriptions: Optional[dict] = None
    is_active: Optional[bool] = None

class CompetencyResponse(CompetencyBase):
    id: int
    is_active: bool
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


# ===========================================
# Position Schemas
# ===========================================

class PositionBase(BaseModel):
    code: str = Field(..., max_length=50, description="岗位编码")
    name: str = Field(..., max_length=100, description="岗位名称")
    category: Optional[str] = Field(None, description="岗位类别")
    industry: Optional[str] = None
    level: Optional[str] = None
    description: Optional[str] = None
    responsibilities: Optional[List[str]] = Field(default_factory=list)
    prerequisites: Optional[List[str]] = Field(default_factory=list)
    career_path: Optional[List[str]] = Field(default_factory=list)

class PositionCreate(PositionBase):
    pass

class PositionUpdate(BaseModel):
    name: Optional[str] = Field(None, max_length=100)
    category: Optional[str] = None
    industry: Optional[str] = None
    level: Optional[str] = None
    description: Optional[str] = None
    responsibilities: Optional[List[str]] = None
    prerequisites: Optional[List[str]] = None
    career_path: Optional[List[str]] = None
    is_active: Optional[bool] = None

class PositionResponse(PositionBase):
    id: int
    is_active: bool
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


# ===========================================
# PositionCompetency Schemas
# ===========================================

class PositionCompetencyCreate(BaseModel):
    competency_id: int = Field(..., description="胜任力ID")
    required_level: int = Field(..., ge=1, le=5, description="要求等级(1-5)")
    weight: float = Field(1.0, description="权重")
    is_mandatory: bool = Field(True, description="是否必修")

class PositionCompetencyUpdate(BaseModel):
    required_level: Optional[int] = Field(None, ge=1, le=5)
    weight: Optional[float] = None
    is_mandatory: Optional[bool] = None

class PositionCompetencyResponse(BaseModel):
    id: int
    position_id: int
    competency_id: int
    competency_name: Optional[str] = None
    competency_code: Optional[str] = None
    competency_category: Optional[str] = None
    required_level: int
    weight: float
    is_mandatory: bool
    created_at: datetime

    class Config:
        from_attributes = True


# ===========================================
# 带胜任力矩阵的岗位详情
# ===========================================

class PositionDetailResponse(PositionResponse):
    competencies: List[PositionCompetencyResponse] = Field(default_factory=list)
```

- [ ] **Step 2: 验证 Schema 能正确导入**

```bash
cd backend
.\venv\Scripts\python.exe -c "from app.domains.position.schemas import PositionCreate, CompetencyCreate, PositionCompetencyCreate; print('OK')"
```

Expected: `OK`

- [ ] **Step 3: 提交**

```bash
git add backend/app/domains/position/schemas.py
git commit -m "feat(position): add Pydantic schemas for position domain"
```

---

### Task 5: 创建 Service 层

**Files:**
- Create: `backend/app/domains/position/service.py`

**Interfaces:**
- Consumes: `app.domains.position.models`, `app.domains.position.schemas`, `app.database.get_db`
- Produces: `PositionService` 类（静态方法），供 router 调用

- [ ] **Step 1: 编写 Service 单元测试**

创建 `backend/tests/test_position_service.py`：

```python
"""Position 域 Service 单元测试"""
import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from app.database import Base
from app.domains.position.models import Position, Competency, PositionCompetency
from app.domains.position.schemas import PositionCreate, PositionUpdate, CompetencyCreate, CompetencyUpdate, PositionCompetencyCreate, PositionCompetencyUpdate
from app.domains.position.service import PositionService


@pytest.fixture
def db():
    """内存 SQLite 测试数据库"""
    engine = create_engine("sqlite:///:memory:", echo=False)
    Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine)
    session = Session()
    yield session
    session.close()


class TestCompetencyService:
    def test_create_competency(self, db):
        data = CompetencyCreate(code="PROG-PY", name="Python编程", category="technical")
        result = PositionService.create_competency(db, data)
        assert result["code"] == 200
        assert result["data"]["code"] == "PROG-PY"
        assert result["data"]["name"] == "Python编程"

    def test_create_duplicate_competency(self, db):
        data = CompetencyCreate(code="PROG-PY", name="Python编程")
        PositionService.create_competency(db, data)
        result = PositionService.create_competency(db, data)
        assert result["code"] == 400

    def test_get_competency_list(self, db):
        PositionService.create_competency(db, CompetencyCreate(code="C1", name="技能1"))
        PositionService.create_competency(db, CompetencyCreate(code="C2", name="技能2"))
        result = PositionService.get_competency_list(db, page=1, page_size=10)
        assert result["code"] == 200
        assert result["data"]["total"] == 2

    def test_update_competency(self, db):
        create_result = PositionService.create_competency(db, CompetencyCreate(code="C1", name="旧名称"))
        cid = create_result["data"]["id"]
        result = PositionService.update_competency(db, cid, CompetencyUpdate(name="新名称"))
        assert result["code"] == 200
        assert result["data"]["name"] == "新名称"

    def test_delete_competency(self, db):
        create_result = PositionService.create_competency(db, CompetencyCreate(code="C1", name="技能1"))
        cid = create_result["data"]["id"]
        result = PositionService.delete_competency(db, cid)
        assert result["code"] == 200


class TestPositionService:
    def test_create_position(self, db):
        data = PositionCreate(code="FE-001", name="前端工程师", category="technical", level="junior")
        result = PositionService.create_position(db, data)
        assert result["code"] == 200
        assert result["data"]["code"] == "FE-001"

    def test_get_position_list(self, db):
        PositionService.create_position(db, PositionCreate(code="P1", name="岗位1"))
        PositionService.create_position(db, PositionCreate(code="P2", name="岗位2"))
        result = PositionService.get_position_list(db, page=1, page_size=10)
        assert result["data"]["total"] == 2

    def test_get_position_list_with_filter(self, db):
        PositionService.create_position(db, PositionCreate(code="P1", name="前端", category="technical"))
        PositionService.create_position(db, PositionCreate(code="P2", name="产品", category="management"))
        result = PositionService.get_position_list(db, page=1, page_size=10, category="technical")
        assert result["data"]["total"] == 1

    def test_get_position_detail(self, db):
        create_result = PositionService.create_position(db, PositionCreate(code="P1", name="岗位1"))
        pid = create_result["data"]["id"]
        result = PositionService.get_position_by_id(db, pid)
        assert result["code"] == 200
        assert result["data"]["name"] == "岗位1"
        assert result["data"]["competencies"] == []

    def test_update_position(self, db):
        create_result = PositionService.create_position(db, PositionCreate(code="P1", name="旧名称"))
        pid = create_result["data"]["id"]
        result = PositionService.update_position(db, pid, PositionUpdate(name="新名称"))
        assert result["code"] == 200
        assert result["data"]["name"] == "新名称"

    def test_delete_position(self, db):
        create_result = PositionService.create_position(db, PositionCreate(code="P1", name="岗位1"))
        pid = create_result["data"]["id"]
        result = PositionService.delete_position(db, pid)
        assert result["code"] == 200


class TestPositionCompetencyService:
    def test_add_competency_to_position(self, db):
        pos_result = PositionService.create_position(db, PositionCreate(code="P1", name="岗位1"))
        comp_result = PositionService.create_competency(db, CompetencyCreate(code="C1", name="技能1"))
        pid = pos_result["data"]["id"]
        cid = comp_result["data"]["id"]

        result = PositionService.add_competency_to_position(db, pid, PositionCompetencyCreate(
            competency_id=cid, required_level=3
        ))
        assert result["code"] == 200
        assert result["data"]["required_level"] == 3

    def test_add_duplicate_competency(self, db):
        pos_result = PositionService.create_position(db, PositionCreate(code="P1", name="岗位1"))
        comp_result = PositionService.create_competency(db, CompetencyCreate(code="C1", name="技能1"))
        pid = pos_result["data"]["id"]
        cid = comp_result["data"]["id"]

        PositionService.add_competency_to_position(db, pid, PositionCompetencyCreate(
            competency_id=cid, required_level=3
        ))
        result = PositionService.add_competency_to_position(db, pid, PositionCompetencyCreate(
            competency_id=cid, required_level=4
        ))
        assert result["code"] == 400

    def test_update_position_competency(self, db):
        pos_result = PositionService.create_position(db, PositionCreate(code="P1", name="岗位1"))
        comp_result = PositionService.create_competency(db, CompetencyCreate(code="C1", name="技能1"))
        pid = pos_result["data"]["id"]
        cid = comp_result["data"]["id"]

        PositionService.add_competency_to_position(db, pid, PositionCompetencyCreate(
            competency_id=cid, required_level=3
        ))
        result = PositionService.update_position_competency(db, pid, cid, PositionCompetencyUpdate(
            required_level=5, is_mandatory=False
        ))
        assert result["code"] == 200
        assert result["data"]["required_level"] == 5
        assert result["data"]["is_mandatory"] is False

    def test_remove_competency_from_position(self, db):
        pos_result = PositionService.create_position(db, PositionCreate(code="P1", name="岗位1"))
        comp_result = PositionService.create_competency(db, CompetencyCreate(code="C1", name="技能1"))
        pid = pos_result["data"]["id"]
        cid = comp_result["data"]["id"]

        PositionService.add_competency_to_position(db, pid, PositionCompetencyCreate(
            competency_id=cid, required_level=3
        ))
        result = PositionService.remove_competency_from_position(db, pid, cid)
        assert result["code"] == 200

    def test_get_position_detail_with_competencies(self, db):
        pos_result = PositionService.create_position(db, PositionCreate(code="P1", name="岗位1"))
        comp_result = PositionService.create_competency(db, CompetencyCreate(code="C1", name="技能1"))
        pid = pos_result["data"]["id"]
        cid = comp_result["data"]["id"]

        PositionService.add_competency_to_position(db, pid, PositionCompetencyCreate(
            competency_id=cid, required_level=4
        ))
        result = PositionService.get_position_by_id(db, pid)
        assert result["code"] == 200
        assert len(result["data"]["competencies"]) == 1
        assert result["data"]["competencies"][0]["competency_name"] == "技能1"
        assert result["data"]["competencies"][0]["required_level"] == 4
```

- [ ] **Step 2: 运行测试验证全部失败**

```bash
cd backend
.\venv\Scripts\python.exe -m pytest tests/test_position_service.py -v
```

Expected: 全部 FAIL（因为 `PositionService` 尚未实现）

- [ ] **Step 3: 创建 `service.py` 实现**

```python
"""
岗位与胜任力域 Service 层
"""
from typing import Optional, Dict, Any
from sqlalchemy.orm import Session
from sqlalchemy import or_

from app.domains.position.models import Position, Competency, PositionCompetency
from app.domains.position.schemas import (
    PositionCreate, PositionUpdate,
    CompetencyCreate, CompetencyUpdate,
    PositionCompetencyCreate, PositionCompetencyUpdate,
)
from app.schemas.response import success, error, bad_request, not_found
from app.utils.logger import LoggerUtil


class PositionService:
    """岗位与胜任力服务"""

    # ===========================================
    # Competency CRUD
    # ===========================================

    @staticmethod
    def create_competency(db: Session, data: CompetencyCreate) -> Dict[str, Any]:
        existing = db.query(Competency).filter(Competency.code == data.code).first()
        if existing:
            return bad_request(message=f"胜任力编码已存在: {data.code}")
        comp = Competency(
            code=data.code,
            name=data.name,
            category=data.category,
            description=data.description,
            level_descriptions=data.level_descriptions or {},
        )
        db.add(comp)
        db.commit()
        db.refresh(comp)
        return success(data=PositionService._competency_to_response(comp), message="胜任力创建成功")

    @staticmethod
    def get_competency_list(
        db: Session, page: int = 1, page_size: int = 20,
        keyword: Optional[str] = None, category: Optional[str] = None
    ) -> Dict[str, Any]:
        query = db.query(Competency)
        if keyword:
            query = query.filter(or_(
                Competency.name.contains(keyword),
                Competency.code.contains(keyword),
            ))
        if category:
            query = query.filter(Competency.category == category)
        total = query.count()
        items = query.offset((page - 1) * page_size).limit(page_size).all()
        return success(data={
            "items": [PositionService._competency_to_response(c) for c in items],
            "total": total,
            "page": page,
            "page_size": page_size,
        })

    @staticmethod
    def get_competency_by_id(db: Session, competency_id: int) -> Dict[str, Any]:
        comp = db.query(Competency).filter(Competency.id == competency_id).first()
        if not comp:
            return not_found(message="胜任力不存在")
        return success(data=PositionService._competency_to_response(comp))

    @staticmethod
    def update_competency(db: Session, competency_id: int, data: CompetencyUpdate) -> Dict[str, Any]:
        comp = db.query(Competency).filter(Competency.id == competency_id).first()
        if not comp:
            return not_found(message="胜任力不存在")
        update_data = data.model_dump(exclude_unset=True)
        for key, value in update_data.items():
            setattr(comp, key, value)
        db.commit()
        db.refresh(comp)
        return success(data=PositionService._competency_to_response(comp), message="更新成功")

    @staticmethod
    def delete_competency(db: Session, competency_id: int) -> Dict[str, Any]:
        comp = db.query(Competency).filter(Competency.id == competency_id).first()
        if not comp:
            return not_found(message="胜任力不存在")
        db.delete(comp)
        db.commit()
        return success(message="删除成功")

    # ===========================================
    # Position CRUD
    # ===========================================

    @staticmethod
    def create_position(db: Session, data: PositionCreate) -> Dict[str, Any]:
        existing = db.query(Position).filter(Position.code == data.code).first()
        if existing:
            return bad_request(message=f"岗位编码已存在: {data.code}")
        pos = Position(
            code=data.code,
            name=data.name,
            category=data.category,
            industry=data.industry,
            level=data.level,
            description=data.description,
            responsibilities=data.responsibilities or [],
            prerequisites=data.prerequisites or [],
            career_path=data.career_path or [],
        )
        db.add(pos)
        db.commit()
        db.refresh(pos)
        return success(data=PositionService._position_to_response(pos), message="岗位创建成功")

    @staticmethod
    def get_position_list(
        db: Session, page: int = 1, page_size: int = 20,
        keyword: Optional[str] = None, category: Optional[str] = None,
        industry: Optional[str] = None, level: Optional[str] = None
    ) -> Dict[str, Any]:
        query = db.query(Position)
        if keyword:
            query = query.filter(or_(
                Position.name.contains(keyword),
                Position.code.contains(keyword),
            ))
        if category:
            query = query.filter(Position.category == category)
        if industry:
            query = query.filter(Position.industry == industry)
        if level:
            query = query.filter(Position.level == level)
        total = query.count()
        items = query.offset((page - 1) * page_size).limit(page_size).all()
        return success(data={
            "items": [PositionService._position_to_response(p) for p in items],
            "total": total,
            "page": page,
            "page_size": page_size,
        })

    @staticmethod
    def get_position_by_id(db: Session, position_id: int) -> Dict[str, Any]:
        pos = db.query(Position).filter(Position.id == position_id).first()
        if not pos:
            return not_found(message="岗位不存在")
        return success(data=PositionService._position_detail_to_response(pos))

    @staticmethod
    def update_position(db: Session, position_id: int, data: PositionUpdate) -> Dict[str, Any]:
        pos = db.query(Position).filter(Position.id == position_id).first()
        if not pos:
            return not_found(message="岗位不存在")
        update_data = data.model_dump(exclude_unset=True)
        for key, value in update_data.items():
            setattr(pos, key, value)
        db.commit()
        db.refresh(pos)
        return success(data=PositionService._position_to_response(pos), message="更新成功")

    @staticmethod
    def delete_position(db: Session, position_id: int) -> Dict[str, Any]:
        pos = db.query(Position).filter(Position.id == position_id).first()
        if not pos:
            return not_found(message="岗位不存在")
        db.delete(pos)
        db.commit()
        return success(message="删除成功")

    # ===========================================
    # Position-Competency 关联管理
    # ===========================================

    @staticmethod
    def add_competency_to_position(
        db: Session, position_id: int, data: PositionCompetencyCreate
    ) -> Dict[str, Any]:
        pos = db.query(Position).filter(Position.id == position_id).first()
        if not pos:
            return not_found(message="岗位不存在")
        comp = db.query(Competency).filter(Competency.id == data.competency_id).first()
        if not comp:
            return not_found(message="胜任力不存在")
        existing = db.query(PositionCompetency).filter(
            PositionCompetency.position_id == position_id,
            PositionCompetency.competency_id == data.competency_id,
        ).first()
        if existing:
            return bad_request(message="该胜任力已关联到此岗位")

        pc = PositionCompetency(
            position_id=position_id,
            competency_id=data.competency_id,
            required_level=data.required_level,
            weight=data.weight,
            is_mandatory=data.is_mandatory,
        )
        db.add(pc)
        db.commit()
        db.refresh(pc)
        return success(data=PositionService._pc_to_response(pc), message="胜任力已添加到岗位")

    @staticmethod
    def update_position_competency(
        db: Session, position_id: int, competency_id: int, data: PositionCompetencyUpdate
    ) -> Dict[str, Any]:
        pc = db.query(PositionCompetency).filter(
            PositionCompetency.position_id == position_id,
            PositionCompetency.competency_id == competency_id,
        ).first()
        if not pc:
            return not_found(message="岗位胜任力关联不存在")
        update_data = data.model_dump(exclude_unset=True)
        for key, value in update_data.items():
            setattr(pc, key, value)
        db.commit()
        db.refresh(pc)
        return success(data=PositionService._pc_to_response(pc), message="更新成功")

    @staticmethod
    def remove_competency_from_position(
        db: Session, position_id: int, competency_id: int
    ) -> Dict[str, Any]:
        pc = db.query(PositionCompetency).filter(
            PositionCompetency.position_id == position_id,
            PositionCompetency.competency_id == competency_id,
        ).first()
        if not pc:
            return not_found(message="岗位胜任力关联不存在")
        db.delete(pc)
        db.commit()
        return success(message="已移除胜任力")

    # ===========================================
    # 私有转换方法
    # ===========================================

    @staticmethod
    def _competency_to_response(comp: Competency) -> Dict[str, Any]:
        return {
            "id": comp.id,
            "code": comp.code,
            "name": comp.name,
            "category": comp.category,
            "description": comp.description,
            "level_descriptions": comp.level_descriptions,
            "is_active": comp.is_active,
            "created_at": comp.created_at.isoformat() if comp.created_at else None,
            "updated_at": comp.updated_at.isoformat() if comp.updated_at else None,
        }

    @staticmethod
    def _position_to_response(pos: Position) -> Dict[str, Any]:
        return {
            "id": pos.id,
            "code": pos.code,
            "name": pos.name,
            "category": pos.category,
            "industry": pos.industry,
            "level": pos.level,
            "description": pos.description,
            "responsibilities": pos.responsibilities,
            "prerequisites": pos.prerequisites,
            "career_path": pos.career_path,
            "is_active": pos.is_active,
            "created_at": pos.created_at.isoformat() if pos.created_at else None,
            "updated_at": pos.updated_at.isoformat() if pos.updated_at else None,
        }

    @staticmethod
    def _position_detail_to_response(pos: Position) -> Dict[str, Any]:
        result = PositionService._position_to_response(pos)
        result["competencies"] = [
            PositionService._pc_to_response(pc) for pc in pos.competencies
        ]
        return result

    @staticmethod
    def _pc_to_response(pc: PositionCompetency) -> Dict[str, Any]:
        return {
            "id": pc.id,
            "position_id": pc.position_id,
            "competency_id": pc.competency_id,
            "competency_name": pc.competency.name if pc.competency else None,
            "competency_code": pc.competency.code if pc.competency else None,
            "competency_category": pc.competency.category if pc.competency else None,
            "required_level": pc.required_level,
            "weight": pc.weight,
            "is_mandatory": pc.is_mandatory,
            "created_at": pc.created_at.isoformat() if pc.created_at else None,
        }
```

- [ ] **Step 4: 运行测试验证全部通过**

```bash
cd backend
.\venv\Scripts\python.exe -m pytest tests/test_position_service.py -v
```

Expected: 全部 PASS

- [ ] **Step 5: 提交**

```bash
git add backend/app/domains/position/service.py backend/tests/test_position_service.py
git commit -m "feat(position): add PositionService with CRUD and competency matrix management

- Competency CRUD (create/list/get/update/delete)
- Position CRUD (create/list/get/update/delete)
- Position-Competency association (add/update/remove)
- Full unit test coverage"
```

---

### Task 6: 创建 Router 并注册

**Files:**
- Create: `backend/app/domains/position/router.py`
- Modify: `backend/app/main.py`

**Interfaces:**
- Consumes: `PositionService`, `get_current_user`, `require_teacher`
- Produces: 已注册的 `/api/v1/positions` 和 `/api/v1/competencies` 路由

- [ ] **Step 1: 创建 `router.py`**

```python
"""
岗位与胜任力域 API 路由
"""
from typing import Optional
from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.database import get_db
from app.schemas.response import success, bad_request, not_found, BaseResponse
from app.domains.position.schemas import (
    PositionCreate, PositionUpdate,
    CompetencyCreate, CompetencyUpdate,
    PositionCompetencyCreate, PositionCompetencyUpdate,
)
from app.domains.position.service import PositionService
from app.utils.auth import get_current_user, CurrentUser, require_teacher

router = APIRouter(prefix="", tags=["岗位与胜任力"])


# ===========================================
# Competency 路由
# ===========================================

@router.get("/competencies", summary="胜任力项列表")
def get_competencies(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    keyword: Optional[str] = Query(None),
    category: Optional[str] = Query(None),
    db: Session = Depends(get_db),
    current_user: CurrentUser = Depends(get_current_user),
) -> BaseResponse:
    return PositionService.get_competency_list(db, page, page_size, keyword, category)


@router.post("/competencies", summary="创建胜任力项")
def create_competency(
    data: CompetencyCreate,
    db: Session = Depends(get_db),
    current_user: CurrentUser = Depends(require_teacher),
) -> BaseResponse:
    return PositionService.create_competency(db, data)


@router.put("/competencies/{competency_id}", summary="更新胜任力项")
def update_competency(
    competency_id: int,
    data: CompetencyUpdate,
    db: Session = Depends(get_db),
    current_user: CurrentUser = Depends(require_teacher),
) -> BaseResponse:
    return PositionService.update_competency(db, competency_id, data)


@router.delete("/competencies/{competency_id}", summary="删除胜任力项")
def delete_competency(
    competency_id: int,
    db: Session = Depends(get_db),
    current_user: CurrentUser = Depends(require_teacher),
) -> BaseResponse:
    return PositionService.delete_competency(db, competency_id)


# ===========================================
# Position 路由
# ===========================================

@router.get("/positions", summary="岗位列表")
def get_positions(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    keyword: Optional[str] = Query(None),
    category: Optional[str] = Query(None),
    industry: Optional[str] = Query(None),
    level: Optional[str] = Query(None),
    db: Session = Depends(get_db),
    current_user: CurrentUser = Depends(get_current_user),
) -> BaseResponse:
    return PositionService.get_position_list(db, page, page_size, keyword, category, industry, level)


@router.post("/positions", summary="创建岗位")
def create_position(
    data: PositionCreate,
    db: Session = Depends(get_db),
    current_user: CurrentUser = Depends(require_teacher),
) -> BaseResponse:
    return PositionService.create_position(db, data)


@router.get("/positions/{position_id}", summary="岗位详情（含胜任力矩阵）")
def get_position_detail(
    position_id: int,
    db: Session = Depends(get_db),
    current_user: CurrentUser = Depends(get_current_user),
) -> BaseResponse:
    return PositionService.get_position_by_id(db, position_id)


@router.put("/positions/{position_id}", summary="更新岗位")
def update_position(
    position_id: int,
    data: PositionUpdate,
    db: Session = Depends(get_db),
    current_user: CurrentUser = Depends(require_teacher),
) -> BaseResponse:
    return PositionService.update_position(db, position_id, data)


@router.delete("/positions/{position_id}", summary="删除岗位")
def delete_position(
    position_id: int,
    db: Session = Depends(get_db),
    current_user: CurrentUser = Depends(require_teacher),
) -> BaseResponse:
    return PositionService.delete_position(db, position_id)


# ===========================================
# Position-Competency 关联路由
# ===========================================

@router.post("/positions/{position_id}/competencies", summary="为岗位添加胜任力要求")
def add_competency_to_position(
    position_id: int,
    data: PositionCompetencyCreate,
    db: Session = Depends(get_db),
    current_user: CurrentUser = Depends(require_teacher),
) -> BaseResponse:
    return PositionService.add_competency_to_position(db, position_id, data)


@router.put("/positions/{position_id}/competencies/{competency_id}", summary="更新岗位胜任力要求")
def update_position_competency(
    position_id: int,
    competency_id: int,
    data: PositionCompetencyUpdate,
    db: Session = Depends(get_db),
    current_user: CurrentUser = Depends(require_teacher),
) -> BaseResponse:
    return PositionService.update_position_competency(db, position_id, competency_id, data)


@router.delete("/positions/{position_id}/competencies/{competency_id}", summary="移除岗位胜任力要求")
def remove_competency_from_position(
    position_id: int,
    competency_id: int,
    db: Session = Depends(get_db),
    current_user: CurrentUser = Depends(require_teacher),
) -> BaseResponse:
    return PositionService.remove_competency_from_position(db, position_id, competency_id)
```

- [ ] **Step 2: 在 `main.py` 中注册路由**

在 `backend/app/main.py` 中添加：

1. 添加 import（在现有 router import 附近）：
```python
from app.domains.position.router import router as position_router
```

2. 添加路由注册（在现有 `app.include_router` 附近）：
```python
app.include_router(position_router, prefix=settings.API_PREFIX)
```

- [ ] **Step 3: 启动后端验证路由注册**

```bash
cd backend
.\venv\Scripts\python.exe -c "
from app.main import app
routes = [r.path for r in app.routes]
paths = [r for r in routes if '/positions' in r or '/competencies' in r]
print(len(paths) > 0)
print(paths)
"
```

Expected: 输出 `True` 和所有 position/competency 相关路由路径

- [ ] **Step 4: 提交**

```bash
git add backend/app/domains/position/router.py backend/app/main.py
git commit -m "feat(position): add API routes and register in main app

- GET/POST/PUT/DELETE /competencies
- GET/POST/PUT/DELETE /positions
- POST/PUT/DELETE /positions/{id}/competencies
- Teacher/Admin auth required for write operations"
```

---

### Task 7: 端到端验证

**Files:**
- 无新文件，仅验证

- [ ] **Step 1: 启动后端**

```bash
cd backend
.\venv\Scripts\python.exe -m uvicorn app.main:app --host 127.0.0.1 --port 8000
```

- [ ] **Step 2: 验证 API 可用**

```bash
# 登录获取 token
$token = (Invoke-RestMethod -Uri "http://127.0.0.1:8000/api/v1/auth/login" -Method Post -Body '{"username":"admin","password":"admin123"}' -ContentType "application/json").data.access_token

# 创建胜任力
Invoke-RestMethod -Uri "http://127.0.0.1:8000/api/v1/competencies" -Method Post -Headers @{Authorization="Bearer $token"} -Body '{"code":"PROG-PY","name":"Python编程","category":"technical"}' -ContentType "application/json"

# 创建岗位
Invoke-RestMethod -Uri "http://127.0.0.1:8000/api/v1/positions" -Method Post -Headers @{Authorization="Bearer $token"} -Body '{"code":"FE-001","name":"前端工程师","category":"technical","level":"junior"}' -ContentType "application/json"

# 添加胜任力到岗位
Invoke-RestMethod -Uri "http://127.0.0.1:8000/api/v1/positions/1/competencies" -Method Post -Headers @{Authorization="Bearer $token"} -Body '{"competency_id":1,"required_level":3}' -ContentType "application/json"

# 查看岗位详情（含胜任力矩阵）
Invoke-RestMethod -Uri "http://127.0.0.1:8000/api/v1/positions/1" -Headers @{Authorization="Bearer $token"}
```

Expected: 所有请求返回 `code: 200`，岗位详情中 `competencies` 数组包含刚添加的胜任力

- [ ] **Step 3: 停止后端，提交**

```bash
git add -A
git commit --allow-empty -m "test: verify position domain API end-to-end"
```
