---
phase: quick
plan: 260327-qsl
type: execute
wave: 1
depends_on: []
files_modified:
  - docs/api.md
autonomous: true
requirements: []
must_haves:
  truths:
    - "Frontend developer can look at docs and know the exact JSON shape for every error status code"
    - "All 3 error response formats (detail object, field validation, list) are documented with examples"
  artifacts:
    - path: "docs/api.md"
      provides: "Error response format documentation in Global Errors section"
      contains: "Error Response Formats"
  key_links: []
---

<objective>
Add error response format documentation to docs/api.md so frontend developers know the JSON shape to expect for each error type, not just the status code and message text.

Purpose: Frontend code needs to parse error responses correctly. DRF has 3 distinct error shapes depending on how the error is raised, and this is not currently documented.
Output: Updated docs/api.md with an "Error Response Formats" subsection in the Global Errors area.
</objective>

<execution_context>
@~/.claude/get-shit-done/workflows/execute-plan.md
@~/.claude/get-shit-done/templates/summary.md
</execution_context>

<context>
@docs/api.md
@session/views.py (for confirming error patterns)
</context>

<tasks>

<task type="auto">
  <name>Task 1: Add error response format documentation to Global Errors section</name>
  <files>docs/api.md</files>
  <action>
Insert a new "### Error Response Formats" subsection inside the Global Errors section, between the existing bullet list (lines 12-17) and the `---` separator (line 19). This subsection documents the 3 JSON shapes that DRF returns:

**Shape 1 — Detail errors** (most 400/403/404/502 responses from views):
Views return `Response({"detail": "..."})` directly.
```json
{"detail": "Only examiners can create presets."}
```
Key: always has a single `"detail"` string field.

**Shape 2 — Field validation errors** (400 from serializer.is_valid(raise_exception=True)):
DRF serializer validation returns field-keyed errors.
```json
{
  "field_name": ["Error message."],
  "other_field": ["Another error."]
}
```
Key: object where each key is a field name and each value is an array of error strings. Also includes `"non_field_errors"` key when the error comes from `validate()` method.

**Shape 3 — List validation errors** (400 from model-level ValidationError):
Model methods raising `ValidationError(...)` produce a flat list.
```json
["Cannot start session: no candidate has accepted the invite yet."]
```
Key: top-level JSON array of error strings.

For each shape, include:
- The JSON example
- When it occurs (which endpoints / what triggers it)
- How to detect it in client code (check if response is object with "detail", object with field keys, or array)

Add a brief note at the top: "This API uses Django REST Framework defaults (no custom exception handler). Errors come in one of three JSON shapes depending on how the error was raised."

Also add a small client-side detection hint:
```
if (typeof body === 'object' && 'detail' in body) → Shape 1
if (Array.isArray(body)) → Shape 3
otherwise → Shape 2 (field validation)
```
  </action>
  <verify>
    <automated>grep -c "Error Response Formats" docs/api.md | grep -q "1" && echo "PASS" || echo "FAIL"</automated>
  </verify>
  <done>docs/api.md contains a clear "Error Response Formats" subsection in the Global Errors area documenting all 3 JSON shapes with examples and detection logic</done>
</task>

</tasks>

<verification>
- `grep "Error Response Formats" docs/api.md` returns a match
- The section appears between the existing Global Errors bullets and the Authentication section
- All 3 shapes are documented with JSON examples
</verification>

<success_criteria>
A frontend developer reading only the Global Errors section of api.md can determine the exact JSON shape for any error response and write client-side parsing logic.
</success_criteria>

<output>
After completion, create `.planning/quick/260327-qsl-include-error-response-format-as-well-in/260327-qsl-SUMMARY.md`
</output>
