#!/usr/bin/env python3

"""
This script emits messages to the sidecar server on faraday
to instruct it that some nodes are available or not
(use available.py or unavailable.py) 
"""

# xxx todo1 - if needed we could add options too to chose between available and unavailable
# xxx todo2 - more importantly we could consider talking to the OMF inventory on faraday
#             to maintain the same status over there


import json
from argparse import ArgumentParser

from sidecar_client import connect_url

# globals
channel = "info:nodes"
default_sidecar_url = "https://r2lab.inria.fr:999/"

# check if run as 'available.py' or 'unavailable.py'
import sys
available_value = 'ko' if 'un' in sys.argv[0] else 'ok'

# parse args
parser = ArgumentParser()
parser.add_argument("nodes", nargs='+', type=int)
parser.add_argument("-u", "--sidecar-url", dest="sidecar_url",
                    default=default_sidecar_url,
                    help="url for thesidecar server (default={})"
                    .format(default_sidecar_url))
args = parser.parse_args()

def check_valid(node):
    return 1 <= node <= 37

invalid_nodes = [ node for node in args.nodes if not check_valid(node) ]
if invalid_nodes:
    print("Invalid inputs {} - exiting".format(invalid_nodes))
    exit(1)

infos = [{'id': node, 'available' : available_value} for node in args.nodes]

url = args.sidecar_url
print("Connecting to sidecar at {}".format(url))
socketio = connect_url(url)
print("Sending {infos} onto {url} on channel {channel}".format(**locals()))
socketio.emit(channel, json.dumps(infos), None)
