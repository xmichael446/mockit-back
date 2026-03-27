---
phase: quick
plan: 01
type: execute
wave: 1
depends_on: []
files_modified: [docs/api.md]
autonomous: true
requirements: [QUICK-DOC-01]

must_haves:
  truths:
    - "Every REST endpoint documents all possible error status codes and messages"
    - "Global errors (401, 429) are documented once at the top and referenced throughout"
    - "A frontend developer can handle every error response without reading backend code"
  artifacts:
    - path: "docs/api.md"
      provides: "Complete API reference with error documentation"
      contains: "Errors:"
  key_links: []
---

<objective>
Add comprehensive error response documentation to every endpoint in docs/api.md.

Purpose: Frontend developers need to know every possible error status code and message to build proper error handling. Currently most endpoints only show success responses.
Output: Updated docs/api.md with error blocks on every endpoint.
</objective>

<execution_context>
@~/.claude/get-shit-done/workflows/execute-plan.md
@~/.claude/get-shit-done/templates/summary.md
</execution_context>

<context>
@docs/api.md
@session/views.py
@main/views.py
</context>

<tasks>

<task type="auto">
  <name>Task 1: Add error responses to all API endpoints</name>
  <files>docs/api.md</files>
  <action>
Update docs/api.md to add error response documentation to every endpoint. Follow these rules:

1. ADD a "Global Errors" section right after the opening paragraph (before "## Authentication") documenting errors that apply to all authenticated endpoints:
   - 401 Unauthorized — missing or invalid token (all authenticated endpoints)
   - 429 Too Many Requests — rate limit exceeded. Note specific rate limits: register (10/hr), guest_join (20/hr), accept_invite (20/hr)

2. ADD a new endpoint section for `POST /api/auth/guest-join/` which is currently undocumented. Insert it in the Authentication section after `GET /api/auth/me/`. Document it fully:
   - Auth: None (public endpoint)
   - Request body: `{"invite_token": "<string>", "first_name": "<string> (optional)"}`
   - Success 201: `{"token": "<drf-token>", "user": {id, username, first_name, last_name, role, is_guest}, "session_id": <int>}`
   - Rate limit: 20/hr (throttle_scope: guest_join)
   - Description: Join a session as an ephemeral guest candidate without registration. Creates a throwaway user with is_guest=True scoped to the session. The returned token works for both REST and WebSocket.

3. For EACH endpoint, add an "Errors:" block after the success response showing all possible error codes and their exact messages. Use this format:
   ```
   Errors:
   - `400` — `"Invalid credentials."` | `"Account is disabled."`
   - `403` — `"Only examiners can create presets."`
   ```
   Use pipe `|` to separate multiple messages for the same status code.

4. Specific error responses to document per endpoint (use EXACT messages from the codebase):

   **POST /api/auth/register/** — 400: validation errors (username exists, password too short, missing fields, invalid role)

   **POST /api/auth/login/** — 400: "Invalid credentials." | "Account is disabled."

   **POST /api/auth/verify-email/** — already has errors documented, keep as-is

   **POST /api/auth/guest-join/** — 400: "Invalid invite token." | "Session is not accepting guests (status: ...)." | "This invite has already been accepted." | "This invite has expired."

   **POST /api/presets/** — 403: "Only examiners can create presets." | 400: part topic wrong-part validation errors

   **POST /api/sessions/** — 403: "Only examiners can create sessions." | "Session limit reached. You can have at most N sessions." | 400: "scheduled_at must be in the future."

   **GET /api/sessions/id/** — 404: "Not found." | 403: "You are not a participant of this session."

   **POST /api/sessions/accept-invite/** — 403: "Only candidates can accept invites." | 400: "Invalid invite token." | "Session is not accepting invitations (status: ...)." | "This invite has already been accepted." | "This invite has expired."

   **POST /api/sessions/id/start/** — 403: "Only the session examiner can start the session." | 400: "Cannot start session: no candidate has accepted the invite yet." | "Session cannot be started. Current status: ..." | 502: "Failed to create video room: ..."

   **POST /api/sessions/id/join/** — 403: "You are not a participant of this session." | 400: "Session is not in progress. Current status: ..." | "Video room is not available."

   **POST /api/sessions/id/end/** — 403: "Only the session examiner can end the session." | 400: "Session is not in progress. Current status: ..."

   **POST /api/sessions/id/parts/** — 403: "You are not a participant of this session." | "Only the examiner can start a part." | 400: "Session is not in progress. Current status: ..." | "part must be 1, 2, or 3." | "Part N has already been started."

   **POST /api/sessions/id/parts/part_num/end/** — 404: "Part N has not been started." | 403: "Only the examiner can end a part." | 400: "Session is not in progress. Current status: ..." | "Part N has already ended."

   **GET /api/sessions/id/parts/part_num/available-questions/** — 403: "Examiner only." | 400: "This session has no preset." | "part_num must be 1, 2, or 3."

   **POST /api/sessions/id/parts/part_num/ask/** — 404: "Question not found." | 403: "Only the examiner can ask questions." | 400: "Session is not in progress..." | "Part N has not been started yet." | "question_id is required." | "This question does not belong to the preset topics for this part." | "This question has already been asked in this part."

   **POST answer-start/** — 404: "Session question not found." | 403: "Only the candidate can signal answer start." | 400: "Session is not in progress..." | "Question has not been asked yet." | "Answer has already been started."

   **POST session-questions/end/** — 404: "Session question not found." | 403: "Only the examiner can end a question." | 400: "Session is not in progress..." | "Question has not been asked yet." | "Question has already ended."

   **POST follow-ups/** — 404: "Session question not found." | "Follow-up not found or does not belong to this question." | 403: "Only the examiner can ask follow-ups." | 400: "Session is not in progress..." | "follow_up_id is required."

   **POST session-follow-ups/end/** — 404: "Session follow-up not found." | 403: "Only the examiner can end follow-ups." | 400: "Session is not in progress..." | "Follow-up has already ended."

   **GET/POST notes/** — 404: "Session question not found." | 403: "Examiner only." | 400 (POST): "content is required." | "content must be 1000 characters or fewer."

   **DELETE notes/** — 404: "Note not found." | 403: "Examiner only."

   **GET result/** — 404: "No result yet." | 403: "You are not a participant." | "Result has not been released yet."

   **POST result/** — 403: "You are not a participant." | "Only the examiner can submit results." | 400: validation errors (invalid criterion, band out of range, duplicate criteria)

   **POST result/release/** — 403: "Only the examiner can release results." | 400: "No result to release. Submit scores first." | "Cannot release: missing scores for ..."

   **POST recording/** — already has partial errors, expand to include: 404: "Not found." | 403: "You are not a participant of this session." | "Only the examiner can upload recordings." | 400: "A recording already exists for this session." | "audio_file is required." | "recording_started_at must be a valid ISO 8601 datetime string."

   **GET recording/** — 404: "No recording found for this session." | 403: "You are not a participant of this session."

5. PRESERVE all existing content (success responses, examples, WS events, typical flows). Only ADD error blocks and the new guest-join section.

6. Keep the existing formatting style. Error blocks should go right after the success response code block for each endpoint.
  </action>
  <verify>
    <automated>[ $(grep -c "Errors:" docs/api.md) -ge 27 ] && echo "PASS: 27+ error blocks found" || echo "FAIL: fewer than 27 error blocks"</automated>
  </verify>
  <done>Every REST endpoint in docs/api.md has an Errors: block listing all possible error status codes and their exact messages. The Global Errors section exists at the top. POST /api/auth/guest-join/ is fully documented as a new section. A frontend developer can implement complete error handling from the docs alone.</done>
</task>

</tasks>

<verification>
- Count of "Errors:" blocks should be >= 27 (one per endpoint plus global section)
- POST /api/auth/guest-join/ section exists with auth, request body, success response, and errors
- All 401, 403, 400, 404, 502 error codes appear where applicable
- Existing success response documentation is preserved unchanged
- File renders correctly as Markdown
</verification>

<success_criteria>
- Every REST endpoint has documented error responses
- Error messages match the exact strings from the codebase
- Global errors (401, 429) documented once at the top
- POST /api/auth/guest-join/ fully documented (was previously missing)
- No existing content removed or altered
</success_criteria>

<output>
After completion, create `.planning/quick/260327-qez-update-the-api-docs-to-include-all-the-p/260327-qez-SUMMARY.md`
</output>
