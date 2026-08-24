from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field


class DiagnosticSessionCreate(BaseModel):
    learner_id: int = Field(..., gt=0)
    questions_per_dimension: int = Field(2, ge=2, le=3)


class DiagnosticAnswerCreate(BaseModel):
    question_id: str = Field(..., min_length=1, max_length=64)
    user_answer: Any
    time_spent_ms: int = Field(0, ge=0)


class DiagnosticQuestion(BaseModel):
    id: str
    type: str
    topic: str
    question: str
    options: List[str]
    difficulty: int
    knowledge_points: List[str] = Field(default_factory=list)
    generation_method: Optional[str] = None
    assessment_mode: str = "diagnostic"
    diagnostic_session_id: Optional[str] = None
    answered: bool = False


class DiagnosticSessionResponse(BaseModel):
    session_id: str
    learner_id: int
    status: str
    total_questions: int
    answered_questions: int
    questions_per_dimension: int
    questions: List[DiagnosticQuestion]
    assessments: Dict[str, Any] = Field(default_factory=dict)
