from flask import Flask, request
import requests
from threading import Thread
from queue import Queue
from traceback import format_exc

from ..process import setup, process



setup()
queue = Queue()
app = Flask(__name__)


@app.route("/", methods=["POST"])
def annotate():
    job = request.form["job"]
    callback = request.form["callback"]
    text = request.form["text"]
    queue.put((job, callback, text))
    return '', 202


def worker():
    while True:
        job, callback, text = queue.get()

        try:
            visual_conf, doc = process(text)
        except:
            requests.post(callback, {
                "job": job,
                "error": format_exc()
            })
            return

        requests.post(callback, {
            "job": job,
            "txt": doc.get_document_text(),
            "ann": str(doc),
            "visual_conf": visual_conf,
        })

Thread(target=worker).start()
