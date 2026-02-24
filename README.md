
# SmartQuiz 🚀

**SmartQuiz** is a practice quiz application that supports **CLI** and **Web**, with exams in **plain JSON**. Perfect for preparing technical certifications (HCIE, CCNA, etc.) or internal training.

## ✨ Features

- **Native CLI** (Python): interactive runner with navigation (next/prev/goto), question shuffling, automatic grading.
- **Modern Web interface**: Tailwind CSS, responsive, forms for all question types.
- **Unified engine**: same logic for CLI and Web (same JSON → same grading).
- **Question types**:
  - Single choice / True/False
  - Multiple choice
  - Fill-in-the-blank
- **JSON exams** with:
  - Title, description, difficulty
  - Automatic shuffle
  - Points per question
  - Optional explanations
- **Full grading**: total points, correct percentage, per-question details.

## 🎯 Demo

### Web UI

```
Exam list → Form → Scored result
```


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

## 🚀 Quick start

```bash
# 1. Clone the repo
git clone https://github.com/javimcasas/SmartQuiz.git
cd SmartQuiz

# 2. Install dependencies (web only)
pip install fastapi uvicorn jinja2

# 3. Add exams to exams/
# (e.g. copy the HCIE Storage JSON exam)

# 4. CLI (always works)
python quiz_runner.py

# 5. Web (optional)
uvicorn web_app:app --reload
# Open http://127.0.0.1:8000/
```

## 📁 Project structure

```
SmartQuiz/
├── exams/                 # Your exam JSON files
│   └── hcie-storage-mock-01.json
├── quizcore.py            # Core engine (quiz logic)
├── quiz_runner.py         # CLI runner
├── web_app.py             # FastAPI + Jinja2 + Tailwind
├── templates/             # HTML views
└── README.md
```

## 📖 JSON exam format

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

## 🛠️ Development

```bash
# Pure CLI (no extra dependencies)
python quiz_runner.py

# Web with hot reload
uvicorn web_app:app --reload

# Add a new exam
# → Copy a JSON file into exams/, reload the page
```

## 🔮 Roadmap

- [ ] Web editor to create JSON exams
- [ ] Export results to CSV/PDF
- [ ] Multi-language support
- [ ] Full REST API
- [ ] Docker deployment

## 📄 License

MIT License – see `LICENSE`.

---

**Made with ❤️ by [javimcasas](https://github.com/javimcasas)**
