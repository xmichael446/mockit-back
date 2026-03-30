# Typical Flows

### Registration flow (Examiner)
1. `POST /api/auth/register/` → user created, verification email sent
2. User clicks link in email → frontend reads `?verify=` from URL
3. `POST /api/auth/verify-email/` `{"token": "<uuid>"}` → returns auth token (user is now logged in)
4. If link expired: `POST /api/auth/resend-verification/` `{"email": "..."}` → new email sent

### Registration flow (Candidate)
1. `POST /api/auth/register/` → token returned immediately, no email verification required

### Guest flow (no registration)
1. Examiner shares `invite_token` out-of-band
2. `POST /api/auth/guest-join/` `{"invite_token": "...", "first_name": "Alice"}` → ephemeral user created, token returned
3. Continue as candidate from step 3 of the Candidate flow below

### Examiner flow
1. `POST /api/auth/login/` → get token
2. `POST /api/presets/` → create preset with topics
3. `POST /api/sessions/` → create session, get `invite_token`
4. Share `invite_token` with candidate out-of-band
5. Connect `ws/session/<id>/?token=...` early — listen for `invite.accepted` to know when candidate is ready
6. `POST /api/sessions/<id>/start/` → get `hms_token`, join 100ms room
7. `POST /api/sessions/<id>/parts/` `{"part": 1}` → start Part 1
8. `GET /api/sessions/<id>/parts/1/available-questions/` → show question list
9. `POST /api/sessions/<id>/parts/1/ask/` `{"question_id": 42}` → ask question (WS fires)
10. `POST /api/sessions/<id>/session-questions/<sq_id>/end/` → stop question
11. Repeat 9–10, optionally ask follow-ups
12. `POST /api/sessions/<id>/parts/1/end/`
13. Repeat for Parts 2 and 3
14. `POST /api/sessions/<id>/end/`
15. `POST /api/sessions/<id>/recording/` (multipart, field `audio_file`) → upload the webm recording
16. `POST /api/sessions/<id>/result/` with all four criterion scores and feedback
17. `POST /api/sessions/<id>/result/release/` → triggers `result.released` WS event to candidate

### Candidate flow
1. `POST /api/auth/login/` → get token
2. `POST /api/sessions/accept-invite/` `{"token": "..."}` → link to session
3. Connect `ws/session/<id>/?token=...` immediately after accepting — listen for `session.started`
4. On `session.started`: `POST /api/sessions/<id>/join/` → get `hms_token`, join 100ms room
5. Listen for `question.asked` → display the question
6. `POST /api/sessions/<id>/session-questions/<sq_id>/answer-start/` when ready to speak
7. Listen for `question.ended`, `followup.asked`, etc.
8. On `session.ended`: show "waiting for examiner feedback" screen
9. On `result.released` WS event: display scores and feedback immediately (full result is included in the event — no extra GET needed)
10. `GET /api/sessions/<id>/recording/` → retrieve the recording URL and timecodes to review the session
