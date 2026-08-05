# Knowledge-Grounded Hallucination Detection Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Replace keyword-driven hallucination decisions with claim-level knowledge-base evidence, structured knowledge-gap reporting, traceable citations, and a frontend credibility indicator.

**Architecture:** Keep `HallucinationUtil.detect_hallucination()` and `JudgeAgent.execute()` compatible with their tuple/dictionary contracts, but make evidence classification the primary decision. Claims are matched to supplied knowledge slices using similarity and entity overlap, then surfaced as supported, weakly supported, contradicted, or insufficient. The frontend consumes the new camelCase report fields and links no-evidence users to the existing knowledge-base upload page.

**Tech Stack:** Python, pytest, loguru, existing Chroma/KnowledgeService results, React, TypeScript, Vitest, Testing Library.

## Global Constraints

- Strong relevance is `similarity >= 0.70`; weak relevance is `0.50 <= similarity < 0.70`; below `0.50` with no entity match is insufficient evidence.
- No fabricated facts or citations; insufficient evidence must produce a knowledge-gap report and upload guidance.
- Every authoritative citation uses `[Document Name-Paragraph Number]`.
- Keyword signals are diagnostic only and cannot independently mark hallucination.
- Emit an `EVIDENCE_GAP` marker whenever a knowledge gap is returned.
- Preserve unrelated working-tree changes.

---

### Task 1: Add failing backend evidence tests

**Files:**
- Modify: `backend/tests/test_judge_hallucination_rules.py`
- Create: `backend/tests/test_hallucination_evidence.py`

**Interfaces:**
- Consumes: `HallucinationUtil.detect_hallucination(content, reference_knowledge=...)` and `JudgeAgent.execute(...)`.
- Produces: regression coverage for strong evidence, weak evidence, contradiction, entity fallback, and knowledge gaps.

- [ ] **Step 1: Write the failing tests first**

```python
from app.utils.hallucination import HallucinationUtil


def test_strong_evidence_is_supported_and_cited():
    detected, info = HallucinationUtil.detect_hallucination(
        "Python 3.12 adds the improved error messages.",
        reference_knowledge=[{
            "title": "Python Release Notes",
            "content": "Python 3.12 adds improved error messages.",
            "similarity": 0.86,
            "slice_index": 2,
            "slice_id": 12,
            "doc_id": 4,
        }],
    )
    assert detected is False
    assert info["credibility"] == "high"
    assert info["claims"][0]["status"] == "supported"
    assert info["citations"][0]["label"] == "[Python Release Notes-Paragraph 3]"


def test_insufficient_evidence_returns_knowledge_gap_and_logs_marker(caplog):
    detected, info = HallucinationUtil.detect_hallucination(
        "The Aurora protocol supports seven independent recovery modes.",
        reference_knowledge=[{
            "title": "Unrelated Notes", "content": "A short history of databases.",
            "similarity": 0.21,
        }],
    )
    assert detected is False
    assert info["credibility"] == "no_evidence"
    assert info["knowledge_gap"]["present"] is True
    assert "Aurora" in info["knowledge_gap"]["entities"]
    assert "EVIDENCE_GAP" in caplog.text
```

Also add JudgeAgent assertions that keyword-only wording does not emit `hallucination_keyword`, while an explicit contradiction emits `hallucination_evidence`.

- [ ] **Step 2: Run the focused tests and verify they fail**

Run: `backend\venv\Scripts\python.exe -m pytest backend/tests/test_hallucination_evidence.py -q`

Expected: FAIL because the detector does not return `credibility`, claim statuses, citations, or an `EVIDENCE_GAP` log.

### Task 2: Implement claim extraction and evidence classification

**Files:**
- Modify: `backend/app/utils/hallucination.py`
- Test: `backend/tests/test_hallucination_evidence.py`

**Interfaces:**
- Consumes: generated text and knowledge slice dictionaries.
- Produces: `_split_claims`, `_extract_entities`, `_classify_claim`, `_build_citation`, and the extended `detect_hallucination` result.

- [ ] **Step 1: Add deterministic helpers and threshold constants**

Implement sentence/bullet splitting, normalized entity extraction, similarity parsing, entity overlap, numeric/version conflict detection, and one-based paragraph citation formatting. Keep malformed similarity at `0.0` and omit citations with no valid title/paragraph identity.

- [ ] **Step 2: Make evidence classification the primary detector path**

For each claim, select the highest-ranked candidate, classify it using the dual thresholds, aggregate credibility/coverage, and set `hallucination_detected` only for contradictions. Preserve keyword/technical checks as diagnostic fields and cap their contribution so wording alone cannot trigger a finding.

- [ ] **Step 3: Add `EVIDENCE_GAP` logging and structured gap output**

When any claim is `insufficient_evidence`, log a warning containing the literal marker and claim/entity context, and populate `knowledge_gap` with claims, entities, attributes, and the upload prompt.

- [ ] **Step 4: Run backend evidence tests**

Run: `backend\venv\Scripts\python.exe -m pytest backend/tests/test_hallucination_evidence.py backend/tests/test_judge_hallucination_rules.py -q`

Expected: PASS.

### Task 3: Adapt JudgeAgent and persistence-facing issue contracts

**Files:**
- Modify: `backend/app/agents/judge_agent.py`
- Modify: `backend/app/agents/content_corrector.py`
- Modify: `backend/app/agents/task_repository.py`
- Test: `backend/tests/test_hallucination_evidence.py`

**Interfaces:**
- Consumes: detector detail dictionary from Task 2.
- Produces: top-level `credibility`, `evidence_coverage`, `citations`, `knowledge_gap`, and `hallucination_evidence` issues while reading legacy keyword records safely.

- [ ] **Step 1: Replace keyword issue creation with evidence issue creation**

Create issues from contradicted claims only, including status, reason, and citation labels. Do not create an issue solely because `detected_keywords` is non-empty.

- [ ] **Step 2: Preserve correction/debate behavior**

Teach correction suggestions to use contradiction evidence and knowledge gaps; retain the old `hallucination_keyword` branch only for historical records. Ensure persisted `is_hallucination` checks recognize `hallucination_evidence`.

- [ ] **Step 3: Run judge and repository tests**

Run: `backend\venv\Scripts\python.exe -m pytest backend/tests/test_hallucination_evidence.py backend/tests/test_judge_hallucination_rules.py -q`

Expected: PASS.

### Task 4: Add frontend evidence types, adapter, and Vitest regression tests

**Files:**
- Create: `src/lib/hallucinationEvidence.ts`
- Create: `src/lib/hallucinationEvidence.test.ts`
- Modify: `src/types/index.ts`

**Interfaces:**
- Consumes: snake_case or camelCase API payloads after the request adapter.
- Produces: `Credibility`, `HallucinationClaim`, `HallucinationReport`, and `normalizeHallucinationReport` with safe defaults.

- [ ] **Step 1: Write Vitest tests before implementation**

```ts
import { describe, expect, it } from 'vitest'
import { normalizeHallucinationReport } from './hallucinationEvidence'

describe('hallucination evidence adapter', () => {
  it('keeps sufficient evidence and citations', () => {
    const report = normalizeHallucinationReport({
      credibility: 'high', evidence_coverage: 1,
      citations: [{ label: '[Python Release Notes-Paragraph 3]', title: 'Python Release Notes', paragraph: 3 }],
      claims: [{ text: 'Python 3.12 adds improved errors.', status: 'supported', similarity: 0.86, citations: ['[Python Release Notes-Paragraph 3]'] }],
    })
    expect(report.credibility).toBe('high')
    expect(report.citations[0].label).toBe('[Python Release Notes-Paragraph 3]')
  })

  it('defaults an evidence gap to noEvidence with upload guidance', () => {
    const report = normalizeHallucinationReport({ knowledge_gap: { present: true, entities: ['Aurora'] } })
    expect(report.credibility).toBe('noEvidence')
    expect(report.knowledgeGap.entities).toContain('Aurora')
    expect(report.knowledgeGap.uploadPrompt).toBeTruthy()
  })
})
```

- [ ] **Step 2: Run Vitest and verify the new tests fail**

Run: `npm test -- src/lib/hallucinationEvidence.test.ts --run`

Expected: FAIL because the adapter and types do not exist.

- [ ] **Step 3: Implement normalization and types**

Normalize both `evidenceCoverage`/`evidence_coverage` and `no_evidence`/`noEvidence`, default missing arrays to `[]`, and never throw for malformed optional fields.

- [ ] **Step 4: Run the Vitest adapter tests**

Run: `npm test -- src/lib/hallucinationEvidence.test.ts --run`

Expected: PASS.

### Task 5: Render the credibility indicator and knowledge-gap action

**Files:**
- Modify: `src/pages/LearningReport.tsx`
- Modify: `src/pages/LearningReport.test.tsx`

**Interfaces:**
- Consumes: `normalizeHallucinationReport` and typed `HallucinationReport`.
- Produces: four-level credibility badge, footnote citations, and `/knowledge-base` upload action for `noEvidence`.

- [ ] **Step 1: Add failing component tests**

Render representative high, medium, low, and no-evidence responses; assert the visible label and that only no-evidence renders a link to `/knowledge-base`.

- [ ] **Step 2: Implement the indicator and evidence sections**

Use camelCase fields, render authoritative citations as footnotes, place weak references in a background section, and show the knowledge-gap claims/entities without inventing content.

- [ ] **Step 3: Run focused frontend tests and typecheck**

Run: `npm test -- src/pages/LearningReport.test.tsx src/lib/hallucinationEvidence.test.ts --run` and `npm run typecheck`.

Expected: PASS with no TypeScript errors.

### Task 6: Add calibration fixture and run the full verification set

**Files:**
- Create: `backend/tests/fixtures/hallucination_claims.json`
- Create: `backend/tests/test_hallucination_calibration.py`
- Modify: `backend/app/config.py` only if threshold settings are not already configurable.

**Interfaces:**
- Consumes: labeled claim/evidence rows and detector thresholds.
- Produces: deterministic ROC points and a documented threshold smoke test.

- [ ] **Step 1: Add labeled fixture and ROC calculation test**

Include positive contradiction, supported, weak, and insufficient examples; calculate false-positive/true-positive points for `0.50` and `0.70` and assert the output is stable.

- [ ] **Step 2: Run backend and frontend verification**

Run: `backend\venv\Scripts\python.exe -m pytest backend/tests/test_hallucination_evidence.py backend/tests/test_judge_hallucination_rules.py backend/tests/test_hallucination_calibration.py -q` and `npm test -- --run`.

Expected: PASS. Run `npm run build` if the focused typecheck is clean.

