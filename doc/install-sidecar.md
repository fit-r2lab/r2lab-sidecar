# install sidecar on `r2lab.inria.fr`

## python

```bash
pip3 install r2lab-sidecar
```

## install systemd service file

for gory reasons, because we use `pyproject.toml` and `hatch` for packaging,
the service file is currently not packaged with the package

so get the service file (in `systemd/sidecar.service`) from the git repository
and install it manually in `/etc/systemd/system`

then enable and start the service

```bash

rsync -ai systemd/sidecar.service root@r2lab.inria.fr:/etc/systemd/system
ssh root@r2lab.inria.fr
systemctl enable sidecar
```
