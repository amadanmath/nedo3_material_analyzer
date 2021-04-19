import uuid
from django.db import models
from django.contrib.auth.models import User


MAX_ACTION_LENGTH=30
MAX_SERVER_ID_LENGTH=20


class Job(models.Model):
    WAITING = 'W'    # the worker is not booted up yet
    QUEUED = 'Q'     # submitted to the worker
    STARTED = 'S'    # worker started working on it
    FINISHED = 'F'   # the results are in
    ERROR = 'E'      # something went wrong, details in `.ann`
    STATE_CHOICES = [
        (WAITING, 'Waiting'),
        (QUEUED, 'Queued'),
        (STARTED, 'Started'),
        (FINISHED, 'Finished'),
        (ERROR, 'Error'),
    ]
    STATE_CHOICES_DICT = dict(STATE_CHOICES)

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='jobs')
    submitted_at = models.DateTimeField(auto_now_add=True)
    started_at = models.DateTimeField(null=True)
    finished_at = models.DateTimeField(null=True)
    state = models.CharField(max_length=1, choices=STATE_CHOICES, default=QUEUED)
    viewed = models.BooleanField(default=False)
    action = models.CharField(max_length=MAX_ACTION_LENGTH)
    txt = models.TextField()
    ann = models.TextField(null=True, blank=True)
    visual_conf = models.TextField(null=True, blank=True)

    class Meta:
        indexes = [
            # finished count per user, get waiting
            models.Index(fields=['state', 'user']),
            # list
            models.Index(fields=['user', 'submitted_at']),
        ]


class BootingServer(models.Model):
    id = models.CharField(max_length=MAX_SERVER_ID_LENGTH, primary_key=True, editable=False)
    booted_at = models.DateTimeField(auto_now_add=True)
