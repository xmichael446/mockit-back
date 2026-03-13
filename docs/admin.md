# Admin Guide

Admin is available at `/admin/`. Login requires a superuser account.

```bash
python manage.py createsuperuser
```

---

## Question Bank

### Adding Topics

Go to **Questions → Topics → Add Topic**.

- **Name** — auto-fills the slug as you type.
- **Part** — scope the topic to Part 1, 2, or 3. Questions inherit their part from their topic.
- Questions can be added inline directly on the Topic page (nested under the topic form). Each question row supports adding follow-up probes as a sub-inline.

### Adding Questions

Two workflows:

**Via Topic page (recommended for bulk entry)**
Open a Topic, scroll to the Questions inline, click **Add another Question**. Add follow-ups in the sub-inline beneath each question row. Click **Show** to expand the "Part 2 Cue Card" section and enter bullet points one per line.

**Via Question page (recommended for editing individual questions)**
Go to **Questions → Questions → Add Question**. Select the topic from a searchable dropdown. The "Part 2 Cue Card" fieldset is collapsed by default — expand it only for Part 2 questions and enter bullet points one per line (each line becomes one element in the stored JSON list).

### Adding Follow-ups

Follow-up questions are added as inline rows under a question. The `order` field is auto-assigned sequentially — just enter the text. Follow-ups added in the same save are numbered after any already-existing ones.

### Question Sets

Go to **Questions → Question Sets → Add Question Set**.

- Select topics via the searchable autocomplete field.
- The `part` field on a question set categorises the set (e.g. a "Part 1 set"), but topics from any part can be included.

---

## Users

Go to **Main → Users**.

- Standard Django user management with an added **Role** field (Examiner / Candidate).
- Password changes, permission groups, and staff/superuser flags work as normal.
- The **Role** field appears in both the add and change forms.

---

## Packages Used in Admin

| Package | Purpose |
|---|---|
| `django-nested-admin` | Nested inline editing (Topic → Question → Follow-up) |
| `django_admin_dracula` | Dark theme |
