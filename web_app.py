# web_app.py
from __future__ import annotations

from pathlib import Path
from typing import Dict, List

from fastapi import FastAPI, Request, Form
from fastapi.responses import RedirectResponse
from fastapi.templating import Jinja2Templates

from quizcore import Exam, Question, load_exam, _check_question_answer, QuestionResult, GradeResult, grade_exam

BASE_DIR = Path(__file__).parent
EXAMS_DIR = BASE_DIR / "exams"

app = FastAPI()
templates = Jinja2Templates(directory=str(BASE_DIR / "templates"))


def list_exam_files() -> List[Path]:
    return sorted(EXAMS_DIR.glob("*.json"))


def load_exam_by_id(exam_id: str) -> Exam:
    for p in list_exam_files():
        if p.stem == exam_id:
            return load_exam(p)
    raise ValueError(f"Exam '{exam_id}' not found")


def grade_exam_by_index(exam: Exam, user_answers_by_index: Dict[int, List[str]]) -> GradeResult:
    per_question: List[QuestionResult] = []
    total_points = 0
    max_points = 0

    for idx, q in enumerate(exam.questions):
        max_points += q.points
        ua = user_answers_by_index.get(idx, [])

        is_correct = _check_question_answer(q, ua)
        gained = q.points if is_correct else 0
        total_points += gained

        per_question.append(
            QuestionResult(
                question_number=idx + 1,
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


def get_theme_response(request: Request, template_name: str, context: dict):
    """Función helper para manejar cookies de tema en todas las respuestas"""
    theme_cookie = request.cookies.get('theme')
    
    # Si no hay cookie, detectar preferencia del navegador
    if not theme_cookie:
        # Verificar headers de preferencia de tema
        prefers_dark = (
            request.headers.get('sec-ch-prefers-color-scheme') == 'dark' or
            request.headers.get('prefers-color-scheme') == 'dark'
        )
        default_theme = 'dark' if prefers_dark else 'light'
        response = templates.TemplateResponse(template_name, {**context, "request": request})
        response.set_cookie(
            key='theme', 
            value=default_theme, 
            httponly=True, 
            samesite='lax',
            max_age=365 * 24 * 60 * 60  # 1 año
        )
        return response
    
    # Cookie existe, pasarla al template
    return templates.TemplateResponse(template_name, {**context, "request": request})


@app.get("/")
def index(request: Request):
    exams = []
    for p in list_exam_files():
        exam = load_exam(p)
        time_limit_seconds = getattr(exam, 'time_limit_seconds', None)
        if time_limit_seconds:
            hours = time_limit_seconds // 3600
            minutes = (time_limit_seconds % 3600) // 60
            seconds = time_limit_seconds % 60
            display_parts = []
            if hours > 0:
                display_parts.append(f"{hours}h")
            display_parts.append(f"{minutes}m")
            if seconds > 0:
                display_parts.append(f"{seconds}s")
            time_limit_display = "⏱️ " + " ".join(display_parts)
        else:
            time_limit_display = None
        exams.append(
            {
                "id": p.stem,
                "title": exam.title,
                "description": exam.description,
                "difficulty": exam.difficulty,
                "time_limit_display": time_limit_display,
            }
        )
    return get_theme_response(request, "index.html", {"exams": exams})


@app.get("/exam/{exam_id}")
def show_exam(request: Request, exam_id: str):
    exam = load_exam_by_id(exam_id)
    return get_theme_response(request, "exam.html", {
        "exam_id": exam_id,
        "exam": exam
    })


@app.post("/exam/{exam_id}")
async def submit_exam(request: Request, exam_id: str):
    exam = load_exam_by_id(exam_id)
    form = await request.form()

    # Mapa de número de pregunta -> Question
    questions_by_number: Dict[int, Question] = {q.number: q for q in exam.questions}

    user_answers_by_number: Dict[int, List[str]] = {}

    idx = 0
    while True:
        num_key = f"q{idx}_num"
        num_val = form.get(num_key)
        if num_val is None:
            break  # no hay más preguntas en el form

        try:
            q_number = int(num_val)
        except ValueError:
            idx += 1
            continue

        q = questions_by_number.get(q_number)
        if q is None:
            idx += 1
            continue

        base_key = f"q{idx}"

        if q.type in ("single", "true_false"):
            val = form.get(base_key)
            if val:
                user_answers_by_number[q_number] = [val]

        elif q.type == "multiple":
            selected: List[str] = []
            for opt in q.options:
                cb_name = f"{base_key}_{opt.value}"
                if form.get(cb_name) == "on":
                    selected.append(opt.value)
            if selected:
                user_answers_by_number[q_number] = selected

        elif q.type == "fill_blank":
            val = form.get(base_key)
            if val:
                user_answers_by_number[q_number] = [val]

        idx += 1

    # Ahora usamos el corrector original por número
    result = grade_exam(exam, user_answers_by_number)

    n_correct = sum(1 for qr in result.per_question if qr.is_correct)
    n_total = len(result.per_question)

    return get_theme_response(request, "result.html", {
        "exam": exam,
        "result": result,
        "n_correct": n_correct,
        "n_total": n_total
    })
