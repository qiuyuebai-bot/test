from datetime import datetime
import uuid
from typing import Any, Dict, List, Optional

from sqlalchemy.orm import Session

from app.domains.learner.models import (
    AnswerRecord,
    DiagnosticSession,
    IssuedTutoringQuestion,
    LearnerProfile,
)
from app.services.tutoring_service import AdaptiveTutoringService


class DiagnosticService:
    """Create and score a six-dimension learner ability assessment."""

    DIMENSIONS = (
        ("theoretical_foundation", "theory fundamentals"),
        ("programming_ability", "programming fundamentals"),
        ("algorithm_design", "algorithm design"),
        ("system_architecture", "system architecture"),
        ("data_analysis", "data analysis"),
        ("engineering_practice", "engineering practice"),
    )

    @classmethod
    def create_or_resume(
        cls,
        db: Session,
        user_id: int,
        learner_id: int,
        questions_per_dimension: int,
    ) -> Dict[str, Any]:
        existing = (
            db.query(DiagnosticSession)
            .filter(
                DiagnosticSession.user_id == user_id,
                DiagnosticSession.learner_id == learner_id,
                DiagnosticSession.status == "active",
            )
            .order_by(DiagnosticSession.created_at.desc())
            .first()
        )
        if existing:
            return cls.serialize_session(db, existing)

        learner = db.query(LearnerProfile).filter(LearnerProfile.id == learner_id).first()
        if not learner:
            raise ValueError("learner_not_found")

        session = DiagnosticSession(
            id=f"diag_{uuid.uuid4().hex}",
            user_id=user_id,
            learner_id=learner_id,
            status="active",
            questions_per_dimension=questions_per_dimension,
            dimension_counts={dimension: 0 for dimension, _ in cls.DIMENSIONS},
            results={"scores": {}},
        )
        db.add(session)
        learner.diagnostic_status = "in_progress"
        db.commit()
        db.refresh(session)

        try:
            for dimension, topic in cls.DIMENSIONS:
                questions = AdaptiveTutoringService.generate_dynamic_questions(
                    user_id=user_id,
                    learner_id=learner_id,
                    topic=topic,
                    difficulty=3,
                    question_count=questions_per_dimension,
                    replace_pending=False,
                    assessment_mode="diagnostic",
                    ability_dimension=dimension,
                    diagnostic_session_id=session.id,
                )
                counts = dict(session.dimension_counts or {})
                counts[dimension] = len(questions)
                session.dimension_counts = counts

            session.total_questions = sum(session.dimension_counts.values())
            db.commit()
            db.refresh(session)
            return cls.serialize_session(db, session)
        except Exception:
            session.status = "failed"
            db.commit()
            raise

    @classmethod
    def serialize_session(cls, db: Session, session: DiagnosticSession) -> Dict[str, Any]:
        questions = (
            db.query(IssuedTutoringQuestion)
            .filter(IssuedTutoringQuestion.diagnostic_session_id == session.id)
            .order_by(IssuedTutoringQuestion.created_at.asc(), IssuedTutoringQuestion.id.asc())
            .all()
        )
        public_questions = []
        for question in questions:
            payload = AdaptiveTutoringService._public_question(question)
            payload["answered"] = question.status == "answered"
            public_questions.append(payload)
        results = dict(session.results or {})
        return {
            "session_id": session.id,
            "learner_id": session.learner_id,
            "status": session.status,
            "total_questions": session.total_questions,
            "answered_questions": session.answered_questions,
            "questions_per_dimension": session.questions_per_dimension,
            "questions": public_questions,
            "assessments": results.get("assessments", {}),
        }

    @classmethod
    def submit_answer(
        cls,
        db: Session,
        user_id: int,
        learner_id: int,
        session_id: str,
        question_id: str,
        user_answer: Any,
        time_spent_ms: int,
    ) -> Dict[str, Any]:
        if not str(question_id).isdigit():
            raise ValueError("invalid_question")

        session = db.query(DiagnosticSession).filter(
            DiagnosticSession.id == session_id,
            DiagnosticSession.user_id == user_id,
            DiagnosticSession.learner_id == learner_id,
        ).first()
        if not session or session.status not in {"active", "completed"}:
            raise ValueError("diagnostic_session_not_found")

        question = db.query(IssuedTutoringQuestion).filter(
            IssuedTutoringQuestion.id == int(question_id),
            IssuedTutoringQuestion.user_id == user_id,
            IssuedTutoringQuestion.learner_id == learner_id,
            IssuedTutoringQuestion.diagnostic_session_id == session_id,
            IssuedTutoringQuestion.assessment_mode == "diagnostic",
        ).first()
        if not question:
            raise ValueError("diagnostic_question_not_found")
        if question.status == "answered":
            return {"success": True, "already_answered": True, "is_correct": None, "score": None}
        if question.status != "issued":
            raise ValueError("diagnostic_question_unavailable")

        answers = user_answer if isinstance(user_answer, list) else str(user_answer).split(",")
        normalized = sorted(str(value).strip().upper() for value in answers if str(value).strip())
        expected = sorted(str(value).strip().upper() for value in (question.answer_key or []))
        is_correct = normalized == expected
        score = 100.0 if is_correct else 0.0

        question.status = "answering"
        record = AnswerRecord(
            user_id=user_id,
            learner_id=learner_id,
            question_id=question.id,
            issued_question_id=question.id,
            question_type=question.question_type,
            question_topic=question.topic,
            question_difficulty=question.difficulty,
            question_content=question.content,
            user_answer=user_answer,
            correct_answer=question.answer_key,
            result="correct" if is_correct else "wrong",
            score=score,
            time_spent_ms=time_spent_ms,
            session_id=session_id,
            sequence_index=cls._sequence_number(db, question.id, session_id),
        )
        db.add(record)

        results = dict(session.results or {})
        scores = dict(results.get("scores") or {})
        dimension = question.ability_dimension or "unknown"
        dimension_scores = list(scores.get(dimension) or [])
        dimension_scores.append(score)
        scores[dimension] = dimension_scores
        session.results = {"scores": scores}
        question.status = "answered"
        question.answered_at = datetime.utcnow()
        db.flush()
        session.answered_questions = db.query(IssuedTutoringQuestion).filter(
            IssuedTutoringQuestion.diagnostic_session_id == session_id,
            IssuedTutoringQuestion.status == "answered",
        ).count()

        if session.answered_questions >= session.total_questions:
            cls._complete_session(db, session)
        db.commit()
        db.refresh(session)
        return {
            "success": True,
            "already_answered": False,
            "is_correct": is_correct,
            "score": score,
            "ability_dimension": dimension,
            "session_complete": session.status == "completed",
            "assessments": (session.results or {}).get("assessments", {}),
        }

    @staticmethod
    def _sequence_number(db: Session, question_id: int, session_id: str) -> int:
        return db.query(IssuedTutoringQuestion).filter(
            IssuedTutoringQuestion.diagnostic_session_id == session_id,
            IssuedTutoringQuestion.id <= question_id,
        ).count()

    @classmethod
    def _complete_session(cls, db: Session, session: DiagnosticSession) -> None:
        results = dict(session.results or {})
        scores = dict(results.get("scores") or {})
        assessments: Dict[str, Any] = {}
        learner = db.query(LearnerProfile).filter(LearnerProfile.id == session.learner_id).first()
        if not learner:
            raise ValueError("learner_not_found")
        existing = dict(learner.ability_assessments or {})

        for dimension, _ in cls.DIMENSIONS:
            values = [float(value) for value in scores.get(dimension, [])]
            if len(values) < 2:
                assessments[dimension] = {
                    "status": "insufficient_evidence",
                    "estimatedScore": None,
                    "confidence": 0.0,
                    "answeredCount": len(values),
                }
                continue
            mean = round(sum(values) / len(values), 1)
            spread = max(values) - min(values)
            confidence = round(min(0.95, 0.55 + len(values) * 0.08 - min(spread, 100) / 500), 2)
            prior = dict(existing.get(dimension) or {})
            adjustment = float(prior.get("manualAdjustment", 0) or 0)
            assessments[dimension] = {
                "status": "estimated",
                "estimatedScore": mean,
                "confidence": confidence,
                "answeredCount": len(values),
                "manualAdjustment": adjustment,
                "lastAssessedAt": datetime.utcnow().isoformat(),
            }
            setattr(learner, dimension, max(0.0, min(100.0, mean + adjustment)))

        session.results = {"scores": scores, "assessments": assessments}
        session.status = "completed"
        session.completed_at = datetime.utcnow()
        learner.ability_assessments = assessments
        learner.diagnostic_status = "completed"
        learner.diagnostic_completed_at = session.completed_at
