import math
from collections import Counter
from typing import List, Tuple
from django.db.models import Q
from peeldb.models import JobPost, SkillAssessmentAttempt, Skill
from .trust import compute_trust_score


def _tokenize(text: str) -> List[str]:
    return [t.lower() for t in (text or "").replace("/", " ").replace("-", " ").split() if t]


def _tfidf_matrix(docs: List[List[str]]):
    # Build vocabulary
    vocab = {}
    for doc in docs:
        for tok in set(doc):
            vocab.setdefault(tok, 0)
            vocab[tok] += 1
    N = len(docs)
    idf = {tok: math.log((N + 1) / (df + 1)) + 1.0 for tok, df in vocab.items()}
    mats = []
    for doc in docs:
        tf = Counter(doc)
        denom = sum(tf.values()) or 1
        vec = {}
        for tok, cnt in tf.items():
            if tok in idf:
                vec[tok] = (cnt / denom) * idf[tok]
        mats.append(vec)
    return mats, idf


def _cosine(a: dict, b: dict) -> float:
    if not a or not b:
        return 0.0
    # dot
    dot = 0.0
    for k, va in a.items():
        vb = b.get(k)
        if vb:
            dot += va * vb
    na = math.sqrt(sum(v*v for v in a.values())) or 1.0
    nb = math.sqrt(sum(v*v for v in b.values())) or 1.0
    return dot / (na * nb)


def _verified_skill_names(user) -> List[str]:
    attempts = (
        SkillAssessmentAttempt.objects.filter(user=user, status="completed", score__gte=0.6)
        .order_by("-completed_at")
    )
    names = []
    seen = set()
    for a in attempts.select_related("skill"):
        if a.skill_id not in seen:
            names.append(a.skill.name)
            seen.add(a.skill_id)
    return names


def recommend_internships(user, top_n: int = 10) -> List[Tuple[JobPost, float]]:
    verified = _verified_skill_names(user)
    if not verified:
        return []
    cand_doc = _tokenize(" ".join(verified))
    jobs = JobPost.objects.filter(Q(job_type="internship") & Q(status__in=["Live", "Published"]))
    job_docs = []
    job_list = []
    for j in jobs.select_related("company").prefetch_related("skills")[:500]:
        text = [j.title or "", j.company_name or "", j.company_description or ""]
        text += [s.name for s in j.skills.all()]
        job_docs.append(_tokenize(" ".join(text)))
        job_list.append(j)
    mats, idf = _tfidf_matrix([cand_doc] + job_docs)
    cand_vec = mats[0]
    sims = []
    for i, j in enumerate(job_list, start=1):
        sims.append((j, _cosine(cand_vec, mats[i])))

    trust = compute_trust_score(user)
    ranked = sorted(((j, sim * trust) for j, sim in sims), key=lambda x: x[1], reverse=True)
    return ranked[:top_n]

