# Results

### GET /api/sessions/<id>/result/
Examiner: always accessible.
Candidate: only accessible after result is released.
```json
{
  "id": 1,
  "overall_band": "7.0",
  "is_released": false,
  "released_at": null,
  "scores": [
    { "id": 1, "criterion": 1, "criterion_label": "Fluency and Coherence", "band": 7, "feedback": "..." },
    { "id": 2, "criterion": 2, "criterion_label": "Grammatical Range & Accuracy", "band": 6, "feedback": "..." },
    { "id": 3, "criterion": 3, "criterion_label": "Lexical Resource", "band": 7, "feedback": "..." },
    { "id": 4, "criterion": 4, "criterion_label": "Pronunciation", "band": 7, "feedback": "..." }
  ]
}
```
Criterion values: 1=FC, 2=GRA, 3=LR, 4=PR

Errors:
- `404` — `"No result yet."`
- `403` — `"You are not a participant."` | `"Result has not been released yet."` (candidate only)

### POST /api/sessions/<id>/result/
Examiner only. Session must be COMPLETED. Submit/update scores.
Calling this multiple times is idempotent — updates existing scores.
```json
// Request
{
  "scores": [
    { "criterion": 1, "band": 7, "feedback": "Speaks fluently with some hesitation." },
    { "criterion": 2, "band": 6, "feedback": "Good range but some errors." },
    { "criterion": 3, "band": 7, "feedback": "Wide vocabulary." },
    { "criterion": 4, "band": 7, "feedback": "Clear pronunciation." }
  ]
}
// Response 201 — result object (see GET)
// overall_band is auto-computed as avg of 4 bands rounded to nearest 0.5
```

Errors:
- `403` — `"You are not a participant."` | `"Only the examiner can submit results."`
- `400` — Validation errors (invalid criterion value, band out of range 1–9, duplicate criterion entries)

### POST /api/sessions/<id>/result/release/
Examiner only. Makes the result visible to the candidate.
```json
// Response 200 — result object with is_released=true
// Broadcasts WS event: result.released
```

Errors:
- `403` — `"Only the examiner can release results."`
- `400` — `"No result to release. Submit scores first."` | `"Cannot release: missing scores for ..."`
