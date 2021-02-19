from django.conf import settings
from django.shortcuts import render

from .models import Job


def index(request):
    return render(request, "webapp/index.html", {
        "workers": settings.WORKERS,
        "data": {
            "workers": { w["id"]: w["name"] for w in settings.WORKERS },
            "states": Job.STATE_CHOICES_DICT,
        },
    })
