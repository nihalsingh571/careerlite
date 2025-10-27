# CareerLite - Open Source Job Portal

CareerLite is a modern, lightweight job board with an emphasis on authenticity and verifiable skills. It provides a clean end‑to‑end hiring flow for candidates and recruiters, plus a trust‑based recommendation engine that matches candidates to internships using a transparent TF‑IDF + Cosine Similarity model multiplied by a Trust Score.

Useful links:
- See SETUP.md for deeper setup details
- Use the GitHub tracker in this repository for issues/PRs

---

## Project Overview

CareerLite streamlines hiring with candidate skill verification, recruiter tools, and a transparent recommendation system. It’s designed to run well on low‑resource infra (college/institution servers) while being easy to develop and maintain.

---

## User Roles & Permissions

CareerLite implements role‑based access control with distinct user types:
- Recruiters, Recruiter Admin, Agency Admin, Agency Recruiter
- Candidates (Job Seekers)
- Admin/Support (optional)

---

## Core Features

### For Recruiters & Companies
- Job posting and management, applicant tracking, interview coordination
- Email templates, bulk ops, metrics dashboard

### For Candidates
- Profile builder, resume upload, application tracking, alerts
- Skill verification via 5 MCQs (20s easy / 30s tough)
- Recommendations based on verified skills and trust score

### Technical Highlights
- Django + PostgreSQL core
- Tailwind/Bootstrap hybrid UI, with Sass/Less precompilers
- Optional Celery + Redis for background jobs (email etc.)
- Optional Elasticsearch (legacy search pages)

---

## Technology Stack

### Backend
- Django 5.x, Python 3.12+ (3.13 works)
- PostgreSQL 14+
- Optional: Redis + Celery, Elasticsearch 7.x

### Frontend & Assets
- Tailwind CSS (compiled to `static/css/tailwind-output.css`)
- Bootstrap + jQuery (legacy pages)
- Precompilers: `sass`, `lessc` via Node.js

---

## Quick Start

For a complete setup, see SETUP.md. The basics are below.

### Prerequisites
- Python 3.12+
- PostgreSQL 14+
- Node.js LTS + npm
- Optional: Redis (Celery), Elasticsearch 7.x

### Environment (.env)
Create a `.env` in the repo root (example values):

```
SECRET_KEY=change-me
DEBUG=True
DB_NAME=dobsp
DB_USER=root
DB_PASSWORD=123456
DB_HOST=127.0.0.1
DB_PORT=5432
COMPRESS_ENABLED=True
COMPRESS_OFFLINE=False
```

### PostgreSQL (Docker example)
```
docker run --name careerlite-postgres \
  -e POSTGRES_USER=root \
  -e POSTGRES_PASSWORD=123456 \
  -e POSTGRES_DB=dobsp \
  -p 5432:5432 -d postgres:14
```

### Install and Run (Windows PowerShell; macOS/Linux similar)
```
python -m venv .venv
.venv\Scripts\activate
python -m pip install --upgrade pip
pip install -r requirements.txt

# Frontend
npm install
npm install -g sass less
npm run build

# Django
.venv\Scripts\python.exe manage.py migrate
.venv\Scripts\python.exe manage.py createsuperuser
.venv\Scripts\python.exe manage.py runserver
```

Access:
- App: http://127.0.0.1:8000/
- Admin: http://127.0.0.1:8000/admin/

---

## New Features In This Fork

### Skill Verification (MCQs)
- When a candidate adds a skill, they can verify it by answering 5 MCQs.
- Time limits: 20 seconds for easy, 30 seconds for tough.
- URL: `/candidate/skill/verify/<skill_id>/` (`candidate:verify_skill`).

### Trust Score (Transparent)
- Combines Assessment Accuracy, Recruiter Rating (with a confidence factor when data is sparse), and Verification Recency.
- Default formula: `0.4*Accuracy + 0.4*AdjRecruiter + 0.2*Recency` (or `0.7*Accuracy + 0.3*Recency` if no rating).

### TF‑IDF + Cosine Recommender
- Pure‑Python TF‑IDF vectorization + cosine similarity (no external ML libs).
- Final score: `cosine_similarity × trust_score`.
- Endpoint: `/candidate/recommendations/` returns JSON top internships.
- Candidate Dashboard shows a “Recommended Internships” card fetching this data.

### Branding & UI
- Project rebranded to CareerLite (logo, titles, footer).
- Dev CSS fallbacks so the site stays styled if precompilers are not installed.

---

## Teammates: Get The Latest And Run

1) Pull latest code
- `git checkout main`
- `git pull --ff-only`

2) Python deps
- Windows: `.venv\Scripts\activate`  |  Unix: `source .venv/bin/activate`
- `pip install -r requirements.txt`

3) Node and CSS tooling
- `npm install`
- `npm install -g sass less`
- `npm run build`

4) Database & migrations
- Ensure PostgreSQL is running
- `.venv\Scripts\python.exe manage.py migrate`

5) Run
- `.venv\Scripts\python.exe manage.py runserver`

Optional services
- Celery + Redis for background tasks (emails, jobs). Registration is resilient without them in dev.
- Elasticsearch for legacy search pages.

Environment flags
- `COMPRESS_ENABLED=True` uses `sass`/`lessc` for SCSS/LESS in templates.
- `COMPRESS_OFFLINE=False` recommended in dev (avoid template scan).

Skill verification quick test
- Add a skill on the Candidate Dashboard, then open the verification link (or `/candidate/skill/verify/<skill_id>/`).

Recommendations quick test
- Visit `/candidate/recommendations/` (JSON) or check the “Recommended Internships” card on the dashboard.

---

## License

MIT License. See LICENSE.

