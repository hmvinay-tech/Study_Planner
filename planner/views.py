from django.contrib import messages
from django.contrib.auth import login, logout
from django.contrib.auth.decorators import login_required
from django.contrib.auth.forms import UserCreationForm, AuthenticationForm
from django.db.models import Q, Sum
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.views.decorators.http import require_POST, require_http_methods

from .forms import StudyTopicFilterForm, StudyTopicForm, TagForm, StudySessionForm, NotificationPreferenceForm, RecurringTopicForm, TopicTemplateForm
from .models import StudyTopic, Tag, StudySession, NotificationPreference, RecurringTopic, UserProfile, TopicTemplate


# Shared page data: the list, form, and progress counts.
def get_user_topics(user):
    return StudyTopic.objects.filter(user=user).select_related('user').prefetch_related('tags')


def filter_user_topics(request, user):
    """Apply the planner's safe, optional search and filter parameters."""
    topics = get_user_topics(user)
    filter_form = StudyTopicFilterForm(request.GET or None)
    if filter_form.is_valid():
        filters = filter_form.cleaned_data
        if filters['q']:
            topics = topics.filter(
                Q(subject__icontains=filters['q'])
                | Q(topic__icontains=filters['q'])
                | Q(notes__icontains=filters['q'])
            )
        if filters['priority']:
            topics = topics.filter(priority=int(filters['priority']))
        if filters['status'] == 'pending':
            topics = topics.filter(completed=False)
        elif filters['status'] == 'completed':
            topics = topics.filter(completed=True)
        elif filters['status'] == 'overdue':
            topics = topics.filter(completed=False, exam_date__lt=timezone.localdate())
        if filters['tag']:
            topics = topics.filter(tags=filters['tag'])
        if filters['exam_date_from']:
            topics = topics.filter(exam_date__gte=filters['exam_date_from'])
        if filters['exam_date_to']:
            topics = topics.filter(exam_date__lte=filters['exam_date_to'])

    return topics.distinct(), {
        'filter_form': filter_form,
        'has_filters': bool(request.GET),
    }


def show_planner(request, form=None):
    all_topics = get_user_topics(request.user)
    topics, filters = filter_user_topics(request, request.user)
    total = all_topics.count()
    finished = all_topics.filter(completed=True).count()
    high_priority_pending = all_topics.filter(completed=False, priority=0).count()
    return render(request, 'planner/home.html', {
        'form': form if form is not None else StudyTopicForm(),
        'topics': topics,
        'shown_count': topics.count(),
        'total': total,
        'finished': finished,
        'pending': total - finished,
        'high_priority_pending': high_priority_pending,
        'today': timezone.localdate(),
        'all_tags': Tag.objects.all(),
        'priority_choices': StudyTopic.PRIORITY_CHOICES,
        **filters,
    })


@require_http_methods(['GET', 'POST'])
@login_required
def home(request):
    if request.method == 'POST':
        form = StudyTopicForm(request.POST)
        if form.is_valid():
            topic = form.save(commit=False)
            topic.user = request.user
            topic.save()
            form.save_m2m()  # save tags
            messages.success(request, 'Study topic added.')
            return redirect('home')
        return show_planner(request, form=form)
    return show_planner(request)


@require_http_methods(['GET', 'POST'])
@login_required
def edit_topic(request, pk):
    topic = get_object_or_404(StudyTopic, pk=pk, user=request.user)
    if request.method == 'POST':
        form = StudyTopicForm(request.POST, instance=topic)
        if form.is_valid():
            form.save()
            messages.success(request, 'Study topic updated.')
            return redirect('home')
    else:
        form = StudyTopicForm(instance=topic)
    return render(request, 'planner/edit_topic.html', {'form': form, 'topic': topic})


@require_POST
@login_required
def complete_topic(request, pk):
    topic = get_object_or_404(StudyTopic, pk=pk, user=request.user)
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
    
    return redirect('home')


@require_POST
@login_required
def delete_topic(request, pk):
    topic = get_object_or_404(StudyTopic, pk=pk, user=request.user)
    topic.delete()
    messages.success(request, 'Study topic deleted.')
    return redirect('home')


@require_http_methods(['GET', 'POST'])
@login_required
def tag_list(request):
    if request.method == 'POST':
        form = TagForm(request.POST)
        if form.is_valid():
            form.save()
            messages.success(request, 'Tag created.')
            return redirect('tag_list')
    else:
        form = TagForm()
    tags = Tag.objects.all()
    return render(request, 'planner/tags.html', {'form': form, 'tags': tags})


@require_POST
@login_required
def delete_tag(request, pk):
    tag = get_object_or_404(Tag, pk=pk)
    tag.delete()
    messages.success(request, 'Tag deleted.')
    return redirect('tag_list')


# Authentication views
def register(request):
    if request.user.is_authenticated:
        return redirect('home')
    if request.method == 'POST':
        form = UserCreationForm(request.POST)
        if form.is_valid():
            user = form.save()
            login(request, user)
            messages.success(request, 'Account created. Welcome!')
            return redirect('home')
    else:
        form = UserCreationForm()
    return render(request, 'registration/register.html', {'form': form})


def login_view(request):
    if request.user.is_authenticated:
        return redirect('home')
    if request.method == 'POST':
        form = AuthenticationForm(request, data=request.POST)
        if form.is_valid():
            user = form.get_user()
            login(request, user)
            messages.success(request, f'Welcome back, {user.username}!')
            return redirect('home')
    else:
        form = AuthenticationForm()
    return render(request, 'registration/login.html', {'form': form})


@require_POST
def logout_view(request):
    logout(request)
    messages.info(request, 'You have been logged out.')
    return redirect('login')


# ===== Study Session Views =====

@login_required
def session_list(request):
    """List study sessions with timer controls."""
    user_sessions = StudySession.objects.filter(user=request.user)
    active_session = user_sessions.filter(ended_at__isnull=True).first()
    sessions = user_sessions[:50]

    if request.method == 'POST':
        form = StudySessionForm(request.POST, user=request.user)
        if form.is_valid():
            session = form.save(commit=False)
            session.user = request.user
            session.subject = session.topic.subject if session.topic else form.cleaned_data['subject']
            session.save()
            messages.success(request, 'Study session started!')
            return redirect('session_list')
    else:
        form = StudySessionForm(user=request.user)

    # Stats for today
    from django.utils import timezone
    from datetime import timedelta
    today = timezone.localdate()
    today_sessions = user_sessions.filter(started_at__date=today)
    today_minutes = today_sessions.aggregate(total=Sum('duration_minutes'))['total'] or 0
    week_ago = today - timedelta(days=6)
    week_sessions = user_sessions.filter(started_at__date__gte=week_ago)
    week_minutes = week_sessions.aggregate(total=Sum('duration_minutes'))['total'] or 0

    return render(request, 'planner/sessions.html', {
        'form': form,
        'sessions': sessions,
        'active_session': active_session,
        'today_minutes': today_minutes,
        'week_minutes': week_minutes,
    })


@require_POST
@login_required
def stop_session(request, pk):
    """Stop an active study session."""
    session = get_object_or_404(StudySession, pk=pk, user=request.user)
    session.stop()
    messages.success(request, f'Session stopped. Duration: {session.duration_minutes} minutes.')
    return redirect('session_list')


@login_required
def session_detail(request, pk):
    """View/edit a study session."""
    session = get_object_or_404(StudySession, pk=pk, user=request.user)
    if request.method == 'POST':
        form = StudySessionForm(request.POST, instance=session, user=request.user)
        if form.is_valid():
            session = form.save(commit=False)
            session.subject = session.topic.subject if session.topic else form.cleaned_data['subject']
            session.save()
            messages.success(request, 'Session updated.')
            return redirect('session_list')
    else:
        form = StudySessionForm(instance=session, user=request.user)
    return render(request, 'planner/session_detail.html', {'form': form, 'session': session})


# ===== Notification Preference Views =====

@login_required
def notification_settings(request):
    """Manage notification preferences."""
    prefs, _ = NotificationPreference.objects.get_or_create(user=request.user)

    if request.method == 'POST':
        form = NotificationPreferenceForm(request.POST, instance=prefs)
        if form.is_valid():
            form.save()
            messages.success(request, 'Notification preferences saved.')
            return redirect('notification_settings')
    else:
        form = NotificationPreferenceForm(instance=prefs)

    # Show upcoming exams that would trigger notifications
    from django.utils import timezone
    from datetime import timedelta
    today = timezone.localdate()
    upcoming = StudyTopic.objects.filter(
        user=request.user,
        completed=False,
        exam_date__gte=today,
        exam_date__lte=today + timedelta(days=prefs.remind_before_days)
    ).order_by('exam_date')

    return render(request, 'planner/notifications.html', {
        'form': form,
        'prefs': prefs,
        'upcoming': upcoming,
    })


# ===== Recurring Topic Views =====

@login_required
def recurring_list(request):
    """Manage recurring topic templates."""
    if request.method == 'POST':
        form = RecurringTopicForm(request.POST)
        if form.is_valid():
            recurring = form.save(commit=False)
            recurring.user = request.user
            recurring.save()
            form.save_m2m()
            messages.success(request, 'Recurring topic created.')
            return redirect('recurring_list')
    else:
        form = RecurringTopicForm()

    recurring_topics = RecurringTopic.objects.filter(user=request.user)

    return render(request, 'planner/recurring.html', {
        'form': form,
        'recurring_topics': recurring_topics,
    })


@require_POST
@login_required
def toggle_recurring(request, pk):
    """Activate/deactivate a recurring topic."""
    recurring = get_object_or_404(RecurringTopic, pk=pk, user=request.user)
    recurring.is_active = not recurring.is_active
    recurring.save()
    status = 'activated' if recurring.is_active else 'paused'
    messages.success(request, f'Recurring topic {status}.')
    return redirect('recurring_list')


@require_POST
@login_required
def delete_recurring(request, pk):
    """Delete a recurring topic template."""
    recurring = get_object_or_404(RecurringTopic, pk=pk, user=request.user)
    recurring.delete()
    messages.success(request, 'Recurring topic deleted.')
    return redirect('recurring_list')


@require_POST
@login_required
def generate_recurring(request, pk):
    """Manually generate next topic from recurring template."""
    recurring = get_object_or_404(RecurringTopic, pk=pk, user=request.user)
    topic = recurring.generate_next()
    if topic:
        messages.success(request, f'Generated: {topic}')
    else:
        messages.info(request, 'Already generated for today or inactive.')
    return redirect('recurring_list')


# ===== Topic Template Views =====

@login_required
def template_list(request):
    """Manage topic templates."""
    if request.method == 'POST':
        form = TopicTemplateForm(request.POST)
        if form.is_valid():
            template = form.save(commit=False)
            template.user = request.user
            template.save()
            form.save_m2m()
            messages.success(request, 'Topic template created.')
            return redirect('template_list')
    else:
        form = TopicTemplateForm()

    templates = TopicTemplate.objects.filter(user=request.user).prefetch_related('default_tags')

    return render(request, 'planner/templates.html', {
        'form': form,
        'templates': templates,
    })


@require_POST
@login_required
def delete_template(request, pk):
    """Delete a topic template."""
    template = get_object_or_404(TopicTemplate, pk=pk, user=request.user)
    template.delete()
    messages.success(request, 'Topic template deleted.')
    return redirect('template_list')


@require_POST
@login_required
def create_from_template(request, pk):
    """Create a study topic from a template."""
    template = get_object_or_404(TopicTemplate, pk=pk, user=request.user)
    topic = template.create_topic(request.user)
    messages.success(request, f'Created topic: {topic}')
    return redirect('home')
