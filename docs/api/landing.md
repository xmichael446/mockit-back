# Landing Page Stats

Public aggregate counts for the marketing landing page. No authentication required.

### GET /api/landing/
**Public -- no authentication required.**

Returns three integer counts summarising platform activity and question-bank coverage.

```json
// Response 200
{
  "sessions_completed": 142,
  "questions_in_bank": 317,
  "topics_covered": 48
}
```

Field definitions:
- `sessions_completed` -- count of `IELTSMockSession` records with status `COMPLETED` (i.e. mocks that ran end-to-end).
- `questions_in_bank` -- total number of `Question` rows in the question bank.
- `topics_covered` -- total number of `Topic` rows in the question bank.

Notes:
- Not paginated -- response is a flat object, not a list.
- No filters or query parameters accepted.
- Response is computed live on every request (no caching in this version).
