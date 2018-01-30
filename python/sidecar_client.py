#!/usr/bin/env python3

"""
This script emits messages to the sidecar server on faraday
to instruct it that some nodes are available or not
(use available.py or unavailable.py)
"""

from argparse import ArgumentParser
import json
import traceback
try:
    from urllib.parse import urlparse
except ImportError:
     from urlparse import urlparse

from socketIO_client import SocketIO, LoggingNamespace

# globals
default_sidecar_url = 'https://r2lab.inria.fr:999/'

glob_supported = {
    'node' : {
        '__range__': range(1, 38),
        'available' : ("on", "off"),
        'usrp_type' : ("b210", "n210", "usrp1", "usrp2"),
        },
    'phone' : {
        '__range__' : range(1, 2),
        'airplane_mode' : ("on", "off"),
        }
    }

def channel_name(type, prefix):
    return "{}:{}s".format(prefix, type)

def connect_url(url):
    parsed = urlparse(url)
    scheme, hostname, port \
            = parsed.scheme, parsed.hostname, parsed.port or 80
    if scheme not in ('http', 'https'):
        print("unsupported scheme {} - malformed socketio URL: {}"
              .format(scheme, url))
    if scheme == 'http':
        host_part = hostname
        extras = {}
    else:
        host_part = "https://{}".format(hostname)
        extras = {'verify' : False}
#        extras = {}
    print("url = {} -> host_part = {}, port = {}"
          .format(url, host_part, port))
    return SocketIO(host_part, port, LoggingNamespace, **extras)



def set_in_obj(socketio, type, channel, id, attribute, value):
    if id not in glob_supported[type]['__range__']:
        print("id {} out of range for type {}"
              .format(id, type))
        return
    if attribute not in glob_supported[type]:
        print("unknown attribute {} on type {}"
              .format(attribute, type))
        return
    if value not in glob_supported[type][attribute]:
        print("unknown value {} on attribute {}"
              .format(value, attribute))
        return
    infos = [{'id': id, attribute: value}]
    print("Sending {infos} on channel {channel}".format(**locals()))
    socketio.emit(channel, json.dumps(infos), None)


def main():
    parser = ArgumentParser()
    parser.add_argument("-t", "--type", choices=glob_supported.keys(), default="node",
                        help="Select one type of object to act on")
    parser.add_argument("set_triples", nargs='+',
                        metavar='node:attribute=value',
                        help="set value=attribute on given obj. id - additive")
    parser.add_argument("-u", "--sidecar-url", dest="sidecar_url",
                        default=default_sidecar_url,
                        help="url for thesidecar server (default={})"
                        .format(default_sidecar_url))
    args = parser.parse_args()

    print("Opening socketio connection to {}".format(args.sidecar_url))
    socketio = connect_url(args.sidecar_url)

    channel = channel_name(args.type, "info")
    for set_triple in args.set_triples:
        try:
            id, rest = set_triple.split(':')
            id = int(id)
            attribute, value = rest.split('=')
            set_in_obj(socketio, args.type, channel, id, attribute, value)
        except Exception as e:
            traceback.print_exc()
            exit(1)

if __name__ == '__main__':
    main()
