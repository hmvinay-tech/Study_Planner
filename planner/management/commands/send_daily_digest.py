from datetime import timedelta

from django.core.management.base import BaseCommand, CommandError
from django.core.mail import send_mail
from django.utils import timezone

from planner.models import NotificationPreference, StudyTopic


class Command(BaseCommand):
    help = 'Send each eligible user one daily study reminder digest.'

    def handle(self, *args, **options):
        now = timezone.localtime()
        today = timezone.localdate()
        due_time = now.time().replace(tzinfo=None)
        preferences = NotificationPreference.objects.filter(
            email_enabled=True,
            email_frequency='daily',
            daily_digest_time__lte=due_time,
        ).exclude(last_digest_sent_on=today).select_related('user')

        sent_count = 0
        failed_users = []
        for preference in preferences:
            if not preference.user.email:
                continue

            topics = StudyTopic.objects.filter(user=preference.user, completed=False)
            sections = []
            if preference.notify_on_due:
                cutoff = today + timedelta(days=preference.remind_before_days)
                due_topics = topics.filter(exam_date__gte=today, exam_date__lte=cutoff).order_by('exam_date')
                if due_topics.exists():
                    sections.append('Coming up:\n' + '\n'.join(
                        f'- {topic.subject}: {topic.topic} (exam {topic.exam_date:%d %b %Y})'
                        for topic in due_topics
                    ))
            if preference.notify_overdue:
                overdue_topics = topics.filter(exam_date__lt=today).order_by('exam_date')
                if overdue_topics.exists():
                    sections.append('Overdue:\n' + '\n'.join(
                        f'- {topic.subject}: {topic.topic} (exam {topic.exam_date:%d %b %Y})'
                        for topic in overdue_topics
                    ))

            if sections:
                try:
                    delivered = send_mail(
                        'Your Study Planner daily digest',
                        'Here is your study reminder for today.\n\n' + '\n\n'.join(sections),
                        None,
                        [preference.user.email],
                        fail_silently=False,
                    )
                except Exception as exc:
                    failed_users.append(f'{preference.user.username}: {exc}')
                    continue
                if not delivered:
                    failed_users.append(f'{preference.user.username}: email backend did not deliver the message')
                    continue
                sent_count += 1

            # Mark empty digests too, so this scheduled command does not repeat work all day.
            preference.last_digest_sent_on = today
            preference.save(update_fields=['last_digest_sent_on'])

        self.stdout.write(self.style.SUCCESS(f'Sent {sent_count} daily digest(s).'))
        if failed_users:
            raise CommandError('Some digests could not be sent: ' + '; '.join(failed_users))
