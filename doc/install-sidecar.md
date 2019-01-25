# install sidecar on `r2lab.inria.fr`

## git

    yum install git
    cd /root
    git clone https://github.com/fit-r2lab/r2lab-sidecar.git

## python

Requires python3 and websokets

    pip3 install websockets
    
## install systemd service file

    cd /root/r2lab-sidecar
    rsync -ai systemd/sidecar.service /etc/systemd/system
    systemctl enable sidecar

## run manually

    systemctl start sidecar
    journalct --unit=sidecar -f
    
NOTES

* `(hostname ignored)` means that the hostname part in the URL is not
  used, of course, only the protocol and port numbers matter in the
  URL.
    
* Ports
  * default prod. mode is on port 999 (wss://r2lab.inria.fr:999/)
  * default devel mode (with -d/--devel) is on 10000 (ws://localhost:10000)

    $ sidecar-server.py --devel
