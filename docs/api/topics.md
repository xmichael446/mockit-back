# Questions & Topics (read-only reference)

### GET /api/topics/
Query params: `?part=1`, `?search=family`, `?limit=10`, `?offset=0`
```json
{
  "count": 50,
  "next": "...",
  "previous": null,
  "results": [{ "id": 1, "name": "Family", "part": 1, "slug": "family" }]
}
```

### GET /api/topics/<id>/
Returns topic with all questions and follow-ups.

### GET /api/questions/<id>/
Returns question with topic info and follow-ups.
