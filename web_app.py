# web_app.py
from __future__ import annotations
import json
import uuid
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional, Any

from fastapi import FastAPI, Request, Form
from fastapi.responses import RedirectResponse
from fastapi.templating import Jinja2Templates

from quizcore import Exam, Question, load_exam, _check_question_answer, QuestionResult, GradeResult, grade_exam

BASE_DIR = Path(__file__).parent
EXAMS_DIR = BASE_DIR / "exams"
COMPLETED_DIR = BASE_DIR / "completed"  # Nueva carpeta para resultados

# Crear directorio si no existe
COMPLETED_DIR.mkdir(exist_ok=True)

app = FastAPI()
templates = Jinja2Templates(directory=str(BASE_DIR / "templates"))


def list_exam_files() -> List[Path]:
    return sorted(EXAMS_DIR.glob("*.json"))


def list_completed_exams() -> List[Dict[str, Any]]:
    """Lista todos los exámenes completados ordenados por fecha (más recientes primero)"""
    results = []
    for result_file in sorted(COMPLETED_DIR.glob("*.json"), reverse=True):
        try:
            with result_file.open(encoding="utf-8") as f:
                data = json.load(f)
            
            # Cargar el examen original para metadata
            exam_file = EXAMS_DIR / f"{data['exam_id']}.json"
            if exam_file.exists():
                exam = load_exam(exam_file)
                results.append({
                    "id": data["id"],
                    "exam_id": data["exam_id"],
                    "title": exam.title,
                    "description": exam.description,
                    "difficulty": exam.difficulty,
                    "completed_at": data["completed_at"],
                    "percentage": data["percentage"],
                    "total_points": data["total_points"],
                    "max_points": data["max_points"],
                    "result_file": result_file.name
                })
        except (json.JSONDecodeError, KeyError, ValueError):
            # Ignorar archivos corruptos
            continue
    
    return results


def load_exam_by_id(exam_id: str) -> Exam:
    for p in list_exam_files():
        if p.stem == exam_id:
            return load_exam(p)
    raise ValueError(f"Exam '{exam_id}' not found")


def save_completed_exam(exam: Exam, result: GradeResult) -> str:
    """Guarda el resultado completado y retorna el ID único"""
    completion_id = str(uuid.uuid4())
    data = {
        "id": completion_id,
        "exam_id": exam.id,
        "title": exam.title,
        "completed_at": datetime.now().isoformat(),
        "total_points": result.total_points,
        "max_points": result.max_points,
        "percentage": result.percentage,
        "per_question": [
            {
                "question_number": qr.question_number,
                "is_correct": qr.is_correct,
                "gained_points": qr.gained_points,
                "max_points": qr.max_points,
                "user_answer": qr.user_answer,
                "correct_answer": qr.correct_answer
            }
            for qr in result.per_question
        ]
    }
    
    result_file = COMPLETED_DIR / f"{completion_id}.json"
    with result_file.open("w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)
    
    return completion_id


def load_completed_exam(completion_id: str) -> Dict[str, Any]:
    """Carga un examen completado por su ID"""
    result_file = COMPLETED_DIR / f"{completion_id}.json"
    if not result_file.exists():
        raise ValueError(f"Completed exam '{completion_id}' not found")
    
    with result_file.open(encoding="utf-8") as f:
        return json.load(f)


def get_theme_response(request: Request, template_name: str, context: dict):
    """Función helper para manejar cookies de tema en todas las respuestas"""
    theme_cookie = request.cookies.get('theme')
    
    if not theme_cookie:
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
            max_age=365 * 24 * 60 * 60
        )
        return response
    
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
        exams.append({
            "id": p.stem,
            "title": exam.title,
            "description": exam.description,
            "difficulty": exam.difficulty,
            "time_limit_display": time_limit_display,
        })
    context = {"exams": exams}
    return get_theme_response(request, "index.html", context)


@app.get("/completed")
def completed(request: Request):
    completed_exams = list_completed_exams()
    context = {"completed_exams": completed_exams}
    return get_theme_response(request, "completed.html", context)


@app.get("/completed/{completion_id}")
def completed_detail(request: Request, completion_id: str):
    try:
        result_data = load_completed_exam(completion_id)
        # Cargar metadata del examen original
        exam = load_exam_by_id(result_data["exam_id"])
        context = {
            "exam": exam,
            "result": result_data,
            "n_correct": sum(1 for qr in result_data["per_question"] if qr["is_correct"]),
            "n_total": len(result_data["per_question"])
        }
        return get_theme_response(request, "result.html", context)
    except ValueError as e:
        # Si no encuentra el examen, mostrar error (o redirigir)
        return RedirectResponse("/", status_code=302)

@app.get("/api/completed/count")
def get_completed_count() -> Dict[str, int]:
    """API simple para contador de exámenes completados"""
    count = len(list(COMPLETED_DIR.glob("*.json")))
    return {"count": count}


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

    questions_by_number: Dict[int, Question] = {q.number: q for q in exam.questions}
    user_answers_by_number: Dict[int, List[str]] = {}

    idx = 0
    while True:
        num_key = f"q{idx}_num"
        num_val = form.get(num_key)
        if num_val is None:
            break

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

    result = grade_exam(exam, user_answers_by_number)
    
    # ¡NUEVO! Guardar el examen completado
    save_completed_exam(exam, result)

    n_correct = sum(1 for qr in result.per_question if qr.is_correct)
    n_total = len(result.per_question)

    return get_theme_response(request, "result.html", {
        "exam": exam,
        "result": result,
        "n_correct": n_correct,
        "n_total": n_total
    })
