# The R2lab infra architecture

![Overview](AA-statusflow.excalidraw.svg)

## updates

* every piece of code that might be of interest to either the infra (or the nodes, btw) is kept in a git repository `r2lab-embedded`
* this contains `services/run-updates.sh` and related systemd unit files (service, timer), that run hourly on faraday, r2lab and r2labapi (and on distrait, for `r2lab-embedded` only)
* for each git repo listed for the host in `services/hosts/`, it follows the upstream branch, and when that has changed it runs the repo's own `deploy/update.sh`, which builds and restarts what needs to be
* each of these repos also keeps its systemd unit files in its `deploy/` folder, installed with `systemctl link`

## faraday

runs several services

* in order to retrieve state from the hardware, through dedicated code:
  * service `monitornodes`
  * service `monitorphones`
  * service `monitorpdus`
  * then each of these 3 services pushes its data to the sidecar server
* syncing the current user accounts from the PLCAPI
  * service `accountsmanager`
  * this does side effects on `/etc/passwd` and related system files, as well as on users `authorized_keys` files

all this is part of `rhubarbe`; the services run from the git repo cloned in `/opt/rhubarbe`, with its own uv environment, that is updated by the above;
regular users on faraday still use the `pip install`'ed version, that is upgraded by hand

## r2lab

runs primarily the folloiwng services

* `nginx` that does the SSL / https termination (and hands over to sjango using `gunicorn`)
* `r2lab-django` that serves the web interface
* `r2lab-sidecar` that runs the websockets server

all this is cloned from git, and updated hourly as described above

* the sidecar is in `/root/r2lab-sidecar`, and runs in its own uv environment
* the website is in `/root/r2lab.inria.fr` and `/root/r2lab.inria.fr-raw`, and is published in `/var/www/r2lab.inria.fr`

## sidecar client

in the `web` folder you will find a simple client that connects to the sidecar server and listens to the websocket

```bash
# open this file in your browser
open web/sidecar-client.html
```

with that tool one can

- select another server to connect to
- connect/disconnect
- ask for a refresh of the status
- see the resulting messages

## addressing

for better firewall traversal, the sidecar server is **running on port 443** on a dedicated IP address, `r2lab-sidecar.inria.fr`

## devel notes

on r2lab.inria.fr, we have a conda environment `r2lab-dev-314` (change name when
moving to future Pythons)  
that is used to run the sidecar code in a debug/development mode

so to test before packaging:

```bash
cd r2lab-sidecar
# push on r2lab.inria.fr
make r2lab

# follow instructions on the remote
ssh root@r2lab.inria.fr
conda activate r2lab-dev-314
pip install -e /tmp/r2lab-dev-sidecar

r2lab-sidecar --debug
```

## devel / local tools

see also the `r2lab-python` repository, and its `examples` folder, for a tool
`animate.py` that can send the sidecar server random events

## JSON files

the sidecar server maintains 3 files in `/var/lib/r2lab-sidecar`

* `nodes.json`
* `phones.json`
* `pdus.json`

as far as the content of each file, it is pretty straightforward, use the web
client (sidecar-client.html) for details on the various structures
