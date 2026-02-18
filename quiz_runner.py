# quiz_runner.py
from __future__ import annotations

from pathlib import Path
from typing import Dict, List

from quizcore import (
    load_exam,
    Exam,
    Question,
    GradeResult,
    QuestionResult,
    _check_question_answer,
)


EXAMS_DIR = Path(__file__).parent / "exams"


def list_exam_files() -> List[Path]:
    return sorted(EXAMS_DIR.glob("*.json"))


def choose_exam() -> Path:
    exams = list_exam_files()
    if not exams:
        print(f"No exams found in {EXAMS_DIR}")
        raise SystemExit(1)

    print("Available exams:")
    for idx, p in enumerate(exams, start=1):
        print(f"  {idx}) {p.name}")

    while True:
        choice = input("Select exam number: ").strip()
        if not choice.isdigit():
            print("Please enter a valid number.")
            continue
        i = int(choice)
        if 1 <= i <= len(exams):
            return exams[i - 1]
        print("Number out of range.")


def render_question(q: Question, visible_index: int, current_answer: List[str] | None) -> None:
    print("-" * 60)
    print(f"Q{visible_index} [{q.type}]")
    print(q.question)

    if q.options:
        for opt in q.options:
            print(f"  {opt.value}) {opt.text}")

    if current_answer:
        print(f"\nCurrent answer: {', '.join(current_answer)}")
    print()
    print("Commands: ")
    print("  - answer input (e.g. a, a,c,d, some text)")
    print("  - n = next, p = previous, g <num> = go to question, s = submit exam")


def parse_answer_input(raw: str, q: Question) -> List[str]:
    raw = raw.strip()
    if not raw:
        return []

    if q.type in ("true_false", "single", "multiple"):
        # Esperamos lista separada por comas para multiple, o un único valor para single/true_false
        parts = [p.strip() for p in raw.split(",") if p.strip()]
        return parts

    if q.type == "fill_blank":
        return [raw]

    return []

def grade_exam_by_index(exam: Exam, user_answers_by_index: Dict[int, List[str]]) -> GradeResult:
    per_question: List[QuestionResult] = []
    total_points = 0
    max_points = 0

    for idx, q in enumerate(exam.questions):
        max_points += q.points
        ua = user_answers_by_index.get(idx, [])  # clave = índice

        is_correct = _check_question_answer(q, ua)
        gained = q.points if is_correct else 0
        total_points += gained

        per_question.append(
            QuestionResult(
                question_number=idx + 1,  # número visible (Q1, Q2, ...)
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

def run_exam(exam: Exam) -> None:
    user_answers: Dict[int, List[str]] = {}
    idx = 0  # índice sobre exam.questions

    while True:
        q = exam.questions[idx]
        current = user_answers.get(idx)  # clave por índice, no por q.number
        render_question(q, visible_index=idx + 1, current_answer=current)

        cmd = input(f"[Q{idx + 1}]> ").strip()

        if not cmd:
            continue

        # Comandos de navegación
        if cmd.lower() == "n":
            if idx < len(exam.questions) - 1:
                idx += 1
            else:
                print("Already at last question.")
            continue

        if cmd.lower() == "p":
            if idx > 0:
                idx -= 1
            else:
                print("Already at first question.")
            continue

        if cmd.lower().startswith("g "):
            _, _, rest = cmd.partition(" ")
            if rest.isdigit():
                target_visible = int(rest)
                target_idx = target_visible - 1
                if 0 <= target_idx < len(exam.questions):
                    idx = target_idx
                else:
                    print(f"Question {target_visible} not found.")
            else:
                print("Usage: g <question_number>")
            continue

        if cmd.lower() == "s":
            break

        ans = parse_answer_input(cmd, q)
        user_answers[idx] = ans

    # Fin del bucle -> corregimos
    result = grade_exam_by_index(exam, user_answers)
    
    n_correct = sum(1 for qr in result.per_question if qr.is_correct)
    n_total_questions = len(result.per_question)

    print("\n" + "=" * 60)
    print(f"Exam: {exam.title}")
    print(f"Score (points): {result.total_points}/{result.max_points} "
        f"({result.percentage:.2f}%)")
    print(f"Score (questions): {n_correct}/{n_total_questions}")
    print("=" * 60)

    for qr in result.per_question:
        status = "OK" if qr.is_correct else "WRONG"
        ua = ", ".join(qr.user_answer) if qr.user_answer else "(no answer)"
        ca = ", ".join(qr.correct_answer)
        print(f"Q{qr.question_number}: {status} "
              f"[{qr.gained_points}/{qr.max_points}]")
        print(f"  Your answer: {ua}")
        print(f"  Correct:     {ca}")
        print()

    print("End of exam.")


def main() -> None:
    exam_path = choose_exam()
    exam = load_exam(exam_path)
    print(f"\nLoaded exam: {exam.title}")
    if exam.description:
        print(exam.description)
    if exam.difficulty:
        print(f"Difficulty: {exam.difficulty}")
    print()
    run_exam(exam)



if __name__ == "__main__":
    main()
