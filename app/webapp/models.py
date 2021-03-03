import uuid
from django.db import models
from django.contrib.auth.models import User


MAX_ACTION_LENGTH=30


class Job(models.Model):
    QUEUED = 'Q'
    STARTED = 'S'
    FINISHED = 'F'
    ERROR = 'E'
    STATE_CHOICES = [
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

    def state_name(self):
        return self.STATE_CHOICES_DICT[self.state]

    def is_finished(self):
        return self.state == self.FINISHED

    def duration(self):
        if not self.finished_at:
            return None
        return (self.finished_at - self.started_at).total_seconds()

    @classmethod
    def new_count(cls, user):
        return cls.objects.filter(
                user=user,
                state=Job.FINISHED,
                viewed=False,
            ).count()

    class Meta:
        indexes = [
            models.Index(fields=['user', 'state']),
            models.Index(fields=['submitted_at']),
        ]
