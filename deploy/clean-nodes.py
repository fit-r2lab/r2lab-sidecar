#!/usr/bin/env python3
"""
Remove from the sidecar's nodes.json the attributes that the monitor
(rhubarbe monitornodes) produces, so that the database starts afresh and the
monitor fills it again at its next cycles.

What is left is what comes from other sources and that the monitor does not
re-create: id, available, data_interface, images, images_usrp, images_wifi,
usrp_type, usrp_duplexer, usrp_logo...

The sidecar keeps all this in memory and rewrites the file when something
changes, so STOP IT FIRST, or the edit will be overwritten:

    systemctl stop r2lab-sidecar
    ./clean-nodes.py [--dry-run] [/var/lib/sidecar/nodes.json]
    systemctl start r2lab-sidecar

A copy of the file is saved next to it, with a timestamp.
"""

import json
import os
import shutil
import sys
import time
from argparse import ArgumentParser
from pathlib import Path

# everything that MonitorNode (rhubarbe/monitor/nodes.py) sets
VOLATILE = (
    # live status
    'cmc_on_off', 'usrp_on_off', 'control_ping', 'control_ssh',
    # what runs on the node, flat keys
    'os_release', 'gnuradio_release', 'uname', 'image_radical',
    'docker_version', 'container_running', 'container_image',
    'container_started',
    # what runs on the node, sub-records
    'metal', 'container',
)


def main():
    parser = ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("file", nargs="?", default="/var/lib/sidecar/nodes.json")
    parser.add_argument("--dry-run", action="store_true",
                        help="only say what would be removed")
    parser.add_argument("-k", "--keep", action="append", default=[],
                        help="a key to keep, even if in the list (repeatable)")
    args = parser.parse_args()

    path = Path(args.file)
    nodes = json.loads(path.read_text())
    wanted = [key for key in VOLATILE if key not in args.keep]
    removed = {}
    for node in nodes:
        for key in wanted:
            if key in node:
                del node[key]
                removed[key] = removed.get(key, 0) + 1

    for key in wanted:
        print(f"{removed.get(key, 0):4} x {key}")
    print(f"{len(nodes)} nodes, {sum(removed.values())} values removed")
    if args.dry_run:
        print("dry run: nothing written")
        return 0

    backup = path.with_name(f"{path.name}.{time.strftime('%Y%m%d-%H%M%S')}")
    shutil.copy2(path, backup)
    temporary = path.with_name(path.name + ".tmp")
    temporary.write_text(json.dumps(nodes))
    os.replace(temporary, path)
    print(f"written {path} (previous version in {backup})")
    return 0


if __name__ == "__main__":
    sys.exit(main())
