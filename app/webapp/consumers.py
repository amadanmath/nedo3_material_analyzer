import json
from django.conf import settings
from django.contrib.auth import authenticate
from channels.auth import login, logout
from channels.generic.websocket import AsyncJsonWebsocketConsumer
from django.core.paginator import Paginator
from channels.db import database_sync_to_async
from asgiref.sync import sync_to_async, async_to_sync
from traceback import format_exc
import logging
import requests
from datetime import timezone

from webapp.models import Job

from brat.conf import parse_visual_conf, add_defaults
from brat.json import get_doc_json, get_coll_json
from brat.annotation import TextAnnotations




PAGE_SIZE = 10

workers = {
    worker['id']: worker
    for worker in settings.WORKERS
}

logger = logging.getLogger(__name__)



def epoch(dt):
    return dt.replace(tzinfo=timezone.utc).timestamp() if dt else None

@database_sync_to_async
def get_paginated_jobs(user, page):
    jobs = Job.objects.filter(user=user).order_by("-submitted_at")
    paginator = Paginator(jobs, PAGE_SIZE)
    try:
        paginated_jobs = paginator.page(page)
        return {
            "prev": paginated_jobs.has_previous() and paginated_jobs.previous_page_number() or None,
            "curr": page,
            "next": paginated_jobs.has_next() and paginated_jobs.next_page_number() or None,
            "maxpage": paginator.num_pages,
            "data": [{
                    "id": str(job.id),
                    "submitted_at": epoch(job.submitted_at),
                    "started_at": epoch(job.started_at),
                    "finished_at": epoch(job.finished_at),
                    "state": job.state,
                    "viewed": job.viewed,
                    "action": job.action,
                    "txt": job.txt,
                } for job in paginated_jobs.object_list
            ],
        }
    except paginator.EmptyPage:
        return {
            "error": "Out of range",
        }


def user_group_name(username):
    return "user.{}".format(username)



class BratConsumer(AsyncJsonWebsocketConsumer):
    async def connect(self):
        await self.accept()
        user = self.scope["user"]
        if user.is_authenticated:
            await self.channel_layer.group_add(user_group_name(user.username), self.channel_name)

    async def disconnect(self, close_code):
        user = self.scope["user"]
        await self.channel_layer.group_discard(user_group_name(user.username), self.channel_name)
        pass

    # get data from websocket
    async def receive_json(self, content):
        user = self.scope["user"]
        req_type = content.get("type")

        if not user.is_authenticated:
            await self.send_json({
                "error": "Not authenticated",
            })

        elif req_type == "analyze":
            text = content['text']
            action = content['action']
            user = self.scope["user"]
            error = None
            job = None

            try:
                url = workers[action]["url"]
                job = await database_sync_to_async(Job.objects.create)(
                    user=user,
                    action=action,
                    txt=text,
                )

                r = requests.post(url, data={
                    "job": str(job.id),
                    "text": text,
                })

                if r.status_code != 202:
                    error = f"Status code {r.status_code}\n\n{response.text}"

            except requests.exceptions.ConnectionError:
                error = format_exc()

            if job:
                if error:
                    job.ann = error
                    job.state = Job.ERROR
                    await database_sync_to_async(job.save)()

                group_name = user_group_name(user.username)
                await self.channel_layer.group_send(group_name, {
                    "type": "update",
                    "msg_type": "changed",
                    "id": str(job.id),
                    "state": job.state,
                })


        elif req_type == "list":
            page = int(content["page"])
            payload = await get_paginated_jobs(user, page)
            await self.send_json({
                "type": "list",
                **payload,
            })


        elif req_type == "show":
            error = None
            job_id = content["id"]
            try:
                job = await database_sync_to_async(Job.objects.get)(pk=job_id)
            except Job.DoesNotExist:
                error = "notfound"

            if job and job.state == Job.ERROR:
                error = "error"

            if error:
                payload = {
                    "error": error,
                }

            else:
                visual_conf = parse_visual_conf(job.visual_conf)
                doc = TextAnnotations(text=job.txt, source=job.ann)
                specific_visual_conf = add_defaults(visual_conf, doc)
                doc_json = get_doc_json(doc)
                coll_json = get_coll_json(specific_visual_conf)
                payload = {
                    "action": job.action,
                    "doc": doc_json,
                    "coll": coll_json,
                }

            await self.send_json({
                "type": "show",
                "id": str(job.id),
                **payload,
            })

            if job and not job.viewed:
                job.viewed = True
                await database_sync_to_async(job.save)()
                group_name = user_group_name(user.username)
                await self.channel_layer.group_send(group_name, {
                    "type": "update",
                    "msg_type": "viewed",
                    "id": str(job.id),
                })

        else:
            logger.error("Bad message type: {}".format(req_type))


    async def update(self, event):
        event = dict(event)
        msg_type = event.pop("msg_type")
        import sys; print("type:", msg_type, "evt:", type(event), event, file=sys.stderr)
        await self.send_json({
            **event,
            "type": msg_type,
        })
