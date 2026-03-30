# Presets

## Presets (examiner only)

### GET /api/presets/
Returns all presets with nested topics.
```json
[
  {
    "id": 1,
    "name": "Standard IELTS Set A",
    "part_1": [{ "id": 1, "name": "Family", "part": 1, "slug": "family" }],
    "part_2": [{ "id": 5, "name": "Describe a place", "part": 2, "slug": "describe-a-place" }],
    "part_3": [{ "id": 9, "name": "Urban development", "part": 3, "slug": "urban-development" }],
    "created_at": "2024-01-01T00:00:00Z"
  }
]
```

### POST /api/presets/
```json
// Request
{
  "name": "My Preset",
  "part_1": [1, 2],   // topic IDs (must be Part 1 topics)
  "part_2": [5],       // topic IDs (must be Part 2 topics)
  "part_3": [9, 10]    // topic IDs (must be Part 3 topics)
}
// Response 201 — same shape as GET single preset
```

Errors:
- `403` — `"Only examiners can create presets."`
- `400` — Topic ID belongs to the wrong part (e.g., a Part 2 topic supplied in `part_1`)
