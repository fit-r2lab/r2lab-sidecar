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
def init_logging(level=logging.INFO):
    """
    initialize global log object
    """
    logging.basicConfig(
        stream=sys.stdout,
        level=level,
        format='%(levelname)s %(asctime)s: %(message)s',
        datefmt="%m-%d %H:%M:%S")
init_logging()

class Category:
    """
    each of these objects represents one of the known
    message categories
    """
    def __init__(self, name, persistent=False):
        self.name = name
        self.persistent = persistent
        ##
        self.filename = None
        self.contents = []
        # relevant only when persistent
        self.by_id = {}

    def _candidate_filenames(self):
        return [
            f"/var/lib/sidecar/{self.name}.json",
            f"./{self.name}.json",
        ]

    def __repr__(self):
        result = f"category:{self.name}"
        result += f" with {len(self.contents)} items"
        return result

    def rehash(self):
        if self.persistent:
            self.by_id = {info['id']: info for info in self.contents}

    def load(self):
        """
        Load from permanent storage
        Either use file from /var/log if available,
        otherwise from .
        """
        for filename in self._candidate_filenames():
            try:
                path = Path(filename)
                with path.open() as feed:
                    self.contents = json.loads(feed.read())
                    self.rehash()
                    self.filename = filename
                    return
            except IOError:
                logging.warning(f"category {self.name}"
                                f" could not open {path}")
        # we've failed
        self.contents = []

    def store(self):
        """
        Store current contents
        """
        # if we've loaded from a filename, re-use it
        # otherwise, write into the first candidate
        if self.filename:
            candidates = [self.filename]
        else:
            candidates = self._candidate_filenames()
        for filename in candidates:
            try:
                with open(filename, 'w') as writer:
                    writer.write(json.dumps(self.contents) + "\n")
                    self.filename = filename
                    logging.info(f"Stored {self.name} in {filename}")
                return True
            except IOError:
                pass
        logging.error(f"could not save category {self}")
        return False

    def update(self, infos):
        """
        triples is a list of triples of the form
        {'id': something, 'somekey': 'somevalue', 'anotherkey': 'anotherval'}
        []
        """
        if not self.persistent:
            self.contents = infos
            self.store()
        else:
            for new_info in infos:
                if 'id' not in new_info:
                    logging.error(f"info object lacks id {new_info}")
                else:
                    if id not in self.by_id:
                        info = dict(id=id)
                        self.contents.append(info)
                        self.by_id[id] = info
                    else:
                        info = self.by_id[id]
                    info.update(new_info)
                    self.rehash()
            self.store()


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

    def check_umbrella(self, umbrella, check_infos):
        """
        Check payload once it's been json-unmarshalled
        """
        if ('action' not in umbrella or
                umbrella['action'] not in ('request', 'info')):
            logging.error(f"Ignoring misformed umbrella {umbrella}")
            return False
        if ('category' not in umbrella or
                umbrella['category'] not in self.hash):
            logging.error(f"Ignoring unknown category in {umbrella}")
            return False
        if 'message' not in umbrella:
            logging.error(f"Ignoring payload without a 'message' {umbrella}")
            return False
        if check_infos:
            message = umbrella['message']
            if not isinstance(message, list):
                logging.error(f"Unexpected message of type {type(message).__name__} - should be a list")
                return False
        return True

    async def broadcast(self, category, origin):
        logging.info(f"broadcasting on {len(self.clients)} clients")
        data = self.hash[category].contents
        umbrella = dict(category=category, action="info",
                        message=data)
        for websocket in self.clients:
            await websocket.send(json.dumps(umbrella))

    async def react_on(self, umbrella, origin):
        # tmp:
        self.dump(f"entering react_on with {umbrella}")
        action = umbrella['action']
        category = umbrella['category']
        if action == 'request':
            if not self.check_umbrella(umbrella, False):
                return
            await self.broadcast(umbrella['category'], origin)
        elif action == 'info':
            if not self.check_umbrella(umbrella, True):
                return
            self.hash[category].update(umbrella['message'])
            self.hash[category].store()
            await self.broadcast(umbrella['category'], origin)

    def websockets_closure(self):
        self.dump("mainloop")
        async def websockets_loop(websocket, path):
            self.register(websocket)
            try:
                async for message in websocket:
                    try:
                        umbrella = json.loads(message)
                        await self.react_on(umbrella, websocket)
                    except json.JSONDecodeError:
                        logging.error("Ignoring non-json message {message}")
            finally:
                self.unregister(websocket)
        return websockets_loop


    def run(self):
        loop = asyncio.get_event_loop()
        task = websockets.serve(self.websockets_closure(), 'localhost', 10000)
        loop.run_until_complete(task)
        loop.run_forever()

if __name__ == '__main__':
    server = SidecarServer()
    server.run()
