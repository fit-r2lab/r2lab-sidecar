#!/usr/bin/env python3

"""
The R2lab sidecar server, rewritten in Python + websockets
as a replacement for historical JavaScript + socketio.

Features:

* the server keeps track of all currently connected clients

* we define categories (currently 3: nodes, phones and leases);
  that describe the current testbed status

*  2 kinds of categories are involved:
  * id-based (nodes and phones)
  * and list-based (leases)

* all categories
  understand the 'request' action,
  that triggers the server to broadcast the current (complete)
  contents for that category

  example: (the JSON representation for ...):
  {'category': 'phones',
   'action': 'request'}

* id-based categories
  understand the 'info' message, that carries news
  about the current status; it can be used e.g. to
  notify web clients, or here in the sidecar server
  to overwrite data for one or several ids
  only supports overwriting specific (id x key) values,
  cannot delete any key - or id for that matter

  as the focal / central point in this architecture,
  the sidecar server keeps track of this data in persistent storage

  example:
  { 'category:': 'nodes',
    'action': 'info',
    'message': [
        {"id": 5, "available" : "ok", "os_release":"fedora-27"},
        {"id": 7, "available" : "ko"},
    ]
  }

* list-based category(ies)
  understand the 'info' message just the same, but
  there are a couple slight differences:
  * not incremental: the complete list of leases is
    always passed over in its entire form
  * not persistent: for that reason, there is no
    storage associated to this category

# Forwarding

As the focal point, the server:
* absorbs all 'request' messages,
  it simply reacts by sending the corresponding

"""

# pylint:disable=w1203

import sys
import json
from pathlib import Path
import logging

import asyncio
import websockets


# pass logging.DEBUG if needed
def init_logger(level=logging.INFO):
    """
    initialize global logger object
    """
    logging.basicConfig(
        stream=sys.stdout,
        level=level,
        format='%(levelname)s %(asctime)s: %(message)s',
        datefmt="%m-%d %H:%M:%S")
init_logger()

class Category:
    """
    each of these objects represents one of the known
    message categories
    """
    def __init__(self, name, persistent=False):
        self.name = name
        self.persistent = persistent
        self.contents = []

    def _filenames(self):
        return [
            f"/var/lib/sidecar/{self.name}.json",
            f"./{self.name}.json",
        ]

    def __repr__(self):
        result = f"category:{self.name}"
        result += f" with {len(self.contents)} items"
        return result

    def load(self):
        """
        Load from permanent storage
        Either use file from /var/log if available,
        otherwise from .
        """
        for filename in self._filenames():
            try:
                path = Path(filename)
                with path.open() as feed:
                    self.contents = json.loads(feed.read())
                    return
            except IOError:
                logging.warning(f"category {self.name}"
                                f" could not open {path}")
        # we've failed
        self.contents = []



CATEGORIES = [
    Category('nodes', persistent=True),
    Category('phones', persistent=True),
    Category('leases', persistent=False),
]


class SidecarServer:
    """
    The server logic
    """

    def __init__(self):
        self.hash = {category.name: category for category in CATEGORIES}
        for category in self.hash.values():
            category.load()
        self.clients = set()

    def dump(self, message):
        """
        devel-oriented dump of current status
        """
        logging.info(f"--- {message}")
        logging.info(f"SidecarServer with {len(self.clients)} clients")
        for category in self.hash.values():
            logging.info(f"{category}")

    def register(self, websocket):
        """
        keep track of connected clients
        """
        self.clients.add(websocket)

    def unregister(self, websocket):
        """
        keep track of connected clients
        """
        self.clients.remove(websocket)

    async def broadcast(self, category, origin):
        logging.info(f"broadcasting on {len(self.clients)} clients")
        data = self.hash[category].contents
        umbrella = dict(category=category, action="info",
                        message=data)
        for websocket in self.clients:
            logging.info(f"broadcasting {category} category to {websocket}")
            await websocket.send(json.dumps(umbrella))

    async def react_on(self, umbrella, origin):
        self.dump(f"entering react_on with {umbrella}")
        if ('action' not in umbrella
                and umbrella['action'] not in ('request', 'info')):
            logging.error(f"Ignoring misformed umbrella {umbrella}")
            return
        action = umbrella['action']
        if action == 'request':
            await self.broadcast(umbrella['category'], origin)


    def ws_closure(self):
        self.dump("mainloop")
        async def websockets_loop(websocket, path):
            self.register(websocket)
            try:
                async for message in websocket:
                    umbrella = json.loads(message)
                    await self.react_on(umbrella, websocket)
            finally:
                self.unregister(websocket)
        return websockets_loop


    def run(self):
        loop = asyncio.get_event_loop()
        task = websockets.serve(self.ws_closure(), 'localhost', 10000)
        loop.run_until_complete(task)
        loop.run_forever()

if __name__ == '__main__':
    server = SidecarServer()
    server.run()
