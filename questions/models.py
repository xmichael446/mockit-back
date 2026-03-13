from django.db import models
from main.models import TimestampedModel


class IELTSSpeakingPart(models.IntegerChoices):
    PART_1 = 1, "Part 1"
    PART_2 = 2, "Part 2"
    PART_3 = 3, "Part 3"


class Topic(TimestampedModel):
    name = models.CharField(max_length=255, unique=True)
    part = models.PositiveSmallIntegerField(choices=IELTSSpeakingPart.choices, default=IELTSSpeakingPart.PART_1, null=True)
    slug = models.SlugField(max_length=255, unique=True)

    def __str__(self):
        return f"{self.get_part_display()} | {self.name}"


class Question(TimestampedModel):
    class Difficulty(models.IntegerChoices):
        EASY = 1, "Easy"
        MEDIUM = 2, "Medium"
        HARD = 3, "Hard"
        EXTRA_HARD = 4, "Extra Hard"

    topic = models.ForeignKey(Topic, on_delete=models.CASCADE, related_name="questions")
    text = models.CharField(max_length=1000)
    bullet_points = models.JSONField(null=True, blank=True)
    difficulty = models.PositiveSmallIntegerField(choices=Difficulty.choices, default=Difficulty.EASY)

    def __str__(self):
        return f"{self.topic} | {self.topic} | {self.get_difficulty_display()}"


class FollowUpQuestion(TimestampedModel):
    question = models.ForeignKey(Question, on_delete=models.CASCADE, related_name="follow_ups")
    text = models.CharField(max_length=1000)

    def __str__(self):
        return f"Follow Up: {self.text}"


class QuestionSet(TimestampedModel):
    name = models.CharField(max_length=255)
    topics = models.ManyToManyField(Topic, related_name="question_sets", blank=True)

    def __str__(self):
        return self.name