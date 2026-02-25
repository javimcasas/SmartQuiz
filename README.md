
# SmartQuiz 🚀

**SmartQuiz** is a **full-featured quiz application** with **CLI** and **modern Web UI**, supporting **AI-generated exams**, **completed results tracking**, and **plain JSON** format. Perfect for technical certifications (HCIE, CCNA, etc.) or knowledge testing.

## ✨ Features

### 🎯 Core

- **Native CLI** + **Responsive Web UI** (FastAPI + Tailwind CSS)
- **Unified engine**: Same logic for CLI/Web (same JSON → same grading)
- **Question types**: Single choice, True/False, Multiple choice, Fill-in-the-blank
- **Automatic grading** with detailed results per question
- **Lists ordered by recency**: Available exams & completed sessions

### 🤖 AI-Powered Exam Generation

- **Perplexity AI integration** (`sonar` model + JSON Schema)
- **Generate exams** from any topic with custom difficulty, question count, types
- **Strict JSON Schema validation** ensuring perfect compatibility

### 📊 Results Tracking

- **Auto-save completed exams** to `completed/` folder
- **Full results storage**: Questions, answers, points, explanations
- **PASS/FAIL badges** based on `passing_score`
- **Review sessions** with detailed per-question feedback

### 📱 Web UI Features

- **Drag & drop JSON import**
- **Delete exams** with confirmation
- **Theme support** (auto-detect dark/light)
- **Temporary notifications** (auto-fade)
- **Mobile responsive cards**

## 📊 Exam Schema (JSON)

```json
{
  "id": "my-exam",
  "title": "Practice Exam",
  "description": "Exam description",
  "difficulty": "easy|medium|hard",
  "shuffle_questions": true,
  "time_limit_seconds": 3600,
  "format": "multiple",
  "passing_score": 80.0,
  "questions": [
    {
      "number": 1,
      "type": "single",           // "single", "multiple", "true_false", "fill_blank"
      "question": "What is...",
      "options": [
        {"value": "a", "text": "Option A", "description": "Explanation"},
        {"value": "b", "text": "Option B"}
      ],
      "correct": ["a"],
      "points": 2,
      "case_sensitive": false     // fill_blank only
    }
  ]
}
```

## 🚀 Quick Start

### 1. Clone & Setup

```bash
git clone https://github.com/javimcasas/SmartQuiz.git
cd SmartQuiz
```

### 2. Web Dependencies

```bash
pip install fastapi uvicorn jinja2 aiohttp python-dotenv
```

### 3. **AI Generation** (Optional but recommended)

```bash
# Create .env file
echo "PERPLEXITY_API_KEY=your_api_key_here" > .env
```

Get your key at [perplexity.ai](https://www.perplexity.ai/)

### 4. Run

```bash
# CLI (no dependencies needed)
python quiz_runner.py

# Web UI
uvicorn web_app:app --reload
# Open http://127.0.0.1:8000/
```

## 📁 Project Structure

```
SmartQuiz/
├── exams/              # 📚 Available exam JSON files (ordered by creation)
├── completed/          # 🏆 Completed sessions (ordered by completion time)
├── quizcore.py         # Core engine + validation
├── web_app.py          # FastAPI Web UI + Perplexity AI
├── templates/          # Jinja2 + Tailwind UI
├── static/             # CSS/JS
├── .env               # PERPLEXITY_API_KEY (AI generation)
└── README.md
```

## 🎮 Usage

### Web Flow

```
Home (/): Available exams (newest first) → Generate/Import → Practice → Results
Completed (/completed): Review sessions (newest first) → Detailed review
```

### Generate Exam (AI ✨)

```
POST /generate-exam:
- title: "HCIE Storage"
- description: "Huawei OceanStor Dorado features"
- num_questions: 20
- difficulty: "hard"
- types: ["single", "multiple"]
- passing_score: 75.0
→ AI generates valid JSON exam instantly!
```

### CLI Flow

```
python quiz_runner.py
→ Select exam → Answer interactively → Auto-grade + detailed results
```

## 🛠️ Development

```bash
# Hot reload web
uvicorn web_app:app --reload

# Add exam manually
cp my-exam.json exams/

# AI generation requires .env with PERPLEXITY_API_KEY
```

## 🔮 Roadmap

- [X] AI exam generation (Perplexity + JSON Schema)
- [X] Completed results tracking + review
- [X] Passing score + PASS/FAIL badges
- [X] Exams ordered by creation time
- [ ] Web editor (JSON builder)
- [ ] Results export (CSV/PDF)
- [ ] Multi-language
- [ ] Docker

## 📄 License

MIT License – see `LICENSE`.

---

**Made with ❤️ by [javimcasas](https://github.com/javimcasas)**

**⭐ Star if useful!**
