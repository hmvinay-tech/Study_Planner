from django import forms
from .models import StudyTopic, Tag, StudySession, NotificationPreference, RecurringTopic, TopicTemplate


class StudyTopicFilterForm(forms.Form):
    STATUS_CHOICES = [
        ('', 'Any status'),
        ('pending', 'To study'),
        ('completed', 'Completed'),
        ('overdue', 'Overdue'),
    ]

    q = forms.CharField(required=False, label='Search', widget=forms.TextInput(attrs={'placeholder': 'Subject, topic, or notes'}))
    priority = forms.ChoiceField(
        required=False,
        label='Priority',
        choices=[('', 'Any priority')] + [(str(value), label) for value, label in StudyTopic.PRIORITY_CHOICES],
    )
    status = forms.ChoiceField(required=False, label='Status', choices=STATUS_CHOICES)
    tag = forms.ModelChoiceField(required=False, label='Tag', queryset=Tag.objects.all(), empty_label='Any tag')
    exam_date_from = forms.DateField(required=False, label='Exam date from', widget=forms.DateInput(attrs={'type': 'date'}))
    exam_date_to = forms.DateField(required=False, label='Exam date to', widget=forms.DateInput(attrs={'type': 'date'}))


class StudyTopicForm(forms.ModelForm):
    tags = forms.ModelMultipleChoiceField(
        queryset=Tag.objects.all(),
        widget=forms.CheckboxSelectMultiple,
        required=False,
    )

    class Meta:
        model = StudyTopic
        fields = ['subject', 'topic', 'exam_date', 'priority', 'tags', 'notes']
        widgets = {
            'exam_date': forms.DateInput(attrs={'type': 'date'}),
            'priority': forms.Select(attrs={'class': 'priority-select'}),
            'notes': forms.Textarea(attrs={'rows': 3, 'placeholder': 'Optional notes, links, or reminders…'}),
        }


class TagForm(forms.ModelForm):
    class Meta:
        model = Tag
        fields = ['name', 'color']
        widgets = {
            'color': forms.TextInput(attrs={'type': 'color'}),
        }


class StudySessionForm(forms.ModelForm):
    class Meta:
        model = StudySession
        fields = ['topic', 'subject', 'notes']
        widgets = {
            'topic': forms.Select(attrs={'class': 'topic-select'}),
            'subject': forms.TextInput(attrs={'placeholder': 'Subject (auto-filled from topic)'}),
            'notes': forms.Textarea(attrs={'rows': 2, 'placeholder': 'What did you study?'}),
        }

    def __init__(self, *args, **kwargs):
        user = kwargs.pop('user', None)
        super().__init__(*args, **kwargs)
        if user:
            self.fields['topic'].queryset = StudyTopic.objects.filter(user=user, completed=False)


class NotificationPreferenceForm(forms.ModelForm):
    class Meta:
        model = NotificationPreference
        fields = ['email_enabled', 'email_frequency', 'remind_before_days', 'notify_on_due', 'notify_overdue', 'daily_digest_time']
        widgets = {
            'daily_digest_time': forms.TimeInput(attrs={'type': 'time'}),
            'remind_before_days': forms.NumberInput(attrs={'min': 0, 'max': 30}),
        }


class RecurringTopicForm(forms.ModelForm):
    tags = forms.ModelMultipleChoiceField(
        queryset=Tag.objects.all(),
        widget=forms.CheckboxSelectMultiple,
        required=False,
    )

    class Meta:
        model = RecurringTopic
        fields = ['subject', 'topic_template', 'exam_date_offset_days', 'frequency', 'priority', 'tags', 'notes']
        widgets = {
            'topic_template': forms.TextInput(attrs={'placeholder': 'e.g., "Review {date} - Chapter 1"'}),
            'exam_date_offset_days': forms.NumberInput(attrs={'min': 1, 'max': 365}),
            'frequency': forms.Select(),
            'priority': forms.Select(),
            'notes': forms.Textarea(attrs={'rows': 2, 'placeholder': 'Optional notes…'}),
        }


class TopicTemplateForm(forms.ModelForm):
    default_tags = forms.ModelMultipleChoiceField(
        queryset=Tag.objects.all(),
        widget=forms.CheckboxSelectMultiple,
        required=False,
    )

    class Meta:
        model = TopicTemplate
        fields = ['name', 'description', 'subject', 'topic', 'default_priority', 'default_tags', 'default_notes', 'exam_date_offset_days']
        widgets = {
            'name': forms.TextInput(attrs={'placeholder': 'e.g., "Weekly Review Template"'}),
            'description': forms.Textarea(attrs={'rows': 2, 'placeholder': 'What is this template for?'}),
            'topic': forms.TextInput(attrs={'placeholder': 'e.g., "Weekly Review {date}"'}),
            'default_priority': forms.Select(),
            'default_notes': forms.Textarea(attrs={'rows': 3, 'placeholder': 'Default notes'}),
            'exam_date_offset_days': forms.NumberInput(attrs={'min': 1, 'max': 365}),
        }
