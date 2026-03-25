from django.db.models import QuerySet
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.views import APIView

from .models import Question, Topic
from .serializers import (
    QuestionDetailSerializer,
    TopicWithQuestionsSerializer,
)

DEFAULT_LIMIT = 10
MAX_LIMIT = 200


def _paginate(qs: QuerySet, request: Request) -> tuple[QuerySet, int, int, int]:
    """Reads limit/offset from query params and slices the queryset."""
    total = qs.count()

    try:
        limit = max(1, min(int(request.query_params.get("limit", DEFAULT_LIMIT)), MAX_LIMIT))
    except (ValueError, TypeError):
        limit = DEFAULT_LIMIT

    try:
        offset = max(0, int(request.query_params.get("offset", 0)))
    except (ValueError, TypeError):
        offset = 0

    return qs[offset: offset + limit], total, limit, offset


class TopicListView(APIView):
    """
    GET /api/topics/
    Returns a paginated list of topics, each with their questions and follow-ups nested.
    Used to populate the question bank panel on initial load and after filtering/searching.

    Without params, returns the first 10 topics as an initial sample.

    Query params:
        part   (int):    filter by IELTS part (1, 2, 3)
        search (str):    case-insensitive match on topic name
        limit  (int):    topics per page (default 10, max 200)
        offset (int):    topics to skip (default 0)
    """

    def get(self, request: Request) -> Response:
        qs = (
            Topic.objects
            .prefetch_related("questions__follow_ups")
            .order_by("topic_number")
        )

        part = request.query_params.get("part")
        if part:
            qs = qs.filter(part=part)

        search = request.query_params.get("search")
        if search:
            qs = qs.filter(name__icontains=search)

        page, total, limit, offset = _paginate(qs, request)

        return Response({
            "count": total,
            "limit": limit,
            "offset": offset,
            "results": TopicWithQuestionsSerializer(page, many=True).data,
        })


class TopicDetailView(APIView):
    """
    GET /api/topics/<pk>/
    Returns a single topic with all its questions and follow-ups.
    """

    def get(self, request: Request, pk: int) -> Response:
        try:
            topic = (
                Topic.objects
                .prefetch_related("questions__follow_ups")
                .get(pk=pk)
            )
        except Topic.DoesNotExist:
            return Response({"detail": "Not found."}, status=404)

        return Response(TopicWithQuestionsSerializer(topic).data)


class QuestionDetailView(APIView):
    """
    GET /api/questions/<pk>/
    Returns the full question detail for the center panel, including topic context and follow-ups.
    """

    def get(self, request: Request, pk: int) -> Response:
        try:
            question = (
                Question.objects
                .select_related("topic")
                .prefetch_related("follow_ups")
                .get(pk=pk)
            )
        except Question.DoesNotExist:
            return Response({"detail": "Not found."}, status=404)

        return Response(QuestionDetailSerializer(question).data)