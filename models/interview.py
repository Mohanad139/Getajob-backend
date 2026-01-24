from pydantic import BaseModel
from typing import Optional, List


class InterviewSessionCreate(BaseModel):
    job_title: str
    job_description: str
    num_questions: Optional[int] = 5


class InterviewQuestionResponse(BaseModel):
    id: int
    question_type: str
    question_text: str
    user_answer: Optional[str]
    ai_feedback: Optional[str]
    score: Optional[int]


class AnswerSubmit(BaseModel):
    question_id: int
    answer: str


class InterviewFeedback(BaseModel):
    score: int
    strengths: List[str]
    weaknesses: List[str]
    suggestions: List[str]
