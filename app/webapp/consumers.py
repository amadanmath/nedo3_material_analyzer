from django.conf import settings
from django.contrib.auth import authenticate
from django.contrib.auth.models import User
from channels.auth import login, logout
from channels.consumer import AsyncConsumer
from channels.generic.websocket import AsyncJsonWebsocketConsumer
from channels.security.websocket import OriginValidator
from django.core.paginator import Paginator
from django.db import transaction
from channels.db import database_sync_to_async
from asgiref.sync import sync_to_async
from traceback import format_exc
from urllib.parse import urlparse, parse_qs
import logging
import aiohttp
import subprocess
import asyncio
import unicodedata
from datetime import timezone, datetime, timedelta
from itertools import groupby
from enum import Enum
import os
import re
import boto3
import botocore


from brat.conf import parse_visual_conf, add_defaults
from brat.json import get_doc_json, get_coll_json
from brat.sudachisplit import find_token_standoffs
from brat.modify_annotations import modify_annotations
from brat.annotation import TextAnnotations
from brat import webanno_tsv
from brat.diff_and_mark import AnnotationDiff
import time

from .models import Job




PAGE_SIZE = 10
BOOT_CHECK_DELAY = 10 # seconds
DEFAULT_SHUTDOWN_DELAY = 10 # minutes


logger = logging.getLogger(__name__)

workers = {
    worker['id']: worker
    for worker in settings.WORKERS
}

actions_by_server = {}
for worker in settings.WORKERS:
    ec2_id = worker.get("ec2_id")
    if ec2_id:
        actions_by_server.setdefault(worker["ec2_id"], []).append(worker["id"])

origin_validator = OriginValidator(None,
    os.environ.get('WS_ORIGINS', '*').split()
)



async def future_with_data(future, data):
    return (await future, data)


def epoch(dt):
    return dt.replace(tzinfo=timezone.utc).timestamp() if dt else None


def nfkc_normalize(text):
    return unicodedata.normalize('NFKC', text)


JA_PUNCTUATIONS = ['．', '。']
_ja_punct_split_re = re.compile("(" + "|".join(re.escape(s) for s in JA_PUNCTUATIONS) + ")")
def nfkc_normalize_without_jp_punct(text):
    parts = _ja_punct_split_re.split(text)
    for index in range(0, len(parts), 2):
        parts[index] = unicodedata.normalize('NFKC', parts[index])
    return ''.join(parts)


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


def timeout_jobs(actions):
    with transaction.atomic():
        updated_jobs = list(Job.objects.select_related('user').filter(state__in=[Job.STARTED, Job.QUEUED], action__in=actions))
        Job.objects.filter(state=Job.QUEUED, action__in=actions).update(state=Job.WAITING)
        Job.objects.filter(state=Job.STARTED, action__in=actions).update(state=Job.ERROR, ann="Timeout")
        return updated_jobs


async def notify_timeout_jobs(channel_layer, updated_jobs):
    tasks = [
        channel_layer.group_send(
            user_group_name(job.user.username),
            {
                "type": "update",
                "msg_type": "changed",
                "id": str(job.id),
                "state": job.state,
            }
        )
        for job in updated_jobs
    ]
    return asyncio.gather(*tasks)



def user_group_name(username):
    return "user.{}".format(username)



class BratConsumer(AsyncJsonWebsocketConsumer):
    async def connect(self):
        await self.accept()
        query_params = parse_qs(self.scope["query_string"].decode('utf-8'))
        if "username" in query_params and "password" in query_params:
            # API access - no session stealing to worry about
            username = query_params["username"][-1]
            password = query_params["password"][-1]
            user = await database_sync_to_async(authenticate)(username=username, password=password)
            if user:
                await login(self.scope, user)
        else:
            # Website access: check origin
            parsed_origin = None
            for header_name, header_value in self.scope.get("headers", []):
                if header_name == b"origin":
                    try:
                        # Set ResultParse
                        parsed_origin = urlparse(header_value.decode("latin1"))
                    except UnicodeDecodeError:
                        pass
            if not origin_validator.valid_origin(parsed_origin):
                await self.close(4001)
                return

            user = self.scope["user"]

        if user and user.is_authenticated:
            await self.channel_layer.group_add(user_group_name(user.username), self.channel_name)


    async def disconnect(self, close_code):
        user = self.scope["user"]
        await self.channel_layer.group_discard(user_group_name(user.username), self.channel_name)
        pass

    # get data from websocket
    async def receive_json(self, content):
        user = self.scope["user"]
        if not user.is_authenticated:
            await self.send_json({
                "type": "unauthorized",
            })
            return

        req_type = content.get("type")
        logger.error("JSON RECEIVED: %s" % req_type)

        if req_type == "analyze":
            await self.channel_layer.send("worker-manager", {
                "type": "submit",
                "text": content["text"],
                "action": content["action"],
                "user_id": self.scope["user"].id,
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
                await self.send_json({
                    "type": "show",
                    "id": str(job.id),
                    "error": error,
                })

            else:
                doc = TextAnnotations(text=job.txt, source=job.ann)
                await self.show(job, doc)

            if job and not job.viewed:
                job.viewed = True
                await database_sync_to_async(job.save)()
                group_name = user_group_name(user.username)
                await self.channel_layer.group_send(group_name, {
                    "type": "update",
                    "msg_type": "viewed",
                    "id": str(job.id),
                })

        elif req_type == "diff":
            error = None
            job_id = content["id"]
            try:
                job = await database_sync_to_async(Job.objects.get)(pk=job_id)
            except Job.DoesNotExist:
                error = "notfound"

            if job and job.state == Job.ERROR:
                error = "error"

            modifier = nfkc_normalize_without_jp_punct
            other_ann = content["ann"]
            if other_ann.startswith("#FORMAT"):
                lines = other_ann.splitlines()
                diff_doc = webanno_tsv.from_lines(lines, modifier(job.txt), modifier)
            else:
                diff_doc = TextAnnotations(text=job.txt, source=other_ann)
                modify_annotations(diff_doc, modifier)

            if error:
                await self.send_json({
                    "type": "show",
                    "id": str(job.id),
                    "error": error,
                })

            else:
                job_doc = TextAnnotations(text=job.txt, source=job.ann)
                modify_annotations(job_doc, modifier)
                doc = AnnotationDiff(diff_doc, job_doc).diff()
                await self.show(job, doc)

        else:
            logger.error("Bad message type: {}".format(req_type))
        logger.error("JSON RECEIVED DONE")


    async def update(self, event):
        event = dict(event)
        msg_type = event.pop("msg_type")
        await self.send_json({
            **event,
            "type": msg_type,
        })

    async def show(self, job, doc):
        raw_visual_conf = parse_visual_conf(job.visual_conf)
        visual_conf = add_defaults(raw_visual_conf, doc)
        norm_urls = None # parse_tools_conf(job.tools_conf).norm_urls
        token_standoffs = find_token_standoffs(doc.get_document_text())
        doc_json = get_doc_json(doc, norm_urls=norm_urls, token_standoffs=token_standoffs)
        coll_json = get_coll_json(visual_conf)
        await self.send_json({
            "type": "show",
            "id": str(job.id),
            "action": job.action,
            "doc": doc_json,
            "coll": coll_json,
        })





class WorkerConsumer(AsyncConsumer):
    def __init__(self):
        logger.error("INITIALISED WORKER CONSUMER %s", id(self))

        ec2_token = os.environ.get('EC2_SESSION_TOKEN')
        if ec2_token:
            ec2_kwargs = {
                "aws_session_token": ec2_token
            }
        else:
            ec2_key_id = os.environ.get("EC2_KEY_ID")
            ec2_access_key = os.environ.get("EC2_ACCESS_KEY")
            if ec2_key_id and ec2_access_key:
                ec2_kwargs = {
                    "aws_access_key_id": ec2_key_id,
                    "aws_secret_access_key": ec2_access_key,
                }
            else:
                logger.warning("EC2 not configured")
                ec2_kwargs = None

        if ec2_kwargs:
            ec2_region = os.environ.get('EC2_REGION')
            if ec2_region:
                ec2_config = botocore.config.Config(
                    region_name=ec2_region,
                )
                ec2_kwargs["config"] = ec2_config

            self.ec2 = boto3.client("ec2", **ec2_kwargs)
        else:
            self.ec2 = None

        self.booting = set()


    async def boot(self, message):
        if not self.ec2:
            logger.error("No EC2 support and worker not up!")
            return

        logger.error("WORKER BOOT!!!")
        action = message["action"]
        if action in self.booting:
            logger.error("ALREADY BOOTING")
            return

        worker = workers[action]
        ec2_id = worker["ec2_id"]
        logger.error("WORKER BOOT %s %s", ec2_id, id(self))

        actions = set(actions_by_server[ec2_id])
        self.booting.update(actions)

        updated_jobs = await database_sync_to_async(timeout_jobs)(actions)
        await notify_timeout_jobs(self.channel_layer, updated_jobs)

        while True:
            try:
                await sync_to_async(self.ec2.start_instances)(InstanceIds=[ec2_id])
                logger.error("SUCCESSFULLY BOOTED %s %s", ec2_id, id(self))
                break
            except botocore.exceptions.ClientError:
                logger.error("ERROR WHILE BOOTING, WILL RETRY %s %s", ec2_id, id(self))
                await asyncio.sleep(BOOT_CHECK_DELAY)

        timeout = aiohttp.ClientTimeout(total=1)
        async with aiohttp.ClientSession(timeout=timeout) as session:
            while actions:
                tasks = [
                    future_with_data(session.get(workers[action]["url"] + "ping"), action)
                    for action in actions
                ]
                for future in asyncio.as_completed(tasks):
                    # just need to know they completed successfully
                    try:
                        result, action = await future
                        logger.error("GOT RESPONSE FROM %s" % action)
                        self.booting.remove(action)
                        actions.remove(action)

                        jobs = await database_sync_to_async(list)(Job.objects.select_related('user').filter(state=Job.WAITING, action=action))
                        url = workers[action]["url"]
                        for job in jobs:
                            response = await session.post(url, data={
                                "job": str(job.id),
                                "text": job.txt,
                            })
                            if response.status == 202:
                                job.state = Job.QUEUED
                            else:
                                job.ann = f"Status code {response.status}\n\n{await response.text()}"
                                job.state = Job.ERROR
                            await database_sync_to_async(job.save)()

                            logger.error("WAITED SUBMIT SENDING UPDATE TO CHANNEL %s", job.id)
                            group_name = user_group_name(job.user.username)
                            await self.channel_layer.group_send(group_name, {
                                "type": "update",
                                "msg_type": "changed",
                                "id": str(job.id),
                                "state": job.state,
                            })
                            logger.error("WAITED SUBMIT SENT UPDATE TO CHANNEL")

                    except (aiohttp.client_exceptions.ClientConnectorError, asyncio.TimeoutError) as x:
                        logger.error("NG: %s says %s", action, type(x))
                        pass

                await asyncio.sleep(BOOT_CHECK_DELAY)


    async def submit(self, message):
        text = message['text']
        action = message['action']
        user_id = message['user_id']
        error = None

        text = nfkc_normalize_without_jp_punct(text)
        worker = workers[action]
        url = worker["url"]
        user = await database_sync_to_async(User.objects.get)(pk=user_id)
        job = await database_sync_to_async(Job.objects.create)(
            user=user,
            action=action,
            txt=text,
        )

        logger.error("MAKING THE REQUEST %s" % job.id)
        timeout = aiohttp.ClientTimeout(total=1)
        async with aiohttp.ClientSession(timeout=timeout) as session:
            data = {
                "job": str(job.id),
                "text": job.txt,
            }
            try:
                async with session.post(url, data=data) as response:
                    logger.error("RESULT: %s %s", response.status, await response.text())

                    if response.status != 202:
                        error = f"Status code {response.status}\n\n{await response.text()}"

            except (aiohttp.client_exceptions.ClientConnectorError, asyncio.TimeoutError):
                logger.error("ERROR in AIOHTTP")
                job.state = Job.WAITING
                await database_sync_to_async(job.save)()
                ec2_id = worker.get("ec2_id")
                logger.error("EC2 ID %s", ec2_id)
                if ec2_id:
                    logger.error("SENDING BOOT MESSAGE")
                    await self.channel_layer.send("worker-manager", {
                        "type": "boot",
                        "action": job.action,
                    })
                    logger.error("SENT BOOT MESSAGE")
                else:
                    logger.warning("ec2_id for {} not configured, cannot boot server".format(action))

        if job:
            if error:
                job.ann = error
                job.state = Job.ERROR
                await database_sync_to_async(job.save)()

            group_name = user_group_name(user.username)
            logger.error("SUBMIT SENDING UPDATE TO CHANNEL %s", job.id)
            await self.channel_layer.group_send(group_name, {
                "type": "update",
                "msg_type": "changed",
                "id": str(job.id),
                "state": job.state,
            })
            logger.error("SUBMIT SENT UPDATE TO CHANNEL")
