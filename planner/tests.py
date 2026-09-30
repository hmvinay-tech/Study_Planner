from django.test import Client, TestCase
from .models import StudyTopic


class PlannerTests(TestCase):
    def test_study_workflow(self):
        self.client.post('/', {'subject': 'Python', 'topic': 'Functions', 'exam_date': '2026-10-15'})
        topic = StudyTopic.objects.get()
        self.assertContains(self.client.get('/'), 'Functions')
        self.client.post(f'/complete/{topic.pk}/')
        topic.refresh_from_db()
        self.assertTrue(topic.completed)
        self.client.post(f'/complete/{topic.pk}/')
        topic.refresh_from_db()
        self.assertFalse(topic.completed)
        self.client.post(f'/delete/{topic.pk}/')
        self.assertEqual(StudyTopic.objects.count(), 0)

    def test_invalid_inputs(self):
        for data in [
            {'subject': ' ', 'topic': 'Loops', 'exam_date': '2026-10-15'},
            {'subject': 'Python', 'topic': 'Loops', 'exam_date': 'not-a-date'},
            {'subject': 'Python', 'topic': 'x' * 151, 'exam_date': '2026-10-15'},
        ]:
            response = self.client.post('/', data)
            self.assertTrue(response.context['form'].errors)
        self.assertEqual(StudyTopic.objects.count(), 0)

    def test_exam_order_and_escaping(self):
        later = StudyTopic.objects.create(subject='Maths', topic='Algebra', exam_date='2026-11-01')
        sooner = StudyTopic.objects.create(subject='Python', topic='<script>alert(1)</script>', exam_date='2026-10-01')
        self.assertEqual(list(StudyTopic.objects.all()), [sooner, later])
        response = self.client.get('/')
        self.assertNotContains(response, '<script>alert(1)</script>')
        self.assertContains(response, '&lt;script&gt;')

    def test_actions_require_post_and_csrf(self):
        topic = StudyTopic.objects.create(subject='Python', topic='Loops', exam_date='2026-10-15')
        for action in ['complete', 'delete']:
            url = f'/{action}/{topic.pk}/'
            self.assertEqual(self.client.get(url).status_code, 405)
            self.assertEqual(Client(enforce_csrf_checks=True).post(url).status_code, 403)

    def test_missing_topic(self):
        self.assertEqual(self.client.post('/complete/999/').status_code, 404)
