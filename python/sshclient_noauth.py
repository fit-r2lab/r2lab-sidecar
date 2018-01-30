# the standard paramiko SSHClient does not have the logic to use no authentication
# like we do on R2Lab between the gateway and slave nodes
# this subclass here lets us use the high-level SSHClient class
# without the various authentication schemes

from paramiko import SSHClient

class SSHClient_noauth(SSHClient):

    def _auth(self, username, *args):
        self._transport.auth_none(username)
        return
