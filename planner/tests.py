"""
Study Planner - Test Suite
Run with: pytest planner/tests.py -v
"""
import pytest
from django.test import Client, override_settings
from django.contrib.auth.models import User
from django.core import mail
from django.core.management import call_command
from datetime import date, time, timedelta
from unittest.mock import patch
from django.urls import reverse
from rest_framework.test import APIClient
from rest_framework.authtoken.models import Token
from planner.models import (
    StudyTopic, Tag, StudySession, UserProfile, Achievement, DailyGoal,
    RecurringTopic, NotificationPreference,
)


# ===== Unit Tests =====

@pytest.mark.unit
@pytest.mark.django_db
class TestStudyTopicModel:
    """Test StudyTopic model methods and properties."""

    def test_str_representation(self, user):
        topic = StudyTopic.objects.create(
            user=user, subject='Python', topic='Functions', exam_date='2026-10-15'
        )
        assert str(topic) == 'Python: Functions'

    def test_is_overdue_property(self, user):
        from django.utils import timezone
        from datetime import timedelta
        
        # Overdue topic
        overdue = StudyTopic.objects.create(
            user=user, subject='Python', topic='Overdue', 
            exam_date=timezone.localdate() - timedelta(days=1)
        )
        assert overdue.is_overdue is True
        
        # Not overdue
        future = StudyTopic.objects.create(
            user=user, subject='Python', topic='Future', 
            exam_date=timezone.localdate() + timedelta(days=1)
        )
        assert future.is_overdue is False
        
        # Completed topic should not be overdue
        completed = StudyTopic.objects.create(
            user=user, subject='Python', topic='Completed', 
            exam_date=timezone.localdate() - timedelta(days=1),
            completed=True
        )
        assert completed.is_overdue is False

    def test_priority_css_property(self, user):
        high = StudyTopic.objects.create(user=user, subject='A', topic='H', exam_date='2026-10-15', priority=0)
        medium = StudyTopic.objects.create(user=user, subject='B', topic='M', exam_date='2026-10-15', priority=1)
        low = StudyTopic.objects.create(user=user, subject='C', topic='L', exam_date='2026-10-15', priority=2)
        
        assert high.priority_css == 'high'
        assert medium.priority_css == 'medium'
        assert low.priority_css == 'low'

    def test_priority_label_property(self, user):
        high = StudyTopic.objects.create(user=user, subject='A', topic='H', exam_date='2026-10-15', priority=0)
        assert high.priority_label == 'High'


@pytest.mark.unit
@pytest.mark.django_db
class TestUserProfileModel:
    """Test UserProfile gamification methods."""

    def test_add_xp_and_level_up(self, user):
        profile = UserProfile.objects.get(user=user)
        initial_level = profile.level
        
        # Add enough XP for multiple level ups
        profile.add_xp(500, 'Test XP')
        profile.refresh_from_db()
        
        assert profile.level > initial_level
        assert profile.xp < profile.xp_for_next_level

    def test_update_streak(self, user):
        from django.utils import timezone
        from datetime import timedelta
        
        profile = UserProfile.objects.get(user=user)
        profile.update_streak()
        assert profile.current_streak == 1
        
        # Simulate next day
        profile.last_activity_date = timezone.localdate() - timedelta(days=1)
        profile.save()
        profile.update_streak()
        assert profile.current_streak == 2


@pytest.mark.unit
@pytest.mark.django_db
class TestAchievementModel:
    """Test achievement unlocking logic."""

    def test_achievement_unlock_streak(self, user):
        from planner.models import Achievement, UserAchievement
        from planner.api_views import AchievementViewSet
        
        achievement = Achievement.objects.create(
            code='test_streak',
            name='Test Streak',
            description='Test',
            type='streak',
            rarity='common',
            xp_reward=50,
            condition={'streak_days': 3}
        )
        
        # Create a viewset instance to call the instance method
        viewset = AchievementViewSet()
        
        # Profile with streak < 3
        profile = UserProfile.objects.get(user=user)
        profile.current_streak = 2
        profile.save()
        
        # Should not unlock
        assert not viewset._check_achievement_condition(user, achievement)
        
        # Profile with streak >= 3
        profile.current_streak = 5
        profile.save()
        
        # Should unlock
        assert viewset._check_achievement_condition(user, achievement)


@pytest.mark.unit
@pytest.mark.django_db
class TestStudySessionModel:
    """Test StudySession timer functionality."""

    def test_session_timer(self, user):
        session = StudySession.objects.create(
            user=user, subject='Python', notes='Test session'
        )
        
        assert session.is_active is True
        assert session.duration_minutes == 0
        
        # Stop session
        session.stop()
        session.refresh_from_db()
        
        assert session.is_active is False
        assert session.duration_minutes >= 1

    def test_stopping_session_updates_profile_and_daily_goals_once(self, user):
        from django.utils import timezone

        session = StudySession.objects.create(user=user, subject='Python')
        minutes_goal = DailyGoal.objects.create(
            user=user, date=timezone.localdate(), goal_type='minutes', target=100
        )
        sessions_goal = DailyGoal.objects.create(
            user=user, date=timezone.localdate(), goal_type='sessions', target=3
        )

        session.stop()
        duration = session.duration_minutes
        session.stop()

        profile = UserProfile.objects.get(user=user)
        minutes_goal.refresh_from_db()
        sessions_goal.refresh_from_db()
        assert profile.total_study_minutes == duration
        assert minutes_goal.current == duration
        assert sessions_goal.current == 1


# ===== API Integration Tests =====

@pytest.mark.api
@pytest.mark.django_db
class TestTopicAPI:
    """Test Topic API endpoints."""

    @pytest.fixture
    def api_client(self, user):
        client = APIClient()
        token, _ = Token.objects.get_or_create(user=user)
        client.credentials(HTTP_AUTHORIZATION=f'Token {token.key}')
        return client

    def test_list_topics(self, api_client, user):
        StudyTopic.objects.create(user=user, subject='Python', topic='Test', exam_date='2026-10-15')
        
        response = api_client.get('/api/topics/')
        assert response.status_code == 200
        assert response.data['count'] == 1

    def test_create_topic(self, api_client, user):
        data = {
            'subject': 'Python',
            'topic': 'New Topic',
            'exam_date': '2026-12-01',
            'priority': 1,
            'notes': 'Test notes',
        }
        response = api_client.post('/api/topics/', data, format='json')
        
        assert response.status_code == 201
        assert response.data['subject'] == 'Python'
        assert response.data['topic'] == 'New Topic'
        assert 'notes_markdown' not in response.data

    def test_complete_topic(self, api_client, user):
        topic = StudyTopic.objects.create(user=user, subject='Python', topic='Test', exam_date='2026-10-15')
        
        response = api_client.post(f'/api/topics/{topic.id}/complete/')
        assert response.status_code == 200
        assert response.data['completed'] is True

    def test_topic_stats(self, api_client, user):
        StudyTopic.objects.create(user=user, subject='Python', topic='Test', exam_date='2026-10-15', completed=True)
        StudyTopic.objects.create(user=user, subject='Python', topic='Test2', exam_date='2026-10-15')
        
        response = api_client.get('/api/topics/stats/')
        assert response.status_code == 200
        assert response.data['total'] == 2
        assert response.data['completed'] == 1
        assert response.data['completion_rate'] == 50.0


@pytest.mark.api
@pytest.mark.django_db
class TestSessionAPI:
    """Test Study Session API endpoints."""

    @pytest.fixture
    def api_client(self, user):
        client = APIClient()
        token, _ = Token.objects.get_or_create(user=user)
        client.credentials(HTTP_AUTHORIZATION=f'Token {token.key}')
        return client

    def test_start_session(self, api_client, user):
        topic = StudyTopic.objects.create(user=user, subject='Python', topic='Test', exam_date='2026-10-15')
        
        response = api_client.post('/api/sessions/', {
            'topic': topic.id,
            'subject': topic.subject,  # Subject is required by serializer
            'notes': 'Starting study'
        }, format='json')
        
        assert response.status_code == 201
        assert response.data['is_active'] is True
        # Topic may not be included in response depending on serializer config
        assert 'topic' in response.data

    def test_stop_session(self, api_client, user):
        topic = StudyTopic.objects.create(user=user, subject='Python', topic='Test', exam_date='2026-10-15')
        session = StudySession.objects.create(user=user, subject='Python', topic=topic, notes='Test')
        
        response = api_client.post(f'/api/sessions/{session.id}/stop/')
        assert response.status_code == 200
        assert response.data['is_active'] is False
        assert response.data['duration_minutes'] >= 1


@pytest.mark.api
@pytest.mark.django_db
class TestGamificationAPI:
    """Test gamification API endpoints."""

    @pytest.fixture
    def api_client(self, user):
        client = APIClient()
        token, _ = Token.objects.get_or_create(user=user)
        client.credentials(HTTP_AUTHORIZATION=f'Token {token.key}')
        return client

    def test_profile_me(self, api_client, user):
        response = api_client.get('/api/profile/me/')
        assert response.status_code == 200
        assert 'xp' in response.data
        assert 'level' in response.data
        assert 'current_streak' in response.data

    def test_achievements_list(self, api_client):
        response = api_client.get('/api/achievements/')
        assert response.status_code == 200
        assert 'count' in response.data

    def test_daily_goals_create_defaults(self, api_client, user):
        response = api_client.post('/api/daily-goals/create_defaults/')
        assert response.status_code == 200
        assert len(response.data) == 2  # minutes and topics goals

    def test_daily_goal_progress(self, api_client, user):
        # Create default goals first
        api_client.post('/api/daily-goals/create_defaults/')
        
        # Get the minutes goal
        goals_response = api_client.get('/api/daily-goals/today/')
        minutes_goal = next(g for g in goals_response.data if g['goal_type'] == 'minutes')
        
        # Add progress
        response = api_client.post(f'/api/daily-goals/{minutes_goal["id"]}/add_progress/', {
            'amount': 30
        }, format='json')
        
        assert response.status_code == 200
        assert response.data['completed'] is True
        assert response.data['xp_awarded'] == 10


@pytest.mark.api
@pytest.mark.django_db
class TestTemplateAPI:
    """Test Topic Template API endpoints."""

    @pytest.fixture
    def api_client(self, user):
        client = APIClient()
        token, _ = Token.objects.get_or_create(user=user)
        client.credentials(HTTP_AUTHORIZATION=f'Token {token.key}')
        return client

    def test_create_template(self, api_client, user):
        data = {
            'name': 'Weekly Review',
            'subject': 'Python',
            'topic': 'Weekly Review {date}',
            'default_priority': 1,
            'exam_date_offset_days': 7,
            'default_notes': 'Review notes',
        }
        response = api_client.post('/api/templates/', data, format='json')
        
        assert response.status_code == 201
        assert response.data['name'] == 'Weekly Review'

    def test_create_from_template(self, api_client, user):
        from planner.models import TopicTemplate
        template = TopicTemplate.objects.create(
            user=user, name='Test', subject='Python', topic='Template {date}',
            exam_date_offset_days=7
        )
        
        response = api_client.post(f'/api/templates/{template.id}/create_topic/', {
            'exam_date': '2026-12-01'
        }, format='json')
        
        assert response.status_code == 201
        assert response.data['topic'] == 'Template {date}'


@pytest.mark.api
@pytest.mark.django_db
class TestExportImportAPI:
    """Test data export/import endpoints."""

    @pytest.fixture
    def api_client(self, user):
        client = APIClient()
        token, _ = Token.objects.get_or_create(user=user)
        client.credentials(HTTP_AUTHORIZATION=f'Token {token.key}')
        return client

    def test_export_json(self, api_client, user):
        StudyTopic.objects.create(user=user, subject='Python', topic='Test', exam_date='2026-10-15')
        
        response = api_client.get('/api/export/json/')
        assert response.status_code == 200
        assert response['Content-Type'] == 'application/json'
        data = response.json()
        assert 'topics' in data
        assert len(data['topics']) == 1

    def test_export_csv(self, api_client, user):
        StudyTopic.objects.create(user=user, subject='Python', topic='Test', exam_date='2026-10-15')
        
        response = api_client.get('/api/export/csv/')
        assert response.status_code == 200
        assert response['Content-Type'] == 'text/csv'
        content = response.content.decode()
        assert 'Subject,Topic,Exam Date' in content


# ===== Integration Tests =====

@pytest.mark.integration
@pytest.mark.django_db
class TestFullWorkflow:
    """End-to-end workflow tests."""

    def test_complete_study_workflow(self, user):
        """Test complete study workflow: add -> complete -> delete."""
        client = Client()
        client.force_login(user)
        
        # Add topic
        response = client.post(reverse('home'), {
            'subject': 'Python',
            'topic': 'Full Workflow',
            'exam_date': '2026-12-01',
            'priority': '1',
        })
        assert response.status_code == 302
        
        topic = StudyTopic.objects.get(topic='Full Workflow')
        assert topic.user == user
        
        # Complete topic
        response = client.post(reverse('complete', args=[topic.pk]))
        assert response.status_code == 302
        topic.refresh_from_db()
        assert topic.completed is True
        
        # Uncomplete
        response = client.post(reverse('complete', args=[topic.pk]))
        topic.refresh_from_db()
        assert topic.completed is False
        
        # Delete
        response = client.post(reverse('delete', args=[topic.pk]))
        assert response.status_code == 302
        assert StudyTopic.objects.count() == 0


@pytest.mark.integration
@pytest.mark.django_db
class TestPlannerEnhancements:
    def test_search_filter_and_topic_edit(self, user):
        client = Client()
        client.force_login(user)
        topic = StudyTopic.objects.create(
            user=user, subject='Python', topic='Functions',
            exam_date='2026-12-01', priority=0,
            notes='<script>alert(1)</script>',
        )
        StudyTopic.objects.create(
            user=user, subject='Django', topic='Models',
            exam_date='2026-12-10', priority=1,
        )

        response = client.get(reverse('home'), {'q': 'Functions', 'priority': '0'})
        assert response.status_code == 200
        assert response.context['total'] == 2
        assert response.context['shown_count'] == 1
        assert b'&lt;script&gt;' in response.content

        response = client.post(reverse('edit_topic', args=[topic.pk]), {
            'subject': 'Python',
            'topic': 'Functions and scope',
            'exam_date': '2026-12-05',
            'priority': '1',
            'notes': 'Updated notes',
        })
        assert response.status_code == 302
        topic.refresh_from_db()
        assert topic.topic == 'Functions and scope'
        assert topic.notes == 'Updated notes'

        another_user = User.objects.create_user(username='another', password='pass12345')
        other_topic = StudyTopic.objects.create(
            user=another_user, subject='Other', topic='Private', exam_date='2026-12-12'
        )
        assert client.get(reverse('edit_topic', args=[other_topic.pk])).status_code == 404

    def test_recurring_generation_obeys_interval_and_exam_offset(self, user):
        recurring = RecurringTopic.objects.create(
            user=user, subject='Python', topic_template='Weekly review',
            frequency='weekly', exam_date_offset_days=5,
        )
        today = date(2026, 10, 1)
        with patch('django.utils.timezone.localdate', return_value=today):
            first = recurring.generate_next()
        assert first.exam_date == today + timedelta(days=5)

        with patch('django.utils.timezone.localdate', return_value=today + timedelta(days=1)):
            assert recurring.generate_next() is None
        with patch('django.utils.timezone.localdate', return_value=today + timedelta(days=7)):
            second = recurring.generate_next()
        assert second is not None
        assert second.exam_date == today + timedelta(days=12)

    def test_session_list_loads_with_stats(self, user):
        client = Client()
        client.force_login(user)
        StudySession.objects.create(user=user, subject='Python')
        response = client.get(reverse('session_list'))
        assert response.status_code == 200
        assert response.context['today_minutes'] == 0

    def test_dashboard_page_is_removed(self, user):
        client = Client()
        client.force_login(user)
        response = client.get('/dashboard/')
        assert response.status_code == 302
        assert response.url == reverse('home')

        planner_response = client.get(reverse('home'))
        assert planner_response.status_code == 200
        assert b'>Dashboard</a>' not in planner_response.content
    @override_settings(EMAIL_BACKEND='django.core.mail.backends.locmem.EmailBackend')
    def test_daily_digest_sends_once_per_day(self, user):
        from django.utils import timezone

        user.email = 'student@example.com'
        user.save(update_fields=['email'])
        preference = NotificationPreference.objects.create(
            user=user, email_enabled=True, email_frequency='daily',
            daily_digest_time=time(0, 0), remind_before_days=3,
        )
        StudyTopic.objects.create(
            user=user, subject='Python', topic='Decorators',
            exam_date=timezone.localdate() + timedelta(days=2),
        )

        call_command('send_daily_digest')
        assert len(mail.outbox) == 1
        preference.refresh_from_db()
        assert preference.last_digest_sent_on == timezone.localdate()

        call_command('send_daily_digest')
        assert len(mail.outbox) == 1


@pytest.mark.api
@pytest.mark.django_db
class TestAPIAccessControls:
    def test_user_cannot_award_xp_or_manage_shared_challenges(self, user):
        client = APIClient()
        token, _ = Token.objects.get_or_create(user=user)
        client.credentials(HTTP_AUTHORIZATION=f'Token {token.key}')

        xp_response = client.post('/api/profile/add_xp/', {'amount': 20}, format='json')
        challenge_response = client.post('/api/challenges/', {}, format='json')
        assert xp_response.status_code == 403
        assert challenge_response.status_code == 403

    def test_user_cannot_attach_another_users_topic_to_session(self, user):
        client = APIClient()
        token, _ = Token.objects.get_or_create(user=user)
        client.credentials(HTTP_AUTHORIZATION=f'Token {token.key}')
        another_user = User.objects.create_user(username='other-api', password='pass12345')
        topic = StudyTopic.objects.create(
            user=another_user, subject='Private', topic='Other topic', exam_date='2026-12-01'
        )

        response = client.post('/api/sessions/', {
            'topic_id': topic.pk, 'subject': 'Private', 'notes': '',
        }, format='json')
        assert response.status_code == 400
        assert 'topic_id' in response.data['error']['details']

    def test_profile_and_notification_lists_only_return_current_user(self, user):
        client = APIClient()
        token, _ = Token.objects.get_or_create(user=user)
        client.credentials(HTTP_AUTHORIZATION=f'Token {token.key}')
        another_user = User.objects.create_user(username='other-list', password='pass12345')
        NotificationPreference.objects.create(user=user)
        NotificationPreference.objects.create(user=another_user)

        profiles = client.get('/api/profile/')
        preferences = client.get('/api/notifications/')
        assert [item['username'] for item in profiles.data['results']] == [user.username]
        assert len(preferences.data['results']) == 1


# ===== Performance Tests =====

@pytest.mark.slow
@pytest.mark.django_db
class TestPerformance:
    """Performance and load tests."""

    def test_bulk_topic_creation(self, user):
        """Test creating many topics efficiently."""
        from django.test.utils import override_settings
        import time
        
        with override_settings(DEBUG=False):
            start = time.time()
            topics = [
                StudyTopic(
                    user=user, 
                    subject=f'Subject {i}', 
                    topic=f'Topic {i}', 
                    exam_date='2026-12-01',
                    priority=i % 3
                )
                for i in range(100)
            ]
            StudyTopic.objects.bulk_create(topics)
            elapsed = time.time() - start
            
            assert StudyTopic.objects.count() == 100
            assert elapsed < 1.0  # Should complete in under 1 second


# ===== Fixtures =====

@pytest.fixture
def user(db):
    """Create a test user."""
    return User.objects.create_user(username='testuser', password='testpass123')


@pytest.fixture
def api_client(user):
    """Create an authenticated API client."""
    client = APIClient()
    token, _ = Token.objects.get_or_create(user=user)
    client.credentials(HTTP_AUTHORIZATION=f'Token {token.key}')
    return client
