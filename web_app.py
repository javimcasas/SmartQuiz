# web_app.py
from __future__ import annotations
import os
import json
import uuid
import tempfile
import aiohttp
import io
import pdfplumber
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional, Any

from fastapi import FastAPI, Request, Form, UploadFile, File, HTTPException
from fastapi.responses import RedirectResponse, FileResponse, JSONResponse
from fastapi.templating import Jinja2Templates
from fastapi.staticfiles import StaticFiles

from quizcore import Exam, Question, load_exam, _check_question_answer, QuestionResult, GradeResult, grade_exam

from dotenv import load_dotenv
load_dotenv()

BASE_DIR = Path(__file__).parent
EXAMS_DIR = BASE_DIR / "exams"
COMPLETED_DIR = BASE_DIR / "completed"

# Crear directorio si no existe
COMPLETED_DIR.mkdir(exist_ok=True)

app = FastAPI()
app.mount("/static", StaticFiles(directory=str(BASE_DIR / "static")), name="static")
templates = Jinja2Templates(directory=str(BASE_DIR / "templates"))


async def call_ai_api(prompt: str, model: str = "sonar") -> str:
    api_key = os.getenv("PERPLEXITY_API_KEY")
    if not api_key:
        raise HTTPException(status_code=500, detail="Missing PERPLEXITY_API_KEY")

    url = "https://api.perplexity.ai/chat/completions"
    headers = {"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"}
    
    # ✅ JSON SCHEMA EXAM STRUCT
    exam_schema = {
        "type": "object",
        "properties": {
            "id": {"type": "string"},
            "title": {"type": "string"},
            "description": {"type": "string"},
            "difficulty": {"type": "string"},
            "shuffle_questions": {"type": "boolean"},
            "time_limit_seconds": {"type": "integer"},
            "format": {"type": "string"},
            "passing_score": {"type": "number"},
            "questions": {
                "type": "array",
                "items": {
                    "type": "object",
                    "properties": {
                        "number": {"type": "integer"},
                        "type": {"type": "string", "enum": ["single", "multiple", "true_false", "fill_blank"]},
                        "question": {"type": "string"},
                        "options": {
                            "type": "array",
                            "items": {
                                "type": "object",
                                "properties": {
                                    "value": {"type": "string"},
                                    "text": {"type": "string"},
                                    "description": {"type": "string"}
                                },
                                "required": ["value", "text"]
                            }
                        },
                        "correct": {"type": "array", "items": {"type": "string"}},
                        "points": {"type": "number"}
                    },
                    "required": ["number", "type", "question", "options", "correct", "points"]
                }
            }
        },
        "required": ["id", "title", "description", "difficulty", "questions"],
        "additionalProperties": False
    }
    
    payload = {
        "model": model,
        "messages": [{"role": "user", "content": prompt}],
        "max_tokens": 8000,
        "temperature": 0.05,
        "response_format": {
            "type": "json_schema",
            "json_schema": {
                "name": "smartquiz_exam",
                "schema": exam_schema
            }
        }
    }

    timeout = aiohttp.ClientTimeout(total=90)
    async with aiohttp.ClientSession(timeout=timeout) as session:
        async with session.post(url, headers=headers, json=payload) as resp:
            if resp.status >= 400:
                err_text = await resp.text()
                raise HTTPException(status_code=502, detail=f"Perplexity {resp.status}: {err_text[:300]}")
            
            data = await resp.json()
            return data["choices"][0]["message"]["content"]


def list_exams() -> List[Dict[str, Any]]:
    """Lista exámenes ordenados por fecha de creación/modificación (más recientes primero)"""
    exams = []
    for exam_path in EXAMS_DIR.glob("*.json"):
        try:
            stat = exam_path.stat()
            created_time = datetime.fromtimestamp(stat.st_ctime)  # Fecha creación
            modified_time = datetime.fromtimestamp(stat.st_mtime)  # Fecha modificación
            
            # Usar creación primero, fallback a modificación
            exam_time = created_time if created_time > modified_time else modified_time
            
            exam = load_exam(exam_path)
            
            # Formatear time_limit para template
            time_limit_seconds = getattr(exam, 'time_limit_seconds', None)
            time_limit_display = None
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
            
            exams.append({
                "id": exam_path.stem,
                "path": exam_path,
                "title": exam.title,
                "description": exam.description,
                "difficulty": exam.difficulty,
                "time_limit_display": time_limit_display,
                "passing_score": getattr(exam, 'passing_score', 0.0),
                "created_time": exam_time,  # Para ordenar
                "created_str": exam_time.strftime("%Y-%m-%d %H:%M"),  # Para template opcional
            })
        except Exception:
            # Ignorar archivos corruptos
            continue
    
    # ✅ ORDENAR POR FECHA REAL DE CREACIÓN (más recientes primero)
    exams.sort(key=lambda x: x["created_time"], reverse=True)
    return exams


def list_completed_exams() -> List[Dict[str, Any]]:
    """Lista todos los exámenes completados ordenados por fecha (más recientes primero)"""
    results = []
    for result_file in COMPLETED_DIR.glob("*.json"):  # Quitar sorted aquí
        try:
            with result_file.open(encoding="utf-8") as f:
                data = json.load(f)
            
            # Parsear fecha para ordenar correctamente
            completed_at = data.get("completed_at")
            if not completed_at:
                continue
                
            # Convertir ISO string a datetime para ordenar
            dt = datetime.fromisoformat(completed_at.replace('Z', '+00:00'))
            
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
                    "completed_at": data["completed_at"],  # String original para template
                    "completed_at_dt": dt,  # Objeto datetime para ordenar
                    "percentage": data["percentage"],
                    "total_points": data["total_points"],
                    "max_points": data["max_points"],
                    "result_file": result_file.name,
                    "passing_score": getattr(exam, 'passing_score', 0.0)
                })
        except (json.JSONDecodeError, KeyError, ValueError, ValueError):
            # Ignorar archivos corruptos o fechas inválidas
            continue
    
    # ✅ ORDENAR POR FECHA REAL (más recientes primero)
    results.sort(key=lambda x: x["completed_at_dt"], reverse=True)
    return results


def load_exam_by_id(exam_id: str) -> Exam:
    """Carga examen por ID usando glob directo"""
    exam_path = EXAMS_DIR / f"{exam_id}.json"
    if not exam_path.exists():
        raise ValueError(f"Exam '{exam_id}' not found")
    return load_exam(exam_path)


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
    
def extract_pdf_text(pdf_bytes: bytes) -> str:
    """Extrae texto PDF con pdfplumber (100% puro Python)"""
    try:
        with pdfplumber.open(io.BytesIO(pdf_bytes)) as pdf:
            text = ""
            for page in pdf.pages[:10]:  # Max 10 páginas aprox
                page_text = page.extract_text()
                if page_text:
                    text += page_text + "\n"
            return text.strip()[:50000]  # Max 50k chars
    except Exception:
        return ""  # Falla silenciosa


async def extract_text_from_files(files: List[UploadFile]) -> str:
    """Extrae texto LIMPIO para IA - menos ruido"""
    texts = []
    for file in files[:3]:
        if file.size > 15 * 1024 * 1024:
            continue
            
        content = await file.read()
        filename = file.filename.lower()
        
        if filename.endswith('.pdf'):
            text = extract_pdf_text(content)
        elif filename.endswith('.txt'):
            text = content.decode('utf-8', errors='ignore')
        else:
            continue
            
        # 1500 chars por archivo
        clean_text = text.strip()[:1500].replace('\n', ' ').replace('\t', ' ')
        if clean_text:
            texts.append(f"📄 {file.filename}:\n{clean_text}")
    
    return "\n---\n".join(texts)


@app.get("/")
def index(request: Request):
    exams = list_exams()  # ✅ Nueva función
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


@app.delete("/exam/{exam_id}")
def delete_exam(exam_id: str):
    """
    Borra el archivo JSON del examen en exams/ por su ID.
    Devuelve JSON para consumo vía fetch en el frontend.
    """
    exam_path = EXAMS_DIR / f"{exam_id}.json"
    if not exam_path.exists():
        raise HTTPException(status_code=404, detail="Exam not found")

    try:
        exam = load_exam(exam_path)
        title = getattr(exam, "title", exam_id)
    except Exception:
        # Si hay problema cargando, igualmente intentamos borrar
        title = exam_id

    try:
        exam_path.unlink()
    except OSError as e:
        raise HTTPException(status_code=500, detail=f"Could not delete exam file: {e}")

    return JSONResponse({"message": f"Exam '{title}' deleted successfully"})


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


@app.get("/generate")
def generate_form(request: Request):
    return get_theme_response(request, "generate.html", {})


@app.post("/generate-exam")
async def generate_exam(
    request: Request,
    title: str = Form(...),
    description: str = Form(...),
    num_questions: int = Form(...),
    difficulty: str = Form(...),
    types: List[str] = Form(...),
    time_limit_seconds: Optional[int] = Form(0),
    passing_score: float = Form(...),
    total_points: float = Form(...),
    format: str = Form("multiple"),
    model: str = Form("sonar"),
    files: List[UploadFile] = File(default=[])
):
    valid_files = [
        file for file in files 
        if file.filename and file.filename.strip() and file.size > 0
    ]
    
    # Extraer textos de archivos para contexto IA
    file_context = ""
    if valid_files:
        file_context = await extract_text_from_files(valid_files)
        
    # 🎯 1. Prompt para IA (tu API)
    context_intro = f"DOCUMENT CONTEXT:\\n{file_context}\\n\\n" if file_context else ""

    prompt = f"""Generate EXACTLY {num_questions} SmartQuiz questions about "{description}".
    {context_intro}

CRITICAL RULES:
1. EXACTLY {num_questions} questions (numbered 1-N)
2. Types ONLY: {','.join(types)} 
3. 4 options A/B/C/D (except fill_blank/true_false)
4. "correct": ["a"] o ["a","b"] array - EXACT lowercase match to option values
5. Points: {total_points/num_questions:.1f} cada una
6. Explanations SOLO en "description" de opción correcta
7. NO markdown, NO texto extra, NO ```json

RESPUESTA JSONSchema VÁLIDO ÚNICAMENTE:

{{
  "id": "ai-{uuid.uuid4().hex[:8]}",
  "title": "{title}",
  "description": "{description}",
  "difficulty": "{difficulty}",
  "shuffle_questions": true,
  "time_limit_seconds": {time_limit_seconds},
  "format": "{format}",
  "passing_score": {passing_score},
  "questions": [ /* {num_questions} objetos */ ]
}}"""

    try:
        # 🎯 2. Llamada a IA (ejemplo con mi API interna)
        ai_response = await call_ai_api(prompt, model)  # ← Implementar esto
        
        # 🎯 3. Parse + validar
        raw_exam = json.loads(ai_response)
        with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False, encoding='utf-8') as temp:
            json.dump(raw_exam, temp, indent=2, ensure_ascii=False)
            temp_path = Path(temp.name)
        
        exam = load_exam(temp_path)  # ← Valida estructura
        temp_path.unlink()
        
        # 🎯 4. Guardar en exams/
        exam_id = raw_exam.get("id", f"ai-{uuid.uuid4().hex[:8]}")
        counter = 1
        output_path = EXAMS_DIR / f"{exam_id}.json"
        while output_path.exists():
            exam_id = f"{raw_exam.get('id', 'ai-generated')}-{counter}"
            output_path = EXAMS_DIR / f"{exam_id}.json"
            counter += 1
        
        with output_path.open("w", encoding="utf-8") as f:
            json.dump(raw_exam, f, indent=2, ensure_ascii=False)
        
        # 🎯 5. Feedback + redirect
        success_msg = f"✅ Exam '{title}' generated successfully!"  # Usa 'title' no exam.title
        return RedirectResponse(f"/?success={success_msg.replace(' ', '%20')}&exam_id={exam_id}", status_code=303)
    
    except json.JSONDecodeError:
        raise HTTPException(400, "AI generated invalid JSON format")
    except Exception as e:
        raise HTTPException(500, f"Generation failed: {str(e)}")
