# Adaptive Exercise Sync Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Automatically publish approved generated exercises to the matching learner's adaptive-guidance queue and record answers through the existing report flow.

**Architecture:** `TaskRepository` saves the resource and delegates conversion of its structured questions to `AdaptiveTutoringService`. Issued question rows retain the source resource and a server-only key. The API loads only queued questions for an authorized learner, and the frontend submits only the learner's selected answer.

**Tech Stack:** FastAPI, SQLAlchemy, Alembic, Pytest, React, TypeScript, Vitest.

## Global Constraints

- Do not change the user's uncommitted resource-generation work on `main`.
- Publish only audit-passed `exercise` resources.
- Correct answers must never be returned by the issued-question endpoint or sent by the frontend.
- Keep answered question rows and answer records for report history.

---

### Task 1: Source Traceability and Publication Service

**Files:**
- Modify: `backend/app/domains/learner/models.py`
- Create: `backend/alembic/versions/d8e3f4a5b6c7_add_issued_question_source.py`
- Modify: `backend/app/services/tutoring_service.py`
- Test: `backend/tests/test_resource_to_tutoring_sync.py`

**Interfaces:**
- Produces: `AdaptiveTutoringService.publish_resource_questions(db, resource, learner, topic) -> int`
- Produces: `AdaptiveTutoringService.get_issued_questions(learner_id) -> list[dict]`

- [x] Add nullable `source_resource_id` and `source_question_index` fields to `IssuedTutoringQuestion`.
- [x] Add the matching Alembic migration with a unique constraint over `(source_resource_id, source_question_index)`.
- [x] Write tests for publishing question payloads, hiding answer keys, idempotency, and superseding pending same-topic resource questions.
- [x] Implement question normalization, transactional publication, and public issued-question serialization.
- [x] Run `python -m pytest tests/test_resource_to_tutoring_sync.py -q`.

### Task 2: Automatic Publication and Authorized Retrieval

**Files:**
- Modify: `backend/app/agents/task_repository.py`
- Modify: `backend/app/domains/tutoring/router.py`
- Test: `backend/tests/test_resource_to_tutoring_sync.py`

**Interfaces:**
- Consumes: `publish_resource_questions(db, resource, learner, topic)`.
- Produces: `GET /tutoring/questions?learner_id=<id>` returns queued public question data.

- [x] Add a test that saving an audit-passed exercise creates learner-owned issued questions and that a failed audit does not.
- [x] Read the task target topic, save it to the resource, and publish the exercise inside `save_resource_and_complete` before commit.
- [x] Require `learner_id` for question retrieval and use existing learner permission checks.
- [x] Run `python -m pytest tests/test_resource_to_tutoring_sync.py -q`.

### Task 3: Secure Learner Submission UI

**Files:**
- Modify: `src/api/core.ts`
- Modify: `src/pages/AdaptiveGuidance.tsx`
- Create: `src/pages/AdaptiveGuidance.test.tsx`

**Interfaces:**
- Consumes: `coreApi.getTutoringQuestions(learnerId)` and `coreApi.submitAnswer({ learnerId, questionId, userAnswer, timeSpentMs, hintsUsed })`.
- Produces: learner-specific question loading and server-authoritative result display.

- [x] Add a frontend test that loads questions with the current learner id and submits no answer key or client score.
- [x] Make issued-question answer fields optional/absent in API types.
- [x] Load queued questions for the selected learner and use the server response for correct/wrong state and score.
- [x] Show an empty state explaining that an approved generated exercise is needed when no question is queued.
- [x] Run `npm.cmd test -- AdaptiveGuidance.test.tsx` and `npm.cmd run typecheck`.

### Task 4: Regression Verification

**Files:**
- Test: `backend/tests/test_resource_to_tutoring_sync.py`
- Test: `src/pages/AdaptiveGuidance.test.tsx`

- [x] Run `backend/.venv/Scripts/python.exe -m pytest tests/test_tutoring_service.py tests/test_resource_to_tutoring_sync.py -q`.
- [x] Run `npm.cmd run build`.
- [x] Review the diff to confirm only feature files, migration, tests, and design records changed.
