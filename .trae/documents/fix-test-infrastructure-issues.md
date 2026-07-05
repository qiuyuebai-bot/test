# 修复测试基础设施三个预存问题

## Context

当前后端测试基线为 148 通过 + 1 个 Windows 文件锁 teardown 错误。但有两个测试文件被整体排除在测试运行之外：
- `test_api_routes.py` — 约 17 个测试因 401 认证失败
- `test_knowledge_service.py` — 触发 79.3MB ONNX 模型下载，阻塞测试

此外，`conftest.py` 的 session teardown 在 Windows 上偶发 `PermissionError: [WinError 32]` 文件锁错误。

本计划修复这三个问题，使完整测试套件（148 + 17 + 知识库测试）可在无网络、无外部依赖的环境下运行。

## 问题1：test_api_routes.py 401 认证失败

### 根因
`conftest.py` 已提供完整的 JWT 认证 fixture 链（`auth_headers`/`admin_auth_headers`，行 187-218），`test_auth.py` 正确使用了此模式。但 `test_api_routes.py` 中约 17 个测试方法未注入 `auth_headers` 参数，也未在 `client.*` 调用中传递 `headers=`，导致所有受 `get_current_user`/`require_role` 保护的端点返回 401。

### 修复方案
为每个失败测试方法添加对应的 `auth_headers` 或 `admin_auth_headers` 参数，并在 `client.*` 调用中传递 `headers=`。

**文件**：`backend/tests/test_api_routes.py`

#### 需添加 `auth_headers`（learner 角色，端点用 `get_current_user`）的测试：

| 测试方法 | 行号 | 端点 |
|---------|------|------|
| test_analyze_learning | 112 | POST /learners/{id}/analyze |
| test_anonymize_learner | 117 | POST /learners/{id}/anonymize |
| test_get_agent_tasks | 186 | GET /agent/tasks |
| test_diagnose | 193 | POST /agent/diagnose |
| test_get_metrics (TestAgentRoutes) | 202 | GET /agent/metrics/hallucination |
| test_generate_resources | 211 | POST /resources/generate/sync |
| test_get_resources | 222 | GET /resources |
| test_get_report | 229 | GET /report/learner/{id} |
| test_get_heatmap | 236 | GET /report/heatmap/{id} |
| test_get_match_curve | 241 | GET /report/match-curve/{id} |
| test_submit_answer | 251 | POST /tutoring/answer |
| test_get_tutoring_history | 268 | GET /tutoring/history/{id} |

每个方法：函数签名加 `auth_headers: dict` 参数，`client.get/post(...)` 调用加 `headers=auth_headers`。

#### 需添加 `admin_auth_headers`（admin/teacher 角色）的测试：

| 测试方法 | 行号 | 端点 | 鉴权 |
|---------|------|------|------|
| test_get_learner_list | 65 | GET /learners | require_teacher（admin 可通过） |
| test_create_doc | 129 | POST /knowledge/upload | require_admin |

每个方法：函数签名加 `admin_auth_headers: dict` 参数，调用加 `headers=admin_auth_headers`。

#### TestErrorHandling 类（3 个测试）：

| 测试方法 | 行号 | 修复 |
|---------|------|------|
| test_invalid_json | 277 | 加 `auth_headers` 参数 + `headers=auth_headers`（与现有 Content-Type header 合并） |
| test_missing_required_fields | 286 | 加 `auth_headers` 参数 + `headers=auth_headers` |
| test_invalid_page_params | 291 | 加 `admin_auth_headers` 参数 + `headers=admin_auth_headers`；断言 `in [200, 422]` 保持不变（admin 角色 + 无效参数返回 200 或 422） |

**test_invalid_json 注意**：当前 `headers={"Content-Type": "application/json"}` 需改为合并 auth header：`headers={**auth_headers, "Content-Type": "application/json"}`。

## 问题2：ChromaDB ONNX 模型下载阻塞

### 根因
`KnowledgeService.search()` 在 `_CHROMA_AVAILABLE=True` 时调用 `collection.query(query_texts=[...])`，触发 ChromaDB 默认 `ONNXMiniLM_L6_V2` 嵌入函数下载 79.3MB ONNX 模型。3 个搜索测试（`test_search_by_keyword`、`test_search_by_industry`、`test_search_empty_result`）会触发此路径。

### 修复方案
在 `conftest.py` 添加 session 级 autouse fixture，将 `_CHROMA_AVAILABLE` 设为 `False`，使 `search()` 走已有的数据库关键词 LIKE 回退路径（`knowledge_service.py:568-617`）。

**文件**：`backend/tests/conftest.py`

在认证 fixture 区块后添加：
```python
@pytest.fixture(autouse=True, scope="session")
def _disable_chroma_for_tests():
    """禁用 ChromaDB，避免测试时下载 79.3MB ONNX 模型。
    search() 会回退到数据库关键词 LIKE 检索路径。"""
    from app.services import knowledge_service as ks
    original = ks._CHROMA_AVAILABLE
    ks._CHROMA_AVAILABLE = False
    ks._chroma_client = None
    ks._chroma_collection = None
    yield
    ks._CHROMA_AVAILABLE = original
```

**验证回退路径匹配**：
- `sample_knowledge_slices` fixture（conftest.py:308-330）seed 的切片内容含 "卷积神经网络(CNN)"，LIKE `%卷积神经网络%` 匹配 → `test_search_by_keyword` 的 `len(results) > 0` 通过
- `test_search_by_industry` 仅断言 `isinstance(results, list)` → 通过
- `test_search_empty_result` 查询 "不存在的关键词xyzabc123"，LIKE 无匹配 → `len(results) == 0` 通过
- `delete_doc`/`batch_delete` 跳过 Chroma 块（`knowledge_service.py:407`），仅做 DB 软删除 → 通过

## 问题3：Windows test.db 文件锁 teardown 错误

### 根因
`engine` fixture（conftest.py:47-62）使用文件型 SQLite（`sqlite:///./data/test.db`）+ 默认 `QueuePool`。teardown 中 `engine.dispose()` 无法关闭已 checkout 的连接，且 Python `sqlite3.Connection` 包装对象在 GC 前不释放 OS 文件句柄，导致 `os.remove(db_path)` 偶发 `WinError 32`。

### 修复方案
切换到内存型 SQLite（`:memory:`）+ `StaticPool`，彻底消除文件，无需 `os.remove`。

**文件**：`backend/tests/conftest.py`

**修改1**：行44，URL 改为内存型：
```python
TEST_DATABASE_URL = "sqlite:///:memory:"
```

**修改2**：行12，import 添加 `StaticPool`：
```python
from sqlalchemy import create_engine, text
from sqlalchemy.pool import StaticPool
```

**修改3**：行50-54，engine 创建添加 `poolclass=StaticPool`：
```python
test_engine = create_engine(
    TEST_DATABASE_URL,
    connect_args={"check_same_thread": False},
    poolclass=StaticPool,
    echo=False,
)
```
`StaticPool` 使所有 Session 共享同一连接，确保 `:memory:` 数据库在整个 session 间保持。

**修改4**：行57-62，teardown 删除 `os.remove` 相关代码（无文件需删除）：
```python
yield test_engine
Base.metadata.drop_all(bind=test_engine)
test_engine.dispose()
```

## 验证

### 步骤1：运行完整后端测试（不再排除任何文件）
```powershell
cd c:\Users\22602\Desktop\新建文件夹\backend
.\venv\Scripts\python.exe -m pytest tests\ -q
```
**预期**：
- `test_api_routes.py`：27 测试全部通过（含之前 401 的 17 个）
- `test_knowledge_service.py`：全部通过（无 ONNX 下载）
- `test_tutoring_service.py`：无 WinError 32 teardown 错误
- 总计：148 + 17 + 知识库测试 ≈ 175+ 测试通过，0 错误

### 步骤2：确认无网络下载
检查 `~/.cache/chroma/onnx_models/` 未被创建（或已存在则无新增下载）。

### 步骤3：确认无 test.db 文件残留
检查 `backend/data/test.db` 不存在（已切换到 :memory:）。

## 假设与约束

1. **不改生产代码**：三个修复仅涉及测试文件（`conftest.py`、`test_api_routes.py`），不修改任何业务逻辑
2. **ChromaDB 禁用仅限测试**：通过 fixture 设置 `_CHROMA_AVAILABLE=False`，不影响生产运行时
3. **认证 fixture 已存在**：`auth_headers`/`admin_auth_headers` 已在 conftest.py 中定义并验证可用（test_auth.py 使用），本计划仅将其注入到未使用的测试中
4. **Edit 持久化 bug**：每次 Edit 后用 Grep 验证，未持久化则重试
5. **内存数据库兼容**：`StaticPool` + `:memory:` 是 SQLAlchemy 官方推荐的 SQLite 测试方案，所有 fixture 共享同一连接
