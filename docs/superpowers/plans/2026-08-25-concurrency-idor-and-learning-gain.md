# 并发竞态与 IDOR 越权修复 + 多轮学习增益证据 实施计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 修复代码审查残留的并发竞态（BaseAgent 状态机、LLM httpx 客户端单例）与 Agent 路由 IDOR 越权（任务列表全量泄露、SSE 无归属任务、聚合统计无过滤、ENTERPRISE 角色边界宽松），并产出多轮"推荐→学习→再测"增益曲线证据，消除"协作不畅"与安全风险扣分隐患。

**Architecture:** 三层修复——agents 层把 BaseAgent 状态机改为"活跃任务集合"模型（状态归属"任一任务执行中"而非"最后一个启动的任务"）；权限层新增统一的"可访问学习者边界"查询（`_accessible_learner_query`，ENTERPRISE 收紧为同企业 fail-closed），`check_data_permission` 与列表接口共用；路由层对任务列表/SSE/聚合统计默认按可访问范围过滤。证据层新增增益曲线脚本：每轮固定难度 pre-test → 真实推荐 → 自适应学习（真实 `process_answer` 闭环）→ 同难度 post-test，增益来自系统真实的画像更新机制（答对 +2 / 答错 -1），非注水。

**Tech Stack:** FastAPI + SQLAlchemy 2.0 + pytest（后端）；证据脚本复用 `AdaptiveTutoringService` 真实服务流程与 `generate_answer_samples.py` 的透明作答模拟。

## Global Constraints

- 所有 pytest / python 命令在 `c:\Users\22602\Desktop\test\backend` 目录下执行（PowerShell）。
- 最小修改：只动问题代码，不重构无关内容；保持既有响应结构（`code/message/data`）与代码风格。
- 诚实证据红线：不注水答题数据、不篡改指标口径；一切模拟假设在证据 JSON 与文档中显式披露。
- pre/post 测试会话 ID 必须以 `diag_` 前缀命名（`diag_gain_...`），按 `metric_service._practice_answer_query` 现有口径排除出 answer_accuracy / resource_match_effectiveness（能力摸底不反映练习正确率）；学习阶段会话（`gain_...`）计入练习口径。
- 每个任务结束跑通该任务测试并提交一次；Task 4/6 完成后须跑全量测试确认无回归。
- git 提交信息用 `fix:` / `feat:` / `docs:` 前缀 + 中文摘要。

---

### Task 1: BaseAgent 状态机并发竞态修复

**Files:**
- Modify: `backend/app/agents/base.py`
- Modify: `backend/app/agents/judge_agent.py:186,243`（删除 `debate_cross_validate` 内两处游离状态写入）
- Test: `backend/tests/test_agent_concurrency.py`（新建）

**Interfaces:**
- Produces: `BaseAgent._active_tasks: set`（活跃任务集合）；`run()` 结束后仅当集合为空才回落 IDLE；`validate()` 纯函数化（不再写共享状态）；`get_status()` 返回锁内快照。下游（orchestrator、路由）消费的 `get_status()` 返回结构不变。
- 行为变化说明（写入提交信息）：原实现 except 分支设置的 `ERROR` 瞬态本就被 `finally` 立即覆盖为 IDLE（不可观测），本次移除该瞬态写入，失败信息保留在 `last_error`。

**背景（为什么这是竞态）:** orchestrator 单例（`orchestrator.py:558-559`）中每种 Agent 只有一个实例，多个任务通过 `run()` 并发复用。旧 `finally`（base.py:145-148）无条件清 `current_task_id`/置 IDLE，任务 A 结束会破坏任务 B 的运行态；`validate()`（160/174 行）、`reset()`（209-211 行）、`_add_log()`（193-203 行）均无锁；judge_agent.py 186/243 行还有两处绕过状态机的直接 `self.status` 写入。

- [ ] **Step 1: 写失败测试**

创建 `backend/tests/test_agent_concurrency.py`：

```python
"""BaseAgent 并发竞态回归测试（代码审查残留问题：单例 Agent 实例被并发任务复用）。"""
import threading

from app.agents.base import AgentStatus, BaseAgent


class DummyAgent(BaseAgent):
    """execute 可控的测试 Agent：按 input_data["n"] 分派启停事件。"""

    def __init__(self):
        super().__init__("dummy", "Dummy")
        self._started: dict = {}
        self._release: dict = {}

    def execute(self, input_data, context=None):
        n = input_data["n"]
        self._started[n] = threading.Event()
        self._release[n] = threading.Event()
        self._started[n].set()
        assert self._release[n].wait(timeout=5), "测试执行超时"
        if input_data.get("fail"):
            raise RuntimeError("boom")
        return {"success": True}


def _run_in_thread(agent, task_id, **payload):
    thread = threading.Thread(
        target=agent.run, args=(task_id, dict(payload, n=task_id))
    )
    thread.start()
    return thread


def test_concurrent_runs_do_not_clobber_each_others_state():
    """任务A先结束不得把任务B的 RUNNING 状态清成 IDLE（原 finally 无条件清除的竞态）。"""
    agent = DummyAgent()

    t_a = _run_in_thread(agent, 1)
    assert agent._started[1].wait(timeout=5)

    t_b = _run_in_thread(agent, 2)
    assert agent._started[2].wait(timeout=5)

    agent._release[1].set()  # A 先结束，B 仍在运行
    t_a.join(timeout=5)

    status = agent.get_status()
    assert status["status"] == AgentStatus.RUNNING  # 旧代码：A 的 finally 置 IDLE → 失败
    assert status["current_task_id"] == 2

    agent._release[2].set()
    t_b.join(timeout=5)

    status = agent.get_status()
    assert status["status"] == AgentStatus.IDLE
    assert status["current_task_id"] is None


def test_error_keeps_last_error_and_returns_to_idle_when_all_done():
    agent = DummyAgent()

    t_a = _run_in_thread(agent, 1, fail=True)
    t_b = _run_in_thread(agent, 2)
    assert agent._started[1].wait(timeout=5)
    assert agent._started[2].wait(timeout=5)

    agent._release[1].set()
    t_a.join(timeout=5)
    assert agent.get_status()["status"] == AgentStatus.RUNNING  # B 仍在运行
    assert agent.get_status()["last_error"] == "boom"

    agent._release[2].set()
    t_b.join(timeout=5)
    assert agent.get_status()["status"] == AgentStatus.IDLE


def test_validate_does_not_break_running_state():
    """validate 不得改写共享状态（旧代码将并发任务的 RUNNING 覆盖为 IDLE）。"""
    agent = DummyAgent()
    t = _run_in_thread(agent, 1)
    assert agent._started[1].wait(timeout=5)

    agent.validate({"ok": True})
    agent.validate(None)  # 校验失败路径同样不得破坏并发状态
    assert agent.get_status()["status"] == AgentStatus.RUNNING

    agent._release[1].set()
    t.join(timeout=5)
    assert agent.get_status()["status"] == AgentStatus.IDLE


def test_add_log_trims_to_last_100_and_reset_is_atomic():
    agent = DummyAgent()
    for i in range(150):
        agent._add_log({"i": i})
    assert len(agent.execution_log) == 100
    assert agent.execution_log[-1]["i"] == 149
    assert agent.execution_log[0]["i"] == 50

    agent.reset()
    assert agent.get_status() == {
        "agent_type": "dummy",
        "agent_name": "Dummy",
        "status": AgentStatus.IDLE,
        "current_task_id": None,
        "last_error": None,
    }


def test_add_log_concurrent_stress_keeps_exact_cap():
    """并发写日志时裁剪不丢条目：加锁后上限精确为 100。"""
    agent = DummyAgent()

    def append_many():
        for _ in range(300):
            agent._add_log({"x": 1})

    threads = [threading.Thread(target=append_many) for _ in range(4)]
    for t in threads:
        t.start()
    for t in threads:
        t.join(timeout=10)

    assert len(agent.execution_log) == 100
```

- [ ] **Step 2: 运行测试确认失败**

```
cd c:\Users\22602\Desktop\test\backend
python -m pytest tests/test_agent_concurrency.py -v
```

预期：`test_concurrent_runs_do_not_clobber_each_others_state`、`test_error_keeps_last_error_and_returns_to_idle_when_all_done`、`test_validate_does_not_break_running_state` FAIL（AssertionError：`'idle' == 'running'` 或 last_error 为 None）；其余 2 个 PASS。

- [ ] **Step 3: 修改 base.py**

Edit 1 —— `__init__`（第 40-41 行），锁改 RLock 并新增活跃任务集合：

```python
        self.execution_log = []
        self._lock = threading.RLock()
        # 活跃任务集合：Agent 实例被多个任务并发复用时，状态机归属"任一任务执行中"
        self._active_tasks: set = set()
```

Edit 2 —— `run()` 成功路径（第 96-100 行），删除提前置 IDLE（终态统一由 finally 管理）：

```python
            result["_meta"] = {
                "agent_type": self.agent_type,
                "agent_name": self.agent_name,
                "duration_ms": duration_ms,
                "success": True,
            }

            log_entry = {
```
（即删除 `with self._lock: self.status = AgentStatus.IDLE` 两行，`result["_meta"]` 赋值后直接接日志构造。）

Edit 3 —— `run()` 异常路径（第 115-118 行），保留 last_error，删除 ERROR 瞬态：

```python
        except Exception as e:
            with self._lock:
                self.last_error = str(e)
```

Edit 4 —— `run()` 的 `finally`（第 145-148 行）改为集合裁决：

```python
        finally:
            with self._lock:
                self._active_tasks.discard(task_id)
                if not self._active_tasks:
                    self.status = AgentStatus.IDLE
                    self.current_task_id = None
```

Edit 5 —— `validate()` 删除两处状态写（第 160 行 `self.status = AgentStatus.VALIDATING` 与第 174 行 `self.status = AgentStatus.IDLE`），方法变为纯校验：

```python
    def validate(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """
        校验输出数据质量

        纯函数化：不再改写共享状态，避免与并发 run() 的状态机互相覆盖

        Args:
            data: 待校验的数据

        Returns:
            校验结果
        """
        result = {
            "passed": True,
            "issues": [],
            "score": 100,
        }

        # 基础校验
        if not data or not isinstance(data, dict):
            result["passed"] = False
            result["issues"].append("输出数据为空或格式错误")
            result["score"] = 0

        return result
```

Edit 6 —— `get_status()` 改为锁内快照：

```python
    def get_status(self) -> Dict[str, Any]:
        """
        获取Agent状态信息（锁内一致快照）

        Returns:
            状态字典
        """
        with self._lock:
            return {
                "agent_type": self.agent_type,
                "agent_name": self.agent_name,
                "status": self.status,
                "current_task_id": self.current_task_id,
                "last_error": self.last_error,
            }
```

Edit 7 —— `_add_log()` 加锁（append 与裁剪原子化）：

```python
    def _add_log(self, log_entry: Dict[str, Any]) -> None:
        """
        添加执行日志

        Args:
            log_entry: 日志条目
        """
        with self._lock:
            self.execution_log.append(log_entry)
            # 最多保留100条日志
            if len(self.execution_log) > 100:
                self.execution_log = self.execution_log[-100:]
```

Edit 8 —— `reset()` 加锁并清空活跃集合：

```python
    def reset(self) -> None:
        """
        重置Agent状态
        """
        with self._lock:
            self.status = AgentStatus.IDLE
            self.current_task_id = None
            self.last_error = None
            self._active_tasks.clear()
```

- [ ] **Step 4: 修改 judge_agent.py（删除两处游离状态写入）**

Edit 1 —— 第 186 行（`debate_cross_validate` 开头）：

```python
        previous_debates = previous_debates or []
```
（删除其上方的 `self.status = AgentStatus.VALIDATING` 与紧随的空行。）

Edit 2 —— 第 239-245 行：

```python
        if current_round >= max_rounds:
            debate_result["debate_ended"] = True
            debate_result["reason"] = "达到最大辩论轮次"

        return debate_result
```
（删除 `self.status = AgentStatus.IDLE` 一行。）

若删除后 `AgentStatus` 在 judge_agent.py 中不再被引用，一并移除其 import（ruff 会提示 F401）。

- [ ] **Step 5: 运行测试确认通过**

```
python -m pytest tests/test_agent_concurrency.py -v
```
预期：5 个用例全部 PASS。

再跑受影响的 Agent 相关既有测试确认无回归：
```
python -m pytest tests/test_agent_statistics.py tests/test_agent_collaboration.py -q
```
预期：全部 PASS（get_status 返回结构未变；若有用例依赖 `ERROR` 瞬态或 `VALIDATING` 状态，按新语义修正断言——终态恒为 IDLE、失败看 `last_error`）。

- [ ] **Step 6: 提交**

```
git add backend/app/agents/base.py backend/app/agents/judge_agent.py backend/tests/test_agent_concurrency.py
git commit -m "fix(agents): BaseAgent 状态机改活跃任务集合模型，消除并发 run/validate/reset 竞态"
```

---

### Task 2: LLMUtil httpx 客户端单例 check-then-act 竞态修复

**Files:**
- Modify: `backend/app/utils/llm.py`（类属性区 + `_get_sync_client`/`_get_async_client`/`close_clients`/`aclose_clients`）
- Test: `backend/tests/test_llm_client_singleton.py`（新建）

**Interfaces:**
- Produces: `LLMUtil._sync_client_lock: threading.Lock`、`LLMUtil._async_client_lock: threading.Lock`；`_get_sync_client`/`_get_async_client` 语义不变（单例、连接池复用），仅并发下保证只创建一次。参考项目中已验证正确的 DCL 模式：`backend/app/domains/knowledge/service.py:74-101`（Chroma 集合单例）。

- [ ] **Step 1: 写失败测试**

创建 `backend/tests/test_llm_client_singleton.py`：

```python
"""LLM httpx 客户端单例并发创建回归测试（check-then-act 竞态修复）。"""
import threading

import app.utils.llm as llm_module
from app.utils.llm import LLMUtil


def _run_concurrent_getter(getter, workers=16):
    """barrier 对齐后并发调用 getter，返回 (clients, barrier)。"""
    barrier = threading.Barrier(workers)
    clients = []

    def worker():
        barrier.wait()
        clients.append(getter())

    threads = [threading.Thread(target=worker) for _ in range(workers)]
    for t in threads:
        t.start()
    for t in threads:
        t.join(timeout=10)
    return clients


def test_sync_client_created_once_under_concurrency(monkeypatch):
    created = []

    class CountingClient(llm_module.httpx.Client):
        def __init__(self, *args, **kwargs):
            created.append(1)
            super().__init__(*args, **kwargs)

    monkeypatch.setattr(llm_module.httpx, "Client", CountingClient)

    LLMUtil._sync_client = None
    try:
        clients = _run_concurrent_getter(LLMUtil._get_sync_client)
        assert len(clients) == 16
        assert all(c is clients[0] for c in clients)
        assert len(created) == 1  # 旧代码：多线程同时通过 None 检查 → created > 1
    finally:
        LLMUtil.close_clients()
        LLMUtil._sync_client = None


def test_async_client_created_once_under_concurrency(monkeypatch):
    created = []

    class CountingAsyncClient(llm_module.httpx.AsyncClient):
        def __init__(self, *args, **kwargs):
            created.append(1)
            super().__init__(*args, **kwargs)

    monkeypatch.setattr(llm_module.httpx, "AsyncClient", CountingAsyncClient)

    LLMUtil._async_client = None
    try:
        clients = _run_concurrent_getter(LLMUtil._get_async_client)
        assert len(clients) == 16
        assert all(c is clients[0] for c in clients)
        assert len(created) == 1
    finally:
        LLMUtil._async_client = None
```

- [ ] **Step 2: 运行测试确认失败**

```
python -m pytest tests/test_llm_client_singleton.py -v
```

预期：两个用例大概率 FAIL（`assert 1 == N`，N>1；barrier 使碰撞概率接近 1）。若偶发通过，重跑一次——该竞态在 16 线程 barrier 对齐下几乎必现。

- [ ] **Step 3: 修改 llm.py**

Edit 1 —— 类属性区（第 48-49 行后）新增锁：

```python
    _sync_client: Optional[httpx.Client] = None
    _async_client: Optional[httpx.AsyncClient] = None
    # 客户端单例双重检查锁（与 knowledge/service.py 的 Chroma DCL 同模式）
    _sync_client_lock: threading.Lock = threading.Lock()
    _async_client_lock: threading.Lock = threading.Lock()
```

Edit 2 —— `_get_sync_client`（第 92-118 行）改为 DCL（`if` 体内包一层 `with cls._sync_client_lock:` + 二次检查，创建逻辑原样内移）：

```python
    @classmethod
    def _get_sync_client(cls, timeout: float = 120.0) -> httpx.Client:
        """
        获取同步 httpx 客户端（单例，复用连接池；双重检查锁防并发重复创建）
        """
        if cls._sync_client is None or cls._sync_client.is_closed:
            with cls._sync_client_lock:
                if cls._sync_client is None or cls._sync_client.is_closed:
                    cls._sync_client = httpx.Client(
                        timeout=timeout,
                        limits=httpx.Limits(
                            max_connections=20,
                            max_keepalive_connections=10,
                            keepalive_expiry=30.0,
                        ),
                        headers=cls._default_headers(),
                        # 不使用系统代理环境变量（HTTP_PROXY/HTTPS_PROXY）：
                        # 本机配置了失效代理（127.0.0.1:7892 未运行），trust_env=True 会走代理导致
                        # WinError 10061 连接被拒；LLM API（DeepSeek）实测可直连，故绕过系统代理。
                        trust_env=False,
                    )
                    logger.debug("[LLM] 创建同步 httpx 客户端（连接池模式）")
        return cls._sync_client
```

Edit 3 —— `_get_async_client`（第 120-143 行）同构：

```python
    @classmethod
    def _get_async_client(cls, timeout: float = 120.0) -> httpx.AsyncClient:
        """
        获取异步 httpx 客户端（单例，复用连接池；双重检查锁防并发重复创建）
        """
        if cls._async_client is None or cls._async_client.is_closed:
            with cls._async_client_lock:
                if cls._async_client is None or cls._async_client.is_closed:
                    cls._async_client = httpx.AsyncClient(
                        timeout=timeout,
                        limits=httpx.Limits(
                            max_connections=20,
                            max_keepalive_connections=10,
                            keepalive_expiry=30.0,
                        ),
                        headers=cls._default_headers(),
                        trust_env=False,  # 同同步客户端：绕过失效的系统代理
                    )
                    logger.debug("[LLM] 创建异步 httpx 客户端（连接池模式）")
        return cls._async_client
```

Edit 4 —— `close_clients`（第 153-161 行）持锁清理：

```python
    @classmethod
    def close_clients(cls) -> None:
        """关闭所有客户端连接（应用退出时调用）"""
        with cls._sync_client_lock:
            if cls._sync_client is not None and not cls._sync_client.is_closed:
                cls._sync_client.close()
                cls._sync_client = None
                logger.debug("[LLM] 同步 httpx 客户端已关闭")
        with cls._async_client_lock:
            if cls._async_client is not None and not cls._async_client.is_closed:
                cls._async_client = None
```

Edit 5 —— `aclose_clients`（第 163-172 行）持锁清理：

```python
    @classmethod
    async def aclose_clients(cls) -> None:
        """异步关闭所有客户端连接（ASGI shutdown 时调用）"""
        with cls._sync_client_lock:
            if cls._sync_client is not None and not cls._sync_client.is_closed:
                cls._sync_client.close()
                cls._sync_client = None
        with cls._async_client_lock:
            if cls._async_client is not None and not cls._async_client.is_closed:
                await cls._async_client.aclose()
                cls._async_client = None
                logger.debug("[LLM] 异步 httpx 客户端已关闭")
```

- [ ] **Step 4: 运行测试确认通过**

```
python -m pytest tests/test_llm_client_singleton.py tests/test_llm_adapters.py -v
```
预期：全部 PASS。

- [ ] **Step 5: 提交**

```
git add backend/app/utils/llm.py backend/tests/test_llm_client_singleton.py
git commit -m "fix(llm): httpx 客户端单例加双重检查锁，消除 check-then-act 竞态"
```

---

### Task 3: 统一"可访问学习者边界"（ENTERPRISE 收紧 + get_accessible_learner_ids）

**Files:**
- Modify: `backend/app/domains/learner/service.py`（import 区 + `check_data_permission`，第 684-733 行）
- Test: `backend/tests/test_learner_permission_boundary.py`（新建）

**Interfaces:**
- Produces:
  - `LearnerService._accessible_learner_query(db: Session, user: User) -> Query[LearnerProfile]`（内部方法，角色边界唯一事实源）
  - `LearnerService.get_accessible_learner_ids(db: Session, user_id: int) -> List[int]`（Task 4/6 的列表过滤用）
  - `check_data_permission(db, user_id, learner_id) -> bool` 签名不变
- 角色边界（部署策略集中化）：ADMIN 全量；ENTERPRISE 同企业（任一方 `enterprise_name` 为空即拒绝，fail-closed）；TEACHER 全量（与教师看板现行暴露面一致，集中声明）；LEARNER 仅本人。
- 行为变化：ENTERPRISE 原先"学习者存在即放行"→ 收紧为同企业匹配。既有测试若依赖旧行为需按新语义修正（仅限 ENTERPRISE 相关断言）。

- [ ] **Step 1: 写失败测试**

创建 `backend/tests/test_learner_permission_boundary.py`：

```python
"""LearnerService 数据权限边界回归测试（ENTERPRISE 收紧 + 统一可访问集合）。"""
import uuid

from app.models import (
    EducationLevelEnum,
    LearnerProfile,
    LearningStyleEnum,
    User,
    UserRoleEnum,
)
from app.domains.learner.service import LearnerService


def _make_user(db_session, role, enterprise_name=None):
    user = User(
        username=f"u_{role.value}_{uuid.uuid4().hex[:8]}",
        password_hash="not-a-real-hash",
        role=role,
        enterprise_name=enterprise_name,
        is_active=True,
    )
    db_session.add(user)
    db_session.commit()
    db_session.refresh(user)
    return user


def _make_learner(db_session, user):
    profile = LearnerProfile(
        user_id=user.id,
        real_name=f"学习者{user.id}",
        display_name=f"Learner{user.id}",
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
        knowledge_blind_areas=["模型蒸馏"],
        knowledge_strengths=["Python编程"],
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


def test_learner_role_only_sees_own_profile(db_session):
    user_a = _make_user(db_session, UserRoleEnum.LEARNER)
    user_b = _make_user(db_session, UserRoleEnum.LEARNER)
    learner_a = _make_learner(db_session, user_a)
    learner_b = _make_learner(db_session, user_b)

    assert LearnerService.check_data_permission(db_session, user_a.id, learner_a.id) is True
    assert LearnerService.check_data_permission(db_session, user_a.id, learner_b.id) is False


def test_enterprise_role_scoped_to_same_enterprise(db_session):
    ent_acme = _make_user(db_session, UserRoleEnum.ENTERPRISE, enterprise_name="Acme")
    ent_beta = _make_user(db_session, UserRoleEnum.ENTERPRISE, enterprise_name="Beta")
    ent_blank = _make_user(db_session, UserRoleEnum.ENTERPRISE, enterprise_name=None)

    acme_member = _make_user(db_session, UserRoleEnum.LEARNER, enterprise_name="Acme")
    beta_member = _make_user(db_session, UserRoleEnum.LEARNER, enterprise_name="Beta")
    no_ent_member = _make_user(db_session, UserRoleEnum.LEARNER, enterprise_name=None)

    acme_learner = _make_learner(db_session, acme_member)
    beta_learner = _make_learner(db_session, beta_member)
    no_ent_learner = _make_learner(db_session, no_ent_member)

    # 同企业放行
    assert LearnerService.check_data_permission(db_session, ent_acme.id, acme_learner.id) is True
    # 跨企业拒绝（旧代码：学习者存在即 True → 失败）
    assert LearnerService.check_data_permission(db_session, ent_acme.id, beta_learner.id) is False
    assert LearnerService.check_data_permission(db_session, ent_beta.id, acme_learner.id) is False
    # 企业归属缺失 fail-closed
    assert LearnerService.check_data_permission(db_session, ent_acme.id, no_ent_learner.id) is False
    assert LearnerService.check_data_permission(db_session, ent_blank.id, acme_learner.id) is False


def test_teacher_and_admin_policies_unchanged(db_session):
    teacher = _make_user(db_session, UserRoleEnum.TEACHER)
    admin = _make_user(db_session, UserRoleEnum.ADMIN)
    member = _make_user(db_session, UserRoleEnum.LEARNER)
    learner = _make_learner(db_session, member)

    assert LearnerService.check_data_permission(db_session, teacher.id, learner.id) is True
    assert LearnerService.check_data_permission(db_session, admin.id, learner.id) is True


def test_get_accessible_learner_ids_matches_boundary(db_session):
    ent_acme = _make_user(db_session, UserRoleEnum.ENTERPRISE, enterprise_name="Acme")
    member_a = _make_user(db_session, UserRoleEnum.LEARNER, enterprise_name="Acme")
    member_b = _make_user(db_session, UserRoleEnum.LEARNER, enterprise_name=None)
    learner_a = _make_learner(db_session, member_a)
    _make_learner(db_session, member_b)

    assert LearnerService.get_accessible_learner_ids(db_session, ent_acme.id) == [learner_a.id]
    assert LearnerService.get_accessible_learner_ids(db_session, 999999) == []
```

- [ ] **Step 2: 运行测试确认失败**

```
python -m pytest tests/test_learner_permission_boundary.py -v
```

预期：`test_enterprise_role_scoped_to_same_enterprise` FAIL（跨企业返回 True）；`test_get_accessible_learner_ids_matches_boundary` FAIL（`AttributeError: ... no attribute 'get_accessible_learner_ids'`）；其余 PASS。

- [ ] **Step 3: 修改 learner/service.py**

Edit 1 —— 第 8 行 import 增加 `false`：

```python
from sqlalchemy import false, or_
```

Edit 2 —— 替换 `check_data_permission`（第 684-733 行）为统一边界实现：

```python
    @staticmethod
    def _accessible_learner_query(db: Session, user: User):
        """当前用户可访问的学习者画像 Query（角色边界唯一事实源）。

        - ADMIN：全量
        - ENTERPRISE：同企业（任一方 enterprise_name 缺失即拒绝，fail-closed）
        - TEACHER：全量（部署策略：与教师看板/管理路由现行暴露面一致，集中声明）
        - LEARNER：仅本人画像
        """
        query = db.query(LearnerProfile)
        if user.role == UserRoleEnum.ADMIN:
            return query
        if user.role == UserRoleEnum.ENTERPRISE:
            if not user.enterprise_name:
                return query.filter(false())
            return query.join(User, LearnerProfile.user_id == User.id).filter(
                User.enterprise_name == user.enterprise_name,
            )
        if user.role == UserRoleEnum.TEACHER:
            return query
        return query.filter(LearnerProfile.user_id == user.id)

    @staticmethod
    def get_accessible_learner_ids(db: Session, user_id: int) -> List[int]:
        """当前用户可访问的学习者画像 ID 列表（列表类接口的默认范围过滤用）。"""
        user = db.query(User).filter(User.id == user_id).first()
        if not user:
            return []
        rows = (
            LearnerService._accessible_learner_query(db, user)
            .with_entities(LearnerProfile.id)
            .all()
        )
        return [row.id for row in rows]

    @staticmethod
    def check_data_permission(
        db: Session,
        user_id: int,
        learner_id: int,
    ) -> bool:
        """
        检查数据权限（角色边界见 _accessible_learner_query）

        Args:
            db: 数据库会话
            user_id: 当前用户ID
            learner_id: 要访问的学习者ID

        Returns:
            是否有权限
        """
        user = db.query(User).filter(User.id == user_id).first()
        if not user:
            return False
        return (
            LearnerService._accessible_learner_query(db, user)
            .filter(LearnerProfile.id == learner_id)
            .first()
            is not None
        )
```

- [ ] **Step 4: 运行测试确认通过 + 检查既有用例**

```
python -m pytest tests/test_learner_permission_boundary.py tests/test_learner_service.py -v
```
预期：新文件 4 个用例 PASS；`test_learner_service.py` 若有 ENTERPRISE 旧语义断言（存在即放行），按"同企业放行/跨企业拒绝"修正测试数据后 PASS。

- [ ] **Step 5: 提交**

```
git add backend/app/domains/learner/service.py backend/tests/test_learner_permission_boundary.py backend/tests/test_learner_service.py
git commit -m "fix(learner): 统一可访问学习者边界，ENTERPRISE 收紧为同企业 fail-closed"
```

---

### Task 4: 任务列表 IDOR 修复（get_task_list 默认范围过滤）

**Files:**
- Modify: `backend/app/domains/agent/router.py:913-924`（`get_task_list` 的过滤段）
- Test: `backend/tests/test_agent_router_security.py`（新建，Task 5/6 复用其 fixtures）

**Interfaces:**
- Consumes: `LearnerService.get_accessible_learner_ids(db, user_id) -> List[int]`（Task 3）
- Produces: 测试文件内 helpers —— `_auth_headers(user) -> dict`、`_seed_user(db, role, enterprise_name=None) -> User`、`_seed_learner(db, user) -> LearnerProfile`、`_seed_task(db, learner_id, name) -> AgentTask`（Task 5/6 直接引用，签名以此为准）。
- 语义：非管理员不传 `learner_id` 时，仅返回其可访问学习者的任务（不含 `learner_id IS NULL` 的无归属任务）；传 `learner_id` 时沿用既有 `check_data_permission` 校验（HTTP 401）；管理员行为不变。

- [ ] **Step 1: 写失败测试**

创建 `backend/tests/test_agent_router_security.py`：

```python
"""Agent 路由安全回归测试：任务列表 IDOR / SSE 归属 / 聚合统计范围。"""
import uuid

from fastapi.testclient import TestClient

from app.models import (
    AgentTask,
    EducationLevelEnum,
    LearnerProfile,
    LearningStyleEnum,
    User,
    UserRoleEnum,
)
from app.utils.auth import create_access_token


# ========== 共享 helpers（Task 5/6 复用） ==========

def _auth_headers(user: User) -> dict:
    token = create_access_token({
        "user_id": user.id,
        "username": user.username,
        "role": user.role.value,
    })
    return {"Authorization": f"Bearer {token}"}


def _seed_user(db, role, enterprise_name=None) -> User:
    user = User(
        username=f"u_{role.value}_{uuid.uuid4().hex[:8]}",
        password_hash="not-a-real-hash",
        role=role,
        enterprise_name=enterprise_name,
        is_active=True,
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


def _seed_learner(db, user) -> LearnerProfile:
    profile = LearnerProfile(
        user_id=user.id,
        real_name=f"学习者{user.id}",
        display_name=f"Learner{user.id}",
        education_level=EducationLevelEnum.BACHELOR.value,
        major="计算机",
        school="测试大学",
        graduation_year=2021,
        current_position="开发工程师",
        years_of_experience=2,
        learning_style=LearningStyleEnum.VISUAL.value,
        preferred_difficulty=3,
        daily_study_time=60,
        target_industry="人工智能",
        target_position="算法工程师",
        learning_goal="提升",
    )
    db.add(profile)
    db.commit()
    db.refresh(profile)
    return profile


def _seed_task(db, learner_id, name) -> AgentTask:
    task = AgentTask(
        task_name=name,
        task_type="learner_diagnosis",
        agent_type="diagnosis",
        status="completed",
        learner_id=learner_id,
        progress=100.0,
    )
    db.add(task)
    db.commit()
    db.refresh(task)
    return task


# ========== Task 4: 任务列表 IDOR ==========

def test_task_list_without_learner_id_scopes_to_own_tasks(client, db_session):
    user_a = _seed_user(db_session, UserRoleEnum.LEARNER)
    user_b = _seed_user(db_session, UserRoleEnum.LEARNER)
    learner_a = _seed_learner(db_session, user_a)
    learner_b = _seed_learner(db_session, user_b)
    _seed_task(db_session, learner_a.id, "A的任务")
    _seed_task(db_session, learner_b.id, "B的任务")
    _seed_task(db_session, None, "无归属任务")

    response = client.get("/api/v1/agent/tasks", headers=_auth_headers(user_a))

    assert response.status_code == 200
    items = response.json()["data"]["items"]
    task_names = {item["task_name"] for item in items}
    # 旧代码：不传 learner_id 返回全部任务（含 B 与无归属）→ 失败
    assert task_names == {"A的任务"}


def test_task_list_with_foreign_learner_id_rejected(client, db_session):
    user_a = _seed_user(db_session, UserRoleEnum.LEARNER)
    user_b = _seed_user(db_session, UserRoleEnum.LEARNER)
    learner_b = _seed_learner(db_session, user_b)

    response = client.get(
        f"/api/v1/agent/tasks?learner_id={learner_b.id}",
        headers=_auth_headers(user_a),
    )

    assert response.status_code == 401
    assert response.json()["message"] == "无权限查看该学习者任务"


def test_task_list_admin_sees_all(client, db_session):
    admin = _seed_user(db_session, UserRoleEnum.ADMIN)
    user_a = _seed_user(db_session, UserRoleEnum.LEARNER)
    user_b = _seed_user(db_session, UserRoleEnum.LEARNER)
    learner_a = _seed_learner(db_session, user_a)
    learner_b = _seed_learner(db_session, user_b)
    _seed_task(db_session, learner_a.id, "A的任务")
    _seed_task(db_session, learner_b.id, "B的任务")
    _seed_task(db_session, None, "无归属任务")

    response = client.get("/api/v1/agent/tasks", headers=_auth_headers(admin))

    assert response.status_code == 200
    assert response.json()["data"]["total"] == 3


def test_task_list_enterprise_scoped_to_same_enterprise(client, db_session):
    ent_acme = _seed_user(db_session, UserRoleEnum.ENTERPRISE, enterprise_name="Acme")
    ent_beta = _seed_user(db_session, UserRoleEnum.ENTERPRISE, enterprise_name="Beta")
    member_acme = _seed_user(db_session, UserRoleEnum.LEARNER, enterprise_name="Acme")
    member_beta = _seed_user(db_session, UserRoleEnum.LEARNER, enterprise_name="Beta")
    learner_acme = _seed_learner(db_session, member_acme)
    learner_beta = _seed_learner(db_session, member_beta)
    _seed_task(db_session, learner_acme.id, "Acme任务")
    _seed_task(db_session, learner_beta.id, "Beta任务")

    response = client.get("/api/v1/agent/tasks", headers=_auth_headers(ent_acme))

    assert response.status_code == 200
    items = response.json()["data"]["items"]
    assert {item["task_name"] for item in items} == {"Acme任务"}

    # 跨企业显式指定 learner_id 同样拒绝
    response = client.get(
        f"/api/v1/agent/tasks?learner_id={learner_beta.id}",
        headers=_auth_headers(ent_acme),
    )
    assert response.status_code == 401
    # Beta 企业管理员可访问自己企业学习者的任务
    response = client.get(
        f"/api/v1/agent/tasks?learner_id={learner_beta.id}",
        headers=_auth_headers(ent_beta),
    )
    assert response.status_code == 200
```

- [ ] **Step 2: 运行测试确认失败**

```
python -m pytest tests/test_agent_router_security.py -v
```

预期：`test_task_list_without_learner_id_scopes_to_own_tasks` FAIL（返回 3 条）；`test_task_list_enterprise_scoped_to_same_enterprise` FAIL（ENTERPRISE 未过滤/未拒绝）。`test_task_list_with_foreign_learner_id_rejected`、`test_task_list_admin_sees_all` PASS（既有逻辑已覆盖）。

- [ ] **Step 3: 修改 agent/router.py 的 get_task_list**

将第 913-924 行的过滤段：

```python
    try:
        query = db.query(AgentTask)

        if learner_id:
            if not current_user.is_admin:
                if not LearnerService.check_data_permission(db, current_user.user_id, learner_id):
                    return unauthorized("无权限查看该学习者任务")
            query = query.filter(AgentTask.learner_id == learner_id)
        if status:
            query = query.filter(AgentTask.status == status)
        if task_type:
            query = query.filter(AgentTask.task_type == task_type)
```

改为：

```python
    try:
        query = db.query(AgentTask)

        if learner_id:
            if not current_user.is_admin:
                if not LearnerService.check_data_permission(db, current_user.user_id, learner_id):
                    return unauthorized("无权限查看该学习者任务")
            query = query.filter(AgentTask.learner_id == learner_id)
        elif not current_user.is_admin:
            # 非管理员默认仅可见有权访问的学习者的任务（不含无归属任务）
            accessible_ids = LearnerService.get_accessible_learner_ids(
                db, current_user.user_id
            )
            query = query.filter(AgentTask.learner_id.in_(accessible_ids))
        if status:
            query = query.filter(AgentTask.status == status)
        if task_type:
            query = query.filter(AgentTask.task_type == task_type)
```

- [ ] **Step 4: 运行测试确认通过 + 全量回归**

```
python -m pytest tests/test_agent_router_security.py -v
python -m pytest tests -q
```

预期：新用例全部 PASS；全量测试通过。若既有用例（如 test_agent_statistics.py / test_agent_collaboration.py / test_api_routes.py）以普通用户身份调用 `/agent/tasks` 且依赖全量列表，将该调用改为 admin 身份（原语义即"全量"）或为其种子数据补建可访问学习者。

- [ ] **Step 5: 提交**

```
git add backend/app/domains/agent/router.py backend/tests/test_agent_router_security.py
git commit -m "fix(agent): 任务列表默认按可访问学习者过滤，修复水平越权信息泄露"
```

---

### Task 5: SSE 进度流统一归属校验

**Files:**
- Modify: `backend/app/domains/agent/router.py:473-475`（`task_events_stream` 的权限段）
- Test: `backend/tests/test_agent_router_security.py`（追加用例，复用 Task 4 的 helpers）

**Interfaces:**
- Consumes: Task 4 测试文件的 `_auth_headers` / `_seed_user` / `_seed_learner` / `_seed_task`（签名见 Task 4 Produces）；router 内已有的 `_check_task_permission(db, current_user, task)`（第 60-65 行）。
- 语义：与 `get_task_status` 等端点一致——非管理员访问 `learner_id IS NULL` 的任务一律 403（旧代码放行）。

- [ ] **Step 1: 追加失败测试**

在 `backend/tests/test_agent_router_security.py` 末尾追加：

```python
# ========== Task 5: SSE 归属校验 ==========

def test_sse_stream_rejects_unowned_task_for_non_admin(client, db_session):
    user = _seed_user(db_session, UserRoleEnum.LEARNER)
    _seed_learner(db_session, user)
    orphan_task = _seed_task(db_session, None, "无归属任务")

    response = client.get(
        f"/api/v1/agent/tasks/{orphan_task.id}/events",
        headers=_auth_headers(user),
    )

    # 旧代码：learner_id 为 None 时跳过校验直接放流 → 失败
    assert response.status_code == 403
    assert response.json()["detail"] == "无权限访问该任务"


def test_sse_stream_allows_owner(client, db_session):
    user = _seed_user(db_session, UserRoleEnum.LEARNER)
    learner = _seed_learner(db_session, user)
    task = _seed_task(db_session, learner.id, "本人任务")

    response = client.get(
        f"/api/v1/agent/tasks/{task.id}/events",
        headers=_auth_headers(user),
    )

    assert response.status_code == 200


def test_sse_stream_rejects_other_learners_task(client, db_session):
    user_a = _seed_user(db_session, UserRoleEnum.LEARNER)
    user_b = _seed_user(db_session, UserRoleEnum.LEARNER)
    learner_b = _seed_learner(db_session, user_b)
    task_b = _seed_task(db_session, learner_b.id, "B的任务")

    response = client.get(
        f"/api/v1/agent/tasks/{task_b.id}/events",
        headers=_auth_headers(user_a),
    )

    assert response.status_code == 403
```

- [ ] **Step 2: 运行测试确认失败**

```
python -m pytest tests/test_agent_router_security.py -v -k sse
```

预期：`test_sse_stream_rejects_unowned_task_for_non_admin` FAIL（返回 200）；其余两个 PASS（既有 check_data_permission 已覆盖有归属任务）。

- [ ] **Step 3: 修改 task_events_stream**

将第 473-475 行：

```python
    if task.learner_id is not None:
        if not LearnerService.check_data_permission(db, user_id, task.learner_id):
            raise HTTPException(status_code=403, detail="无权限访问该任务")
```

改为（与其他端点同一归属策略，无归属任务对非管理员一律拒绝）：

```python
    if not _check_task_permission(db, current_user, task):
        raise HTTPException(status_code=403, detail="无权限访问该任务")
```

注：`user_id = current_user.user_id`（第 467 行）若因此不再被使用则删除该行（ruff F841 会提示）。

- [ ] **Step 4: 运行测试确认通过**

```
python -m pytest tests/test_agent_router_security.py -v
```
预期：全部 PASS（Task 4 + Task 5 用例）。

- [ ] **Step 5: 提交**

```
git add backend/app/domains/agent/router.py backend/tests/test_agent_router_security.py
git commit -m "fix(agent): SSE 进度流统一归属校验，无归属任务对非管理员拒绝"
```

---

### Task 6: Agent 状态聚合统计按可访问范围过滤

**Files:**
- Modify: `backend/app/domains/agent/router.py`（`get_all_agent_status` 第 274-278 行、`get_agent_status` 第 302-308 行）
- Test: `backend/tests/test_agent_router_security.py`（追加用例，复用 Task 4 的 helpers）

**Interfaces:**
- Consumes: `LearnerService.get_accessible_learner_ids(db, user_id) -> List[int]`（Task 3）；Task 4 helpers。
- 语义：`/agent/status` 与 `/agent/status/{agent_type}` 的任务统计（`total_tasks_handled` 等）对非管理员只统计其可访问学习者的任务；管理员全量。端点仍对所有登录用户可用（不破坏前端看板）。

- [ ] **Step 1: 追加失败测试**

在 `backend/tests/test_agent_router_security.py` 末尾追加：

```python
# ========== Task 6: 聚合统计范围 ==========

def _diagnosis_entry(body):
    for agent in body["data"]["agents"]:
        if agent.get("agent_type") == "diagnosis":
            return agent
    return None


def test_agent_status_statistics_scoped_for_non_admin(client, db_session):
    user_a = _seed_user(db_session, UserRoleEnum.LEARNER)
    user_b = _seed_user(db_session, UserRoleEnum.LEARNER)
    learner_a = _seed_learner(db_session, user_a)
    learner_b = _seed_learner(db_session, user_b)
    _seed_task(db_session, learner_a.id, "A的诊断")
    _seed_task(db_session, learner_b.id, "B的诊断")

    response = client.get("/api/v1/agent/status", headers=_auth_headers(user_a))

    assert response.status_code == 200
    entry = _diagnosis_entry(response.json())
    # 旧代码：统计全量（2）→ 失败
    assert entry["total_tasks_handled"] == 1


def test_agent_status_statistics_full_for_admin(client, db_session):
    admin = _seed_user(db_session, UserRoleEnum.ADMIN)
    user_a = _seed_user(db_session, UserRoleEnum.LEARNER)
    user_b = _seed_user(db_session, UserRoleEnum.LEARNER)
    learner_a = _seed_learner(db_session, user_a)
    learner_b = _seed_learner(db_session, user_b)
    _seed_task(db_session, learner_a.id, "A的诊断")
    _seed_task(db_session, learner_b.id, "B的诊断")

    response = client.get("/api/v1/agent/status", headers=_auth_headers(admin))

    assert response.status_code == 200
    entry = _diagnosis_entry(response.json())
    assert entry["total_tasks_handled"] == 2


def test_single_agent_status_scoped_for_non_admin(client, db_session):
    user_a = _seed_user(db_session, UserRoleEnum.LEARNER)
    user_b = _seed_user(db_session, UserRoleEnum.LEARNER)
    learner_a = _seed_learner(db_session, user_a)
    learner_b = _seed_learner(db_session, user_b)
    _seed_task(db_session, learner_a.id, "A的诊断")
    _seed_task(db_session, learner_b.id, "B的诊断")

    response = client.get(
        "/api/v1/agent/status/diagnosis",
        headers=_auth_headers(user_a),
    )

    assert response.status_code == 200
    assert response.json()["data"]["total_tasks_handled"] == 1
```

- [ ] **Step 2: 运行测试确认失败**

```
python -m pytest tests/test_agent_router_security.py -v -k "status"
```

预期：`test_agent_status_statistics_scoped_for_non_admin`、`test_single_agent_status_scoped_for_non_admin` FAIL（统计为 2）；admin 用例 PASS。

- [ ] **Step 3: 修改两个状态端点**

Edit 1 —— `get_all_agent_status`（第 274-276 行）：

```python
        statuses = orchestrator.get_all_agents_status()
        statistics = _calculate_agent_statistics(db.query(AgentTask).all())
```

改为：

```python
        statuses = orchestrator.get_all_agents_status()
        if current_user.is_admin:
            tasks = db.query(AgentTask).all()
        else:
            accessible_ids = LearnerService.get_accessible_learner_ids(
                db, current_user.user_id
            )
            tasks = (
                db.query(AgentTask)
                .filter(AgentTask.learner_id.in_(accessible_ids))
                .all()
            )
        statistics = _calculate_agent_statistics(tasks)
```

Edit 2 —— `get_agent_status`（第 306-308 行）：

```python
        status.update(
            _calculate_agent_statistics(db.query(AgentTask).all()).get(agent_type, {})
        )
```

改为：

```python
        if current_user.is_admin:
            tasks = db.query(AgentTask).all()
        else:
            accessible_ids = LearnerService.get_accessible_learner_ids(
                db, current_user.user_id
            )
            tasks = (
                db.query(AgentTask)
                .filter(AgentTask.learner_id.in_(accessible_ids))
                .all()
            )
        status.update(_calculate_agent_statistics(tasks).get(agent_type, {}))
```

- [ ] **Step 4: 运行测试确认通过 + 全量回归**

```
python -m pytest tests/test_agent_router_security.py tests/test_agent_statistics.py -v
python -m pytest tests -q
```

预期：全部 PASS（test_agent_statistics.py 直接测 `_calculate_agent_statistics` 纯函数，不受影响；若其走路由且以普通用户依赖全量统计，改为 admin 身份）。

- [ ] **Step 5: 提交**

```
git add backend/app/domains/agent/router.py backend/tests/test_agent_router_security.py
git commit -m "fix(agent): Agent 状态聚合统计按可访问范围过滤"
```

---

### Task 7: 多轮"推荐→学习→再测"增益曲线脚本

**Files:**
- Create: `backend/scripts/generate_learning_gain_curve.py`
- Test: `backend/tests/test_learning_gain_curve.py`（新建，纯函数单测）

**Interfaces:**
- Consumes: `AdaptiveTutoringService.get_recommendations(learner_id)` / `generate_dynamic_questions(user_id, learner_id, topic, difficulty, question_count, replace_pending)` / `process_answer(user_id, learner_id, question_id, user_answer, time_spent_ms, hints_used, session_id, sequence_index)`；`scripts.generate_answer_samples.correctness_probability` / `pick_answer`（复用透明作答模拟）。
- Produces: `docs/evidence/learning-gain-curve.json`（Task 8 引用）；纯函数 `effective_ability(learner, topic)`、`phase_stats(correct, total)`、`build_session_ids(learner_id, round_no)`、`summarize_rounds(rounds)`（测试引用，签名以此为准）。
- 增益机制（诚实披露，写入证据 JSON）：作答概率 `p = clamp(0.5 + (ability − d×20)/100, 0.05, 0.95)`，`ability` **每题实时读取画像当前值**；画像由真实 `process_answer` 闭环更新（`_update_learner_profile`：答对 +2 / 答错 -1，写 `ability_assessments[*].estimatedScore`）。跨轮增益 = 系统真实画像增长机制的输出，不是注水。
- 口径：pre/post 测试 `session_id` 前缀 `diag_gain_`（被 `_practice_answer_query` 的 `diag_%` 排除规则剔除出练习指标）；学习阶段 `gain_`（计入练习指标）。

- [ ] **Step 1: 写失败测试**

创建 `backend/tests/test_learning_gain_curve.py`：

```python
"""generate_learning_gain_curve 纯函数单测。"""
from types import SimpleNamespace

from scripts.generate_learning_gain_curve import (
    build_session_ids,
    effective_ability,
    phase_stats,
    summarize_rounds,
)


def _learner(assessments=None, **columns):
    defaults = {
        "theoretical_foundation": 50.0,
        "programming_ability": 50.0,
        "algorithm_design": 50.0,
        "system_architecture": 50.0,
        "data_analysis": 50.0,
        "engineering_practice": 50.0,
    }
    defaults.update(columns)
    return SimpleNamespace(ability_assessments=assessments or {}, **defaults)


def test_effective_ability_prefers_estimated_score():
    learner = _learner({"data_analysis": {"estimatedScore": 66}}, data_analysis=60)
    assert effective_ability(learner, "数据分析") == 66


def test_effective_ability_falls_back_to_base_column():
    learner = _learner({}, data_analysis=44)
    assert effective_ability(learner, "数据分析") == 44


def test_effective_ability_defaults_to_dimension_mean():
    learner = _learner({}, data_analysis=70)
    assert effective_ability(learner, "陌生主题") == 50.0


def test_phase_stats():
    assert phase_stats(3, 6) == {"correct": 3, "total": 6, "accuracy": 50.0}
    assert phase_stats(0, 0) == {"correct": 0, "total": 0, "accuracy": None}


def test_build_session_ids_uses_diagnostic_prefix_for_tests_only():
    ids = build_session_ids(learner_id=5, round_no=1)
    assert ids["pre"] == "diag_gain_l5_r1_pre"
    assert ids["post"] == "diag_gain_l5_r1_post"
    assert ids["learn"] == "gain_l5_r1_learn"  # 学习阶段计入练习口径


def test_summarize_rounds():
    rounds = [
        {"pre": {"accuracy": 30.0}, "post": {"accuracy": 40.0},
         "within_round_gain_pp": 10.0},
        {"pre": {"accuracy": 45.0}, "post": {"accuracy": 55.0},
         "within_round_gain_pp": 10.0},
    ]
    summary = summarize_rounds(rounds)
    assert summary["pre_round1_accuracy"] == 30.0
    assert summary["post_roundN_accuracy"] == 55.0
    assert summary["cross_round_gain_pp"] == 25.0
    assert summary["mean_within_round_gain_pp"] == 10.0
```

- [ ] **Step 2: 运行测试确认失败**

```
python -m pytest tests/test_learning_gain_curve.py -v
```

预期：全部 FAIL（`ModuleNotFoundError: No module named 'scripts.generate_learning_gain_curve'`）。

- [ ] **Step 3: 实现脚本**

创建 `backend/scripts/generate_learning_gain_curve.py`：

```python
"""多轮"推荐→学习→再测"增益曲线证据生成（学习效果增益评分项）。

每轮三阶段（全部走真实服务流程，仅"作答者"为透明模拟）：
  pre-test:  固定难度 D 出题作答（session_id 前缀 diag_gain_，按现有口径排除出练习指标）
  learn:     get_recommendations 推荐主题 → 自适应会话练习（首题诊断推荐难度，
             之后逐题消费 next_question_difficulty），每题经 process_answer 真实
             判分 / 讲解 / 资源推荐 / 画像更新
  post-test: 与 pre-test 同难度 D 再测（session_id 前缀 diag_gain_）

增益机制（真实闭环，非注水，假设已在证据 JSON 中显式披露）：
  作答概率 p = clamp(0.5 + (ability - difficulty×20)/100, 0.05, 0.95)，
  ability 每题实时读取画像当前值；画像经真实 process_answer 闭环更新
  （答对 +2 / 答错 -1）→ 后轮 pre-test 正确率随画像增长而上升。

用法:
  cd backend
  python -m scripts.generate_learning_gain_curve --smoke      # 冒烟：1 学习者 1 轮 2+2+2 题
  python -m scripts.generate_learning_gain_curve              # 全量：learners 4,5 × 3 轮
"""
import argparse
import json
import random
import sys
import time
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from sqlalchemy import or_  # noqa: E402

from app.database import SessionLocal  # noqa: E402
import app.utils.llm  # noqa: E402,F401  # 先行加载以打破 utils<->ai_content_service 循环导入
from app.models import (  # noqa: E402
    AnswerRecord,
    IssuedTutoringQuestion,
    LearnerProfile,
)
from app.services.tutoring_service import AdaptiveTutoringService  # noqa: E402
from scripts.generate_answer_samples import (  # noqa: E402
    correctness_probability,
    pick_answer,
)

EVIDENCE_PATH = (
    Path(__file__).resolve().parents[2] / "docs" / "evidence" / "learning-gain-curve.json"
)

TOPIC_DIMENSION = {
    "理论": "theoretical_foundation",
    "编程": "programming_ability",
    "算法": "algorithm_design",
    "架构": "system_architecture",
    "数据": "data_analysis",
    "工程": "engineering_practice",
}


def _enum_value(value: Any) -> Any:
    return getattr(value, "value", value)


def topic_dimension(topic: str) -> Optional[str]:
    for keyword, dimension in TOPIC_DIMENSION.items():
        if keyword in (topic or ""):
            return dimension
    return None


def effective_ability(learner: LearnerProfile, topic: str) -> float:
    """当前有效能力分：优先画像 ability_assessments 的 estimatedScore
    （随真实练习闭环增长），回退基础列，再回退六维均值。"""
    dimension = topic_dimension(topic)
    if dimension:
        assessments = learner.ability_assessments or {}
        entry = assessments.get(dimension) or {}
        raw = entry.get("estimatedScore")
        if raw is not None:
            try:
                return float(raw)
            except (TypeError, ValueError):
                pass
        base = getattr(learner, dimension, None)
        if base is not None:
            return float(base)
    values = [float(getattr(learner, d) or 50.0) for d in TOPIC_DIMENSION.values()]
    return sum(values) / len(values)


def phase_stats(correct: int, total: int) -> Dict[str, Any]:
    return {
        "correct": correct,
        "total": total,
        "accuracy": round(correct / total * 100, 2) if total else None,
    }


def build_session_ids(learner_id: int, round_no: int) -> Dict[str, str]:
    """pre/post 用 diag_ 前缀排除出口径；learn 计入练习口径。"""
    return {
        "pre": f"diag_gain_l{learner_id}_r{round_no}_pre",
        "learn": f"gain_l{learner_id}_r{round_no}_learn",
        "post": f"diag_gain_l{learner_id}_r{round_no}_post",
    }


def summarize_rounds(rounds: List[Dict[str, Any]]) -> Dict[str, Any]:
    pre_first = rounds[0]["pre"]["accuracy"] if rounds else None
    post_last = rounds[-1]["post"]["accuracy"] if rounds else None
    cross_gain = (
        round(post_last - pre_first, 2)
        if pre_first is not None and post_last is not None
        else None
    )
    within_gains = [
        r["within_round_gain_pp"] for r in rounds if r["within_round_gain_pp"] is not None
    ]
    return {
        "pre_round1_accuracy": pre_first,
        "post_roundN_accuracy": post_last,
        "cross_round_gain_pp": cross_gain,
        "mean_within_round_gain_pp": (
            round(sum(within_gains) / len(within_gains), 2) if within_gains else None
        ),
    }


def answer_one(
    db,
    learner: LearnerProfile,
    topic: str,
    difficulty: Optional[int],
    session_id: str,
    sequence_index: int,
    rng: random.Random,
) -> Optional[Tuple[bool, Optional[int]]]:
    """生成并作答一题（真实服务流程）。返回 (是否判对, 下一题难度)；流程失败返回 None。"""
    questions = AdaptiveTutoringService.generate_dynamic_questions(
        user_id=learner.user_id,
        learner_id=learner.id,
        topic=topic,
        difficulty=difficulty,  # None -> 诊断推荐难度；否则严格按指定难度
        question_count=1,
        replace_pending=True,
    )
    if not questions or not str(questions[0].get("id", "")).isdigit():
        print(f"  [warn] 未生成题目: learner={learner.id} topic={topic}", flush=True)
        return None
    row = (
        db.query(IssuedTutoringQuestion)
        .filter(IssuedTutoringQuestion.id == int(questions[0]["id"]))
        .first()
    )
    if row is None:
        return None
    db.refresh(learner)
    ability = effective_ability(learner, row.topic)
    p = correctness_probability(ability, row.difficulty)
    intended_correct = rng.random() < p
    submit = pick_answer(row.answer_key or [], len(row.options or []), intended_correct, rng)
    result = AdaptiveTutoringService.process_answer(
        user_id=learner.user_id,
        learner_id=learner.id,
        question_id=str(row.id),
        user_answer=",".join(submit),
        time_spent_ms=rng.randint(15000, 90000),
        hints_used=0,
        session_id=session_id,
        sequence_index=sequence_index,
    )
    if not result.get("success"):
        print(f"  [error] 提交失败 q={row.id}: {result.get('error')}", flush=True)
        return None
    actual_correct = bool(result.get("is_correct"))
    print(
        f"  q={row.id} d={row.difficulty} p={p:.2f} -> {'对' if actual_correct else '错'}"
        f" 下一题d={result.get('next_question_difficulty')}",
        flush=True,
    )
    return actual_correct, result.get("next_question_difficulty")


def run_fixed_phase(
    db,
    learner: LearnerProfile,
    topic: str,
    difficulty: int,
    count: int,
    session_id: str,
    rng: random.Random,
) -> Dict[str, Any]:
    """固定难度测试阶段（pre/post-test）：忽略难度自适应信号，保证轮间可比。"""
    correct = total = 0
    for i in range(count):
        outcome = answer_one(db, learner, topic, difficulty, session_id, i + 1, rng)
        if outcome is None:
            continue
        is_correct, _ = outcome
        total += 1
        correct += 1 if is_correct else 0
    return phase_stats(correct, total)


def run_learn_phase(
    db,
    learner: LearnerProfile,
    topic: str,
    count: int,
    session_id: str,
    rng: random.Random,
) -> Dict[str, Any]:
    """推荐→学习阶段：首题诊断推荐难度，其后逐题消费 next_question_difficulty。"""
    correct = total = 0
    next_difficulty: Optional[int] = None
    for i in range(count):
        outcome = answer_one(db, learner, topic, next_difficulty, session_id, i + 1, rng)
        if outcome is None:
            break
        is_correct, next_difficulty = outcome
        total += 1
        correct += 1 if is_correct else 0
    records = db.query(AnswerRecord).filter(AnswerRecord.session_id == session_id).all()
    with_resource = sum(1 for r in records if r.next_resource_id is not None)
    stats = phase_stats(correct, total)
    stats["with_resource_recommendation"] = with_resource
    return stats


def run_gain_round(
    db,
    learner: LearnerProfile,
    topic: str,
    round_no: int,
    cfg: Dict[str, Any],
    rng: random.Random,
) -> Dict[str, Any]:
    ids = build_session_ids(learner.id, round_no)

    ability_start = effective_ability(learner, topic)
    recommendation = AdaptiveTutoringService.get_recommendations(learner.id)
    print(f"  -- Round {round_no} 能力={ability_start:.1f} 推荐={recommendation.get('primary_topic')}", flush=True)

    pre = run_fixed_phase(db, learner, topic, cfg["difficulty"], cfg["test_questions"], ids["pre"], rng)
    learn = run_learn_phase(db, learner, topic, cfg["learn_questions"], ids["learn"], rng)
    db.refresh(learner)
    ability_after_learn = effective_ability(learner, topic)
    post = run_fixed_phase(db, learner, topic, cfg["difficulty"], cfg["test_questions"], ids["post"], rng)
    db.refresh(learner)

    within_gain = (
        round(post["accuracy"] - pre["accuracy"], 2)
        if pre["accuracy"] is not None and post["accuracy"] is not None
        else None
    )
    return {
        "round": round_no,
        "recommendation": {
            "primary_topic": recommendation.get("primary_topic"),
            "source": recommendation.get("source"),
            "recommended_difficulty": recommendation.get("recommended_difficulty"),
        },
        "ability_start": round(ability_start, 1),
        "ability_after_learn": round(ability_after_learn, 1),
        "pre": pre,
        "learn": learn,
        "post": post,
        "within_round_gain_pp": within_gain,
    }


def analyze_existing_sessions(db, min_questions: int = 4) -> Dict[str, Any]:
    """既有真实练习会话的组内增益：每会话按 sequence_index 前后半比较正确率。"""
    sessions: Dict[str, List[AnswerRecord]] = {}
    query = db.query(AnswerRecord).filter(
        or_(
            AnswerRecord.session_id.is_(None),
            ~AnswerRecord.session_id.like("diag_%"),
        )
    )
    for record in query.all():
        sessions.setdefault(record.session_id, []).append(record)

    early_correct = early_total = late_correct = late_total = 0
    session_count = 0
    for rows in sessions.values():
        rows.sort(key=lambda r: (r.sequence_index or 0, r.id))
        if len(rows) < min_questions:
            continue
        session_count += 1
        half = len(rows) // 2
        for row in rows[:half]:
            early_total += 1
            early_correct += 1 if _enum_value(row.result) == "correct" else 0
        for row in rows[half:]:
            late_total += 1
            late_correct += 1 if _enum_value(row.result) == "correct" else 0

    return {
        "description": "既有真实练习会话按题序前半 vs 后半的正确率（自适应闭环的组内增益证据）",
        "min_questions_per_session": min_questions,
        "session_count": session_count,
        "early_half": phase_stats(early_correct, early_total),
        "late_half": phase_stats(late_correct, late_total),
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--learner-ids", default="4,5", help="逗号分隔的学习者ID（默认 4,5）")
    parser.add_argument("--rounds", type=int, default=3, help="增益轮数")
    parser.add_argument("--test-questions", type=int, default=6, help="pre/post 每阶段题数")
    parser.add_argument("--learn-questions", type=int, default=8, help="学习阶段题数")
    parser.add_argument("--difficulty", type=int, default=3, help="pre/post 固定测试难度（1-5）")
    parser.add_argument("--seed", type=int, default=20260901, help="随机种子（可复现）")
    parser.add_argument("--smoke", action="store_true", help="冒烟模式：1 学习者 1 轮 2+2+2 题")
    parser.add_argument("--output", default=str(EVIDENCE_PATH), help="证据 JSON 输出路径")
    args = parser.parse_args()

    if args.smoke:
        args.learner_ids = args.learner_ids.split(",")[0]
        args.rounds, args.test_questions, args.learn_questions = 1, 2, 2

    cfg = {
        "difficulty": args.difficulty,
        "test_questions": args.test_questions,
        "learn_questions": args.learn_questions,
    }
    rng = random.Random(args.seed)
    learner_ids = [int(x) for x in args.learner_ids.split(",") if x.strip()]

    db = SessionLocal()
    try:
        before_total = db.query(AnswerRecord).count()
        print(f"运行前答题记录={before_total}")
        print(
            f"参数: learners={learner_ids} rounds={args.rounds} "
            f"test={args.test_questions} learn={args.learn_questions} "
            f"difficulty={args.difficulty} seed={args.seed}"
        )

        learners_evidence = []
        start = time.time()
        for learner_id in learner_ids:
            learner = db.query(LearnerProfile).filter(LearnerProfile.id == learner_id).first()
            if not learner:
                print(f"[warn] learner={learner_id} 不存在，跳过")
                continue
            label = learner.display_name or learner.real_name or f"learner_{learner.id}"
            # 主题取首轮推荐并固定，保证轮间可比；每轮推荐信号仍记录在证据中
            topic = AdaptiveTutoringService.get_recommendations(learner.id).get("primary_topic")
            if not topic:
                print(f"[warn] learner={learner_id} 无可用推荐主题，跳过")
                continue
            print(f"\n=== learner={learner.id} ({label}) 固定主题={topic} ===", flush=True)

            rounds = []
            for round_no in range(1, args.rounds + 1):
                rounds.append(run_gain_round(db, learner, topic, round_no, cfg, rng))
                db.refresh(learner)

            learners_evidence.append({
                "learner_id": learner.id,
                "label": label,
                "topic": topic,
                "rounds": rounds,
                "summary": summarize_rounds(rounds),
            })

        existing = analyze_existing_sessions(db)
        evidence = {
            "evidence_type": "learning-gain-curve",
            "generated_at": datetime.now().isoformat(timespec="seconds"),
            "config": {
                "rounds": args.rounds,
                "test_questions": args.test_questions,
                "learn_questions": args.learn_questions,
                "fixed_test_difficulty": args.difficulty,
                "seed": args.seed,
                "learner_ids": learner_ids,
                "method": (
                    "每轮 pre-test(固定难度) → 推荐 → 自适应学习(真实 process_answer 闭环) → "
                    "post-test(同固定难度)；作答概率 p=clamp(0.5+(ability-d×20)/100, 0.05, 0.95)，"
                    "ability 每题实时读取画像（画像由真实判分闭环更新：答对+2/答错-1）"
                ),
                "metric_scope_note": (
                    "pre/post 测试 session_id 以 diag_ 前缀按现有口径排除出 "
                    "answer_accuracy/resource_match_effectiveness；学习阶段 session 计入练习口径"
                ),
            },
            "learners": learners_evidence,
            "existing_adaptive_sessions": existing,
        }

        output = Path(args.output)
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(
            json.dumps(evidence, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
        )
        after_total = db.query(AnswerRecord).count()
        print(f"\n===== 汇总 =====")
        for item in learners_evidence:
            print(
                f"learner={item['learner_id']}({item['label']}) "
                f"R1前测={item['summary']['pre_round1_accuracy']}% -> "
                f"R{args.rounds}后测={item['summary']['post_roundN_accuracy']}% "
                f"跨轮增益={item['summary']['cross_round_gain_pp']}pp"
            )
        print(f"答题记录: {before_total} -> {after_total}")
        print(f"证据已写入: {output}")
        print(f"总耗时 {time.time() - start:.0f}s")
        return 0 if learners_evidence else 1
    finally:
        db.close()


if __name__ == "__main__":
    raise SystemExit(main())
```

- [ ] **Step 4: 运行测试确认通过**

```
python -m pytest tests/test_learning_gain_curve.py -v
```
预期：7 个用例全部 PASS。

- [ ] **Step 5: 冒烟验证（真实 DB + LLM）**

```
python -m scripts.generate_learning_gain_curve --smoke
```
预期：退出码 0；控制台输出 1 学习者 1 轮的 pre/learn/post 题目作答日志；`docs/evidence/learning-gain-curve.json` 生成（冒烟数据，Task 8 会全量重跑覆盖）。若 process_answer 失败（LLM 不可用等），排查 DeepSeek 配置后重试——本脚本与既有 `generate_answer_samples.py` 走完全相同的调用链。

- [ ] **Step 6: 提交**

```
git add backend/scripts/generate_learning_gain_curve.py backend/tests/test_learning_gain_curve.py
git commit -m "feat(evidence): 多轮推荐→学习→再测增益曲线脚本与纯函数单测"
```

---

### Task 8: 全量证据生成与验收文档更新

**Files:**
- Modify: `docs/evidence/acceptance-remediation-summary.md`（追加 §5）
- Generate: `docs/evidence/learning-gain-curve.json`（全量重跑覆盖）
- Regenerate: `docs/evidence/metric-evidence-latest.json`

**Interfaces:**
- Consumes: Task 7 脚本（全量运行）；`scripts.generate_metric_evidence.py --output ../docs/evidence/metric-evidence-latest.json`。

- [ ] **Step 1: 全量运行增益曲线脚本**

```
python -m scripts.generate_learning_gain_curve
```

预期：learners 4,5 × 3 轮全部完成（约 2×3×(6+8+6)=120 次真实 process_answer，含 LLM 调用，耗时以分钟计）。检查 `docs/evidence/learning-gain-curve.json`：
- 每学习者 `summary.cross_round_gain_pp` 为正（弱基础学习者亦应为正，幅度受能力边界约束）；
- `rounds[*].learn.with_resource_recommendation` 多数 > 0（资源推荐链路在环）；
- `existing_adaptive_sessions.late_half.accuracy` ≥ `early_half.accuracy`（既有真实数据的组内增益）。

若 `cross_round_gain_pp` 不为正：核对 `ability_start` 是否逐轮上行（画像闭环生效的标志）。若画像未增长，检查 `_update_learner_profile` 是否被 topic 维度命中（`topic_dimension` 无映射时画像不更新）——此时在证据 JSON 的 `config.method` 中如实披露该约束，并在 §5 中按实测值归因，不得改写脚本"造"增益。

- [ ] **Step 2: 刷新全局指标证据**

```
python -m scripts.generate_metric_evidence --output ../docs/evidence/metric-evidence-latest.json
```

预期：`metric-evidence-latest.json` 更新。学习阶段（`gain_*` 会话）计入练习口径，answer_accuracy / resource_match_effectiveness 的分子分母相应变化（预期小幅上行：学习阶段为适配难度下的作答）；pre/post（`diag_gain_*`）不进入两指标。记录新旧数值用于 §5。

- [ ] **Step 3: 更新验收归因文档**

在 `docs/evidence/acceptance-remediation-summary.md` 末尾追加（数值从 `learning-gain-curve.json` 与刷新后的 `metric-evidence-latest.json` 逐字段抄录，禁止臆造）：

```markdown
## 5. 多轮"推荐→学习→再测"增益曲线证据（2026-08-25 补充）

> 数据来源：`docs/evidence/learning-gain-curve.json`（脚本 `backend/scripts/generate_learning_gain_curve.py`，固定随机种子，可复现）

### 5.1 方法与假设披露

- 每轮 pre-test（固定难度 3）→ 真实推荐 → 自适应学习（真实 `process_answer` 判分/讲解/资源推荐/画像更新闭环）→ post-test（同固定难度 3）。
- 作答模拟与既有样本同规则：`p = clamp(0.5 + (ability − d×20)/100, 0.05, 0.95)`，且 **ability 每题实时读取画像当前值**——跨轮增益来自系统真实的画像更新机制（答对 +2 / 答错 -1），非注水。
- pre/post 测试会话以 `diag_` 前缀排除出 answer_accuracy / resource_match_effectiveness 口径（能力摸底不反映练习正确率）；学习阶段会话计入练习口径。
- 主题取首轮推荐并固定，保证轮间可比。

### 5.2 增益曲线（按学习者）

| 学习者 | 主题 | R1 前测 | R1 后测 | R3 前测 | R3 后测 | 跨轮增益（R1前测→R3后测） | 画像能力变化 |
|---|---|---|---|---|---|---|---|
| （从 JSON learners[*].rounds / summary 抄录） | | | | | | pp | 起→止 |

### 5.3 既有真实会话的组内增益（无模拟）

- early_half 正确率 X% → late_half 正确率 Y%（n 个会话，session_count 抄录），自适应难度降级闭环的既有数据佐证。

### 5.4 结论

- 增益曲线证明"推荐→学习→再测"闭环产生可测量的正确率上行（跨轮 +Z pp），且增益来自真实画像更新机制。
- 85% 绝对阈值仍受弱基础学习者能力边界约束（§3.1 归因不变）：增益曲线给出的是**机制增益证据**，而非对绝对阈值的注水达标。
- 全局指标刷新后：answer_accuracy A% → B%，resource_match_effectiveness C% → D%（学习阶段样本计入练习口径）。
```

- [ ] **Step 4: 全量回归 + 提交**

```
python -m pytest tests -q
```
预期：全绿。

```
git add docs/evidence/learning-gain-curve.json docs/evidence/metric-evidence-latest.json docs/evidence/acceptance-remediation-summary.md
git commit -m "docs(evidence): 生成多轮学习增益曲线证据并更新验收归因文档"
```

---

## 自查记录（Self-Review）

1. **覆盖检查**：base.py 单例竞态（Task 1）✓；llm.py httpx 单例竞态（Task 2，审查中同类的第二处竞态）✓；Agent 路由归属校验/IDOR——任务列表泄露（Task 4）、SSE 无归属（Task 5）、聚合统计（Task 6）、ENTERPRISE/TEACHER 宽松边界（Task 3）✓；学习效果增益曲线证据（Task 7/8）✓。
2. **占位符扫描**：Task 8 §5 表格数值标注"从 JSON 抄录"——证据文档记录的是运行后才能产生的测量值，属记录性内容而非实现占位；其余任务步骤均含完整代码与命令。
3. **类型一致性**：`get_accessible_learner_ids(db, user_id: int) -> List[int]` 在 Task 3 定义、Task 4/6 以相同签名调用；`build_session_ids`/`phase_stats`/`summarize_rounds`/`effective_ability` 在 Task 7 脚本与测试中签名一致；`_check_task_permission(db, current_user, task)` 复用 router 既有定义（第 60-65 行）。
4. **风险与既有测试**：Task 3 改变 ENTERPRISE 语义、Task 4/6 改变非管理员的默认可见面——各任务均含全量回归步骤与"改为 admin 身份/补建可访问学习者"的修正指引；Task 1 移除不可观测的 ERROR/VALIDATING 瞬态，`get_status()` 返回结构不变。
