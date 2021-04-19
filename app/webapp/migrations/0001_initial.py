# Generated by Django 3.1.7 on 2021-03-05 06:36

from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion
import uuid


class Migration(migrations.Migration):

    initial = True

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name='BootingServer',
            fields=[
                ('id', models.CharField(editable=False, max_length=20, primary_key=True, serialize=False)),
                ('booted_at', models.DateTimeField(auto_now_add=True)),
            ],
        ),
        migrations.CreateModel(
            name='Job',
            fields=[
                ('id', models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ('submitted_at', models.DateTimeField(auto_now_add=True)),
                ('started_at', models.DateTimeField(null=True)),
                ('finished_at', models.DateTimeField(null=True)),
                ('state', models.CharField(choices=[('W', 'Waiting'), ('Q', 'Queued'), ('S', 'Started'), ('F', 'Finished'), ('E', 'Error')], default='Q', max_length=1)),
                ('viewed', models.BooleanField(default=False)),
                ('action', models.CharField(max_length=30)),
                ('txt', models.TextField()),
                ('ann', models.TextField(blank=True, null=True)),
                ('visual_conf', models.TextField(blank=True, null=True)),
                ('user', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='jobs', to=settings.AUTH_USER_MODEL)),
            ],
        ),
        migrations.AddIndex(
            model_name='job',
            index=models.Index(fields=['state', 'user'], name='webapp_job_state_d41469_idx'),
        ),
        migrations.AddIndex(
            model_name='job',
            index=models.Index(fields=['user', 'submitted_at'], name='webapp_job_user_id_cb166d_idx'),
        ),
    ]