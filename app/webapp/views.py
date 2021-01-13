from django.conf import settings
from django.contrib.auth.decorators import login_required
from django.core.exceptions import ValidationError
from django.core.paginator import Paginator
from django.http import Http404
from django.http import HttpResponse
from django.middleware import csrf
from django.shortcuts import render, redirect
from django.urls import reverse
from django.utils import timezone
from django.utils.datastructures import MultiValueDictKeyError
from django.views.decorators.csrf import csrf_exempt
import requests

from brat.conf import parse_visual_conf, add_defaults
from brat.json import get_doc_json, get_coll_json
from brat.annotation import TextAnnotations

from .models import Job



workers = {
    worker['id']: worker
    for worker in settings.WORKERS
}


@login_required
def index(request):
    return render(request, "webapp/index.html", {
        "workers": settings.WORKERS,
    })


@login_required
def new_count_text(request):
    return HttpResponse(Job.new_count(request.user) or '')


@login_required
def analyze(request):
    text = request.POST['text']
    action = request.POST['action']
    worker = workers[action]
    callback = request.build_absolute_uri(reverse('finalize'))
    error = None

    job = Job.objects.create(
        user=request.user,
        action=action,
        txt=text,
    )

    try:
        r = requests.post(worker['url'], data={
            "job": str(job.id),
            "text": text,
            "callback": callback,
        })

        if r.status_code != 202:
            error = f"Status code {r.status_code}\n\n{response.text}"

    except requests.exceptions.ConnectionError:
        error = format_exc()

    if error:
        job.ann = error
        job.state = Job.ERROR
        job.save()

    return redirect('index')


@csrf_exempt
def finalize(request):
    try:
        job_id = request.POST['job']
        error = request.POST.get('error')
        if not error:
            txt = request.POST['txt']
            ann = request.POST['ann']
            visual_conf = request.POST['visual_conf']
        job = Job.objects.get(pk=job_id)
    except (Job.DoesNotExist, MultiValueDictKeyError):
        # TODO
        from traceback import format_exc
        print(format_exc())

        raise Http404()

    if error:
        job.ann = error
        job.state = Job.ERROR
    else:
        job.txt = txt
        job.ann = ann
        job.visual_conf = visual_conf
        job.state = Job.FINISHED

    job.finished_at = timezone.now()
    job.save()

    return HttpResponse(status=204)


@login_required
def list(request):
    jobs = Job.objects.filter(user=request.user).order_by("-started_at")
    paginator = Paginator(jobs, 25)
    page_number = request.GET.get("page")
    jobs_page = paginator.get_page(page_number)
    return render(request, "webapp/list.html", {
        "jobs_page": jobs_page,
    })


@login_required
def show(request, job_id):
    try:
        job = Job.objects.get(pk=job_id, finished_at__isnull=False)
    except (Job.DoesNotExist, ValidationError):
        raise Http404()

    doc = TextAnnotations(text=job.txt, source=job.ann)
    visual_conf = parse_visual_conf(job.visual_conf)
    specific_visual_conf = add_defaults(visual_conf, doc)

    doc_json = get_doc_json(doc)
    coll_json = get_coll_json(specific_visual_conf)

    if not job.viewed:
        job.viewed = True
        job.save()

    return render(request, 'webapp/show.html', {
        "data": {
            "doc": doc_json,
            "coll": coll_json,
        },
    })
