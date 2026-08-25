"""BaseAgent 并发竞态回归测试（代码审查残留问题：单例 Agent 实例被并发任务复用）。"""
import threading

from app.agents.base import AgentStatus, BaseAgent


class DummyAgent(BaseAgent):
    """execute 可控的测试 Agent：从 input_data 取启停事件（测试预先创建，无注册竞态）。"""

    def execute(self, input_data, context=None):
        started = input_data["started"]
        release = input_data["release"]
        started.set()
        assert release.wait(timeout=5), "测试执行超时"
        if input_data.get("fail"):
            raise RuntimeError("boom")
        return {"success": True}


def _start_task(agent, task_id, fail=False):
    """启动一个可控任务，返回 (线程, started事件, release事件)。"""
    started = threading.Event()
    release = threading.Event()
    payload = {"started": started, "release": release, "fail": fail}
    thread = threading.Thread(target=agent.run, args=(task_id, payload))
    thread.start()
    return thread, started, release


def test_concurrent_runs_do_not_clobber_each_others_state():
    """任务A先结束不得把任务B的 RUNNING 状态清成 IDLE（原 finally 无条件清除的竞态）。"""
    agent = DummyAgent("dummy", "Dummy")

    t_a, started_a, release_a = _start_task(agent, 1)
    assert started_a.wait(timeout=5)

    t_b, started_b, release_b = _start_task(agent, 2)
    assert started_b.wait(timeout=5)

    release_a.set()  # A 先结束，B 仍在运行
    t_a.join(timeout=5)

    status = agent.get_status()
    assert status["status"] == AgentStatus.RUNNING  # 旧代码：A 的 finally 置 IDLE → 失败
    assert status["current_task_id"] == 2

    release_b.set()
    t_b.join(timeout=5)

    status = agent.get_status()
    assert status["status"] == AgentStatus.IDLE
    assert status["current_task_id"] is None


def test_error_keeps_last_error_and_returns_to_idle_when_all_done():
    agent = DummyAgent("dummy", "Dummy")

    t_a, started_a, release_a = _start_task(agent, 1, fail=True)
    t_b, started_b, release_b = _start_task(agent, 2)
    assert started_a.wait(timeout=5)
    assert started_b.wait(timeout=5)

    release_a.set()
    t_a.join(timeout=5)
    assert agent.get_status()["status"] == AgentStatus.RUNNING  # B 仍在运行
    assert agent.get_status()["last_error"] == "boom"

    release_b.set()
    t_b.join(timeout=5)
    assert agent.get_status()["status"] == AgentStatus.IDLE


def test_validate_does_not_break_running_state():
    """validate 不得改写共享状态（旧代码将并发任务的 RUNNING 覆盖为 IDLE）。"""
    agent = DummyAgent("dummy", "Dummy")
    t, started, release = _start_task(agent, 1)
    assert started.wait(timeout=5)

    agent.validate({"ok": True})
    agent.validate(None)  # 校验失败路径同样不得破坏并发状态
    assert agent.get_status()["status"] == AgentStatus.RUNNING

    release.set()
    t.join(timeout=5)
    assert agent.get_status()["status"] == AgentStatus.IDLE


def test_add_log_trims_to_last_100_and_reset_is_atomic():
    agent = DummyAgent("dummy", "Dummy")
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
    agent = DummyAgent("dummy", "Dummy")

    def append_many():
        for _ in range(300):
            agent._add_log({"x": 1})

    threads = [threading.Thread(target=append_many) for _ in range(4)]
    for t in threads:
        t.start()
    for t in threads:
        t.join(timeout=10)

    assert len(agent.execution_log) == 100
