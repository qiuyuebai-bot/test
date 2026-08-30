# 幻觉率治理实现计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 在不删除或弱化真实问题的前提下，建立统一、可审计的证据感知幻觉率统计，并为严格 `<5.00%` 的正式验收提供可靠门禁。

**Architecture:** 以 `MetricsUtil` 作为唯一记录分类和公式实现，`MetricService` 负责开发态样本门槛与滚动窗口，证据报告负责正式验收的 60 条样本门槛。`HallucinationUtil`/`JudgeAgent` 产出标准审查元数据，`TaskRepository` 以追加式、幂等的最终审查记录保存结果；API、健康检查和报告全部复用同一服务。

**Tech Stack:** Python 3、FastAPI、SQLAlchemy、Alembic（本计划首期不新增迁移）、pytest、现有知识库检索和 JSON 证据报告脚本。

## Global Constraints

- 目标值固定为幻觉率严格 `<5.00%`，不是 `<=5%`。
- `H = reviewed_hallucination`，`E = reviewed_clean + reviewed_hallucination`，幻觉率为 `H / E * 100`。
- `evidence_gap`、`pending_review`、`invalid_record` 不进入 `H` 或 `E`，且治理后的状态分类互斥。
- 正式验收最少 60 条合格审查；当前 H=3 时必须达到 E=61 才能满足严格目标。
- 关键词、绝对化词和不确定性词只能是诊断信号；关键词单独命中不得确认幻觉。
- 不删除历史 `DebateRecord`、不修改原始内容、不伪造样本或专家标注，不通过换口径降低指标。
- 报告、日志和测试夹具不得包含真实密钥、token 或密码；现有用户改动必须保留。

## 文件结构与职责

- `backend/app/utils/metrics.py`：集中记录状态分类、全量/滚动窗口统计和政策常量。
- `backend/app/services/metric_registry.py`：声明运行态样本门槛、公式和政策版本。
- `backend/app/services/metric_service.py`：计算全量与 30 天滚动幻觉率，并将状态元数据传给所有消费者。
- `backend/app/utils/hallucination.py`：完善 claim 证据和数字/单位/版本冲突校验。
- `backend/app/agents/judge_agent.py`：输出标准证据状态和审查结果元数据。
- `backend/app/agents/task_repository.py`、`backend/app/agents/orchestrator.py`：保存最终审查版本，避免重复计入分母。
- `backend/app/domains/agent/schemas.py`、`backend/app/schemas/core.py`：扩展指标响应契约。
- `backend/app/domains/agent/router.py`、`backend/app/health.py`、`backend/app/services/report_service.py`：统一 API、健康检查和系统报告。
- `backend/scripts/generate_metric_evidence.py`：生成正式幻觉率 claim、补样量和政策版本。
- `backend/scripts/export_hallucination_review_queue.py`：只读导出需人工复核的记录和补样建议。
- `backend/tests/test_hallucination_metrics.py`、`backend/tests/test_metric_service.py`、`backend/tests/test_hallucination_evidence.py`、`backend/tests/test_hallucination_persistence.py`、`backend/tests/test_metric_evidence.py`、`backend/tests/test_hallucination_review_queue.py`：回归、边界和接口验收测试。

---

### Task 1: 建立统一状态分类与统计策略

**Files:**
- Modify: `backend/app/utils/metrics.py:14-128`
- Modify: `backend/app/services/metric_registry.py:74-83`
- Test: `backend/tests/test_hallucination_metrics.py`
- Test: `backend/tests/test_metric_service.py:238-260`

**Interfaces:**
- Produces `MetricsUtil.classify_debate_record(record: Any) -> str`，只返回 `reviewed_clean`、`reviewed_hallucination`、`evidence_gap`、`pending_review` 或 `invalid_record`。
- Produces `MetricsUtil.calculate_hallucination_metrics(db, start_date=None, end_date=None, learner_id=None, minimum_sample_size=None, window_days=None) -> Dict[str, Any]`。
- Returned metrics include `state_counts`、`invalid_records`、`high_risk_checks`、`high_risk_reviewed`、`high_risk_review_coverage`、`policy_version`、`formal_minimum_sample_size`、`target_percent` and `window`; existing keys remain backward compatible.

- [ ] **Step 1: Write failing classification and boundary tests**

```python
def test_record_states_are_mutually_exclusive(db_session, sample_agent_task):
    gap = _add_record(db_session, sample_agent_task.id, is_hallucination=True,
                      conflict_points=[{"type": "knowledge_gap"}])
    pending = _add_record(db_session, sample_agent_task.id, is_hallucination=False)
    clean = _add_record(db_session, sample_agent_task.id, is_hallucination=False,
                        resolution_status="resolved", judge_decision="approved")
    hallucination = _add_record(db_session, sample_agent_task.id, is_hallucination=True,
                                resolution_status="resolved", judge_decision="rejected",
                                conflict_points=[{"type": "hallucination_evidence"}])

    assert MetricsUtil.classify_debate_record(gap) == "evidence_gap"
    assert MetricsUtil.classify_debate_record(pending) == "pending_review"
    assert MetricsUtil.classify_debate_record(clean) == "reviewed_clean"
    assert MetricsUtil.classify_debate_record(hallucination) == "reviewed_hallucination"


def test_strict_target_requires_61_records_when_h_is_three(db_session, sample_agent_task):
    for index in range(61):
        _add_record(db_session, sample_agent_task.id,
                    is_hallucination=index < 3,
                    resolution_status="resolved",
                    judge_decision="rejected" if index < 3 else "approved",
                    conflict_points=([{"type": "hallucination_evidence"}]
                                     if index < 3 else []))

    metrics = MetricsUtil.calculate_hallucination_metrics(
        db_session, minimum_sample_size=60
    )
    assert metrics["hallucination_rate"] == 4.92
    assert metrics["evaluated_checks"] == 61
    assert metrics["state_counts"]["reviewed_hallucination"] == 3
```

- [ ] **Step 2: Run the focused tests and verify failure**

Run: `pytest -q backend/tests/test_hallucination_metrics.py backend/tests/test_metric_service.py -k "states_are_mutually_exclusive or strict_target_requires_61 or hallucination_rate"`

Expected: FAIL because the centralized state classifier, strict sample argument, and state counts do not exist yet.

- [ ] **Step 3: Implement policy constants and classifier**

Add these constants in `MetricsUtil` and keep the runtime/formal distinction explicit:

```python
HALLUCINATION_POLICY_VERSION = "hallucination-rate-v1"
MIN_HALLUCINATION_SAMPLE = 10
FORMAL_MIN_HALLUCINATION_SAMPLE = 60
HALLUCINATION_TARGET_PERCENT = 5.0
RECENT_WINDOW_DAYS = 30
```

Implement `classify_debate_record` in this order: invalid required content/JSON, standardized `audit_metadata.evidence_status`/`review_outcome`, legacy evidence-gap marker, completed-status check, then the `is_hallucination` boolean. Count `pending_review` only after evidence gaps have been removed, so the new state counts sum to `total_checks`. Add `_is_high_risk_record(record) -> bool` for `conflict_severity in {high, critical}` or an explicit safety/regulatory risk flag, and return reviewed/total high-risk counts plus coverage. Make `minimum_sample_size` default to 10; accept an explicit value for the formal report. Reject simultaneous `start_date` and `window_days` with `ValueError`, and derive the window start from `utcnow_naive() - timedelta(days=window_days)` otherwise.

- [ ] **Step 4: Update the registry and run the focused tests**

Set the registry's `hallucination_rate.minimum_sample_size` to `10`; retain the formula text and add the policy version through the returned metadata. Run:

`pytest -q backend/tests/test_hallucination_metrics.py backend/tests/test_metric_service.py -k "states_are_mutually_exclusive or strict_target_requires_61 or hallucination_rate"`

Expected: PASS, with old tests updated from the five-record runtime gate to the ten-record runtime gate.

- [ ] **Step 5: Commit the policy/classifier change**

```text
git add backend/app/utils/metrics.py backend/app/services/metric_registry.py backend/tests/test_hallucination_metrics.py backend/tests/test_metric_service.py
git commit -m "feat: centralize hallucination metric states"
```

### Task 2: Make evidence and high-risk rule results auditable

**Files:**
- Modify: `backend/app/utils/hallucination.py:39-305,435-575`
- Modify: `backend/app/agents/judge_agent.py:35-165`
- Test: `backend/tests/test_hallucination_evidence.py`
- Test: `backend/tests/test_judge_hallucination_rules.py`

**Interfaces:**
- Preserve `HallucinationUtil.detect_hallucination(...) -> Tuple[bool, Dict[str, Any]]`.
- Preserve `JudgeAgent.execute(...) -> Dict[str, Any]`, adding `evidence_status`, `review_outcome`, `review_source`, and `risk_flags` without removing legacy fields.
- Keep `hallucination_keyword` readable for old records but never emit it as a decisive new issue.

- [ ] **Step 1: Add failing rule tests**

```python
def test_unrelated_years_do_not_create_a_conflict():
    assert HallucinationUtil._claim_conflict(
        "Python 3.12 was released in 2023.",
        {"content": "The project was founded in 2018.", "similarity": 0.91},
    ) is None


def test_weak_or_missing_evidence_is_pending_not_hallucination():
    result = JudgeAgent().execute({
        "generated_content": "The Aurora protocol supports seven recovery modes.",
        "reference_knowledge": [{
            "title": "Unrelated Notes", "content": "A database history.",
            "similarity": 0.21,
        }],
    })
    assert result["hallucination_detected"] is False
    assert result["review_outcome"] == "pending"
    assert result["evidence_status"] == "gap"


def test_keyword_only_language_is_not_a_decisive_issue():
    result = JudgeAgent().execute({
        "generated_content": "这个结论可能需要进一步核实。",
        "reference_knowledge": [{
            "title": "Notes", "content": "结论需要核实。", "similarity": 0.86,
        }],
    })
    assert result["hallucination_detected"] is False
    assert all(item["type"] != "hallucination_keyword" for item in result["issues"])
```

- [ ] **Step 2: Run the rule tests and verify failure**

Run: `pytest -q backend/tests/test_hallucination_evidence.py backend/tests/test_judge_hallucination_rules.py -k "unrelated_years or weak_or_missing or keyword_only"`

Expected: FAIL because year comparison is currently not entity-aware and the judge result lacks the standardized outcome fields.

- [ ] **Step 3: Implement entity-aware numeric, version, and unit checks**

Add a private `_normalize_numeric_facts(text: str) -> list[dict]` helper that returns normalized value, unit, and nearby entity tokens. Update `_claim_conflict` to compare only matching entity/attribute facts; compare versions and dates only when the same fact is present in both texts. Store deterministic `risk_flags` for numeric, unit, version, safety, and topic mismatch. A keyword score may lower confidence but cannot set `hallucination_detected=True`.

- [ ] **Step 4: Add standardized judge metadata and run the tests**

In `HallucinationUtil._detect_against_knowledge`, set `review_outcome` to `hallucination` for contradictions, `pending` for any knowledge gap or weak-only result, and `clean` only when every material claim has strong support and no contradiction. In `JudgeAgent.execute`, copy this to the result and set `evidence_status` to `sufficient` or `gap`, while preserving citations and knowledge-gap details. Run:

`pytest -q backend/tests/test_hallucination_evidence.py backend/tests/test_judge_hallucination_rules.py`

Expected: PASS, including all existing evidence-grounding regressions.

- [ ] **Step 5: Commit the evidence rule change**

```text
git add backend/app/utils/hallucination.py backend/app/agents/judge_agent.py backend/tests/test_hallucination_evidence.py backend/tests/test_judge_hallucination_rules.py
git commit -m "fix: make hallucination decisions evidence based"
```

### Task 3: Persist final review metadata without duplicate denominator rows

**Files:**
- Modify: `backend/app/agents/task_repository.py:218-293`
- Modify: `backend/app/agents/orchestrator.py:170-215,420-525`
- Test: `backend/tests/test_hallucination_metrics.py`
- Create: `backend/tests/test_hallucination_persistence.py`

**Interfaces:**
- Add `TaskRepository._audit_key(task_id: int, round_num: int, original_content: str) -> str` using SHA-256.
- `save_debate_record(..., final_review: bool = False)` stores an `audit_metadata` object containing `audit_key`, `evidence_status`, `review_outcome`, `review_source`, `policy_version`, and `is_final_review` in `agent_judge_view`.
- A repeated final save with the same audit key updates the existing final record; non-final rounds remain unresolved and never enter `E`.

- [ ] **Step 1: Add failing persistence tests**

```python
import json

from app.agents.task_repository import TaskRepository
from app.models import DebateRecord


def test_final_review_persists_metadata_and_is_idempotent(
    db_session, sample_agent_task, monkeypatch
):
    from contextlib import contextmanager
    import app.agents.task_repository as repository_module

    @contextmanager
    def same_session():
        yield db_session

    monkeypatch.setattr(repository_module, "get_db_context", same_session)
    payload = {
        "original_content": "supported content",
        "reference_content": "source",
        "final_decision": "approved",
        "evidence_status": "sufficient",
        "review_outcome": "clean",
        "review_source": "knowledge_grounded",
        "conflict_points": [],
        "corrections": [],
    }
    repo = TaskRepository()
    repo.save_debate_record(sample_agent_task.id, 1, payload, final_review=True)
    repo.save_debate_record(sample_agent_task.id, 1, payload, final_review=True)

    rows = db_session.query(DebateRecord).filter(
        DebateRecord.task_id == sample_agent_task.id
    ).all()
    assert len(rows) == 1
    metadata = json.loads(rows[0].agent_judge_view)["audit_metadata"]
    assert metadata["is_final_review"] is True
    assert metadata["policy_version"] == "hallucination-rate-v1"
```

- [ ] **Step 2: Run the persistence test and verify failure**

Run: `pytest -q backend/tests/test_hallucination_persistence.py -k "persists_metadata"`

Expected: FAIL because the repository currently inserts a new row and does not persist an audit key or standard metadata.

- [ ] **Step 3: Implement audit key and final-row upsert behavior**

Compute the key from task, round, and original content before writing. Query existing rows for the task and round, parse `agent_judge_view`, and update the row only when its stored key matches and either row is final. Keep the original content unchanged; update only the final decision, evidence metadata, correction payload, and timestamps. A correction with changed content or a new policy version gets a new key and an appended row, preserving the old row. Set `resolution_status` to `resolved` only for final approved/rejected/confirmed decisions; keep intermediate rows `unresolved`.

- [ ] **Step 4: Pass judge metadata through the orchestrator and run tests**

Pass `evidence_status`, `review_outcome`, and `review_source` from `final_audit` into the fallback final-review payload in `orchestrator.py`, and include the same fields in every `debate_result`. Run:

`pytest -q backend/tests/test_hallucination_metrics.py backend/tests/test_hallucination_persistence.py`

Expected: PASS, with the existing debate flow still saving corrections and the metric classifier seeing only the final review.

- [ ] **Step 5: Commit the persistence change**

```text
git add backend/app/agents/task_repository.py backend/app/agents/orchestrator.py backend/tests/test_hallucination_metrics.py backend/tests/test_hallucination_persistence.py
git commit -m "feat: persist idempotent hallucination reviews"
```

### Task 4: Expose runtime and formal policy consistently

**Files:**
- Modify: `backend/app/services/metric_service.py:344-380`
- Modify: `backend/app/domains/agent/schemas.py:170-184`
- Modify: `backend/app/schemas/core.py:184-205`
- Modify: `backend/app/domains/agent/router.py:1158-1185`
- Modify: `backend/app/health.py:285-335`
- Modify: `backend/app/services/report_service.py:465-530`
- Test: `backend/tests/test_metric_service.py`
- Test: `backend/tests/test_hallucination_metrics.py`

**Interfaces:**
- `MetricCalculator.hallucination_rate` returns all-time facts plus `metadata["rolling_30d"]` with the same numerator/denominator/state fields.
- API responses add optional `state_counts`, `invalid_records`, `high_risk_checks`, `high_risk_reviewed`, `high_risk_review_coverage`, `policy_version`, `formal_minimum_sample_size`, `target_percent`, `operator`, and `rolling_30d` fields; the runtime `minimum_sample_size` default changes from 5 to 10.
- Health and report services must not run a second raw `DebateRecord.is_hallucination / total` formula.

- [ ] **Step 1: Add failing service and API contract tests**

```python
def test_metric_contains_policy_and_rolling_window_metadata(db_session):
    result = _by_id(MetricService.calculate_metrics(
        db_session, scope="global", metric_ids=["hallucination_rate"]
    ))["hallucination_rate"]
    assert result["metadata"]["policy_version"] == "hallucination-rate-v1"
    assert result["metadata"]["formal_minimum_sample_size"] == 60
    assert "rolling_30d" in result["metadata"]


def test_hallucination_endpoint_returns_mutually_exclusive_counts(
    client, auth_headers
):
    response = client.get(
        "/api/v1/agent/metrics/hallucination", headers=auth_headers
    )
    data = response.json()["data"]
    counts = data["state_counts"]
    assert sum(counts.values()) == data["total_checks"]
    assert data["policy_version"] == "hallucination-rate-v1"
```

- [ ] **Step 2: Run the contract tests and verify failure**

Run: `pytest -q backend/tests/test_metric_service.py backend/tests/test_hallucination_metrics.py -k "policy_and_rolling or mutually_exclusive_counts"`

Expected: FAIL because the service and response models do not yet expose the new metadata.

- [ ] **Step 3: Implement all-time and 30-day calculations**

Have `MetricCalculator.hallucination_rate` call `MetricsUtil.calculate_hallucination_metrics` twice: once with the default runtime gate and once with `window_days=30`. Put the second result under `metadata["rolling_30d"]`; carry through `state_counts`, `invalid_records`, `high_risk_checks`, `high_risk_reviewed`, `high_risk_review_coverage`, `policy_version`, `formal_minimum_sample_size`, and `target_percent`. Add optional Pydantic fields with defaults so old clients remain valid.

Set `MetricsResponse.minimum_sample_size` and `SystemMetricsResponse.minimum_sample_size` defaults to `10`, and expose `formal_minimum_sample_size=60` as a separate field; do not overload one field with both policies.

- [ ] **Step 4: Remove conflicting raw formulas and run tests**

Update `health.py` and `report_service.py` to read the canonical result; update the router's formula description to `confirmed hallucinations / completed evidence reviews`. Run:

`pytest -q backend/tests/test_metric_service.py backend/tests/test_hallucination_metrics.py`

Expected: PASS, including no-data, learner-scope, pending-gap, and snapshot regressions.

- [ ] **Step 5: Commit the service contract change**

```text
git add backend/app/services/metric_service.py backend/app/domains/agent/schemas.py backend/app/schemas/core.py backend/app/domains/agent/router.py backend/app/health.py backend/app/services/report_service.py backend/tests/test_metric_service.py backend/tests/test_hallucination_metrics.py
git commit -m "feat: expose governed hallucination metric"
```

### Task 5: Make the evidence report enforce the formal `<5%` gate

**Files:**
- Modify: `backend/scripts/generate_metric_evidence.py:20-90,180-285`
- Test: `backend/tests/test_metric_evidence.py`

**Interfaces:**
- Keep `_claim(metric, target, minimum_sample_size, operator)` and support both `">="` and `"<"` with strict comparison.
- `build_report(db)` adds `claims["hallucination_rate"]` and `evidence.hallucination.required_additional_reviews`.
- Keep `FORMAL_MINIMUM_SAMPLE_SIZE=10` for the existing adaptation claims, and add `HALLUCINATION_FORMAL_MINIMUM_SAMPLE_SIZE=60`, `hallucination_target_percent=5.0`, and `metric_policy_version="hallucination-rate-v1"` for the hallucination claim.

- [ ] **Step 1: Add failing strict-claim and remediation tests**

```python
def test_hallucination_claim_is_strict_and_requires_formal_sample():
    metric = _metric(5.0, 60, metric_id="hallucination_rate")
    claim = _claim(metric, target=5.0, minimum_sample_size=60, operator="<")
    assert claim["status"] == "failed"

    insufficient = _claim(
        _metric(4.0, 59, metric_id="hallucination_rate"),
        target=5.0, minimum_sample_size=60, operator="<"
    )
    assert insufficient["status"] == "insufficient_evidence"


def test_required_additional_reviews_for_current_baseline():
    remediation = _required_additional_reviews(hallucinations=3, evaluated=53)
    assert remediation == 8
```

- [ ] **Step 2: Run the report tests and verify failure**

Run: `pytest -q backend/tests/test_metric_evidence.py -k "strict_claim or additional_reviews"`

Expected: FAIL because `_claim` currently only handles `>=` and the report has no hallucination claim or remediation calculation.

- [ ] **Step 3: Implement strict claim evaluation and report metadata**

Keep `FORMAL_MINIMUM_SAMPLE_SIZE = 10` for the existing resource and answer claims, and add `HALLUCINATION_FORMAL_MINIMUM_SAMPLE_SIZE = 60`. Add `from math import floor` and `_required_additional_reviews(hallucinations: int, evaluated: int) -> int` using `max(0, floor(20 * hallucinations - evaluated) + 1)`, while documenting that the 60-record formal gate is applied separately. Add the hallucination claim to the aggregate formal status; a current 3/53 report must be `insufficient_evidence`, not a pass. Include state counts, high-risk review coverage, rolling-30-day data, policy version, and the computed remediation count in `evidence.hallucination`; a missing high-risk coverage value must make the formal claim `insufficient_evidence`.

- [ ] **Step 4: Generate a temporary report and run all report tests**

Run from the repository root:

`python backend/scripts/generate_metric_evidence.py --output artifacts/hallucination-rate-governance-check.json`

Then run: `pytest -q backend/tests/test_metric_evidence.py`

Expected: the temporary report contains `hallucination_rate` in `evidence.claims`, reports the current sample as below the formal gate, contains `required_additional_reviews`, and all tests pass. Do not overwrite the user's existing evidence report during this check.

- [ ] **Step 5: Commit the evidence-report change**

```text
git add backend/scripts/generate_metric_evidence.py backend/tests/test_metric_evidence.py
git commit -m "feat: enforce formal hallucination rate claim"
```

### Task 6: Provide a read-only review queue exporter

**Files:**
- Create: `backend/scripts/export_hallucination_review_queue.py`
- Create: `backend/tests/test_hallucination_review_queue.py`

**Interfaces:**
- `build_review_queue(db, limit: int | None = None) -> dict` reads records only and groups them by the canonical state.
- CLI `python backend/scripts/export_hallucination_review_queue.py --output <path>` writes JSON outside tracked source files.
- When `limit` is provided, it caps the total number of serialized records after chronological ordering; it does not change metric counts or sampling calculations.
- Each record item contains `id`, `task_id`, `state`, `original_content_sha256`, `original_content`, `reference_content`, `citations`, `conflict_type`, `is_hallucination`, `resolution_status`, and `judge_decision`.

- [ ] **Step 1: Add failing queue-export tests**

```python
from scripts.export_hallucination_review_queue import build_review_queue
from tests.test_hallucination_metrics import _add_record


def test_review_queue_contains_confirmed_rows_and_required_sample_count(
    db_session, sample_agent_task
):
    for index in range(53):
        _add_record(
            db_session, sample_agent_task.id, is_hallucination=index < 3,
            resolution_status="resolved",
            judge_decision="rejected" if index < 3 else "approved",
            conflict_points=([{"type": "hallucination_evidence"}]
                             if index < 3 else []),
        )
    queue = build_review_queue(db_session)
    assert len(queue["records"]["reviewed_hallucination"]) == 3
    assert queue["required_additional_reviews"] == 8
    assert queue["policy_version"] == "hallucination-rate-v1"
```

- [ ] **Step 2: Run the queue test and verify failure**

Run: `pytest -q backend/tests/test_hallucination_review_queue.py`

Expected: FAIL because the exporter and its canonical-state grouping do not exist.

- [ ] **Step 3: Implement the read-only exporter**

Load `DebateRecord` through `SessionLocal`, call `MetricsUtil.classify_debate_record` for every row, serialize only the fields in the interface, hash original content with SHA-256, and calculate `required_additional_reviews` from the current `H/E`. Never call `db.add`, `db.delete`, or `db.commit`; close the session in `main` and write the requested output path with UTF-8 JSON.

- [ ] **Step 4: Run the exporter tests and CLI check**

Run: `pytest -q backend/tests/test_hallucination_review_queue.py`

`python backend/scripts/export_hallucination_review_queue.py --output artifacts/hallucination-review-queue.json`

Expected: PASS and a JSON file grouped into the five mutually exclusive states, with the current three confirmed rows available for manual review.

- [ ] **Step 5: Commit the queue exporter**

```text
git add backend/scripts/export_hallucination_review_queue.py backend/tests/test_hallucination_review_queue.py
git commit -m "feat: export hallucination review queue"
```

### Task 7: Execute review, remediation, and full verification

**Files:**
- Read and review: `docs/evidence/metric-evidence-latest.json`
- Read-only operational input: current `DebateRecord` rows selected by `MetricsUtil.classify_debate_record`
- Verify: all files changed by Tasks 1-5

**Interfaces:**
- The operational output is an append-only review record and a versioned evidence report; no historical row deletion is permitted.
- The acceptance result is `passed` only when all-time and 30-day windows meet the formal gate, high-risk review coverage is 100%, and `invalid_record == 0`.

- [ ] **Step 1: Export the three current confirmed records before changing data**

Run the read-only exporter, which records each row's ID, task ID, original content hash, evidence citations, conflict type, `is_hallucination`, resolution status, and judge decision. Store the export outside tracked source files:

`python backend/scripts/export_hallucination_review_queue.py --output artifacts/hallucination-review-queue-before.json`

- [ ] **Step 2: Independently adjudicate and append corrections**

For each of the three rows, retain `reviewed_hallucination` unless a reviewer can point to a source-backed false positive. A correction must append a new final review with the old row ID, reviewer, reason, source citation, and before/after values. Evidence gaps are reclassified only when the source review proves there was no sufficient evidence at the time; they are not converted merely to lower the rate.

- [ ] **Step 3: Generate real stratified samples until the formal gate is reachable**

Use the existing production generation flow and fixed sampling metadata across time, industry, resource type, model version, and risk level. Review every high-risk or conflict sample; use the report's `required_additional_reviews` value to determine the minimum count. With H=3 and E=53, complete at least eight evidence-backed non-hallucination reviews to reach E=61, then continue the 30-day window until it has at least 30 qualifying reviews.

- [ ] **Step 4: Run focused, full, and safety verification**

Run:

`pytest -q backend/tests/test_hallucination_metrics.py backend/tests/test_hallucination_evidence.py backend/tests/test_judge_hallucination_rules.py backend/tests/test_metric_service.py backend/tests/test_metric_evidence.py`

`pytest -q backend/tests`

`git diff --check`

Expected: focused and full tests pass, the temporary report has no secret-like values, and API/report/health outputs share the same H/E and state counts.

- [ ] **Step 5: Produce the final acceptance report**

Run:

`python backend/scripts/generate_metric_evidence.py --output artifacts/hallucination-rate-governance-final.json`

Check `evidence.claims.hallucination_rate.status`, all-time and `rolling_30d` values, `state_counts`, `invalid_records`, high-risk coverage, and `metric_policy_version`. If any gate is not met, leave the claim as `insufficient_evidence` or `failed` and route publishing to manual review; do not manufacture a pass.
