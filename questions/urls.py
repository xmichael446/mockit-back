from django.urls import path

from .views import QuestionDetailView, TopicDetailView, TopicListView

urlpatterns = [
    path("topics/", TopicListView.as_view(), name="topic-list"),
    path("topics/<int:pk>/", TopicDetailView.as_view(), name="topic-detail"),
    path("questions/<int:pk>/", QuestionDetailView.as_view(), name="question-detail"),
]
