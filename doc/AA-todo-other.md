This is about known issues and other similar stuff

# web plugins

 * investigate many 'could not parse JSON' errors
 * materialize gnuradio; 2 angles
   * show static info about nodes that have the right hardware
   * show dynamic info about gnuradio being installed on nodes or not

# rhubarbe / monitor

* seems like sometimes the monitor gets lost and does not do its job properly

# sidecar

* extend with leases
* foresee for 'hard' leases that come from omf_sfa, and 'soft' leases that are just intentions (not yet validated...)

# deployment

* ssh connection from r2lab to faraday is WORKING

# django authentication

Let's start with a summary of how authentication info is exposed across the system

### exposed context 

###### python

* `request.session` has a `r2lab_context` field

###### templates

* `r2lab_context` is available to the templates when logged in

###### javascript

* from `templates/r2lab/r2lab_user.js`; for now this exposes
* `r2lab_user` : the **email** of logged in user
* `r2lab_hrn` : **hrn** for that user
* `r2lab_slices` : the list of slice hrn's that the user is a member of


### Look & feel
* login / password points at **LOCAL** login (i.e. **not** for logging into the portal anymore)
* for now there still is a **Access the portal** button **but only when not logged in**
  * however this is replaced with a **logout** button, so there is **no reference to the portal** anymore **when logged in**
* which means that we'll probably a better integrated logged-in widget at some point, that summarizes email, and the logout button; list of slices (+ the current one) probably don't belong here but some place else in the page, tbd...

### Low-priority business

This is about how to display various info from the previous page; the following are available as first-class citizens to templates (i.e. not as part of `r2lab_context`, as they are **not persistent** across a session)

* `previous_message` is something that would need to be emphasized in the main template; not really sure this is particularly useful when using AJAX, so might by trashed
* `login_message` is set right after a login attempt - to say if it succeeded or not; might need to be merged with `previous_message` in some way; probably useful only when a login attempt is failing so this should go into the login_widget I believe


# architecture / migration or `r2lab` inside the faraday network

* we now have an IP address declared on the same subnet as faraday
* `138.96.16.98 r2lab-vm.inria.fr`

It could sound like a good idea to migrate the `r2lab.inria.fr` services in the same physical box as faraday. However it remains to understand, how to face the following challenges:

* we'd need 2 VM's in a single box (currently faraday)
* with a rather special networking setup (e.g. trunking on the optical link)

* is using a kvm for the new `r2lab` a workable option ?
  * in this case we'd really want the VM to use a disk in pass-through mode and not through an image, [like possibly explained here](http://serverfault.com/questions/410210/kvm-qemu-use-lvm-volumes-directly-without-image-file)

* ubuntu does not advise the use of libvirt/lxc (lack of apparmor); in our case anyway we'd probably much rather use fedora libvirt/lxc like on all the other cloud boxes.
* this however would require to
  * backup dismantle the current ubuntu setup
  * install fedora/libvirt blabla
  * redo the networking setup (in fedora; was in ubuntu)
  * create a dummy ubuntu and re-populate (including omf_sfa and nitos and everything)
  * **NOTE**: at all cost **refrain from going to fedora** directly; step1=ubuntu; which does not prevent from doing a step2 in fedora and see how this goes)
  * this VM needs with network interfaces towards public internet + nodes
  * then create a second fedora VM for r2lab - this would be easy enough, excapt that only the public internet would be accessible from that box.

* to make it worse, this migration should **not last too long**

* finally, note that if we ever go to an SFA wrapper as a replacement for `omf-sfa`, then all this painful stuff is just useless....

**It feels really urgent to wait until all this fog clears up...**