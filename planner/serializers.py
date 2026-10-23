from rest_framework import serializers
from .models import (
    StudyTopic, Tag, StudySession, NotificationPreference, RecurringTopic,
    UserProfile, Achievement, UserAchievement, DailyGoal, WeeklyGoal,
    Leaderboard, StudyChallenge, ChallengeParticipant, TopicTemplate
)


class TagSerializer(serializers.ModelSerializer):
    class Meta:
        model = Tag
        fields = ['id', 'name', 'color', 'topics_count']
        read_only_fields = ['id', 'topics_count']

    topics_count = serializers.IntegerField(source='topics.count', read_only=True)


class StudyTopicSerializer(serializers.ModelSerializer):
    tags = TagSerializer(many=True, read_only=True)
    tag_ids = serializers.PrimaryKeyRelatedField(
        queryset=Tag.objects.all(), many=True, write_only=True, source='tags', required=False
    )
    priority_label = serializers.CharField(source='get_priority_display', read_only=True)
    is_overdue = serializers.BooleanField(read_only=True)
    days_until_exam = serializers.SerializerMethodField()

    class Meta:
        model = StudyTopic
        fields = [
            'id', 'subject', 'topic', 'exam_date', 'completed', 'priority',
            'priority_label', 'tags', 'tag_ids', 'notes', 'created_at', 'updated_at',
            'is_overdue', 'days_until_exam',
        ]
        read_only_fields = ['id', 'created_at', 'updated_at', 'user']

    def get_days_until_exam(self, obj):
        from django.utils import timezone
        if obj.completed:
            return None
        delta = obj.exam_date - timezone.localdate()
        return delta.days

    def create(self, validated_data):
        tags = validated_data.pop('tags', [])
        # user is set by perform_create in the view
        topic = StudyTopic.objects.create(**validated_data)
        topic.tags.set(tags)
        return topic

    def update(self, instance, validated_data):
        tags = validated_data.pop('tags', None)
        for attr, value in validated_data.items():
            setattr(instance, attr, value)
        instance.save()
        if tags is not None:
            instance.tags.set(tags)
        return instance


class StudyTopicListSerializer(serializers.ModelSerializer):
    """Lightweight serializer for list views."""
    tags = TagSerializer(many=True, read_only=True)
    priority_label = serializers.CharField(source='get_priority_display', read_only=True)
    is_overdue = serializers.BooleanField(read_only=True)

    class Meta:
        model = StudyTopic
        fields = ['id', 'subject', 'topic', 'exam_date', 'completed', 'priority', 'priority_label', 'tags', 'is_overdue']


class StudySessionSerializer(serializers.ModelSerializer):
    topic = StudyTopicListSerializer(read_only=True)
    topic_id = serializers.PrimaryKeyRelatedField(
        queryset=StudyTopic.objects.all(), write_only=True, source='topic', required=False, allow_null=True
    )
    is_active = serializers.BooleanField(read_only=True)

    class Meta:
        model = StudySession
        fields = [
            'id', 'topic', 'topic_id', 'subject', 'started_at', 'ended_at',
            'duration_minutes', 'notes', 'is_active',
        ]
        read_only_fields = ['id', 'started_at', 'user', 'duration_minutes']

    def create(self, validated_data):
        topic = validated_data.get('topic')
        validated_data['subject'] = topic.subject if topic else validated_data.get('subject', '')
        # user is set by perform_create in the view
        return StudySession.objects.create(**validated_data)

    def validate(self, attrs):
        request = self.context.get('request')
        topic = attrs.get('topic')
        if request and topic and topic.user_id != request.user.id:
            raise serializers.ValidationError({'topic_id': 'You can only attach sessions to your own topics.'})
        return attrs


class NotificationPreferenceSerializer(serializers.ModelSerializer):
    class Meta:
        model = NotificationPreference
        fields = [
            'email_enabled', 'email_frequency', 'remind_before_days',
            'notify_on_due', 'notify_overdue', 'daily_digest_time',
        ]


class RecurringTopicSerializer(serializers.ModelSerializer):
    tags = TagSerializer(many=True, read_only=True)
    tag_ids = serializers.PrimaryKeyRelatedField(
        queryset=Tag.objects.all(), many=True, write_only=True, source='tags', required=False
    )
    priority_label = serializers.CharField(source='get_priority_display', read_only=True)
    frequency_label = serializers.CharField(source='get_frequency_display', read_only=True)

    class Meta:
        model = RecurringTopic
        fields = [
            'id', 'subject', 'topic_template', 'exam_date_offset_days', 'frequency',
            'frequency_label', 'priority', 'priority_label', 'tags', 'tag_ids', 'notes',
            'is_active', 'last_generated', 'created_at',
        ]
        read_only_fields = ['id', 'last_generated', 'created_at', 'user']

    def create(self, validated_data):
        tags = validated_data.pop('tags', [])
        # user is set by perform_create in the view
        recurring = RecurringTopic.objects.create(**validated_data)
        recurring.tags.set(tags)
        return recurring

    def update(self, instance, validated_data):
        tags = validated_data.pop('tags', None)
        for attr, value in validated_data.items():
            setattr(instance, attr, value)
        instance.save()
        if tags is not None:
            instance.tags.set(tags)
        return instance


# Export/Import Serializers
class ExportDataSerializer(serializers.Serializer):
    """Serializer for full data export."""
    topics = StudyTopicSerializer(many=True)
    tags = TagSerializer(many=True)
    sessions = StudySessionSerializer(many=True)
    recurring_topics = RecurringTopicSerializer(many=True)
    exported_at = serializers.DateTimeField()
    version = serializers.CharField(default='1.0')


class ImportDataSerializer(serializers.Serializer):
    """Serializer for data import validation."""
    topics = StudyTopicSerializer(many=True, required=False)
    tags = TagSerializer(many=True, required=False)
    sessions = StudySessionSerializer(many=True, required=False)
    recurring_topics = RecurringTopicSerializer(many=True, required=False)

    def validate_topics(self, value):
        """Convert string priority labels to integers."""
        priority_map = {'high': 0, 'High': 0, 'medium': 1, 'Medium': 1, 'low': 2, 'Low': 2}
        for topic in value:
            if 'priority' in topic and isinstance(topic['priority'], str):
                topic['priority'] = priority_map.get(topic['priority'].lower(), 1)
        return value

    def validate_recurring_topics(self, value):
        """Convert string priority labels to integers."""
        priority_map = {'high': 0, 'High': 0, 'medium': 1, 'Medium': 1, 'low': 2, 'Low': 2}
        for rt in value:
            if 'priority' in rt and isinstance(rt['priority'], str):
                rt['priority'] = priority_map.get(rt['priority'].lower(), 1)
        return value


# ===== Gamification Serializers =====

class UserProfileSerializer(serializers.ModelSerializer):
    xp_progress_percent = serializers.FloatField(read_only=True)
    username = serializers.CharField(source='user.username', read_only=True)
    
    class Meta:
        model = UserProfile
        fields = [
            'id', 'username', 'xp', 'level', 'xp_for_next_level', 'xp_progress_percent',
            'current_streak', 'longest_streak', 'last_activity_date',
            'total_topics_completed', 'total_study_minutes', 'perfect_days',
            'daily_goal_minutes', 'weekly_goal_topics', 'timezone',
        ]
        read_only_fields = ['id', 'xp', 'level', 'xp_for_next_level', 'xp_progress_percent',
                           'current_streak', 'longest_streak', 'last_activity_date',
                           'total_topics_completed', 'total_study_minutes', 'perfect_days']


class AchievementSerializer(serializers.ModelSerializer):
    is_earned = serializers.SerializerMethodField()
    earned_at = serializers.SerializerMethodField()
    
    class Meta:
        model = Achievement
        fields = [
            'id', 'code', 'name', 'description', 'type', 'rarity', 'icon',
            'xp_reward', 'condition', 'is_earned', 'earned_at',
        ]
        read_only_fields = ['id', 'code', 'name', 'description', 'type', 'rarity', 'icon', 'xp_reward', 'condition']
    
    def get_is_earned(self, obj):
        request = self.context.get('request')
        if request and request.user.is_authenticated:
            return UserAchievement.objects.filter(user=request.user, achievement=obj).exists()
        return False
    
    def get_earned_at(self, obj):
        request = self.context.get('request')
        if request and request.user.is_authenticated:
            ua = UserAchievement.objects.filter(user=request.user, achievement=obj).first()
            return ua.earned_at if ua else None
        return None


class UserAchievementSerializer(serializers.ModelSerializer):
    achievement = AchievementSerializer(read_only=True)
    
    class Meta:
        model = UserAchievement
        fields = ['id', 'achievement', 'earned_at', 'progress']
        read_only_fields = ['id', 'achievement', 'earned_at', 'progress']


class DailyGoalSerializer(serializers.ModelSerializer):
    progress_percent = serializers.FloatField(read_only=True)
    
    class Meta:
        model = DailyGoal
        fields = ['id', 'date', 'goal_type', 'target', 'current', 'completed', 'progress_percent', 'xp_reward']
        read_only_fields = ['id', 'date', 'current', 'completed', 'progress_percent', 'xp_reward']


class WeeklyGoalSerializer(serializers.ModelSerializer):
    progress_percent = serializers.FloatField(read_only=True)
    
    class Meta:
        model = WeeklyGoal
        fields = ['id', 'week_start', 'goal_type', 'target', 'current', 'completed', 'progress_percent', 'xp_reward']
        read_only_fields = ['id', 'week_start', 'current', 'completed', 'progress_percent', 'xp_reward']


class LeaderboardSerializer(serializers.ModelSerializer):
    class Meta:
        model = Leaderboard
        fields = ['id', 'category', 'period', 'period_start', 'period_end', 'rankings', 'updated_at']
        read_only_fields = ['id', 'rankings', 'updated_at']


class StudyChallengeSerializer(serializers.ModelSerializer):
    is_running = serializers.BooleanField(read_only=True)
    user_progress = serializers.SerializerMethodField()
    user_participation = serializers.SerializerMethodField()
    
    class Meta:
        model = StudyChallenge
        fields = [
            'id', 'name', 'description', 'type', 'target', 'subject',
            'xp_reward', 'badge_reward', 'starts_at', 'ends_at', 'is_active',
            'is_running', 'user_progress', 'user_participation',
        ]
        read_only_fields = ['id', 'is_running', 'user_progress', 'user_participation']
    
    def get_user_progress(self, obj):
        request = self.context.get('request')
        if request and request.user.is_authenticated:
            participant = ChallengeParticipant.objects.filter(user=request.user, challenge=obj).first()
            if participant:
                return {
                    'progress': participant.progress,
                    'completed': participant.completed,
                    'progress_percent': participant.progress_percent,
                }
        return None
    
    def get_user_participation(self, obj):
        request = self.context.get('request')
        if request and request.user.is_authenticated:
            return ChallengeParticipant.objects.filter(user=request.user, challenge=obj).exists()
        return False


class ChallengeParticipantSerializer(serializers.ModelSerializer):
    challenge = StudyChallengeSerializer(read_only=True)
    progress_percent = serializers.FloatField(read_only=True)
    
    class Meta:
        model = ChallengeParticipant
        fields = ['id', 'challenge', 'joined_at', 'progress', 'completed', 'completed_at', 'reward_claimed', 'progress_percent']
        read_only_fields = ['id', 'joined_at', 'completed', 'completed_at', 'reward_claimed', 'progress_percent']


class TopicTemplateSerializer(serializers.ModelSerializer):
    default_tags = TagSerializer(many=True, read_only=True)
    default_tag_ids = serializers.PrimaryKeyRelatedField(
        queryset=Tag.objects.all(), many=True, write_only=True, source='default_tags', required=False
    )
    default_priority_label = serializers.CharField(source='get_default_priority_display', read_only=True)
    default_priority_css = serializers.CharField(read_only=True)

    class Meta:
        model = TopicTemplate
        fields = [
            'id', 'name', 'description', 'subject', 'topic', 'default_priority',
            'default_priority_label', 'default_priority_css', 'default_tags', 'default_tag_ids',
            'default_notes', 'exam_date_offset_days',
            'created_at', 'updated_at',
        ]
        read_only_fields = ['id', 'created_at', 'updated_at', 'user']

    def create(self, validated_data):
        tags = validated_data.pop('default_tags', [])
        template = TopicTemplate.objects.create(user=self.context['request'].user, **validated_data)
        template.default_tags.set(tags)
        return template
