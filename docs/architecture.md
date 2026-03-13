# Architecture Overview

MockIT is a Django-based platform for conducting assisted IELTS Speaking mock tests. Examiners run live video sessions with candidates, navigating a question bank, taking notes, and scoring in real time. Candidates receive structured feedback afterward.

## Apps

| App | Responsibility |
|---|---|
| `main` | Custom `User` model (extends `AbstractUser`) |
| `questions` | Question bank — topics, questions, follow-ups, question sets |
| `session` | Mock session lifecycle — scheduling, scoring, feedback |

## Tech Stack

- **Backend**: Django 5.2, Django REST Framework
- **Database**: PostgreSQL
- **Admin**: `django-nested-admin` for nested inline editing
- **Real-time** *(planned)*: Django Channels + WebSockets

---

## Data Model Summary

### `main`

```
User (AbstractUser)
  ├── role: Examiner | Candidate
  ├── created_at, updated_at
  └── (inherits: username, email, first_name, last_name, is_active, password, ...)
```

### `questions`

```
Topic
  ├── name, slug (auto-filled)
  ├── part: Part 1 | Part 2 | Part 3
  └── questions → [Question]

Question
  ├── topic → Topic
  ├── text
  ├── difficulty: Easy | Medium | Hard | Extra Hard
  ├── bullet_points (JSON list, Part 2 cue cards only)
  └── follow_ups → [FollowUpQuestion]

FollowUpQuestion
  ├── question → Question
  └── text

QuestionSet
  ├── name
  ├── part
  └── topics (M2M → Topic)
```

### `session`

```
SessionPreset                          ← reusable session plan
  ├── name, description
  ├── created_by → User
  └── parts → [SessionPresetPart]
      ├── part: Part 1 | Part 2 | Part 3
      └── questions → [SessionPresetQuestion]  (ordered)
          ├── question → Question
          └── order

IELTSMockSession
  ├── examiner → User
  ├── candidate → User
  ├── preset → SessionPreset (nullable, for analytics only)
  ├── status: Scheduled | In Progress | Completed | Cancelled
  ├── invite_token (UUID, unique), invite_expires_at, invite_accepted_at
  ├── video_room_id
  ├── scheduled_at, started_at, ended_at
  ├── duration (computed property)
  └── parts → [SessionPart]

SessionPart
  ├── session → IELTSMockSession
  ├── part: Part 1 | Part 2 | Part 3
  ├── started_at, ended_at
  ├── duration (computed property)
  └── session_questions → [SessionQuestion]

SessionQuestion                        ← one question slot in a live session
  ├── session_part → SessionPart
  ├── question → Question
  ├── order
  ├── asked_at          (examiner pressed "Ask" — null = skipped)
  ├── answer_started_at (candidate starts speaking; after prep for Part 2)
  ├── ended_at          (examiner pressed "Stop")
  ├── was_asked (bool property)
  ├── prep_duration, speaking_duration, total_duration (computed properties)
  ├── notes → [Note]
  └── session_follow_ups → [SessionFollowUp]

SessionFollowUp                        ← created on demand when examiner asks a follow-up
  ├── session_question → SessionQuestion
  ├── follow_up → FollowUpQuestion
  ├── asked_at
  ├── ended_at
  └── duration (computed property)

Note
  ├── session_question → SessionQuestion
  └── content

SessionResult (OneToOne → IELTSMockSession)
  ├── overall_band (Decimal, computed via compute_overall_band())
  ├── is_released, released_at
  └── scores → [CriterionScore]

CriterionScore
  ├── session_result → SessionResult
  ├── criterion: FC | GRA | LR | PR
  ├── band (1–9, validated)
  └── feedback
```

#### Session lifecycle

1. Examiner creates a `SessionPreset` (one-time setup, reusable).
2. A new `IELTSMockSession` is created from the preset. `SessionPart` and `SessionQuestion` rows are pre-populated from the preset with all timestamps null.
3. Session starts → `started_at` set on the session and the active part.
4. Examiner presses **"Ask"** on a question → `asked_at` set on `SessionQuestion`.
5. For **Part 2**: prep timer runs → examiner presses **"Start speaking"** → `answer_started_at` set.
   For **Parts 1 & 3**: `answer_started_at` is set immediately alongside `asked_at`.
6. Examiner presses **"Ask follow-up"** → `SessionFollowUp` created with `asked_at`.
7. Examiner presses **"Stop"** → `ended_at` set on the question or follow-up.
8. Questions with `asked_at=None` at session end = skipped.
9. Session ends → scoring + `SessionResult` created.

---

## IELTS Speaking Structure

| Part | Format | Duration |
|---|---|---|
| Part 1 | Examiner asks questions on familiar topics | 4–5 min |
| Part 2 | Candidate speaks on a cue card topic (1 min prep, 1–2 min talk) | 3–4 min |
| Part 3 | Two-way discussion on abstract themes related to Part 2 | 4–5 min |

## Scoring

Four criteria, each scored 1–9 (whole numbers):

| Code | Criterion |
|---|---|
| FC | Fluency and Coherence |
| GRA | Grammatical Range & Accuracy |
| LR | Lexical Resource |
| PR | Pronunciation |

**Overall Speaking band** = average of 4 criteria, rounded to nearest 0.5 with **0.25 rounding down** (individual skill rule). Implemented in `SessionResult.compute_overall_band()`.

> Note: The overall IELTS test score (across all 4 skills) uses a different rule where 0.25 rounds **up**. `compute_overall_band()` only handles the Speaking band.
