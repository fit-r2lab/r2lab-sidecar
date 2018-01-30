#!/usr/bin/env python -i
from __future__ import print_function

import json
from socketIO_client import SocketIO, LoggingNamespace

def io_callback(*args, **kwds):
    print('on socketIO response', *args, **kwds)

print("Run this script with python -i")
socketio = None

# xxx would need to import sidecar_client instead
def i(hostname='localhost', port=999):
    global socketio
    socketio = SocketIO(hostname, port, LoggingNamespace)
    print("""---
    soketio connected to {}:{}""".format(hostname, port))

def ir():
    i('r2lab.inria.fr')
ir()
print("Run i('localhost', 999) e.g. to create another connection")
print("Or just i() e.g. to use localhost")
print("Or just ir() e.g. to connect to r2lab")

def myemit(channel, msg):
    global soketio
    print("On channel {} : {}".format(channel, msg))
    socketio.emit(channel, json.dumps(msg), io_callback)

def s(infos):
    # can work only one dict -> wrap it in a list
    if isinstance(infos, dict):
        infos = [infos]
    myemit('info:nodes', infos)
print("Run s({'id':4, 'cmc_on_off': 'on'}) to send a message on 'info:nodes'")

def a(id, info):
    info['id'] = id
    e(info)
print("Run a(4, {'cmc_on_off': 'off'}) to send a status message about a specific node")

def sr():
    myemit('request:nodes', 'EMIT')
print("Run sr() to send on request:nodes")

####################
lease_template = {
    'valid_from': '2016-03-08T14:00:00Z',
    'valid_until': '2016-03-08T15:00:00Z',
    'status': 'accepted',
    'resource_type': 'lease',
    'uuid': 'b1a4e674-18c5-49fc-8415-3819d95b33ac',
    'name': '5458a2e0-e51c-11e5-ad16-525400646cb0',
    'urn': 'urn:publicid:IDN+r2lab+lease+5458a2e0-e51c-11e5-ad16-525400646cb0',
    'account': {'resource_type': 'account',
                'uuid': 'fab07428-1eb2-4940-80f8-c848b87a365e',
                'name': 'onelab.inria.r2lab.admin',
                'urn': 'urn:publicid:IDN+onelab:inria:r2lab+slice+admin',
                'created_at': '2016-02-01T14:48:14Z',
                'valid_until': '2030-12-31T23:59:59Z'},
    'components': [{'resource_type': 'node',
                    'uuid': '713f6553-963e-4ef4-a100-bf58be0bc9f0',
                    'status': 'unknown',
                    'name': '37nodes',
                    'urn': 'urn:publicid:IDN+r2lab+node+37nodes',
                    'available': True,
                    'exclusive': True,
                    'domain': 'r2lab'}]}
import time
def ts(hour):
    return time.strftime("%Y-%M-%DT{hour}:00:00CET".format(hour=hour))
print("Run ts(14) to get a time spec for today at 14:00")

from copy import copy
def lea(h_from, h_until, status='accepted'):
    result = copy(lease_template)
    result.update( {'valid_from' : ts(h_from),
                    'valid_until' : ts(h_until),
                    'status' : status})
    return result
print("Run lea(14, 15) to build a lease record for today between 14:00 and 15:00")

def l(*args):
    lease = lea(*args)
    myemit('info:leases', [lease])
print("Run l(14, 15) to send that lease on info:leases")

def lr():
    myemit('request:leases', 'EMIT')
print("run lr() to send a message on request:leases")    
    
