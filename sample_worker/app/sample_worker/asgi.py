from quart import Quart, websocket
from quart.utils import run_sync
from concurrent.futures import ProcessPoolExecutor
import asyncio
from traceback import format_exc

from .process import setup, process



app = Quart(__name__)
pool = ProcessPoolExecutor(max_workers=1)

setup()


def process_wrapper(text):
    visual_conf, doc = process(text)
    return (visual_conf, doc.get_document_text(), str(doc))


@app.websocket('/ws')
async def ws():
    loop = asyncio.get_running_loop()
    while True:
        data = await websocket.receive_json()
        print("GOT {}".format(data))
        text = data["text"]
        try:
            # visual_conf, doc = await run_sync(process)(text)
            visual_conf, txt, ann = await loop.run_in_executor(pool, process_wrapper, text)
            response = {
                "txt": txt,
                "ann": ann,
                "visual_conf": visual_conf,
            }
        except:
            response = {
                "error": format_exc(),
            }

        await websocket.send_json(response)


if __name__ == "__main__":
    app.run()
