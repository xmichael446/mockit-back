# MockIT — Landing Page Brief

## What is MockIT?

MockIT is a web platform for conducting **live IELTS Speaking mock tests** over video call. It connects IELTS examiners with candidates in a structured, professional session — handling everything from question delivery to scoring and feedback, all in one place.

The IELTS Speaking test is a face-to-face interview conducted by a certified examiner. It has three parts and lasts 11–14 minutes. MockIT digitises the entire experience: the examiner runs the session from a structured dashboard, the candidate joins via a private video link, and both receive a full record of the session afterward.

---

## The Problem It Solves

Preparing for the IELTS Speaking test is hard to do alone. Candidates need:
- A real human to speak with (not a chatbot)
- An examiner who follows the official three-part format
- Structured, criterion-based scoring (not vague "you did okay" feedback)
- A recording of the session to review afterward

Examiners doing mock tests manually have no tooling — they juggle question notes, a timer, a score sheet, and a video call simultaneously. MockIT gives them a proper workspace.

---

## Who It's For

**Primary user — IELTS Examiner / Tutor**
- Conducts one-on-one mock speaking tests
- Needs a structured question bank, live note-taking, and a scoring panel
- Wants to deliver professional, band-score feedback to candidates

**Secondary user — IELTS Candidate**
- Preparing for the IELTS Speaking exam
- Joins via invite link — no prior account required (can join as a guest)
- Receives their band scores (FC, GRA, LR, PR) and written feedback after the session

---

## How It Works (User Flow)

### Examiner
1. Creates an account and logs in
2. Builds a **session preset** — selects topics from the question bank for Parts 1, 2, and 3
3. Schedules a session and shares an **invite link** with the candidate
4. Starts the session when the candidate joins — both enter a live video call
5. Navigates questions from a structured panel during the call, takes live notes, asks follow-ups
6. Ends the session, then scores the candidate on four IELTS criteria (1–9 bands each)
7. Releases the results — the candidate receives their band scores and feedback

### Candidate
1. Receives an invite link from the examiner
2. Clicks the link — can join as a guest (just a name) or create an account to save session history
3. Waits in a lobby until the examiner starts the session
4. Participates in the video interview across three parts
5. After the session ends, waits for the examiner to release scores
6. Receives detailed band scores and written feedback for each IELTS criterion

---

## Core Features

### Live Video Session
- Real-time video call using 100ms (HMS SDK)
- Three-column examiner layout: question navigator | video feed | live scoring panel
- Candidate sees a clean fullscreen video view with the current question displayed as an overlay
- Session controls always accessible at the bottom of the video

### Question Bank & Presets
- Structured question bank organised by IELTS part (1, 2, 3) and topic
- Each question has follow-up questions attached
- Part 2 questions include cue card bullet points
- Examiners build reusable presets from the bank for repeated use

### Live Session Controls (Examiner)
- Ask a question → marks it as asked, timestamps it, broadcasts it to the candidate's screen
- Part 2: separate "Start speaking" button to track prep time vs. speaking time
- Ask follow-up questions on demand
- Add private notes per question during the session
- End question / end part / end session buttons

### Scoring & Feedback
- Scores on four IELTS criteria: Fluency & Coherence, Grammatical Range & Accuracy, Lexical Resource, Pronunciation
- Each criterion scored 1–9 with written feedback
- Overall band auto-calculated using the official IELTS rounding rule (nearest 0.5, 0.25 rounds down)
- Examiner releases results when ready — candidate is notified in real time via WebSocket

### Session Recording
- Examiner can record and upload the session audio
- Full timecode map: every part, question, and follow-up is timestamped relative to session start
- Candidate can replay the session aligned to the question timeline

### Candidate Onboarding
- Candidates join via invite link — no friction
- Option to join as a **guest** (first name only, no account) or register/login to save history
- Guest accounts are immediately active with no email verification required

### Examiner Account (Email Verification)
- Examiners register with username, password, name, and email
- Email verification required before first login (link sent via Resend)
- Resend verification email option built into the login flow

---

## IELTS Speaking Structure (Context for Design)

| Part | Format | Typical Duration |
|------|--------|-----------------|
| Part 1 | Examiner asks questions on familiar topics (home, work, hobbies) | 4–5 min |
| Part 2 | Candidate speaks on a cue card topic (1 min prep, 1–2 min talk) | 3–4 min |
| Part 3 | Two-way discussion on abstract themes related to Part 2 | 4–5 min |

**Scoring Criteria:**
- **FC** — Fluency and Coherence
- **GRA** — Grammatical Range & Accuracy
- **LR** — Lexical Resource
- **PR** — Pronunciation

---

## Tech Stack (for context, not for display)

- Frontend: Svelte 5 + TypeScript + Vite (SPA)
- Backend: Django 5.2 + Django REST Framework
- Database: PostgreSQL
- Video: 100ms (HMS) SDK
- Real-time events: WebSockets (Django Channels)
- Email: Resend

---

## Tone & Positioning

- **Professional but approachable** — this is a serious test prep tool, not a toy, but it shouldn't feel clinical or corporate
- **Trust through structure** — the platform mirrors the real IELTS exam format exactly, which is a core selling point
- **Built for examiners first** — the examiner's workflow is the product; candidates get a clean, anxiety-reducing experience as a result
- Positioned as a **purpose-built tool**, not a generic video call with a scoresheet bolted on

---

## Key Differentiators to Highlight

1. **Structured exactly like the real IELTS Speaking test** — three parts, official scoring criteria, official band calculation
2. **Examiners have a real workspace** — question bank, live notes, per-question timestamps, scoring panel, all in one screen
3. **Candidates don't need an account** — join as a guest in seconds with just a name
4. **Full session record** — audio recording with timecoded question markers so candidates can review exactly where they struggled
5. **Real-time scoring delivery** — results pushed to the candidate the moment the examiner releases them

---

## Suggested Landing Page Sections

1. **Hero** — headline, one-line description, two CTAs: "I'm an Examiner" (sign up) and "I have an invite" (join flow)
2. **Problem statement** — why mock tests matter, why doing them without tooling is painful
3. **How it works** — visual three-step flow, separate tracks for examiner and candidate
4. **Feature highlights** — live video + question navigator, scoring panel, session recording, instant results
5. **IELTS format explainer** — brief section showing the three-part structure and four scoring criteria, signals legitimacy
6. **Social proof / trust signal** — (placeholder for testimonials or stats)
7. **CTA footer** — examiner signup, candidate join-with-link
