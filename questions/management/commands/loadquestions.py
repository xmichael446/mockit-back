import json
import os
from django.core.management.base import BaseCommand
from questions.models import Topic, Question  # Change 'your_app' to your app's name

class Command(BaseCommand):
    help = 'Loads IELTS speaking questions from a nested JSON file into the database'

    def add_arguments(self, parser):
        # Allows you to pass the file path as an argument in the terminal
        parser.add_argument('json_file', type=str, help='Path to the ielts_data.json file')

    def handle(self, *args, **options):
        file_path = options['json_file']

        if not os.path.exists(file_path):
            self.stderr.write(self.style.ERROR(f"File not found: {file_path}"))
            return

        with open(file_path, 'r', encoding='utf-8') as f:
            try:
                data = json.load(f)
            except json.JSONDecodeError:
                self.stderr.write(self.style.ERROR("Invalid JSON file. Please check the file formatting."))
                return

        topics_created = 0
        questions_created = 0

        for topic_data in data:
            # 1. Create or get the Topic
            # We use slug as the unique identifier to prevent duplicates
            topic, t_created = Topic.objects.get_or_create(
                slug=topic_data['slug'],
                defaults={
                    'name': topic_data['name'],
                    'part': topic_data['part'],
                }
            )

            if t_created:
                topics_created += 1

            # 2. Create or get Questions for this Topic
            for q_data in topic_data['questions']:
                # Ensure the difficulty integer maps safely to your model's 1-4 choices
                # Defaulting Part 1 to Easy(1), Part 2 to Medium(2), Part 3 to Hard(3)
                difficulty_level = min(q_data.get('difficulty', 1), 3)

                # We use the text and topic as unique identifiers for the question
                question, q_created = Question.objects.get_or_create(
                    topic=topic,
                    text=q_data['text'],
                    defaults={
                        'bullet_points': q_data['bullet_points'],
                        'difficulty': difficulty_level
                    }
                )

                if q_created:
                    questions_created += 1

        # Success output
        self.stdout.write(self.style.SUCCESS(
            f'Successfully processed {len(data)} topics!\n'
            f'Database changes: Created {topics_created} new Topics and {questions_created} new Questions.'
        ))
