# Adaptive Exercise Sync Design

## Goal

Publish an approved `exercise` resource as learner-owned adaptive-guidance questions automatically. The learner answers those questions, and the existing answer-record and learning-report flow records the result.

## Scope

- Publish only resources whose type is `exercise` and whose final audit passed.
- Store each published question in `issued_tutoring_questions` with the learner's `user_id`, the source resource id, and its position in the source set.
- Return only unanswered learner-owned questions from the tutoring question API. Correct answers remain server-only.
- Grade issued questions from the stored answer key and preserve the existing `AnswerRecord` report flow.

## Data Flow

1. `TaskRepository.save_resource_and_complete` creates a ready exercise resource.
2. It reads `basic_questions` and `advanced_questions` from `content_json` and publishes valid questions in the same database transaction.
3. `GET /tutoring/questions?learner_id=<id>` verifies access and returns public question fields only.
4. The adaptive-guidance page submits only question id, selected option letters, duration, and learner id.
5. `process_answer` uses the stored answer key, marks the question answered, creates `AnswerRecord`, and returns feedback.

## Rules

- Publishing the same resource twice is idempotent.
- Re-generating a topic supersedes only unanswered resource-published questions for that learner and topic; answered questions remain for reports.
- Failed audits and empty exercise payloads create no issued questions.
- Administrators can inspect a learner's question list through existing permission checks; learner answers use the learner account.

## Verification

- Backend tests prove publication, no answer-key leakage, idempotency, superseding, and server-side grading.
- Frontend tests prove the selected learner id is used for loading and that answer submission does not include a correct answer or local score.
- Run focused tests plus the frontend type-check/build before completion.
