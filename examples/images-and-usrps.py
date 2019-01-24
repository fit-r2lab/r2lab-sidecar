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

scope = [(x, f"{x:02d}") for x in range(1, 38)]

default_images_dir = "../../r2lab.inria.fr-raw/node-images"

from r2lab import (
    default_sidecar_url, SidecarSyncClient, SidecarPayload)

def images_infos(node_images):

    result = []
    root = Path(node_images)
    for index, name in scope:
        pictures = root.glob(f"*/fit{name}*")
        paths = [str(picture.relative_to(root))
                 for picture in pictures]
        print(f"{index} -> pictures")
        result.append({"id": index,
                       "images": paths})
    return result


def send_infos(infos, sidecar_url):
    print(f"connecting to {sidecar_url}")
    with SidecarSyncClient(sidecar_url) as sidecar:
        payload = SidecarPayload()
        payload.fill_from_infos(infos, category='nodes')
        sidecar.send_payload(payload)


def main():
    parser = ArgumentParser(formatter_class=ArgumentDefaultsHelpFormatter)
    parser.add_argument(
        "-u", "--sidecar-url", dest="sidecar_url",
        default=default_sidecar_url,
        help="url for the sidecar server")
    parser.add_argument(
        "-v", "--verbose", action='store_true', default=False)
    parser.add_argument(
        "-d", "--images-dir", dest='node_images',
        default=default_images_dir,
        help="location of the node-images local dir")
    args = parser.parse_args()

    infos = images_infos(args.node_images)
    if args.verbose:
        print(json.dumps(infos, indent=4))
    send_infos(infos, args.sidecar_url)

main()
