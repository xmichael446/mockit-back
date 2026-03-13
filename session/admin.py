from django.contrib import admin

from .models import MockPreset


@admin.register(MockPreset)
class MockPresetAdmin(admin.ModelAdmin):
    list_display = ("name", "part_1_count", "part_2_count", "part_3_count", "created_at")
    search_fields = ("name",)
    autocomplete_fields = ("part_1", "part_2", "part_3")

    @admin.display(description="Part 1 topics")
    def part_1_count(self, obj):
        return obj.part_1.count()

    @admin.display(description="Part 2 topics")
    def part_2_count(self, obj):
        return obj.part_2.count()

    @admin.display(description="Part 3 topics")
    def part_3_count(self, obj):
        return obj.part_3.count()
