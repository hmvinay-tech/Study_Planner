from django.contrib import messages
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.views.decorators.http import require_POST, require_http_methods
from .forms import StudyTopicForm
from .models import StudyTopic


# Shared page data: the list, form, and progress counts.
def show_planner(request, form=None):
    topics = StudyTopic.objects.all()
    total = topics.count()
    finished = topics.filter(completed=True).count()
    return render(request, 'planner/home.html', {
        'form': form if form is not None else StudyTopicForm(),
        'topics': topics, 'total': total, 'finished': finished,
        'pending': total - finished, 'today': timezone.localdate(),
    })


@require_http_methods(['GET', 'POST'])
def home(request):
    if request.method == 'POST':
        form = StudyTopicForm(request.POST)
        if form.is_valid():
            form.save()
            messages.success(request, 'Study topic added.')
            return redirect('home')
        return show_planner(request, form=form)
    return show_planner(request)


@require_POST
def complete_topic(request, pk):
    topic = get_object_or_404(StudyTopic, pk=pk)
    topic.completed = not topic.completed
    topic.save()
    return redirect('home')


@require_POST
def delete_topic(request, pk):
    topic = get_object_or_404(StudyTopic, pk=pk)
    topic.delete()
    messages.success(request, 'Study topic deleted.')
    return redirect('home')

