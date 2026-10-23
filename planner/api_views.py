import csv
import json
from datetime import timedelta
from django.http import HttpResponse
from django.utils import timezone
from django_filters.rest_framework import DjangoFilterBackend
from rest_framework import viewsets, status, filters
from rest_framework.decorators import action, api_view, permission_classes
from rest_framework.permissions import IsAuthenticated, IsAdminUser, AllowAny
from rest_framework.response import Response
from rest_framework.authtoken.models import Token
from rest_framework.authtoken.views import ObtainAuthToken

from .models import (
    StudyTopic, Tag, StudySession, NotificationPreference, RecurringTopic,
    UserProfile, Achievement, UserAchievement, DailyGoal, WeeklyGoal,
    Leaderboard, StudyChallenge, ChallengeParticipant, TopicTemplate
)
from .serializers import (
    TagSerializer, StudyTopicSerializer, StudyTopicListSerializer,
    StudySessionSerializer, NotificationPreferenceSerializer,
    RecurringTopicSerializer, ExportDataSerializer, ImportDataSerializer,
    UserProfileSerializer, AchievementSerializer, UserAchievementSerializer,
    DailyGoalSerializer, WeeklyGoalSerializer, LeaderboardSerializer,
    StudyChallengeSerializer, ChallengeParticipantSerializer,
    TopicTemplateSerializer,
)


class UserFilteredViewSetMixin:
    """Mixin to filter queryset by current user."""
    def get_queryset(self):
        return self.queryset.filter(user=self.request.user)


class TagViewSet(UserFilteredViewSetMixin, viewsets.ModelViewSet):
    serializer_class = TagSerializer
    queryset = Tag.objects.all()
    filter_backends = [DjangoFilterBackend, filters.OrderingFilter, filters.SearchFilter]
    search_fields = ['name']
    ordering_fields = ['name', 'created_at']
    ordering = ['name']

    def get_queryset(self):
        # Tags are global, not user-specific
        return Tag.objects.all()


class StudyTopicViewSet(UserFilteredViewSetMixin, viewsets.ModelViewSet):
    queryset = StudyTopic.objects.select_related('user').prefetch_related('tags')
    filter_backends = [DjangoFilterBackend, filters.OrderingFilter, filters.SearchFilter]
    filterset_fields = ['completed', 'priority', 'tags']
    search_fields = ['subject', 'topic', 'notes']
    ordering_fields = ['exam_date', 'created_at', 'updated_at', 'priority']
    ordering = ['completed', 'exam_date', 'priority']

    def get_serializer_class(self):
        if self.action == 'list':
            return StudyTopicListSerializer
        return StudyTopicSerializer

    def perform_create(self, serializer):
        serializer.save(user=self.request.user)

    @action(detail=True, methods=['post'])
    def complete(self, request, pk=None):
        """Toggle completion status."""
        topic = self.get_object()
        was_completed = topic.completed
        topic.completed = not topic.completed
        topic.save()
        
        # Update user profile for gamification
        if topic.completed and not was_completed:
            profile = UserProfile.get_or_create_for_user(request.user)
            profile.total_topics_completed += 1
            # Award XP based on priority
            xp_rewards = {0: 20, 1: 10, 2: 5}  # high, medium, low
            profile.add_xp(xp_rewards.get(topic.priority, 10), f'Completed: {topic.topic}')
            # Update streak
            profile.update_streak()
            profile.save()
        
        return Response(StudyTopicSerializer(topic, context={'request': request}).data)

    @action(detail=False, methods=['get'])
    def overdue(self, request):
        """Get overdue topics."""
        today = timezone.localdate()
        overdue = self.get_queryset().filter(completed=False, exam_date__lt=today)
        serializer = self.get_serializer(overdue, many=True)
        return Response(serializer.data)

    @action(detail=False, methods=['get'])
    def due_soon(self, request):
        """Get topics due within N days (default 7)."""
        days = int(request.query_params.get('days', 7))
        today = timezone.localdate()
        due_soon = self.get_queryset().filter(
            completed=False,
            exam_date__gte=today,
            exam_date__lte=today + timedelta(days=days)
        )
        serializer = self.get_serializer(due_soon, many=True)
        return Response(serializer.data)

    @action(detail=False, methods=['get'])
    def stats(self, request):
        """Get user statistics."""
        stats = StudyTopic.get_user_stats(request.user)
        return Response(stats)

    @action(detail=False, methods=['post'])
    def reorder(self, request):
        """Reorder topics by providing a list of topic IDs in the desired order."""
        topic_ids = request.data.get('topic_ids', [])
        if not topic_ids:
            return Response({'detail': 'topic_ids list required.'}, status=status.HTTP_400_BAD_REQUEST)
        
        # Verify all topics belong to user
        topics = StudyTopic.objects.filter(id__in=topic_ids, user=request.user)
        if topics.count() != len(topic_ids):
            return Response({'detail': 'Some topics not found or access denied.'}, status=status.HTTP_400_BAD_REQUEST)
        
        # Update order by setting a custom order field or using the ID
        # We'll use a simple approach: update each topic's ID position
        # Since we order by ID as last resort, we can't easily reorder without an order field
        # For now, we'll return the new order for the frontend to handle
        return Response({
            'detail': 'Order updated. Frontend should re-render with new order.',
            'topic_ids': topic_ids,
        })


class TopicTemplateViewSet(UserFilteredViewSetMixin, viewsets.ModelViewSet):
    serializer_class = TopicTemplateSerializer
    queryset = TopicTemplate.objects.prefetch_related('default_tags')
    filter_backends = [DjangoFilterBackend, filters.OrderingFilter]
    ordering = ['-created_at']

    @action(detail=True, methods=['post'])
    def create_topic(self, request, pk=None):
        """Create a study topic from this template."""
        template = self.get_object()
        exam_date = request.data.get('exam_date')
        if exam_date:
            from datetime import datetime
            exam_date = datetime.strptime(exam_date, '%Y-%m-%d').date()
        topic = template.create_topic(request.user, exam_date)
        return Response(StudyTopicSerializer(topic, context={'request': request}).data, status=status.HTTP_201_CREATED)


class StudySessionViewSet(UserFilteredViewSetMixin, viewsets.ModelViewSet):
    serializer_class = StudySessionSerializer
    queryset = StudySession.objects.select_related('topic', 'user')
    filter_backends = [DjangoFilterBackend, filters.OrderingFilter]
    filterset_fields = ['topic']
    ordering_fields = ['started_at', 'duration_minutes']
    ordering = ['-started_at']

    def perform_create(self, serializer):
        serializer.save(user=self.request.user)

    @action(detail=True, methods=['post'])
    def stop(self, request, pk=None):
        """Stop an active session."""
        session = self.get_object()
        if session.ended_at:
            return Response({'detail': 'Session already stopped.'}, status=status.HTTP_400_BAD_REQUEST)
        session.stop()
        return Response(StudySessionSerializer(session, context={'request': request}).data)

    @action(detail=False, methods=['get'])
    def active(self, request):
        """Get currently active session."""
        active = self.get_queryset().filter(ended_at__isnull=True).first()
        if active:
            return Response(StudySessionSerializer(active, context={'request': request}).data)
        return Response({'detail': 'No active session.'}, status=status.HTTP_404_NOT_FOUND)

    @action(detail=False, methods=['get'])
    def summary(self, request):
        """Get session summary stats."""
        from django.db.models import Sum
        today = timezone.localdate()
        week_ago = today - timedelta(days=6)
        month_ago = today - timedelta(days=29)

        sessions = self.get_queryset()
        today_minutes = sessions.filter(started_at__date=today).aggregate(Sum('duration_minutes'))['duration_minutes__sum'] or 0
        week_minutes = sessions.filter(started_at__date__gte=week_ago).aggregate(Sum('duration_minutes'))['duration_minutes__sum'] or 0
        month_minutes = sessions.filter(started_at__date__gte=month_ago).aggregate(Sum('duration_minutes'))['duration_minutes__sum'] or 0
        total_minutes = sessions.aggregate(Sum('duration_minutes'))['duration_minutes__sum'] or 0
        total_sessions = sessions.count()

        return Response({
            'today_minutes': today_minutes,
            'week_minutes': week_minutes,
            'month_minutes': month_minutes,
            'total_minutes': total_minutes,
            'total_sessions': total_sessions,
        })


class NotificationPreferenceViewSet(viewsets.ModelViewSet):
    serializer_class = NotificationPreferenceSerializer
    queryset = NotificationPreference.objects.all().order_by('user_id')
    http_method_names = ['get', 'put', 'patch', 'head', 'options']

    def get_queryset(self):
        return NotificationPreference.objects.filter(user=self.request.user).order_by('user_id')

    def get_object(self):
        obj, _ = NotificationPreference.objects.get_or_create(user=self.request.user)
        return obj


class RecurringTopicViewSet(UserFilteredViewSetMixin, viewsets.ModelViewSet):
    serializer_class = RecurringTopicSerializer
    queryset = RecurringTopic.objects.prefetch_related('tags')
    filter_backends = [DjangoFilterBackend, filters.OrderingFilter]
    filterset_fields = ['is_active', 'frequency']
    ordering = ['-created_at']

    def perform_create(self, serializer):
        serializer.save(user=self.request.user)

    @action(detail=True, methods=['post'])
    def generate(self, request, pk=None):
        """Manually generate next topic from template."""
        recurring = self.get_object()
        topic = recurring.generate_next()
        if topic:
            return Response(StudyTopicSerializer(topic, context={'request': request}).data)
        return Response({'detail': 'Could not generate (inactive or already generated today).'}, status=status.HTTP_400_BAD_REQUEST)

    @action(detail=True, methods=['post'])
    def toggle(self, request, pk=None):
        """Toggle active status."""
        recurring = self.get_object()
        recurring.is_active = not recurring.is_active
        recurring.save()
        return Response(RecurringTopicSerializer(recurring, context={'request': request}).data)


# ===== Auth Token Views =====

class CustomAuthToken(ObtainAuthToken):
    """Get auth token for API access."""
    def post(self, request, *args, **kwargs):
        serializer = self.serializer_class(data=request.data, context={'request': request})
        serializer.is_valid(raise_exception=True)
        user = serializer.validated_data['user']
        token, created = Token.objects.get_or_create(user=user)
        return Response({
            'token': token.key,
            'user_id': user.pk,
            'username': user.username,
        })


@api_view(['POST'])
@permission_classes([AllowAny])
def register_api(request):
    """Register new user via API and return token."""
    from django.contrib.auth.models import User
    username = request.data.get('username')
    password = request.data.get('password')
    email = request.data.get('email', '')

    if not username or not password:
        return Response({'error': 'Username and password required.'}, status=status.HTTP_400_BAD_REQUEST)

    if User.objects.filter(username=username).exists():
        return Response({'error': 'Username already exists.'}, status=status.HTTP_400_BAD_REQUEST)

    user = User.objects.create_user(username=username, password=password, email=email)
    token, _ = Token.objects.get_or_create(user=user)
    return Response({
        'token': token.key,
        'user_id': user.pk,
        'username': user.username,
    }, status=status.HTTP_201_CREATED)


# ===== Export/Import Views =====

@api_view(['GET'])
@permission_classes([IsAuthenticated])
def export_data(request):
    """Export all user data as JSON."""
    from django.core.serializers.json import DjangoJSONEncoder

    user = request.user
    topics = StudyTopic.objects.filter(user=user)
    tags = Tag.objects.filter(topics__user=user).distinct()
    sessions = StudySession.objects.filter(user=user)
    recurring = RecurringTopic.objects.filter(user=user)

    data = {
        'topics': StudyTopicSerializer(topics, many=True, context={'request': request}).data,
        'tags': TagSerializer(tags, many=True).data,
        'sessions': StudySessionSerializer(sessions, many=True, context={'request': request}).data,
        'recurring_topics': RecurringTopicSerializer(recurring, many=True, context={'request': request}).data,
        'exported_at': timezone.now(),
        'version': '1.0',
    }

    response = HttpResponse(
        json.dumps(data, cls=DjangoJSONEncoder, indent=2),
        content_type='application/json'
    )
    response['Content-Disposition'] = f'attachment; filename="study_planner_export_{timezone.now().strftime("%Y%m%d")}.json"'
    return response


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def export_csv(request):
    """Export topics as CSV."""
    topics = StudyTopic.objects.filter(user=request.user).select_related('user').prefetch_related('tags')

    response = HttpResponse(content_type='text/csv')
    response['Content-Disposition'] = f'attachment; filename="topics_{timezone.now().strftime("%Y%m%d")}.csv"'

    writer = csv.writer(response)
    writer.writerow(['Subject', 'Topic', 'Exam Date', 'Completed', 'Priority', 'Tags', 'Notes', 'Created At'])

    for topic in topics:
        writer.writerow([
            topic.subject,
            topic.topic,
            topic.exam_date,
            'Yes' if topic.completed else 'No',
            topic.get_priority_display(),
            ', '.join(tag.name for tag in topic.tags.all()),
            topic.notes,
            topic.created_at,
        ])

    return response


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def import_data(request):
    """Import data from JSON."""
    try:
        data = json.loads(request.body)
    except json.JSONDecodeError:
        return Response({'error': 'Invalid JSON.'}, status=status.HTTP_400_BAD_REQUEST)

    # Fields that are read-only properties, not model fields
    topic_readonly = {'priority_label', 'is_overdue', 'days_until_exam', 'created_at', 'updated_at', 'id'}
    session_readonly = {'is_active', 'id', 'started_at', 'duration_minutes', 'user'}
    recurring_readonly = {'priority_label', 'frequency_label', 'id', 'last_generated', 'created_at', 'user'}
    tag_readonly = {'id', 'topics_count'}

    user = request.user
    created = {'topics': 0, 'tags': 0, 'sessions': 0, 'recurring': 0}

    # Import tags first (referenced by others)
    tag_map = {}  # old_id -> new_tag
    for tag_data in data.get('tags', []):
        # Remove read-only fields
        for field in tag_readonly:
            tag_data.pop(field, None)
        tag, created_tag = Tag.objects.get_or_create(
            name=tag_data['name'],
            defaults={'color': tag_data.get('color', '#5551aa')}
        )
        tag_map[tag_data['id']] = tag
        if created_tag:
            created['tags'] += 1

    # Import topics
    for topic_data in data.get('topics', []):
        # Remove read-only fields and M2M fields
        for field in topic_readonly:
            topic_data.pop(field, None)
        topic_data.pop('tags', None)  # M2M field handled separately
        # Convert string priority to int
        if 'priority' in topic_data and isinstance(topic_data['priority'], str):
            priority_map = {'high': 0, 'High': 0, 'medium': 1, 'Medium': 1, 'low': 2, 'Low': 2}
            topic_data['priority'] = priority_map.get(topic_data['priority'].lower(), 1)
        tag_ids = topic_data.pop('tag_ids', [])
        tags = [tag_map.get(tid) for tid in tag_ids if tag_map.get(tid)]
        topic = StudyTopic.objects.create(user=user, **topic_data)
        topic.tags.set(tags)
        created['topics'] += 1

    # Import sessions
    for session_data in data.get('sessions', []):
        # Remove read-only fields
        for field in session_readonly:
            session_data.pop(field, None)
        topic_id = session_data.pop('topic_id', None)
        topic = None
        if topic_id:
            # Try to find by original ID (won't match) - skip for now
            pass
        StudySession.objects.create(user=user, topic=topic, **session_data)
        created['sessions'] += 1

    # Import recurring topics
    for rec_data in data.get('recurring_topics', []):
        # Remove read-only fields and M2M fields
        for field in recurring_readonly:
            rec_data.pop(field, None)
        rec_data.pop('tags', None)  # M2M field handled separately
        # Convert string priority to int
        if 'priority' in rec_data and isinstance(rec_data['priority'], str):
            priority_map = {'high': 0, 'High': 0, 'medium': 1, 'Medium': 1, 'low': 2, 'Low': 2}
            rec_data['priority'] = priority_map.get(rec_data['priority'].lower(), 1)
        tag_ids = rec_data.pop('tag_ids', [])
        tags = [tag_map.get(tid) for tid in tag_ids if tag_map.get(tid)]
        rec = RecurringTopic.objects.create(user=user, **rec_data)
        rec.tags.set(tags)
        created['recurring'] += 1

    return Response({'created': created, 'message': 'Import successful.'})


# ===== Gamification Views =====

class UserProfileViewSet(viewsets.ModelViewSet):
    serializer_class = UserProfileSerializer
    queryset = UserProfile.objects.all()
    http_method_names = ['get', 'post', 'put', 'patch', 'head', 'options']

    def get_queryset(self):
        return UserProfile.objects.filter(user=self.request.user)
    
    def get_object(self):
        profile, _ = UserProfile.objects.get_or_create(user=self.request.user)
        return profile
    
    @action(detail=False, methods=['get'])
    def me(self, request):
        """Get current user's profile."""
        profile = self.get_object()
        serializer = self.get_serializer(profile)
        return Response(serializer.data)
    
    @action(detail=False, methods=['post'])
    def add_xp(self, request):
        """Allow staff to award a bounded amount of XP for administration."""
        if not request.user.is_staff:
            return Response({'detail': 'Staff access required.'}, status=status.HTTP_403_FORBIDDEN)
        try:
            amount = int(request.data.get('amount', 0))
        except (TypeError, ValueError):
            return Response({'amount': 'Enter a whole number.'}, status=status.HTTP_400_BAD_REQUEST)
        if not 1 <= amount <= 10000:
            return Response({'amount': 'Amount must be between 1 and 10000.'}, status=status.HTTP_400_BAD_REQUEST)
        reason = str(request.data.get('reason', 'Manual XP award')).strip()[:150]
        profile = self.get_object()
        leveled_up = profile.add_xp(amount, reason)
        return Response({
            'profile': UserProfileSerializer(profile).data,
            'leveled_up': leveled_up,
        })


class AchievementViewSet(viewsets.ReadOnlyModelViewSet):
    serializer_class = AchievementSerializer
    queryset = Achievement.objects.filter(is_active=True)
    filter_backends = [DjangoFilterBackend, filters.OrderingFilter]
    filterset_fields = ['type', 'rarity']
    ordering = ['type', 'rarity', 'name']
    
    @action(detail=False, methods=['get'])
    def earned(self, request):
        """Get user's earned achievements."""
        earned = UserAchievement.objects.filter(user=request.user).select_related('achievement')
        serializer = UserAchievementSerializer(earned, many=True, context={'request': request})
        return Response(serializer.data)
    
    @action(detail=False, methods=['get'])
    def unearned(self, request):
        """Get user's unearned achievements."""
        earned_ids = UserAchievement.objects.filter(user=request.user).values_list('achievement_id', flat=True)
        unearned = self.get_queryset().exclude(id__in=earned_ids)
        serializer = self.get_serializer(unearned, many=True, context={'request': request})
        return Response(serializer.data)
    
    @action(detail=True, methods=['post'])
    def check_unlock(self, request, pk=None):
        """Check if user meets criteria for this achievement."""
        achievement = self.get_object()
        user = request.user
        
        # Check if already earned
        if UserAchievement.objects.filter(user=user, achievement=achievement).exists():
            return Response({'already_earned': True})
        
        # Check conditions
        unlocked = self._check_achievement_condition(user, achievement)
        
        if unlocked:
            ua = UserAchievement.objects.create(user=user, achievement=achievement)
            # Award XP
            profile = UserProfile.get_or_create_for_user(user)
            profile.add_xp(achievement.xp_reward, f'Achievement: {achievement.name}')
            
            return Response({
                'unlocked': True,
                'achievement': AchievementSerializer(achievement, context={'request': request}).data,
                'xp_awarded': achievement.xp_reward,
            })
        
        return Response({'unlocked': False, 'message': 'Conditions not met'})
    
    def _check_achievement_condition(self, user, achievement):
        """Check if user meets achievement condition."""
        cond = achievement.condition
        profile = UserProfile.get_or_create_for_user(user)
        
        if achievement.type == 'streak':
            if 'streak_days' in cond:
                return profile.current_streak >= cond['streak_days']
            if 'longest_streak' in cond:
                return profile.longest_streak >= cond['longest_streak']
        
        elif achievement.type == 'completion':
            if 'topics_completed' in cond:
                return profile.total_topics_completed >= cond['topics_completed']
            if 'perfect_days' in cond:
                return profile.perfect_days >= cond['perfect_days']
        
        elif achievement.type == 'time':
            if 'study_minutes' in cond:
                return profile.total_study_minutes >= cond['study_minutes']
        
        elif achievement.type == 'subject':
            if 'subject_topics' in cond:
                subject = cond.get('subject')
                count = StudyTopic.objects.filter(user=user, subject=subject, completed=True).count()
                return count >= cond['subject_topics']
        
        elif achievement.type == 'priority':
            if 'high_priority_completed' in cond:
                count = StudyTopic.objects.filter(user=user, priority=0, completed=True).count()
                return count >= cond['high_priority_completed']
        
        return False


class DailyGoalViewSet(viewsets.ModelViewSet):
    serializer_class = DailyGoalSerializer
    queryset = DailyGoal.objects.all()
    filter_backends = [DjangoFilterBackend, filters.OrderingFilter]
    filterset_fields = ['goal_type', 'completed']
    ordering = ['-date']
    
    def get_queryset(self):
        return DailyGoal.objects.filter(user=self.request.user)
    
    def perform_create(self, serializer):
        serializer.save(user=self.request.user)
    
    @action(detail=False, methods=['get'])
    def today(self, request):
        """Get today's goals."""
        from django.utils import timezone
        today = timezone.localdate()
        goals = self.get_queryset().filter(date=today)
        serializer = self.get_serializer(goals, many=True)
        return Response(serializer.data)
    
    @action(detail=False, methods=['post'])
    def create_defaults(self, request):
        """Create default daily goals for today."""
        from django.utils import timezone
        profile = UserProfile.get_or_create_for_user(request.user)
        today = timezone.localdate()
        
        goals_data = [
            {'goal_type': 'minutes', 'target': profile.daily_goal_minutes, 'xp_reward': 10},
            {'goal_type': 'topics', 'target': 3, 'xp_reward': 15},
        ]
        
        created = []
        for g in goals_data:
            goal, _ = DailyGoal.objects.get_or_create(
                user=request.user,
                date=today,
                goal_type=g['goal_type'],
                defaults={'target': g['target'], 'xp_reward': g['xp_reward']}
            )
            created.append(goal)
        
        serializer = self.get_serializer(created, many=True)
        return Response(serializer.data)
    
    @action(detail=True, methods=['post'])
    def add_progress(self, request, pk=None):
        """Add progress to a daily goal."""
        goal = self.get_object()
        amount = request.data.get('amount', 1)
        
        if goal.completed:
            return Response({'error': 'Goal already completed'}, status=status.HTTP_400_BAD_REQUEST)
        
        completed = goal.add_progress(amount)
        serializer = self.get_serializer(goal)
        return Response({
            'goal': serializer.data,
            'completed': completed,
            'xp_awarded': goal.xp_reward if completed else 0,
        })


class WeeklyGoalViewSet(viewsets.ModelViewSet):
    serializer_class = WeeklyGoalSerializer
    queryset = WeeklyGoal.objects.all()
    filter_backends = [DjangoFilterBackend, filters.OrderingFilter]
    filterset_fields = ['goal_type', 'completed']
    ordering = ['-week_start']
    
    def get_queryset(self):
        return WeeklyGoal.objects.filter(user=self.request.user)
    
    def perform_create(self, serializer):
        serializer.save(user=self.request.user)
    
    @action(detail=False, methods=['get'])
    def current(self, request):
        """Get current week's goals."""
        from django.utils import timezone
        from datetime import timedelta
        today = timezone.localdate()
        week_start = today - timedelta(days=today.weekday())  # Monday
        goals = self.get_queryset().filter(week_start=week_start)
        serializer = self.get_serializer(goals, many=True)
        return Response(serializer.data)


class LeaderboardViewSet(viewsets.ReadOnlyModelViewSet):
    serializer_class = LeaderboardSerializer
    queryset = Leaderboard.objects.all()
    filter_backends = [DjangoFilterBackend, filters.OrderingFilter]
    filterset_fields = ['category', 'period']
    ordering = ['category', 'period', '-period_start']
    
    @action(detail=False, methods=['get'])
    def top(self, request):
        """Get top rankings for a category."""
        category = request.query_params.get('category', 'xp')
        period = request.query_params.get('period', 'all_time')
        
        lb = Leaderboard.objects.filter(category=category, period=period).first()
        if lb:
            return Response(lb.rankings)
        return Response([])


class StudyChallengeViewSet(viewsets.ModelViewSet):
    serializer_class = StudyChallengeSerializer
    queryset = StudyChallenge.objects.filter(is_active=True)
    filter_backends = [DjangoFilterBackend, filters.OrderingFilter]
    filterset_fields = ['type', 'is_active']
    ordering = ['-starts_at']

    def get_permissions(self):
        if self.action in {'create', 'update', 'partial_update', 'destroy'}:
            return [IsAdminUser()]
        return [permission() for permission in self.permission_classes]
    
    @action(detail=False, methods=['get'])
    def active(self, request):
        """Get currently active challenges."""
        from django.utils import timezone
        now = timezone.now()
        challenges = self.get_queryset().filter(starts_at__lte=now, ends_at__gte=now)
        serializer = self.get_serializer(challenges, many=True, context={'request': request})
        return Response(serializer.data)
    
    @action(detail=True, methods=['post'])
    def join(self, request, pk=None):
        """Join a challenge."""
        challenge = self.get_object()
        if not challenge.is_running:
            return Response({'error': 'Challenge is not currently running'}, status=status.HTTP_400_BAD_REQUEST)
        
        participant, created = ChallengeParticipant.objects.get_or_create(
            user=request.user,
            challenge=challenge
        )
        if not created:
            return Response({'error': 'Already joined this challenge'}, status=status.HTTP_400_BAD_REQUEST)
        
        serializer = ChallengeParticipantSerializer(participant)
        return Response(serializer.data, status=status.HTTP_201_CREATED)
    
    @action(detail=True, methods=['post'])
    def add_progress(self, request, pk=None):
        """Add progress to a challenge."""
        challenge = self.get_object()
        amount = request.data.get('amount', 1)
        
        try:
            participant = ChallengeParticipant.objects.get(user=request.user, challenge=challenge)
        except ChallengeParticipant.DoesNotExist:
            return Response({'error': 'Not joined this challenge'}, status=status.HTTP_400_BAD_REQUEST)
        
        if participant.completed:
            return Response({'error': 'Challenge already completed'}, status=status.HTTP_400_BAD_REQUEST)
        
        completed = participant.add_progress(amount)
        
        # Check if challenge completed
        if completed and not participant.reward_claimed:
            # Award XP
            profile = UserProfile.get_or_create_for_user(request.user)
            profile.add_xp(challenge.xp_reward, f'Challenge: {challenge.name}')
            
            # Award badge if any
            if challenge.badge_reward:
                UserAchievement.objects.get_or_create(
                    user=request.user,
                    achievement=challenge.badge_reward
                )
                profile.add_xp(challenge.badge_reward.xp_reward, f'Badge: {challenge.badge_reward.name}')
            
            participant.reward_claimed = True
            participant.save()
        
        serializer = ChallengeParticipantSerializer(participant)
        return Response(serializer.data)
    
    @action(detail=False, methods=['get'])
    def my_challenges(self, request):
        """Get user's challenge participations."""
        participations = ChallengeParticipant.objects.filter(user=request.user).select_related('challenge')
        serializer = ChallengeParticipantSerializer(participations, many=True, context={'request': request})
        return Response(serializer.data)


# Auto-create default achievements
def create_default_achievements():
    """Create default achievements. Run once via management command or shell."""
    achievements = [
        # Streak achievements
        {'code': 'streak_3', 'name': 'Getting Started', 'description': 'Maintain a 3-day study streak', 'type': 'streak', 'rarity': 'common', 'icon': '🔥', 'xp_reward': 25, 'condition': {'streak_days': 3}},
        {'code': 'streak_7', 'name': 'Week Warrior', 'description': 'Maintain a 7-day study streak', 'type': 'streak', 'rarity': 'uncommon', 'icon': '🔥', 'xp_reward': 50, 'condition': {'streak_days': 7}},
        {'code': 'streak_14', 'name': 'Fortnight Fighter', 'description': 'Maintain a 14-day study streak', 'type': 'streak', 'rarity': 'rare', 'icon': '🔥', 'xp_reward': 100, 'condition': {'streak_days': 14}},
        {'code': 'streak_30', 'name': 'Monthly Master', 'description': 'Maintain a 30-day study streak', 'type': 'streak', 'rarity': 'epic', 'icon': '🔥', 'xp_reward': 250, 'condition': {'streak_days': 30}},
        {'code': 'streak_100', 'name': 'Centurion', 'description': 'Maintain a 100-day study streak', 'type': 'streak', 'rarity': 'legendary', 'icon': '🔥', 'xp_reward': 1000, 'condition': {'streak_days': 100}},
        
        # Completion achievements
        {'code': 'first_completion', 'name': 'First Steps', 'description': 'Complete your first topic', 'type': 'completion', 'rarity': 'common', 'icon': '🎯', 'xp_reward': 10, 'condition': {'topics_completed': 1}},
        {'code': 'completions_10', 'name': 'Decade', 'description': 'Complete 10 topics', 'type': 'completion', 'rarity': 'common', 'icon': '🎯', 'xp_reward': 50, 'condition': {'topics_completed': 10}},
        {'code': 'completions_50', 'name': 'Half Century', 'description': 'Complete 50 topics', 'type': 'completion', 'rarity': 'uncommon', 'icon': '🎯', 'xp_reward': 150, 'condition': {'topics_completed': 50}},
        {'code': 'completions_100', 'name': 'Centurion Scholar', 'description': 'Complete 100 topics', 'type': 'completion', 'rarity': 'rare', 'icon': '🎯', 'xp_reward': 300, 'condition': {'topics_completed': 100}},
        {'code': 'perfect_3', 'name': 'Perfect Three', 'description': 'Have 3 perfect days (all topics completed)', 'type': 'completion', 'rarity': 'uncommon', 'icon': '⭐', 'xp_reward': 75, 'condition': {'perfect_days': 3}},
        {'code': 'perfect_7', 'name': 'Perfect Week', 'description': 'Have 7 perfect days', 'type': 'completion', 'rarity': 'rare', 'icon': '⭐', 'xp_reward': 200, 'condition': {'perfect_days': 7}},
        
        # Time achievements
        {'code': 'time_60', 'name': 'Hour of Power', 'description': 'Study for 60 total minutes', 'type': 'time', 'rarity': 'common', 'icon': '⏱️', 'xp_reward': 25, 'condition': {'study_minutes': 60}},
        {'code': 'time_300', 'name': 'Five Hour Energy', 'description': 'Study for 300 total minutes', 'type': 'time', 'rarity': 'uncommon', 'icon': '⏱️', 'xp_reward': 75, 'condition': {'study_minutes': 300}},
        {'code': 'time_1000', 'name': 'Time Lord', 'description': 'Study for 1000 total minutes', 'type': 'time', 'rarity': 'epic', 'icon': '⏱️', 'xp_reward': 250, 'condition': {'study_minutes': 1000}},
        
        # Subject mastery
        {'code': 'subject_5', 'name': 'Subject Specialist', 'description': 'Complete 5 topics in a single subject', 'type': 'subject', 'rarity': 'common', 'icon': '📚', 'xp_reward': 30, 'condition': {'subject_topics': 5}},
        {'code': 'subject_20', 'name': 'Subject Master', 'description': 'Complete 20 topics in a single subject', 'type': 'subject', 'rarity': 'rare', 'icon': '📚', 'xp_reward': 150, 'condition': {'subject_topics': 20}},
        
        # Priority
        {'code': 'high_priority_5', 'name': 'Priority One', 'description': 'Complete 5 high-priority topics', 'type': 'priority', 'rarity': 'uncommon', 'icon': '🚨', 'xp_reward': 50, 'condition': {'high_priority_completed': 5}},
        {'code': 'high_priority_20', 'name': 'Crisis Manager', 'description': 'Complete 20 high-priority topics', 'type': 'priority', 'rarity': 'epic', 'icon': '🚨', 'xp_reward': 200, 'condition': {'high_priority_completed': 20}},
        
        # Special
        {'code': 'early_bird', 'name': 'Early Bird', 'description': 'Complete a topic before 8 AM', 'type': 'special', 'rarity': 'uncommon', 'icon': '🌅', 'xp_reward': 30, 'condition': {'early_completion': True}},
        {'code': 'night_owl', 'name': 'Night Owl', 'description': 'Complete a topic after 10 PM', 'type': 'special', 'rarity': 'uncommon', 'icon': '🦉', 'xp_reward': 30, 'condition': {'late_completion': True}},
        {'code': 'weekend_warrior', 'name': 'Weekend Warrior', 'description': 'Complete 5 topics on weekends', 'type': 'special', 'rarity': 'rare', 'icon': '🏰', 'xp_reward': 100, 'condition': {'weekend_completions': 5}},
    ]
    
    for ach_data in achievements:
        Achievement.objects.get_or_create(
            code=ach_data['code'],
            defaults=ach_data
        )


# ===== Webhook =====

@api_view(['POST'])
@permission_classes([AllowAny])  # In production, verify webhook secret
def webhook_receive(request):
    """Receive webhooks from external services."""
    event = request.data.get('event')
    payload = request.data.get('payload', {})

    # Log webhook (in production, process asynchronously)
    print(f"Webhook received: {event} - {payload}")

    # Example: Create topic from webhook
    if event == 'topic.created':
        user = None  # Would need user identification in production
        # StudyTopic.objects.create(user=user, **payload)

    return Response({'status': 'ok'})
