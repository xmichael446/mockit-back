from rest_framework import serializers

from .models import FollowUpQuestion, Question, Topic


class FollowUpQuestionSerializer(serializers.ModelSerializer):
    class Meta:
        model = FollowUpQuestion
        fields = ("id", "text")


class QuestionSerializer(serializers.ModelSerializer):
    """Question with follow-ups — used nested inside TopicSerializer."""
    follow_ups = FollowUpQuestionSerializer(many=True, read_only=True)

    class Meta:
        model = Question
        fields = ("id", "text", "difficulty", "bullet_points", "follow_ups")


class TopicSerializer(serializers.ModelSerializer):
    """Compact topic — used inside QuestionDetailSerializer and QuestionSetSerializer."""
    class Meta:
        model = Topic
        fields = ("id", "topic_number", "name", "part", "slug")


class TopicWithQuestionsSerializer(serializers.ModelSerializer):
    """Full topic with all nested questions and their follow-ups."""
    questions = QuestionSerializer(many=True, read_only=True)

    class Meta:
        model = Topic
        fields = ("id", "topic_number", "name", "part", "slug", "questions")


class QuestionDetailSerializer(serializers.ModelSerializer):
    """Full question for the center panel — includes topic context and follow-ups."""
    topic = TopicSerializer(read_only=True)
    follow_ups = FollowUpQuestionSerializer(many=True, read_only=True)

    class Meta:
        model = Question
        fields = ("id", "topic", "text", "difficulty", "bullet_points", "follow_ups")

