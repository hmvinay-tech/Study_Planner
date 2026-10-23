from django.db import migrations, models


def move_immediate_digests_to_daily(apps, schema_editor):
    NotificationPreference = apps.get_model('planner', 'NotificationPreference')
    NotificationPreference.objects.filter(email_frequency='immediate').update(email_frequency='daily')


class Migration(migrations.Migration):
    dependencies = [('planner', '0007_studytopic_notes_markdown_topictemplate')]

    operations = [
        migrations.RunPython(move_immediate_digests_to_daily, migrations.RunPython.noop),
        migrations.RemoveField(model_name='studytopic', name='notes_markdown'),
        migrations.RemoveField(model_name='topictemplate', name='default_notes_markdown'),
        migrations.AddField(
            model_name='notificationpreference',
            name='last_digest_sent_on',
            field=models.DateField(blank=True, null=True),
        ),
        migrations.AlterField(
            model_name='notificationpreference',
            name='email_frequency',
            field=models.CharField(
                choices=[('none', 'None'), ('daily', 'Daily digest')],
                default='daily',
                max_length=10,
            ),
        ),
    ]
