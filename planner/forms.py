from django import forms
from .models import StudyTopic


class StudyTopicForm(forms.ModelForm):
    class Meta:
        model = StudyTopic
        fields = ['subject', 'topic', 'exam_date']
        widgets = {'exam_date': forms.DateInput(attrs={'type': 'date'})}
