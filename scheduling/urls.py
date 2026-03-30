from django.urls import path

from .views import (
    AvailabilitySlotDetailView,
    AvailabilitySlotListCreateView,
    BlockedDateDetailView,
    BlockedDateListCreateView,
    ExaminerAvailableSlotsView,
    ExaminerIsAvailableView,
)

urlpatterns = [
    path("availability/", AvailabilitySlotListCreateView.as_view(), name="availability-list-create"),
    path("availability/<int:pk>/", AvailabilitySlotDetailView.as_view(), name="availability-detail"),
    path("blocked-dates/", BlockedDateListCreateView.as_view(), name="blocked-date-list-create"),
    path("blocked-dates/<int:pk>/", BlockedDateDetailView.as_view(), name="blocked-date-detail"),
    path("examiners/<int:pk>/available-slots/", ExaminerAvailableSlotsView.as_view(), name="examiner-available-slots"),
    path("examiners/<int:pk>/is-available/", ExaminerIsAvailableView.as_view(), name="examiner-is-available"),
]
