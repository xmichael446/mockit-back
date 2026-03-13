import json

from django import forms
from django.contrib import admin
import nested_admin

from .models import FollowUpQuestion, Question, Topic


# ─── Bullet points: textarea → JSON list ──────────────────────────────────────

class BulletPointsWidget(forms.Textarea):
    def format_value(self, value):
        if isinstance(value, list):
            return '\n'.join(str(v) for v in value)
        if isinstance(value, str):
            try:
                import json as _json
                parsed = _json.loads(value)
                if isinstance(parsed, list):
                    return '\n'.join(str(v) for v in parsed)
            except (json.JSONDecodeError, TypeError):
                pass
        return value or ''


class BulletPointsField(forms.CharField):
    widget = BulletPointsWidget

    def __init__(self, *args, **kwargs):
        kwargs.setdefault('required', False)
        kwargs.setdefault('help_text', 'One bullet point per line (Part 2 cue cards only).')
        super().__init__(*args, **kwargs)

    def clean(self, value):
        value = super().clean(value)
        if not value or not value.strip():
            return None
        lines = [line.strip() for line in value.splitlines() if line.strip()]
        return lines or None


class QuestionForm(forms.ModelForm):
    bullet_points = BulletPointsField()

    class Meta:
        model = Question
        fields = '__all__'


# ─── Inlines ──────────────────────────────────────────────────────────────────

class FollowUpNestedInline(nested_admin.NestedTabularInline):
    model = FollowUpQuestion
    extra = 0
    fields = ('text',)
    verbose_name = 'Follow-up question'
    verbose_name_plural = 'Follow-up questions'


class QuestionNestedInline(nested_admin.NestedStackedInline):
    model = Question
    form = QuestionForm
    extra = 0
    inlines = [FollowUpNestedInline]
    show_change_link = True
    verbose_name = 'Question'
    verbose_name_plural = 'Questions'
    fieldsets = (
        (None, {'fields': ('difficulty', 'text')}),
        ('Part 2 Cue Card', {
            'classes': ('collapse',),
            'fields': ('bullet_points',),
            'description': 'Only fill this in for Part 2 questions.',
        }),
    )


# ─── Topic ────────────────────────────────────────────────────────────────────

@admin.register(Topic)
class TopicAdmin(nested_admin.NestedModelAdmin):
    list_display = ('name', 'part', 'question_count', 'created_at')
    list_filter = ('part',)
    search_fields = ('name',)
    prepopulated_fields = {'slug': ('name',)}
    inlines = [QuestionNestedInline]

    @admin.display(description='Questions')
    def question_count(self, obj):
        return obj.questions.count()


# ─── Question ─────────────────────────────────────────────────────────────────

class FollowUpInline(admin.TabularInline):
    model = FollowUpQuestion
    extra = 2
    fields = ('text',)
    verbose_name = 'Follow-up question'
    verbose_name_plural = 'Follow-up questions'


@admin.register(Question)
class QuestionAdmin(admin.ModelAdmin):
    form = QuestionForm
    list_display = ('topic', 'text_preview', 'difficulty', 'follow_up_count', 'has_bullet_points')
    list_filter = ('difficulty', 'topic__part', 'topic')
    search_fields = ('text', 'topic__name')
    autocomplete_fields = ('topic',)
    inlines = [FollowUpInline]
    fieldsets = (
        (None, {'fields': ('topic', 'difficulty', 'text')}),
        ('Part 2 Cue Card', {
            'classes': ('collapse',),
            'fields': ('bullet_points',),
            'description': 'Only fill this in for Part 2 questions.',
        }),
    )

    @admin.display(description='Question', ordering='text')
    def text_preview(self, obj):
        return obj.text[:90] + '…' if len(obj.text) > 90 else obj.text

    @admin.display(description='Follow-ups')
    def follow_up_count(self, obj):
        n = obj.follow_ups.count()
        return n if n else '—'

    @admin.display(description='Cue card', boolean=True)
    def has_bullet_points(self, obj):
        return bool(obj.bullet_points)
