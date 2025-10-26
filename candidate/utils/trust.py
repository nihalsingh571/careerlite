from datetime import datetime, timedelta
from django.utils import timezone
from peeldb.models import SkillAssessmentAttempt


def compute_assessment_accuracy(user) -> float:
    qs = SkillAssessmentAttempt.objects.filter(user=user, status="completed")
    if not qs.exists():
        return 0.0
    total = 0
    correct = 0
    for a in qs.only("total_questions", "correct_answers"):
        total += a.total_questions
        correct += a.correct_answers
    return (correct / total) if total else 0.0


def compute_verification_recency(user) -> float:
    qs = SkillAssessmentAttempt.objects.filter(user=user, status="completed").order_by("-completed_at")
    if not qs.exists() or not qs.first().completed_at:
        return 0.0
    last = qs.first().completed_at
    days = (timezone.now() - last).days
    # 1.0 at 0 days, decays linearly to 0.0 at 180 days
    freshness = max(0.0, 1.0 - (days / 180.0))
    return min(1.0, freshness)


def compute_trust_score(user, recruiter_rating: float | None = None, verified_internships: int = 0) -> float:
    acc = compute_assessment_accuracy(user)
    rec = compute_verification_recency(user)

    if recruiter_rating is None:
        # Case 1: no recruiter rating
        return 0.7 * acc + 0.3 * rec

    # Confidence factor for recruiter rating (grow with count)
    cf = min(1.0, 0.5 + 0.1 * max(0, verified_internships))  # 0.5 baseline up to 1.0
    adj_rating = recruiter_rating * cf

    return 0.4 * acc + 0.4 * adj_rating + 0.2 * rec

