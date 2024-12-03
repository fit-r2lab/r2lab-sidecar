#!/usr/bin/env python3

"""
The R2lab sidecar server, rewritten in Python + websockets
as a replacement for historical JavaScript + socketio.

Features:

* the server keeps track of all currently connected clients

* we define categories (currently 4: nodes, phones, pdus and leases);
  that describe the current testbed status

*  2 kinds of categories are involved:
  * id-based (nodes, phones and pdus)
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

# pylint:disable=c0111, w1203, w0603

import sys
import json
from pathlib import Path
import logging as logger
from argparse import ArgumentParser, ArgumentDefaultsHelpFormatter
import asyncio
from collections import defaultdict

from urllib.parse import urlparse

import websockets

from r2lab_sidecar.version import __version__


DEFAULT_SIDECAR_URL = "wss://r2lab-sidecar.inria.fr:443/"
DEVEL_SIDECAR_URL = "ws://localhost:10000/"
DEFAULT_SSL_CERT = "/etc/dsissl/auto/prod-r2lab.inria.fr/fullchain.pem"
DEFAULT_SSL_KEY = "/etc/dsissl/auto/prod-r2lab.inria.fr/privkey.pem"

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
            f"/var/lib/sidecar/{self.name}.json",
            # for the devel server mostly
            f"{self.name}.json",
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

    def update_and_find_news(self, infos):
        """
        triples is a list of triples of the form
        {'id': something, 'somekey': 'somevalue', 'anotherkey': 'anotherval'}

        returns a list of news that should be broadcasted
        """
        # non-persistent categories receive the whole list each time
        # and that overrides contents
        if not self.persistent:
            self.contents = infos
            return self.contents
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
                for key, v in incoming_info.items():
                    if key not in old_info:
                        has_changed = True
                    elif old_info[key] != v:
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
    Category('pdus', persistent=True),
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

    def info_dump(self, message, payload=None):
        logger.info(self._dump(message, payload))

    def warning_dump(self, message, payload=None):
        logger.warning(self._dump(message, payload))


    def _spot(self, websocket):
        """
        finds the host for a given websocket
        we cannot use websocket.remote_address to do this cleanup
        because it's None when the connection is closed
        """
        for host, host_set in self.clients_by_host.items():
            if websocket in host_set:
                return host
        return None

    def register(self, websocket):
        """
        keep track of connected clients
        """
        self.clients.add(websocket)
        client_address, *_ = websocket.remote_address
        self.clients_by_host[client_address].add(websocket)
        self.info_dump("Registered new client")

    def unregister(self, websocket):
        """
        keep track of connected clients
        """
        host = self._spot(websocket)
        if not host:
            self.warning_dump(f"Failed to unregister unknown client {websocket} !")
        self.info_dump(f"Unregistering client from {host}")
        self.clients.remove(websocket)
        host_set = self.clients_by_host[host]
        host_set.remove(websocket)
        # last client from this address ?
        if not host_set:
            del self.clients_by_host[host]


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


    async def broadcast(self, umbrella, _origin):
        if DEBUG:
            self.info_dump(
                f"Broadcast {umbrella['category']},{umbrella['action']}",
            payload=umbrella)
        # avoid: RuntimeError: Set changed size during iteration
        for websocket in self.clients.copy():
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
        action = umbrella['action']
        category = umbrella['category']
        if action == 'request':
            if not self.check_umbrella(umbrella, False):
                return
            if DEBUG:
                self.info_dump(f"Reacting on 'request' on {category}")
            # broadcast current known contents
            await self.broadcast_category(umbrella['category'], origin)
            # broadcast request as well
            # typically useful for monitorleases
            # need to avoid that on non-persistent categories ?
            await self.broadcast(umbrella, origin)
        elif action == 'info':
            if not self.check_umbrella(umbrella, True):
                return
            if DEBUG:
                self.info_dump(f"Reacting on 'info' on {category}",
                          payload=umbrella)
            news = (self.hash_by_category[category]
                    .update_and_find_news(umbrella['message']))
            if DEBUG:
                self.info_dump(f"\n    news={news}")
            if news:
                # don't allocate a new umbrella object, we don't need this one anymore
                umbrella['message'] = news
                umbrella['incremental'] = True
                await self.broadcast(umbrella, origin)


    def websockets_closure(self):

        async def websockets_loop(websocket):
            self.register(websocket)
            try:
                async for message in websocket:
                    try:
                        umbrella = json.loads(message)
                        await self.react_on(umbrella, websocket)
                    except json.JSONDecodeError:
                        logger.error(f"Ignoring non-json message {message}")
            except websockets.exceptions.ConnectionClosedError:
                logger.error(f"Connection closed with {websocket}")
            finally:
                self.unregister(websocket)
        return websockets_loop


    async def monitor(self, period):
        while True:
            self.info_dump("cyclic status")
            await asyncio.sleep(period)


    async def serve(self, url, cert, key):
        # websockets.uri deprecated in websockets 9.x
        # uri = websockets.uri.parse_uri(url)
        # ignore 2 fields resource_name and user_info
        # secure, hostname, port, *_ = uri
        parsed = urlparse(url)
        secure = parsed.scheme != 'ws'
        try:
            hostname, port = parsed.netloc.split(':')
        except:
            hostname, port = parsed.netloc, 443 if secure else 80

        ssl_context = None
        if secure:
            import ssl
            ssl_context = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
            ssl_context.load_cert_chain(cert, key)

        await websockets.serve(
            self.websockets_closure(),
            hostname, port, ssl=ssl_context)


    def run(self, url, cert, key, period):
        self.info_dump(f"Sidecar server - mainloop")
        async def both():
            async with asyncio.TaskGroup() as tg:
                tg.create_task(self.monitor(period))
                tg.create_task(self.serve(url, cert, key))
        with asyncio.Runner() as runner:
            runner.run(both())


    def main(self):
        parser = ArgumentParser(formatter_class=ArgumentDefaultsHelpFormatter)
        parser.add_argument(
            "-u", "--sidecar-url", default=DEFAULT_SIDECAR_URL,
            help="Typically a ws:// or wss:// url")
        parser.add_argument(
            "-c", "--cert", default=DEFAULT_SSL_CERT,
            help="SSL certificate (wss only)")
        parser.add_argument(
            "-k", "--key", default=DEFAULT_SSL_KEY,
            help="Private key for SSL certificate (wss only)")
        parser.add_argument(
            "-D", "--devel", action='store_true', default=False,
            help=f"shorthand for --url {DEVEL_SIDECAR_URL}")
        parser.add_argument(
            "-p", "--period", default=15,
            help="monitoring period in seconds")
        parser.add_argument(
            "-d", "--debug", action='store_true', default=False,
            help="enable debug mode")
        parser.add_argument(
            "--version", action='store_true', default=False)
        args = parser.parse_args()

        if args.version:
            print(f"r2lab-sidecar {__version__}")
            sys.exit(0)

        if args.debug:
            global DEBUG
            DEBUG = True
            logger.getLogger().setLevel(logger.DEBUG)

        if not args.devel:
            if not Path(args.cert).exists():
                logger.error(f"Cannot find cert file {args.cert}")
                sys.exit(1)
            if not Path(args.key).exists():
                logger.error(f"Cannot find key file {args.key}")
                sys.exit(1)

        url = DEVEL_SIDECAR_URL if args.devel else args.sidecar_url

        self.run(url, args.cert, args.key, args.period)
