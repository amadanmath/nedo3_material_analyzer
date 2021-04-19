from django.middleware import csrf
from django.conf import settings
from django.shortcuts import render
from django.utils import timezone
from django.http import Http404, HttpResponse, JsonResponse
from django.utils.datastructures import MultiValueDictKeyError
from django.views.decorators.csrf import csrf_exempt
from django.contrib.auth import authenticate, login, logout
from asgiref.sync import async_to_sync
from channels.layers import get_channel_layer
import re
import logging


from .consumers import user_group_name
from .models import Job


logger = logging.getLogger(__name__)


def index(request):
    index_uri = request.build_absolute_uri()
    ws_uri = re.sub("/$", "", re.sub(r"^https?:", "ws:", index_uri, flags=re.I)) + "/ws/brat/"
    if request.user.is_authenticated:
        count = Job.objects.filter(user=request.user, state=Job.FINISHED, viewed=False).count()
        username = request.user.username
    else:
        count = None
        username = None

    return render(request, "webapp/index.html", {
        "workers": settings.WORKERS,
        "data": {
            "count": count,
            "user": username,
            "workers": { w["id"]: w["name"] for w in settings.WORKERS },
            "states": Job.STATE_CHOICES_DICT,
        },
    })


@csrf_exempt
def update(request):
    try:
        job_id = request.POST["job"]
        logger.error("UPDATE RECEIVED %s", job_id)
        error = request.POST.get("error")
        if not error:
            state = request.POST["state"]
            if state == Job.FINISHED:
                txt = request.POST["txt"]
                ann = request.POST["ann"]
                visual_conf = request.POST["visual_conf"]
            job = Job.objects.get(pk=job_id)
    except (Job.DoesNotExist, MultiValueDictKeyError):
        raise Http404()

    if error:
        job.ann = error
        job.state = Job.ERROR
    else:
        if state == Job.FINISHED:
            job.txt = txt
            job.ann = ann
            job.visual_conf = visual_conf
            job.finished_at = timezone.now()
        elif state == Job.STARTED:
            job.started_at = timezone.now()
        job.state = state

    job.save()

    logger.error("UPDATE SENDING UPDATE TO CHANNEL %s", job_id)
    channel_layer = get_channel_layer()
    group_name = user_group_name(job.user.username)
    async_to_sync(channel_layer.group_send)(group_name, {
        "type": "update",
        "msg_type": "changed",
        "id": job_id,
        "state": job.state,
    })
    logger.error("UPDATE SENT UPDATE TO CHANNEL %s", job_id)
    return HttpResponse(status=204)


def ajax_login(request):
    if not (request.is_ajax and request.method == "POST"):
        raise Http404()

    username = request.POST['username']
    password = request.POST['password']

    user = authenticate(request, username=username, password=password)
    if user is None:
        return JsonResponse({
            "success": False,
        }, status=200)

    else:
        login(request, user)
        count = Job.objects.filter(user=user, state=Job.FINISHED, viewed=False).count()
        return JsonResponse({
            "success": True,
            "user": username,
            "count": count,
            "csrf_token": csrf.get_token(request),
        }, status=200)


def ajax_logout(request):
    if not (request.is_ajax and request.method == "POST"):
        raise Http404()

    logout(request)
    return JsonResponse({
        "csrf_token": csrf.get_token(request),
    }, status=200)
