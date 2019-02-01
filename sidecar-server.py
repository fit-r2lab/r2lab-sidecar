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

Once the server has properly reacted on an incoming message,
it is always broadcasted to all current clients.
"""

# pylint:disable=w1203

import sys
import json
from pathlib import Path
import logging as logger
from argparse import ArgumentParser, ArgumentDefaultsHelpFormatter
import asyncio
from collections import defaultdict

import websockets


default_sidecar_url = "wss://r2lab.inria.fr:999/"
devel_sidecar_url = "ws://localhost:10000/"
default_ssl_cert = "/etc/pki/tls/certs/r2lab_inria_fr.crt"
default_ssl_key = "/etc/pki/tls/private/r2lab.inria.fr.key"

DEBUG = False

logger.basicConfig(
    stream=sys.stdout,
    level=logger.INFO,
    format='%(levelname)s %(asctime)s: %(message)s',
    datefmt="%m-%d %H:%M:%S")

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
        self.hash_by_id = {}

    # for devel mode: use files in .
    # when /var/lib is not writable for us
    def _candidate_filenames(self):
        return [
            # tmp
            f"/tmp/{self.name}.json",
            f"/var/lib/sidecar/{self.name}.json",
            f"/var/lib/sidecar/{self.name}.json",
            f"./{self.name}.json",
        ]

    def __repr__(self):
        return f"{len(self.contents)} {self.name}"

    def rehash(self):
        if self.persistent:
            self.hash_by_id = {info['id']: info
                               for info in self.contents}

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
                logger.warning(f"category {self.name}"
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
                    logger.info(f"Stored {self.name} in {filename}")
                return True
            except IOError:
                pass
        logger.error(f"could not save category {self}")
        return False

    def update(self, infos):
        """
        triples is a list of triples of the form
        {'id': something, 'somekey': 'somevalue', 'anotherkey': 'anotherval'}
        []
        """
        # non-persistent categories receive the whole list each time
        # and that overrides contents
        if not self.persistent:
            # xxx it feels like in some cases, at least when a lease is set on the UI
            # there may be a need to merge here too...
            self.contents = infos
            return self.contents
            # xxx also this might deserve a save()
        else:
            result = []
            for incoming_info in infos:
                if 'id' not in incoming_info:
                    logger.error(f"info object lacks id {incoming_info}")
                    continue
                id = incoming_info['id']
                if id not in self.hash_by_id:
                    # first time we see this id
                    self.contents.append(incoming_info)
                    self.hash_by_id[id] = incoming_info
                    result.append(incoming_info)
                else:
                    has_changed = False
                    # make sure there's something new..
                    old_info = self.hash_by_id[id]
                    for k, v in incoming_info.items():
                        if k not in old_info:
                            has_changed = True
                        elif old_info[k] != v:
                            has_changed = True
                    if has_changed:
                        old_info.update(incoming_info)
                        result.append(old_info)
                    else:
                        logger.debug(f"no change on id={id}")
            if result:
                self.store()
            return result


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
        self.hash_by_category = {category.name: category
                                 for category in CATEGORIES}
        for category in self.hash_by_category.values():
            category.load()
        self.clients = set()
        # this is not operational, just for more meaningful
        # accounting of number of clients per hostname
        self.clients_by_host = defaultdict(set)


    def _dump(self, message, payload=None):
        """
        devel-oriented dump of current status
        """
        line = "["
        line += (', '.join(f"{category}"
                 for category in self.hash_by_category.values()))
        line += f"] {message} | "
        line += f"{len(self.clients)} clients "
        line += f"from: {len(self.clients_by_host)} hosts - "
        line += (', '.join(f"{add} [{len(clients)}]"
                           for (add, clients) in self.clients_by_host.items()))
        if DEBUG and payload:
            line += f"\n   payload={payload}"
        return line

    def dump(self, message, payload=None):
        logger.info(self._dump(message, payload))


    def register(self, websocket):
        """
        keep track of connected clients
        """
        self.clients.add(websocket)
        client_address, *_ = websocket.remote_address
        self.clients_by_host[client_address].add(websocket)
        self.dump("Registered new client")

    def unregister(self, websocket):
        """
        keep track of connected clients
        """
        if websocket in self.clients:
            self.clients.remove(websocket)
            client_address, *_ = websocket.remote_address
            host_set = self.clients_by_host[client_address]
            host_set.remove(websocket)
            if not host_set:
                del self.clients_by_host[client_address]
            self.dump("Unregistered client")
            # temp
            for i in range(3):
                logger.info('---')
        else:
            logger.error(f"Unregistering unknown client !")


    def check_umbrella(self, umbrella, check_infos):
        """
        Check payload once it's been json-unmarshalled
        """
        if ('action' not in umbrella or
                umbrella['action'] not in ('request', 'info')):
            logger.error(f"Ignoring misformed umbrella {umbrella}")
            return False
        if ('category' not in umbrella or
                umbrella['category'] not in self.hash_by_category):
            logger.error(f"Ignoring unknown category in {umbrella}")
            return False
        if 'message' not in umbrella:
            logger.error(f"Ignoring payload without a 'message' {umbrella}")
            return False
        if check_infos:
            message = umbrella['message']
            if not isinstance(message, list):
                logger.error(f"Unexpected message of type "
                             f"{type(message).__name__} - should be a list")
                return False
        return True


    async def broadcast(self, umbrella, origin):
        self.dump(
            f"Broadcast {umbrella['category']},{umbrella['action']}",
            payload=umbrella)
        for websocket in self.clients:
            try:
                await websocket.send(json.dumps(umbrella))
            except websockets.exceptions.ConnectionClosed:
                logger.info("Client has vanished - ignoring")

    async def broadcast_category(self, category, origin):
        data = self.hash_by_category[category].contents
        umbrella = dict(category=category, action="info",
                        message=data)
        await self.broadcast(umbrella, origin)


    async def react_on(self, umbrella, origin):
        # origin is the client that was the original sender
        # self.dump(f"entering react_on with {umbrella}")
        action = umbrella['action']
        category = umbrella['category']
        if action == 'request':
            if not self.check_umbrella(umbrella, False):
                return
            self.dump(f"Reacting on 'request' on {category}")
            # broadcast current known contents
            await self.broadcast_category(umbrella['category'], origin)
            # broadcast request as well
            # typically useful for monitorleases
            # xxx might avoid that on non-persistent categories
            await self.broadcast(umbrella, origin)
        elif action == 'info':
            if not self.check_umbrella(umbrella, True):
                return
            self.dump(f"Reacting on 'info' on {category}",
                      payload=umbrella)
            news = self.hash_by_category[category].update(umbrella['message'])
            self.dump(f"\n    news={news}")
            if news:
                # don't allocate a new umbrella object, we don't need this one anymore
                umbrella['message'] = news
                await self.broadcast(umbrella, origin)

    def websockets_closure(self):
        self.dump(f"Sidecar server mainloop")
        async def websockets_loop(websocket, path):
            self.register(websocket)
            try:
                async for message in websocket:
                    try:
                        umbrella = json.loads(message)
                        await self.react_on(umbrella, websocket)
                    except json.JSONDecodeError:
                        logger.error(f"Ignoring non-json message {message}")
            finally:
                self.unregister(websocket)
        return websockets_loop


    def run(self, url, cert, key):
        uri = websockets.uri.parse_uri(url)
        # ignore 2 fields resource_name and user_info
        secure, hostname, port, *_ = uri

        ssl_context = None
        if secure:
            import ssl
            ssl_context = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
            ssl_context.load_cert_chain(cert, key)

        loop = asyncio.get_event_loop()
        task = websockets.serve(self.websockets_closure(),
                                hostname, port, ssl=ssl_context)
        loop.run_until_complete(task)
        loop.run_forever()

    def main(self):
        parser = ArgumentParser(formatter_class=ArgumentDefaultsHelpFormatter)
        parser.add_argument(
            "-u", "--sidecar-url", default=default_sidecar_url,
            help="Typically a ws:// or wss:// url")
        parser.add_argument(
            "-c", "--cert", default=default_ssl_cert,
            help="SSL certificate (wss only)")
        parser.add_argument(
            "-k", "--key", default=default_ssl_key,
            help="Private key for SSL certificate (wss only)")
        parser.add_argument(
            "-d", "--devel", action='store_true', default=False,
            help=f"shorthand for --url {devel_sidecar_url}")
        args = parser.parse_args()

        url = devel_sidecar_url if args.devel else args.sidecar_url

        self.run(url, args.cert, args.key)


if __name__ == '__main__':
    SidecarServer().main()
