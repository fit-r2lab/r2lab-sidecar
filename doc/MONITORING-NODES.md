# What monitornodes reports about a node

`monitornodes` (in the `rhubarbe` repo, `rhubarbe/monitor/nodes.py`, one service on faraday) probes each node
in its own task, and pushes one JSON record per node to the sidecar. The sidecar keeps the last record
of each node and broadcasts changes; it does not interpret anything, and can be trashed at any time (the
monitor fills it again). This page describes what is in these records, and how it is computed.

The model is built around two ideas

* **live flags** tell what answers *right now*, and are overwritten at each probe;
* **last known records** (`metal`, `container`) tell what was running the last time we could see it. They are
  kept while the node is off, or still booting, because that is useful to users; each carries a `seen`
  timestamp, so a consumer can tell how stale it is.

## The record

| key | content | set by |
|---|---|---|
| `id` | the node number, 1..37 | |
| `cmc_on_off` | `on`, `off`, or `fail` if the CMC card does not answer properly | CMC (http) |
| `usrp_on_off` | `on`, `off` or `fail` | CMC (http) |
| `control_ping` | `on` or `off`: the node is reachable | tcp scan, else ICMP ping |
| `control_ssh` | `on` or `off`: ssh answers *on any port* (22, or the docker host port) | ssh probes |
| `ssh_ports` | list of the ports where ssh answers: `[22]`, `[2222]`, `[22, 2222]` or `[]` | ssh probes |
| `control_telnet` | `on` or `off`; **only present if `probe_telnet` is on (the default)** | tcp scan |
| `state` | one label summarizing the above, see below | computed |
| `metal` | last known state of the bare machine, see below | ssh probes |
| `container` | last known state of the container, or `null`, see below | ssh probes |
| `static` | free-form record about the *position* (SDR, photos, ...); comes from `positions.yaml` through `inventory-nodes.yaml`; `null` if it vanishes | inventory |
| `availability` | `{status: ok|ko, reason, since}`; comes from r2lab-api, polled every `cycle_availability` seconds | r2lab-api |

Updates to the sidecar are shallow: each key of a message replaces the same key in the stored record.

### `metal`

`ssh_port`, `os_release` (e.g. `fedora-44`, from `/etc/os-release`), `pretty_name`, `image_radical`
(from `/etc/rhubarbe-image`), `uname`, `gnuradio_release`, `docker_version` (empty if no docker), `seen`.

### `container`

`null` on a regular node, and on a docker host that has no container. Otherwise `image`, `running`, `started`,
`os_release` and `pretty_name` (only visible through the container's own sshd on port 22, so kept from the
previous probe when the container is stopped and the image is the same), `seen`.

`seen` is not refreshed at each probe, otherwise the sidecar would broadcast all the time: only when the
record changes, or every 5 minutes.

## How a node is probed

One probe, then `cycle_nodes` seconds of sleep. Nodes are probed concurrently.

1. CMC `usrpstatus` and `status` (http). `off` or `fail`: report and stop.
2. A plain tcp connection (no data exchanged) to port 22, to the docker host port (`[docker] host_ssh_port`,
   2222), and, if `probe_telnet` is on, to port 23, all in parallel, with `[networking] tcp_timeout`. Each port
   is `open`, `closed` (refused, or rejected by a firewall: Fedora answers 'no route to host') or `filtered`
   (no answer in time).
3. If 23 is open, the node runs the image loader or saver: no ssh is tried (the two never coexist), the record
   is reported with `control_telnet: on`, and `metal` / `container` are left alone.
4. If 22 is open, ssh to it and run the commands that tell the os, `/etc/rhubarbe-image`, docker, and whether
   the sshd we reached is inside a container (`/.dockerenv` or `/run/.containerenv`, printed as
   `IN_CONTAINER:yes|no`). On a docker node, port 22 leads *into the container*, and the docker host has its own
   sshd on 2222: that marker is what tells them apart.
5. Then, from what we learned (the code is `MonitorNode.probe_setup`):
   * 22 answers and is not a container: this is a regular node, `metal` comes from this very probe and
     `container` is `null`, at once, so a node that is up for a few seconds only still gets its `metal` refreshed;
   * 22 answers with docker visible on it: a docker image whose own sshd is on 22, same, `metal` and `container`
     from this probe;
   * otherwise (22 is a container, or does not answer), if 2222 is not closed, ssh to the docker host on 2222:
     if it answers, `metal` and `container` come from there, and `control_ssh` is `on` even though 22 does not
     answer (a docker host without a container);
   * in all the other cases nothing is written, the last known records stay.
6. If nothing answered with ssh: `control_ping` is `on` if any port was open, otherwise we ping.

Whatever the order of the steps, `metal` and `container` are only ever written from a conclusive probe, never
reset when the node goes off, boots, or is loading an image.

## `state`

Computed in one place, `MonitorNode.update_state()`, from the flags:

| `state` | meaning | what answers |
|---|---|---|
| `off` | CMC says off | nothing |
| `unknown` | the CMC does not answer properly | |
| `bios` | on, no ping | the CMC only |
| `booting` | pings, nothing else yet (OS warming up) | ping |
| `telnet` | an image is being loaded or saved (needs `probe_telnet`) | port 23 |
| `regular` | a plain node | ssh on 22 |
| `container` | a docker node running its container | ssh on 22 (container) and 2222 (host), or 22 in a container with the host momentarily silent |
| `docker-only` | a docker host without its container: ready, nothing to log into | ssh on 2222 |
| `zombie` | `booting` for more than 3 minutes (`ZOMBIE_AFTER`) | ping |

`booting` and `zombie` look the same to one probe; the monitor keeps since when the node has been booting.

The older flat keys keep their meaning, so a consumer that does not know about `state` still works:
`control_ping`, `control_ssh`.

## The one-character summary in the logs

`monitornodes` logs one line every `log_period` seconds, one character per node (in the order of the
inventory), computed by `one_char_summary()`. A symbol means that the node cannot be ssh-ed yet; a letter
means that it can, and says which OS.

| char | |
|---|---|
| `·` | off |
| `○` | bios |
| `◔` | booting |
| `◑` | telnet |
| `⌂` | docker-only |
| `⊘` | zombie |
| `?` | unknown, or no state yet |
| `F` `U` `D` `C` `R` `^` | regular node: fedora, ubuntu, debian, centos, rocky, other |
| `f` `u` `d` `c` `r` `*` | container: the same, for the OS of the container, which is what the user runs |

## Configuration (`rhubarbe.conf`)

* `[monitor] cycle_nodes`: sleep between two probes of a node
* `[monitor] cycle_availability`: how often r2lab-api is polled for availability
* `[monitor] probe_telnet`: look at port 23; **on by default**; set to false if a bare tcp
  connection turns out to disturb a running rload or rsave
* `[networking] tcp_timeout`, `ssh_timeout`, `ping_timeout`
* `[docker] host_ssh_port`

## Who reads and writes what

* written by `rhubarbe/monitor/nodes.py`; `static` is read from `InventoryNodes`
  (`rhubarbe/inventorynodes.py`), `availability` from r2lab-api (`rhubarbe/r2labapiproxy.py`)
* read by the web UI, `r2lab.inria.fr/django/assets/r2lab/`: `livemap.js` (the size of a node follows the flags;
  `state` only tells `telnet` and `zombie` apart), `livetable.js`, `livecolumns.js`, `livehardware.js`,
  `distros.js` (which os to show, and whether `metal` is current)
* simulated by `r2lab-python/examples/animate.py`, to try the UI and the sidecar without a testbed; described in
  `r2lab-python/r2lab/sidecar_payload.py` (`SUPPORTED`, informational)
* `rhubarbe/monitor/prometheus.py` exports `cmc_on_off`, `usrp_on_off`, `control_ssh` and `control_ping`
* where to change what, for the sources of truth (`static`, `availability`): see
  `r2lab-misc/inventory/AA-where-to-change-what.excalidraw.svg`
