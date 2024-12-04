# The R2lab infra architecture

![Overview](AA-1-statusflow.png)

## updates

* every piece of code that might be of interest to either the infra (or the nodes, btw) is kept in a git repository `r2lab-embedded`
* this contains `services/pull-and-restart.sh` and related systemd files (service, timer), which takes care of updating the code on a regular basis

## faraday

runs several services

* in order to retrieve state from the hardware, through dedicated code:
  * service `monitornodes`
  * service `monitorphones`
  * service `monitorpdus`
  * then each of these 3 services pushes its data to the sidecar server
* refreshing the leases, by asking the PLCAPI over xmlrpc
  * service `monitorleases`
  * this also pushes its data to the sidecar server
* syncing the current user accounts from the PLCAPI
  * service `accountsmanager`
  * this does side effects on `/etc/passwd` and related system files, as well as on users `authorized_keys` files

all this is part of `rhubarbe` which is `pip install`'ed

## r2lab

runs primarily the folloiwng services

* `nginx` that does the SSL / https termination (and hands over to sjango using `gunicorn`)
* `r2lab-django` that serves the web interface
* `r2lab-sidecar` that runs the websockets server

as of end of 2024, this comes from

* `pip install r2lab-sidecar`
* and the website is cloned in `/root/r2lab.inria.fr` and `/root/r2lab.inria.fr-raw`

# devel notes

===== xxx here ===

* talk about the make targets and the conda envs to run devel code on both faraday and r2lab
* talk about the sattic web sidecar client
* talk about r2lab-sidecar as a separate address to be able to use port 443 b/c of common firewall rules on public networks


* run `monitor.py 19 22 23` for focusing on a set of nodes only

* run `animate.py` locally to simulate new random events cyclically

* OUTDATED run `sudo sidecar.js -l` when running locally on a devel box; this will use json files in current directory as opposed to in `/var/lib/sidecar/`; also `sudo` is required to bind to privileged port `999`;

* note that you can also use the -u option to use either http or https, or to run on another port number; when running the django server locally you can specify the sidecar URL in `settings.py`; sudo won't be necessary if you run on a port > 1024

* run `sudo sidecar.js -l -v` for verbose output

## JSON files

  * the 2 `json` files are essentially second-order and do not matter at all
  * `complete.json` essentially is a way to store stuff across a restart of the sidecar (which is done every 10 minutes)
  * `news.json` was a first attempt at providing an easy way to post new things, but this is not needed **at all* anymore

## JSON format

## v0 - up to 2016/10

What was flying on the bus was of 2 kinds

### `leases`

* on channels `chan-leases` and `chan-leases-request`
* no change made in this area

### `status`

* on channels `chan-status` and `chan-status-request`
* a (possibly partial) list of records
* each one having a mandatory `id` field, an integer
* this is implicitly about **nodes** since there was no other type of info available
* the set of known fields in this record is
  * `id` : node id
  * `available` : set manually by other means (nightly)
  * `cmc_on_off`
  * `control_ping`
  * `control_ssh`
  * `os_release`:
    * string from `/etc/fedora-release /etc/lsb-release`
    * it would end with `-gnuradio-{version}` if present
  * `image_radical` : string from last line of `/etc/rhubarbe-image`
  * `wlan<n>_[rt]x_rate` - still in monitor.py --wlan but not mostly obsolete otherwise

## v1 - end october 2016

### channel names

All channels are renamed as follows for consistency

| old name            | new name       |
|---------------------|----------------|
| `chan-leases`         | `info:leases`    |
| `chan-leases-request` | `request:leases` |
| `chan-status`         | **`info:nodes`**     |
| `chan-status-request` | **`request:nodes`**  |
|                       | `info:phones` |
|							| `request:phones` |

### `phones`

* on the new channels `chan-phones` and `chan-phones-request`
* we have a mechanism very close to the `nodes` thingy
* with the following fields for now
  * `wifi_on_off`: "on" or "off" or "fail"
  * `airplane_mode` : "on" or "off" or "fail"

### `nodes`

#### renamings
  * the `chan-status` channel into `channel:nodes`
  * the `chan-status-request` channel into `channel:nodes-request`

#### more data probed for each node

* **OK** `usrp_on_off` : "on" or "off" or "fail"
  * frequent updates from `monitor`
* `usrp_type` : "b210" or "x310" or "none"
  * **needs to be filled manually** for starters - a bit like `available`
  * ideally the nightly should do that later on
* **OK** `gnuradio_release`: 'none' or a version string
  * this would undo the kind of hack we had in place previously
  * that would piggyback the gnuradio version on top of `os_release`
* **OK** `uname`: could be beneficially added in the mix, in order to detect stupid mistakes earlier

