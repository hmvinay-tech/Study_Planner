from django.db import models


class StudyTopic(models.Model):
    subject = models.CharField(max_length=80)
    topic = models.CharField(max_length=150)
    exam_date = models.DateField()
    completed = models.BooleanField(default=False)

    class Meta:
        ordering = ['completed', 'exam_date', 'id']

    def __str__(self):
        return f'{self.subject}: {self.topic}'
