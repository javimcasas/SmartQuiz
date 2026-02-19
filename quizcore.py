# quizcore.py
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import List, Dict, Optional, Any
import json
import random


# ====== Domain models ======

@dataclass
class AnswerOption:
    value: str
    text: str
    description: Optional[str] = None


@dataclass
class Question:
    number: int
    type: str              # "true_false", "single", "multiple", "fill_blank"
    question: str
    options: List[AnswerOption]
    correct: List[str]
    points: int = 1
    case_sensitive: bool = False  # relevante para fill_blank


@dataclass
class Exam:
    id: str
    title: str
    description: str
    questions: List[Question]
    shuffle_questions: bool = False
    difficulty: Optional[str] = None
    time_limit_seconds: Optional[int] = None
    format: str = "multiple"
    block_previous: bool = False
    

@dataclass
class QuestionResult:
    question_number: int
    is_correct: bool
    gained_points: int
    max_points: int
    user_answer: List[str]
    correct_answer: List[str]


@dataclass
class GradeResult:
    total_points: int
    max_points: int
    percentage: float
    per_question: List[QuestionResult]


@dataclass
class QuestionResultFull:
    question_number: int
    question_text: str
    question_type: str
    options: List[AnswerOption]
    is_correct: bool
    gained_points: int
    max_points: int
    user_answer: List[str]
    correct_answer: List[str]


# ====== Loading & validation ======

def load_exam(path: str | Path) -> Exam:
    path = Path(path)
    with path.open(encoding="utf-8") as f:
        raw = json.load(f)

    questions: List[Question] = []
    for q in raw.get("questions", []):
        options_raw = q.get("options") or []
        options = [
            AnswerOption(
                value=o["value"],
                text=o["text"],
                description=o.get("description")
            )
            for o in options_raw
        ]

        question = Question(
            number=q["number"],
            type=q["type"],
            question=q["question"],
            options=options,
            correct=list(q["correct"]),
            points=q.get("points", 1),
            case_sensitive=q.get("case_sensitive", False),
        )
        questions.append(question)

    exam = Exam(
        id=raw["id"],
        title=raw["title"],
        description=raw.get("description", ""),
        questions=questions,
        shuffle_questions=raw.get("shuffle_questions", False),
        difficulty=raw.get("difficulty"),
        time_limit_seconds=raw.get("time_limit_seconds"),
        format=raw.get("format", "multiple"),
        block_previous=raw.get("block_previous", False),
    )

    validate_exam(exam)
    if exam.shuffle_questions:
        random.shuffle(exam.questions)
        
    if exam.time_limit_seconds and exam.time_limit_seconds < 0: 
        raise ValueError("Invalid time limit")

    return exam


def validate_exam(exam: Exam) -> None:
    numbers = set()
    for q in exam.questions:
        if q.number in numbers:
            raise ValueError(f"Duplicate question number: {q.number}")
        numbers.add(q.number)

        # Para tipos con opciones, validamos que los "correct" existan en ellas
        if q.type in ("true_false", "single", "multiple"):
            option_values = {o.value for o in q.options}
            for c in q.correct:
                if c not in option_values:
                    raise ValueError(
                        f"Question {q.number}: correct value '{c}' "
                        f"not found in options {option_values}"
                    )

        # Para fill_blank no hay opciones, así que no validamos contra options


# ====== Grading ======

def grade_exam(exam: Exam, user_answers: Dict[int, List[str]]) -> GradeResult:
    per_question: List[QuestionResult] = []
    total_points = 0
    max_points = 0

    for q in exam.questions:
        max_points += q.points
        ua = user_answers.get(q.number, [])

        is_correct = _check_question_answer(q, ua)
        gained = q.points if is_correct else 0
        total_points += gained

        per_question.append(
            QuestionResult(
                question_number=q.number,
                is_correct=is_correct,
                gained_points=gained,
                max_points=q.points,
                user_answer=ua,
                correct_answer=q.correct,
            )
        )

    percentage = (total_points / max_points * 100) if max_points > 0 else 0.0
    return GradeResult(
        total_points=total_points,
        max_points=max_points,
        percentage=percentage,
        per_question=per_question,
    )


def _check_question_answer(q: Question, user_answer: List[str]) -> bool:
    # Normalizamos según tipo
    if q.type in ("true_false", "single", "multiple"):
        correct_set = set(q.correct)
        ua_set = set(user_answer)
        # Regla simple: tiene que coincidir exactamente el conjunto
        return ua_set == correct_set

    if q.type == "fill_blank":
        if not user_answer:
            return False
        # Tomamos solo la primera respuesta del usuario
        ua = user_answer[0]
        if not q.case_sensitive:
            ua_norm = ua.strip().lower()
            correct_norm = [c.strip().lower() for c in q.correct]
            return ua_norm in correct_norm
        else:
            ua_norm = ua.strip()
            correct_norm = [c.strip() for c in q.correct]
            return ua_norm in correct_norm

    # Si el tipo es desconocido, lo marcamos como incorrecto
    return False
