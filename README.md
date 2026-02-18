# SmartQuiz 🚀

**SmartQuiz** es una aplicación de quizzes de práctica que soporta **CLI** y **Web**, con exámenes en **JSON puro**. Perfecta para preparación de certificaciones técnicas (HCIE, CCNA, etc.) o formación interna.

## ✨ Características

- **CLI nativo** (Python): runner interactivo con navegación (next/prev/goto), shuffle de preguntas, corrección automática.
- **Interfaz Web moderna**: Tailwind CSS, responsive, formularios para todos los tipos de pregunta.
- **Motor unificado**: misma lógica para CLI y Web (mismo JSON → misma corrección).
- **Tipos de pregunta**:
  - Single choice / True/False
  - Multiple choice
  - Fill-in-the-blank
- **Exámenes JSON** con:
  - Título, descripción, dificultad
  - Shuffle automático
  - Puntos por pregunta
  - Explicaciones opcionales
- **Corrección completa**: puntos totales, % correcto, detalle por pregunta.

## 🎯 Demo

### Web UI

```
Lista de exámenes → Formulario → Resultado con puntuación
```

![screenshot](https://via.placeholder.com/1200x600/0f172a/64748b?text=SmartQuiz+Web+Demo)

### CLI Runner

```
Available exams:
  1) hcie-storage-mock-01.json
Select exam number: 1

Loaded exam: Huawei HCIE-Storage Practice Exam
Q1 [multiple] Which OceanStor features...
Commands: n=next, p=previous, g<num>, s=submit
[Q1]> a,c
```

## 🚀 Rápido para empezar

```bash
# 1. Clona el repo
git clone https://github.com/javimcasas/SmartQuiz.git
cd SmartQuiz

# 2. Instala dependencias (solo para web)
pip install fastapi uvicorn jinja2

# 3. Añade exámenes a exams/
# (ej: copia el JSON de HCIE Storage que generé)

# 4. CLI (siempre funciona)
python quiz_runner.py

# 5. Web (opcional)
uvicorn web_app:app --reload
# Abre http://127.0.0.1:8000/
```

## 📁 Estructura del proyecto

```
SmartQuiz/
├── exams/                 # Tus JSON de exámenes
│   └── hcie-storage-mock-01.json
├── quizcore.py           # Motor central (lógica de quizzes)
├── quiz_runner.py        # CLI runner
├── web_app.py            # FastAPI + Jinja2 + Tailwind
├── templates/            # HTML views
└── README.md
```

## 📖 Formato de examen JSON

```json
{
  "id": "my-exam",
  "title": "My Practice Exam",
  "difficulty": "hard",
  "shuffle_questions": true,
  "questions": [
    {
      "number": 1,
      "type": "single",     // "true_false", "single", "multiple", "fill_blank"
      "question": "What is...",
      "options": [{"value": "a", "text": "..."}],
      "correct": ["a"],
      "points": 2
    }
  ]
}
```

## 🛠️ Desarrollo

```bash
# CLI puro (sin dependencias)
python quiz_runner.py

# Web con hot reload
uvicorn web_app:app --reload

# Añadir nuevo examen
# → Copia JSON a exams/, recarga página
```

## 🔮 Roadmap

- [ ] Editor web para crear exámenes JSON
- [ ] Exportar resultados CSV/PDF
- [ ] Multi-idioma
- [ ] API REST completa
- [ ] Docker deployment

## 📄 Licencia

MIT License – ver `LICENSE`.

---

**Hecho con ❤️ por [javimcasas](https://github.com/javimcasas)**
