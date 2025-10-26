from django.shortcuts import render, get_object_or_404, redirect
from django.http import JsonResponse, Http404
from django.views.decorators.http import require_http_methods
from django.db import transaction
from django.utils import timezone
from peeldb.models import Skill, Question, MCQOption, SkillAssessmentAttempt, SkillAssessmentAnswer
from mpcomp.views import jobseeker_login_required
import random


def _pick_questions(skill: Skill, count: int = 5):
    tough = list(Question.objects.filter(skills=skill, status="Live", difficulty="tough"))
    easy = list(Question.objects.filter(skills=skill, status="Live", difficulty="easy"))
    random.shuffle(tough)
    random.shuffle(easy)
    picked = []
    # Aim 2 tough + 3 easy by default
    picked.extend(tough[:2])
    remain = count - len(picked)
    picked.extend(easy[:max(remain, 0)])
    if len(picked) < count:
        rest = list(Question.objects.filter(skills=skill, status="Live").exclude(id__in=[q.id for q in picked]))
        random.shuffle(rest)
        picked.extend(rest[: count - len(picked)])
    return picked[:count]


@jobseeker_login_required
@require_http_methods(["GET"]) 
def start_skill_assessment(request, skill_id):
    skill = get_object_or_404(Skill, id=skill_id)
    questions = _pick_questions(skill, 5)
    if len(questions) == 0:
        return render(request, "candidate/skill_assessment_empty.html", {"skill": skill})
    with transaction.atomic():
        attempt = SkillAssessmentAttempt.objects.create(user=request.user, skill=skill, status="in_progress")
        # we don't persist the selection ordering; render will include all questions
    # Prepare payload
    q_payload = []
    for q in questions:
        options = list(MCQOption.objects.filter(question=q))
        random.shuffle(options)
        q_payload.append({
            "id": q.id,
            "title": q.title,
            "description": q.description,
            "difficulty": q.difficulty,
            "time_limit": 30 if q.difficulty == "tough" else 20,
            "options": [{"id": o.id, "text": o.text} for o in options],
        })
    return render(request, "candidate/skill_assessment.html", {"attempt": attempt, "skill": skill, "questions": q_payload})


@jobseeker_login_required
@require_http_methods(["POST"]) 
def submit_skill_answer(request, attempt_id):
    attempt = get_object_or_404(SkillAssessmentAttempt, id=attempt_id, user=request.user)
    if attempt.status == "completed":
        return JsonResponse({"success": False, "error": "Attempt already completed"}, status=400)
    try:
        qid = int(request.POST.get("question_id"))
        oid = int(request.POST.get("option_id")) if request.POST.get("option_id") else None
        time_taken = int(request.POST.get("time_taken_sec", 0))
    except (TypeError, ValueError):
        return JsonResponse({"success": False, "error": "Invalid payload"}, status=400)

    question = get_object_or_404(Question, id=qid)
    option = MCQOption.objects.filter(id=oid, question=question).first() if oid else None
    is_correct = bool(option and option.is_correct)
    SkillAssessmentAnswer.objects.create(
        attempt=attempt,
        question=question,
        selected_option=option,
        is_correct=is_correct,
        time_taken_sec=max(time_taken, 0),
    )
    return JsonResponse({"success": True, "is_correct": is_correct})


@jobseeker_login_required
@require_http_methods(["POST"]) 
def finish_skill_assessment(request, attempt_id):
    attempt = get_object_or_404(SkillAssessmentAttempt, id=attempt_id, user=request.user)
    if attempt.status != "completed":
        attempt.finalize()
    return JsonResponse({
        "success": True,
        "score": attempt.score,
        "correct": attempt.correct_answers,
        "total": attempt.total_questions,
    })
