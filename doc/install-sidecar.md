# install sidecar on `r2lab.inria.fr`

## git

    yum install git
    cd /root
    git clone https://github.com/fit-r2lab/r2lab-sidecar.git
    
## node.js

### r2lab (fedora)
    yum install -y nodejs npm
    
## install nodejs dependencies
 
    cd /root/r2lab-sidecar
    npm install

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
    
* when running a devel server: as of Jan 2017 : we use 999 (over
https) and not 443 any longer as the port number for sidecar, as
r2lab.inria.fr runs on https In any case you need to run your devel
instance of `sidecar.js` like as follows, option `-l` allows to log in
a local file instead of `/var/log/sidecar.log`:

    $ sudo sidecar.js -l
