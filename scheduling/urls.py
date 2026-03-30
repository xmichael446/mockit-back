from django.urls import path

from .views import (
    AcceptRequestView,
    AvailabilitySlotDetailView,
    AvailabilitySlotListCreateView,
    BlockedDateDetailView,
    BlockedDateListCreateView,
    CancelRequestView,
    ExaminerAvailableSlotsView,
    ExaminerIsAvailableView,
    RejectRequestView,
    SessionRequestListCreateView,
)

urlpatterns = [
    path("availability/", AvailabilitySlotListCreateView.as_view(), name="availability-list-create"),
    path("availability/<int:pk>/", AvailabilitySlotDetailView.as_view(), name="availability-detail"),
    path("blocked-dates/", BlockedDateListCreateView.as_view(), name="blocked-date-list-create"),
    path("blocked-dates/<int:pk>/", BlockedDateDetailView.as_view(), name="blocked-date-detail"),
    path("examiners/<int:pk>/available-slots/", ExaminerAvailableSlotsView.as_view(), name="examiner-available-slots"),
    path("examiners/<int:pk>/is-available/", ExaminerIsAvailableView.as_view(), name="examiner-is-available"),
    path("requests/", SessionRequestListCreateView.as_view(), name="session-request-list-create"),
    path("requests/<int:pk>/accept/", AcceptRequestView.as_view(), name="session-request-accept"),
    path("requests/<int:pk>/reject/", RejectRequestView.as_view(), name="session-request-reject"),
    path("requests/<int:pk>/cancel/", CancelRequestView.as_view(), name="session-request-cancel"),
]
