from django.db import models
from django.contrib.auth.models import User


class Tag(models.Model):
    name = models.CharField(max_length=30, unique=True)
    color = models.CharField(max_length=7, default='#5551aa')  # hex color

    class Meta:
        ordering = ['name']

    def __str__(self):
        return self.name


class TopicTemplate(models.Model):
    """Reusable templates for creating study topics quickly."""
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='topic_templates')
    name = models.CharField(max_length=100)
    description = models.TextField(blank=True, default='')
    subject = models.CharField(max_length=80, blank=True, default='')
    topic = models.CharField(max_length=150)
    default_priority = models.IntegerField(choices=[
        (0, 'High'), (1, 'Medium'), (2, 'Low')
    ], default=1)
    default_tags = models.ManyToManyField(Tag, blank=True, related_name='templates')
    default_notes = models.TextField(blank=True, default='')
    exam_date_offset_days = models.PositiveIntegerField(default=7)
    is_public = models.BooleanField(default=False)  # for future sharing
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return f'{self.name} ({self.subject})'

    def create_topic(self, user, exam_date=None):
        """Create a StudyTopic from this template."""
        from django.utils import timezone
        from datetime import timedelta
        
        if exam_date is None:
            exam_date = timezone.localdate() + timedelta(days=self.exam_date_offset_days)
        
        topic = StudyTopic.objects.create(
            user=user,
            subject=self.subject,
            topic=self.topic,
            exam_date=exam_date,
            priority=self.default_priority,
            notes=self.default_notes,
        )
        topic.tags.set(self.default_tags.all())
        return topic

    @property
    def default_priority_css(self):
        return {0: 'high', 1: 'medium', 2: 'low'}[self.default_priority]


class StudyTopic(models.Model):
    PRIORITY_CHOICES = [
        (0, 'High'),
        (1, 'Medium'),
        (2, 'Low'),
    ]

    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='study_topics', null=True, blank=True)
    subject = models.CharField(max_length=80)
    topic = models.CharField(max_length=150)
    exam_date = models.DateField()
    completed = models.BooleanField(default=False)
    priority = models.IntegerField(choices=PRIORITY_CHOICES, default=1)
    tags = models.ManyToManyField(Tag, blank=True, related_name='topics')
    notes = models.TextField(blank=True, default='')
    created_at = models.DateTimeField(auto_now_add=True, null=True)
    updated_at = models.DateTimeField(auto_now=True, null=True)

    class Meta:
        ordering = ['completed', 'exam_date', 'priority', 'id']

    def __str__(self):
        return f'{self.subject}: {self.topic}'

    @property
    def is_overdue(self):
        from django.utils import timezone
        return not self.completed and self.exam_date < timezone.localdate()

    @property
    def priority_label(self):
        return dict(self.PRIORITY_CHOICES)[self.priority]

    @property
    def priority_css(self):
        return {0: 'high', 1: 'medium', 2: 'low'}[self.priority]

    @classmethod
    def get_user_stats(cls, user):
        """Get comprehensive statistics for a user."""
        from django.utils import timezone
        from django.db.models import Count, Q
        from datetime import timedelta

        today = timezone.localdate()
        topics = cls.objects.filter(user=user)

        total = topics.count()
        completed = topics.filter(completed=True).count()
        pending = total - completed
        overdue = topics.filter(completed=False, exam_date__lt=today).count()
        due_today = topics.filter(completed=False, exam_date=today).count()

        # Completion rate
        completion_rate = round((completed / total * 100) if total > 0 else 0, 1)

        # Priority breakdown
        priority_stats = topics.values('priority', 'completed').annotate(count=Count('id'))
        priority_breakdown = {'high': {'total': 0, 'completed': 0}, 'medium': {'total': 0, 'completed': 0}, 'low': {'total': 0, 'completed': 0}}
        for stat in priority_stats:
            # Handle both integer and string values for priority (Django choices quirk)
            pri = stat['priority']
            if isinstance(pri, str):
                pri_map = {'High': 0, 'Medium': 1, 'Low': 2, 'high': 0, 'medium': 1, 'low': 2}
                pri = pri_map.get(pri, 1)
            p = {0: 'high', 1: 'medium', 2: 'low'}[pri]
            if stat['completed']:
                priority_breakdown[p]['completed'] = stat['count']
            else:
                priority_breakdown[p]['total'] = stat['count']

        # Weekly completion (last 7 days)
        week_ago = today - timedelta(days=6)
        weekly = topics.filter(created_at__date__gte=week_ago).values('created_at__date', 'completed').annotate(count=Count('id'))
        weekly_data = {}
        for i in range(7):
            d = week_ago + timedelta(days=i)
            weekly_data[d.isoformat()] = {'added': 0, 'completed': 0}
        for stat in weekly:
            date_str = stat['created_at__date'].isoformat()
            if stat['completed']:
                weekly_data[date_str]['completed'] = stat['count']
            else:
                weekly_data[date_str]['added'] = stat['count']

        # Monthly completion (last 30 days)
        month_ago = today - timedelta(days=29)
        monthly = topics.filter(created_at__date__gte=month_ago).values('created_at__date', 'completed').annotate(count=Count('id'))
        monthly_data = {}
        for i in range(30):
            d = month_ago + timedelta(days=i)
            monthly_data[d.isoformat()] = {'added': 0, 'completed': 0}
        for stat in monthly:
            date_str = stat['created_at__date'].isoformat()
            if stat['completed']:
                monthly_data[date_str]['completed'] = stat['count']
            else:
                monthly_data[date_str]['added'] = stat['count']

        # Study streak (consecutive days with completed topics)
        streak = cls._calculate_streak(user, today)

        # Subject breakdown
        subject_stats = topics.values('subject', 'completed').annotate(count=Count('id'))
        subjects = {}
        for stat in subject_stats:
            s = stat['subject']
            if s not in subjects:
                subjects[s] = {'total': 0, 'completed': 0}
            if stat['completed']:
                subjects[s]['completed'] = stat['count']
            else:
                subjects[s]['total'] = stat['count']

        return {
            'total': total,
            'completed': completed,
            'pending': pending,
            'overdue': overdue,
            'due_today': due_today,
            'completion_rate': completion_rate,
            'priority_breakdown': priority_breakdown,
            'weekly_data': weekly_data,
            'monthly_data': monthly_data,
            'streak': streak,
            'subjects': subjects,
        }

    @classmethod
    def _calculate_streak(cls, user, today):
        """Calculate current study streak (consecutive days with at least one completion)."""
        from datetime import timedelta

        # Get dates when user completed topics
        completed_dates = set(
            cls.objects.filter(user=user, completed=True)
            .values_list('updated_at__date', flat=True)
            .distinct()
        )

        streak = 0
        current_day = today
        while current_day in completed_dates:
            streak += 1
            current_day -= timedelta(days=1)

        return streak


class StudySession(models.Model):
    """Track actual study time spent on topics."""
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='study_sessions')
    topic = models.ForeignKey(StudyTopic, on_delete=models.CASCADE, related_name='sessions', null=True, blank=True)
    subject = models.CharField(max_length=80)  # denormalized for quick queries
    started_at = models.DateTimeField(auto_now_add=True)
    ended_at = models.DateTimeField(null=True, blank=True)
    duration_minutes = models.PositiveIntegerField(default=0)
    notes = models.TextField(blank=True, default='')

    class Meta:
        ordering = ['-started_at']

    def __str__(self):
        topic_str = f' - {self.topic}' if self.topic else ''
        return f'{self.subject}{topic_str} - {self.duration_minutes}min'

    @property
    def is_active(self):
        return self.ended_at is None

    def stop(self):
        from django.utils import timezone
        from django.db import transaction
        from django.db.models import F

        if self.ended_at is None:
            with transaction.atomic():
                self.ended_at = timezone.now()
                delta = self.ended_at - self.started_at
                self.duration_minutes = max(1, int(delta.total_seconds() / 60))
                self.save(update_fields=['ended_at', 'duration_minutes'])

                UserProfile.get_or_create_for_user(self.user)
                UserProfile.objects.filter(user=self.user).update(
                    total_study_minutes=F('total_study_minutes') + self.duration_minutes
                )

                # Keep today's study goals in sync with completed sessions.
                goals = DailyGoal.objects.select_for_update().filter(
                    user=self.user,
                    date=timezone.localdate(),
                    goal_type__in=['minutes', 'sessions'],
                    completed=False,
                )
                for goal in goals:
                    progress = self.duration_minutes if goal.goal_type == 'minutes' else 1
                    goal.add_progress(progress)


class NotificationPreference(models.Model):
    """User preferences for email/browser notifications."""
    FREQUENCY_CHOICES = [
        ('none', 'None'),
        ('daily', 'Daily digest'),
    ]

    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='notification_prefs')
    email_enabled = models.BooleanField(default=True)
    email_frequency = models.CharField(max_length=10, choices=FREQUENCY_CHOICES, default='daily')
    remind_before_days = models.PositiveIntegerField(default=3)  # days before exam
    notify_on_due = models.BooleanField(default=True)
    notify_overdue = models.BooleanField(default=True)
    daily_digest_time = models.TimeField(default='08:00')
    last_digest_sent_on = models.DateField(null=True, blank=True)

    def __str__(self):
        return f'{self.user.username} notifications'


class RecurringTopic(models.Model):
    """Template for generating recurring study topics."""
    FREQUENCY_CHOICES = [
        ('daily', 'Daily'),
        ('weekly', 'Weekly'),
        ('biweekly', 'Bi-weekly'),
        ('monthly', 'Monthly'),
    ]

    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='recurring_topics')
    subject = models.CharField(max_length=80)
    topic_template = models.CharField(max_length=150)
    exam_date_offset_days = models.PositiveIntegerField(default=7)  # days from creation
    frequency = models.CharField(max_length=10, choices=FREQUENCY_CHOICES, default='weekly')
    priority = models.IntegerField(choices=StudyTopic.PRIORITY_CHOICES, default=1)
    tags = models.ManyToManyField(Tag, blank=True)
    notes = models.TextField(blank=True, default='')
    is_active = models.BooleanField(default=True)
    last_generated = models.DateField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return f'{self.subject}: {self.topic_template} ({self.get_frequency_display()})'

    def generate_next(self):
        """Generate the next StudyTopic from this template."""
        from django.utils import timezone
        from datetime import timedelta

        if not self.is_active:
            return None

        today = timezone.localdate()
        intervals = {
            'daily': timedelta(days=1),
            'weekly': timedelta(days=7),
            'biweekly': timedelta(days=14),
            'monthly': timedelta(days=30),
        }
        interval = intervals.get(self.frequency, timedelta(days=7))
        if self.last_generated and today - self.last_generated < interval:
            return None

        next_exam = today + timedelta(days=self.exam_date_offset_days)

        topic = StudyTopic.objects.create(
            user=self.user,
            subject=self.subject,
            topic=self.topic_template,
            exam_date=next_exam,
            priority=self.priority,
            notes=self.notes,
        )
        topic.tags.set(self.tags.all())

        self.last_generated = today
        self.save(update_fields=['last_generated'])

        return topic


# ===== Gamification Models =====

class UserProfile(models.Model):
    """Extended user profile with gamification data."""
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='profile')
    
    # XP & Level
    xp = models.PositiveIntegerField(default=0)
    level = models.PositiveIntegerField(default=1)
    xp_for_next_level = models.PositiveIntegerField(default=100)
    
    # Streaks
    current_streak = models.PositiveIntegerField(default=0)
    longest_streak = models.PositiveIntegerField(default=0)
    last_activity_date = models.DateField(null=True, blank=True)
    
    # Stats
    total_topics_completed = models.PositiveIntegerField(default=0)
    total_study_minutes = models.PositiveIntegerField(default=0)
    perfect_days = models.PositiveIntegerField(default=0)  # days with all topics completed
    
    # Preferences
    daily_goal_minutes = models.PositiveIntegerField(default=30)
    weekly_goal_topics = models.PositiveIntegerField(default=5)
    timezone = models.CharField(max_length=50, default='Asia/Kolkata')
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        ordering = ['-xp']
    
    def __str__(self):
        return f'{self.user.username} - Level {self.level} ({self.xp} XP)'
    
    @property
    def xp_progress_percent(self):
        return round((self.xp / self.xp_for_next_level) * 100, 1)
    
    @classmethod
    def get_or_create_for_user(cls, user):
        profile, _ = cls.objects.get_or_create(user=user)
        return profile
    
    def add_xp(self, amount, reason=''):
        """Add XP and check for level up."""
        self.xp += amount
        leveled_up = False
        while self.xp >= self.xp_for_next_level:
            self.xp -= self.xp_for_next_level
            self.level += 1
            self.xp_for_next_level = int(self.xp_for_next_level * 1.5)  # Increasing XP requirement
            leveled_up = True
        self.save()
        return leveled_up
    
    def update_streak(self):
        """Update streak based on last activity."""
        from django.utils import timezone
        from datetime import timedelta
        
        today = timezone.localdate()
        if self.last_activity_date:
            if self.last_activity_date == today:
                return  # already updated today
            elif self.last_activity_date == today - timedelta(days=1):
                self.current_streak += 1
            else:
                self.current_streak = 1
        else:
            self.current_streak = 1
        
        if self.current_streak > self.longest_streak:
            self.longest_streak = self.current_streak
        
        self.last_activity_date = today
        self.save()


class Achievement(models.Model):
    """Define available achievements/badges."""
    ACHIEVEMENT_TYPES = [
        ('streak', 'Streak'),
        ('completion', 'Completion'),
        ('time', 'Study Time'),
        ('subject', 'Subject Mastery'),
        ('priority', 'Priority Master'),
        ('social', 'Social'),
        ('special', 'Special'),
    ]
    
    RARITY_CHOICES = [
        ('common', 'Common'),
        ('uncommon', 'Uncommon'),
        ('rare', 'Rare'),
        ('epic', 'Epic'),
        ('legendary', 'Legendary'),
    ]
    
    code = models.CharField(max_length=50, unique=True)  # e.g., 'streak_7', 'first_completion'
    name = models.CharField(max_length=100)
    description = models.TextField()
    type = models.CharField(max_length=20, choices=ACHIEVEMENT_TYPES)
    rarity = models.CharField(max_length=15, choices=RARITY_CHOICES, default='common')
    icon = models.CharField(max_length=10, default='🏆')  # emoji or icon class
    xp_reward = models.PositiveIntegerField(default=0)
    
    # Conditions (JSON for flexibility)
    condition = models.JSONField(default=dict, help_text='Condition to unlock, e.g., {"streak_days": 7}')
    
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        ordering = ['type', 'rarity', 'name']
    
    def __str__(self):
        return f'{self.name} ({self.get_rarity_display()})'


class UserAchievement(models.Model):
    """Track user's earned achievements."""
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='achievements')
    achievement = models.ForeignKey(Achievement, on_delete=models.CASCADE, related_name='user_achievements')
    earned_at = models.DateTimeField(auto_now_add=True)
    progress = models.JSONField(default=dict, help_text='Progress toward achievement')
    
    class Meta:
        unique_together = ['user', 'achievement']
        ordering = ['-earned_at']
    
    def __str__(self):
        return f'{self.user.username} - {self.achievement.name}'


class DailyGoal(models.Model):
    """Daily goals for users."""
    GOAL_TYPES = [
        ('minutes', 'Study Minutes'),
        ('topics', 'Topics Completed'),
        ('sessions', 'Sessions Completed'),
    ]
    
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='daily_goals')
    date = models.DateField()
    goal_type = models.CharField(max_length=15, choices=GOAL_TYPES)
    target = models.PositiveIntegerField()
    current = models.PositiveIntegerField(default=0)
    completed = models.BooleanField(default=False)
    xp_reward = models.PositiveIntegerField(default=10)
    
    class Meta:
        unique_together = ['user', 'date', 'goal_type']
        ordering = ['-date']
    
    def __str__(self):
        return f'{self.user.username} - {self.date} - {self.get_goal_type_display()}'
    
    @property
    def progress_percent(self):
        return min(100, round((self.current / self.target) * 100, 1)) if self.target > 0 else 0
    
    def add_progress(self, amount):
        self.current = min(self.target, self.current + amount)
        if self.current >= self.target and not self.completed:
            self.completed = True
            # Award XP
            profile = UserProfile.get_or_create_for_user(self.user)
            profile.add_xp(self.xp_reward, f'Daily goal: {self.get_goal_type_display()}')
        self.save()
        return self.completed


class WeeklyGoal(models.Model):
    """Weekly goals for users."""
    GOAL_TYPES = [
        ('topics', 'Topics Completed'),
        ('minutes', 'Study Minutes'),
        ('streak', 'Maintain Streak'),
        ('sessions', 'Sessions Completed'),
    ]
    
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='weekly_goals')
    week_start = models.DateField()  # Monday of the week
    goal_type = models.CharField(max_length=15, choices=GOAL_TYPES)
    target = models.PositiveIntegerField()
    current = models.PositiveIntegerField(default=0)
    completed = models.BooleanField(default=False)
    xp_reward = models.PositiveIntegerField(default=50)
    
    class Meta:
        unique_together = ['user', 'week_start', 'goal_type']
        ordering = ['-week_start']
    
    def __str__(self):
        return f'{self.user.username} - Week of {self.week_start} - {self.get_goal_type_display()}'
    
    @property
    def progress_percent(self):
        return min(100, round((self.current / self.target) * 100, 1)) if self.target > 0 else 0


class Leaderboard(models.Model):
    """Leaderboard snapshots for different categories."""
    CATEGORY_CHOICES = [
        ('xp', 'Total XP'),
        ('level', 'Level'),
        ('streak', 'Current Streak'),
        ('topics', 'Topics Completed'),
        ('minutes', 'Study Minutes'),
        ('weekly_xp', 'Weekly XP'),
    ]
    
    PERIOD_CHOICES = [
        ('all_time', 'All Time'),
        ('weekly', 'Weekly'),
        ('monthly', 'Monthly'),
    ]
    
    category = models.CharField(max_length=20, choices=CATEGORY_CHOICES)
    period = models.CharField(max_length=15, choices=PERIOD_CHOICES, default='all_time')
    period_start = models.DateField(null=True, blank=True)  # for weekly/monthly
    period_end = models.DateField(null=True, blank=True)
    
    # Top 10 stored as JSON for quick retrieval
    rankings = models.JSONField(default=list)  # [{rank, user_id, username, value}, ...]
    
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        unique_together = ['category', 'period', 'period_start']
        ordering = ['category', 'period', '-period_start']
    
    def __str__(self):
        return f'{self.get_category_display()} - {self.get_period_display()}'


class StudyChallenge(models.Model):
    """Time-limited study challenges."""
    CHALLENGE_TYPES = [
        ('complete_topics', 'Complete N Topics'),
        ('study_minutes', 'Study N Minutes'),
        ('maintain_streak', 'Maintain Streak for N Days'),
        ('all_high_priority', 'Complete All High Priority'),
        ('subject_mastery', 'Complete N Topics in Subject'),
    ]
    
    name = models.CharField(max_length=100)
    description = models.TextField()
    type = models.CharField(max_length=30, choices=CHALLENGE_TYPES)
    
    # Challenge parameters
    target = models.PositiveIntegerField()
    subject = models.CharField(max_length=80, blank=True)  # for subject-specific
    
    # Rewards
    xp_reward = models.PositiveIntegerField(default=100)
    badge_reward = models.ForeignKey(Achievement, on_delete=models.SET_NULL, null=True, blank=True)
    
    # Timing
    starts_at = models.DateTimeField()
    ends_at = models.DateTimeField()
    is_active = models.BooleanField(default=True)
    
    # Participants
    participants = models.ManyToManyField(User, through='ChallengeParticipant', related_name='challenges')
    
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        ordering = ['-starts_at']
    
    def __str__(self):
        return f'{self.name} ({self.get_type_display()})'
    
    @property
    def is_running(self):
        from django.utils import timezone
        now = timezone.now()
        return self.is_active and self.starts_at <= now <= self.ends_at


class ChallengeParticipant(models.Model):
    """Track user progress in challenges."""
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='challenge_participations')
    challenge = models.ForeignKey(StudyChallenge, on_delete=models.CASCADE, related_name='challenge_participants')
    joined_at = models.DateTimeField(auto_now_add=True)
    progress = models.PositiveIntegerField(default=0)
    completed = models.BooleanField(default=False)
    completed_at = models.DateTimeField(null=True, blank=True)
    reward_claimed = models.BooleanField(default=False)
    
    class Meta:
        unique_together = ['user', 'challenge']
        ordering = ['-joined_at']
    
    def __str__(self):
        return f'{self.user.username} - {self.challenge.name} ({self.progress}/{self.challenge.target})'
    
    @property
    def progress_percent(self):
        return min(100, round((self.progress / self.challenge.target) * 100, 1)) if self.challenge.target > 0 else 0
    
    def add_progress(self, amount):
        self.progress = min(self.challenge.target, self.progress + amount)
        if self.progress >= self.challenge.target and not self.completed:
            self.completed = True
            from django.utils import timezone
            self.completed_at = timezone.now()
        self.save()
        return self.completed


# Signal to auto-create UserProfile when User is created
from django.db.models.signals import post_save
from django.dispatch import receiver

@receiver(post_save, sender=User)
def create_user_profile(sender, instance, created, **kwargs):
    if created:
        UserProfile.objects.get_or_create(user=instance)

@receiver(post_save, sender=User)
def save_user_profile(sender, instance, **kwargs):
    if hasattr(instance, 'profile'):
        instance.profile.save()
