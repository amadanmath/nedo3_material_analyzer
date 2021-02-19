import json
import threading
from django.conf import settings
from django.contrib.auth import authenticate
from channels.auth import login, logout
from channels.generic.websocket import AsyncJsonWebsocketConsumer
from django.core.paginator import Paginator
from channels.db import database_sync_to_async
from asgiref.sync import sync_to_async, async_to_sync
from traceback import format_exc
import asyncio
import logging
import websockets
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
    return dt.replace(tzinfo=timezone.utc).timestamp()

@database_sync_to_async
def get_paginated_jobs(user, page):
    jobs = Job.objects.filter(user=user).order_by("-started_at")
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
                    "started_at": epoch(job.started_at),
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
    return "user:{}".format(username)



class BratConsumer(AsyncJsonWebsocketConsumer):
    async def connect(self):
        await self.accept()
        user = self.scope["user"]
        if user.is_authenticated:
            self.channel_layer.group_add(user_group_name(user.username), self.channel_name)
            count = await database_sync_to_async(Job.objects.filter(user=user, state=Job.FINISHED, viewed=False).count)()
        else:
            count = 0
        await self.send(json.dumps({
            "type": "hello",
            "user": user.is_authenticated and user.username,
            "count": count,
        }))

    async def disconnect(self, close_code):
        user = self.scope["user"]
        self.channel_layer.group_discard(user_group_name(user.username), self.channel_name)
        pass

    # get data from websocket
    async def receive_json(self, content):
        user = self.scope["user"]
        req_type = content.get("type")

        if req_type == "login":
            user = await database_sync_to_async(authenticate)(
                username=content["username"],
                password=content["password"],
            )
            if user:
                await login(self.scope, user)
                self.scope["session"].modified = True
                await database_sync_to_async(self.scope["session"].save)()
                self.channel_layer.group_add(user_group_name(user.username), self.channel_name)
                count = await database_sync_to_async(Job.objects.filter(user=user, state=Job.FINISHED, viewed=False).count)()
                await self.send_json({
                    "type": "hello",
                    "user": user.username,
                    "count": count,
                })
            else:
                await self.send_json({
                    "type": "loginFailed",
                })


        elif not user.is_authenticated:
            await self.send_json({
                "error": "Not authenticated",
            })
        # from django.contrib.auth.models import User
        # user = database_sync_to_async(User.objects.first)()
        # if False:
        #     pass
        # # DEBUG


        elif req_type == "analyze":
            text = content['text']
            action = content['action']
            url = workers[action]["url"]
            # TODO REMOVE

            threading.Thread(target=asyncio.run, args=(self.analyze_and_respond(
                text, action, url
            ),)).start()


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
                await self.send_json({
                    "type": "viewed",
                    "id": str(job.id),
                })

        else:
            logger.error("Bad message type: {}".format(req_type))

        # await self.send_json({
        #     **result,
        #     'scope': self.scope,
        # }, default=lambda o: o.decode() if isinstance(o, bytes) else f"<#{type(o).__name__}>")

    async def analyze_and_respond(self, text, action, url):
        user = self.scope["user"]
        error = None
        job = None

        try:
            job = await database_sync_to_async(Job.objects.create)(
                user=user,
                action=action,
                txt=text,
            )

            logger.critical("got job")
            await self.send_json({
                "type": "changed",
                "state": job.state,
                "id": str(job.id),
            })

            async with websockets.connect(url) as worker_ws:
                await worker_ws.send(json.dumps({ 'text': text }))
                result = json.loads(await worker_ws.recv())

            if "error" in result:
                error = "[{action}]: {error}".format(action=action, error=result.pop("error"))

        except:
            error = format_exc()

        if job:
            if error:
                logger.error(error)
                job.ann = error
                job.state = Job.ERROR

            else:
                job.txt = result["txt"]
                job.ann = result["ann"]
                job.visual_conf = result["visual_conf"]
                job.state = Job.FINISHED

            await database_sync_to_async(job.save)()
            await self.send_json({
                "type": "changed",
                "id": str(job.id),
                "state": job.state,
                # DEBUG
                # "error": job.ann if job.state == Job.ERROR else None
            })
