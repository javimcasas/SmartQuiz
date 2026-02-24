# web_app.py
from __future__ import annotations
import json
import uuid
import tempfile
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional, Any

from fastapi import FastAPI, Request, Form, UploadFile, File, HTTPException
from fastapi.responses import RedirectResponse, FileResponse
from fastapi.templating import Jinja2Templates
from fastapi.staticfiles import StaticFiles

from quizcore import Exam, Question, load_exam, _check_question_answer, QuestionResult, GradeResult, grade_exam

BASE_DIR = Path(__file__).parent
EXAMS_DIR = BASE_DIR / "exams"
COMPLETED_DIR = BASE_DIR / "completed"  # Nueva carpeta para resultados

# Crear directorio si no existe
COMPLETED_DIR.mkdir(exist_ok=True)


app = FastAPI()
app.mount("/static", StaticFiles(directory=str(BASE_DIR / "static")), name="static")
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
                    "result_file": result_file.name,
                    "passing_score": getattr(exam, 'passing_score', 0.0)
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
    """Guarda el resultado COMPLETO con preguntas y opciones"""
    completion_id = str(uuid.uuid4())
    
    # Crear resultados completos con preguntas
    per_question_full = []
    for qr in result.per_question:
        # Buscar pregunta original por número
        question = next((q for q in exam.questions if q.number == qr.question_number), None)
        if question:
            per_question_full.append({
                "question_number": qr.question_number,
                "question_text": question.question,
                "question_type": question.type,
                "options": [
                    {
                        "value": opt.value,
                        "text": opt.text,
                        "description": opt.description
                    }
                    for opt in question.options
                ],
                "is_correct": qr.is_correct,
                "gained_points": qr.gained_points,
                "max_points": qr.max_points,
                "user_answer": qr.user_answer,
                "correct_answer": qr.correct_answer
            })
    
    data = {
        "id": completion_id,
        "exam_id": exam.id,
        "title": exam.title,
        "completed_at": datetime.now().isoformat(),
        "total_points": result.total_points,
        "max_points": result.max_points,
        "percentage": result.percentage,
        "per_question": per_question_full,
        "passing_score": getattr(exam, 'passing_score', 0.0)
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

def import_exam(file: UploadFile) -> str:
    """Importa un archivo JSON como examen nuevo"""
    if not file.filename.lower().endswith('.json'):
        raise HTTPException(status_code=400, detail="Only JSON files allowed")
    
    content = file.file.read().decode('utf-8')
    try:
        raw_exam = json.loads(content)
        
        # ✅ FIX: Crear Path temporal para validar con load_exam
        with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False, encoding='utf-8') as temp_file:
            json.dump(raw_exam, temp_file, indent=2, ensure_ascii=False)
            temp_path = Path(temp_file.name)
        
        try:
            exam = load_exam(temp_path)  # Ahora sí: Path válido
        finally:
            temp_path.unlink()  # Limpiar temp file
        
        # Generar ID único
        exam_id = raw_exam.get('id', f"imported_{uuid.uuid4().hex[:8]}")
        output_path = EXAMS_DIR / f"{exam_id}.json"
        
        # Si ya existe, añadir sufijo
        counter = 1
        while output_path.exists():
            exam_id = f"{raw_exam.get('id', 'imported')}_{counter}"
            output_path = EXAMS_DIR / f"{exam_id}.json"
            counter += 1
        
        # Guardar el raw_exam validado
        with output_path.open('w', encoding='utf-8') as f:
            json.dump(raw_exam, f, indent=2, ensure_ascii=False)
        
        return exam_id
        
    except json.JSONDecodeError:
        raise HTTPException(status_code=400, detail="Invalid JSON format")
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Invalid exam format: {str(e)}")


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
            "passing_score": getattr(exam, 'passing_score', 0.0)
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
        exam = load_exam_by_id(result_data["exam_id"])
        
        # Convertir a formato compatible con template
        result_obj = type('Result', (), {
            'total_points': result_data['total_points'],
            'max_points': result_data['max_points'],
            'percentage': result_data['percentage'],
            'per_question': result_data['per_question']
        })()
        
        context = {
            "exam": exam,
            "result": result_obj,
            "n_correct": sum(1 for qr in result_data["per_question"] if qr["is_correct"]),
            "n_total": len(result_data["per_question"])
        }
        return get_theme_response(request, "result.html", context)
    except ValueError:
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


@app.post("/upload-exam")
async def upload_exam(file: UploadFile = File(...)):
    try:
        exam_id = import_exam(file)
        return {"success": True, "exam_id": exam_id, "message": f"Exam '{exam_id}' imported successfully!"}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail="Upload failed")


@app.get("/upload")
def upload_form(request: Request):
    return get_theme_response(request, "upload.html", {})