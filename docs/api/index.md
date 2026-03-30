# MockIT API Reference

All HTTP endpoints are prefixed with `/api/`. Authentication uses DRF Token auth: `Authorization: Token <token>`.
WebSocket connections authenticate via query-string token: `ws://host/ws/session/<id>/?token=<token>`.

## Sections

| Section | Description |
|---------|-------------|
| [Global Errors](global-errors.md) | Error shapes, rate limits |
| [Authentication](authentication.md) | Register, login, logout, guest join |
| [Presets](presets.md) | Examiner preset CRUD |
| [Sessions](sessions.md) | Session lifecycle |
| [Session Parts](session-parts.md) | Part start/end |
| [Questions](questions.md) | Question asking and tracking |
| [Follow-Ups](follow-ups.md) | Follow-up questions |
| [Notes](notes.md) | Examiner notes |
| [Results](results.md) | Scoring and release |
| [Recording](recording.md) | Audio recording upload/retrieval |
| [Topics](topics.md) | Read-only question bank |
| [WebSocket](websocket.md) | Real-time session events |
| [Typical Flows](typical-flows.md) | End-to-end usage examples |
