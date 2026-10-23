from django.core.management.base import BaseCommand
from planner.models import (
    Achievement, StudyChallenge, UserProfile
)
from django.contrib.auth.models import User
from django.utils import timezone
from datetime import timedelta


class Command(BaseCommand):
    help = 'Initialize default gamification data (achievements, challenges)'

    def handle(self, *args, **options):
        self.stdout.write('Initializing gamification data...')
        
        # Create default achievements
        achievements = [
            # Streak achievements
            {'code': 'streak_3', 'name': 'Getting Started', 'description': 'Maintain a 3-day study streak', 'type': 'streak', 'rarity': 'common', 'icon': 'fire', 'xp_reward': 25, 'condition': {'streak_days': 3}},
            {'code': 'streak_7', 'name': 'Week Warrior', 'description': 'Maintain a 7-day study streak', 'type': 'streak', 'rarity': 'uncommon', 'icon': 'fire', 'xp_reward': 50, 'condition': {'streak_days': 7}},
            {'code': 'streak_14', 'name': 'Fortnight Fighter', 'description': 'Maintain a 14-day study streak', 'type': 'streak', 'rarity': 'rare', 'icon': 'fire', 'xp_reward': 100, 'condition': {'streak_days': 14}},
            {'code': 'streak_30', 'name': 'Monthly Master', 'description': 'Maintain a 30-day study streak', 'type': 'streak', 'rarity': 'epic', 'icon': 'fire', 'xp_reward': 250, 'condition': {'streak_days': 30}},
            {'code': 'streak_100', 'name': 'Centurion', 'description': 'Maintain a 100-day study streak', 'type': 'streak', 'rarity': 'legendary', 'icon': 'fire', 'xp_reward': 1000, 'condition': {'streak_days': 100}},
            
            # Completion achievements
            {'code': 'first_completion', 'name': 'First Steps', 'description': 'Complete your first topic', 'type': 'completion', 'rarity': 'common', 'icon': 'target', 'xp_reward': 10, 'condition': {'topics_completed': 1}},
            {'code': 'completions_10', 'name': 'Decade', 'description': 'Complete 10 topics', 'type': 'completion', 'rarity': 'common', 'icon': 'target', 'xp_reward': 50, 'condition': {'topics_completed': 10}},
            {'code': 'completions_50', 'name': 'Half Century', 'description': 'Complete 50 topics', 'type': 'completion', 'rarity': 'uncommon', 'icon': 'target', 'xp_reward': 150, 'condition': {'topics_completed': 50}},
            {'code': 'completions_100', 'name': 'Centurion Scholar', 'description': 'Complete 100 topics', 'type': 'completion', 'rarity': 'rare', 'icon': 'target', 'xp_reward': 300, 'condition': {'topics_completed': 100}},
            {'code': 'perfect_3', 'name': 'Perfect Three', 'description': 'Have 3 perfect days (all topics completed)', 'type': 'completion', 'rarity': 'uncommon', 'icon': 'star', 'xp_reward': 75, 'condition': {'perfect_days': 3}},
            {'code': 'perfect_7', 'name': 'Perfect Week', 'description': 'Have 7 perfect days', 'type': 'completion', 'rarity': 'rare', 'icon': 'star', 'xp_reward': 200, 'condition': {'perfect_days': 7}},
            
            # Time achievements
            {'code': 'time_60', 'name': 'Hour of Power', 'description': 'Study for 60 total minutes', 'type': 'time', 'rarity': 'common', 'icon': 'clock', 'xp_reward': 25, 'condition': {'study_minutes': 60}},
            {'code': 'time_300', 'name': 'Five Hour Energy', 'description': 'Study for 300 total minutes', 'type': 'time', 'rarity': 'uncommon', 'icon': 'clock', 'xp_reward': 75, 'condition': {'study_minutes': 300}},
            {'code': 'time_1000', 'name': 'Time Lord', 'description': 'Study for 1000 total minutes', 'type': 'time', 'rarity': 'epic', 'icon': 'clock', 'xp_reward': 250, 'condition': {'study_minutes': 1000}},
            
            # Subject mastery
            {'code': 'subject_5', 'name': 'Subject Specialist', 'description': 'Complete 5 topics in a single subject', 'type': 'subject', 'rarity': 'common', 'icon': 'book', 'xp_reward': 30, 'condition': {'subject_topics': 5}},
            {'code': 'subject_20', 'name': 'Subject Master', 'description': 'Complete 20 topics in a single subject', 'type': 'subject', 'rarity': 'rare', 'icon': 'book', 'xp_reward': 150, 'condition': {'subject_topics': 20}},
            
            # Priority
            {'code': 'high_priority_5', 'name': 'Priority One', 'description': 'Complete 5 high-priority topics', 'type': 'priority', 'rarity': 'uncommon', 'icon': 'alert', 'xp_reward': 50, 'condition': {'high_priority_completed': 5}},
            {'code': 'high_priority_20', 'name': 'Crisis Manager', 'description': 'Complete 20 high-priority topics', 'type': 'priority', 'rarity': 'epic', 'icon': 'alert', 'xp_reward': 200, 'condition': {'high_priority_completed': 20}},
            
            # Special
            {'code': 'early_bird', 'name': 'Early Bird', 'description': 'Complete a topic before 8 AM', 'type': 'special', 'rarity': 'uncommon', 'icon': 'sunrise', 'xp_reward': 30, 'condition': {'early_completion': True}},
            {'code': 'night_owl', 'name': 'Night Owl', 'description': 'Complete a topic after 10 PM', 'type': 'special', 'rarity': 'uncommon', 'icon': 'moon', 'xp_reward': 30, 'condition': {'late_completion': True}},
            {'code': 'weekend_warrior', 'name': 'Weekend Warrior', 'description': 'Complete 5 topics on weekends', 'type': 'special', 'rarity': 'rare', 'icon': 'castle', 'xp_reward': 100, 'condition': {'weekend_completions': 5}},
        ]
        
        created_count = 0
        for ach_data in achievements:
            ach, created = Achievement.objects.get_or_create(
                code=ach_data['code'],
                defaults=ach_data
            )
            if created:
                created_count += 1
                self.stdout.write(f'  Created achievement: {ach.name}')
        
        self.stdout.write(self.style.SUCCESS(f'Created {created_count} achievements'))
        
        # Create default challenges
        now = timezone.now()
        challenges = [
            {
                'name': '7-Day Streak Challenge',
                'description': 'Maintain a study streak for 7 consecutive days',
                'type': 'maintain_streak',
                'target': 7,
                'xp_reward': 100,
                'starts_at': now,
                'ends_at': now + timedelta(days=30),
            },
            {
                'name': 'Complete 10 Topics',
                'description': 'Complete 10 study topics this month',
                'type': 'complete_topics',
                'target': 10,
                'xp_reward': 150,
                'starts_at': now,
                'ends_at': now + timedelta(days=30),
            },
            {
                'name': 'Study for 5 Hours',
                'description': 'Accumulate 300 minutes of study time',
                'type': 'study_minutes',
                'target': 300,
                'xp_reward': 100,
                'starts_at': now,
                'ends_at': now + timedelta(days=14),
            },
            {
                'name': 'High Priority Hero',
                'description': 'Complete 5 high-priority topics',
                'type': 'all_high_priority',
                'target': 5,
                'xp_reward': 200,
                'starts_at': now,
                'ends_at': now + timedelta(days=30),
            },
        ]
        
        challenge_created = 0
        for ch_data in challenges:
            ch, created = StudyChallenge.objects.get_or_create(
                name=ch_data['name'],
                defaults=ch_data
            )
            if created:
                challenge_created += 1
                self.stdout.write(f'  Created challenge: {ch.name}')
        
        self.stdout.write(self.style.SUCCESS(f'Created {challenge_created} challenges'))
        
        # Ensure all users have profiles
        for user in User.objects.all():
            UserProfile.objects.get_or_create(user=user)
        
        self.stdout.write(self.style.SUCCESS('Gamification initialization complete!'))