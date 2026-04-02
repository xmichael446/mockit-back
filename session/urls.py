from django.urls import path

from .views import (
    AcceptInviteView,
    AnswerStartView,
    AskFollowUpView,
    AskQuestionView,
    AvailableQuestionsView,
    CancelSessionView,
    CreateShareView,
    EndFollowUpView,
    EndQuestionView,
    EndSessionPartView,
    EndSessionView,
    JoinSessionView,
    MockPresetDeleteView,
    MockPresetListCreateView,
    NoteDeleteView,
    NoteListCreateView,
    ReleaseResultView,
    SessionDetailView,
    SessionListCreateView,
    SessionPartView,
    SessionQuestionListView,
    SessionRecordingView,
    SessionResultView,
    SharedSessionDetailView,
    StartSessionView,
)

urlpatterns = [
    # ── Presets ──────────────────────────────────────────────────────────────
    path("presets/", MockPresetListCreateView.as_view(), name="preset-list-create"),
    path("presets/<int:pk>/", MockPresetDeleteView.as_view(), name="preset-delete"),

    # ── Sessions (core) ───────────────────────────────────────────────────────
    path("sessions/", SessionListCreateView.as_view(), name="session-list-create"),
    # Note: literal paths must precede <int:pk>/ to avoid routing conflicts
    path("sessions/accept-invite/", AcceptInviteView.as_view(), name="session-accept-invite"),
    path("sessions/shared/<str:share_token>/", SharedSessionDetailView.as_view(), name="session-shared-detail"),
    path("sessions/<int:pk>/", SessionDetailView.as_view(), name="session-detail"),
    path("sessions/<int:pk>/start/", StartSessionView.as_view(), name="session-start"),
    path("sessions/<int:pk>/join/", JoinSessionView.as_view(), name="session-join"),
    path("sessions/<int:pk>/end/", EndSessionView.as_view(), name="session-end"),

    # ── Parts ─────────────────────────────────────────────────────────────────
    path("sessions/<int:pk>/parts/", SessionPartView.as_view(), name="session-parts"),
    path("sessions/<int:pk>/parts/<int:part_num>/end/", EndSessionPartView.as_view(), name="session-part-end"),

    # ── Questions (per part) ──────────────────────────────────────────────────
    path("sessions/<int:pk>/parts/<int:part_num>/available-questions/", AvailableQuestionsView.as_view(), name="session-available-questions"),
    path("sessions/<int:pk>/parts/<int:part_num>/ask/", AskQuestionView.as_view(), name="session-ask-question"),
    path("sessions/<int:pk>/parts/<int:part_num>/questions/", SessionQuestionListView.as_view(), name="session-questions"),

    # ── Session question actions ──────────────────────────────────────────────
    path("sessions/<int:pk>/session-questions/<int:sq_id>/answer-start/", AnswerStartView.as_view(), name="session-question-answer-start"),
    path("sessions/<int:pk>/session-questions/<int:sq_id>/end/", EndQuestionView.as_view(), name="session-question-end"),

    # ── Follow-ups ────────────────────────────────────────────────────────────
    path("sessions/<int:pk>/session-questions/<int:sq_id>/follow-ups/", AskFollowUpView.as_view(), name="session-ask-followup"),
    path("sessions/<int:pk>/session-follow-ups/<int:sf_id>/end/", EndFollowUpView.as_view(), name="session-followup-end"),

    # ── Notes ─────────────────────────────────────────────────────────────────
    path("sessions/<int:pk>/session-questions/<int:sq_id>/notes/", NoteListCreateView.as_view(), name="session-notes"),
    path("sessions/<int:pk>/notes/<int:note_id>/", NoteDeleteView.as_view(), name="session-note-delete"),

    # ── Results ───────────────────────────────────────────────────────────────
    path("sessions/<int:pk>/result/", SessionResultView.as_view(), name="session-result"),
    path("sessions/<int:pk>/result/release/", ReleaseResultView.as_view(), name="session-result-release"),

    # ── Recording ─────────────────────────────────────────────────────────────
    path("sessions/<int:pk>/recording/", SessionRecordingView.as_view(), name="session-recording"),

    # ── Share ─────────────────────────────────────────────────────────────────
    path("sessions/<int:pk>/share/", CreateShareView.as_view(), name="session-share"),

    # ── Cancel ────────────────────────────────────────────────────────────────
    path("sessions/<int:pk>/cancel/", CancelSessionView.as_view(), name="session-cancel"),
]
