from django.urls import path, include
from rest_framework.routers import DefaultRouter
from . import api_views

router = DefaultRouter()
router.register(r'tags', api_views.TagViewSet, basename='tag')
router.register(r'topics', api_views.StudyTopicViewSet, basename='topic')
router.register(r'sessions', api_views.StudySessionViewSet, basename='session')
router.register(r'notifications', api_views.NotificationPreferenceViewSet, basename='notification')
router.register(r'recurring', api_views.RecurringTopicViewSet, basename='recurring')

# Gamification
router.register(r'profile', api_views.UserProfileViewSet, basename='profile')
router.register(r'achievements', api_views.AchievementViewSet, basename='achievement')
router.register(r'daily-goals', api_views.DailyGoalViewSet, basename='daily-goal')
router.register(r'weekly-goals', api_views.WeeklyGoalViewSet, basename='weekly-goal')
router.register(r'leaderboards', api_views.LeaderboardViewSet, basename='leaderboard')
router.register(r'challenges', api_views.StudyChallengeViewSet, basename='challenge')

# Templates
router.register(r'templates', api_views.TopicTemplateViewSet, basename='template')

urlpatterns = [
    path('', include(router.urls)),

    # Auth
    path('auth/token/', api_views.CustomAuthToken.as_view(), name='api_token'),
    path('auth/register/', api_views.register_api, name='api_register'),

    # Export/Import
    path('export/json/', api_views.export_data, name='api_export_json'),
    path('export/csv/', api_views.export_csv, name='api_export_csv'),
    path('import/', api_views.import_data, name='api_import'),

    # Webhook
    path('webhook/', api_views.webhook_receive, name='api_webhook'),
]