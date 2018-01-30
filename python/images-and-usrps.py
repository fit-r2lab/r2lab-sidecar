#!/usr/bin/env python3
# -*- coding: utf-8 -*-
from pathlib import Path
import re
import json
from argparse import ArgumentParser, ArgumentDefaultsHelpFormatter

"""
The job here is to
* take USRP details as hard-wired in this very script
* gather known images (from the contents of node-images on this box)
* and send all this to sidecar
"""

images_dir = "../../r2lab-raw/node-images"

from sidecar_client import default_sidecar_url, connect_url, set_in_obj, channel_name

infos = [
    dict(id=1, usrp_type='usrp2'),
    dict(id=6, usrp_type='b210', usrp_duplexer = 'for UE'),
    dict(id=11, usrp_type='b210'),
    dict(id=12, usrp_type='n210'),
    dict(id=13, usrp_type='usrp2'),
    dict(id=15, usrp_type='n210'),
    dict(id=16, usrp_type='b210', usrp_duplexer = 'for eNB'),
    dict(id=19, usrp_type='b210', usrp_duplexer = 'for eNB'),
    dict(id=20, usrp_type='none'),
    dict(id=21, usrp_type='usrp1'),
    dict(id=23, usrp_type='b210', usrp_duplexer = 'for eNB'),
    dict(id=27, usrp_type='n210'),
    dict(id=28, usrp_type='usrp1'),
    dict(id=30, usrp_type='n210'),
    dict(id=31, usrp_type='n210'),
    dict(id=36, usrp_type='n210'),
    dict(id=37, usrp_type='n210'),
    ]

# fill in / fast access
hash = { info['id']: info for info in infos }
for id in range(1, 38):
    if id not in hash:
        info = dict(id=id, usrp_type='none', usrp_duplexer=None)
        infos.append(info)
        hash[id] = info


def scan_images(infos):

    naming_re = re.compile("(?P<id>[0-9][0-9])-(?P<rest>.*)")

    for info in infos:
        info['images_usrp'] = []
        info['images_wifi'] = []
    
    top = Path(images_dir)
    print("scanning for images in {}".format(top))
    for image in top.glob('[0-9][0-9]-*'):
        basename = image.name
        match = naming_re.match(basename)
        id = int(match.group('id'))
        rest = match.group('rest')
        key = 'images_usrp' if 'u' in rest else 'images_wifi'
        hash[id][key].append(basename)

def send_infos(infos, sidecar_url):
    channel = channel_name('node', 'info')
    
    print("connection to channel {} @ {}".format(channel, sidecar_url))
    socketio = connect_url(sidecar_url)
    
    socketio.emit(channel, json.dumps(infos), None)


parser = ArgumentParser(formatter_class=ArgumentDefaultsHelpFormatter)
parser.add_argument("-u", "--sidecar-url", dest="sidecar_url",
                    default=default_sidecar_url,
                    help="url for the sidecar server")
parser.add_argument("-v", "--verbose")
args = parser.parse_args()
print(args)

scan_images(infos)
if args.verbose:
    print(json.dumps(infos, indent=4))
send_infos(infos, args.sidecar_url)



