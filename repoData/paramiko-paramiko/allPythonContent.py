__FILENAME__ = demo
#!/usr/bin/env python

# Copyright (C) 2003-2007  Robey Pointer <robeypointer@gmail.com>
#
# This file is part of paramiko.
#
# Paramiko is free software; you can redistribute it and/or modify it under the
# terms of the GNU Lesser General Public License as published by the Free
# Software Foundation; either version 2.1 of the License, or (at your option)
# any later version.
#
# Paramiko is distributed in the hope that it will be useful, but WITHOUT ANY
# WARRANTY; without even the implied warranty of MERCHANTABILITY or FITNESS FOR
# A PARTICULAR PURPOSE.  See the GNU Lesser General Public License for more
# details.
#
# You should have received a copy of the GNU Lesser General Public License
# along with Paramiko; if not, write to the Free Software Foundation, Inc.,
# 59 Temple Place, Suite 330, Boston, MA  02111-1307  USA.


import base64
from binascii import hexlify
import getpass
import os
import select
import socket
import sys
import time
import traceback
from paramiko.py3compat import input

import paramiko
try:
    import interactive
except ImportError:
    from . import interactive


def agent_auth(transport, username):
    """
    Attempt to authenticate to the given transport using any of the private
    keys available from an SSH agent.
    """
    
    agent = paramiko.Agent()
    agent_keys = agent.get_keys()
    if len(agent_keys) == 0:
        return
        
    for key in agent_keys:
        print('Trying ssh-agent key %s' % hexlify(key.get_fingerprint()))
        try:
            transport.auth_publickey(username, key)
            print('... success!')
            return
        except paramiko.SSHException:
            print('... nope.')


def manual_auth(username, hostname):
    default_auth = 'p'
    auth = input('Auth by (p)assword, (r)sa key, or (d)ss key? [%s] ' % default_auth)
    if len(auth) == 0:
        auth = default_auth

    if auth == 'r':
        default_path = os.path.join(os.environ['HOME'], '.ssh', 'id_rsa')
        path = input('RSA key [%s]: ' % default_path)
        if len(path) == 0:
            path = default_path
        try:
            key = paramiko.RSAKey.from_private_key_file(path)
        except paramiko.PasswordRequiredException:
            password = getpass.getpass('RSA key password: ')
            key = paramiko.RSAKey.from_private_key_file(path, password)
        t.auth_publickey(username, key)
    elif auth == 'd':
        default_path = os.path.join(os.environ['HOME'], '.ssh', 'id_dsa')
        path = input('DSS key [%s]: ' % default_path)
        if len(path) == 0:
            path = default_path
        try:
            key = paramiko.DSSKey.from_private_key_file(path)
        except paramiko.PasswordRequiredException:
            password = getpass.getpass('DSS key password: ')
            key = paramiko.DSSKey.from_private_key_file(path, password)
        t.auth_publickey(username, key)
    else:
        pw = getpass.getpass('Password for %s@%s: ' % (username, hostname))
        t.auth_password(username, pw)


# setup logging
paramiko.util.log_to_file('demo.log')

username = ''
if len(sys.argv) > 1:
    hostname = sys.argv[1]
    if hostname.find('@') >= 0:
        username, hostname = hostname.split('@')
else:
    hostname = input('Hostname: ')
if len(hostname) == 0:
    print('*** Hostname required.')
    sys.exit(1)
port = 22
if hostname.find(':') >= 0:
    hostname, portstr = hostname.split(':')
    port = int(portstr)

# now connect
try:
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    sock.connect((hostname, port))
except Exception as e:
    print('*** Connect failed: ' + str(e))
    traceback.print_exc()
    sys.exit(1)

try:
    t = paramiko.Transport(sock)
    try:
        t.start_client()
    except paramiko.SSHException:
        print('*** SSH negotiation failed.')
        sys.exit(1)

    try:
        keys = paramiko.util.load_host_keys(os.path.expanduser('~/.ssh/known_hosts'))
    except IOError:
        try:
            keys = paramiko.util.load_host_keys(os.path.expanduser('~/ssh/known_hosts'))
        except IOError:
            print('*** Unable to open host keys file')
            keys = {}

    # check server's host key -- this is important.
    key = t.get_remote_server_key()
    if hostname not in keys:
        print('*** WARNING: Unknown host key!')
    elif key.get_name() not in keys[hostname]:
        print('*** WARNING: Unknown host key!')
    elif keys[hostname][key.get_name()] != key:
        print('*** WARNING: Host key has changed!!!')
        sys.exit(1)
    else:
        print('*** Host key OK.')

    # get username
    if username == '':
        default_username = getpass.getuser()
        username = input('Username [%s]: ' % default_username)
        if len(username) == 0:
            username = default_username

    agent_auth(t, username)
    if not t.is_authenticated():
        manual_auth(username, hostname)
    if not t.is_authenticated():
        print('*** Authentication failed. :(')
        t.close()
        sys.exit(1)

    chan = t.open_session()
    chan.get_pty()
    chan.invoke_shell()
    print('*** Here we go!\n')
    interactive.interactive_shell(chan)
    chan.close()
    t.close()

except Exception as e:
    print('*** Caught exception: ' + str(e.__class__) + ': ' + str(e))
    traceback.print_exc()
    try:
        t.close()
    except:
        pass
    sys.exit(1)



########NEW FILE########
__FILENAME__ = demo_keygen
#!/usr/bin/env python

# Copyright (C) 2010 Sofian Brabez <sbz@6dev.net>
#
# This file is part of paramiko.
#
# Paramiko is free software; you can redistribute it and/or modify it under the
# terms of the GNU Lesser General Public License as published by the Free
# Software Foundation; either version 2.1 of the License, or (at your option)
# any later version.
#
# Paramiko is distributed in the hope that it will be useful, but WITHOUT ANY
# WARRANTY; without even the implied warranty of MERCHANTABILITY or FITNESS FOR
# A PARTICULAR PURPOSE.  See the GNU Lesser General Public License for more
# details.
#
# You should have received a copy of the GNU Lesser General Public License
# along with Paramiko; if not, write to the Free Software Foundation, Inc.,
# 59 Temple Place, Suite 330, Boston, MA  02111-1307  USA.

import sys

from binascii import hexlify
from optparse import OptionParser

from paramiko import DSSKey
from paramiko import RSAKey
from paramiko.ssh_exception import SSHException
from paramiko.py3compat import u

usage="""
%prog [-v] [-b bits] -t type [-N new_passphrase] [-f output_keyfile]"""

default_values = {
    "ktype": "dsa",
    "bits": 1024,
    "filename": "output",
    "comment": ""
}

key_dispatch_table = {
    'dsa': DSSKey,
    'rsa': RSAKey,
}

def progress(arg=None):

    if not arg:
        sys.stdout.write('0%\x08\x08\x08 ')
        sys.stdout.flush()
    elif arg[0] == 'p':
        sys.stdout.write('25%\x08\x08\x08\x08 ')
        sys.stdout.flush()
    elif arg[0] == 'h':
        sys.stdout.write('50%\x08\x08\x08\x08 ')
        sys.stdout.flush()
    elif arg[0] == 'x':
        sys.stdout.write('75%\x08\x08\x08\x08 ')
        sys.stdout.flush()

if __name__ == '__main__':

    phrase=None
    pfunc=None

    parser = OptionParser(usage=usage)
    parser.add_option("-t", "--type", type="string", dest="ktype",
        help="Specify type of key to create (dsa or rsa)",
        metavar="ktype", default=default_values["ktype"])
    parser.add_option("-b", "--bits", type="int", dest="bits",
        help="Number of bits in the key to create", metavar="bits",
        default=default_values["bits"])
    parser.add_option("-N", "--new-passphrase", dest="newphrase",
        help="Provide new passphrase", metavar="phrase")
    parser.add_option("-P", "--old-passphrase", dest="oldphrase",
        help="Provide old passphrase", metavar="phrase")
    parser.add_option("-f", "--filename", type="string", dest="filename",
        help="Filename of the key file", metavar="filename",
        default=default_values["filename"])
    parser.add_option("-q", "--quiet", default=False, action="store_false",
        help="Quiet")
    parser.add_option("-v", "--verbose", default=False, action="store_true",
        help="Verbose")
    parser.add_option("-C", "--comment", type="string", dest="comment",
        help="Provide a new comment", metavar="comment",
        default=default_values["comment"])

    (options, args) = parser.parse_args()

    if len(sys.argv) == 1:
        parser.print_help()
        sys.exit(0)

    for o in list(default_values.keys()):
        globals()[o] = getattr(options, o, default_values[o.lower()])

    if options.newphrase:
        phrase = getattr(options, 'newphrase')

    if options.verbose:
        pfunc = progress
        sys.stdout.write("Generating priv/pub %s %d bits key pair (%s/%s.pub)..." % (ktype, bits, filename, filename))
        sys.stdout.flush()

    if ktype == 'dsa' and bits > 1024:
        raise SSHException("DSA Keys must be 1024 bits")

    if ktype not in key_dispatch_table:
        raise SSHException("Unknown %s algorithm to generate keys pair" % ktype)

    # generating private key
    prv = key_dispatch_table[ktype].generate(bits=bits, progress_func=pfunc)
    prv.write_private_key_file(filename, password=phrase)

    # generating public key
    pub = key_dispatch_table[ktype](filename=filename, password=phrase)
    with open("%s.pub" % filename, 'w') as f:
        f.write("%s %s" % (pub.get_name(), pub.get_base64()))
        if options.comment:
            f.write(" %s" % comment)

    if options.verbose:
        print("done.")

    hash = u(hexlify(pub.get_fingerprint()))
    print("Fingerprint: %d %s %s.pub (%s)" % (bits, ":".join([ hash[i:2+i] for i in range(0, len(hash), 2)]), filename, ktype.upper()))

########NEW FILE########
__FILENAME__ = demo_server
#!/usr/bin/env python

# Copyright (C) 2003-2007  Robey Pointer <robeypointer@gmail.com>
#
# This file is part of paramiko.
#
# Paramiko is free software; you can redistribute it and/or modify it under the
# terms of the GNU Lesser General Public License as published by the Free
# Software Foundation; either version 2.1 of the License, or (at your option)
# any later version.
#
# Paramiko is distributed in the hope that it will be useful, but WITHOUT ANY
# WARRANTY; without even the implied warranty of MERCHANTABILITY or FITNESS FOR
# A PARTICULAR PURPOSE.  See the GNU Lesser General Public License for more
# details.
#
# You should have received a copy of the GNU Lesser General Public License
# along with Paramiko; if not, write to the Free Software Foundation, Inc.,
# 59 Temple Place, Suite 330, Boston, MA  02111-1307  USA.

import base64
from binascii import hexlify
import os
import socket
import sys
import threading
import traceback

import paramiko
from paramiko.py3compat import b, u, decodebytes


# setup logging
paramiko.util.log_to_file('demo_server.log')

host_key = paramiko.RSAKey(filename='test_rsa.key')
#host_key = paramiko.DSSKey(filename='test_dss.key')

print('Read key: ' + u(hexlify(host_key.get_fingerprint())))


class Server (paramiko.ServerInterface):
    # 'data' is the output of base64.encodestring(str(key))
    # (using the "user_rsa_key" files)
    data = (b'AAAAB3NzaC1yc2EAAAABIwAAAIEAyO4it3fHlmGZWJaGrfeHOVY7RWO3P9M7hp'
            b'fAu7jJ2d7eothvfeuoRFtJwhUmZDluRdFyhFY/hFAh76PJKGAusIqIQKlkJxMC'
            b'KDqIexkgHAfID/6mqvmnSJf0b5W8v5h2pI/stOSwTQ+pxVhwJ9ctYDhRSlF0iT'
            b'UWT10hcuO4Ks8=')
    good_pub_key = paramiko.RSAKey(data=decodebytes(data))

    def __init__(self):
        self.event = threading.Event()

    def check_channel_request(self, kind, chanid):
        if kind == 'session':
            return paramiko.OPEN_SUCCEEDED
        return paramiko.OPEN_FAILED_ADMINISTRATIVELY_PROHIBITED

    def check_auth_password(self, username, password):
        if (username == 'robey') and (password == 'foo'):
            return paramiko.AUTH_SUCCESSFUL
        return paramiko.AUTH_FAILED

    def check_auth_publickey(self, username, key):
        print('Auth attempt with key: ' + u(hexlify(key.get_fingerprint())))
        if (username == 'robey') and (key == self.good_pub_key):
            return paramiko.AUTH_SUCCESSFUL
        return paramiko.AUTH_FAILED

    def get_allowed_auths(self, username):
        return 'password,publickey'

    def check_channel_shell_request(self, channel):
        self.event.set()
        return True

    def check_channel_pty_request(self, channel, term, width, height, pixelwidth,
                                  pixelheight, modes):
        return True


# now connect
try:
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    sock.bind(('', 2200))
except Exception as e:
    print('*** Bind failed: ' + str(e))
    traceback.print_exc()
    sys.exit(1)

try:
    sock.listen(100)
    print('Listening for connection ...')
    client, addr = sock.accept()
except Exception as e:
    print('*** Listen/accept failed: ' + str(e))
    traceback.print_exc()
    sys.exit(1)

print('Got a connection!')

try:
    t = paramiko.Transport(client)
    try:
        t.load_server_moduli()
    except:
        print('(Failed to load moduli -- gex will be unsupported.)')
        raise
    t.add_server_key(host_key)
    server = Server()
    try:
        t.start_server(server=server)
    except paramiko.SSHException:
        print('*** SSH negotiation failed.')
        sys.exit(1)

    # wait for auth
    chan = t.accept(20)
    if chan is None:
        print('*** No channel.')
        sys.exit(1)
    print('Authenticated!')

    server.event.wait(10)
    if not server.event.isSet():
        print('*** Client never asked for a shell.')
        sys.exit(1)

    chan.send('\r\n\r\nWelcome to my dorky little BBS!\r\n\r\n')
    chan.send('We are on fire all the time!  Hooray!  Candy corn for everyone!\r\n')
    chan.send('Happy birthday to Robot Dave!\r\n\r\n')
    chan.send('Username: ')
    f = chan.makefile('rU')
    username = f.readline().strip('\r\n')
    chan.send('\r\nI don\'t like you, ' + username + '.\r\n')
    chan.close()

except Exception as e:
    print('*** Caught exception: ' + str(e.__class__) + ': ' + str(e))
    traceback.print_exc()
    try:
        t.close()
    except:
        pass
    sys.exit(1)


########NEW FILE########
__FILENAME__ = demo_sftp
#!/usr/bin/env python

# Copyright (C) 2003-2007  Robey Pointer <robeypointer@gmail.com>
#
# This file is part of paramiko.
#
# Paramiko is free software; you can redistribute it and/or modify it under the
# terms of the GNU Lesser General Public License as published by the Free
# Software Foundation; either version 2.1 of the License, or (at your option)
# any later version.
#
# Paramiko is distributed in the hope that it will be useful, but WITHOUT ANY
# WARRANTY; without even the implied warranty of MERCHANTABILITY or FITNESS FOR
# A PARTICULAR PURPOSE.  See the GNU Lesser General Public License for more
# details.
#
# You should have received a copy of the GNU Lesser General Public License
# along with Paramiko; if not, write to the Free Software Foundation, Inc.,
# 59 Temple Place, Suite 330, Boston, MA  02111-1307  USA.

# based on code provided by raymond mosteller (thanks!)

import base64
import getpass
import os
import socket
import sys
import traceback

import paramiko
from paramiko.py3compat import input


# setup logging
paramiko.util.log_to_file('demo_sftp.log')

# get hostname
username = ''
if len(sys.argv) > 1:
    hostname = sys.argv[1]
    if hostname.find('@') >= 0:
        username, hostname = hostname.split('@')
else:
    hostname = input('Hostname: ')
if len(hostname) == 0:
    print('*** Hostname required.')
    sys.exit(1)
port = 22
if hostname.find(':') >= 0:
    hostname, portstr = hostname.split(':')
    port = int(portstr)


# get username
if username == '':
    default_username = getpass.getuser()
    username = input('Username [%s]: ' % default_username)
    if len(username) == 0:
        username = default_username
password = getpass.getpass('Password for %s@%s: ' % (username, hostname))


# get host key, if we know one
hostkeytype = None
hostkey = None
try:
    host_keys = paramiko.util.load_host_keys(os.path.expanduser('~/.ssh/known_hosts'))
except IOError:
    try:
        # try ~/ssh/ too, because windows can't have a folder named ~/.ssh/
        host_keys = paramiko.util.load_host_keys(os.path.expanduser('~/ssh/known_hosts'))
    except IOError:
        print('*** Unable to open host keys file')
        host_keys = {}

if hostname in host_keys:
    hostkeytype = host_keys[hostname].keys()[0]
    hostkey = host_keys[hostname][hostkeytype]
    print('Using host key of type %s' % hostkeytype)


# now, connect and use paramiko Transport to negotiate SSH2 across the connection
try:
    t = paramiko.Transport((hostname, port))
    t.connect(username=username, password=password, hostkey=hostkey)
    sftp = paramiko.SFTPClient.from_transport(t)

    # dirlist on remote host
    dirlist = sftp.listdir('.')
    print("Dirlist: %s" % dirlist)

    # copy this demo onto the server
    try:
        sftp.mkdir("demo_sftp_folder")
    except IOError:
        print('(assuming demo_sftp_folder/ already exists)')
    with sftp.open('demo_sftp_folder/README', 'w') as f:
        f.write('This was created by demo_sftp.py.\n')
    with open('demo_sftp.py', 'r') as f:
        data = f.read()
    sftp.open('demo_sftp_folder/demo_sftp.py', 'w').write(data)
    print('created demo_sftp_folder/ on the server')
    
    # copy the README back here
    with sftp.open('demo_sftp_folder/README', 'r') as f:
        data = f.read()
    with open('README_demo_sftp', 'w') as f:
        f.write(data)
    print('copied README back here')
    
    # BETTER: use the get() and put() methods
    sftp.put('demo_sftp.py', 'demo_sftp_folder/demo_sftp.py')
    sftp.get('demo_sftp_folder/README', 'README_demo_sftp')

    t.close()

except Exception as e:
    print('*** Caught exception: %s: %s' % (e.__class__, e))
    traceback.print_exc()
    try:
        t.close()
    except:
        pass
    sys.exit(1)

########NEW FILE########
__FILENAME__ = demo_simple
#!/usr/bin/env python

# Copyright (C) 2003-2007  Robey Pointer <robeypointer@gmail.com>
#
# This file is part of paramiko.
#
# Paramiko is free software; you can redistribute it and/or modify it under the
# terms of the GNU Lesser General Public License as published by the Free
# Software Foundation; either version 2.1 of the License, or (at your option)
# any later version.
#
# Paramiko is distributed in the hope that it will be useful, but WITHOUT ANY
# WARRANTY; without even the implied warranty of MERCHANTABILITY or FITNESS FOR
# A PARTICULAR PURPOSE.  See the GNU Lesser General Public License for more
# details.
#
# You should have received a copy of the GNU Lesser General Public License
# along with Paramiko; if not, write to the Free Software Foundation, Inc.,
# 59 Temple Place, Suite 330, Boston, MA  02111-1307  USA.


import base64
import getpass
import os
import socket
import sys
import traceback
from paramiko.py3compat import input

import paramiko
try:
    import interactive
except ImportError:
    from . import interactive


# setup logging
paramiko.util.log_to_file('demo_simple.log')

# get hostname
username = ''
if len(sys.argv) > 1:
    hostname = sys.argv[1]
    if hostname.find('@') >= 0:
        username, hostname = hostname.split('@')
else:
    hostname = input('Hostname: ')
if len(hostname) == 0:
    print('*** Hostname required.')
    sys.exit(1)
port = 22
if hostname.find(':') >= 0:
    hostname, portstr = hostname.split(':')
    port = int(portstr)


# get username
if username == '':
    default_username = getpass.getuser()
    username = input('Username [%s]: ' % default_username)
    if len(username) == 0:
        username = default_username
password = getpass.getpass('Password for %s@%s: ' % (username, hostname))


# now, connect and use paramiko Client to negotiate SSH2 across the connection
try:
    client = paramiko.SSHClient()
    client.load_system_host_keys()
    client.set_missing_host_key_policy(paramiko.WarningPolicy())
    print('*** Connecting...')
    client.connect(hostname, port, username, password)
    chan = client.invoke_shell()
    print(repr(client.get_transport()))
    print('*** Here we go!\n')
    interactive.interactive_shell(chan)
    chan.close()
    client.close()

except Exception as e:
    print('*** Caught exception: %s: %s' % (e.__class__, e))
    traceback.print_exc()
    try:
        client.close()
    except:
        pass
    sys.exit(1)

########NEW FILE########
__FILENAME__ = forward
#!/usr/bin/env python

# Copyright (C) 2003-2007  Robey Pointer <robeypointer@gmail.com>
#
# This file is part of paramiko.
#
# Paramiko is free software; you can redistribute it and/or modify it under the
# terms of the GNU Lesser General Public License as published by the Free
# Software Foundation; either version 2.1 of the License, or (at your option)
# any later version.
#
# Paramiko is distributed in the hope that it will be useful, but WITHOUT ANY
# WARRANTY; without even the implied warranty of MERCHANTABILITY or FITNESS FOR
# A PARTICULAR PURPOSE.  See the GNU Lesser General Public License for more
# details.
#
# You should have received a copy of the GNU Lesser General Public License
# along with Paramiko; if not, write to the Free Software Foundation, Inc.,
# 59 Temple Place, Suite 330, Boston, MA  02111-1307  USA.

"""
Sample script showing how to do local port forwarding over paramiko.

This script connects to the requested SSH server and sets up local port
forwarding (the openssh -L option) from a local port through a tunneled
connection to a destination reachable from the SSH server machine.
"""

import getpass
import os
import socket
import select
try:
    import SocketServer
except ImportError:
    import socketserver as SocketServer

import sys
from optparse import OptionParser

import paramiko

SSH_PORT = 22
DEFAULT_PORT = 4000

g_verbose = True


class ForwardServer (SocketServer.ThreadingTCPServer):
    daemon_threads = True
    allow_reuse_address = True
    

class Handler (SocketServer.BaseRequestHandler):

    def handle(self):
        try:
            chan = self.ssh_transport.open_channel('direct-tcpip',
                                                   (self.chain_host, self.chain_port),
                                                   self.request.getpeername())
        except Exception as e:
            verbose('Incoming request to %s:%d failed: %s' % (self.chain_host,
                                                              self.chain_port,
                                                              repr(e)))
            return
        if chan is None:
            verbose('Incoming request to %s:%d was rejected by the SSH server.' %
                    (self.chain_host, self.chain_port))
            return

        verbose('Connected!  Tunnel open %r -> %r -> %r' % (self.request.getpeername(),
                                                            chan.getpeername(), (self.chain_host, self.chain_port)))
        while True:
            r, w, x = select.select([self.request, chan], [], [])
            if self.request in r:
                data = self.request.recv(1024)
                if len(data) == 0:
                    break
                chan.send(data)
            if chan in r:
                data = chan.recv(1024)
                if len(data) == 0:
                    break
                self.request.send(data)
                
        peername = self.request.getpeername()
        chan.close()
        self.request.close()
        verbose('Tunnel closed from %r' % (peername,))


def forward_tunnel(local_port, remote_host, remote_port, transport):
    # this is a little convoluted, but lets me configure things for the Handler
    # object.  (SocketServer doesn't give Handlers any way to access the outer
    # server normally.)
    class SubHander (Handler):
        chain_host = remote_host
        chain_port = remote_port
        ssh_transport = transport
    ForwardServer(('', local_port), SubHander).serve_forever()


def verbose(s):
    if g_verbose:
        print(s)


HELP = """\
Set up a forward tunnel across an SSH server, using paramiko. A local port
(given with -p) is forwarded across an SSH session to an address:port from
the SSH server. This is similar to the openssh -L option.
"""


def get_host_port(spec, default_port):
    "parse 'hostname:22' into a host and port, with the port optional"
    args = (spec.split(':', 1) + [default_port])[:2]
    args[1] = int(args[1])
    return args[0], args[1]


def parse_options():
    global g_verbose
    
    parser = OptionParser(usage='usage: %prog [options] <ssh-server>[:<server-port>]',
                          version='%prog 1.0', description=HELP)
    parser.add_option('-q', '--quiet', action='store_false', dest='verbose', default=True,
                      help='squelch all informational output')
    parser.add_option('-p', '--local-port', action='store', type='int', dest='port',
                      default=DEFAULT_PORT,
                      help='local port to forward (default: %d)' % DEFAULT_PORT)
    parser.add_option('-u', '--user', action='store', type='string', dest='user',
                      default=getpass.getuser(),
                      help='username for SSH authentication (default: %s)' % getpass.getuser())
    parser.add_option('-K', '--key', action='store', type='string', dest='keyfile',
                      default=None,
                      help='private key file to use for SSH authentication')
    parser.add_option('', '--no-key', action='store_false', dest='look_for_keys', default=True,
                      help='don\'t look for or use a private key file')
    parser.add_option('-P', '--password', action='store_true', dest='readpass', default=False,
                      help='read password (for key or password auth) from stdin')
    parser.add_option('-r', '--remote', action='store', type='string', dest='remote', default=None, metavar='host:port',
                      help='remote host and port to forward to')
    options, args = parser.parse_args()

    if len(args) != 1:
        parser.error('Incorrect number of arguments.')
    if options.remote is None:
        parser.error('Remote address required (-r).')
    
    g_verbose = options.verbose
    server_host, server_port = get_host_port(args[0], SSH_PORT)
    remote_host, remote_port = get_host_port(options.remote, SSH_PORT)
    return options, (server_host, server_port), (remote_host, remote_port)


def main():
    options, server, remote = parse_options()
    
    password = None
    if options.readpass:
        password = getpass.getpass('Enter SSH password: ')
    
    client = paramiko.SSHClient()
    client.load_system_host_keys()
    client.set_missing_host_key_policy(paramiko.WarningPolicy())

    verbose('Connecting to ssh host %s:%d ...' % (server[0], server[1]))
    try:
        client.connect(server[0], server[1], username=options.user, key_filename=options.keyfile,
                       look_for_keys=options.look_for_keys, password=password)
    except Exception as e:
        print('*** Failed to connect to %s:%d: %r' % (server[0], server[1], e))
        sys.exit(1)

    verbose('Now forwarding port %d to %s:%d ...' % (options.port, remote[0], remote[1]))

    try:
        forward_tunnel(options.port, remote[0], remote[1], client.get_transport())
    except KeyboardInterrupt:
        print('C-c: Port forwarding stopped.')
        sys.exit(0)


if __name__ == '__main__':
    main()

########NEW FILE########
__FILENAME__ = interactive
# Copyright (C) 2003-2007  Robey Pointer <robeypointer@gmail.com>
#
# This file is part of paramiko.
#
# Paramiko is free software; you can redistribute it and/or modify it under the
# terms of the GNU Lesser General Public License as published by the Free
# Software Foundation; either version 2.1 of the License, or (at your option)
# any later version.
#
# Paramiko is distributed in the hope that it will be useful, but WITHOUT ANY
# WARRANTY; without even the implied warranty of MERCHANTABILITY or FITNESS FOR
# A PARTICULAR PURPOSE.  See the GNU Lesser General Public License for more
# details.
#
# You should have received a copy of the GNU Lesser General Public License
# along with Paramiko; if not, write to the Free Software Foundation, Inc.,
# 59 Temple Place, Suite 330, Boston, MA  02111-1307  USA.


import socket
import sys
from paramiko.py3compat import u

# windows does not have termios...
try:
    import termios
    import tty
    has_termios = True
except ImportError:
    has_termios = False


def interactive_shell(chan):
    if has_termios:
        posix_shell(chan)
    else:
        windows_shell(chan)


def posix_shell(chan):
    import select
    
    oldtty = termios.tcgetattr(sys.stdin)
    try:
        tty.setraw(sys.stdin.fileno())
        tty.setcbreak(sys.stdin.fileno())
        chan.settimeout(0.0)

        while True:
            r, w, e = select.select([chan, sys.stdin], [], [])
            if chan in r:
                try:
                    x = u(chan.recv(1024))
                    if len(x) == 0:
                        sys.stdout.write('\r\n*** EOF\r\n')
                        break
                    sys.stdout.write(x)
                    sys.stdout.flush()
                except socket.timeout:
                    pass
            if sys.stdin in r:
                x = sys.stdin.read(1)
                if len(x) == 0:
                    break
                chan.send(x)

    finally:
        termios.tcsetattr(sys.stdin, termios.TCSADRAIN, oldtty)

    
# thanks to Mike Looijmans for this code
def windows_shell(chan):
    import threading

    sys.stdout.write("Line-buffered terminal emulation. Press F6 or ^Z to send EOF.\r\n\r\n")
        
    def writeall(sock):
        while True:
            data = sock.recv(256)
            if not data:
                sys.stdout.write('\r\n*** EOF ***\r\n\r\n')
                sys.stdout.flush()
                break
            sys.stdout.write(data)
            sys.stdout.flush()
        
    writer = threading.Thread(target=writeall, args=(chan,))
    writer.start()
        
    try:
        while True:
            d = sys.stdin.read(1)
            if not d:
                break
            chan.send(d)
    except EOFError:
        # user hit ^Z or F6
        pass

########NEW FILE########
__FILENAME__ = rforward
#!/usr/bin/env python

# Copyright (C) 2008  Robey Pointer <robeypointer@gmail.com>
#
# This file is part of paramiko.
#
# Paramiko is free software; you can redistribute it and/or modify it under the
# terms of the GNU Lesser General Public License as published by the Free
# Software Foundation; either version 2.1 of the License, or (at your option)
# any later version.
#
# Paramiko is distributed in the hope that it will be useful, but WITHOUT ANY
# WARRANTY; without even the implied warranty of MERCHANTABILITY or FITNESS FOR
# A PARTICULAR PURPOSE.  See the GNU Lesser General Public License for more
# details.
#
# You should have received a copy of the GNU Lesser General Public License
# along with Paramiko; if not, write to the Free Software Foundation, Inc.,
# 59 Temple Place, Suite 330, Boston, MA  02111-1307  USA.

"""
Sample script showing how to do remote port forwarding over paramiko.

This script connects to the requested SSH server and sets up remote port
forwarding (the openssh -R option) from a remote port through a tunneled
connection to a destination reachable from the local machine.
"""

import getpass
import os
import socket
import select
import sys
import threading
from optparse import OptionParser

import paramiko

SSH_PORT = 22
DEFAULT_PORT = 4000

g_verbose = True


def handler(chan, host, port):
    sock = socket.socket()
    try:
        sock.connect((host, port))
    except Exception as e:
        verbose('Forwarding request to %s:%d failed: %r' % (host, port, e))
        return
    
    verbose('Connected!  Tunnel open %r -> %r -> %r' % (chan.origin_addr,
                                                        chan.getpeername(), (host, port)))
    while True:
        r, w, x = select.select([sock, chan], [], [])
        if sock in r:
            data = sock.recv(1024)
            if len(data) == 0:
                break
            chan.send(data)
        if chan in r:
            data = chan.recv(1024)
            if len(data) == 0:
                break
            sock.send(data)
    chan.close()
    sock.close()
    verbose('Tunnel closed from %r' % (chan.origin_addr,))


def reverse_forward_tunnel(server_port, remote_host, remote_port, transport):
    transport.request_port_forward('', server_port)
    while True:
        chan = transport.accept(1000)
        if chan is None:
            continue
        thr = threading.Thread(target=handler, args=(chan, remote_host, remote_port))
        thr.setDaemon(True)
        thr.start()


def verbose(s):
    if g_verbose:
        print(s)


HELP = """\
Set up a reverse forwarding tunnel across an SSH server, using paramiko. A
port on the SSH server (given with -p) is forwarded across an SSH session
back to the local machine, and out to a remote site reachable from this
network. This is similar to the openssh -R option.
"""


def get_host_port(spec, default_port):
    "parse 'hostname:22' into a host and port, with the port optional"
    args = (spec.split(':', 1) + [default_port])[:2]
    args[1] = int(args[1])
    return args[0], args[1]


def parse_options():
    global g_verbose
    
    parser = OptionParser(usage='usage: %prog [options] <ssh-server>[:<server-port>]',
                          version='%prog 1.0', description=HELP)
    parser.add_option('-q', '--quiet', action='store_false', dest='verbose', default=True,
                      help='squelch all informational output')
    parser.add_option('-p', '--remote-port', action='store', type='int', dest='port',
                      default=DEFAULT_PORT,
                      help='port on server to forward (default: %d)' % DEFAULT_PORT)
    parser.add_option('-u', '--user', action='store', type='string', dest='user',
                      default=getpass.getuser(),
                      help='username for SSH authentication (default: %s)' % getpass.getuser())
    parser.add_option('-K', '--key', action='store', type='string', dest='keyfile',
                      default=None,
                      help='private key file to use for SSH authentication')
    parser.add_option('', '--no-key', action='store_false', dest='look_for_keys', default=True,
                      help='don\'t look for or use a private key file')
    parser.add_option('-P', '--password', action='store_true', dest='readpass', default=False,
                      help='read password (for key or password auth) from stdin')
    parser.add_option('-r', '--remote', action='store', type='string', dest='remote', default=None, metavar='host:port',
                      help='remote host and port to forward to')
    options, args = parser.parse_args()

    if len(args) != 1:
        parser.error('Incorrect number of arguments.')
    if options.remote is None:
        parser.error('Remote address required (-r).')
    
    g_verbose = options.verbose
    server_host, server_port = get_host_port(args[0], SSH_PORT)
    remote_host, remote_port = get_host_port(options.remote, SSH_PORT)
    return options, (server_host, server_port), (remote_host, remote_port)


def main():
    options, server, remote = parse_options()
    
    password = None
    if options.readpass:
        password = getpass.getpass('Enter SSH password: ')
    
    client = paramiko.SSHClient()
    client.load_system_host_keys()
    client.set_missing_host_key_policy(paramiko.WarningPolicy())

    verbose('Connecting to ssh host %s:%d ...' % (server[0], server[1]))
    try:
        client.connect(server[0], server[1], username=options.user, key_filename=options.keyfile,
                       look_for_keys=options.look_for_keys, password=password)
    except Exception as e:
        print('*** Failed to connect to %s:%d: %r' % (server[0], server[1], e))
        sys.exit(1)

    verbose('Now forwarding remote port %d to %s:%d ...' % (options.port, remote[0], remote[1]))

    try:
        reverse_forward_tunnel(options.port, remote[0], remote[1], client.get_transport())
    except KeyboardInterrupt:
        print('C-c: Port forwarding stopped.')
        sys.exit(0)


if __name__ == '__main__':
    main()

########NEW FILE########
__FILENAME__ = agent
# Copyright (C) 2003-2007  John Rochester <john@jrochester.org>
#
# This file is part of paramiko.
#
# Paramiko is free software; you can redistribute it and/or modify it under the
# terms of the GNU Lesser General Public License as published by the Free
# Software Foundation; either version 2.1 of the License, or (at your option)
# any later version.
#
# Paramiko is distributed in the hope that it will be useful, but WITHOUT ANY
# WARRANTY; without even the implied warranty of MERCHANTABILITY or FITNESS FOR
# A PARTICULAR PURPOSE.  See the GNU Lesser General Public License for more
# details.
#
# You should have received a copy of the GNU Lesser General Public License
# along with Paramiko; if not, write to the Free Software Foundation, Inc.,
# 59 Temple Place, Suite 330, Boston, MA  02111-1307  USA.

"""
SSH Agent interface
"""

import os
import socket
import struct
import sys
import threading
import time
import tempfile
import stat
from select import select
from paramiko.common import asbytes, io_sleep
from paramiko.py3compat import byte_chr

from paramiko.ssh_exception import SSHException
from paramiko.message import Message
from paramiko.pkey import PKey
from paramiko.util import retry_on_signal

cSSH2_AGENTC_REQUEST_IDENTITIES = byte_chr(11)
SSH2_AGENT_IDENTITIES_ANSWER = 12
cSSH2_AGENTC_SIGN_REQUEST = byte_chr(13)
SSH2_AGENT_SIGN_RESPONSE = 14


class AgentSSH(object):
    def __init__(self):
        self._conn = None
        self._keys = ()

    def get_keys(self):
        """
        Return the list of keys available through the SSH agent, if any.  If
        no SSH agent was running (or it couldn't be contacted), an empty list
        will be returned.

        :return:
            a tuple of `.AgentKey` objects representing keys available on the
            SSH agent
        """
        return self._keys

    def _connect(self, conn):
        self._conn = conn
        ptype, result = self._send_message(cSSH2_AGENTC_REQUEST_IDENTITIES)
        if ptype != SSH2_AGENT_IDENTITIES_ANSWER:
            raise SSHException('could not get keys from ssh-agent')
        keys = []
        for i in range(result.get_int()):
            keys.append(AgentKey(self, result.get_binary()))
            result.get_string()
        self._keys = tuple(keys)

    def _close(self):
        #self._conn.close()
        self._conn = None
        self._keys = ()

    def _send_message(self, msg):
        msg = asbytes(msg)
        self._conn.send(struct.pack('>I', len(msg)) + msg)
        l = self._read_all(4)
        msg = Message(self._read_all(struct.unpack('>I', l)[0]))
        return ord(msg.get_byte()), msg

    def _read_all(self, wanted):
        result = self._conn.recv(wanted)
        while len(result) < wanted:
            if len(result) == 0:
                raise SSHException('lost ssh-agent')
            extra = self._conn.recv(wanted - len(result))
            if len(extra) == 0:
                raise SSHException('lost ssh-agent')
            result += extra
        return result


class AgentProxyThread(threading.Thread):
    """
    Class in charge of communication between two channels.
    """
    def __init__(self, agent):
        threading.Thread.__init__(self, target=self.run)
        self._agent = agent
        self._exit = False

    def run(self):
        try:
            (r, addr) = self.get_connection()
            self.__inr = r
            self.__addr = addr
            self._agent.connect()
            self._communicate()
        except:
            #XXX Not sure what to do here ... raise or pass ?
            raise

    def _communicate(self):
        import fcntl
        oldflags = fcntl.fcntl(self.__inr, fcntl.F_GETFL)
        fcntl.fcntl(self.__inr, fcntl.F_SETFL, oldflags | os.O_NONBLOCK)
        while not self._exit:
            events = select([self._agent._conn, self.__inr], [], [], 0.5)
            for fd in events[0]:
                if self._agent._conn == fd:
                    data = self._agent._conn.recv(512)
                    if len(data) != 0:
                        self.__inr.send(data)
                    else:
                        self._close()
                        break
                elif self.__inr == fd:
                    data = self.__inr.recv(512)
                    if len(data) != 0:
                        self._agent._conn.send(data)
                    else:
                        self._close()
                        break
            time.sleep(io_sleep)

    def _close(self):
        self._exit = True
        self.__inr.close()
        self._agent._conn.close()


class AgentLocalProxy(AgentProxyThread):
    """
    Class to be used when wanting to ask a local SSH Agent being
    asked from a remote fake agent (so use a unix socket for ex.)
    """
    def __init__(self, agent):
        AgentProxyThread.__init__(self, agent)

    def get_connection(self):
        """
        Return a pair of socket object and string address.

        May block!
        """
        conn = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        try:
            conn.bind(self._agent._get_filename())
            conn.listen(1)
            (r, addr) = conn.accept()
            return r, addr
        except:
            raise


class AgentRemoteProxy(AgentProxyThread):
    """
    Class to be used when wanting to ask a remote SSH Agent
    """
    def __init__(self, agent, chan):
        AgentProxyThread.__init__(self, agent)
        self.__chan = chan

    def get_connection(self):
        return self.__chan, None


class AgentClientProxy(object):
    """
    Class proxying request as a client:

    #. client ask for a request_forward_agent()
    #. server creates a proxy and a fake SSH Agent
    #. server ask for establishing a connection when needed,
       calling the forward_agent_handler at client side.
    #. the forward_agent_handler launch a thread for connecting
       the remote fake agent and the local agent
    #. Communication occurs ...
    """
    def __init__(self, chanRemote):
        self._conn = None
        self.__chanR = chanRemote
        self.thread = AgentRemoteProxy(self, chanRemote)
        self.thread.start()

    def __del__(self):
        self.close()

    def connect(self):
        """
        Method automatically called by ``AgentProxyThread.run``.
        """
        if ('SSH_AUTH_SOCK' in os.environ) and (sys.platform != 'win32'):
            conn = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
            try:
                retry_on_signal(lambda: conn.connect(os.environ['SSH_AUTH_SOCK']))
            except:
                # probably a dangling env var: the ssh agent is gone
                return
        elif sys.platform == 'win32':
            import paramiko.win_pageant as win_pageant
            if win_pageant.can_talk_to_agent():
                conn = win_pageant.PageantConnection()
            else:
                return
        else:
            # no agent support
            return
        self._conn = conn

    def close(self):
        """
        Close the current connection and terminate the agent
        Should be called manually
        """
        if hasattr(self, "thread"):
            self.thread._exit = True
            self.thread.join(1000)
        if self._conn is not None:
            self._conn.close()


class AgentServerProxy(AgentSSH):
    """
    :param .Transport t: Transport used for SSH Agent communication forwarding

    :raises SSHException: mostly if we lost the agent
    """
    def __init__(self, t):
        AgentSSH.__init__(self)
        self.__t = t
        self._dir = tempfile.mkdtemp('sshproxy')
        os.chmod(self._dir, stat.S_IRWXU)
        self._file = self._dir + '/sshproxy.ssh'
        self.thread = AgentLocalProxy(self)
        self.thread.start()

    def __del__(self):
        self.close()

    def connect(self):
        conn_sock = self.__t.open_forward_agent_channel()
        if conn_sock is None:
            raise SSHException('lost ssh-agent')
        conn_sock.set_name('auth-agent')
        self._connect(conn_sock)

    def close(self):
        """
        Terminate the agent, clean the files, close connections
        Should be called manually
        """
        os.remove(self._file)
        os.rmdir(self._dir)
        self.thread._exit = True
        self.thread.join(1000)
        self._close()

    def get_env(self):
        """
        Helper for the environnement under unix

        :return:
            a dict containing the ``SSH_AUTH_SOCK`` environnement variables
        """
        return {'SSH_AUTH_SOCK': self._get_filename()}

    def _get_filename(self):
        return self._file


class AgentRequestHandler(object):
    def __init__(self, chanClient):
        self._conn = None
        self.__chanC = chanClient
        chanClient.request_forward_agent(self._forward_agent_handler)
        self.__clientProxys = []

    def _forward_agent_handler(self, chanRemote):
        self.__clientProxys.append(AgentClientProxy(chanRemote))

    def __del__(self):
        self.close()

    def close(self):
        for p in self.__clientProxys:
            p.close()


class Agent(AgentSSH):
    """
    Client interface for using private keys from an SSH agent running on the
    local machine.  If an SSH agent is running, this class can be used to
    connect to it and retreive `.PKey` objects which can be used when
    attempting to authenticate to remote SSH servers.

    Upon initialization, a session with the local machine's SSH agent is
    opened, if one is running. If no agent is running, initialization will
    succeed, but `get_keys` will return an empty tuple.

    :raises SSHException:
        if an SSH agent is found, but speaks an incompatible protocol
    """
    def __init__(self):
        AgentSSH.__init__(self)

        if ('SSH_AUTH_SOCK' in os.environ) and (sys.platform != 'win32'):
            conn = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
            try:
                conn.connect(os.environ['SSH_AUTH_SOCK'])
            except:
                # probably a dangling env var: the ssh agent is gone
                return
        elif sys.platform == 'win32':
            from . import win_pageant
            if win_pageant.can_talk_to_agent():
                conn = win_pageant.PageantConnection()
            else:
                return
        else:
            # no agent support
            return
        self._connect(conn)

    def close(self):
        """
        Close the SSH agent connection.
        """
        self._close()


class AgentKey(PKey):
    """
    Private key held in a local SSH agent.  This type of key can be used for
    authenticating to a remote server (signing).  Most other key operations
    work as expected.
    """
    def __init__(self, agent, blob):
        self.agent = agent
        self.blob = blob
        self.name = Message(blob).get_text()

    def asbytes(self):
        return self.blob

    def __str__(self):
        return self.asbytes()

    def get_name(self):
        return self.name

    def sign_ssh_data(self, data):
        msg = Message()
        msg.add_byte(cSSH2_AGENTC_SIGN_REQUEST)
        msg.add_string(self.blob)
        msg.add_string(data)
        msg.add_int(0)
        ptype, result = self.agent._send_message(msg)
        if ptype != SSH2_AGENT_SIGN_RESPONSE:
            raise SSHException('key cannot be used for signing')
        return result.get_binary()

########NEW FILE########
__FILENAME__ = auth_handler
# Copyright (C) 2003-2007  Robey Pointer <robeypointer@gmail.com>
#
# This file is part of paramiko.
#
# Paramiko is free software; you can redistribute it and/or modify it under the
# terms of the GNU Lesser General Public License as published by the Free
# Software Foundation; either version 2.1 of the License, or (at your option)
# any later version.
#
# Paramiko is distributed in the hope that it will be useful, but WITHOUT ANY
# WARRANTY; without even the implied warranty of MERCHANTABILITY or FITNESS FOR
# A PARTICULAR PURPOSE.  See the GNU Lesser General Public License for more
# details.
#
# You should have received a copy of the GNU Lesser General Public License
# along with Paramiko; if not, write to the Free Software Foundation, Inc.,
# 59 Temple Place, Suite 330, Boston, MA  02111-1307  USA.

"""
`.AuthHandler`
"""

import weakref
from paramiko.common import cMSG_SERVICE_REQUEST, cMSG_DISCONNECT, \
    DISCONNECT_SERVICE_NOT_AVAILABLE, DISCONNECT_NO_MORE_AUTH_METHODS_AVAILABLE, \
    cMSG_USERAUTH_REQUEST, cMSG_SERVICE_ACCEPT, DEBUG, AUTH_SUCCESSFUL, INFO, \
    cMSG_USERAUTH_SUCCESS, cMSG_USERAUTH_FAILURE, AUTH_PARTIALLY_SUCCESSFUL, \
    cMSG_USERAUTH_INFO_REQUEST, WARNING, AUTH_FAILED, cMSG_USERAUTH_PK_OK, \
    cMSG_USERAUTH_INFO_RESPONSE, MSG_SERVICE_REQUEST, MSG_SERVICE_ACCEPT, \
    MSG_USERAUTH_REQUEST, MSG_USERAUTH_SUCCESS, MSG_USERAUTH_FAILURE, \
    MSG_USERAUTH_BANNER, MSG_USERAUTH_INFO_REQUEST, MSG_USERAUTH_INFO_RESPONSE

from paramiko.message import Message
from paramiko.py3compat import bytestring
from paramiko.ssh_exception import SSHException, AuthenticationException, \
    BadAuthenticationType, PartialAuthentication
from paramiko.server import InteractiveQuery


class AuthHandler (object):
    """
    Internal class to handle the mechanics of authentication.
    """
    
    def __init__(self, transport):
        self.transport = weakref.proxy(transport)
        self.username = None
        self.authenticated = False
        self.auth_event = None
        self.auth_method = ''
        self.banner = None
        self.password = None
        self.private_key = None
        self.interactive_handler = None
        self.submethods = None
        # for server mode:
        self.auth_username = None
        self.auth_fail_count = 0
        
    def is_authenticated(self):
        return self.authenticated

    def get_username(self):
        if self.transport.server_mode:
            return self.auth_username
        else:
            return self.username

    def auth_none(self, username, event):
        self.transport.lock.acquire()
        try:
            self.auth_event = event
            self.auth_method = 'none'
            self.username = username
            self._request_auth()
        finally:
            self.transport.lock.release()

    def auth_publickey(self, username, key, event):
        self.transport.lock.acquire()
        try:
            self.auth_event = event
            self.auth_method = 'publickey'
            self.username = username
            self.private_key = key
            self._request_auth()
        finally:
            self.transport.lock.release()

    def auth_password(self, username, password, event):
        self.transport.lock.acquire()
        try:
            self.auth_event = event
            self.auth_method = 'password'
            self.username = username
            self.password = password
            self._request_auth()
        finally:
            self.transport.lock.release()
    
    def auth_interactive(self, username, handler, event, submethods=''):
        """
        response_list = handler(title, instructions, prompt_list)
        """
        self.transport.lock.acquire()
        try:
            self.auth_event = event
            self.auth_method = 'keyboard-interactive'
            self.username = username
            self.interactive_handler = handler
            self.submethods = submethods
            self._request_auth()
        finally:
            self.transport.lock.release()
    
    def abort(self):
        if self.auth_event is not None:
            self.auth_event.set()

    ###  internals...

    def _request_auth(self):
        m = Message()
        m.add_byte(cMSG_SERVICE_REQUEST)
        m.add_string('ssh-userauth')
        self.transport._send_message(m)

    def _disconnect_service_not_available(self):
        m = Message()
        m.add_byte(cMSG_DISCONNECT)
        m.add_int(DISCONNECT_SERVICE_NOT_AVAILABLE)
        m.add_string('Service not available')
        m.add_string('en')
        self.transport._send_message(m)
        self.transport.close()

    def _disconnect_no_more_auth(self):
        m = Message()
        m.add_byte(cMSG_DISCONNECT)
        m.add_int(DISCONNECT_NO_MORE_AUTH_METHODS_AVAILABLE)
        m.add_string('No more auth methods available')
        m.add_string('en')
        self.transport._send_message(m)
        self.transport.close()

    def _get_session_blob(self, key, service, username):
        m = Message()
        m.add_string(self.transport.session_id)
        m.add_byte(cMSG_USERAUTH_REQUEST)
        m.add_string(username)
        m.add_string(service)
        m.add_string('publickey')
        m.add_boolean(True)
        m.add_string(key.get_name())
        m.add_string(key)
        return m.asbytes()

    def wait_for_response(self, event):
        while True:
            event.wait(0.1)
            if not self.transport.is_active():
                e = self.transport.get_exception()
                if (e is None) or issubclass(e.__class__, EOFError):
                    e = AuthenticationException('Authentication failed.')
                raise e
            if event.isSet():
                break
        if not self.is_authenticated():
            e = self.transport.get_exception()
            if e is None:
                e = AuthenticationException('Authentication failed.')
            # this is horrible.  Python Exception isn't yet descended from
            # object, so type(e) won't work. :(
            if issubclass(e.__class__, PartialAuthentication):
                return e.allowed_types
            raise e
        return []

    def _parse_service_request(self, m):
        service = m.get_text()
        if self.transport.server_mode and (service == 'ssh-userauth'):
            # accepted
            m = Message()
            m.add_byte(cMSG_SERVICE_ACCEPT)
            m.add_string(service)
            self.transport._send_message(m)
            return
        # dunno this one
        self._disconnect_service_not_available()

    def _parse_service_accept(self, m):
        service = m.get_text()
        if service == 'ssh-userauth':
            self.transport._log(DEBUG, 'userauth is OK')
            m = Message()
            m.add_byte(cMSG_USERAUTH_REQUEST)
            m.add_string(self.username)
            m.add_string('ssh-connection')
            m.add_string(self.auth_method)
            if self.auth_method == 'password':
                m.add_boolean(False)
                password = bytestring(self.password)
                m.add_string(password)
            elif self.auth_method == 'publickey':
                m.add_boolean(True)
                m.add_string(self.private_key.get_name())
                m.add_string(self.private_key)
                blob = self._get_session_blob(self.private_key, 'ssh-connection', self.username)
                sig = self.private_key.sign_ssh_data(blob)
                m.add_string(sig)
            elif self.auth_method == 'keyboard-interactive':
                m.add_string('')
                m.add_string(self.submethods)
            elif self.auth_method == 'none':
                pass
            else:
                raise SSHException('Unknown auth method "%s"' % self.auth_method)
            self.transport._send_message(m)
        else:
            self.transport._log(DEBUG, 'Service request "%s" accepted (?)' % service)

    def _send_auth_result(self, username, method, result):
        # okay, send result
        m = Message()
        if result == AUTH_SUCCESSFUL:
            self.transport._log(INFO, 'Auth granted (%s).' % method)
            m.add_byte(cMSG_USERAUTH_SUCCESS)
            self.authenticated = True
        else:
            self.transport._log(INFO, 'Auth rejected (%s).' % method)
            m.add_byte(cMSG_USERAUTH_FAILURE)
            m.add_string(self.transport.server_object.get_allowed_auths(username))
            if result == AUTH_PARTIALLY_SUCCESSFUL:
                m.add_boolean(True)
            else:
                m.add_boolean(False)
                self.auth_fail_count += 1
        self.transport._send_message(m)
        if self.auth_fail_count >= 10:
            self._disconnect_no_more_auth()
        if result == AUTH_SUCCESSFUL:
            self.transport._auth_trigger()

    def _interactive_query(self, q):
        # make interactive query instead of response
        m = Message()
        m.add_byte(cMSG_USERAUTH_INFO_REQUEST)
        m.add_string(q.name)
        m.add_string(q.instructions)
        m.add_string(bytes())
        m.add_int(len(q.prompts))
        for p in q.prompts:
            m.add_string(p[0])
            m.add_boolean(p[1])
        self.transport._send_message(m)
 
    def _parse_userauth_request(self, m):
        if not self.transport.server_mode:
            # er, uh... what?
            m = Message()
            m.add_byte(cMSG_USERAUTH_FAILURE)
            m.add_string('none')
            m.add_boolean(False)
            self.transport._send_message(m)
            return
        if self.authenticated:
            # ignore
            return
        username = m.get_text()
        service = m.get_text()
        method = m.get_text()
        self.transport._log(DEBUG, 'Auth request (type=%s) service=%s, username=%s' % (method, service, username))
        if service != 'ssh-connection':
            self._disconnect_service_not_available()
            return
        if (self.auth_username is not None) and (self.auth_username != username):
            self.transport._log(WARNING, 'Auth rejected because the client attempted to change username in mid-flight')
            self._disconnect_no_more_auth()
            return
        self.auth_username = username

        if method == 'none':
            result = self.transport.server_object.check_auth_none(username)
        elif method == 'password':
            changereq = m.get_boolean()
            password = m.get_binary()
            try:
                password = password.decode('UTF-8')
            except UnicodeError:
                # some clients/servers expect non-utf-8 passwords!
                # in this case, just return the raw byte string.
                pass
            if changereq:
                # always treated as failure, since we don't support changing passwords, but collect
                # the list of valid auth types from the callback anyway
                self.transport._log(DEBUG, 'Auth request to change passwords (rejected)')
                newpassword = m.get_binary()
                try:
                    newpassword = newpassword.decode('UTF-8', 'replace')
                except UnicodeError:
                    pass
                result = AUTH_FAILED
            else:
                result = self.transport.server_object.check_auth_password(username, password)
        elif method == 'publickey':
            sig_attached = m.get_boolean()
            keytype = m.get_text()
            keyblob = m.get_binary()
            try:
                key = self.transport._key_info[keytype](Message(keyblob))
            except SSHException as e:
                self.transport._log(INFO, 'Auth rejected: public key: %s' % str(e))
                key = None
            except:
                self.transport._log(INFO, 'Auth rejected: unsupported or mangled public key')
                key = None
            if key is None:
                self._disconnect_no_more_auth()
                return
            # first check if this key is okay... if not, we can skip the verify
            result = self.transport.server_object.check_auth_publickey(username, key)
            if result != AUTH_FAILED:
                # key is okay, verify it
                if not sig_attached:
                    # client wants to know if this key is acceptable, before it
                    # signs anything...  send special "ok" message
                    m = Message()
                    m.add_byte(cMSG_USERAUTH_PK_OK)
                    m.add_string(keytype)
                    m.add_string(keyblob)
                    self.transport._send_message(m)
                    return
                sig = Message(m.get_binary())
                blob = self._get_session_blob(key, service, username)
                if not key.verify_ssh_sig(blob, sig):
                    self.transport._log(INFO, 'Auth rejected: invalid signature')
                    result = AUTH_FAILED
        elif method == 'keyboard-interactive':
            lang = m.get_string()
            submethods = m.get_string()
            result = self.transport.server_object.check_auth_interactive(username, submethods)
            if isinstance(result, InteractiveQuery):
                # make interactive query instead of response
                self._interactive_query(result)
                return
        else:
            result = self.transport.server_object.check_auth_none(username)
        # okay, send result
        self._send_auth_result(username, method, result)

    def _parse_userauth_success(self, m):
        self.transport._log(INFO, 'Authentication (%s) successful!' % self.auth_method)
        self.authenticated = True
        self.transport._auth_trigger()
        if self.auth_event is not None:
            self.auth_event.set()

    def _parse_userauth_failure(self, m):
        authlist = m.get_list()
        partial = m.get_boolean()
        if partial:
            self.transport._log(INFO, 'Authentication continues...')
            self.transport._log(DEBUG, 'Methods: ' + str(authlist))
            self.transport.saved_exception = PartialAuthentication(authlist)
        elif self.auth_method not in authlist:
            self.transport._log(DEBUG, 'Authentication type (%s) not permitted.' % self.auth_method)
            self.transport._log(DEBUG, 'Allowed methods: ' + str(authlist))
            self.transport.saved_exception = BadAuthenticationType('Bad authentication type', authlist)
        else:
            self.transport._log(INFO, 'Authentication (%s) failed.' % self.auth_method)
        self.authenticated = False
        self.username = None
        if self.auth_event is not None:
            self.auth_event.set()

    def _parse_userauth_banner(self, m):
        banner = m.get_string()
        self.banner = banner
        lang = m.get_string()
        self.transport._log(INFO, 'Auth banner: %s' % banner)
        # who cares.
    
    def _parse_userauth_info_request(self, m):
        if self.auth_method != 'keyboard-interactive':
            raise SSHException('Illegal info request from server')
        title = m.get_text()
        instructions = m.get_text()
        m.get_binary()  # lang
        prompts = m.get_int()
        prompt_list = []
        for i in range(prompts):
            prompt_list.append((m.get_text(), m.get_boolean()))
        response_list = self.interactive_handler(title, instructions, prompt_list)
        
        m = Message()
        m.add_byte(cMSG_USERAUTH_INFO_RESPONSE)
        m.add_int(len(response_list))
        for r in response_list:
            m.add_string(r)
        self.transport._send_message(m)
    
    def _parse_userauth_info_response(self, m):
        if not self.transport.server_mode:
            raise SSHException('Illegal info response from server')
        n = m.get_int()
        responses = []
        for i in range(n):
            responses.append(m.get_text())
        result = self.transport.server_object.check_auth_interactive_response(responses)
        if isinstance(type(result), InteractiveQuery):
            # make interactive query instead of response
            self._interactive_query(result)
            return
        self._send_auth_result(self.auth_username, 'keyboard-interactive', result)

    _handler_table = {
        MSG_SERVICE_REQUEST: _parse_service_request,
        MSG_SERVICE_ACCEPT: _parse_service_accept,
        MSG_USERAUTH_REQUEST: _parse_userauth_request,
        MSG_USERAUTH_SUCCESS: _parse_userauth_success,
        MSG_USERAUTH_FAILURE: _parse_userauth_failure,
        MSG_USERAUTH_BANNER: _parse_userauth_banner,
        MSG_USERAUTH_INFO_REQUEST: _parse_userauth_info_request,
        MSG_USERAUTH_INFO_RESPONSE: _parse_userauth_info_response,
    }

########NEW FILE########
__FILENAME__ = ber
# Copyright (C) 2003-2007  Robey Pointer <robeypointer@gmail.com>
#
# This file is part of paramiko.
#
# Paramiko is free software; you can redistribute it and/or modify it under the
# terms of the GNU Lesser General Public License as published by the Free
# Software Foundation; either version 2.1 of the License, or (at your option)
# any later version.
#
# Paramiko is distributed in the hope that it will be useful, but WITHOUT ANY
# WARRANTY; without even the implied warranty of MERCHANTABILITY or FITNESS FOR
# A PARTICULAR PURPOSE.  See the GNU Lesser General Public License for more
# details.
#
# You should have received a copy of the GNU Lesser General Public License
# along with Paramiko; if not, write to the Free Software Foundation, Inc.,
# 59 Temple Place, Suite 330, Boston, MA  02111-1307  USA.
from paramiko.common import max_byte, zero_byte
from paramiko.py3compat import b, byte_ord, byte_chr, long

import paramiko.util as util


class BERException (Exception):
    pass


class BER(object):
    """
    Robey's tiny little attempt at a BER decoder.
    """

    def __init__(self, content=bytes()):
        self.content = b(content)
        self.idx = 0

    def asbytes(self):
        return self.content

    def __str__(self):
        return self.asbytes()

    def __repr__(self):
        return 'BER(\'' + repr(self.content) + '\')'

    def decode(self):
        return self.decode_next()
    
    def decode_next(self):
        if self.idx >= len(self.content):
            return None
        ident = byte_ord(self.content[self.idx])
        self.idx += 1
        if (ident & 31) == 31:
            # identifier > 30
            ident = 0
            while self.idx < len(self.content):
                t = byte_ord(self.content[self.idx])
                self.idx += 1
                ident = (ident << 7) | (t & 0x7f)
                if not (t & 0x80):
                    break
        if self.idx >= len(self.content):
            return None
        # now fetch length
        size = byte_ord(self.content[self.idx])
        self.idx += 1
        if size & 0x80:
            # more complimicated...
            # FIXME: theoretically should handle indefinite-length (0x80)
            t = size & 0x7f
            if self.idx + t > len(self.content):
                return None
            size = util.inflate_long(self.content[self.idx: self.idx + t], True)
            self.idx += t
        if self.idx + size > len(self.content):
            # can't fit
            return None
        data = self.content[self.idx: self.idx + size]
        self.idx += size
        # now switch on id
        if ident == 0x30:
            # sequence
            return self.decode_sequence(data)
        elif ident == 2:
            # int
            return util.inflate_long(data)
        else:
            # 1: boolean (00 false, otherwise true)
            raise BERException('Unknown ber encoding type %d (robey is lazy)' % ident)

    def decode_sequence(data):
        out = []
        ber = BER(data)
        while True:
            x = ber.decode_next()
            if x is None:
                break
            out.append(x)
        return out
    decode_sequence = staticmethod(decode_sequence)

    def encode_tlv(self, ident, val):
        # no need to support ident > 31 here
        self.content += byte_chr(ident)
        if len(val) > 0x7f:
            lenstr = util.deflate_long(len(val))
            self.content += byte_chr(0x80 + len(lenstr)) + lenstr
        else:
            self.content += byte_chr(len(val))
        self.content += val

    def encode(self, x):
        if type(x) is bool:
            if x:
                self.encode_tlv(1, max_byte)
            else:
                self.encode_tlv(1, zero_byte)
        elif (type(x) is int) or (type(x) is long):
            self.encode_tlv(2, util.deflate_long(x))
        elif type(x) is str:
            self.encode_tlv(4, x)
        elif (type(x) is list) or (type(x) is tuple):
            self.encode_tlv(0x30, self.encode_sequence(x))
        else:
            raise BERException('Unknown type for encoding: %s' % repr(type(x)))

    def encode_sequence(data):
        ber = BER()
        for item in data:
            ber.encode(item)
        return ber.asbytes()
    encode_sequence = staticmethod(encode_sequence)

########NEW FILE########
__FILENAME__ = buffered_pipe
# Copyright (C) 2006-2007  Robey Pointer <robeypointer@gmail.com>
#
# This file is part of paramiko.
#
# Paramiko is free software; you can redistribute it and/or modify it under the
# terms of the GNU Lesser General Public License as published by the Free
# Software Foundation; either version 2.1 of the License, or (at your option)
# any later version.
#
# Paramiko is distributed in the hope that it will be useful, but WITHOUT ANY
# WARRANTY; without even the implied warranty of MERCHANTABILITY or FITNESS FOR
# A PARTICULAR PURPOSE.  See the GNU Lesser General Public License for more
# details.
#
# You should have received a copy of the GNU Lesser General Public License
# along with Paramiko; if not, write to the Free Software Foundation, Inc.,
# 59 Temple Place, Suite 330, Boston, MA  02111-1307  USA.

"""
Attempt to generalize the "feeder" part of a `.Channel`: an object which can be
read from and closed, but is reading from a buffer fed by another thread.  The
read operations are blocking and can have a timeout set.
"""

import array
import threading
import time
from paramiko.py3compat import PY2, b


class PipeTimeout (IOError):
    """
    Indicates that a timeout was reached on a read from a `.BufferedPipe`.
    """
    pass


class BufferedPipe (object):
    """
    A buffer that obeys normal read (with timeout) & close semantics for a
    file or socket, but is fed data from another thread.  This is used by
    `.Channel`.
    """
    
    def __init__(self):
        self._lock = threading.Lock()
        self._cv = threading.Condition(self._lock)
        self._event = None
        self._buffer = array.array('B')
        self._closed = False

    if PY2:
        def _buffer_frombytes(self, data):
            self._buffer.fromstring(data)

        def _buffer_tobytes(self, limit=None):
            return self._buffer[:limit].tostring()
    else:
        def _buffer_frombytes(self, data):
            self._buffer.frombytes(data)

        def _buffer_tobytes(self, limit=None):
            return self._buffer[:limit].tobytes()

    def set_event(self, event):
        """
        Set an event on this buffer.  When data is ready to be read (or the
        buffer has been closed), the event will be set.  When no data is
        ready, the event will be cleared.
        
        :param threading.Event event: the event to set/clear
        """
        self._event = event
        if len(self._buffer) > 0:
            event.set()
        else:
            event.clear()
        
    def feed(self, data):
        """
        Feed new data into this pipe.  This method is assumed to be called
        from a separate thread, so synchronization is done.
        
        :param data: the data to add, as a `str`
        """
        self._lock.acquire()
        try:
            if self._event is not None:
                self._event.set()
            self._buffer_frombytes(b(data))
            self._cv.notifyAll()
        finally:
            self._lock.release()

    def read_ready(self):
        """
        Returns true if data is buffered and ready to be read from this
        feeder.  A ``False`` result does not mean that the feeder has closed;
        it means you may need to wait before more data arrives.
        
        :return:
            ``True`` if a `read` call would immediately return at least one
            byte; ``False`` otherwise.
        """
        self._lock.acquire()
        try:
            if len(self._buffer) == 0:
                return False
            return True
        finally:
            self._lock.release()

    def read(self, nbytes, timeout=None):
        """
        Read data from the pipe.  The return value is a string representing
        the data received.  The maximum amount of data to be received at once
        is specified by ``nbytes``.  If a string of length zero is returned,
        the pipe has been closed.

        The optional ``timeout`` argument can be a nonnegative float expressing
        seconds, or ``None`` for no timeout.  If a float is given, a
        `.PipeTimeout` will be raised if the timeout period value has elapsed
        before any data arrives.

        :param int nbytes: maximum number of bytes to read
        :param float timeout:
            maximum seconds to wait (or ``None``, the default, to wait forever)
        :return: the read data, as a `str`
        
        :raises PipeTimeout:
            if a timeout was specified and no data was ready before that
            timeout
        """
        out = bytes()
        self._lock.acquire()
        try:
            if len(self._buffer) == 0:
                if self._closed:
                    return out
                # should we block?
                if timeout == 0.0:
                    raise PipeTimeout()
                # loop here in case we get woken up but a different thread has
                # grabbed everything in the buffer.
                while (len(self._buffer) == 0) and not self._closed:
                    then = time.time()
                    self._cv.wait(timeout)
                    if timeout is not None:
                        timeout -= time.time() - then
                        if timeout <= 0.0:
                            raise PipeTimeout()

            # something's in the buffer and we have the lock!
            if len(self._buffer) <= nbytes:
                out = self._buffer_tobytes()
                del self._buffer[:]
                if (self._event is not None) and not self._closed:
                    self._event.clear()
            else:
                out = self._buffer_tobytes(nbytes)
                del self._buffer[:nbytes]
        finally:
            self._lock.release()

        return out
    
    def empty(self):
        """
        Clear out the buffer and return all data that was in it.
        
        :return:
            any data that was in the buffer prior to clearing it out, as a
            `str`
        """
        self._lock.acquire()
        try:
            out = self._buffer_tobytes()
            del self._buffer[:]
            if (self._event is not None) and not self._closed:
                self._event.clear()
            return out
        finally:
            self._lock.release()
    
    def close(self):
        """
        Close this pipe object.  Future calls to `read` after the buffer
        has been emptied will return immediately with an empty string.
        """
        self._lock.acquire()
        try:
            self._closed = True
            self._cv.notifyAll()
            if self._event is not None:
                self._event.set()
        finally:
            self._lock.release()

    def __len__(self):
        """
        Return the number of bytes buffered.
        
        :return: number (`int`) of bytes buffered
        """
        self._lock.acquire()
        try:
            return len(self._buffer)
        finally:
            self._lock.release()

########NEW FILE########
__FILENAME__ = channel
# Copyright (C) 2003-2007  Robey Pointer <robeypointer@gmail.com>
#
# This file is part of paramiko.
#
# Paramiko is free software; you can redistribute it and/or modify it under the
# terms of the GNU Lesser General Public License as published by the Free
# Software Foundation; either version 2.1 of the License, or (at your option)
# any later version.
#
# Paramiko is distributed in the hope that it will be useful, but WITHOUT ANY
# WARRANTY; without even the implied warranty of MERCHANTABILITY or FITNESS FOR
# A PARTICULAR PURPOSE.  See the GNU Lesser General Public License for more
# details.
#
# You should have received a copy of the GNU Lesser General Public License
# along with Paramiko; if not, write to the Free Software Foundation, Inc.,
# 59 Temple Place, Suite 330, Boston, MA  02111-1307  USA.

"""
Abstraction for an SSH2 channel.
"""

import binascii
import os
import socket
import time
import threading

from paramiko import util
from paramiko.common import cMSG_CHANNEL_REQUEST, cMSG_CHANNEL_WINDOW_ADJUST, \
    cMSG_CHANNEL_DATA, cMSG_CHANNEL_EXTENDED_DATA, DEBUG, ERROR, \
    cMSG_CHANNEL_SUCCESS, cMSG_CHANNEL_FAILURE, cMSG_CHANNEL_EOF, \
    cMSG_CHANNEL_CLOSE
from paramiko.message import Message
from paramiko.py3compat import bytes_types
from paramiko.ssh_exception import SSHException
from paramiko.file import BufferedFile
from paramiko.buffered_pipe import BufferedPipe, PipeTimeout
from paramiko import pipe


# lower bound on the max packet size we'll accept from the remote host
MIN_PACKET_SIZE = 1024


class Channel (object):
    """
    A secure tunnel across an SSH `.Transport`.  A Channel is meant to behave
    like a socket, and has an API that should be indistinguishable from the
    Python socket API.

    Because SSH2 has a windowing kind of flow control, if you stop reading data
    from a Channel and its buffer fills up, the server will be unable to send
    you any more data until you read some of it.  (This won't affect other
    channels on the same transport -- all channels on a single transport are
    flow-controlled independently.)  Similarly, if the server isn't reading
    data you send, calls to `send` may block, unless you set a timeout.  This
    is exactly like a normal network socket, so it shouldn't be too surprising.
    """

    def __init__(self, chanid):
        """
        Create a new channel.  The channel is not associated with any
        particular session or `.Transport` until the Transport attaches it.
        Normally you would only call this method from the constructor of a
        subclass of `.Channel`.

        :param int chanid:
            the ID of this channel, as passed by an existing `.Transport`.
        """
        self.chanid = chanid
        self.remote_chanid = 0
        self.transport = None
        self.active = False
        self.eof_received = 0
        self.eof_sent = 0
        self.in_buffer = BufferedPipe()
        self.in_stderr_buffer = BufferedPipe()
        self.timeout = None
        self.closed = False
        self.ultra_debug = False
        self.lock = threading.Lock()
        self.out_buffer_cv = threading.Condition(self.lock)
        self.in_window_size = 0
        self.out_window_size = 0
        self.in_max_packet_size = 0
        self.out_max_packet_size = 0
        self.in_window_threshold = 0
        self.in_window_sofar = 0
        self.status_event = threading.Event()
        self._name = str(chanid)
        self.logger = util.get_logger('paramiko.transport')
        self._pipe = None
        self.event = threading.Event()
        self.event_ready = False
        self.combine_stderr = False
        self.exit_status = -1
        self.origin_addr = None
    
    def __del__(self):
        try:
            self.close()
        except:
            pass
        
    def __repr__(self):
        """
        Return a string representation of this object, for debugging.
        """
        out = '<paramiko.Channel %d' % self.chanid
        if self.closed:
            out += ' (closed)'
        elif self.active:
            if self.eof_received:
                out += ' (EOF received)'
            if self.eof_sent:
                out += ' (EOF sent)'
            out += ' (open) window=%d' % self.out_window_size
            if len(self.in_buffer) > 0:
                out += ' in-buffer=%d' % (len(self.in_buffer),)
        out += ' -> ' + repr(self.transport)
        out += '>'
        return out

    def get_pty(self, term='vt100', width=80, height=24, width_pixels=0,
                height_pixels=0):
        """
        Request a pseudo-terminal from the server.  This is usually used right
        after creating a client channel, to ask the server to provide some
        basic terminal semantics for a shell invoked with `invoke_shell`.
        It isn't necessary (or desirable) to call this method if you're going
        to exectue a single command with `exec_command`.

        :param str term: the terminal type to emulate (for example, ``'vt100'``)
        :param int width: width (in characters) of the terminal screen
        :param int height: height (in characters) of the terminal screen
        :param int width_pixels: width (in pixels) of the terminal screen
        :param int height_pixels: height (in pixels) of the terminal screen
        
        :raises SSHException:
            if the request was rejected or the channel was closed
        """
        if self.closed or self.eof_received or self.eof_sent or not self.active:
            raise SSHException('Channel is not open')
        m = Message()
        m.add_byte(cMSG_CHANNEL_REQUEST)
        m.add_int(self.remote_chanid)
        m.add_string('pty-req')
        m.add_boolean(True)
        m.add_string(term)
        m.add_int(width)
        m.add_int(height)
        m.add_int(width_pixels)
        m.add_int(height_pixels)
        m.add_string(bytes())
        self._event_pending()
        self.transport._send_user_message(m)
        self._wait_for_event()

    def invoke_shell(self):
        """
        Request an interactive shell session on this channel.  If the server
        allows it, the channel will then be directly connected to the stdin,
        stdout, and stderr of the shell.
        
        Normally you would call `get_pty` before this, in which case the
        shell will operate through the pty, and the channel will be connected
        to the stdin and stdout of the pty.
        
        When the shell exits, the channel will be closed and can't be reused.
        You must open a new channel if you wish to open another shell.
        
        :raises SSHException: if the request was rejected or the channel was
            closed
        """
        if self.closed or self.eof_received or self.eof_sent or not self.active:
            raise SSHException('Channel is not open')
        m = Message()
        m.add_byte(cMSG_CHANNEL_REQUEST)
        m.add_int(self.remote_chanid)
        m.add_string('shell')
        m.add_boolean(True)
        self._event_pending()
        self.transport._send_user_message(m)
        self._wait_for_event()

    def exec_command(self, command):
        """
        Execute a command on the server.  If the server allows it, the channel
        will then be directly connected to the stdin, stdout, and stderr of
        the command being executed.
        
        When the command finishes executing, the channel will be closed and
        can't be reused.  You must open a new channel if you wish to execute
        another command.

        :param str command: a shell command to execute.

        :raises SSHException: if the request was rejected or the channel was
            closed
        """
        if self.closed or self.eof_received or self.eof_sent or not self.active:
            raise SSHException('Channel is not open')
        m = Message()
        m.add_byte(cMSG_CHANNEL_REQUEST)
        m.add_int(self.remote_chanid)
        m.add_string('exec')
        m.add_boolean(True)
        m.add_string(command)
        self._event_pending()
        self.transport._send_user_message(m)
        self._wait_for_event()

    def invoke_subsystem(self, subsystem):
        """
        Request a subsystem on the server (for example, ``sftp``).  If the
        server allows it, the channel will then be directly connected to the
        requested subsystem.
        
        When the subsystem finishes, the channel will be closed and can't be
        reused.

        :param str subsystem: name of the subsystem being requested.

        :raises SSHException:
            if the request was rejected or the channel was closed
        """
        if self.closed or self.eof_received or self.eof_sent or not self.active:
            raise SSHException('Channel is not open')
        m = Message()
        m.add_byte(cMSG_CHANNEL_REQUEST)
        m.add_int(self.remote_chanid)
        m.add_string('subsystem')
        m.add_boolean(True)
        m.add_string(subsystem)
        self._event_pending()
        self.transport._send_user_message(m)
        self._wait_for_event()

    def resize_pty(self, width=80, height=24, width_pixels=0, height_pixels=0):
        """
        Resize the pseudo-terminal.  This can be used to change the width and
        height of the terminal emulation created in a previous `get_pty` call.

        :param int width: new width (in characters) of the terminal screen
        :param int height: new height (in characters) of the terminal screen
        :param int width_pixels: new width (in pixels) of the terminal screen
        :param int height_pixels: new height (in pixels) of the terminal screen

        :raises SSHException:
            if the request was rejected or the channel was closed
        """
        if self.closed or self.eof_received or self.eof_sent or not self.active:
            raise SSHException('Channel is not open')
        m = Message()
        m.add_byte(cMSG_CHANNEL_REQUEST)
        m.add_int(self.remote_chanid)
        m.add_string('window-change')
        m.add_boolean(False)
        m.add_int(width)
        m.add_int(height)
        m.add_int(width_pixels)
        m.add_int(height_pixels)
        self.transport._send_user_message(m)

    def exit_status_ready(self):
        """
        Return true if the remote process has exited and returned an exit
        status. You may use this to poll the process status if you don't
        want to block in `recv_exit_status`. Note that the server may not
        return an exit status in some cases (like bad servers).
        
        :return:
            ``True`` if `recv_exit_status` will return immediately, else ``False``.

        .. versionadded:: 1.7.3
        """
        return self.closed or self.status_event.isSet()
        
    def recv_exit_status(self):
        """
        Return the exit status from the process on the server.  This is
        mostly useful for retrieving the reults of an `exec_command`.
        If the command hasn't finished yet, this method will wait until
        it does, or until the channel is closed.  If no exit status is
        provided by the server, -1 is returned.
        
        :return: the exit code (as an `int`) of the process on the server.
        
        .. versionadded:: 1.2
        """
        self.status_event.wait()
        assert self.status_event.isSet()
        return self.exit_status

    def send_exit_status(self, status):
        """
        Send the exit status of an executed command to the client.  (This
        really only makes sense in server mode.)  Many clients expect to
        get some sort of status code back from an executed command after
        it completes.
        
        :param int status: the exit code of the process
        
        .. versionadded:: 1.2
        """
        # in many cases, the channel will not still be open here.
        # that's fine.
        m = Message()
        m.add_byte(cMSG_CHANNEL_REQUEST)
        m.add_int(self.remote_chanid)
        m.add_string('exit-status')
        m.add_boolean(False)
        m.add_int(status)
        self.transport._send_user_message(m)
    
    def request_x11(self, screen_number=0, auth_protocol=None, auth_cookie=None,
                    single_connection=False, handler=None):
        """
        Request an x11 session on this channel.  If the server allows it,
        further x11 requests can be made from the server to the client,
        when an x11 application is run in a shell session.
        
        From RFC4254::

            It is RECOMMENDED that the 'x11 authentication cookie' that is
            sent be a fake, random cookie, and that the cookie be checked and
            replaced by the real cookie when a connection request is received.
        
        If you omit the auth_cookie, a new secure random 128-bit value will be
        generated, used, and returned.  You will need to use this value to
        verify incoming x11 requests and replace them with the actual local
        x11 cookie (which requires some knoweldge of the x11 protocol).
        
        If a handler is passed in, the handler is called from another thread
        whenever a new x11 connection arrives.  The default handler queues up
        incoming x11 connections, which may be retrieved using
        `.Transport.accept`.  The handler's calling signature is::
        
            handler(channel: Channel, (address: str, port: int))
        
        :param int screen_number: the x11 screen number (0, 10, etc)
        :param str auth_protocol:
            the name of the X11 authentication method used; if none is given,
            ``"MIT-MAGIC-COOKIE-1"`` is used
        :param str auth_cookie:
            hexadecimal string containing the x11 auth cookie; if none is
            given, a secure random 128-bit value is generated
        :param bool single_connection:
            if True, only a single x11 connection will be forwarded (by
            default, any number of x11 connections can arrive over this
            session)
        :param function handler:
            an optional handler to use for incoming X11 connections
        :return: the auth_cookie used
        """
        if self.closed or self.eof_received or self.eof_sent or not self.active:
            raise SSHException('Channel is not open')
        if auth_protocol is None:
            auth_protocol = 'MIT-MAGIC-COOKIE-1'
        if auth_cookie is None:
            auth_cookie = binascii.hexlify(os.urandom(16))

        m = Message()
        m.add_byte(cMSG_CHANNEL_REQUEST)
        m.add_int(self.remote_chanid)
        m.add_string('x11-req')
        m.add_boolean(True)
        m.add_boolean(single_connection)
        m.add_string(auth_protocol)
        m.add_string(auth_cookie)
        m.add_int(screen_number)
        self._event_pending()
        self.transport._send_user_message(m)
        self._wait_for_event()
        self.transport._set_x11_handler(handler)
        return auth_cookie

    def request_forward_agent(self, handler):
        """
        Request for a forward SSH Agent on this channel.
        This is only valid for an ssh-agent from OpenSSH !!!

        :param function handler:
            a required handler to use for incoming SSH Agent connections

        :return: True if we are ok, else False (at that time we always return ok)

        :raises: SSHException in case of channel problem.
        """
        if self.closed or self.eof_received or self.eof_sent or not self.active:
            raise SSHException('Channel is not open')

        m = Message()
        m.add_byte(cMSG_CHANNEL_REQUEST)
        m.add_int(self.remote_chanid)
        m.add_string('auth-agent-req@openssh.com')
        m.add_boolean(False)
        self.transport._send_user_message(m)
        self.transport._set_forward_agent_handler(handler)
        return True

    def get_transport(self):
        """
        Return the `.Transport` associated with this channel.
        """
        return self.transport

    def set_name(self, name):
        """
        Set a name for this channel.  Currently it's only used to set the name
        of the channel in logfile entries.  The name can be fetched with the
        `get_name` method.

        :param str name: new channel name
        """
        self._name = name

    def get_name(self):
        """
        Get the name of this channel that was previously set by `set_name`.
        """
        return self._name

    def get_id(self):
        """
        Return the `int` ID # for this channel.
        
        The channel ID is unique across a `.Transport` and usually a small
        number.  It's also the number passed to
        `.ServerInterface.check_channel_request` when determining whether to
        accept a channel request in server mode.
        """
        return self.chanid
    
    def set_combine_stderr(self, combine):
        """
        Set whether stderr should be combined into stdout on this channel.
        The default is ``False``, but in some cases it may be convenient to
        have both streams combined.
        
        If this is ``False``, and `exec_command` is called (or ``invoke_shell``
        with no pty), output to stderr will not show up through the `recv`
        and `recv_ready` calls.  You will have to use `recv_stderr` and
        `recv_stderr_ready` to get stderr output.
        
        If this is ``True``, data will never show up via `recv_stderr` or
        `recv_stderr_ready`.
        
        :param bool combine:
            ``True`` if stderr output should be combined into stdout on this
            channel.
        :return: the previous setting (a `bool`).
        
        .. versionadded:: 1.1
        """
        data = bytes()
        self.lock.acquire()
        try:
            old = self.combine_stderr
            self.combine_stderr = combine
            if combine and not old:
                # copy old stderr buffer into primary buffer
                data = self.in_stderr_buffer.empty()
        finally:
            self.lock.release()
        if len(data) > 0:
            self._feed(data)
        return old

    ###  socket API

    def settimeout(self, timeout):
        """
        Set a timeout on blocking read/write operations.  The ``timeout``
        argument can be a nonnegative float expressing seconds, or ``None``.  If
        a float is given, subsequent channel read/write operations will raise
        a timeout exception if the timeout period value has elapsed before the
        operation has completed.  Setting a timeout of ``None`` disables
        timeouts on socket operations.

        ``chan.settimeout(0.0)`` is equivalent to ``chan.setblocking(0)``;
        ``chan.settimeout(None)`` is equivalent to ``chan.setblocking(1)``.

        :param float timeout:
            seconds to wait for a pending read/write operation before raising
            ``socket.timeout``, or ``None`` for no timeout.
        """
        self.timeout = timeout

    def gettimeout(self):
        """
        Returns the timeout in seconds (as a float) associated with socket
        operations, or ``None`` if no timeout is set.  This reflects the last
        call to `setblocking` or `settimeout`.
        """
        return self.timeout

    def setblocking(self, blocking):
        """
        Set blocking or non-blocking mode of the channel: if ``blocking`` is 0,
        the channel is set to non-blocking mode; otherwise it's set to blocking
        mode. Initially all channels are in blocking mode.

        In non-blocking mode, if a `recv` call doesn't find any data, or if a
        `send` call can't immediately dispose of the data, an error exception
        is raised. In blocking mode, the calls block until they can proceed. An
        EOF condition is considered "immediate data" for `recv`, so if the
        channel is closed in the read direction, it will never block.

        ``chan.setblocking(0)`` is equivalent to ``chan.settimeout(0)``;
        ``chan.setblocking(1)`` is equivalent to ``chan.settimeout(None)``.

        :param int blocking:
            0 to set non-blocking mode; non-0 to set blocking mode.
        """
        if blocking:
            self.settimeout(None)
        else:
            self.settimeout(0.0)

    def getpeername(self):
        """
        Return the address of the remote side of this Channel, if possible.

        This simply wraps `.Transport.getpeername`, used to provide enough of a
        socket-like interface to allow asyncore to work. (asyncore likes to
        call ``'getpeername'``.)
        """
        return self.transport.getpeername()

    def close(self):
        """
        Close the channel.  All future read/write operations on the channel
        will fail.  The remote end will receive no more data (after queued data
        is flushed).  Channels are automatically closed when their `.Transport`
        is closed or when they are garbage collected.
        """
        self.lock.acquire()
        try:
            # only close the pipe when the user explicitly closes the channel.
            # otherwise they will get unpleasant surprises.  (and do it before
            # checking self.closed, since the remote host may have already
            # closed the connection.)
            if self._pipe is not None:
                self._pipe.close()
                self._pipe = None

            if not self.active or self.closed:
                return
            msgs = self._close_internal()
        finally:
            self.lock.release()
        for m in msgs:
            if m is not None:
                self.transport._send_user_message(m)

    def recv_ready(self):
        """
        Returns true if data is buffered and ready to be read from this
        channel.  A ``False`` result does not mean that the channel has closed;
        it means you may need to wait before more data arrives.
        
        :return:
            ``True`` if a `recv` call on this channel would immediately return
            at least one byte; ``False`` otherwise.
        """
        return self.in_buffer.read_ready()

    def recv(self, nbytes):
        """
        Receive data from the channel.  The return value is a string
        representing the data received.  The maximum amount of data to be
        received at once is specified by ``nbytes``.  If a string of length zero
        is returned, the channel stream has closed.

        :param int nbytes: maximum number of bytes to read.
        :return: received data, as a `str`
        
        :raises socket.timeout:
            if no data is ready before the timeout set by `settimeout`.
        """
        try:
            out = self.in_buffer.read(nbytes, self.timeout)
        except PipeTimeout:
            raise socket.timeout()

        ack = self._check_add_window(len(out))
        # no need to hold the channel lock when sending this
        if ack > 0:
            m = Message()
            m.add_byte(cMSG_CHANNEL_WINDOW_ADJUST)
            m.add_int(self.remote_chanid)
            m.add_int(ack)
            self.transport._send_user_message(m)

        return out

    def recv_stderr_ready(self):
        """
        Returns true if data is buffered and ready to be read from this
        channel's stderr stream.  Only channels using `exec_command` or
        `invoke_shell` without a pty will ever have data on the stderr
        stream.
        
        :return:
            ``True`` if a `recv_stderr` call on this channel would immediately
            return at least one byte; ``False`` otherwise.
        
        .. versionadded:: 1.1
        """
        return self.in_stderr_buffer.read_ready()

    def recv_stderr(self, nbytes):
        """
        Receive data from the channel's stderr stream.  Only channels using
        `exec_command` or `invoke_shell` without a pty will ever have data
        on the stderr stream.  The return value is a string representing the
        data received.  The maximum amount of data to be received at once is
        specified by ``nbytes``.  If a string of length zero is returned, the
        channel stream has closed.

        :param int nbytes: maximum number of bytes to read.
        :return: received data as a `str`
        
        :raises socket.timeout: if no data is ready before the timeout set by
            `settimeout`.
        
        .. versionadded:: 1.1
        """
        try:
            out = self.in_stderr_buffer.read(nbytes, self.timeout)
        except PipeTimeout:
            raise socket.timeout()
            
        ack = self._check_add_window(len(out))
        # no need to hold the channel lock when sending this
        if ack > 0:
            m = Message()
            m.add_byte(cMSG_CHANNEL_WINDOW_ADJUST)
            m.add_int(self.remote_chanid)
            m.add_int(ack)
            self.transport._send_user_message(m)

        return out

    def send_ready(self):
        """
        Returns true if data can be written to this channel without blocking.
        This means the channel is either closed (so any write attempt would
        return immediately) or there is at least one byte of space in the 
        outbound buffer. If there is at least one byte of space in the
        outbound buffer, a `send` call will succeed immediately and return
        the number of bytes actually written.
        
        :return:
            ``True`` if a `send` call on this channel would immediately succeed
            or fail
        """
        self.lock.acquire()
        try:
            if self.closed or self.eof_sent:
                return True
            return self.out_window_size > 0
        finally:
            self.lock.release()
    
    def send(self, s):
        """
        Send data to the channel.  Returns the number of bytes sent, or 0 if
        the channel stream is closed.  Applications are responsible for
        checking that all data has been sent: if only some of the data was
        transmitted, the application needs to attempt delivery of the remaining
        data.

        :param str s: data to send
        :return: number of bytes actually sent, as an `int`

        :raises socket.timeout: if no data could be sent before the timeout set
            by `settimeout`.
        """
        size = len(s)
        self.lock.acquire()
        try:
            size = self._wait_for_send_window(size)
            if size == 0:
                # eof or similar
                return 0
            m = Message()
            m.add_byte(cMSG_CHANNEL_DATA)
            m.add_int(self.remote_chanid)
            m.add_string(s[:size])
        finally:
            self.lock.release()
        # Note: We release self.lock before calling _send_user_message.
        # Otherwise, we can deadlock during re-keying.
        self.transport._send_user_message(m)
        return size

    def send_stderr(self, s):
        """
        Send data to the channel on the "stderr" stream.  This is normally
        only used by servers to send output from shell commands -- clients
        won't use this.  Returns the number of bytes sent, or 0 if the channel
        stream is closed.  Applications are responsible for checking that all
        data has been sent: if only some of the data was transmitted, the
        application needs to attempt delivery of the remaining data.
        
        :param str s: data to send.
        :return: number of bytes actually sent, as an `int`.
        
        :raises socket.timeout:
            if no data could be sent before the timeout set by `settimeout`.
        
        .. versionadded:: 1.1
        """
        size = len(s)
        self.lock.acquire()
        try:
            size = self._wait_for_send_window(size)
            if size == 0:
                # eof or similar
                return 0
            m = Message()
            m.add_byte(cMSG_CHANNEL_EXTENDED_DATA)
            m.add_int(self.remote_chanid)
            m.add_int(1)
            m.add_string(s[:size])
        finally:
            self.lock.release()
        # Note: We release self.lock before calling _send_user_message.
        # Otherwise, we can deadlock during re-keying.
        self.transport._send_user_message(m)
        return size

    def sendall(self, s):
        """
        Send data to the channel, without allowing partial results.  Unlike
        `send`, this method continues to send data from the given string until
        either all data has been sent or an error occurs.  Nothing is returned.

        :param str s: data to send.

        :raises socket.timeout:
            if sending stalled for longer than the timeout set by `settimeout`.
        :raises socket.error:
            if an error occured before the entire string was sent.
        
        .. note::
            If the channel is closed while only part of the data hase been
            sent, there is no way to determine how much data (if any) was sent.
            This is irritating, but identically follows Python's API.
        """
        while s:
            if self.closed:
                # this doesn't seem useful, but it is the documented behavior of Socket
                raise socket.error('Socket is closed')
            sent = self.send(s)
            s = s[sent:]
        return None

    def sendall_stderr(self, s):
        """
        Send data to the channel's "stderr" stream, without allowing partial
        results.  Unlike `send_stderr`, this method continues to send data
        from the given string until all data has been sent or an error occurs.
        Nothing is returned.
        
        :param str s: data to send to the client as "stderr" output.
        
        :raises socket.timeout:
            if sending stalled for longer than the timeout set by `settimeout`.
        :raises socket.error:
            if an error occured before the entire string was sent.
            
        .. versionadded:: 1.1
        """
        while s:
            if self.closed:
                raise socket.error('Socket is closed')
            sent = self.send_stderr(s)
            s = s[sent:]
        return None

    def makefile(self, *params):
        """
        Return a file-like object associated with this channel.  The optional
        ``mode`` and ``bufsize`` arguments are interpreted the same way as by
        the built-in ``file()`` function in Python.

        :return: `.ChannelFile` object which can be used for Python file I/O.
        """
        return ChannelFile(*([self] + list(params)))

    def makefile_stderr(self, *params):
        """
        Return a file-like object associated with this channel's stderr
        stream.   Only channels using `exec_command` or `invoke_shell`
        without a pty will ever have data on the stderr stream.
        
        The optional ``mode`` and ``bufsize`` arguments are interpreted the
        same way as by the built-in ``file()`` function in Python.  For a
        client, it only makes sense to open this file for reading.  For a
        server, it only makes sense to open this file for writing.
        
        :return: `.ChannelFile` object which can be used for Python file I/O.

        .. versionadded:: 1.1
        """
        return ChannelStderrFile(*([self] + list(params)))
        
    def fileno(self):
        """
        Returns an OS-level file descriptor which can be used for polling, but
        but not for reading or writing.  This is primaily to allow Python's
        ``select`` module to work.

        The first time ``fileno`` is called on a channel, a pipe is created to
        simulate real OS-level file descriptor (FD) behavior.  Because of this,
        two OS-level FDs are created, which will use up FDs faster than normal.
        (You won't notice this effect unless you have hundreds of channels
        open at the same time.)

        :return: an OS-level file descriptor (`int`)
        
        .. warning::
            This method causes channel reads to be slightly less efficient.
        """
        self.lock.acquire()
        try:
            if self._pipe is not None:
                return self._pipe.fileno()
            # create the pipe and feed in any existing data
            self._pipe = pipe.make_pipe()
            p1, p2 = pipe.make_or_pipe(self._pipe)
            self.in_buffer.set_event(p1)
            self.in_stderr_buffer.set_event(p2)
            return self._pipe.fileno()
        finally:
            self.lock.release()

    def shutdown(self, how):
        """
        Shut down one or both halves of the connection.  If ``how`` is 0,
        further receives are disallowed.  If ``how`` is 1, further sends
        are disallowed.  If ``how`` is 2, further sends and receives are
        disallowed.  This closes the stream in one or both directions.

        :param int how:
            0 (stop receiving), 1 (stop sending), or 2 (stop receiving and
              sending).
        """
        if (how == 0) or (how == 2):
            # feign "read" shutdown
            self.eof_received = 1
        if (how == 1) or (how == 2):
            self.lock.acquire()
            try:
                m = self._send_eof()
            finally:
                self.lock.release()
            if m is not None:
                self.transport._send_user_message(m)
    
    def shutdown_read(self):
        """
        Shutdown the receiving side of this socket, closing the stream in
        the incoming direction.  After this call, future reads on this
        channel will fail instantly.  This is a convenience method, equivalent
        to ``shutdown(0)``, for people who don't make it a habit to
        memorize unix constants from the 1970s.
        
        .. versionadded:: 1.2
        """
        self.shutdown(0)
    
    def shutdown_write(self):
        """
        Shutdown the sending side of this socket, closing the stream in
        the outgoing direction.  After this call, future writes on this
        channel will fail instantly.  This is a convenience method, equivalent
        to ``shutdown(1)``, for people who don't make it a habit to
        memorize unix constants from the 1970s.
        
        .. versionadded:: 1.2
        """
        self.shutdown(1)

    ###  calls from Transport

    def _set_transport(self, transport):
        self.transport = transport
        self.logger = util.get_logger(self.transport.get_log_channel())

    def _set_window(self, window_size, max_packet_size):
        self.in_window_size = window_size
        self.in_max_packet_size = max_packet_size
        # threshold of bytes we receive before we bother to send a window update
        self.in_window_threshold = window_size // 10
        self.in_window_sofar = 0
        self._log(DEBUG, 'Max packet in: %d bytes' % max_packet_size)
        
    def _set_remote_channel(self, chanid, window_size, max_packet_size):
        self.remote_chanid = chanid
        self.out_window_size = window_size
        self.out_max_packet_size = max(max_packet_size, MIN_PACKET_SIZE)
        self.active = 1
        self._log(DEBUG, 'Max packet out: %d bytes' % max_packet_size)
        
    def _request_success(self, m):
        self._log(DEBUG, 'Sesch channel %d request ok' % self.chanid)
        self.event_ready = True
        self.event.set()
        return

    def _request_failed(self, m):
        self.lock.acquire()
        try:
            msgs = self._close_internal()
        finally:
            self.lock.release()
        for m in msgs:
            if m is not None:
                self.transport._send_user_message(m)

    def _feed(self, m):
        if isinstance(m, bytes_types):
            # passed from _feed_extended
            s = m
        else:
            s = m.get_binary()
        self.in_buffer.feed(s)

    def _feed_extended(self, m):
        code = m.get_int()
        s = m.get_binary()
        if code != 1:
            self._log(ERROR, 'unknown extended_data type %d; discarding' % code)
            return
        if self.combine_stderr:
            self._feed(s)
        else:
            self.in_stderr_buffer.feed(s)
        
    def _window_adjust(self, m):
        nbytes = m.get_int()
        self.lock.acquire()
        try:
            if self.ultra_debug:
                self._log(DEBUG, 'window up %d' % nbytes)
            self.out_window_size += nbytes
            self.out_buffer_cv.notifyAll()
        finally:
            self.lock.release()

    def _handle_request(self, m):
        key = m.get_text()
        want_reply = m.get_boolean()
        server = self.transport.server_object
        ok = False
        if key == 'exit-status':
            self.exit_status = m.get_int()
            self.status_event.set()
            ok = True
        elif key == 'xon-xoff':
            # ignore
            ok = True
        elif key == 'pty-req':
            term = m.get_string()
            width = m.get_int()
            height = m.get_int()
            pixelwidth = m.get_int()
            pixelheight = m.get_int()
            modes = m.get_string()
            if server is None:
                ok = False
            else:
                ok = server.check_channel_pty_request(self, term, width, height, pixelwidth,
                                                      pixelheight, modes)
        elif key == 'shell':
            if server is None:
                ok = False
            else:
                ok = server.check_channel_shell_request(self)
        elif key == 'env':
            name = m.get_string()
            value = m.get_string()
            if server is None:
                ok = False
            else:
                ok = server.check_channel_env_request(self, name, value)
        elif key == 'exec':
            cmd = m.get_text()
            if server is None:
                ok = False
            else:
                ok = server.check_channel_exec_request(self, cmd)
        elif key == 'subsystem':
            name = m.get_text()
            if server is None:
                ok = False
            else:
                ok = server.check_channel_subsystem_request(self, name)
        elif key == 'window-change':
            width = m.get_int()
            height = m.get_int()
            pixelwidth = m.get_int()
            pixelheight = m.get_int()
            if server is None:
                ok = False
            else:
                ok = server.check_channel_window_change_request(self, width, height, pixelwidth,
                                                                pixelheight)
        elif key == 'x11-req':
            single_connection = m.get_boolean()
            auth_proto = m.get_text()
            auth_cookie = m.get_binary()
            screen_number = m.get_int()
            if server is None:
                ok = False
            else:
                ok = server.check_channel_x11_request(self, single_connection,
                                                      auth_proto, auth_cookie, screen_number)
        elif key == 'auth-agent-req@openssh.com':
            if server is None:
                ok = False
            else:
                ok = server.check_channel_forward_agent_request(self)
        else:
            self._log(DEBUG, 'Unhandled channel request "%s"' % key)
            ok = False
        if want_reply:
            m = Message()
            if ok:
                m.add_byte(cMSG_CHANNEL_SUCCESS)
            else:
                m.add_byte(cMSG_CHANNEL_FAILURE)
            m.add_int(self.remote_chanid)
            self.transport._send_user_message(m)

    def _handle_eof(self, m):
        self.lock.acquire()
        try:
            if not self.eof_received:
                self.eof_received = True
                self.in_buffer.close()
                self.in_stderr_buffer.close()
                if self._pipe is not None:
                    self._pipe.set_forever()
        finally:
            self.lock.release()
        self._log(DEBUG, 'EOF received (%s)', self._name)

    def _handle_close(self, m):
        self.lock.acquire()
        try:
            msgs = self._close_internal()
            self.transport._unlink_channel(self.chanid)
        finally:
            self.lock.release()
        for m in msgs:
            if m is not None:
                self.transport._send_user_message(m)

    ###  internals...

    def _log(self, level, msg, *args):
        self.logger.log(level, "[chan " + self._name + "] " + msg, *args)

    def _event_pending(self):
        self.event.clear()
        self.event_ready = False

    def _wait_for_event(self):
        self.event.wait()
        assert self.event.isSet()
        if self.event_ready:
            return
        e = self.transport.get_exception()
        if e is None:
            e = SSHException('Channel closed.')
        raise e

    def _set_closed(self):
        # you are holding the lock.
        self.closed = True
        self.in_buffer.close()
        self.in_stderr_buffer.close()
        self.out_buffer_cv.notifyAll()
        # Notify any waiters that we are closed
        self.event.set()
        self.status_event.set()
        if self._pipe is not None:
            self._pipe.set_forever()

    def _send_eof(self):
        # you are holding the lock.
        if self.eof_sent:
            return None
        m = Message()
        m.add_byte(cMSG_CHANNEL_EOF)
        m.add_int(self.remote_chanid)
        self.eof_sent = True
        self._log(DEBUG, 'EOF sent (%s)', self._name)
        return m

    def _close_internal(self):
        # you are holding the lock.
        if not self.active or self.closed:
            return None, None
        m1 = self._send_eof()
        m2 = Message()
        m2.add_byte(cMSG_CHANNEL_CLOSE)
        m2.add_int(self.remote_chanid)
        self._set_closed()
        # can't unlink from the Transport yet -- the remote side may still
        # try to send meta-data (exit-status, etc)
        return m1, m2

    def _unlink(self):
        # server connection could die before we become active: still signal the close!
        if self.closed:
            return
        self.lock.acquire()
        try:
            self._set_closed()
            self.transport._unlink_channel(self.chanid)
        finally:
            self.lock.release()

    def _check_add_window(self, n):
        self.lock.acquire()
        try:
            if self.closed or self.eof_received or not self.active:
                return 0
            if self.ultra_debug:
                self._log(DEBUG, 'addwindow %d' % n)
            self.in_window_sofar += n
            if self.in_window_sofar <= self.in_window_threshold:
                return 0
            if self.ultra_debug:
                self._log(DEBUG, 'addwindow send %d' % self.in_window_sofar)
            out = self.in_window_sofar
            self.in_window_sofar = 0
            return out
        finally:
            self.lock.release()

    def _wait_for_send_window(self, size):
        """
        (You are already holding the lock.)
        Wait for the send window to open up, and allocate up to ``size`` bytes
        for transmission.  If no space opens up before the timeout, a timeout
        exception is raised.  Returns the number of bytes available to send
        (may be less than requested).
        """
        # you are already holding the lock
        if self.closed or self.eof_sent:
            return 0
        if self.out_window_size == 0:
            # should we block?
            if self.timeout == 0.0:
                raise socket.timeout()
            # loop here in case we get woken up but a different thread has filled the buffer
            timeout = self.timeout
            while self.out_window_size == 0:
                if self.closed or self.eof_sent:
                    return 0
                then = time.time()
                self.out_buffer_cv.wait(timeout)
                if timeout is not None:
                    timeout -= time.time() - then
                    if timeout <= 0.0:
                        raise socket.timeout()
        # we have some window to squeeze into
        if self.closed or self.eof_sent:
            return 0
        if self.out_window_size < size:
            size = self.out_window_size
        if self.out_max_packet_size - 64 < size:
            size = self.out_max_packet_size - 64
        self.out_window_size -= size
        if self.ultra_debug:
            self._log(DEBUG, 'window down to %d' % self.out_window_size)
        return size
        

class ChannelFile (BufferedFile):
    """
    A file-like wrapper around `.Channel`.  A ChannelFile is created by calling
    `Channel.makefile`.

    .. warning::
        To correctly emulate the file object created from a socket's `makefile
        <python:socket.socket.makefile>` method, a `.Channel` and its
        `.ChannelFile` should be able to be closed or garbage-collected
        independently. Currently, closing the `ChannelFile` does nothing but
        flush the buffer.
    """

    def __init__(self, channel, mode='r', bufsize=-1):
        self.channel = channel
        BufferedFile.__init__(self)
        self._set_mode(mode, bufsize)

    def __repr__(self):
        """
        Returns a string representation of this object, for debugging.
        """
        return '<paramiko.ChannelFile from ' + repr(self.channel) + '>'

    def _read(self, size):
        return self.channel.recv(size)

    def _write(self, data):
        self.channel.sendall(data)
        return len(data)


class ChannelStderrFile (ChannelFile):
    def __init__(self, channel, mode='r', bufsize=-1):
        ChannelFile.__init__(self, channel, mode, bufsize)

    def _read(self, size):
        return self.channel.recv_stderr(size)
    
    def _write(self, data):
        self.channel.sendall_stderr(data)
        return len(data)


# vim: set shiftwidth=4 expandtab :

########NEW FILE########
__FILENAME__ = client
# Copyright (C) 2006-2007  Robey Pointer <robeypointer@gmail.com>
#
# This file is part of paramiko.
#
# Paramiko is free software; you can redistribute it and/or modify it under the
# terms of the GNU Lesser General Public License as published by the Free
# Software Foundation; either version 2.1 of the License, or (at your option)
# any later version.
#
# Paramiko is distributed in the hope that it will be useful, but WITHOUT ANY
# WARRANTY; without even the implied warranty of MERCHANTABILITY or FITNESS FOR
# A PARTICULAR PURPOSE.  See the GNU Lesser General Public License for more
# details.
#
# You should have received a copy of the GNU Lesser General Public License
# along with Paramiko; if not, write to the Free Software Foundation, Inc.,
# 59 Temple Place, Suite 330, Boston, MA  02111-1307  USA.

"""
SSH client & key policies
"""

from binascii import hexlify
import getpass
import os
import socket
import warnings

from paramiko.agent import Agent
from paramiko.common import DEBUG
from paramiko.config import SSH_PORT
from paramiko.dsskey import DSSKey
from paramiko.hostkeys import HostKeys
from paramiko.py3compat import string_types
from paramiko.resource import ResourceManager
from paramiko.rsakey import RSAKey
from paramiko.ssh_exception import SSHException, BadHostKeyException
from paramiko.transport import Transport
from paramiko.util import retry_on_signal


class SSHClient (object):
    """
    A high-level representation of a session with an SSH server.  This class
    wraps `.Transport`, `.Channel`, and `.SFTPClient` to take care of most
    aspects of authenticating and opening channels.  A typical use case is::

        client = SSHClient()
        client.load_system_host_keys()
        client.connect('ssh.example.com')
        stdin, stdout, stderr = client.exec_command('ls -l')

    You may pass in explicit overrides for authentication and server host key
    checking.  The default mechanism is to try to use local key files or an
    SSH agent (if one is running).

    .. versionadded:: 1.6
    """

    def __init__(self):
        """
        Create a new SSHClient.
        """
        self._system_host_keys = HostKeys()
        self._host_keys = HostKeys()
        self._host_keys_filename = None
        self._log_channel = None
        self._policy = RejectPolicy()
        self._transport = None
        self._agent = None

    def load_system_host_keys(self, filename=None):
        """
        Load host keys from a system (read-only) file.  Host keys read with
        this method will not be saved back by `save_host_keys`.

        This method can be called multiple times.  Each new set of host keys
        will be merged with the existing set (new replacing old if there are
        conflicts).

        If ``filename`` is left as ``None``, an attempt will be made to read
        keys from the user's local "known hosts" file, as used by OpenSSH,
        and no exception will be raised if the file can't be read.  This is
        probably only useful on posix.

        :param str filename: the filename to read, or ``None``

        :raises IOError:
            if a filename was provided and the file could not be read
        """
        if filename is None:
            # try the user's .ssh key file, and mask exceptions
            filename = os.path.expanduser('~/.ssh/known_hosts')
            try:
                self._system_host_keys.load(filename)
            except IOError:
                pass
            return
        self._system_host_keys.load(filename)

    def load_host_keys(self, filename):
        """
        Load host keys from a local host-key file.  Host keys read with this
        method will be checked after keys loaded via `load_system_host_keys`,
        but will be saved back by `save_host_keys` (so they can be modified).
        The missing host key policy `.AutoAddPolicy` adds keys to this set and
        saves them, when connecting to a previously-unknown server.

        This method can be called multiple times.  Each new set of host keys
        will be merged with the existing set (new replacing old if there are
        conflicts).  When automatically saving, the last hostname is used.

        :param str filename: the filename to read

        :raises IOError: if the filename could not be read
        """
        self._host_keys_filename = filename
        self._host_keys.load(filename)

    def save_host_keys(self, filename):
        """
        Save the host keys back to a file.  Only the host keys loaded with
        `load_host_keys` (plus any added directly) will be saved -- not any
        host keys loaded with `load_system_host_keys`.

        :param str filename: the filename to save to

        :raises IOError: if the file could not be written
        """

        # update local host keys from file (in case other SSH clients
        # have written to the known_hosts file meanwhile.
        if self._host_keys_filename is not None:
            self.load_host_keys(self._host_keys_filename)

        with open(filename, 'w') as f:
            for hostname, keys in self._host_keys.items():
                for keytype, key in keys.items():
                    f.write('%s %s %s\n' % (hostname, keytype, key.get_base64()))

    def get_host_keys(self):
        """
        Get the local `.HostKeys` object.  This can be used to examine the
        local host keys or change them.

        :return: the local host keys as a `.HostKeys` object.
        """
        return self._host_keys

    def set_log_channel(self, name):
        """
        Set the channel for logging.  The default is ``"paramiko.transport"``
        but it can be set to anything you want.

        :param str name: new channel name for logging
        """
        self._log_channel = name

    def set_missing_host_key_policy(self, policy):
        """
        Set the policy to use when connecting to a server that doesn't have a
        host key in either the system or local `.HostKeys` objects.  The
        default policy is to reject all unknown servers (using `.RejectPolicy`).
        You may substitute `.AutoAddPolicy` or write your own policy class.

        :param .MissingHostKeyPolicy policy:
            the policy to use when receiving a host key from a
            previously-unknown server
        """
        self._policy = policy

    def connect(self, hostname, port=SSH_PORT, username=None, password=None, pkey=None,
                key_filename=None, timeout=None, allow_agent=True, look_for_keys=True,
                compress=False, sock=None):
        """
        Connect to an SSH server and authenticate to it.  The server's host key
        is checked against the system host keys (see `load_system_host_keys`)
        and any local host keys (`load_host_keys`).  If the server's hostname
        is not found in either set of host keys, the missing host key policy
        is used (see `set_missing_host_key_policy`).  The default policy is
        to reject the key and raise an `.SSHException`.

        Authentication is attempted in the following order of priority:

            - The ``pkey`` or ``key_filename`` passed in (if any)
            - Any key we can find through an SSH agent
            - Any "id_rsa" or "id_dsa" key discoverable in ``~/.ssh/``
            - Plain username/password auth, if a password was given

        If a private key requires a password to unlock it, and a password is
        passed in, that password will be used to attempt to unlock the key.

        :param str hostname: the server to connect to
        :param int port: the server port to connect to
        :param str username:
            the username to authenticate as (defaults to the current local
            username)
        :param str password:
            a password to use for authentication or for unlocking a private key
        :param .PKey pkey: an optional private key to use for authentication
        :param str key_filename:
            the filename, or list of filenames, of optional private key(s) to
            try for authentication
        :param float timeout: an optional timeout (in seconds) for the TCP connect
        :param bool allow_agent: set to False to disable connecting to the SSH agent
        :param bool look_for_keys:
            set to False to disable searching for discoverable private key
            files in ``~/.ssh/``
        :param bool compress: set to True to turn on compression
        :param socket sock:
            an open socket or socket-like object (such as a `.Channel`) to use
            for communication to the target host

        :raises BadHostKeyException: if the server's host key could not be
            verified
        :raises AuthenticationException: if authentication failed
        :raises SSHException: if there was any other error connecting or
            establishing an SSH session
        :raises socket.error: if a socket error occurred while connecting
        """
        if not sock:
            for (family, socktype, proto, canonname, sockaddr) in socket.getaddrinfo(hostname, port, socket.AF_UNSPEC, socket.SOCK_STREAM):
                if socktype == socket.SOCK_STREAM:
                    af = family
                    addr = sockaddr
                    break
            else:
                # some OS like AIX don't indicate SOCK_STREAM support, so just guess. :(
                af, _, _, _, addr = socket.getaddrinfo(hostname, port, socket.AF_UNSPEC, socket.SOCK_STREAM)
            sock = socket.socket(af, socket.SOCK_STREAM)
            if timeout is not None:
                try:
                    sock.settimeout(timeout)
                except:
                    pass
            retry_on_signal(lambda: sock.connect(addr))

        t = self._transport = Transport(sock)
        t.use_compression(compress=compress)
        if self._log_channel is not None:
            t.set_log_channel(self._log_channel)
        t.start_client()
        ResourceManager.register(self, t)

        server_key = t.get_remote_server_key()
        keytype = server_key.get_name()

        if port == SSH_PORT:
            server_hostkey_name = hostname
        else:
            server_hostkey_name = "[%s]:%d" % (hostname, port)
        our_server_key = self._system_host_keys.get(server_hostkey_name, {}).get(keytype, None)
        if our_server_key is None:
            our_server_key = self._host_keys.get(server_hostkey_name, {}).get(keytype, None)
        if our_server_key is None:
            # will raise exception if the key is rejected; let that fall out
            self._policy.missing_host_key(self, server_hostkey_name, server_key)
            # if the callback returns, assume the key is ok
            our_server_key = server_key

        if server_key != our_server_key:
            raise BadHostKeyException(hostname, server_key, our_server_key)

        if username is None:
            username = getpass.getuser()

        if key_filename is None:
            key_filenames = []
        elif isinstance(key_filename, string_types):
            key_filenames = [key_filename]
        else:
            key_filenames = key_filename
        self._auth(username, password, pkey, key_filenames, allow_agent, look_for_keys)

    def close(self):
        """
        Close this SSHClient and its underlying `.Transport`.
        """
        if self._transport is None:
            return
        self._transport.close()
        self._transport = None

        if self._agent is not None:
            self._agent.close()
            self._agent = None

    def exec_command(self, command, bufsize=-1, timeout=None, get_pty=False):
        """
        Execute a command on the SSH server.  A new `.Channel` is opened and
        the requested command is executed.  The command's input and output
        streams are returned as Python ``file``-like objects representing
        stdin, stdout, and stderr.

        :param str command: the command to execute
        :param int bufsize:
            interpreted the same way as by the built-in ``file()`` function in
            Python
        :param int timeout:
            set command's channel timeout. See `Channel.settimeout`.settimeout
        :return:
            the stdin, stdout, and stderr of the executing command, as a
            3-tuple

        :raises SSHException: if the server fails to execute the command
        """
        chan = self._transport.open_session()
        if get_pty:
            chan.get_pty()
        chan.settimeout(timeout)
        chan.exec_command(command)
        stdin = chan.makefile('wb', bufsize)
        stdout = chan.makefile('r', bufsize)
        stderr = chan.makefile_stderr('r', bufsize)
        return stdin, stdout, stderr

    def invoke_shell(self, term='vt100', width=80, height=24, width_pixels=0,
                     height_pixels=0):
        """
        Start an interactive shell session on the SSH server.  A new `.Channel`
        is opened and connected to a pseudo-terminal using the requested
        terminal type and size.

        :param str term:
            the terminal type to emulate (for example, ``"vt100"``)
        :param int width: the width (in characters) of the terminal window
        :param int height: the height (in characters) of the terminal window
        :param int width_pixels: the width (in pixels) of the terminal window
        :param int height_pixels: the height (in pixels) of the terminal window
        :return: a new `.Channel` connected to the remote shell

        :raises SSHException: if the server fails to invoke a shell
        """
        chan = self._transport.open_session()
        chan.get_pty(term, width, height, width_pixels, height_pixels)
        chan.invoke_shell()
        return chan

    def open_sftp(self):
        """
        Open an SFTP session on the SSH server.

        :return: a new `.SFTPClient` session object
        """
        return self._transport.open_sftp_client()

    def get_transport(self):
        """
        Return the underlying `.Transport` object for this SSH connection.
        This can be used to perform lower-level tasks, like opening specific
        kinds of channels.

        :return: the `.Transport` for this connection
        """
        return self._transport

    def _auth(self, username, password, pkey, key_filenames, allow_agent, look_for_keys):
        """
        Try, in order:

            - The key passed in, if one was passed in.
            - Any key we can find through an SSH agent (if allowed).
            - Any "id_rsa" or "id_dsa" key discoverable in ~/.ssh/ (if allowed).
            - Plain username/password auth, if a password was given.

        (The password might be needed to unlock a private key, or for
        two-factor authentication [for which it is required].)
        """
        saved_exception = None
        two_factor = False
        allowed_types = []

        if pkey is not None:
            try:
                self._log(DEBUG, 'Trying SSH key %s' % hexlify(pkey.get_fingerprint()))
                allowed_types = self._transport.auth_publickey(username, pkey)
                two_factor = (allowed_types == ['password'])
                if not two_factor:
                    return
            except SSHException as e:
                saved_exception = e

        if not two_factor:
            for key_filename in key_filenames:
                for pkey_class in (RSAKey, DSSKey):
                    try:
                        key = pkey_class.from_private_key_file(key_filename, password)
                        self._log(DEBUG, 'Trying key %s from %s' % (hexlify(key.get_fingerprint()), key_filename))
                        self._transport.auth_publickey(username, key)
                        two_factor = (allowed_types == ['password'])
                        if not two_factor:
                            return
                        break
                    except SSHException as e:
                        saved_exception = e

        if not two_factor and allow_agent:
            if self._agent is None:
                self._agent = Agent()

            for key in self._agent.get_keys():
                try:
                    self._log(DEBUG, 'Trying SSH agent key %s' % hexlify(key.get_fingerprint()))
                    # for 2-factor auth a successfully auth'd key will result in ['password']
                    allowed_types = self._transport.auth_publickey(username, key)
                    two_factor = (allowed_types == ['password'])
                    if not two_factor:
                        return
                    break
                except SSHException as e:
                    saved_exception = e

        if not two_factor:
            keyfiles = []
            rsa_key = os.path.expanduser('~/.ssh/id_rsa')
            dsa_key = os.path.expanduser('~/.ssh/id_dsa')
            if os.path.isfile(rsa_key):
                keyfiles.append((RSAKey, rsa_key))
            if os.path.isfile(dsa_key):
                keyfiles.append((DSSKey, dsa_key))
            # look in ~/ssh/ for windows users:
            rsa_key = os.path.expanduser('~/ssh/id_rsa')
            dsa_key = os.path.expanduser('~/ssh/id_dsa')
            if os.path.isfile(rsa_key):
                keyfiles.append((RSAKey, rsa_key))
            if os.path.isfile(dsa_key):
                keyfiles.append((DSSKey, dsa_key))

            if not look_for_keys:
                keyfiles = []

            for pkey_class, filename in keyfiles:
                try:
                    key = pkey_class.from_private_key_file(filename, password)
                    self._log(DEBUG, 'Trying discovered key %s in %s' % (hexlify(key.get_fingerprint()), filename))
                    # for 2-factor auth a successfully auth'd key will result in ['password']
                    allowed_types = self._transport.auth_publickey(username, key)
                    two_factor = (allowed_types == ['password'])
                    if not two_factor:
                        return
                    break
                except (SSHException, IOError) as e:
                    saved_exception = e

        if password is not None:
            try:
                self._transport.auth_password(username, password)
                return
            except SSHException as e:
                saved_exception = e
        elif two_factor:
            raise SSHException('Two-factor authentication requires a password')

        # if we got an auth-failed exception earlier, re-raise it
        if saved_exception is not None:
            raise saved_exception
        raise SSHException('No authentication methods available')

    def _log(self, level, msg):
        self._transport._log(level, msg)


class MissingHostKeyPolicy (object):
    """
    Interface for defining the policy that `.SSHClient` should use when the
    SSH server's hostname is not in either the system host keys or the
    application's keys.  Pre-made classes implement policies for automatically
    adding the key to the application's `.HostKeys` object (`.AutoAddPolicy`),
    and for automatically rejecting the key (`.RejectPolicy`).

    This function may be used to ask the user to verify the key, for example.
    """

    def missing_host_key(self, client, hostname, key):
        """
        Called when an `.SSHClient` receives a server key for a server that
        isn't in either the system or local `.HostKeys` object.  To accept
        the key, simply return.  To reject, raised an exception (which will
        be passed to the calling application).
        """
        pass


class AutoAddPolicy (MissingHostKeyPolicy):
    """
    Policy for automatically adding the hostname and new host key to the
    local `.HostKeys` object, and saving it.  This is used by `.SSHClient`.
    """

    def missing_host_key(self, client, hostname, key):
        client._host_keys.add(hostname, key.get_name(), key)
        if client._host_keys_filename is not None:
            client.save_host_keys(client._host_keys_filename)
        client._log(DEBUG, 'Adding %s host key for %s: %s' %
                    (key.get_name(), hostname, hexlify(key.get_fingerprint())))


class RejectPolicy (MissingHostKeyPolicy):
    """
    Policy for automatically rejecting the unknown hostname & key.  This is
    used by `.SSHClient`.
    """

    def missing_host_key(self, client, hostname, key):
        client._log(DEBUG, 'Rejecting %s host key for %s: %s' %
                    (key.get_name(), hostname, hexlify(key.get_fingerprint())))
        raise SSHException('Server %r not found in known_hosts' % hostname)


class WarningPolicy (MissingHostKeyPolicy):
    """
    Policy for logging a Python-style warning for an unknown host key, but
    accepting it. This is used by `.SSHClient`.
    """
    def missing_host_key(self, client, hostname, key):
        warnings.warn('Unknown %s host key for %s: %s' %
                      (key.get_name(), hostname, hexlify(key.get_fingerprint())))

########NEW FILE########
__FILENAME__ = common
# Copyright (C) 2003-2007  Robey Pointer <robeypointer@gmail.com>
#
# This file is part of paramiko.
#
# Paramiko is free software; you can redistribute it and/or modify it under the
# terms of the GNU Lesser General Public License as published by the Free
# Software Foundation; either version 2.1 of the License, or (at your option)
# any later version.
#
# Paramiko is distributed in the hope that it will be useful, but WITHOUT ANY
# WARRANTY; without even the implied warranty of MERCHANTABILITY or FITNESS FOR
# A PARTICULAR PURPOSE.  See the GNU Lesser General Public License for more
# details.
#
# You should have received a copy of the GNU Lesser General Public License
# along with Paramiko; if not, write to the Free Software Foundation, Inc.,
# 59 Temple Place, Suite 330, Boston, MA  02111-1307  USA.

"""
Common constants and global variables.
"""
import logging
from paramiko.py3compat import byte_chr, PY2, bytes_types, string_types, b, long

MSG_DISCONNECT, MSG_IGNORE, MSG_UNIMPLEMENTED, MSG_DEBUG, MSG_SERVICE_REQUEST, \
    MSG_SERVICE_ACCEPT = range(1, 7)
MSG_KEXINIT, MSG_NEWKEYS = range(20, 22)
MSG_USERAUTH_REQUEST, MSG_USERAUTH_FAILURE, MSG_USERAUTH_SUCCESS, \
    MSG_USERAUTH_BANNER = range(50, 54)
MSG_USERAUTH_PK_OK = 60
MSG_USERAUTH_INFO_REQUEST, MSG_USERAUTH_INFO_RESPONSE = range(60, 62)
MSG_GLOBAL_REQUEST, MSG_REQUEST_SUCCESS, MSG_REQUEST_FAILURE = range(80, 83)
MSG_CHANNEL_OPEN, MSG_CHANNEL_OPEN_SUCCESS, MSG_CHANNEL_OPEN_FAILURE, \
    MSG_CHANNEL_WINDOW_ADJUST, MSG_CHANNEL_DATA, MSG_CHANNEL_EXTENDED_DATA, \
    MSG_CHANNEL_EOF, MSG_CHANNEL_CLOSE, MSG_CHANNEL_REQUEST, \
    MSG_CHANNEL_SUCCESS, MSG_CHANNEL_FAILURE = range(90, 101)

cMSG_DISCONNECT = byte_chr(MSG_DISCONNECT)
cMSG_IGNORE = byte_chr(MSG_IGNORE)
cMSG_UNIMPLEMENTED = byte_chr(MSG_UNIMPLEMENTED)
cMSG_DEBUG = byte_chr(MSG_DEBUG)
cMSG_SERVICE_REQUEST = byte_chr(MSG_SERVICE_REQUEST)
cMSG_SERVICE_ACCEPT = byte_chr(MSG_SERVICE_ACCEPT)
cMSG_KEXINIT = byte_chr(MSG_KEXINIT)
cMSG_NEWKEYS = byte_chr(MSG_NEWKEYS)
cMSG_USERAUTH_REQUEST = byte_chr(MSG_USERAUTH_REQUEST)
cMSG_USERAUTH_FAILURE = byte_chr(MSG_USERAUTH_FAILURE)
cMSG_USERAUTH_SUCCESS = byte_chr(MSG_USERAUTH_SUCCESS)
cMSG_USERAUTH_BANNER = byte_chr(MSG_USERAUTH_BANNER)
cMSG_USERAUTH_PK_OK = byte_chr(MSG_USERAUTH_PK_OK)
cMSG_USERAUTH_INFO_REQUEST = byte_chr(MSG_USERAUTH_INFO_REQUEST)
cMSG_USERAUTH_INFO_RESPONSE = byte_chr(MSG_USERAUTH_INFO_RESPONSE)
cMSG_GLOBAL_REQUEST = byte_chr(MSG_GLOBAL_REQUEST)
cMSG_REQUEST_SUCCESS = byte_chr(MSG_REQUEST_SUCCESS)
cMSG_REQUEST_FAILURE = byte_chr(MSG_REQUEST_FAILURE)
cMSG_CHANNEL_OPEN = byte_chr(MSG_CHANNEL_OPEN)
cMSG_CHANNEL_OPEN_SUCCESS = byte_chr(MSG_CHANNEL_OPEN_SUCCESS)
cMSG_CHANNEL_OPEN_FAILURE = byte_chr(MSG_CHANNEL_OPEN_FAILURE)
cMSG_CHANNEL_WINDOW_ADJUST = byte_chr(MSG_CHANNEL_WINDOW_ADJUST)
cMSG_CHANNEL_DATA = byte_chr(MSG_CHANNEL_DATA)
cMSG_CHANNEL_EXTENDED_DATA = byte_chr(MSG_CHANNEL_EXTENDED_DATA)
cMSG_CHANNEL_EOF = byte_chr(MSG_CHANNEL_EOF)
cMSG_CHANNEL_CLOSE = byte_chr(MSG_CHANNEL_CLOSE)
cMSG_CHANNEL_REQUEST = byte_chr(MSG_CHANNEL_REQUEST)
cMSG_CHANNEL_SUCCESS = byte_chr(MSG_CHANNEL_SUCCESS)
cMSG_CHANNEL_FAILURE = byte_chr(MSG_CHANNEL_FAILURE)

# for debugging:
MSG_NAMES = {
    MSG_DISCONNECT: 'disconnect',
    MSG_IGNORE: 'ignore',
    MSG_UNIMPLEMENTED: 'unimplemented',
    MSG_DEBUG: 'debug',
    MSG_SERVICE_REQUEST: 'service-request',
    MSG_SERVICE_ACCEPT: 'service-accept',
    MSG_KEXINIT: 'kexinit',
    MSG_NEWKEYS: 'newkeys',
    30: 'kex30',
    31: 'kex31',
    32: 'kex32',
    33: 'kex33',
    34: 'kex34',
    MSG_USERAUTH_REQUEST: 'userauth-request',
    MSG_USERAUTH_FAILURE: 'userauth-failure',
    MSG_USERAUTH_SUCCESS: 'userauth-success',
    MSG_USERAUTH_BANNER: 'userauth--banner',
    MSG_USERAUTH_PK_OK: 'userauth-60(pk-ok/info-request)',
    MSG_USERAUTH_INFO_RESPONSE: 'userauth-info-response',
    MSG_GLOBAL_REQUEST: 'global-request',
    MSG_REQUEST_SUCCESS: 'request-success',
    MSG_REQUEST_FAILURE: 'request-failure',
    MSG_CHANNEL_OPEN: 'channel-open',
    MSG_CHANNEL_OPEN_SUCCESS: 'channel-open-success',
    MSG_CHANNEL_OPEN_FAILURE: 'channel-open-failure',
    MSG_CHANNEL_WINDOW_ADJUST: 'channel-window-adjust',
    MSG_CHANNEL_DATA: 'channel-data',
    MSG_CHANNEL_EXTENDED_DATA: 'channel-extended-data',
    MSG_CHANNEL_EOF: 'channel-eof',
    MSG_CHANNEL_CLOSE: 'channel-close',
    MSG_CHANNEL_REQUEST: 'channel-request',
    MSG_CHANNEL_SUCCESS: 'channel-success',
    MSG_CHANNEL_FAILURE: 'channel-failure'
}


# authentication request return codes:
AUTH_SUCCESSFUL, AUTH_PARTIALLY_SUCCESSFUL, AUTH_FAILED = range(3)


# channel request failed reasons:
(OPEN_SUCCEEDED,
 OPEN_FAILED_ADMINISTRATIVELY_PROHIBITED,
 OPEN_FAILED_CONNECT_FAILED,
 OPEN_FAILED_UNKNOWN_CHANNEL_TYPE,
 OPEN_FAILED_RESOURCE_SHORTAGE) = range(0, 5)


CONNECTION_FAILED_CODE = {
    1: 'Administratively prohibited',
    2: 'Connect failed',
    3: 'Unknown channel type',
    4: 'Resource shortage'
}


DISCONNECT_SERVICE_NOT_AVAILABLE, DISCONNECT_AUTH_CANCELLED_BY_USER, \
    DISCONNECT_NO_MORE_AUTH_METHODS_AVAILABLE = 7, 13, 14

zero_byte = byte_chr(0)
one_byte = byte_chr(1)
four_byte = byte_chr(4)
max_byte = byte_chr(0xff)
cr_byte = byte_chr(13)
linefeed_byte = byte_chr(10)
crlf = cr_byte + linefeed_byte

if PY2:
    cr_byte_value = cr_byte
    linefeed_byte_value = linefeed_byte
else:
    cr_byte_value = 13
    linefeed_byte_value = 10


def asbytes(s):
    if not isinstance(s, bytes_types):
        if isinstance(s, string_types):
            s = b(s)
        else:
            try:
                s = s.asbytes()
            except Exception:
                raise Exception('Unknown type')
    return s

xffffffff = long(0xffffffff)
x80000000 = long(0x80000000)
o666 = 438
o660 = 432
o644 = 420
o600 = 384
o777 = 511
o700 = 448
o70 = 56

DEBUG = logging.DEBUG
INFO = logging.INFO
WARNING = logging.WARNING
ERROR = logging.ERROR
CRITICAL = logging.CRITICAL

# Common IO/select/etc sleep period, in seconds
io_sleep = 0.01

########NEW FILE########
__FILENAME__ = compress
# Copyright (C) 2003-2007  Robey Pointer <robeypointer@gmail.com>
#
# This file is part of paramiko.
#
# Paramiko is free software; you can redistribute it and/or modify it under the
# terms of the GNU Lesser General Public License as published by the Free
# Software Foundation; either version 2.1 of the License, or (at your option)
# any later version.
#
# Paramiko is distributed in the hope that it will be useful, but WITHOUT ANY
# WARRANTY; without even the implied warranty of MERCHANTABILITY or FITNESS FOR
# A PARTICULAR PURPOSE.  See the GNU Lesser General Public License for more
# details.
#
# You should have received a copy of the GNU Lesser General Public License
# along with Paramiko; if not, write to the Free Software Foundation, Inc.,
# 59 Temple Place, Suite 330, Boston, MA  02111-1307  USA.

"""
Compression implementations for a Transport.
"""

import zlib


class ZlibCompressor (object):
    def __init__(self):
        self.z = zlib.compressobj(9)

    def __call__(self, data):
        return self.z.compress(data) + self.z.flush(zlib.Z_FULL_FLUSH)


class ZlibDecompressor (object):
    def __init__(self):
        self.z = zlib.decompressobj()

    def __call__(self, data):
        return self.z.decompress(data)

########NEW FILE########
__FILENAME__ = config
# Copyright (C) 2006-2007  Robey Pointer <robeypointer@gmail.com>
# Copyright (C) 2012  Olle Lundberg <geek@nerd.sh>
#
# This file is part of paramiko.
#
# Paramiko is free software; you can redistribute it and/or modify it under the
# terms of the GNU Lesser General Public License as published by the Free
# Software Foundation; either version 2.1 of the License, or (at your option)
# any later version.
#
# Paramiko is distributed in the hope that it will be useful, but WITHOUT ANY
# WARRANTY; without even the implied warranty of MERCHANTABILITY or FITNESS FOR
# A PARTICULAR PURPOSE.  See the GNU Lesser General Public License for more
# details.
#
# You should have received a copy of the GNU Lesser General Public License
# along with Paramiko; if not, write to the Free Software Foundation, Inc.,
# 59 Temple Place, Suite 330, Boston, MA  02111-1307  USA.

"""
Configuration file (aka ``ssh_config``) support.
"""

import fnmatch
import os
import re
import socket

SSH_PORT = 22
proxy_re = re.compile(r"^(proxycommand)\s*=*\s*(.*)", re.I)


class SSHConfig (object):
    """
    Representation of config information as stored in the format used by
    OpenSSH. Queries can be made via `lookup`. The format is described in
    OpenSSH's ``ssh_config`` man page. This class is provided primarily as a
    convenience to posix users (since the OpenSSH format is a de-facto
    standard on posix) but should work fine on Windows too.

    .. versionadded:: 1.6
    """

    def __init__(self):
        """
        Create a new OpenSSH config object.
        """
        self._config = []

    def parse(self, file_obj):
        """
        Read an OpenSSH config from the given file object.

        :param file file_obj: a file-like object to read the config file from
        """
        host = {"host": ['*'], "config": {}}
        for line in file_obj:
            line = line.rstrip('\n').lstrip()
            if (line == '') or (line[0] == '#'):
                continue
            if '=' in line:
                # Ensure ProxyCommand gets properly split
                if line.lower().strip().startswith('proxycommand'):
                    match = proxy_re.match(line)
                    key, value = match.group(1).lower(), match.group(2)
                else:
                    key, value = line.split('=', 1)
                    key = key.strip().lower()
            else:
                # find first whitespace, and split there
                i = 0
                while (i < len(line)) and not line[i].isspace():
                    i += 1
                if i == len(line):
                    raise Exception('Unparsable line: %r' % line)
                key = line[:i].lower()
                value = line[i:].lstrip()

            if key == 'host':
                self._config.append(host)
                value = value.split()
                host = {key: value, 'config': {}}
            #identityfile, localforward, remoteforward keys are special cases, since they are allowed to be
            # specified multiple times and they should be tried in order
            # of specification.
            
            elif key in ['identityfile', 'localforward', 'remoteforward']:
                if key in host['config']:
                    host['config'][key].append(value)
                else:
                    host['config'][key] = [value]
            elif key not in host['config']:
                host['config'].update({key: value})
        self._config.append(host)

    def lookup(self, hostname):
        """
        Return a dict of config options for a given hostname.

        The host-matching rules of OpenSSH's ``ssh_config`` man page are used,
        which means that all configuration options from matching host
        specifications are merged, with more specific hostmasks taking
        precedence. In other words, if ``"Port"`` is set under ``"Host *"``
        and also ``"Host *.example.com"``, and the lookup is for
        ``"ssh.example.com"``, then the port entry for ``"Host *.example.com"``
        will win out.

        The keys in the returned dict are all normalized to lowercase (look for
        ``"port"``, not ``"Port"``. The values are processed according to the
        rules for substitution variable expansion in ``ssh_config``.

        :param str hostname: the hostname to lookup
        """
        matches = [config for config in self._config if
                   self._allowed(hostname, config['host'])]

        ret = {}
        for match in matches:
            for key, value in match['config'].items():
                if key not in ret:
                    # Create a copy of the original value,
                    # else it will reference the original list
                    # in self._config and update that value too
                    # when the extend() is being called.
                    ret[key] = value[:]
                elif key == 'identityfile':
                    ret[key].extend(value)
        ret = self._expand_variables(ret, hostname)
        return ret

    def _allowed(self, hostname, hosts):
        match = False
        for host in hosts:
            if host.startswith('!') and fnmatch.fnmatch(hostname, host[1:]):
                return False
            elif fnmatch.fnmatch(hostname, host):
                match = True
        return match

    def _expand_variables(self, config, hostname):
        """
        Return a dict of config options with expanded substitutions
        for a given hostname.

        Please refer to man ``ssh_config`` for the parameters that
        are replaced.

        :param dict config: the config for the hostname
        :param str hostname: the hostname that the config belongs to
        """

        if 'hostname' in config:
            config['hostname'] = config['hostname'].replace('%h', hostname)
        else:
            config['hostname'] = hostname

        if 'port' in config:
            port = config['port']
        else:
            port = SSH_PORT

        user = os.getenv('USER')
        if 'user' in config:
            remoteuser = config['user']
        else:
            remoteuser = user

        host = socket.gethostname().split('.')[0]
        fqdn = LazyFqdn(config, host)
        homedir = os.path.expanduser('~')
        replacements = {'controlpath':
                        [
                            ('%h', config['hostname']),
                            ('%l', fqdn),
                            ('%L', host),
                            ('%n', hostname),
                            ('%p', port),
                            ('%r', remoteuser),
                            ('%u', user)
                        ],
                        'identityfile':
                        [
                            ('~', homedir),
                            ('%d', homedir),
                            ('%h', config['hostname']),
                            ('%l', fqdn),
                            ('%u', user),
                            ('%r', remoteuser)
                        ],
                        'proxycommand':
                        [
                            ('%h', config['hostname']),
                            ('%p', port),
                            ('%r', remoteuser)
                        ]
                        }

        for k in config:
            if k in replacements:
                for find, replace in replacements[k]:
                    if isinstance(config[k], list):
                        for item in range(len(config[k])):
                            config[k][item] = config[k][item].\
                                replace(find, str(replace))
                    else:
                        config[k] = config[k].replace(find, str(replace))
        return config


class LazyFqdn(object):
    """
    Returns the host's fqdn on request as string.
    """

    def __init__(self, config, host=None):
        self.fqdn = None
        self.config = config
        self.host = host

    def __str__(self):
        if self.fqdn is None:
            #
            # If the SSH config contains AddressFamily, use that when
            # determining  the local host's FQDN. Using socket.getfqdn() from
            # the standard library is the most general solution, but can
            # result in noticeable delays on some platforms when IPv6 is
            # misconfigured or not available, as it calls getaddrinfo with no
            # address family specified, so both IPv4 and IPv6 are checked.
            #

            # Handle specific option
            fqdn = None
            address_family = self.config.get('addressfamily', 'any').lower()
            if address_family != 'any':
                try:
                    family = socket.AF_INET if address_family == 'inet' \
                        else socket.AF_INET6
                    results = socket.getaddrinfo(
                        self.host,
                        None,
                        family,
                        socket.SOCK_DGRAM,
                        socket.IPPROTO_IP,
                        socket.AI_CANONNAME
                    )
                    for res in results:
                        af, socktype, proto, canonname, sa = res
                        if canonname and '.' in canonname:
                            fqdn = canonname
                            break
                # giaerror -> socket.getaddrinfo() can't resolve self.host
                # (which is from socket.gethostname()). Fall back to the
                # getfqdn() call below.
                except socket.gaierror:
                    pass
            # Handle 'any' / unspecified
            if fqdn is None:
                fqdn = socket.getfqdn()
            # Cache
            self.fqdn = fqdn
        return self.fqdn

########NEW FILE########
__FILENAME__ = dsskey
# Copyright (C) 2003-2007  Robey Pointer <robeypointer@gmail.com>
#
# This file is part of paramiko.
#
# Paramiko is free software; you can redistribute it and/or modify it under the
# terms of the GNU Lesser General Public License as published by the Free
# Software Foundation; either version 2.1 of the License, or (at your option)
# any later version.
#
# Paramiko is distributed in the hope that it will be useful, but WITHOUT ANY
# WARRANTY; without even the implied warranty of MERCHANTABILITY or FITNESS FOR
# A PARTICULAR PURPOSE.  See the GNU Lesser General Public License for more
# details.
#
# You should have received a copy of the GNU Lesser General Public License
# along with Paramiko; if not, write to the Free Software Foundation, Inc.,
# 59 Temple Place, Suite 330, Boston, MA  02111-1307  USA.

"""
DSS keys.
"""

import os
from hashlib import sha1

from Crypto.PublicKey import DSA

from paramiko import util
from paramiko.common import zero_byte
from paramiko.py3compat import long
from paramiko.ssh_exception import SSHException
from paramiko.message import Message
from paramiko.ber import BER, BERException
from paramiko.pkey import PKey


class DSSKey (PKey):
    """
    Representation of a DSS key which can be used to sign an verify SSH2
    data.
    """

    def __init__(self, msg=None, data=None, filename=None, password=None, vals=None, file_obj=None):
        self.p = None
        self.q = None
        self.g = None
        self.y = None
        self.x = None
        if file_obj is not None:
            self._from_private_key(file_obj, password)
            return
        if filename is not None:
            self._from_private_key_file(filename, password)
            return
        if (msg is None) and (data is not None):
            msg = Message(data)
        if vals is not None:
            self.p, self.q, self.g, self.y = vals
        else:
            if msg is None:
                raise SSHException('Key object may not be empty')
            if msg.get_text() != 'ssh-dss':
                raise SSHException('Invalid key')
            self.p = msg.get_mpint()
            self.q = msg.get_mpint()
            self.g = msg.get_mpint()
            self.y = msg.get_mpint()
        self.size = util.bit_length(self.p)

    def asbytes(self):
        m = Message()
        m.add_string('ssh-dss')
        m.add_mpint(self.p)
        m.add_mpint(self.q)
        m.add_mpint(self.g)
        m.add_mpint(self.y)
        return m.asbytes()

    def __str__(self):
        return self.asbytes()

    def __hash__(self):
        h = hash(self.get_name())
        h = h * 37 + hash(self.p)
        h = h * 37 + hash(self.q)
        h = h * 37 + hash(self.g)
        h = h * 37 + hash(self.y)
        # h might be a long by now...
        return hash(h)

    def get_name(self):
        return 'ssh-dss'

    def get_bits(self):
        return self.size

    def can_sign(self):
        return self.x is not None

    def sign_ssh_data(self, data):
        digest = sha1(data).digest()
        dss = DSA.construct((long(self.y), long(self.g), long(self.p), long(self.q), long(self.x)))
        # generate a suitable k
        qsize = len(util.deflate_long(self.q, 0))
        while True:
            k = util.inflate_long(os.urandom(qsize), 1)
            if (k > 2) and (k < self.q):
                break
        r, s = dss.sign(util.inflate_long(digest, 1), k)
        m = Message()
        m.add_string('ssh-dss')
        # apparently, in rare cases, r or s may be shorter than 20 bytes!
        rstr = util.deflate_long(r, 0)
        sstr = util.deflate_long(s, 0)
        if len(rstr) < 20:
            rstr = zero_byte * (20 - len(rstr)) + rstr
        if len(sstr) < 20:
            sstr = zero_byte * (20 - len(sstr)) + sstr
        m.add_string(rstr + sstr)
        return m

    def verify_ssh_sig(self, data, msg):
        if len(msg.asbytes()) == 40:
            # spies.com bug: signature has no header
            sig = msg.asbytes()
        else:
            kind = msg.get_text()
            if kind != 'ssh-dss':
                return 0
            sig = msg.get_binary()

        # pull out (r, s) which are NOT encoded as mpints
        sigR = util.inflate_long(sig[:20], 1)
        sigS = util.inflate_long(sig[20:], 1)
        sigM = util.inflate_long(sha1(data).digest(), 1)

        dss = DSA.construct((long(self.y), long(self.g), long(self.p), long(self.q)))
        return dss.verify(sigM, (sigR, sigS))

    def _encode_key(self):
        if self.x is None:
            raise SSHException('Not enough key information')
        keylist = [0, self.p, self.q, self.g, self.y, self.x]
        try:
            b = BER()
            b.encode(keylist)
        except BERException:
            raise SSHException('Unable to create ber encoding of key')
        return b.asbytes()

    def write_private_key_file(self, filename, password=None):
        self._write_private_key_file('DSA', filename, self._encode_key(), password)

    def write_private_key(self, file_obj, password=None):
        self._write_private_key('DSA', file_obj, self._encode_key(), password)

    def generate(bits=1024, progress_func=None):
        """
        Generate a new private DSS key.  This factory function can be used to
        generate a new host key or authentication key.

        :param int bits: number of bits the generated key should be.
        :param function progress_func:
            an optional function to call at key points in key generation (used
            by ``pyCrypto.PublicKey``).
        :return: new `.DSSKey` private key
        """
        dsa = DSA.generate(bits, os.urandom, progress_func)
        key = DSSKey(vals=(dsa.p, dsa.q, dsa.g, dsa.y))
        key.x = dsa.x
        return key
    generate = staticmethod(generate)

    ###  internals...

    def _from_private_key_file(self, filename, password):
        data = self._read_private_key_file('DSA', filename, password)
        self._decode_key(data)

    def _from_private_key(self, file_obj, password):
        data = self._read_private_key('DSA', file_obj, password)
        self._decode_key(data)

    def _decode_key(self, data):
        # private key file contains:
        # DSAPrivateKey = { version = 0, p, q, g, y, x }
        try:
            keylist = BER(data).decode()
        except BERException as e:
            raise SSHException('Unable to parse key file: ' + str(e))
        if (type(keylist) is not list) or (len(keylist) < 6) or (keylist[0] != 0):
            raise SSHException('not a valid DSA private key file (bad ber encoding)')
        self.p = keylist[1]
        self.q = keylist[2]
        self.g = keylist[3]
        self.y = keylist[4]
        self.x = keylist[5]
        self.size = util.bit_length(self.p)

########NEW FILE########
__FILENAME__ = ecdsakey
# Copyright (C) 2003-2007  Robey Pointer <robeypointer@gmail.com>
#
# This file is part of paramiko.
#
# Paramiko is free software; you can redistribute it and/or modify it under the
# terms of the GNU Lesser General Public License as published by the Free
# Software Foundation; either version 2.1 of the License, or (at your option)
# any later version.
#
# Paramiko is distrubuted in the hope that it will be useful, but WITHOUT ANY
# WARRANTY; without even the implied warranty of MERCHANTABILITY or FITNESS FOR
# A PARTICULAR PURPOSE.  See the GNU Lesser General Public License for more
# details.
#
# You should have received a copy of the GNU Lesser General Public License
# along with Paramiko; if not, write to the Free Software Foundation, Inc.,
# 59 Temple Place, Suite 330, Boston, MA  02111-1307  USA.

"""
L{ECDSAKey}
"""

import binascii
from hashlib import sha256

from ecdsa import SigningKey, VerifyingKey, der, curves
from ecdsa.test_pyecdsa import ECDSA

from paramiko.common import four_byte, one_byte
from paramiko.message import Message
from paramiko.pkey import PKey
from paramiko.py3compat import byte_chr, u
from paramiko.ssh_exception import SSHException


class ECDSAKey (PKey):
    """
    Representation of an ECDSA key which can be used to sign and verify SSH2
    data.
    """

    def __init__(self, msg=None, data=None, filename=None, password=None, vals=None, file_obj=None):
        self.verifying_key = None
        self.signing_key = None
        if file_obj is not None:
            self._from_private_key(file_obj, password)
            return
        if filename is not None:
            self._from_private_key_file(filename, password)
            return
        if (msg is None) and (data is not None):
            msg = Message(data)
        if vals is not None:
            self.verifying_key, self.signing_key = vals
        else:
            if msg is None:
                raise SSHException('Key object may not be empty')
            if msg.get_text() != 'ecdsa-sha2-nistp256':
                raise SSHException('Invalid key')
            curvename = msg.get_text()
            if curvename != 'nistp256':
                raise SSHException("Can't handle curve of type %s" % curvename)

            pointinfo = msg.get_binary()
            if pointinfo[0:1] != four_byte:
                raise SSHException('Point compression is being used: %s' %
                                   binascii.hexlify(pointinfo))
            self.verifying_key = VerifyingKey.from_string(pointinfo[1:],
                                                          curve=curves.NIST256p)
        self.size = 256

    def asbytes(self):
        key = self.verifying_key
        m = Message()
        m.add_string('ecdsa-sha2-nistp256')
        m.add_string('nistp256')

        point_str = four_byte + key.to_string()

        m.add_string(point_str)
        return m.asbytes()

    def __str__(self):
        return self.asbytes()

    def __hash__(self):
        h = hash(self.get_name())
        h = h * 37 + hash(self.verifying_key.pubkey.point.x())
        h = h * 37 + hash(self.verifying_key.pubkey.point.y())
        return hash(h)

    def get_name(self):
        return 'ecdsa-sha2-nistp256'

    def get_bits(self):
        return self.size

    def can_sign(self):
        return self.signing_key is not None

    def sign_ssh_data(self, data):
        sig = self.signing_key.sign_deterministic(
            data, sigencode=self._sigencode, hashfunc=sha256)
        m = Message()
        m.add_string('ecdsa-sha2-nistp256')
        m.add_string(sig)
        return m

    def verify_ssh_sig(self, data, msg):
        if msg.get_text() != 'ecdsa-sha2-nistp256':
            return False
        sig = msg.get_binary()

        # verify the signature by SHA'ing the data and encrypting it
        # using the public key.
        hash_obj = sha256(data).digest()
        return self.verifying_key.verify_digest(sig, hash_obj,
                                                sigdecode=self._sigdecode)

    def write_private_key_file(self, filename, password=None):
        key = self.signing_key or self.verifying_key
        self._write_private_key_file('EC', filename, key.to_der(), password)

    def write_private_key(self, file_obj, password=None):
        key = self.signing_key or self.verifying_key
        self._write_private_key('EC', file_obj, key.to_der(), password)

    def generate(bits, progress_func=None):
        """
        Generate a new private RSA key.  This factory function can be used to
        generate a new host key or authentication key.

        @param bits: number of bits the generated key should be.
        @type bits: int
        @param progress_func: an optional function to call at key points in
            key generation (used by C{pyCrypto.PublicKey}).
        @type progress_func: function
        @return: new private key
        @rtype: L{RSAKey}
        """
        signing_key = ECDSA.generate()
        key = ECDSAKey(vals=(signing_key, signing_key.get_verifying_key()))
        return key
    generate = staticmethod(generate)

    ###  internals...

    def _from_private_key_file(self, filename, password):
        data = self._read_private_key_file('EC', filename, password)
        self._decode_key(data)

    def _from_private_key(self, file_obj, password):
        data = self._read_private_key('EC', file_obj, password)
        self._decode_key(data)

    ALLOWED_PADDINGS = [one_byte, byte_chr(2) * 2, byte_chr(3) * 3, byte_chr(4) * 4,
                        byte_chr(5) * 5, byte_chr(6) * 6, byte_chr(7) * 7]

    def _decode_key(self, data):
        s, padding = der.remove_sequence(data)
        if padding:
            if padding not in self.ALLOWED_PADDINGS:
                raise ValueError("weird padding: %s" % u(binascii.hexlify(data)))
            data = data[:-len(padding)]
        key = SigningKey.from_der(data)
        self.signing_key = key
        self.verifying_key = key.get_verifying_key()
        self.size = 256

    def _sigencode(self, r, s, order):
        msg = Message()
        msg.add_mpint(r)
        msg.add_mpint(s)
        return msg.asbytes()

    def _sigdecode(self, sig, order):
        msg = Message(sig)
        r = msg.get_mpint()
        s = msg.get_mpint()
        return r, s

########NEW FILE########
__FILENAME__ = file
# Copyright (C) 2003-2007  Robey Pointer <robeypointer@gmail.com>
#
# This file is part of paramiko.
#
# Paramiko is free software; you can redistribute it and/or modify it under the
# terms of the GNU Lesser General Public License as published by the Free
# Software Foundation; either version 2.1 of the License, or (at your option)
# any later version.
#
# Paramiko is distributed in the hope that it will be useful, but WITHOUT ANY
# WARRANTY; without even the implied warranty of MERCHANTABILITY or FITNESS FOR
# A PARTICULAR PURPOSE.  See the GNU Lesser General Public License for more
# details.
#
# You should have received a copy of the GNU Lesser General Public License
# along with Paramiko; if not, write to the Free Software Foundation, Inc.,
# 59 Temple Place, Suite 330, Boston, MA  02111-1307  USA.
from paramiko.common import linefeed_byte_value, crlf, cr_byte, linefeed_byte, \
    cr_byte_value
from paramiko.py3compat import BytesIO, PY2, u, b, bytes_types


class BufferedFile (object):
    """
    Reusable base class to implement Python-style file buffering around a
    simpler stream.
    """

    _DEFAULT_BUFSIZE = 8192

    SEEK_SET = 0
    SEEK_CUR = 1
    SEEK_END = 2

    FLAG_READ = 0x1
    FLAG_WRITE = 0x2
    FLAG_APPEND = 0x4
    FLAG_BINARY = 0x10
    FLAG_BUFFERED = 0x20
    FLAG_LINE_BUFFERED = 0x40
    FLAG_UNIVERSAL_NEWLINE = 0x80

    def __init__(self):
        self.newlines = None
        self._flags = 0
        self._bufsize = self._DEFAULT_BUFSIZE
        self._wbuffer = BytesIO()
        self._rbuffer = bytes()
        self._at_trailing_cr = False
        self._closed = False
        # pos - position within the file, according to the user
        # realpos - position according the OS
        # (these may be different because we buffer for line reading)
        self._pos = self._realpos = 0
        # size only matters for seekable files
        self._size = 0

    def __del__(self):
        self.close()
        
    def __iter__(self):
        """
        Returns an iterator that can be used to iterate over the lines in this
        file.  This iterator happens to return the file itself, since a file is
        its own iterator.

        :raises ValueError: if the file is closed.
        """
        if self._closed:
            raise ValueError('I/O operation on closed file')
        return self

    def close(self):
        """
        Close the file.  Future read and write operations will fail.
        """
        self.flush()
        self._closed = True

    def flush(self):
        """
        Write out any data in the write buffer.  This may do nothing if write
        buffering is not turned on.
        """
        self._write_all(self._wbuffer.getvalue())
        self._wbuffer = BytesIO()
        return

    if PY2:
        def next(self):
            """
            Returns the next line from the input, or raises
            `~exceptions.StopIteration` when EOF is hit.  Unlike Python file
            objects, it's okay to mix calls to `next` and `readline`.

            :raises StopIteration: when the end of the file is reached.

            :return: a line (`str`) read from the file.
            """
            line = self.readline()
            if not line:
                raise StopIteration
            return line
    else:
        def __next__(self):
            """
            Returns the next line from the input, or raises L{StopIteration} when
            EOF is hit.  Unlike python file objects, it's okay to mix calls to
            C{next} and L{readline}.

            @raise StopIteration: when the end of the file is reached.

            @return: a line read from the file.
            @rtype: str
            """
            line = self.readline()
            if not line:
                raise StopIteration
            return line

    def read(self, size=None):
        """
        Read at most ``size`` bytes from the file (less if we hit the end of the
        file first).  If the ``size`` argument is negative or omitted, read all
        the remaining data in the file.

        .. note::
            ``'b'`` mode flag is ignored (``self.FLAG_BINARY`` in
            ``self._flags``), because SSH treats all files as binary, since we
            have no idea what encoding the file is in, or even if the file is
            text data.

        :param int size: maximum number of bytes to read
        :return:
            data read from the file (as bytes), or an empty string if EOF was
            encountered immediately
        """
        if self._closed:
            raise IOError('File is closed')
        if not (self._flags & self.FLAG_READ):
            raise IOError('File is not open for reading')
        if (size is None) or (size < 0):
            # go for broke
            result = self._rbuffer
            self._rbuffer = bytes()
            self._pos += len(result)
            while True:
                try:
                    new_data = self._read(self._DEFAULT_BUFSIZE)
                except EOFError:
                    new_data = None
                if (new_data is None) or (len(new_data) == 0):
                    break
                result += new_data
                self._realpos += len(new_data)
                self._pos += len(new_data)
            return result 
        if size <= len(self._rbuffer):
            result = self._rbuffer[:size]
            self._rbuffer = self._rbuffer[size:]
            self._pos += len(result)
            return result 
        while len(self._rbuffer) < size:
            read_size = size - len(self._rbuffer)
            if self._flags & self.FLAG_BUFFERED:
                read_size = max(self._bufsize, read_size)
            try:
                new_data = self._read(read_size)
            except EOFError:
                new_data = None
            if (new_data is None) or (len(new_data) == 0):
                break
            self._rbuffer += new_data
            self._realpos += len(new_data)
        result = self._rbuffer[:size]
        self._rbuffer = self._rbuffer[size:]
        self._pos += len(result)
        return result 

    def readline(self, size=None):
        """
        Read one entire line from the file.  A trailing newline character is
        kept in the string (but may be absent when a file ends with an
        incomplete line).  If the size argument is present and non-negative, it
        is a maximum byte count (including the trailing newline) and an
        incomplete line may be returned.  An empty string is returned only when
        EOF is encountered immediately.

        .. note::
            Unlike stdio's ``fgets``, the returned string contains null
            characters (``'\\0'``) if they occurred in the input.

        :param int size: maximum length of returned string.
        :return:
            next line of the file, or an empty string if the end of the
            file has been reached.

            If the file was opened in binary (``'b'``) mode: bytes are returned
            Else: the encoding of the file is assumed to be UTF-8 and character
            strings (`str`) are returned
        """
        # it's almost silly how complex this function is.
        if self._closed:
            raise IOError('File is closed')
        if not (self._flags & self.FLAG_READ):
            raise IOError('File not open for reading')
        line = self._rbuffer
        while True:
            if self._at_trailing_cr and (self._flags & self.FLAG_UNIVERSAL_NEWLINE) and (len(line) > 0):
                # edge case: the newline may be '\r\n' and we may have read
                # only the first '\r' last time.
                if line[0] == linefeed_byte_value:
                    line = line[1:]
                    self._record_newline(crlf)
                else:
                    self._record_newline(cr_byte)
                self._at_trailing_cr = False
            # check size before looking for a linefeed, in case we already have
            # enough.
            if (size is not None) and (size >= 0):
                if len(line) >= size:
                    # truncate line and return
                    self._rbuffer = line[size:]
                    line = line[:size]
                    self._pos += len(line)
                    return line if self._flags & self.FLAG_BINARY else u(line)
                n = size - len(line)
            else:
                n = self._bufsize
            if (linefeed_byte in line) or ((self._flags & self.FLAG_UNIVERSAL_NEWLINE) and (cr_byte in line)):
                break
            try:
                new_data = self._read(n)
            except EOFError:
                new_data = None
            if (new_data is None) or (len(new_data) == 0):
                self._rbuffer = bytes()
                self._pos += len(line)
                return line if self._flags & self.FLAG_BINARY else u(line)
            line += new_data
            self._realpos += len(new_data)
        # find the newline
        pos = line.find(linefeed_byte)
        if self._flags & self.FLAG_UNIVERSAL_NEWLINE:
            rpos = line.find(cr_byte)
            if (rpos >= 0) and (rpos < pos or pos < 0):
                pos = rpos
        xpos = pos + 1
        if (line[pos] == cr_byte_value) and (xpos < len(line)) and (line[xpos] == linefeed_byte_value):
            xpos += 1
        self._rbuffer = line[xpos:]
        lf = line[pos:xpos]
        line = line[:pos] + linefeed_byte
        if (len(self._rbuffer) == 0) and (lf == cr_byte):
            # we could read the line up to a '\r' and there could still be a
            # '\n' following that we read next time.  note that and eat it.
            self._at_trailing_cr = True
        else:
            self._record_newline(lf)
        self._pos += len(line)
        return line if self._flags & self.FLAG_BINARY else u(line)

    def readlines(self, sizehint=None):
        """
        Read all remaining lines using `readline` and return them as a list.
        If the optional ``sizehint`` argument is present, instead of reading up
        to EOF, whole lines totalling approximately sizehint bytes (possibly
        after rounding up to an internal buffer size) are read.

        :param int sizehint: desired maximum number of bytes to read.
        :return: `list` of lines read from the file.
        """
        lines = []
        byte_count = 0
        while True:
            line = self.readline()
            if len(line) == 0:
                break
            lines.append(line)
            byte_count += len(line)
            if (sizehint is not None) and (byte_count >= sizehint):
                break
        return lines

    def seek(self, offset, whence=0):
        """
        Set the file's current position, like stdio's ``fseek``.  Not all file
        objects support seeking.

        .. note::
            If a file is opened in append mode (``'a'`` or ``'a+'``), any seek
            operations will be undone at the next write (as the file position
            will move back to the end of the file).
        
        :param int offset:
            position to move to within the file, relative to ``whence``.
        :param int whence:
            type of movement: 0 = absolute; 1 = relative to the current
            position; 2 = relative to the end of the file.

        :raises IOError: if the file doesn't support random access.
        """
        raise IOError('File does not support seeking.')

    def tell(self):
        """
        Return the file's current position.  This may not be accurate or
        useful if the underlying file doesn't support random access, or was
        opened in append mode.

        :return: file position (`number <int>` of bytes).
        """
        return self._pos

    def write(self, data):
        """
        Write data to the file.  If write buffering is on (``bufsize`` was
        specified and non-zero), some or all of the data may not actually be
        written yet.  (Use `flush` or `close` to force buffered data to be
        written out.)

        :param str data: data to write
        """
        data = b(data)
        if self._closed:
            raise IOError('File is closed')
        if not (self._flags & self.FLAG_WRITE):
            raise IOError('File not open for writing')
        if not (self._flags & self.FLAG_BUFFERED):
            self._write_all(data)
            return
        self._wbuffer.write(data)
        if self._flags & self.FLAG_LINE_BUFFERED:
            # only scan the new data for linefeed, to avoid wasting time.
            last_newline_pos = data.rfind(linefeed_byte)
            if last_newline_pos >= 0:
                wbuf = self._wbuffer.getvalue()
                last_newline_pos += len(wbuf) - len(data)
                self._write_all(wbuf[:last_newline_pos + 1])
                self._wbuffer = BytesIO()
                self._wbuffer.write(wbuf[last_newline_pos + 1:])
            return
        # even if we're line buffering, if the buffer has grown past the
        # buffer size, force a flush.
        if self._wbuffer.tell() >= self._bufsize:
            self.flush()
        return

    def writelines(self, sequence):
        """
        Write a sequence of strings to the file.  The sequence can be any
        iterable object producing strings, typically a list of strings.  (The
        name is intended to match `readlines`; `writelines` does not add line
        separators.)

        :param iterable sequence: an iterable sequence of strings.
        """
        for line in sequence:
            self.write(line)
        return

    def xreadlines(self):
        """
        Identical to ``iter(f)``.  This is a deprecated file interface that
        predates Python iterator support.
        """
        return self

    @property
    def closed(self):
        return self._closed

    ###  overrides...

    def _read(self, size):
        """
        (subclass override)
        Read data from the stream.  Return ``None`` or raise ``EOFError`` to
        indicate EOF.
        """
        raise EOFError()

    def _write(self, data):
        """
        (subclass override)
        Write data into the stream.
        """
        raise IOError('write not implemented')

    def _get_size(self):
        """
        (subclass override)
        Return the size of the file.  This is called from within `_set_mode`
        if the file is opened in append mode, so the file position can be
        tracked and `seek` and `tell` will work correctly.  If the file is
        a stream that can't be randomly accessed, you don't need to override
        this method,
        """
        return 0

    ###  internals...

    def _set_mode(self, mode='r', bufsize=-1):
        """
        Subclasses call this method to initialize the BufferedFile.
        """
        # set bufsize in any event, because it's used for readline().
        self._bufsize = self._DEFAULT_BUFSIZE
        if bufsize < 0:
            # do no buffering by default, because otherwise writes will get
            # buffered in a way that will probably confuse people.
            bufsize = 0
        if bufsize == 1:
            # apparently, line buffering only affects writes.  reads are only
            # buffered if you call readline (directly or indirectly: iterating
            # over a file will indirectly call readline).
            self._flags |= self.FLAG_BUFFERED | self.FLAG_LINE_BUFFERED
        elif bufsize > 1:
            self._bufsize = bufsize
            self._flags |= self.FLAG_BUFFERED
            self._flags &= ~self.FLAG_LINE_BUFFERED
        elif bufsize == 0:
            # unbuffered
            self._flags &= ~(self.FLAG_BUFFERED | self.FLAG_LINE_BUFFERED)

        if ('r' in mode) or ('+' in mode):
            self._flags |= self.FLAG_READ
        if ('w' in mode) or ('+' in mode):
            self._flags |= self.FLAG_WRITE
        if 'a' in mode:
            self._flags |= self.FLAG_WRITE | self.FLAG_APPEND
            self._size = self._get_size()
            self._pos = self._realpos = self._size
        if 'b' in mode:
            self._flags |= self.FLAG_BINARY
        if 'U' in mode:
            self._flags |= self.FLAG_UNIVERSAL_NEWLINE
            # built-in file objects have this attribute to store which kinds of
            # line terminations they've seen:
            # <http://www.python.org/doc/current/lib/built-in-funcs.html>
            self.newlines = None

    def _write_all(self, data):
        # the underlying stream may be something that does partial writes (like
        # a socket).
        while len(data) > 0:
            count = self._write(data)
            data = data[count:]
            if self._flags & self.FLAG_APPEND:
                self._size += count
                self._pos = self._realpos = self._size
            else:
                self._pos += count
                self._realpos += count
        return None

    def _record_newline(self, newline):
        # silliness about tracking what kinds of newlines we've seen.
        # i don't understand why it can be None, a string, or a tuple, instead
        # of just always being a tuple, but we'll emulate that behavior anyway.
        if not (self._flags & self.FLAG_UNIVERSAL_NEWLINE):
            return
        if self.newlines is None:
            self.newlines = newline
        elif self.newlines != newline and isinstance(self.newlines, bytes_types):
            self.newlines = (self.newlines, newline)
        elif newline not in self.newlines:
            self.newlines += (newline,)

########NEW FILE########
__FILENAME__ = hostkeys
# Copyright (C) 2006-2007  Robey Pointer <robeypointer@gmail.com>
#
# This file is part of paramiko.
#
# Paramiko is free software; you can redistribute it and/or modify it under the
# terms of the GNU Lesser General Public License as published by the Free
# Software Foundation; either version 2.1 of the License, or (at your option)
# any later version.
#
# Paramiko is distributed in the hope that it will be useful, but WITHOUT ANY
# WARRANTY; without even the implied warranty of MERCHANTABILITY or FITNESS FOR
# A PARTICULAR PURPOSE.  See the GNU Lesser General Public License for more
# details.
#
# You should have received a copy of the GNU Lesser General Public License
# along with Paramiko; if not, write to the Free Software Foundation, Inc.,
# 59 Temple Place, Suite 330, Boston, MA  02111-1307  USA.


import binascii
import os

from hashlib import sha1
from hmac import HMAC

from paramiko.py3compat import b, u, encodebytes, decodebytes

try:
    from collections import MutableMapping
except ImportError:
    # noinspection PyUnresolvedReferences
    from UserDict import DictMixin as MutableMapping

from paramiko.dsskey import DSSKey
from paramiko.rsakey import RSAKey
from paramiko.util import get_logger, constant_time_bytes_eq
from paramiko.ecdsakey import ECDSAKey


class HostKeys (MutableMapping):
    """
    Representation of an OpenSSH-style "known hosts" file.  Host keys can be
    read from one or more files, and then individual hosts can be looked up to
    verify server keys during SSH negotiation.

    A `.HostKeys` object can be treated like a dict; any dict lookup is
    equivalent to calling `lookup`.

    .. versionadded:: 1.5.3
    """

    def __init__(self, filename=None):
        """
        Create a new HostKeys object, optionally loading keys from an OpenSSH
        style host-key file.

        :param str filename: filename to load host keys from, or ``None``
        """
        # emulate a dict of { hostname: { keytype: PKey } }
        self._entries = []
        if filename is not None:
            self.load(filename)

    def add(self, hostname, keytype, key):
        """
        Add a host key entry to the table.  Any existing entry for a
        ``(hostname, keytype)`` pair will be replaced.

        :param str hostname: the hostname (or IP) to add
        :param str keytype: key type (``"ssh-rsa"`` or ``"ssh-dss"``)
        :param .PKey key: the key to add
        """
        for e in self._entries:
            if (hostname in e.hostnames) and (e.key.get_name() == keytype):
                e.key = key
                return
        self._entries.append(HostKeyEntry([hostname], key))

    def load(self, filename):
        """
        Read a file of known SSH host keys, in the format used by OpenSSH.
        This type of file unfortunately doesn't exist on Windows, but on
        posix, it will usually be stored in
        ``os.path.expanduser("~/.ssh/known_hosts")``.

        If this method is called multiple times, the host keys are merged,
        not cleared.  So multiple calls to `load` will just call `add`,
        replacing any existing entries and adding new ones.

        :param str filename: name of the file to read host keys from

        :raises IOError: if there was an error reading the file
        """
        with open(filename, 'r') as f:
            for lineno, line in enumerate(f):
                line = line.strip()
                if (len(line) == 0) or (line[0] == '#'):
                    continue
                e = HostKeyEntry.from_line(line, lineno)
                if e is not None:
                    _hostnames = e.hostnames
                    for h in _hostnames:
                        if self.check(h, e.key):
                            e.hostnames.remove(h)
                    if len(e.hostnames):
                        self._entries.append(e)

    def save(self, filename):
        """
        Save host keys into a file, in the format used by OpenSSH.  The order of
        keys in the file will be preserved when possible (if these keys were
        loaded from a file originally).  The single exception is that combined
        lines will be split into individual key lines, which is arguably a bug.

        :param str filename: name of the file to write

        :raises IOError: if there was an error writing the file

        .. versionadded:: 1.6.1
        """
        with open(filename, 'w') as f:
            for e in self._entries:
                line = e.to_line()
                if line:
                    f.write(line)

    def lookup(self, hostname):
        """
        Find a hostkey entry for a given hostname or IP.  If no entry is found,
        ``None`` is returned.  Otherwise a dictionary of keytype to key is
        returned.  The keytype will be either ``"ssh-rsa"`` or ``"ssh-dss"``.

        :param str hostname: the hostname (or IP) to lookup
        :return: dict of `str` -> `.PKey` keys associated with this host (or ``None``)
        """
        class SubDict (MutableMapping):
            def __init__(self, hostname, entries, hostkeys):
                self._hostname = hostname
                self._entries = entries
                self._hostkeys = hostkeys

            def __iter__(self):
                for k in self.keys():
                    yield k

            def __len__(self):
                return len(self.keys())

            def __delitem__(self, key):
                for e in list(self._entries):
                    if e.key.get_name() == key:
                        self._entries.remove(e)
                else:
                    raise KeyError(key)

            def __getitem__(self, key):
                for e in self._entries:
                    if e.key.get_name() == key:
                        return e.key
                raise KeyError(key)

            def __setitem__(self, key, val):
                for e in self._entries:
                    if e.key is None:
                        continue
                    if e.key.get_name() == key:
                        # replace
                        e.key = val
                        break
                else:
                    # add a new one
                    e = HostKeyEntry([hostname], val)
                    self._entries.append(e)
                    self._hostkeys._entries.append(e)

            def keys(self):
                return [e.key.get_name() for e in self._entries if e.key is not None]

        entries = []
        for e in self._entries:
            for h in e.hostnames:
                if h.startswith('|1|') and constant_time_bytes_eq(self.hash_host(hostname, h), h) or h == hostname:
                    entries.append(e)
        if len(entries) == 0:
            return None
        return SubDict(hostname, entries, self)

    def check(self, hostname, key):
        """
        Return True if the given key is associated with the given hostname
        in this dictionary.

        :param str hostname: hostname (or IP) of the SSH server
        :param .PKey key: the key to check
        :return:
            ``True`` if the key is associated with the hostname; else ``False``
        """
        k = self.lookup(hostname)
        if k is None:
            return False
        host_key = k.get(key.get_name(), None)
        if host_key is None:
            return False
        return host_key.asbytes() == key.asbytes()

    def clear(self):
        """
        Remove all host keys from the dictionary.
        """
        self._entries = []

    def __iter__(self):
        for k in self.keys():
            yield k

    def __len__(self):
        return len(self.keys())

    def __delitem__(self, key):
        k = self[key]

    def __getitem__(self, key):
        ret = self.lookup(key)
        if ret is None:
            raise KeyError(key)
        return ret

    def __setitem__(self, hostname, entry):
        # don't use this please.
        if len(entry) == 0:
            self._entries.append(HostKeyEntry([hostname], None))
            return
        for key_type in entry.keys():
            found = False
            for e in self._entries:
                if (hostname in e.hostnames) and (e.key.get_name() == key_type):
                    # replace
                    e.key = entry[key_type]
                    found = True
            if not found:
                self._entries.append(HostKeyEntry([hostname], entry[key_type]))

    def keys(self):
        # Python 2.4 sets would be nice here.
        ret = []
        for e in self._entries:
            for h in e.hostnames:
                if h not in ret:
                    ret.append(h)
        return ret

    def values(self):
        ret = []
        for k in self.keys():
            ret.append(self.lookup(k))
        return ret

    def hash_host(hostname, salt=None):
        """
        Return a "hashed" form of the hostname, as used by OpenSSH when storing
        hashed hostnames in the known_hosts file.

        :param str hostname: the hostname to hash
        :param str salt: optional salt to use when hashing (must be 20 bytes long)
        :return: the hashed hostname as a `str`
        """
        if salt is None:
            salt = os.urandom(sha1().digest_size)
        else:
            if salt.startswith('|1|'):
                salt = salt.split('|')[2]
            salt = decodebytes(b(salt))
        assert len(salt) == sha1().digest_size
        hmac = HMAC(salt, b(hostname), sha1).digest()
        hostkey = '|1|%s|%s' % (u(encodebytes(salt)), u(encodebytes(hmac)))
        return hostkey.replace('\n', '')
    hash_host = staticmethod(hash_host)


class InvalidHostKey(Exception):
    def __init__(self, line, exc):
        self.line = line
        self.exc = exc
        self.args = (line, exc)


class HostKeyEntry:
    """
    Representation of a line in an OpenSSH-style "known hosts" file.
    """

    def __init__(self, hostnames=None, key=None):
        self.valid = (hostnames is not None) and (key is not None)
        self.hostnames = hostnames
        self.key = key

    def from_line(cls, line, lineno=None):
        """
        Parses the given line of text to find the names for the host,
        the type of key, and the key data. The line is expected to be in the
        format used by the OpenSSH known_hosts file.

        Lines are expected to not have leading or trailing whitespace.
        We don't bother to check for comments or empty lines.  All of
        that should be taken care of before sending the line to us.

        :param str line: a line from an OpenSSH known_hosts file
        """
        log = get_logger('paramiko.hostkeys')
        fields = line.split(' ')
        if len(fields) < 3:
            # Bad number of fields
            log.info("Not enough fields found in known_hosts in line %s (%r)" %
                     (lineno, line))
            return None
        fields = fields[:3]

        names, keytype, key = fields
        names = names.split(',')

        # Decide what kind of key we're looking at and create an object
        # to hold it accordingly.
        try:
            key = b(key)
            if keytype == 'ssh-rsa':
                key = RSAKey(data=decodebytes(key))
            elif keytype == 'ssh-dss':
                key = DSSKey(data=decodebytes(key))
            elif keytype == 'ecdsa-sha2-nistp256':
                key = ECDSAKey(data=decodebytes(key))
            else:
                log.info("Unable to handle key of type %s" % (keytype,))
                return None

        except binascii.Error as e:
            raise InvalidHostKey(line, e)

        return cls(names, key)
    from_line = classmethod(from_line)

    def to_line(self):
        """
        Returns a string in OpenSSH known_hosts file format, or None if
        the object is not in a valid state.  A trailing newline is
        included.
        """
        if self.valid:
            return '%s %s %s\n' % (','.join(self.hostnames), self.key.get_name(),
                   self.key.get_base64())
        return None

    def __repr__(self):
        return '<HostKeyEntry %r: %r>' % (self.hostnames, self.key)

########NEW FILE########
__FILENAME__ = kex_gex
# Copyright (C) 2003-2007  Robey Pointer <robeypointer@gmail.com>
#
# This file is part of paramiko.
#
# Paramiko is free software; you can redistribute it and/or modify it under the
# terms of the GNU Lesser General Public License as published by the Free
# Software Foundation; either version 2.1 of the License, or (at your option)
# any later version.
#
# Paramiko is distributed in the hope that it will be useful, but WITHOUT ANY
# WARRANTY; without even the implied warranty of MERCHANTABILITY or FITNESS FOR
# A PARTICULAR PURPOSE.  See the GNU Lesser General Public License for more
# details.
#
# You should have received a copy of the GNU Lesser General Public License
# along with Paramiko; if not, write to the Free Software Foundation, Inc.,
# 59 Temple Place, Suite 330, Boston, MA  02111-1307  USA.

"""
Variant on `KexGroup1 <paramiko.kex_group1.KexGroup1>` where the prime "p" and
generator "g" are provided by the server.  A bit more work is required on the
client side, and a B{lot} more on the server side.
"""

import os
from hashlib import sha1

from paramiko import util
from paramiko.common import DEBUG
from paramiko.message import Message
from paramiko.py3compat import byte_chr, byte_ord, byte_mask
from paramiko.ssh_exception import SSHException


_MSG_KEXDH_GEX_REQUEST_OLD, _MSG_KEXDH_GEX_GROUP, _MSG_KEXDH_GEX_INIT, \
    _MSG_KEXDH_GEX_REPLY, _MSG_KEXDH_GEX_REQUEST = range(30, 35)
c_MSG_KEXDH_GEX_REQUEST_OLD, c_MSG_KEXDH_GEX_GROUP, c_MSG_KEXDH_GEX_INIT, \
    c_MSG_KEXDH_GEX_REPLY, c_MSG_KEXDH_GEX_REQUEST = [byte_chr(c) for c in range(30, 35)]


class KexGex (object):

    name = 'diffie-hellman-group-exchange-sha1'
    min_bits = 1024
    max_bits = 8192
    preferred_bits = 2048

    def __init__(self, transport):
        self.transport = transport
        self.p = None
        self.q = None
        self.g = None
        self.x = None
        self.e = None
        self.f = None
        self.old_style = False

    def start_kex(self, _test_old_style=False):
        if self.transport.server_mode:
            self.transport._expect_packet(_MSG_KEXDH_GEX_REQUEST, _MSG_KEXDH_GEX_REQUEST_OLD)
            return
        # request a bit range: we accept (min_bits) to (max_bits), but prefer
        # (preferred_bits).  according to the spec, we shouldn't pull the
        # minimum up above 1024.
        m = Message()
        if _test_old_style:
            # only used for unit tests: we shouldn't ever send this
            m.add_byte(c_MSG_KEXDH_GEX_REQUEST_OLD)
            m.add_int(self.preferred_bits)
            self.old_style = True
        else:
            m.add_byte(c_MSG_KEXDH_GEX_REQUEST)
            m.add_int(self.min_bits)
            m.add_int(self.preferred_bits)
            m.add_int(self.max_bits)
        self.transport._send_message(m)
        self.transport._expect_packet(_MSG_KEXDH_GEX_GROUP)

    def parse_next(self, ptype, m):
        if ptype == _MSG_KEXDH_GEX_REQUEST:
            return self._parse_kexdh_gex_request(m)
        elif ptype == _MSG_KEXDH_GEX_GROUP:
            return self._parse_kexdh_gex_group(m)
        elif ptype == _MSG_KEXDH_GEX_INIT:
            return self._parse_kexdh_gex_init(m)
        elif ptype == _MSG_KEXDH_GEX_REPLY:
            return self._parse_kexdh_gex_reply(m)
        elif ptype == _MSG_KEXDH_GEX_REQUEST_OLD:
            return self._parse_kexdh_gex_request_old(m)
        raise SSHException('KexGex asked to handle packet type %d' % ptype)

    ###  internals...

    def _generate_x(self):
        # generate an "x" (1 < x < (p-1)/2).
        q = (self.p - 1) // 2
        qnorm = util.deflate_long(q, 0)
        qhbyte = byte_ord(qnorm[0])
        byte_count = len(qnorm)
        qmask = 0xff
        while not (qhbyte & 0x80):
            qhbyte <<= 1
            qmask >>= 1
        while True:
            x_bytes = os.urandom(byte_count)
            x_bytes = byte_mask(x_bytes[0], qmask) + x_bytes[1:]
            x = util.inflate_long(x_bytes, 1)
            if (x > 1) and (x < q):
                break
        self.x = x

    def _parse_kexdh_gex_request(self, m):
        minbits = m.get_int()
        preferredbits = m.get_int()
        maxbits = m.get_int()
        # smoosh the user's preferred size into our own limits
        if preferredbits > self.max_bits:
            preferredbits = self.max_bits
        if preferredbits < self.min_bits:
            preferredbits = self.min_bits
        # fix min/max if they're inconsistent.  technically, we could just pout
        # and hang up, but there's no harm in giving them the benefit of the
        # doubt and just picking a bitsize for them.
        if minbits > preferredbits:
            minbits = preferredbits
        if maxbits < preferredbits:
            maxbits = preferredbits
        # now save a copy
        self.min_bits = minbits
        self.preferred_bits = preferredbits
        self.max_bits = maxbits
        # generate prime
        pack = self.transport._get_modulus_pack()
        if pack is None:
            raise SSHException('Can\'t do server-side gex with no modulus pack')
        self.transport._log(DEBUG, 'Picking p (%d <= %d <= %d bits)' % (minbits, preferredbits, maxbits))
        self.g, self.p = pack.get_modulus(minbits, preferredbits, maxbits)
        m = Message()
        m.add_byte(c_MSG_KEXDH_GEX_GROUP)
        m.add_mpint(self.p)
        m.add_mpint(self.g)
        self.transport._send_message(m)
        self.transport._expect_packet(_MSG_KEXDH_GEX_INIT)

    def _parse_kexdh_gex_request_old(self, m):
        # same as above, but without min_bits or max_bits (used by older clients like putty)
        self.preferred_bits = m.get_int()
        # smoosh the user's preferred size into our own limits
        if self.preferred_bits > self.max_bits:
            self.preferred_bits = self.max_bits
        if self.preferred_bits < self.min_bits:
            self.preferred_bits = self.min_bits
        # generate prime
        pack = self.transport._get_modulus_pack()
        if pack is None:
            raise SSHException('Can\'t do server-side gex with no modulus pack')
        self.transport._log(DEBUG, 'Picking p (~ %d bits)' % (self.preferred_bits,))
        self.g, self.p = pack.get_modulus(self.min_bits, self.preferred_bits, self.max_bits)
        m = Message()
        m.add_byte(c_MSG_KEXDH_GEX_GROUP)
        m.add_mpint(self.p)
        m.add_mpint(self.g)
        self.transport._send_message(m)
        self.transport._expect_packet(_MSG_KEXDH_GEX_INIT)
        self.old_style = True

    def _parse_kexdh_gex_group(self, m):
        self.p = m.get_mpint()
        self.g = m.get_mpint()
        # reject if p's bit length < 1024 or > 8192
        bitlen = util.bit_length(self.p)
        if (bitlen < 1024) or (bitlen > 8192):
            raise SSHException('Server-generated gex p (don\'t ask) is out of range (%d bits)' % bitlen)
        self.transport._log(DEBUG, 'Got server p (%d bits)' % bitlen)
        self._generate_x()
        # now compute e = g^x mod p
        self.e = pow(self.g, self.x, self.p)
        m = Message()
        m.add_byte(c_MSG_KEXDH_GEX_INIT)
        m.add_mpint(self.e)
        self.transport._send_message(m)
        self.transport._expect_packet(_MSG_KEXDH_GEX_REPLY)

    def _parse_kexdh_gex_init(self, m):
        self.e = m.get_mpint()
        if (self.e < 1) or (self.e > self.p - 1):
            raise SSHException('Client kex "e" is out of range')
        self._generate_x()
        self.f = pow(self.g, self.x, self.p)
        K = pow(self.e, self.x, self.p)
        key = self.transport.get_server_key().asbytes()
        # okay, build up the hash H of (V_C || V_S || I_C || I_S || K_S || min || n || max || p || g || e || f || K)
        hm = Message()
        hm.add(self.transport.remote_version, self.transport.local_version,
               self.transport.remote_kex_init, self.transport.local_kex_init,
               key)
        if not self.old_style:
            hm.add_int(self.min_bits)
        hm.add_int(self.preferred_bits)
        if not self.old_style:
            hm.add_int(self.max_bits)
        hm.add_mpint(self.p)
        hm.add_mpint(self.g)
        hm.add_mpint(self.e)
        hm.add_mpint(self.f)
        hm.add_mpint(K)
        H = sha1(hm.asbytes()).digest()
        self.transport._set_K_H(K, H)
        # sign it
        sig = self.transport.get_server_key().sign_ssh_data(H)
        # send reply
        m = Message()
        m.add_byte(c_MSG_KEXDH_GEX_REPLY)
        m.add_string(key)
        m.add_mpint(self.f)
        m.add_string(sig)
        self.transport._send_message(m)
        self.transport._activate_outbound()

    def _parse_kexdh_gex_reply(self, m):
        host_key = m.get_string()
        self.f = m.get_mpint()
        sig = m.get_string()
        if (self.f < 1) or (self.f > self.p - 1):
            raise SSHException('Server kex "f" is out of range')
        K = pow(self.f, self.x, self.p)
        # okay, build up the hash H of (V_C || V_S || I_C || I_S || K_S || min || n || max || p || g || e || f || K)
        hm = Message()
        hm.add(self.transport.local_version, self.transport.remote_version,
               self.transport.local_kex_init, self.transport.remote_kex_init,
               host_key)
        if not self.old_style:
            hm.add_int(self.min_bits)
        hm.add_int(self.preferred_bits)
        if not self.old_style:
            hm.add_int(self.max_bits)
        hm.add_mpint(self.p)
        hm.add_mpint(self.g)
        hm.add_mpint(self.e)
        hm.add_mpint(self.f)
        hm.add_mpint(K)
        self.transport._set_K_H(K, sha1(hm.asbytes()).digest())
        self.transport._verify_key(host_key, sig)
        self.transport._activate_outbound()

########NEW FILE########
__FILENAME__ = kex_group1
# Copyright (C) 2003-2007  Robey Pointer <robeypointer@gmail.com>
#
# This file is part of paramiko.
#
# Paramiko is free software; you can redistribute it and/or modify it under the
# terms of the GNU Lesser General Public License as published by the Free
# Software Foundation; either version 2.1 of the License, or (at your option)
# any later version.
#
# Paramiko is distributed in the hope that it will be useful, but WITHOUT ANY
# WARRANTY; without even the implied warranty of MERCHANTABILITY or FITNESS FOR
# A PARTICULAR PURPOSE.  See the GNU Lesser General Public License for more
# details.
#
# You should have received a copy of the GNU Lesser General Public License
# along with Paramiko; if not, write to the Free Software Foundation, Inc.,
# 59 Temple Place, Suite 330, Boston, MA  02111-1307  USA.

"""
Standard SSH key exchange ("kex" if you wanna sound cool).  Diffie-Hellman of
1024 bit key halves, using a known "p" prime and "g" generator.
"""

import os
from hashlib import sha1

from paramiko import util
from paramiko.common import max_byte, zero_byte
from paramiko.message import Message
from paramiko.py3compat import byte_chr, long, byte_mask
from paramiko.ssh_exception import SSHException


_MSG_KEXDH_INIT, _MSG_KEXDH_REPLY = range(30, 32)
c_MSG_KEXDH_INIT, c_MSG_KEXDH_REPLY = [byte_chr(c) for c in range(30, 32)]

# draft-ietf-secsh-transport-09.txt, page 17
P = 0xFFFFFFFFFFFFFFFFC90FDAA22168C234C4C6628B80DC1CD129024E088A67CC74020BBEA63B139B22514A08798E3404DDEF9519B3CD3A431B302B0A6DF25F14374FE1356D6D51C245E485B576625E7EC6F44C42E9A637ED6B0BFF5CB6F406B7EDEE386BFB5A899FA5AE9F24117C4B1FE649286651ECE65381FFFFFFFFFFFFFFFF
G = 2

b7fffffffffffffff = byte_chr(0x7f) + max_byte * 7
b0000000000000000 = zero_byte * 8


class KexGroup1(object):

    name = 'diffie-hellman-group1-sha1'

    def __init__(self, transport):
        self.transport = transport
        self.x = long(0)
        self.e = long(0)
        self.f = long(0)

    def start_kex(self):
        self._generate_x()
        if self.transport.server_mode:
            # compute f = g^x mod p, but don't send it yet
            self.f = pow(G, self.x, P)
            self.transport._expect_packet(_MSG_KEXDH_INIT)
            return
        # compute e = g^x mod p (where g=2), and send it
        self.e = pow(G, self.x, P)
        m = Message()
        m.add_byte(c_MSG_KEXDH_INIT)
        m.add_mpint(self.e)
        self.transport._send_message(m)
        self.transport._expect_packet(_MSG_KEXDH_REPLY)

    def parse_next(self, ptype, m):
        if self.transport.server_mode and (ptype == _MSG_KEXDH_INIT):
            return self._parse_kexdh_init(m)
        elif not self.transport.server_mode and (ptype == _MSG_KEXDH_REPLY):
            return self._parse_kexdh_reply(m)
        raise SSHException('KexGroup1 asked to handle packet type %d' % ptype)

    ###  internals...

    def _generate_x(self):
        # generate an "x" (1 < x < q), where q is (p-1)/2.
        # p is a 128-byte (1024-bit) number, where the first 64 bits are 1. 
        # therefore q can be approximated as a 2^1023.  we drop the subset of
        # potential x where the first 63 bits are 1, because some of those will be
        # larger than q (but this is a tiny tiny subset of potential x).
        while 1:
            x_bytes = os.urandom(128)
            x_bytes = byte_mask(x_bytes[0], 0x7f) + x_bytes[1:]
            if (x_bytes[:8] != b7fffffffffffffff and
                    x_bytes[:8] != b0000000000000000):
                break
        self.x = util.inflate_long(x_bytes)

    def _parse_kexdh_reply(self, m):
        # client mode
        host_key = m.get_string()
        self.f = m.get_mpint()
        if (self.f < 1) or (self.f > P - 1):
            raise SSHException('Server kex "f" is out of range')
        sig = m.get_binary()
        K = pow(self.f, self.x, P)
        # okay, build up the hash H of (V_C || V_S || I_C || I_S || K_S || e || f || K)
        hm = Message()
        hm.add(self.transport.local_version, self.transport.remote_version,
               self.transport.local_kex_init, self.transport.remote_kex_init)
        hm.add_string(host_key)
        hm.add_mpint(self.e)
        hm.add_mpint(self.f)
        hm.add_mpint(K)
        self.transport._set_K_H(K, sha1(hm.asbytes()).digest())
        self.transport._verify_key(host_key, sig)
        self.transport._activate_outbound()

    def _parse_kexdh_init(self, m):
        # server mode
        self.e = m.get_mpint()
        if (self.e < 1) or (self.e > P - 1):
            raise SSHException('Client kex "e" is out of range')
        K = pow(self.e, self.x, P)
        key = self.transport.get_server_key().asbytes()
        # okay, build up the hash H of (V_C || V_S || I_C || I_S || K_S || e || f || K)
        hm = Message()
        hm.add(self.transport.remote_version, self.transport.local_version,
               self.transport.remote_kex_init, self.transport.local_kex_init)
        hm.add_string(key)
        hm.add_mpint(self.e)
        hm.add_mpint(self.f)
        hm.add_mpint(K)
        H = sha1(hm.asbytes()).digest()
        self.transport._set_K_H(K, H)
        # sign it
        sig = self.transport.get_server_key().sign_ssh_data(H)
        # send reply
        m = Message()
        m.add_byte(c_MSG_KEXDH_REPLY)
        m.add_string(key)
        m.add_mpint(self.f)
        m.add_string(sig)
        self.transport._send_message(m)
        self.transport._activate_outbound()

########NEW FILE########
__FILENAME__ = message
# Copyright (C) 2003-2007  Robey Pointer <robeypointer@gmail.com>
#
# This file is part of paramiko.
#
# Paramiko is free software; you can redistribute it and/or modify it under the
# terms of the GNU Lesser General Public License as published by the Free
# Software Foundation; either version 2.1 of the License, or (at your option)
# any later version.
#
# Paramiko is distributed in the hope that it will be useful, but WITHOUT ANY
# WARRANTY; without even the implied warranty of MERCHANTABILITY or FITNESS FOR
# A PARTICULAR PURPOSE.  See the GNU Lesser General Public License for more
# details.
#
# You should have received a copy of the GNU Lesser General Public License
# along with Paramiko; if not, write to the Free Software Foundation, Inc.,
# 59 Temple Place, Suite 330, Boston, MA  02111-1307  USA.

"""
Implementation of an SSH2 "message".
"""

import struct

from paramiko import util
from paramiko.common import zero_byte, max_byte, one_byte, asbytes
from paramiko.py3compat import long, BytesIO, u, integer_types


class Message (object):
    """
    An SSH2 message is a stream of bytes that encodes some combination of
    strings, integers, bools, and infinite-precision integers (known in Python
    as longs).  This class builds or breaks down such a byte stream.
    
    Normally you don't need to deal with anything this low-level, but it's
    exposed for people implementing custom extensions, or features that
    paramiko doesn't support yet.
    """

    big_int = long(0xff000000)

    def __init__(self, content=None):
        """
        Create a new SSH2 message.

        :param str content:
            the byte stream to use as the message content (passed in only when
            decomposing a message).
        """
        if content is not None:
            self.packet = BytesIO(content)
        else:
            self.packet = BytesIO()

    def __str__(self):
        """
        Return the byte stream content of this message, as a string/bytes obj.
        """
        return self.asbytes()

    def __repr__(self):
        """
        Returns a string representation of this object, for debugging.
        """
        return 'paramiko.Message(' + repr(self.packet.getvalue()) + ')'

    def asbytes(self):
        """
        Return the byte stream content of this Message, as bytes.
        """
        return self.packet.getvalue()

    def rewind(self):
        """
        Rewind the message to the beginning as if no items had been parsed
        out of it yet.
        """
        self.packet.seek(0)

    def get_remainder(self):
        """
        Return the bytes (as a `str`) of this message that haven't already been
        parsed and returned.
        """
        position = self.packet.tell()
        remainder = self.packet.read()
        self.packet.seek(position)
        return remainder

    def get_so_far(self):
        """
        Returns the `str` bytes of this message that have been parsed and
        returned. The string passed into a message's constructor can be
        regenerated by concatenating ``get_so_far`` and `get_remainder`.
        """
        position = self.packet.tell()
        self.rewind()
        return self.packet.read(position)

    def get_bytes(self, n):
        """
        Return the next ``n`` bytes of the message (as a `str`), without
        decomposing into an int, decoded string, etc.  Just the raw bytes are
        returned. Returns a string of ``n`` zero bytes if there weren't ``n``
        bytes remaining in the message.
        """
        b = self.packet.read(n)
        max_pad_size = 1 << 20  # Limit padding to 1 MB
        if len(b) < n < max_pad_size:
            return b + zero_byte * (n - len(b))
        return b

    def get_byte(self):
        """
        Return the next byte of the message, without decomposing it.  This
        is equivalent to `get_bytes(1) <get_bytes>`.

        :return:
            the next (`str`) byte of the message, or ``'\000'`` if there aren't
            any bytes remaining.
        """
        return self.get_bytes(1)

    def get_boolean(self):
        """
        Fetch a boolean from the stream.
        """
        b = self.get_bytes(1)
        return b != zero_byte

    def get_int(self):
        """
        Fetch an int from the stream.

        :return: a 32-bit unsigned `int`.
        """
        byte = self.get_bytes(1)
        if byte == max_byte:
            return util.inflate_long(self.get_binary())
        byte += self.get_bytes(3)
        return struct.unpack('>I', byte)[0]

    def get_size(self):
        """
        Fetch an int from the stream.

        @return: a 32-bit unsigned integer.
        @rtype: int
        """
        return struct.unpack('>I', self.get_bytes(4))[0]

    def get_int64(self):
        """
        Fetch a 64-bit int from the stream.

        :return: a 64-bit unsigned integer (`long`).
        """
        return struct.unpack('>Q', self.get_bytes(8))[0]

    def get_mpint(self):
        """
        Fetch a long int (mpint) from the stream.

        :return: an arbitrary-length integer (`long`).
        """
        return util.inflate_long(self.get_binary())

    def get_string(self):
        """
        Fetch a `str` from the stream.  This could be a byte string and may
        contain unprintable characters.  (It's not unheard of for a string to
        contain another byte-stream message.)
        """
        return self.get_bytes(self.get_size())

    def get_text(self):
        """
        Fetch a string from the stream.  This could be a byte string and may
        contain unprintable characters.  (It's not unheard of for a string to
        contain another byte-stream Message.)

        @return: a string.
        @rtype: string
        """
        return u(self.get_bytes(self.get_size()))
        #return self.get_bytes(self.get_size())

    def get_binary(self):
        """
        Fetch a string from the stream.  This could be a byte string and may
        contain unprintable characters.  (It's not unheard of for a string to
        contain another byte-stream Message.)

        @return: a string.
        @rtype: string
        """
        return self.get_bytes(self.get_size())

    def get_list(self):
        """
        Fetch a `list` of `strings <str>` from the stream.
        
        These are trivially encoded as comma-separated values in a string.
        """
        return self.get_text().split(',')

    def add_bytes(self, b):
        """
        Write bytes to the stream, without any formatting.
        
        :param str b: bytes to add
        """
        self.packet.write(b)
        return self

    def add_byte(self, b):
        """
        Write a single byte to the stream, without any formatting.
        
        :param str b: byte to add
        """
        self.packet.write(b)
        return self

    def add_boolean(self, b):
        """
        Add a boolean value to the stream.
        
        :param bool b: boolean value to add
        """
        if b:
            self.packet.write(one_byte)
        else:
            self.packet.write(zero_byte)
        return self
            
    def add_size(self, n):
        """
        Add an integer to the stream.
        
        :param int n: integer to add
        """
        self.packet.write(struct.pack('>I', n))
        return self
            
    def add_int(self, n):
        """
        Add an integer to the stream.
        
        :param int n: integer to add
        """
        if n >= Message.big_int:
            self.packet.write(max_byte)
            self.add_string(util.deflate_long(n))
        else:
            self.packet.write(struct.pack('>I', n))
        return self

    def add_int64(self, n):
        """
        Add a 64-bit int to the stream.

        :param long n: long int to add
        """
        self.packet.write(struct.pack('>Q', n))
        return self

    def add_mpint(self, z):
        """
        Add a long int to the stream, encoded as an infinite-precision
        integer.  This method only works on positive numbers.
        
        :param long z: long int to add
        """
        self.add_string(util.deflate_long(z))
        return self

    def add_string(self, s):
        """
        Add a string to the stream.
        
        :param str s: string to add
        """
        s = asbytes(s)
        self.add_size(len(s))
        self.packet.write(s)
        return self

    def add_list(self, l):
        """
        Add a list of strings to the stream.  They are encoded identically to
        a single string of values separated by commas.  (Yes, really, that's
        how SSH2 does it.)
        
        :param list l: list of strings to add
        """
        self.add_string(','.join(l))
        return self
        
    def _add(self, i):
        if type(i) is bool:
            return self.add_boolean(i)
        elif isinstance(i, integer_types):
            return self.add_int(i)
        elif type(i) is list:
            return self.add_list(i)
        else:
            return self.add_string(i)

    def add(self, *seq):
        """
        Add a sequence of items to the stream.  The values are encoded based
        on their type: str, int, bool, list, or long.

        .. warning::
            Longs are encoded non-deterministically.  Don't use this method.
        
        :param seq: the sequence of items
        """
        for item in seq:
            self._add(item)

########NEW FILE########
__FILENAME__ = packet
# Copyright (C) 2003-2007  Robey Pointer <robeypointer@gmail.com>
#
# This file is part of paramiko.
#
# Paramiko is free software; you can redistribute it and/or modify it under the
# terms of the GNU Lesser General Public License as published by the Free
# Software Foundation; either version 2.1 of the License, or (at your option)
# any later version.
#
# Paramiko is distributed in the hope that it will be useful, but WITHOUT ANY
# WARRANTY; without even the implied warranty of MERCHANTABILITY or FITNESS FOR
# A PARTICULAR PURPOSE.  See the GNU Lesser General Public License for more
# details.
#
# You should have received a copy of the GNU Lesser General Public License
# along with Paramiko; if not, write to the Free Software Foundation, Inc.,
# 59 Temple Place, Suite 330, Boston, MA  02111-1307  USA.

"""
Packet handling
"""

import errno
import os
import socket
import struct
import threading
import time
from hmac import HMAC

from paramiko import util
from paramiko.common import linefeed_byte, cr_byte_value, asbytes, MSG_NAMES, \
    DEBUG, xffffffff, zero_byte
from paramiko.py3compat import u, byte_ord
from paramiko.ssh_exception import SSHException, ProxyCommandFailure
from paramiko.message import Message


def compute_hmac(key, message, digest_class):
    return HMAC(key, message, digest_class).digest()


class NeedRekeyException (Exception):
    pass


class Packetizer (object):
    """
    Implementation of the base SSH packet protocol.
    """

    # READ the secsh RFC's before raising these values.  if anything,
    # they should probably be lower.
    REKEY_PACKETS = pow(2, 29)
    REKEY_BYTES = pow(2, 29)

    REKEY_PACKETS_OVERFLOW_MAX = pow(2, 29)     # Allow receiving this many packets after a re-key request before terminating
    REKEY_BYTES_OVERFLOW_MAX = pow(2, 29)       # Allow receiving this many bytes after a re-key request before terminating

    def __init__(self, socket):
        self.__socket = socket
        self.__logger = None
        self.__closed = False
        self.__dump_packets = False
        self.__need_rekey = False
        self.__init_count = 0
        self.__remainder = bytes()

        # used for noticing when to re-key:
        self.__sent_bytes = 0
        self.__sent_packets = 0
        self.__received_bytes = 0
        self.__received_packets = 0
        self.__received_bytes_overflow = 0
        self.__received_packets_overflow = 0

        # current inbound/outbound ciphering:
        self.__block_size_out = 8
        self.__block_size_in = 8
        self.__mac_size_out = 0
        self.__mac_size_in = 0
        self.__block_engine_out = None
        self.__block_engine_in = None
        self.__sdctr_out = False
        self.__mac_engine_out = None
        self.__mac_engine_in = None
        self.__mac_key_out = bytes()
        self.__mac_key_in = bytes()
        self.__compress_engine_out = None
        self.__compress_engine_in = None
        self.__sequence_number_out = 0
        self.__sequence_number_in = 0

        # lock around outbound writes (packet computation)
        self.__write_lock = threading.RLock()

        # keepalives:
        self.__keepalive_interval = 0
        self.__keepalive_last = time.time()
        self.__keepalive_callback = None

    def set_log(self, log):
        """
        Set the Python log object to use for logging.
        """
        self.__logger = log

    def set_outbound_cipher(self, block_engine, block_size, mac_engine, mac_size, mac_key, sdctr=False):
        """
        Switch outbound data cipher.
        """
        self.__block_engine_out = block_engine
        self.__sdctr_out = sdctr
        self.__block_size_out = block_size
        self.__mac_engine_out = mac_engine
        self.__mac_size_out = mac_size
        self.__mac_key_out = mac_key
        self.__sent_bytes = 0
        self.__sent_packets = 0
        # wait until the reset happens in both directions before clearing rekey flag
        self.__init_count |= 1
        if self.__init_count == 3:
            self.__init_count = 0
            self.__need_rekey = False

    def set_inbound_cipher(self, block_engine, block_size, mac_engine, mac_size, mac_key):
        """
        Switch inbound data cipher.
        """
        self.__block_engine_in = block_engine
        self.__block_size_in = block_size
        self.__mac_engine_in = mac_engine
        self.__mac_size_in = mac_size
        self.__mac_key_in = mac_key
        self.__received_bytes = 0
        self.__received_packets = 0
        self.__received_bytes_overflow = 0
        self.__received_packets_overflow = 0
        # wait until the reset happens in both directions before clearing rekey flag
        self.__init_count |= 2
        if self.__init_count == 3:
            self.__init_count = 0
            self.__need_rekey = False

    def set_outbound_compressor(self, compressor):
        self.__compress_engine_out = compressor

    def set_inbound_compressor(self, compressor):
        self.__compress_engine_in = compressor

    def close(self):
        self.__closed = True
        self.__socket.close()

    def set_hexdump(self, hexdump):
        self.__dump_packets = hexdump

    def get_hexdump(self):
        return self.__dump_packets

    def get_mac_size_in(self):
        return self.__mac_size_in

    def get_mac_size_out(self):
        return self.__mac_size_out

    def need_rekey(self):
        """
        Returns ``True`` if a new set of keys needs to be negotiated.  This
        will be triggered during a packet read or write, so it should be
        checked after every read or write, or at least after every few.
        """
        return self.__need_rekey

    def set_keepalive(self, interval, callback):
        """
        Turn on/off the callback keepalive.  If ``interval`` seconds pass with
        no data read from or written to the socket, the callback will be
        executed and the timer will be reset.
        """
        self.__keepalive_interval = interval
        self.__keepalive_callback = callback
        self.__keepalive_last = time.time()

    def read_all(self, n, check_rekey=False):
        """
        Read as close to N bytes as possible, blocking as long as necessary.

        :param int n: number of bytes to read
        :return: the data read, as a `str`

        :raises EOFError:
            if the socket was closed before all the bytes could be read
        """
        out = bytes()
        # handle over-reading from reading the banner line
        if len(self.__remainder) > 0:
            out = self.__remainder[:n]
            self.__remainder = self.__remainder[n:]
            n -= len(out)
        while n > 0:
            got_timeout = False
            try:
                x = self.__socket.recv(n)
                if len(x) == 0:
                    raise EOFError()
                out += x
                n -= len(x)
            except socket.timeout:
                got_timeout = True
            except socket.error as e:
                # on Linux, sometimes instead of socket.timeout, we get
                # EAGAIN.  this is a bug in recent (> 2.6.9) kernels but
                # we need to work around it.
                if (type(e.args) is tuple) and (len(e.args) > 0) and (e.args[0] == errno.EAGAIN):
                    got_timeout = True
                elif (type(e.args) is tuple) and (len(e.args) > 0) and (e.args[0] == errno.EINTR):
                    # syscall interrupted; try again
                    pass
                elif self.__closed:
                    raise EOFError()
                else:
                    raise
            if got_timeout:
                if self.__closed:
                    raise EOFError()
                if check_rekey and (len(out) == 0) and self.__need_rekey:
                    raise NeedRekeyException()
                self._check_keepalive()
        return out

    def write_all(self, out):
        self.__keepalive_last = time.time()
        while len(out) > 0:
            retry_write = False
            try:
                n = self.__socket.send(out)
            except socket.timeout:
                retry_write = True
            except socket.error as e:
                if (type(e.args) is tuple) and (len(e.args) > 0) and (e.args[0] == errno.EAGAIN):
                    retry_write = True
                elif (type(e.args) is tuple) and (len(e.args) > 0) and (e.args[0] == errno.EINTR):
                    # syscall interrupted; try again
                    retry_write = True
                else:
                    n = -1
            except ProxyCommandFailure:
                raise  # so it doesn't get swallowed by the below catchall
            except Exception:
                # could be: (32, 'Broken pipe')
                n = -1
            if retry_write:
                n = 0
                if self.__closed:
                    n = -1
            if n < 0:
                raise EOFError()
            if n == len(out):
                break
            out = out[n:]
        return

    def readline(self, timeout):
        """
        Read a line from the socket.  We assume no data is pending after the
        line, so it's okay to attempt large reads.
        """
        buf = self.__remainder
        while not linefeed_byte in buf:
            buf += self._read_timeout(timeout)
        n = buf.index(linefeed_byte)
        self.__remainder = buf[n + 1:]
        buf = buf[:n]
        if (len(buf) > 0) and (buf[-1] == cr_byte_value):
            buf = buf[:-1]
        return u(buf)

    def send_message(self, data):
        """
        Write a block of data using the current cipher, as an SSH block.
        """
        # encrypt this sucka
        data = asbytes(data)
        cmd = byte_ord(data[0])
        if cmd in MSG_NAMES:
            cmd_name = MSG_NAMES[cmd]
        else:
            cmd_name = '$%x' % cmd
        orig_len = len(data)
        self.__write_lock.acquire()
        try:
            if self.__compress_engine_out is not None:
                data = self.__compress_engine_out(data)
            packet = self._build_packet(data)
            if self.__dump_packets:
                self._log(DEBUG, 'Write packet <%s>, length %d' % (cmd_name, orig_len))
                self._log(DEBUG, util.format_binary(packet, 'OUT: '))
            if self.__block_engine_out is not None:
                out = self.__block_engine_out.encrypt(packet)
            else:
                out = packet
            # + mac
            if self.__block_engine_out is not None:
                payload = struct.pack('>I', self.__sequence_number_out) + packet
                out += compute_hmac(self.__mac_key_out, payload, self.__mac_engine_out)[:self.__mac_size_out]
            self.__sequence_number_out = (self.__sequence_number_out + 1) & xffffffff
            self.write_all(out)

            self.__sent_bytes += len(out)
            self.__sent_packets += 1
            if (self.__sent_packets >= self.REKEY_PACKETS or self.__sent_bytes >= self.REKEY_BYTES)\
                    and not self.__need_rekey:
                # only ask once for rekeying
                self._log(DEBUG, 'Rekeying (hit %d packets, %d bytes sent)' %
                          (self.__sent_packets, self.__sent_bytes))
                self.__received_bytes_overflow = 0
                self.__received_packets_overflow = 0
                self._trigger_rekey()
        finally:
            self.__write_lock.release()

    def read_message(self):
        """
        Only one thread should ever be in this function (no other locking is
        done).

        :raises SSHException: if the packet is mangled
        :raises NeedRekeyException: if the transport should rekey
        """
        header = self.read_all(self.__block_size_in, check_rekey=True)
        if self.__block_engine_in is not None:
            header = self.__block_engine_in.decrypt(header)
        if self.__dump_packets:
            self._log(DEBUG, util.format_binary(header, 'IN: '))
        packet_size = struct.unpack('>I', header[:4])[0]
        # leftover contains decrypted bytes from the first block (after the length field)
        leftover = header[4:]
        if (packet_size - len(leftover)) % self.__block_size_in != 0:
            raise SSHException('Invalid packet blocking')
        buf = self.read_all(packet_size + self.__mac_size_in - len(leftover))
        packet = buf[:packet_size - len(leftover)]
        post_packet = buf[packet_size - len(leftover):]
        if self.__block_engine_in is not None:
            packet = self.__block_engine_in.decrypt(packet)
        if self.__dump_packets:
            self._log(DEBUG, util.format_binary(packet, 'IN: '))
        packet = leftover + packet

        if self.__mac_size_in > 0:
            mac = post_packet[:self.__mac_size_in]
            mac_payload = struct.pack('>II', self.__sequence_number_in, packet_size) + packet
            my_mac = compute_hmac(self.__mac_key_in, mac_payload, self.__mac_engine_in)[:self.__mac_size_in]
            if not util.constant_time_bytes_eq(my_mac, mac):
                raise SSHException('Mismatched MAC')
        padding = byte_ord(packet[0])
        payload = packet[1:packet_size - padding]

        if self.__dump_packets:
            self._log(DEBUG, 'Got payload (%d bytes, %d padding)' % (packet_size, padding))

        if self.__compress_engine_in is not None:
            payload = self.__compress_engine_in(payload)

        msg = Message(payload[1:])
        msg.seqno = self.__sequence_number_in
        self.__sequence_number_in = (self.__sequence_number_in + 1) & xffffffff

        # check for rekey
        raw_packet_size = packet_size + self.__mac_size_in + 4
        self.__received_bytes += raw_packet_size
        self.__received_packets += 1
        if self.__need_rekey:
            # we've asked to rekey -- give them some packets to comply before
            # dropping the connection
            self.__received_bytes_overflow += raw_packet_size
            self.__received_packets_overflow += 1
            if (self.__received_packets_overflow >= self.REKEY_PACKETS_OVERFLOW_MAX) or \
               (self.__received_bytes_overflow >= self.REKEY_BYTES_OVERFLOW_MAX):
                raise SSHException('Remote transport is ignoring rekey requests')
        elif (self.__received_packets >= self.REKEY_PACKETS) or \
             (self.__received_bytes >= self.REKEY_BYTES):
            # only ask once for rekeying
            self._log(DEBUG, 'Rekeying (hit %d packets, %d bytes received)' %
                      (self.__received_packets, self.__received_bytes))
            self.__received_bytes_overflow = 0
            self.__received_packets_overflow = 0
            self._trigger_rekey()

        cmd = byte_ord(payload[0])
        if cmd in MSG_NAMES:
            cmd_name = MSG_NAMES[cmd]
        else:
            cmd_name = '$%x' % cmd
        if self.__dump_packets:
            self._log(DEBUG, 'Read packet <%s>, length %d' % (cmd_name, len(payload)))
        return cmd, msg

    ##########  protected

    def _log(self, level, msg):
        if self.__logger is None:
            return
        if issubclass(type(msg), list):
            for m in msg:
                self.__logger.log(level, m)
        else:
            self.__logger.log(level, msg)

    def _check_keepalive(self):
        if (not self.__keepalive_interval) or (not self.__block_engine_out) or \
                self.__need_rekey:
            # wait till we're encrypting, and not in the middle of rekeying
            return
        now = time.time()
        if now > self.__keepalive_last + self.__keepalive_interval:
            self.__keepalive_callback()
            self.__keepalive_last = now

    def _read_timeout(self, timeout):
        start = time.time()
        while True:
            try:
                x = self.__socket.recv(128)
                if len(x) == 0:
                    raise EOFError()
                break
            except socket.timeout:
                pass
            except EnvironmentError as e:
                if (type(e.args) is tuple and len(e.args) > 0 and
                        e.args[0] == errno.EINTR):
                    pass
                else:
                    raise
            if self.__closed:
                raise EOFError()
            now = time.time()
            if now - start >= timeout:
                raise socket.timeout()
        return x

    def _build_packet(self, payload):
        # pad up at least 4 bytes, to nearest block-size (usually 8)
        bsize = self.__block_size_out
        padding = 3 + bsize - ((len(payload) + 8) % bsize)
        packet = struct.pack('>IB', len(payload) + padding + 1, padding)
        packet += payload
        if self.__sdctr_out or self.__block_engine_out is None:
            # cute trick i caught openssh doing: if we're not encrypting or SDCTR mode (RFC4344),
            # don't waste random bytes for the padding
            packet += (zero_byte * padding)
        else:
            packet += os.urandom(padding)
        return packet

    def _trigger_rekey(self):
        # outside code should check for this flag
        self.__need_rekey = True

########NEW FILE########
__FILENAME__ = pipe
# Copyright (C) 2003-2007  Robey Pointer <robeypointer@gmail.com>
#
# This file is part of paramiko.
#
# Paramiko is free software; you can redistribute it and/or modify it under the
# terms of the GNU Lesser General Public License as published by the Free
# Software Foundation; either version 2.1 of the License, or (at your option)
# any later version.
#
# Paramiko is distributed in the hope that it will be useful, but WITHOUT ANY
# WARRANTY; without even the implied warranty of MERCHANTABILITY or FITNESS FOR
# A PARTICULAR PURPOSE.  See the GNU Lesser General Public License for more
# details.
#
# You should have received a copy of the GNU Lesser General Public License
# along with Paramiko; if not, write to the Free Software Foundation, Inc.,
# 59 Temple Place, Suite 330, Boston, MA  02111-1307  USA.

"""
Abstraction of a one-way pipe where the read end can be used in
`select.select`. Normally this is trivial, but Windows makes it nearly
impossible.

The pipe acts like an Event, which can be set or cleared. When set, the pipe
will trigger as readable in `select <select.select>`.
"""

import sys
import os
import socket


def make_pipe():
    if sys.platform[:3] != 'win':
        p = PosixPipe()
    else:
        p = WindowsPipe()
    return p


class PosixPipe (object):
    def __init__(self):
        self._rfd, self._wfd = os.pipe()
        self._set = False
        self._forever = False
        self._closed = False
    
    def close(self):
        os.close(self._rfd)
        os.close(self._wfd)
        # used for unit tests:
        self._closed = True
    
    def fileno(self):
        return self._rfd

    def clear(self):
        if not self._set or self._forever:
            return
        os.read(self._rfd, 1)
        self._set = False
    
    def set(self):
        if self._set or self._closed:
            return
        self._set = True
        os.write(self._wfd, b'*')
    
    def set_forever(self):
        self._forever = True
        self.set()


class WindowsPipe (object):
    """
    On Windows, only an OS-level "WinSock" may be used in select(), but reads
    and writes must be to the actual socket object.
    """
    def __init__(self):
        serv = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        serv.bind(('127.0.0.1', 0))
        serv.listen(1)
    
        # need to save sockets in _rsock/_wsock so they don't get closed
        self._rsock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self._rsock.connect(('127.0.0.1', serv.getsockname()[1]))
    
        self._wsock, addr = serv.accept()
        serv.close()
        self._set = False
        self._forever = False
        self._closed = False
    
    def close(self):
        self._rsock.close()
        self._wsock.close()
        # used for unit tests:
        self._closed = True
    
    def fileno(self):
        return self._rsock.fileno()

    def clear (self):
        if not self._set or self._forever:
            return
        self._rsock.recv(1)
        self._set = False
    
    def set (self):
        if self._set or self._closed:
            return
        self._set = True
        self._wsock.send(b'*')

    def set_forever (self):
        self._forever = True
        self.set()


class OrPipe (object):
    def __init__(self, pipe):
        self._set = False
        self._partner = None
        self._pipe = pipe
    
    def set(self):
        self._set = True
        if not self._partner._set:
            self._pipe.set()
    
    def clear(self):
        self._set = False
        if not self._partner._set:
            self._pipe.clear()


def make_or_pipe(pipe):
    """
    wraps a pipe into two pipe-like objects which are "or"d together to
    affect the real pipe. if either returned pipe is set, the wrapped pipe
    is set. when both are cleared, the wrapped pipe is cleared.
    """
    p1 = OrPipe(pipe)
    p2 = OrPipe(pipe)
    p1._partner = p2
    p2._partner = p1
    return p1, p2


########NEW FILE########
__FILENAME__ = pkey
# Copyright (C) 2003-2007  Robey Pointer <robeypointer@gmail.com>
#
# This file is part of paramiko.
#
# Paramiko is free software; you can redistribute it and/or modify it under the
# terms of the GNU Lesser General Public License as published by the Free
# Software Foundation; either version 2.1 of the License, or (at your option)
# any later version.
#
# Paramiko is distributed in the hope that it will be useful, but WITHOUT ANY
# WARRANTY; without even the implied warranty of MERCHANTABILITY or FITNESS FOR
# A PARTICULAR PURPOSE.  See the GNU Lesser General Public License for more
# details.
#
# You should have received a copy of the GNU Lesser General Public License
# along with Paramiko; if not, write to the Free Software Foundation, Inc.,
# 59 Temple Place, Suite 330, Boston, MA  02111-1307  USA.

"""
Common API for all public keys.
"""

import base64
from binascii import hexlify, unhexlify
import os
from hashlib import md5

from Crypto.Cipher import DES3, AES

from paramiko import util
from paramiko.common import o600, zero_byte
from paramiko.py3compat import u, encodebytes, decodebytes, b
from paramiko.ssh_exception import SSHException, PasswordRequiredException


class PKey (object):
    """
    Base class for public keys.
    """

    # known encryption types for private key files:
    _CIPHER_TABLE = {
        'AES-128-CBC': {'cipher': AES, 'keysize': 16, 'blocksize': 16, 'mode': AES.MODE_CBC},
        'DES-EDE3-CBC': {'cipher': DES3, 'keysize': 24, 'blocksize': 8, 'mode': DES3.MODE_CBC},
    }

    def __init__(self, msg=None, data=None):
        """
        Create a new instance of this public key type.  If ``msg`` is given,
        the key's public part(s) will be filled in from the message.  If
        ``data`` is given, the key's public part(s) will be filled in from
        the string.

        :param .Message msg:
            an optional SSH `.Message` containing a public key of this type.
        :param str data: an optional string containing a public key of this type

        :raises SSHException:
            if a key cannot be created from the ``data`` or ``msg`` given, or
            no key was passed in.
        """
        pass

    def asbytes(self):
        """
        Return a string of an SSH `.Message` made up of the public part(s) of
        this key.  This string is suitable for passing to `__init__` to
        re-create the key object later.
        """
        return bytes()

    def __str__(self):
        return self.asbytes()

    # noinspection PyUnresolvedReferences
    def __cmp__(self, other):
        """
        Compare this key to another.  Returns 0 if this key is equivalent to
        the given key, or non-0 if they are different.  Only the public parts
        of the key are compared, so a public key will compare equal to its
        corresponding private key.

        :param .Pkey other: key to compare to.
        """
        hs = hash(self)
        ho = hash(other)
        if hs != ho:
            return cmp(hs, ho)
        return cmp(self.asbytes(), other.asbytes())

    def __eq__(self, other):
        return hash(self) == hash(other)

    def get_name(self):
        """
        Return the name of this private key implementation.

        :return:
            name of this private key type, in SSH terminology, as a `str` (for
            example, ``"ssh-rsa"``).
        """
        return ''

    def get_bits(self):
        """
        Return the number of significant bits in this key.  This is useful
        for judging the relative security of a key.

        :return: bits in the key (as an `int`)
        """
        return 0

    def can_sign(self):
        """
        Return ``True`` if this key has the private part necessary for signing
        data.
        """
        return False

    def get_fingerprint(self):
        """
        Return an MD5 fingerprint of the public part of this key.  Nothing
        secret is revealed.

        :return:
            a 16-byte `string <str>` (binary) of the MD5 fingerprint, in SSH
            format.
        """
        return md5(self.asbytes()).digest()

    def get_base64(self):
        """
        Return a base64 string containing the public part of this key.  Nothing
        secret is revealed.  This format is compatible with that used to store
        public key files or recognized host keys.

        :return: a base64 `string <str>` containing the public part of the key.
        """
        return u(encodebytes(self.asbytes())).replace('\n', '')

    def sign_ssh_data(self, data):
        """
        Sign a blob of data with this private key, and return a `.Message`
        representing an SSH signature message.

        :param str data: the data to sign.
        :return: an SSH signature `message <.Message>`.
        """
        return bytes()

    def verify_ssh_sig(self, data, msg):
        """
        Given a blob of data, and an SSH message representing a signature of
        that data, verify that it was signed with this key.

        :param str data: the data that was signed.
        :param .Message msg: an SSH signature message
        :return:
            ``True`` if the signature verifies correctly; ``False`` otherwise.
        """
        return False

    def from_private_key_file(cls, filename, password=None):
        """
        Create a key object by reading a private key file.  If the private
        key is encrypted and ``password`` is not ``None``, the given password
        will be used to decrypt the key (otherwise `.PasswordRequiredException`
        is thrown).  Through the magic of Python, this factory method will
        exist in all subclasses of PKey (such as `.RSAKey` or `.DSSKey`), but
        is useless on the abstract PKey class.

        :param str filename: name of the file to read
        :param str password: an optional password to use to decrypt the key file,
            if it's encrypted
        :return: a new `.PKey` based on the given private key

        :raises IOError: if there was an error reading the file
        :raises PasswordRequiredException: if the private key file is
            encrypted, and ``password`` is ``None``
        :raises SSHException: if the key file is invalid
        """
        key = cls(filename=filename, password=password)
        return key
    from_private_key_file = classmethod(from_private_key_file)

    def from_private_key(cls, file_obj, password=None):
        """
        Create a key object by reading a private key from a file (or file-like)
        object.  If the private key is encrypted and ``password`` is not ``None``,
        the given password will be used to decrypt the key (otherwise
        `.PasswordRequiredException` is thrown).

        :param file file_obj: the file to read from
        :param str password:
            an optional password to use to decrypt the key, if it's encrypted
        :return: a new `.PKey` based on the given private key

        :raises IOError: if there was an error reading the key
        :raises PasswordRequiredException: if the private key file is encrypted,
            and ``password`` is ``None``
        :raises SSHException: if the key file is invalid
        """
        key = cls(file_obj=file_obj, password=password)
        return key
    from_private_key = classmethod(from_private_key)

    def write_private_key_file(self, filename, password=None):
        """
        Write private key contents into a file.  If the password is not
        ``None``, the key is encrypted before writing.

        :param str filename: name of the file to write
        :param str password:
            an optional password to use to encrypt the key file

        :raises IOError: if there was an error writing the file
        :raises SSHException: if the key is invalid
        """
        raise Exception('Not implemented in PKey')

    def write_private_key(self, file_obj, password=None):
        """
        Write private key contents into a file (or file-like) object.  If the
        password is not ``None``, the key is encrypted before writing.

        :param file file_obj: the file object to write into
        :param str password: an optional password to use to encrypt the key

        :raises IOError: if there was an error writing to the file
        :raises SSHException: if the key is invalid
        """
        raise Exception('Not implemented in PKey')

    def _read_private_key_file(self, tag, filename, password=None):
        """
        Read an SSH2-format private key file, looking for a string of the type
        ``"BEGIN xxx PRIVATE KEY"`` for some ``xxx``, base64-decode the text we
        find, and return it as a string.  If the private key is encrypted and
        ``password`` is not ``None``, the given password will be used to decrypt
        the key (otherwise `.PasswordRequiredException` is thrown).

        :param str tag: ``"RSA"`` or ``"DSA"``, the tag used to mark the data block.
        :param str filename: name of the file to read.
        :param str password:
            an optional password to use to decrypt the key file, if it's
            encrypted.
        :return: data blob (`str`) that makes up the private key.

        :raises IOError: if there was an error reading the file.
        :raises PasswordRequiredException: if the private key file is
            encrypted, and ``password`` is ``None``.
        :raises SSHException: if the key file is invalid.
        """
        with open(filename, 'r') as f:
            data = self._read_private_key(tag, f, password)
        return data

    def _read_private_key(self, tag, f, password=None):
        lines = f.readlines()
        start = 0
        while (start < len(lines)) and (lines[start].strip() != '-----BEGIN ' + tag + ' PRIVATE KEY-----'):
            start += 1
        if start >= len(lines):
            raise SSHException('not a valid ' + tag + ' private key file')
        # parse any headers first
        headers = {}
        start += 1
        while start < len(lines):
            l = lines[start].split(': ')
            if len(l) == 1:
                break
            headers[l[0].lower()] = l[1].strip()
            start += 1
        # find end
        end = start
        while (lines[end].strip() != '-----END ' + tag + ' PRIVATE KEY-----') and (end < len(lines)):
            end += 1
        # if we trudged to the end of the file, just try to cope.
        try:
            data = decodebytes(b(''.join(lines[start:end])))
        except base64.binascii.Error as e:
            raise SSHException('base64 decoding error: ' + str(e))
        if 'proc-type' not in headers:
            # unencryped: done
            return data
        # encrypted keyfile: will need a password
        if headers['proc-type'] != '4,ENCRYPTED':
            raise SSHException('Unknown private key structure "%s"' % headers['proc-type'])
        try:
            encryption_type, saltstr = headers['dek-info'].split(',')
        except:
            raise SSHException("Can't parse DEK-info in private key file")
        if encryption_type not in self._CIPHER_TABLE:
            raise SSHException('Unknown private key cipher "%s"' % encryption_type)
        # if no password was passed in, raise an exception pointing out that we need one
        if password is None:
            raise PasswordRequiredException('Private key file is encrypted')
        cipher = self._CIPHER_TABLE[encryption_type]['cipher']
        keysize = self._CIPHER_TABLE[encryption_type]['keysize']
        mode = self._CIPHER_TABLE[encryption_type]['mode']
        salt = unhexlify(b(saltstr))
        key = util.generate_key_bytes(md5, salt, password, keysize)
        return cipher.new(key, mode, salt).decrypt(data)

    def _write_private_key_file(self, tag, filename, data, password=None):
        """
        Write an SSH2-format private key file in a form that can be read by
        paramiko or openssh.  If no password is given, the key is written in
        a trivially-encoded format (base64) which is completely insecure.  If
        a password is given, DES-EDE3-CBC is used.

        :param str tag: ``"RSA"`` or ``"DSA"``, the tag used to mark the data block.
        :param file filename: name of the file to write.
        :param str data: data blob that makes up the private key.
        :param str password: an optional password to use to encrypt the file.

        :raises IOError: if there was an error writing the file.
        """
        with open(filename, 'w', o600) as f:
            # grrr... the mode doesn't always take hold
            os.chmod(filename, o600)
            self._write_private_key(tag, f, data, password)

    def _write_private_key(self, tag, f, data, password=None):
        f.write('-----BEGIN %s PRIVATE KEY-----\n' % tag)
        if password is not None:
            # since we only support one cipher here, use it
            cipher_name = list(self._CIPHER_TABLE.keys())[0]
            cipher = self._CIPHER_TABLE[cipher_name]['cipher']
            keysize = self._CIPHER_TABLE[cipher_name]['keysize']
            blocksize = self._CIPHER_TABLE[cipher_name]['blocksize']
            mode = self._CIPHER_TABLE[cipher_name]['mode']
            salt = os.urandom(16)
            key = util.generate_key_bytes(md5, salt, password, keysize)
            if len(data) % blocksize != 0:
                n = blocksize - len(data) % blocksize
                #data += os.urandom(n)
                # that would make more sense ^, but it confuses openssh.
                data += zero_byte * n
            data = cipher.new(key, mode, salt).encrypt(data)
            f.write('Proc-Type: 4,ENCRYPTED\n')
            f.write('DEK-Info: %s,%s\n' % (cipher_name, u(hexlify(salt)).upper()))
            f.write('\n')
        s = u(encodebytes(data))
        # re-wrap to 64-char lines
        s = ''.join(s.split('\n'))
        s = '\n'.join([s[i: i + 64] for i in range(0, len(s), 64)])
        f.write(s)
        f.write('\n')
        f.write('-----END %s PRIVATE KEY-----\n' % tag)

########NEW FILE########
__FILENAME__ = primes
# Copyright (C) 2003-2007  Robey Pointer <robeypointer@gmail.com>
#
# This file is part of paramiko.
#
# Paramiko is free software; you can redistribute it and/or modify it under the
# terms of the GNU Lesser General Public License as published by the Free
# Software Foundation; either version 2.1 of the License, or (at your option)
# any later version.
#
# Paramiko is distributed in the hope that it will be useful, but WITHOUT ANY
# WARRANTY; without even the implied warranty of MERCHANTABILITY or FITNESS FOR
# A PARTICULAR PURPOSE.  See the GNU Lesser General Public License for more
# details.
#
# You should have received a copy of the GNU Lesser General Public License
# along with Paramiko; if not, write to the Free Software Foundation, Inc.,
# 59 Temple Place, Suite 330, Boston, MA  02111-1307  USA.

"""
Utility functions for dealing with primes.
"""

import os

from paramiko import util
from paramiko.py3compat import byte_mask, long
from paramiko.ssh_exception import SSHException


def _roll_random(n):
    """returns a random # from 0 to N-1"""
    bits = util.bit_length(n - 1)
    byte_count = (bits + 7) // 8
    hbyte_mask = pow(2, bits % 8) - 1

    # so here's the plan:
    # we fetch as many random bits as we'd need to fit N-1, and if the
    # generated number is >= N, we try again.  in the worst case (N-1 is a
    # power of 2), we have slightly better than 50% odds of getting one that
    # fits, so i can't guarantee that this loop will ever finish, but the odds
    # of it looping forever should be infinitesimal.
    while True:
        x = os.urandom(byte_count)
        if hbyte_mask > 0:
            x = byte_mask(x[0], hbyte_mask) + x[1:]
        num = util.inflate_long(x, 1)
        if num < n:
            break
    return num


class ModulusPack (object):
    """
    convenience object for holding the contents of the /etc/ssh/moduli file,
    on systems that have such a file.
    """

    def __init__(self):
        # pack is a hash of: bits -> [ (generator, modulus) ... ]
        self.pack = {}
        self.discarded = []

    def _parse_modulus(self, line):
        timestamp, mod_type, tests, tries, size, generator, modulus = line.split()
        mod_type = int(mod_type)
        tests = int(tests)
        tries = int(tries)
        size = int(size)
        generator = int(generator)
        modulus = long(modulus, 16)

        # weed out primes that aren't at least:
        # type 2 (meets basic structural requirements)
        # test 4 (more than just a small-prime sieve)
        # tries < 100 if test & 4 (at least 100 tries of miller-rabin)
        if (mod_type < 2) or (tests < 4) or ((tests & 4) and (tests < 8) and (tries < 100)):
            self.discarded.append((modulus, 'does not meet basic requirements'))
            return
        if generator == 0:
            generator = 2

        # there's a bug in the ssh "moduli" file (yeah, i know: shock! dismay!
        # call cnn!) where it understates the bit lengths of these primes by 1.
        # this is okay.
        bl = util.bit_length(modulus)
        if (bl != size) and (bl != size + 1):
            self.discarded.append((modulus, 'incorrectly reported bit length %d' % size))
            return
        if bl not in self.pack:
            self.pack[bl] = []
        self.pack[bl].append((generator, modulus))

    def read_file(self, filename):
        """
        :raises IOError: passed from any file operations that fail.
        """
        self.pack = {}
        with open(filename, 'r') as f:
            for line in f:
                line = line.strip()
                if (len(line) == 0) or (line[0] == '#'):
                    continue
                try:
                    self._parse_modulus(line)
                except:
                    continue

    def get_modulus(self, min, prefer, max):
        bitsizes = sorted(self.pack.keys())
        if len(bitsizes) == 0:
            raise SSHException('no moduli available')
        good = -1
        # find nearest bitsize >= preferred
        for b in bitsizes:
            if (b >= prefer) and (b < max) and (b < good or good == -1):
                good = b
        # if that failed, find greatest bitsize >= min
        if good == -1:
            for b in bitsizes:
                if (b >= min) and (b < max) and (b > good):
                    good = b
        if good == -1:
            # their entire (min, max) range has no intersection with our range.
            # if their range is below ours, pick the smallest.  otherwise pick
            # the largest.  it'll be out of their range requirement either way,
            # but we'll be sending them the closest one we have.
            good = bitsizes[0]
            if min > good:
                good = bitsizes[-1]
        # now pick a random modulus of this bitsize
        n = _roll_random(len(self.pack[good]))
        return self.pack[good][n]

########NEW FILE########
__FILENAME__ = proxy
# Copyright (C) 2012  Yipit, Inc <coders@yipit.com>
#
# This file is part of paramiko.
#
# Paramiko is free software; you can redistribute it and/or modify it under the
# terms of the GNU Lesser General Public License as published by the Free
# Software Foundation; either version 2.1 of the License, or (at your option)
# any later version.
#
# Paramiko is distrubuted in the hope that it will be useful, but WITHOUT ANY
# WARRANTY; without even the implied warranty of MERCHANTABILITY or FITNESS FOR
# A PARTICULAR PURPOSE.  See the GNU Lesser General Public License for more
# details.
#
# You should have received a copy of the GNU Lesser General Public License
# along with Paramiko; if not, write to the Free Software Foundation, Inc.,
# 59 Temple Place, Suite 330, Boston, MA  02111-1307  USA.


from datetime import datetime
import os
from shlex import split as shlsplit
import signal
from subprocess import Popen, PIPE
from select import select
import socket

from paramiko.ssh_exception import ProxyCommandFailure


class ProxyCommand(object):
    """
    Wraps a subprocess running ProxyCommand-driven programs.

    This class implements a the socket-like interface needed by the
    `.Transport` and `.Packetizer` classes. Using this class instead of a
    regular socket makes it possible to talk with a Popen'd command that will
    proxy traffic between the client and a server hosted in another machine.
    """
    def __init__(self, command_line):
        """
        Create a new CommandProxy instance. The instance created by this
        class can be passed as an argument to the `.Transport` class.

        :param str command_line:
            the command that should be executed and used as the proxy.
        """
        self.cmd = shlsplit(command_line)
        self.process = Popen(self.cmd, stdin=PIPE, stdout=PIPE, stderr=PIPE)
        self.timeout = None
        self.buffer = []

    def send(self, content):
        """
        Write the content received from the SSH client to the standard
        input of the forked command.

        :param str content: string to be sent to the forked command
        """
        try:
            self.process.stdin.write(content)
        except IOError as e:
            # There was a problem with the child process. It probably
            # died and we can't proceed. The best option here is to
            # raise an exception informing the user that the informed
            # ProxyCommand is not working.
            raise ProxyCommandFailure(' '.join(self.cmd), e.strerror)
        return len(content)

    def recv(self, size):
        """
        Read from the standard output of the forked program.

        :param int size: how many chars should be read

        :return: the length of the read content, as an `int`
        """
        try:
            start = datetime.now()
            while len(self.buffer) < size:
                if self.timeout is not None:
                    elapsed = (datetime.now() - start).microseconds
                    timeout = self.timeout * 1000 * 1000  # to microseconds
                    if elapsed >= timeout:
                        raise socket.timeout()
                r, w, x = select([self.process.stdout], [], [], 0.0)
                if r and r[0] == self.process.stdout:
                    b = os.read(self.process.stdout.fileno(), 1)
                    # Store in class-level buffer for persistence across
                    # timeouts; this makes us act more like a real socket
                    # (where timeouts don't actually drop data.)
                    self.buffer.append(b)
            result = ''.join(self.buffer)
            self.buffer = []
            return result
        except socket.timeout:
            raise  # socket.timeout is a subclass of IOError
        except IOError as e:
            raise ProxyCommandFailure(' '.join(self.cmd), e.strerror)

    def close(self):
        os.kill(self.process.pid, signal.SIGTERM)

    def settimeout(self, timeout):
        self.timeout = timeout

########NEW FILE########
__FILENAME__ = py3compat
import sys
import base64

__all__ = ['PY2', 'string_types', 'integer_types', 'text_type', 'bytes_types', 'bytes', 'long', 'input',
           'decodebytes', 'encodebytes', 'bytestring', 'byte_ord', 'byte_chr', 'byte_mask',
           'b', 'u', 'b2s', 'StringIO', 'BytesIO', 'is_callable', 'MAXSIZE', 'next']

PY2 = sys.version_info[0] < 3

if PY2:
    string_types = basestring
    text_type = unicode
    bytes_types = str
    bytes = str
    integer_types = (int, long)
    long = long
    input = raw_input
    decodebytes = base64.decodestring
    encodebytes = base64.encodestring


    def bytestring(s):  # NOQA
        if isinstance(s, unicode):
            return s.encode('utf-8')
        return s


    byte_ord = ord  # NOQA
    byte_chr = chr  # NOQA


    def byte_mask(c, mask):
        return chr(ord(c) & mask)


    def b(s, encoding='utf8'):  # NOQA
        """cast unicode or bytes to bytes"""
        if isinstance(s, str):
            return s
        elif isinstance(s, unicode):
            return s.encode(encoding)
        else:
            raise TypeError("Expected unicode or bytes, got %r" % s)


    def u(s, encoding='utf8'):  # NOQA
        """cast bytes or unicode to unicode"""
        if isinstance(s, str):
            return s.decode(encoding)
        elif isinstance(s, unicode):
            return s
        else:
            raise TypeError("Expected unicode or bytes, got %r" % s)


    def b2s(s):
        return s


    try:
        import cStringIO

        StringIO = cStringIO.StringIO   # NOQA
    except ImportError:
        import StringIO

        StringIO = StringIO.StringIO    # NOQA

    BytesIO = StringIO


    def is_callable(c):  # NOQA
        return callable(c)


    def get_next(c):  # NOQA
        return c.next


    def next(c):
        return c.next()

    # It's possible to have sizeof(long) != sizeof(Py_ssize_t).
    class X(object):
        def __len__(self):
            return 1 << 31


    try:
        len(X())
    except OverflowError:
        # 32-bit
        MAXSIZE = int((1 << 31) - 1)        # NOQA
    else:
        # 64-bit
        MAXSIZE = int((1 << 63) - 1)        # NOQA
    del X
else:
    import collections
    import struct
    string_types = str
    text_type = str
    bytes = bytes
    bytes_types = bytes
    integer_types = int
    class long(int):
        pass
    input = input
    decodebytes = base64.decodebytes
    encodebytes = base64.encodebytes

    def bytestring(s):
        return s

    def byte_ord(c):
        # In case we're handed a string instead of an int.
        if not isinstance(c, int):
            c = ord(c)
        return c

    def byte_chr(c):
        assert isinstance(c, int)
        return struct.pack('B', c)

    def byte_mask(c, mask):
        assert isinstance(c, int)
        return struct.pack('B', c & mask)

    def b(s, encoding='utf8'):
        """cast unicode or bytes to bytes"""
        if isinstance(s, bytes):
            return s
        elif isinstance(s, str):
            return s.encode(encoding)
        else:
            raise TypeError("Expected unicode or bytes, got %r" % s)

    def u(s, encoding='utf8'):
        """cast bytes or unicode to unicode"""
        if isinstance(s, bytes):
            return s.decode(encoding)
        elif isinstance(s, str):
            return s
        else:
            raise TypeError("Expected unicode or bytes, got %r" % s)

    def b2s(s):
        return s.decode() if isinstance(s, bytes) else s

    import io
    StringIO = io.StringIO      # NOQA
    BytesIO = io.BytesIO        # NOQA

    def is_callable(c):
        return isinstance(c, collections.Callable)

    def get_next(c):
        return c.__next__

    next = next

    MAXSIZE = sys.maxsize       # NOQA

########NEW FILE########
__FILENAME__ = resource
# Copyright (C) 2003-2007  Robey Pointer <robeypointer@gmail.com>
#
# This file is part of paramiko.
#
# Paramiko is free software; you can redistribute it and/or modify it under the
# terms of the GNU Lesser General Public License as published by the Free
# Software Foundation; either version 2.1 of the License, or (at your option)
# any later version.
#
# Paramiko is distributed in the hope that it will be useful, but WITHOUT ANY
# WARRANTY; without even the implied warranty of MERCHANTABILITY or FITNESS FOR
# A PARTICULAR PURPOSE.  See the GNU Lesser General Public License for more
# details.
#
# You should have received a copy of the GNU Lesser General Public License
# along with Paramiko; if not, write to the Free Software Foundation, Inc.,
# 59 Temple Place, Suite 330, Boston, MA  02111-1307  USA.

"""
Resource manager.
"""

import weakref


class ResourceManager (object):
    """
    A registry of objects and resources that should be closed when those
    objects are deleted.
    
    This is meant to be a safer alternative to Python's ``__del__`` method,
    which can cause reference cycles to never be collected.  Objects registered
    with the ResourceManager can be collected but still free resources when
    they die.
    
    Resources are registered using `register`, and when an object is garbage
    collected, each registered resource is closed by having its ``close()``
    method called.  Multiple resources may be registered per object, but a
    resource will only be closed once, even if multiple objects register it.
    (The last object to register it wins.)
    """
    
    def __init__(self):
        self._table = {}
        
    def register(self, obj, resource):
        """
        Register a resource to be closed with an object is collected.
        
        When the given ``obj`` is garbage-collected by the Python interpreter,
        the ``resource`` will be closed by having its ``close()`` method called.
        Any exceptions are ignored.
        
        :param object obj: the object to track
        :param object resource:
            the resource to close when the object is collected
        """
        def callback(ref):
            try:
                resource.close()
            except:
                pass
            del self._table[id(resource)]

        # keep the weakref in a table so it sticks around long enough to get
        # its callback called. :)
        self._table[id(resource)] = weakref.ref(obj, callback)


# singleton
ResourceManager = ResourceManager()

########NEW FILE########
__FILENAME__ = rsakey
# Copyright (C) 2003-2007  Robey Pointer <robeypointer@gmail.com>
#
# This file is part of paramiko.
#
# Paramiko is free software; you can redistribute it and/or modify it under the
# terms of the GNU Lesser General Public License as published by the Free
# Software Foundation; either version 2.1 of the License, or (at your option)
# any later version.
#
# Paramiko is distributed in the hope that it will be useful, but WITHOUT ANY
# WARRANTY; without even the implied warranty of MERCHANTABILITY or FITNESS FOR
# A PARTICULAR PURPOSE.  See the GNU Lesser General Public License for more
# details.
#
# You should have received a copy of the GNU Lesser General Public License
# along with Paramiko; if not, write to the Free Software Foundation, Inc.,
# 59 Temple Place, Suite 330, Boston, MA  02111-1307  USA.

"""
RSA keys.
"""

import os
from hashlib import sha1

from Crypto.PublicKey import RSA

from paramiko import util
from paramiko.common import max_byte, zero_byte, one_byte
from paramiko.message import Message
from paramiko.ber import BER, BERException
from paramiko.pkey import PKey
from paramiko.py3compat import long
from paramiko.ssh_exception import SSHException

SHA1_DIGESTINFO = b'\x30\x21\x30\x09\x06\x05\x2b\x0e\x03\x02\x1a\x05\x00\x04\x14'


class RSAKey (PKey):
    """
    Representation of an RSA key which can be used to sign and verify SSH2
    data.
    """

    def __init__(self, msg=None, data=None, filename=None, password=None, vals=None, file_obj=None):
        self.n = None
        self.e = None
        self.d = None
        self.p = None
        self.q = None
        if file_obj is not None:
            self._from_private_key(file_obj, password)
            return
        if filename is not None:
            self._from_private_key_file(filename, password)
            return
        if (msg is None) and (data is not None):
            msg = Message(data)
        if vals is not None:
            self.e, self.n = vals
        else:
            if msg is None:
                raise SSHException('Key object may not be empty')
            if msg.get_text() != 'ssh-rsa':
                raise SSHException('Invalid key')
            self.e = msg.get_mpint()
            self.n = msg.get_mpint()
        self.size = util.bit_length(self.n)

    def asbytes(self):
        m = Message()
        m.add_string('ssh-rsa')
        m.add_mpint(self.e)
        m.add_mpint(self.n)
        return m.asbytes()

    def __str__(self):
        return self.asbytes()

    def __hash__(self):
        h = hash(self.get_name())
        h = h * 37 + hash(self.e)
        h = h * 37 + hash(self.n)
        return hash(h)

    def get_name(self):
        return 'ssh-rsa'

    def get_bits(self):
        return self.size

    def can_sign(self):
        return self.d is not None

    def sign_ssh_data(self, data):
        digest = sha1(data).digest()
        rsa = RSA.construct((long(self.n), long(self.e), long(self.d)))
        sig = util.deflate_long(rsa.sign(self._pkcs1imify(digest), bytes())[0], 0)
        m = Message()
        m.add_string('ssh-rsa')
        m.add_string(sig)
        return m

    def verify_ssh_sig(self, data, msg):
        if msg.get_text() != 'ssh-rsa':
            return False
        sig = util.inflate_long(msg.get_binary(), True)
        # verify the signature by SHA'ing the data and encrypting it using the
        # public key.  some wackiness ensues where we "pkcs1imify" the 20-byte
        # hash into a string as long as the RSA key.
        hash_obj = util.inflate_long(self._pkcs1imify(sha1(data).digest()), True)
        rsa = RSA.construct((long(self.n), long(self.e)))
        return rsa.verify(hash_obj, (sig,))

    def _encode_key(self):
        if (self.p is None) or (self.q is None):
            raise SSHException('Not enough key info to write private key file')
        keylist = [0, self.n, self.e, self.d, self.p, self.q,
                   self.d % (self.p - 1), self.d % (self.q - 1),
                   util.mod_inverse(self.q, self.p)]
        try:
            b = BER()
            b.encode(keylist)
        except BERException:
            raise SSHException('Unable to create ber encoding of key')
        return b.asbytes()

    def write_private_key_file(self, filename, password=None):
        self._write_private_key_file('RSA', filename, self._encode_key(), password)

    def write_private_key(self, file_obj, password=None):
        self._write_private_key('RSA', file_obj, self._encode_key(), password)

    def generate(bits, progress_func=None):
        """
        Generate a new private RSA key.  This factory function can be used to
        generate a new host key or authentication key.

        :param int bits: number of bits the generated key should be.
        :param function progress_func:
            an optional function to call at key points in key generation (used
            by ``pyCrypto.PublicKey``).
        :return: new `.RSAKey` private key
        """
        rsa = RSA.generate(bits, os.urandom, progress_func)
        key = RSAKey(vals=(rsa.e, rsa.n))
        key.d = rsa.d
        key.p = rsa.p
        key.q = rsa.q
        return key
    generate = staticmethod(generate)

    ###  internals...

    def _pkcs1imify(self, data):
        """
        turn a 20-byte SHA1 hash into a blob of data as large as the key's N,
        using PKCS1's \"emsa-pkcs1-v1_5\" encoding.  totally bizarre.
        """
        size = len(util.deflate_long(self.n, 0))
        filler = max_byte * (size - len(SHA1_DIGESTINFO) - len(data) - 3)
        return zero_byte + one_byte + filler + zero_byte + SHA1_DIGESTINFO + data

    def _from_private_key_file(self, filename, password):
        data = self._read_private_key_file('RSA', filename, password)
        self._decode_key(data)

    def _from_private_key(self, file_obj, password):
        data = self._read_private_key('RSA', file_obj, password)
        self._decode_key(data)

    def _decode_key(self, data):
        # private key file contains:
        # RSAPrivateKey = { version = 0, n, e, d, p, q, d mod p-1, d mod q-1, q**-1 mod p }
        try:
            keylist = BER(data).decode()
        except BERException:
            raise SSHException('Unable to parse key file')
        if (type(keylist) is not list) or (len(keylist) < 4) or (keylist[0] != 0):
            raise SSHException('Not a valid RSA private key file (bad ber encoding)')
        self.n = keylist[1]
        self.e = keylist[2]
        self.d = keylist[3]
        # not really needed
        self.p = keylist[4]
        self.q = keylist[5]
        self.size = util.bit_length(self.n)

########NEW FILE########
__FILENAME__ = server
# Copyright (C) 2003-2007  Robey Pointer <robeypointer@gmail.com>
#
# This file is part of paramiko.
#
# Paramiko is free software; you can redistribute it and/or modify it under the
# terms of the GNU Lesser General Public License as published by the Free
# Software Foundation; either version 2.1 of the License, or (at your option)
# any later version.
#
# Paramiko is distributed in the hope that it will be useful, but WITHOUT ANY
# WARRANTY; without even the implied warranty of MERCHANTABILITY or FITNESS FOR
# A PARTICULAR PURPOSE.  See the GNU Lesser General Public License for more
# details.
#
# You should have received a copy of the GNU Lesser General Public License
# along with Paramiko; if not, write to the Free Software Foundation, Inc.,
# 59 Temple Place, Suite 330, Boston, MA  02111-1307  USA.

"""
`.ServerInterface` is an interface to override for server support.
"""

import threading
from paramiko import util
from paramiko.common import DEBUG, ERROR, OPEN_FAILED_ADMINISTRATIVELY_PROHIBITED, AUTH_FAILED
from paramiko.py3compat import string_types


class ServerInterface (object):
    """
    This class defines an interface for controlling the behavior of Paramiko
    in server mode.

    Methods on this class are called from Paramiko's primary thread, so you
    shouldn't do too much work in them.  (Certainly nothing that blocks or
    sleeps.)
    """

    def check_channel_request(self, kind, chanid):
        """
        Determine if a channel request of a given type will be granted, and
        return ``OPEN_SUCCEEDED`` or an error code.  This method is
        called in server mode when the client requests a channel, after
        authentication is complete.

        If you allow channel requests (and an ssh server that didn't would be
        useless), you should also override some of the channel request methods
        below, which are used to determine which services will be allowed on
        a given channel:

            - `check_channel_pty_request`
            - `check_channel_shell_request`
            - `check_channel_subsystem_request`
            - `check_channel_window_change_request`
            - `check_channel_x11_request`
            - `check_channel_forward_agent_request`

        The ``chanid`` parameter is a small number that uniquely identifies the
        channel within a `.Transport`.  A `.Channel` object is not created
        unless this method returns ``OPEN_SUCCEEDED`` -- once a
        `.Channel` object is created, you can call `.Channel.get_id` to
        retrieve the channel ID.

        The return value should either be ``OPEN_SUCCEEDED`` (or
        ``0``) to allow the channel request, or one of the following error
        codes to reject it:

            - ``OPEN_FAILED_ADMINISTRATIVELY_PROHIBITED``
            - ``OPEN_FAILED_CONNECT_FAILED``
            - ``OPEN_FAILED_UNKNOWN_CHANNEL_TYPE``
            - ``OPEN_FAILED_RESOURCE_SHORTAGE``
        
        The default implementation always returns
        ``OPEN_FAILED_ADMINISTRATIVELY_PROHIBITED``.

        :param str kind:
            the kind of channel the client would like to open (usually
            ``"session"``).
        :param int chanid: ID of the channel
        :return: an `int` success or failure code (listed above)
        """
        return OPEN_FAILED_ADMINISTRATIVELY_PROHIBITED

    def get_allowed_auths(self, username):
        """
        Return a list of authentication methods supported by the server.
        This list is sent to clients attempting to authenticate, to inform them
        of authentication methods that might be successful.

        The "list" is actually a string of comma-separated names of types of
        authentication.  Possible values are ``"password"``, ``"publickey"``,
        and ``"none"``.

        The default implementation always returns ``"password"``.

        :param str username: the username requesting authentication.
        :return: a comma-separated `str` of authentication types
        """
        return 'password'

    def check_auth_none(self, username):
        """
        Determine if a client may open channels with no (further)
        authentication.

        Return `.AUTH_FAILED` if the client must authenticate, or
        `.AUTH_SUCCESSFUL` if it's okay for the client to not
        authenticate.

        The default implementation always returns `.AUTH_FAILED`.

        :param str username: the username of the client.
        :return:
            `.AUTH_FAILED` if the authentication fails; `.AUTH_SUCCESSFUL` if
            it succeeds.
        :rtype: int
        """
        return AUTH_FAILED

    def check_auth_password(self, username, password):
        """
        Determine if a given username and password supplied by the client is
        acceptable for use in authentication.

        Return `.AUTH_FAILED` if the password is not accepted,
        `.AUTH_SUCCESSFUL` if the password is accepted and completes
        the authentication, or `.AUTH_PARTIALLY_SUCCESSFUL` if your
        authentication is stateful, and this key is accepted for
        authentication, but more authentication is required.  (In this latter
        case, `get_allowed_auths` will be called to report to the client what
        options it has for continuing the authentication.)

        The default implementation always returns `.AUTH_FAILED`.

        :param str username: the username of the authenticating client.
        :param str password: the password given by the client.
        :return:
            `.AUTH_FAILED` if the authentication fails; `.AUTH_SUCCESSFUL` if
            it succeeds; `.AUTH_PARTIALLY_SUCCESSFUL` if the password auth is
            successful, but authentication must continue.
        :rtype: int
        """
        return AUTH_FAILED

    def check_auth_publickey(self, username, key):
        """
        Determine if a given key supplied by the client is acceptable for use
        in authentication.  You should override this method in server mode to
        check the username and key and decide if you would accept a signature
        made using this key.

        Return `.AUTH_FAILED` if the key is not accepted,
        `.AUTH_SUCCESSFUL` if the key is accepted and completes the
        authentication, or `.AUTH_PARTIALLY_SUCCESSFUL` if your
        authentication is stateful, and this password is accepted for
        authentication, but more authentication is required.  (In this latter
        case, `get_allowed_auths` will be called to report to the client what
        options it has for continuing the authentication.)

        Note that you don't have to actually verify any key signtature here.
        If you're willing to accept the key, Paramiko will do the work of
        verifying the client's signature.
        
        The default implementation always returns `.AUTH_FAILED`.

        :param str username: the username of the authenticating client
        :param .PKey key: the key object provided by the client
        :return:
            `.AUTH_FAILED` if the client can't authenticate with this key;
            `.AUTH_SUCCESSFUL` if it can; `.AUTH_PARTIALLY_SUCCESSFUL` if it
            can authenticate with this key but must continue with
            authentication
        :rtype: int
        """
        return AUTH_FAILED
    
    def check_auth_interactive(self, username, submethods):
        """
        Begin an interactive authentication challenge, if supported.  You
        should override this method in server mode if you want to support the
        ``"keyboard-interactive"`` auth type, which requires you to send a
        series of questions for the client to answer.
        
        Return `.AUTH_FAILED` if this auth method isn't supported.  Otherwise,
        you should return an `.InteractiveQuery` object containing the prompts
        and instructions for the user.  The response will be sent via a call
        to `check_auth_interactive_response`.
        
        The default implementation always returns `.AUTH_FAILED`.
        
        :param str username: the username of the authenticating client
        :param str submethods:
            a comma-separated list of methods preferred by the client (usually
            empty)
        :return:
            `.AUTH_FAILED` if this auth method isn't supported; otherwise an
            object containing queries for the user
        :rtype: int or `.InteractiveQuery`
        """
        return AUTH_FAILED
    
    def check_auth_interactive_response(self, responses):
        """
        Continue or finish an interactive authentication challenge, if
        supported.  You should override this method in server mode if you want
        to support the ``"keyboard-interactive"`` auth type.
        
        Return `.AUTH_FAILED` if the responses are not accepted,
        `.AUTH_SUCCESSFUL` if the responses are accepted and complete
        the authentication, or `.AUTH_PARTIALLY_SUCCESSFUL` if your
        authentication is stateful, and this set of responses is accepted for
        authentication, but more authentication is required.  (In this latter
        case, `get_allowed_auths` will be called to report to the client what
        options it has for continuing the authentication.)

        If you wish to continue interactive authentication with more questions,
        you may return an `.InteractiveQuery` object, which should cause the
        client to respond with more answers, calling this method again.  This
        cycle can continue indefinitely.

        The default implementation always returns `.AUTH_FAILED`.

        :param list responses: list of `str` responses from the client
        :return:
            `.AUTH_FAILED` if the authentication fails; `.AUTH_SUCCESSFUL` if
            it succeeds; `.AUTH_PARTIALLY_SUCCESSFUL` if the interactive auth
            is successful, but authentication must continue; otherwise an
            object containing queries for the user
        :rtype: int or `.InteractiveQuery`
        """
        return AUTH_FAILED
        
    def check_port_forward_request(self, address, port):
        """
        Handle a request for port forwarding.  The client is asking that
        connections to the given address and port be forwarded back across
        this ssh connection.  An address of ``"0.0.0.0"`` indicates a global
        address (any address associated with this server) and a port of ``0``
        indicates that no specific port is requested (usually the OS will pick
        a port).
        
        The default implementation always returns ``False``, rejecting the
        port forwarding request.  If the request is accepted, you should return
        the port opened for listening.
        
        :param str address: the requested address
        :param int port: the requested port
        :return:
            the port number (`int`) that was opened for listening, or ``False``
            to reject
        """
        return False
    
    def cancel_port_forward_request(self, address, port):
        """
        The client would like to cancel a previous port-forwarding request.
        If the given address and port is being forwarded across this ssh
        connection, the port should be closed.
        
        :param str address: the forwarded address
        :param int port: the forwarded port
        """
        pass
        
    def check_global_request(self, kind, msg):
        """
        Handle a global request of the given ``kind``.  This method is called
        in server mode and client mode, whenever the remote host makes a global
        request.  If there are any arguments to the request, they will be in
        ``msg``.

        There aren't any useful global requests defined, aside from port
        forwarding, so usually this type of request is an extension to the
        protocol.

        If the request was successful and you would like to return contextual
        data to the remote host, return a tuple.  Items in the tuple will be
        sent back with the successful result.  (Note that the items in the
        tuple can only be strings, ints, longs, or bools.)

        The default implementation always returns ``False``, indicating that it
        does not support any global requests.
        
        .. note:: Port forwarding requests are handled separately, in
            `check_port_forward_request`.

        :param str kind: the kind of global request being made.
        :param .Message msg: any extra arguments to the request.
        :return:
            ``True`` or a `tuple` of data if the request was granted; ``False``
            otherwise.
        """
        return False

    ###  Channel requests

    def check_channel_pty_request(self, channel, term, width, height, pixelwidth, pixelheight,
                                  modes):
        """
        Determine if a pseudo-terminal of the given dimensions (usually
        requested for shell access) can be provided on the given channel.

        The default implementation always returns ``False``.

        :param .Channel channel: the `.Channel` the pty request arrived on.
        :param str term: type of terminal requested (for example, ``"vt100"``).
        :param int width: width of screen in characters.
        :param int height: height of screen in characters.
        :param int pixelwidth:
            width of screen in pixels, if known (may be ``0`` if unknown).
        :param int pixelheight:
            height of screen in pixels, if known (may be ``0`` if unknown).
        :return:
            ``True`` if the psuedo-terminal has been allocated; ``False``
            otherwise.
        """
        return False

    def check_channel_shell_request(self, channel):
        """
        Determine if a shell will be provided to the client on the given
        channel.  If this method returns ``True``, the channel should be
        connected to the stdin/stdout of a shell (or something that acts like
        a shell).

        The default implementation always returns ``False``.

        :param .Channel channel: the `.Channel` the request arrived on.
        :return:
            ``True`` if this channel is now hooked up to a shell; ``False`` if
            a shell can't or won't be provided.
        """
        return False

    def check_channel_exec_request(self, channel, command):
        """
        Determine if a shell command will be executed for the client.  If this
        method returns ``True``, the channel should be connected to the stdin,
        stdout, and stderr of the shell command.
        
        The default implementation always returns ``False``.
        
        :param .Channel channel: the `.Channel` the request arrived on.
        :param str command: the command to execute.
        :return:
            ``True`` if this channel is now hooked up to the stdin, stdout, and
            stderr of the executing command; ``False`` if the command will not
            be executed.
        
        .. versionadded:: 1.1
        """
        return False
        
    def check_channel_subsystem_request(self, channel, name):
        """
        Determine if a requested subsystem will be provided to the client on
        the given channel.  If this method returns ``True``, all future I/O
        through this channel will be assumed to be connected to the requested
        subsystem.  An example of a subsystem is ``sftp``.

        The default implementation checks for a subsystem handler assigned via
        `.Transport.set_subsystem_handler`.
        If one has been set, the handler is invoked and this method returns
        ``True``.  Otherwise it returns ``False``.

        .. note:: Because the default implementation uses the `.Transport` to
            identify valid subsystems, you probably won't need to override this
            method.

        :param .Channel channel: the `.Channel` the pty request arrived on.
        :param str name: name of the requested subsystem.
        :return:
            ``True`` if this channel is now hooked up to the requested
            subsystem; ``False`` if that subsystem can't or won't be provided.
        """
        handler_class, larg, kwarg = channel.get_transport()._get_subsystem_handler(name)
        if handler_class is None:
            return False
        handler = handler_class(channel, name, self, *larg, **kwarg)
        handler.start()
        return True

    def check_channel_window_change_request(self, channel, width, height, pixelwidth, pixelheight):
        """
        Determine if the pseudo-terminal on the given channel can be resized.
        This only makes sense if a pty was previously allocated on it.

        The default implementation always returns ``False``.

        :param .Channel channel: the `.Channel` the pty request arrived on.
        :param int width: width of screen in characters.
        :param int height: height of screen in characters.
        :param int pixelwidth:
            width of screen in pixels, if known (may be ``0`` if unknown).
        :param int pixelheight:
            height of screen in pixels, if known (may be ``0`` if unknown).
        :return: ``True`` if the terminal was resized; ``False`` if not.
        """
        return False
    
    def check_channel_x11_request(self, channel, single_connection, auth_protocol, auth_cookie, screen_number):
        """
        Determine if the client will be provided with an X11 session.  If this
        method returns ``True``, X11 applications should be routed through new
        SSH channels, using `.Transport.open_x11_channel`.
        
        The default implementation always returns ``False``.
        
        :param .Channel channel: the `.Channel` the X11 request arrived on
        :param bool single_connection:
            ``True`` if only a single X11 channel should be opened, else
            ``False``.
        :param str auth_protocol: the protocol used for X11 authentication
        :param str auth_cookie: the cookie used to authenticate to X11
        :param int screen_number: the number of the X11 screen to connect to
        :return: ``True`` if the X11 session was opened; ``False`` if not
        """
        return False

    def check_channel_forward_agent_request(self, channel):
        """
        Determine if the client will be provided with an forward agent session.
        If this method returns ``True``, the server will allow SSH Agent
        forwarding.

        The default implementation always returns ``False``.

        :param .Channel channel: the `.Channel` the request arrived on
        :return: ``True`` if the AgentForward was loaded; ``False`` if not
        """
        return False

    def check_channel_direct_tcpip_request(self, chanid, origin, destination):
        """
        Determine if a local port forwarding channel will be granted, and
        return ``OPEN_SUCCEEDED`` or an error code.  This method is
        called in server mode when the client requests a channel, after
        authentication is complete.

        The ``chanid`` parameter is a small number that uniquely identifies the
        channel within a `.Transport`.  A `.Channel` object is not created
        unless this method returns ``OPEN_SUCCEEDED`` -- once a
        `.Channel` object is created, you can call `.Channel.get_id` to
        retrieve the channel ID.

        The origin and destination parameters are (ip_address, port) tuples
        that correspond to both ends of the TCP connection in the forwarding
        tunnel.

        The return value should either be ``OPEN_SUCCEEDED`` (or
        ``0``) to allow the channel request, or one of the following error
        codes to reject it:

            - ``OPEN_FAILED_ADMINISTRATIVELY_PROHIBITED``
            - ``OPEN_FAILED_CONNECT_FAILED``
            - ``OPEN_FAILED_UNKNOWN_CHANNEL_TYPE``
            - ``OPEN_FAILED_RESOURCE_SHORTAGE``
        
        The default implementation always returns
        ``OPEN_FAILED_ADMINISTRATIVELY_PROHIBITED``.

        :param int chanid: ID of the channel
        :param tuple origin:
            2-tuple containing the IP address and port of the originator
            (client side)
        :param tuple destination:
            2-tuple containing the IP address and port of the destination
            (server side)
        :return: an `int` success or failure code (listed above)
        """
        return OPEN_FAILED_ADMINISTRATIVELY_PROHIBITED

    def check_channel_env_request(self, channel, name, value):
        """
        Check whether a given environment variable can be specified for the
        given channel.  This method should return C{True} if the server
        is willing to set the specified environment variable.  Note that
        some environment variables (e.g., PATH) can be exceedingly
        dangerous, so blindly allowing the client to set the environment
        is almost certainly not a good idea.

        The default implementation always returns C{False}.

        @param channel: the L{Channel} the env request arrived on
        @type channel: L{Channel}
        @param name: foo bar baz
        @type name: str
        @param value: flklj
        @type value: str
        @rtype: bool
        """
        return False


class InteractiveQuery (object):
    """
    A query (set of prompts) for a user during interactive authentication.
    """
    
    def __init__(self, name='', instructions='', *prompts):
        """
        Create a new interactive query to send to the client.  The name and
        instructions are optional, but are generally displayed to the end
        user.  A list of prompts may be included, or they may be added via
        the `add_prompt` method.
        
        :param str name: name of this query
        :param str instructions:
            user instructions (usually short) about this query
        :param str prompts: one or more authentication prompts
        """
        self.name = name
        self.instructions = instructions
        self.prompts = []
        for x in prompts:
            if isinstance(x, string_types):
                self.add_prompt(x)
            else:
                self.add_prompt(x[0], x[1])
    
    def add_prompt(self, prompt, echo=True):
        """
        Add a prompt to this query.  The prompt should be a (reasonably short)
        string.  Multiple prompts can be added to the same query.
        
        :param str prompt: the user prompt
        :param bool echo:
            ``True`` (default) if the user's response should be echoed;
            ``False`` if not (for a password or similar)
        """
        self.prompts.append((prompt, echo))


class SubsystemHandler (threading.Thread):
    """
    Handler for a subsytem in server mode.  If you create a subclass of this
    class and pass it to `.Transport.set_subsystem_handler`, an object of this
    class will be created for each request for this subsystem.  Each new object
    will be executed within its own new thread by calling `start_subsystem`.
    When that method completes, the channel is closed.

    For example, if you made a subclass ``MP3Handler`` and registered it as the
    handler for subsystem ``"mp3"``, then whenever a client has successfully
    authenticated and requests subsytem ``"mp3"``, an object of class
    ``MP3Handler`` will be created, and `start_subsystem` will be called on
    it from a new thread.
    """
    def __init__(self, channel, name, server):
        """
        Create a new handler for a channel.  This is used by `.ServerInterface`
        to start up a new handler when a channel requests this subsystem.  You
        don't need to override this method, but if you do, be sure to pass the
        ``channel`` and ``name`` parameters through to the original ``__init__``
        method here.

        :param .Channel channel: the channel associated with this subsystem request.
        :param str name: name of the requested subsystem.
        :param .ServerInterface server:
            the server object for the session that started this subsystem
        """
        threading.Thread.__init__(self, target=self._run)
        self.__channel = channel
        self.__transport = channel.get_transport()
        self.__name = name
        self.__server = server
        
    def get_server(self):
        """
        Return the `.ServerInterface` object associated with this channel and
        subsystem.
        """
        return self.__server

    def _run(self):
        try:
            self.__transport._log(DEBUG, 'Starting handler for subsystem %s' % self.__name)
            self.start_subsystem(self.__name, self.__transport, self.__channel)
        except Exception as e:
            self.__transport._log(ERROR, 'Exception in subsystem handler for "%s": %s' %
                                  (self.__name, str(e)))
            self.__transport._log(ERROR, util.tb_strings())
        try:
            self.finish_subsystem()
        except:
            pass

    def start_subsystem(self, name, transport, channel):
        """
        Process an ssh subsystem in server mode.  This method is called on a
        new object (and in a new thread) for each subsystem request.  It is
        assumed that all subsystem logic will take place here, and when the
        subsystem is finished, this method will return.  After this method
        returns, the channel is closed.

        The combination of ``transport`` and ``channel`` are unique; this handler
        corresponds to exactly one `.Channel` on one `.Transport`.

        .. note::
            It is the responsibility of this method to exit if the underlying
            `.Transport` is closed.  This can be done by checking
            `.Transport.is_active` or noticing an EOF on the `.Channel`.  If
            this method loops forever without checking for this case, your
            Python interpreter may refuse to exit because this thread will
            still be running.

        :param str name: name of the requested subsystem.
        :param .Transport transport: the server-mode `.Transport`.
        :param .Channel channel: the channel associated with this subsystem request.
        """
        pass

    def finish_subsystem(self):
        """
        Perform any cleanup at the end of a subsystem.  The default
        implementation just closes the channel.

        .. versionadded:: 1.1
        """
        self.__channel.close()

########NEW FILE########
__FILENAME__ = sftp
# Copyright (C) 2003-2007  Robey Pointer <robeypointer@gmail.com>
#
# This file is part of paramiko.
#
# Paramiko is free software; you can redistribute it and/or modify it under the
# terms of the GNU Lesser General Public License as published by the Free
# Software Foundation; either version 2.1 of the License, or (at your option)
# any later version.
#
# Paramiko is distributed in the hope that it will be useful, but WITHOUT ANY
# WARRANTY; without even the implied warranty of MERCHANTABILITY or FITNESS FOR
# A PARTICULAR PURPOSE.  See the GNU Lesser General Public License for more
# details.
#
# You should have received a copy of the GNU Lesser General Public License
# along with Paramiko; if not, write to the Free Software Foundation, Inc.,
# 59 Temple Place, Suite 330, Boston, MA  02111-1307  USA.

import select
import socket
import struct

from paramiko import util
from paramiko.common import asbytes, DEBUG
from paramiko.message import Message
from paramiko.py3compat import byte_chr, byte_ord


CMD_INIT, CMD_VERSION, CMD_OPEN, CMD_CLOSE, CMD_READ, CMD_WRITE, CMD_LSTAT, CMD_FSTAT, \
    CMD_SETSTAT, CMD_FSETSTAT, CMD_OPENDIR, CMD_READDIR, CMD_REMOVE, CMD_MKDIR, \
    CMD_RMDIR, CMD_REALPATH, CMD_STAT, CMD_RENAME, CMD_READLINK, CMD_SYMLINK = range(1, 21)
CMD_STATUS, CMD_HANDLE, CMD_DATA, CMD_NAME, CMD_ATTRS = range(101, 106)
CMD_EXTENDED, CMD_EXTENDED_REPLY = range(200, 202)

SFTP_OK = 0
SFTP_EOF, SFTP_NO_SUCH_FILE, SFTP_PERMISSION_DENIED, SFTP_FAILURE, SFTP_BAD_MESSAGE, \
    SFTP_NO_CONNECTION, SFTP_CONNECTION_LOST, SFTP_OP_UNSUPPORTED = range(1, 9)

SFTP_DESC = ['Success',
             'End of file',
             'No such file',
             'Permission denied',
             'Failure',
             'Bad message',
             'No connection',
             'Connection lost',
             'Operation unsupported']

SFTP_FLAG_READ = 0x1
SFTP_FLAG_WRITE = 0x2
SFTP_FLAG_APPEND = 0x4
SFTP_FLAG_CREATE = 0x8
SFTP_FLAG_TRUNC = 0x10
SFTP_FLAG_EXCL = 0x20

_VERSION = 3


# for debugging
CMD_NAMES = {
    CMD_INIT: 'init',
    CMD_VERSION: 'version',
    CMD_OPEN: 'open',
    CMD_CLOSE: 'close',
    CMD_READ: 'read',
    CMD_WRITE: 'write',
    CMD_LSTAT: 'lstat',
    CMD_FSTAT: 'fstat',
    CMD_SETSTAT: 'setstat',
    CMD_FSETSTAT: 'fsetstat',
    CMD_OPENDIR: 'opendir',
    CMD_READDIR: 'readdir',
    CMD_REMOVE: 'remove',
    CMD_MKDIR: 'mkdir',
    CMD_RMDIR: 'rmdir',
    CMD_REALPATH: 'realpath',
    CMD_STAT: 'stat',
    CMD_RENAME: 'rename',
    CMD_READLINK: 'readlink',
    CMD_SYMLINK: 'symlink',
    CMD_STATUS: 'status',
    CMD_HANDLE: 'handle',
    CMD_DATA: 'data',
    CMD_NAME: 'name',
    CMD_ATTRS: 'attrs',
    CMD_EXTENDED: 'extended',
    CMD_EXTENDED_REPLY: 'extended_reply'
}


class SFTPError (Exception):
    pass


class BaseSFTP (object):
    def __init__(self):
        self.logger = util.get_logger('paramiko.sftp')
        self.sock = None
        self.ultra_debug = False

    ###  internals...

    def _send_version(self):
        self._send_packet(CMD_INIT, struct.pack('>I', _VERSION))
        t, data = self._read_packet()
        if t != CMD_VERSION:
            raise SFTPError('Incompatible sftp protocol')
        version = struct.unpack('>I', data[:4])[0]
        #        if version != _VERSION:
        #            raise SFTPError('Incompatible sftp protocol')
        return version

    def _send_server_version(self):
        # winscp will freak out if the server sends version info before the
        # client finishes sending INIT.
        t, data = self._read_packet()
        if t != CMD_INIT:
            raise SFTPError('Incompatible sftp protocol')
        version = struct.unpack('>I', data[:4])[0]
        # advertise that we support "check-file"
        extension_pairs = ['check-file', 'md5,sha1']
        msg = Message()
        msg.add_int(_VERSION)
        msg.add(*extension_pairs)
        self._send_packet(CMD_VERSION, msg)
        return version
        
    def _log(self, level, msg, *args):
        self.logger.log(level, msg, *args)

    def _write_all(self, out):
        while len(out) > 0:
            n = self.sock.send(out)
            if n <= 0:
                raise EOFError()
            if n == len(out):
                return
            out = out[n:]
        return

    def _read_all(self, n):
        out = bytes()
        while n > 0:
            if isinstance(self.sock, socket.socket):
                # sometimes sftp is used directly over a socket instead of
                # through a paramiko channel.  in this case, check periodically
                # if the socket is closed.  (for some reason, recv() won't ever
                # return or raise an exception, but calling select on a closed
                # socket will.)
                while True:
                    read, write, err = select.select([self.sock], [], [], 0.1)
                    if len(read) > 0:
                        x = self.sock.recv(n)
                        break
            else:
                x = self.sock.recv(n)
                
            if len(x) == 0:
                raise EOFError()
            out += x
            n -= len(x)
        return out

    def _send_packet(self, t, packet):
        #self._log(DEBUG2, 'write: %s (len=%d)' % (CMD_NAMES.get(t, '0x%02x' % t), len(packet)))
        packet = asbytes(packet)
        out = struct.pack('>I', len(packet) + 1) + byte_chr(t) + packet
        if self.ultra_debug:
            self._log(DEBUG, util.format_binary(out, 'OUT: '))
        self._write_all(out)

    def _read_packet(self):
        x = self._read_all(4)
        # most sftp servers won't accept packets larger than about 32k, so
        # anything with the high byte set (> 16MB) is just garbage.
        if byte_ord(x[0]):
            raise SFTPError('Garbage packet received')
        size = struct.unpack('>I', x)[0]
        data = self._read_all(size)
        if self.ultra_debug:
            self._log(DEBUG, util.format_binary(data, 'IN: '))
        if size > 0:
            t = byte_ord(data[0])
            #self._log(DEBUG2, 'read: %s (len=%d)' % (CMD_NAMES.get(t), '0x%02x' % t, len(data)-1))
            return t, data[1:]
        return 0, bytes()

########NEW FILE########
__FILENAME__ = sftp_attr
# Copyright (C) 2003-2006 Robey Pointer <robeypointer@gmail.com>
#
# This file is part of paramiko.
#
# Paramiko is free software; you can redistribute it and/or modify it under the
# terms of the GNU Lesser General Public License as published by the Free
# Software Foundation; either version 2.1 of the License, or (at your option)
# any later version.
#
# Paramiko is distributed in the hope that it will be useful, but WITHOUT ANY
# WARRANTY; without even the implied warranty of MERCHANTABILITY or FITNESS FOR
# A PARTICULAR PURPOSE.  See the GNU Lesser General Public License for more
# details.
#
# You should have received a copy of the GNU Lesser General Public License
# along with Paramiko; if not, write to the Free Software Foundation, Inc.,
# 59 Temple Place, Suite 330, Boston, MA  02111-1307  USA.

import stat
import time
from paramiko.common import x80000000, o700, o70, xffffffff
from paramiko.py3compat import long, b


class SFTPAttributes (object):
    """
    Representation of the attributes of a file (or proxied file) for SFTP in
    client or server mode.  It attemps to mirror the object returned by
    `os.stat` as closely as possible, so it may have the following fields,
    with the same meanings as those returned by an `os.stat` object:

        - ``st_size``
        - ``st_uid``
        - ``st_gid``
        - ``st_mode``
        - ``st_atime``
        - ``st_mtime``

    Because SFTP allows flags to have other arbitrary named attributes, these
    are stored in a dict named ``attr``.  Occasionally, the filename is also
    stored, in ``filename``.
    """

    FLAG_SIZE = 1
    FLAG_UIDGID = 2
    FLAG_PERMISSIONS = 4
    FLAG_AMTIME = 8
    FLAG_EXTENDED = x80000000

    def __init__(self):
        """
        Create a new (empty) SFTPAttributes object.  All fields will be empty.
        """
        self._flags = 0
        self.st_size = None
        self.st_uid = None
        self.st_gid = None
        self.st_mode = None
        self.st_atime = None
        self.st_mtime = None
        self.attr = {}

    def from_stat(cls, obj, filename=None):
        """
        Create an `.SFTPAttributes` object from an existing ``stat`` object (an
        object returned by `os.stat`).

        :param object obj: an object returned by `os.stat` (or equivalent).
        :param str filename: the filename associated with this file.
        :return: new `.SFTPAttributes` object with the same attribute fields.
        """
        attr = cls()
        attr.st_size = obj.st_size
        attr.st_uid = obj.st_uid
        attr.st_gid = obj.st_gid
        attr.st_mode = obj.st_mode
        attr.st_atime = obj.st_atime
        attr.st_mtime = obj.st_mtime
        if filename is not None:
            attr.filename = filename
        return attr
    from_stat = classmethod(from_stat)

    def __repr__(self):
        return '<SFTPAttributes: %s>' % self._debug_str()

    ###  internals...

    def _from_msg(cls, msg, filename=None, longname=None):
        attr = cls()
        attr._unpack(msg)
        if filename is not None:
            attr.filename = filename
        if longname is not None:
            attr.longname = longname
        return attr
    _from_msg = classmethod(_from_msg)

    def _unpack(self, msg):
        self._flags = msg.get_int()
        if self._flags & self.FLAG_SIZE:
            self.st_size = msg.get_int64()
        if self._flags & self.FLAG_UIDGID:
            self.st_uid = msg.get_int()
            self.st_gid = msg.get_int()
        if self._flags & self.FLAG_PERMISSIONS:
            self.st_mode = msg.get_int()
        if self._flags & self.FLAG_AMTIME:
            self.st_atime = msg.get_int()
            self.st_mtime = msg.get_int()
        if self._flags & self.FLAG_EXTENDED:
            count = msg.get_int()
            for i in range(count):
                self.attr[msg.get_string()] = msg.get_string()

    def _pack(self, msg):
        self._flags = 0
        if self.st_size is not None:
            self._flags |= self.FLAG_SIZE
        if (self.st_uid is not None) and (self.st_gid is not None):
            self._flags |= self.FLAG_UIDGID
        if self.st_mode is not None:
            self._flags |= self.FLAG_PERMISSIONS
        if (self.st_atime is not None) and (self.st_mtime is not None):
            self._flags |= self.FLAG_AMTIME
        if len(self.attr) > 0:
            self._flags |= self.FLAG_EXTENDED
        msg.add_int(self._flags)
        if self._flags & self.FLAG_SIZE:
            msg.add_int64(self.st_size)
        if self._flags & self.FLAG_UIDGID:
            msg.add_int(self.st_uid)
            msg.add_int(self.st_gid)
        if self._flags & self.FLAG_PERMISSIONS:
            msg.add_int(self.st_mode)
        if self._flags & self.FLAG_AMTIME:
            # throw away any fractional seconds
            msg.add_int(long(self.st_atime))
            msg.add_int(long(self.st_mtime))
        if self._flags & self.FLAG_EXTENDED:
            msg.add_int(len(self.attr))
            for key, val in self.attr.items():
                msg.add_string(key)
                msg.add_string(val)
        return

    def _debug_str(self):
        out = '[ '
        if self.st_size is not None:
            out += 'size=%d ' % self.st_size
        if (self.st_uid is not None) and (self.st_gid is not None):
            out += 'uid=%d gid=%d ' % (self.st_uid, self.st_gid)
        if self.st_mode is not None:
            out += 'mode=' + oct(self.st_mode) + ' '
        if (self.st_atime is not None) and (self.st_mtime is not None):
            out += 'atime=%d mtime=%d ' % (self.st_atime, self.st_mtime)
        for k, v in self.attr.items():
            out += '"%s"=%r ' % (str(k), v)
        out += ']'
        return out

    def _rwx(n, suid, sticky=False):
        if suid:
            suid = 2
        out = '-r'[n >> 2] + '-w'[(n >> 1) & 1]
        if sticky:
            out += '-xTt'[suid + (n & 1)]
        else:
            out += '-xSs'[suid + (n & 1)]
        return out
    _rwx = staticmethod(_rwx)

    def __str__(self):
        """create a unix-style long description of the file (like ls -l)"""
        if self.st_mode is not None:
            kind = stat.S_IFMT(self.st_mode)
            if kind == stat.S_IFIFO:
                ks = 'p'
            elif kind == stat.S_IFCHR:
                ks = 'c'
            elif kind == stat.S_IFDIR:
                ks = 'd'
            elif kind == stat.S_IFBLK:
                ks = 'b'
            elif kind == stat.S_IFREG:
                ks = '-'
            elif kind == stat.S_IFLNK:
                ks = 'l'
            elif kind == stat.S_IFSOCK:
                ks = 's'
            else:
                ks = '?'
            ks += self._rwx((self.st_mode & o700) >> 6, self.st_mode & stat.S_ISUID)
            ks += self._rwx((self.st_mode & o70) >> 3, self.st_mode & stat.S_ISGID)
            ks += self._rwx(self.st_mode & 7, self.st_mode & stat.S_ISVTX, True)
        else:
            ks = '?---------'
        # compute display date
        if (self.st_mtime is None) or (self.st_mtime == xffffffff):
            # shouldn't really happen
            datestr = '(unknown date)'
        else:
            if abs(time.time() - self.st_mtime) > 15552000:
                # (15552000 = 6 months)
                datestr = time.strftime('%d %b %Y', time.localtime(self.st_mtime))
            else:
                datestr = time.strftime('%d %b %H:%M', time.localtime(self.st_mtime))
        filename = getattr(self, 'filename', '?')

        # not all servers support uid/gid
        uid = self.st_uid
        gid = self.st_gid
        if uid is None:
            uid = 0
        if gid is None:
            gid = 0

        return '%s   1 %-8d %-8d %8d %-12s %s' % (ks, uid, gid, self.st_size, datestr, filename)

    def asbytes(self):
        return b(str(self))

########NEW FILE########
__FILENAME__ = sftp_client
# Copyright (C) 2003-2007  Robey Pointer <robeypointer@gmail.com>
#
# This file is part of Paramiko.
#
# Paramiko is free software; you can redistribute it and/or modify it under the
# terms of the GNU Lesser General Public License as published by the Free
# Software Foundation; either version 2.1 of the License, or (at your option)
# any later version.
#
# Paramiko is distributed in the hope that it will be useful, but WITHOUT ANY
# WARRANTY; without even the implied warranty of MERCHANTABILITY or FITNESS FOR
# A PARTICULAR PURPOSE.  See the GNU Lesser General Public License for more
# details.
#
# You should have received a copy of the GNU Lesser General Public License
# along with Paramiko; if not, write to the Free Software Foundation, Inc.,
# 59 Temple Place, Suite 330, Boston, MA  02111-1307  USA.


from binascii import hexlify
import errno
import os
import stat
import threading
import time
import weakref
from paramiko import util
from paramiko.channel import Channel
from paramiko.message import Message
from paramiko.common import INFO, DEBUG, o777
from paramiko.py3compat import bytestring, b, u, long, string_types, bytes_types
from paramiko.sftp import BaseSFTP, CMD_OPENDIR, CMD_HANDLE, SFTPError, CMD_READDIR, \
    CMD_NAME, CMD_CLOSE, SFTP_FLAG_READ, SFTP_FLAG_WRITE, SFTP_FLAG_CREATE, \
    SFTP_FLAG_TRUNC, SFTP_FLAG_APPEND, SFTP_FLAG_EXCL, CMD_OPEN, CMD_REMOVE, \
    CMD_RENAME, CMD_MKDIR, CMD_RMDIR, CMD_STAT, CMD_ATTRS, CMD_LSTAT, \
    CMD_SYMLINK, CMD_SETSTAT, CMD_READLINK, CMD_REALPATH, CMD_STATUS, SFTP_OK, \
    SFTP_EOF, SFTP_NO_SUCH_FILE, SFTP_PERMISSION_DENIED

from paramiko.sftp_attr import SFTPAttributes
from paramiko.ssh_exception import SSHException
from paramiko.sftp_file import SFTPFile


def _to_unicode(s):
    """
    decode a string as ascii or utf8 if possible (as required by the sftp
    protocol).  if neither works, just return a byte string because the server
    probably doesn't know the filename's encoding.
    """
    try:
        return s.encode('ascii')
    except (UnicodeError, AttributeError):
        try:
            return s.decode('utf-8')
        except UnicodeError:
            return s

b_slash = b'/'


class SFTPClient(BaseSFTP):
    """
    SFTP client object.
    
    Used to open an SFTP session across an open SSH `.Transport` and perform
    remote file operations.
    """
    def __init__(self, sock):
        """
        Create an SFTP client from an existing `.Channel`.  The channel
        should already have requested the ``"sftp"`` subsystem.

        An alternate way to create an SFTP client context is by using
        `from_transport`.

        :param .Channel sock: an open `.Channel` using the ``"sftp"`` subsystem

        :raises SSHException: if there's an exception while negotiating
            sftp
        """
        BaseSFTP.__init__(self)
        self.sock = sock
        self.ultra_debug = False
        self.request_number = 1
        # lock for request_number
        self._lock = threading.Lock()
        self._cwd = None
        # request # -> SFTPFile
        self._expecting = weakref.WeakValueDictionary()
        if type(sock) is Channel:
            # override default logger
            transport = self.sock.get_transport()
            self.logger = util.get_logger(transport.get_log_channel() + '.sftp')
            self.ultra_debug = transport.get_hexdump()
        try:
            server_version = self._send_version()
        except EOFError:
            raise SSHException('EOF during negotiation')
        self._log(INFO, 'Opened sftp connection (server version %d)' % server_version)

    def from_transport(cls, t):
        """
        Create an SFTP client channel from an open `.Transport`.

        :param .Transport t: an open `.Transport` which is already authenticated
        :return:
            a new `.SFTPClient` object, referring to an sftp session (channel)
            across the transport
        """
        chan = t.open_session()
        if chan is None:
            return None
        chan.invoke_subsystem('sftp')
        return cls(chan)
    from_transport = classmethod(from_transport)

    def _log(self, level, msg, *args):
        if isinstance(msg, list):
            for m in msg:
                self._log(level, m, *args)
        else:
            # escape '%' in msg (they could come from file or directory names) before logging
            msg = msg.replace('%','%%')
            super(SFTPClient, self)._log(level, "[chan %s] " + msg, *([self.sock.get_name()] + list(args)))

    def close(self):
        """
        Close the SFTP session and its underlying channel.

        .. versionadded:: 1.4
        """
        self._log(INFO, 'sftp session closed.')
        self.sock.close()

    def get_channel(self):
        """
        Return the underlying `.Channel` object for this SFTP session.  This
        might be useful for doing things like setting a timeout on the channel.

        .. versionadded:: 1.7.1
        """
        return self.sock

    def listdir(self, path='.'):
        """
        Return a list containing the names of the entries in the given ``path``.

        The list is in arbitrary order.  It does not include the special
        entries ``'.'`` and ``'..'`` even if they are present in the folder.
        This method is meant to mirror ``os.listdir`` as closely as possible.
        For a list of full `.SFTPAttributes` objects, see `listdir_attr`.

        :param str path: path to list (defaults to ``'.'``)
        """
        return [f.filename for f in self.listdir_attr(path)]

    def listdir_attr(self, path='.'):
        """
        Return a list containing `.SFTPAttributes` objects corresponding to
        files in the given ``path``.  The list is in arbitrary order.  It does
        not include the special entries ``'.'`` and ``'..'`` even if they are
        present in the folder.

        The returned `.SFTPAttributes` objects will each have an additional
        field: ``longname``, which may contain a formatted string of the file's
        attributes, in unix format.  The content of this string will probably
        depend on the SFTP server implementation.

        :param str path: path to list (defaults to ``'.'``)
        :return: list of `.SFTPAttributes` objects

        .. versionadded:: 1.2
        """
        path = self._adjust_cwd(path)
        self._log(DEBUG, 'listdir(%r)' % path)
        t, msg = self._request(CMD_OPENDIR, path)
        if t != CMD_HANDLE:
            raise SFTPError('Expected handle')
        handle = msg.get_binary()
        filelist = []
        while True:
            try:
                t, msg = self._request(CMD_READDIR, handle)
            except EOFError:
                # done with handle
                break
            if t != CMD_NAME:
                raise SFTPError('Expected name response')
            count = msg.get_int()
            for i in range(count):
                filename = msg.get_text()
                longname = msg.get_text()
                attr = SFTPAttributes._from_msg(msg, filename, longname)
                if (filename != '.') and (filename != '..'):
                    filelist.append(attr)
        self._request(CMD_CLOSE, handle)
        return filelist

    def open(self, filename, mode='r', bufsize=-1):
        """
        Open a file on the remote server.  The arguments are the same as for
        Python's built-in `python:file` (aka `python:open`).  A file-like
        object is returned, which closely mimics the behavior of a normal
        Python file object, including the ability to be used as a context
        manager.

        The mode indicates how the file is to be opened: ``'r'`` for reading,
        ``'w'`` for writing (truncating an existing file), ``'a'`` for
        appending, ``'r+'`` for reading/writing, ``'w+'`` for reading/writing
        (truncating an existing file), ``'a+'`` for reading/appending.  The
        Python ``'b'`` flag is ignored, since SSH treats all files as binary.
        The ``'U'`` flag is supported in a compatible way.

        Since 1.5.2, an ``'x'`` flag indicates that the operation should only
        succeed if the file was created and did not previously exist.  This has
        no direct mapping to Python's file flags, but is commonly known as the
        ``O_EXCL`` flag in posix.

        The file will be buffered in standard Python style by default, but
        can be altered with the ``bufsize`` parameter.  ``0`` turns off
        buffering, ``1`` uses line buffering, and any number greater than 1
        (``>1``) uses that specific buffer size.

        :param str filename: name of the file to open
        :param str mode: mode (Python-style) to open in
        :param int bufsize: desired buffering (-1 = default buffer size)
        :return: an `.SFTPFile` object representing the open file

        :raises IOError: if the file could not be opened.
        """
        filename = self._adjust_cwd(filename)
        self._log(DEBUG, 'open(%r, %r)' % (filename, mode))
        imode = 0
        if ('r' in mode) or ('+' in mode):
            imode |= SFTP_FLAG_READ
        if ('w' in mode) or ('+' in mode) or ('a' in mode):
            imode |= SFTP_FLAG_WRITE
        if 'w' in mode:
            imode |= SFTP_FLAG_CREATE | SFTP_FLAG_TRUNC
        if 'a' in mode:
            imode |= SFTP_FLAG_CREATE | SFTP_FLAG_APPEND
        if 'x' in mode:
            imode |= SFTP_FLAG_CREATE | SFTP_FLAG_EXCL
        attrblock = SFTPAttributes()
        t, msg = self._request(CMD_OPEN, filename, imode, attrblock)
        if t != CMD_HANDLE:
            raise SFTPError('Expected handle')
        handle = msg.get_binary()
        self._log(DEBUG, 'open(%r, %r) -> %s' % (filename, mode, hexlify(handle)))
        return SFTPFile(self, handle, mode, bufsize)

    # Python continues to vacillate about "open" vs "file"...
    file = open

    def remove(self, path):
        """
        Remove the file at the given path.  This only works on files; for
        removing folders (directories), use `rmdir`.

        :param str path: path (absolute or relative) of the file to remove

        :raises IOError: if the path refers to a folder (directory)
        """
        path = self._adjust_cwd(path)
        self._log(DEBUG, 'remove(%r)' % path)
        self._request(CMD_REMOVE, path)

    unlink = remove

    def rename(self, oldpath, newpath):
        """
        Rename a file or folder from ``oldpath`` to ``newpath``.

        :param str oldpath: existing name of the file or folder
        :param str newpath: new name for the file or folder

        :raises IOError: if ``newpath`` is a folder, or something else goes
            wrong
        """
        oldpath = self._adjust_cwd(oldpath)
        newpath = self._adjust_cwd(newpath)
        self._log(DEBUG, 'rename(%r, %r)' % (oldpath, newpath))
        self._request(CMD_RENAME, oldpath, newpath)

    def mkdir(self, path, mode=o777):
        """
        Create a folder (directory) named ``path`` with numeric mode ``mode``.
        The default mode is 0777 (octal).  On some systems, mode is ignored.
        Where it is used, the current umask value is first masked out.

        :param str path: name of the folder to create
        :param int mode: permissions (posix-style) for the newly-created folder
        """
        path = self._adjust_cwd(path)
        self._log(DEBUG, 'mkdir(%r, %r)' % (path, mode))
        attr = SFTPAttributes()
        attr.st_mode = mode
        self._request(CMD_MKDIR, path, attr)

    def rmdir(self, path):
        """
        Remove the folder named ``path``.

        :param str path: name of the folder to remove
        """
        path = self._adjust_cwd(path)
        self._log(DEBUG, 'rmdir(%r)' % path)
        self._request(CMD_RMDIR, path)

    def stat(self, path):
        """
        Retrieve information about a file on the remote system.  The return
        value is an object whose attributes correspond to the attributes of
        Python's ``stat`` structure as returned by ``os.stat``, except that it
        contains fewer fields.  An SFTP server may return as much or as little
        info as it wants, so the results may vary from server to server.

        Unlike a Python `python:stat` object, the result may not be accessed as
        a tuple.  This is mostly due to the author's slack factor.

        The fields supported are: ``st_mode``, ``st_size``, ``st_uid``,
        ``st_gid``, ``st_atime``, and ``st_mtime``.

        :param str path: the filename to stat
        :return:
            an `.SFTPAttributes` object containing attributes about the given
            file
        """
        path = self._adjust_cwd(path)
        self._log(DEBUG, 'stat(%r)' % path)
        t, msg = self._request(CMD_STAT, path)
        if t != CMD_ATTRS:
            raise SFTPError('Expected attributes')
        return SFTPAttributes._from_msg(msg)

    def lstat(self, path):
        """
        Retrieve information about a file on the remote system, without
        following symbolic links (shortcuts).  This otherwise behaves exactly
        the same as `stat`.

        :param str path: the filename to stat
        :return:
            an `.SFTPAttributes` object containing attributes about the given
            file
        """
        path = self._adjust_cwd(path)
        self._log(DEBUG, 'lstat(%r)' % path)
        t, msg = self._request(CMD_LSTAT, path)
        if t != CMD_ATTRS:
            raise SFTPError('Expected attributes')
        return SFTPAttributes._from_msg(msg)

    def symlink(self, source, dest):
        """
        Create a symbolic link (shortcut) of the ``source`` path at
        ``destination``.

        :param str source: path of the original file
        :param str dest: path of the newly created symlink
        """
        dest = self._adjust_cwd(dest)
        self._log(DEBUG, 'symlink(%r, %r)' % (source, dest))
        source = bytestring(source)
        self._request(CMD_SYMLINK, source, dest)

    def chmod(self, path, mode):
        """
        Change the mode (permissions) of a file.  The permissions are
        unix-style and identical to those used by Python's `os.chmod`
        function.

        :param str path: path of the file to change the permissions of
        :param int mode: new permissions
        """
        path = self._adjust_cwd(path)
        self._log(DEBUG, 'chmod(%r, %r)' % (path, mode))
        attr = SFTPAttributes()
        attr.st_mode = mode
        self._request(CMD_SETSTAT, path, attr)

    def chown(self, path, uid, gid):
        """
        Change the owner (``uid``) and group (``gid``) of a file.  As with
        Python's `os.chown` function, you must pass both arguments, so if you
        only want to change one, use `stat` first to retrieve the current
        owner and group.

        :param str path: path of the file to change the owner and group of
        :param int uid: new owner's uid
        :param int gid: new group id
        """
        path = self._adjust_cwd(path)
        self._log(DEBUG, 'chown(%r, %r, %r)' % (path, uid, gid))
        attr = SFTPAttributes()
        attr.st_uid, attr.st_gid = uid, gid
        self._request(CMD_SETSTAT, path, attr)

    def utime(self, path, times):
        """
        Set the access and modified times of the file specified by ``path``.  If
        ``times`` is ``None``, then the file's access and modified times are set
        to the current time.  Otherwise, ``times`` must be a 2-tuple of numbers,
        of the form ``(atime, mtime)``, which is used to set the access and
        modified times, respectively.  This bizarre API is mimicked from Python
        for the sake of consistency -- I apologize.

        :param str path: path of the file to modify
        :param tuple times:
            ``None`` or a tuple of (access time, modified time) in standard
            internet epoch time (seconds since 01 January 1970 GMT)
        """
        path = self._adjust_cwd(path)
        if times is None:
            times = (time.time(), time.time())
        self._log(DEBUG, 'utime(%r, %r)' % (path, times))
        attr = SFTPAttributes()
        attr.st_atime, attr.st_mtime = times
        self._request(CMD_SETSTAT, path, attr)

    def truncate(self, path, size):
        """
        Change the size of the file specified by ``path``.  This usually
        extends or shrinks the size of the file, just like the `~file.truncate`
        method on Python file objects.

        :param str path: path of the file to modify
        :param size: the new size of the file
        :type size: int or long
        """
        path = self._adjust_cwd(path)
        self._log(DEBUG, 'truncate(%r, %r)' % (path, size))
        attr = SFTPAttributes()
        attr.st_size = size
        self._request(CMD_SETSTAT, path, attr)

    def readlink(self, path):
        """
        Return the target of a symbolic link (shortcut).  You can use
        `symlink` to create these.  The result may be either an absolute or
        relative pathname.

        :param str path: path of the symbolic link file
        :return: target path, as a `str`
        """
        path = self._adjust_cwd(path)
        self._log(DEBUG, 'readlink(%r)' % path)
        t, msg = self._request(CMD_READLINK, path)
        if t != CMD_NAME:
            raise SFTPError('Expected name response')
        count = msg.get_int()
        if count == 0:
            return None
        if count != 1:
            raise SFTPError('Readlink returned %d results' % count)
        return _to_unicode(msg.get_string())

    def normalize(self, path):
        """
        Return the normalized path (on the server) of a given path.  This
        can be used to quickly resolve symbolic links or determine what the
        server is considering to be the "current folder" (by passing ``'.'``
        as ``path``).

        :param str path: path to be normalized
        :return: normalized form of the given path (as a `str`)

        :raises IOError: if the path can't be resolved on the server
        """
        path = self._adjust_cwd(path)
        self._log(DEBUG, 'normalize(%r)' % path)
        t, msg = self._request(CMD_REALPATH, path)
        if t != CMD_NAME:
            raise SFTPError('Expected name response')
        count = msg.get_int()
        if count != 1:
            raise SFTPError('Realpath returned %d results' % count)
        return msg.get_text()

    def chdir(self, path=None):
        """
        Change the "current directory" of this SFTP session.  Since SFTP
        doesn't really have the concept of a current working directory, this is
        emulated by Paramiko.  Once you use this method to set a working
        directory, all operations on this `.SFTPClient` object will be relative
        to that path. You can pass in ``None`` to stop using a current working
        directory.

        :param str path: new current working directory

        :raises IOError: if the requested path doesn't exist on the server

        .. versionadded:: 1.4
        """
        if path is None:
            self._cwd = None
            return
        if not stat.S_ISDIR(self.stat(path).st_mode):
            raise SFTPError(errno.ENOTDIR, "%s: %s" % (os.strerror(errno.ENOTDIR), path))
        self._cwd = b(self.normalize(path))

    def getcwd(self):
        """
        Return the "current working directory" for this SFTP session, as
        emulated by Paramiko.  If no directory has been set with `chdir`,
        this method will return ``None``.

        .. versionadded:: 1.4
        """
        return self._cwd and u(self._cwd)

    def putfo(self, fl, remotepath, file_size=0, callback=None, confirm=True):
        """
        Copy the contents of an open file object (``fl``) to the SFTP server as
        ``remotepath``. Any exception raised by operations will be passed
        through.

        The SFTP operations use pipelining for speed.

        :param file fl: opened file or file-like object to copy
        :param str remotepath: the destination path on the SFTP server
        :param int file_size:
            optional size parameter passed to callback. If none is specified,
            size defaults to 0
        :param callable callback:
            optional callback function (form: ``func(int, int)``) that accepts
            the bytes transferred so far and the total bytes to be transferred
            (since 1.7.4)
        :param bool confirm:
            whether to do a stat() on the file afterwards to confirm the file
            size (since 1.7.7)

        :return:
            an `.SFTPAttributes` object containing attributes about the given
            file.

        .. versionadded:: 1.4
        .. versionchanged:: 1.7.4
            Began returning rich attribute objects.
        """
        with self.file(remotepath, 'wb') as fr:
            fr.set_pipelined(True)
            size = 0
            while True:
                data = fl.read(32768)
                fr.write(data)
                size += len(data)
                if callback is not None:
                    callback(size, file_size)
                if len(data) == 0:
                    break
        if confirm:
            s = self.stat(remotepath)
            if s.st_size != size:
                raise IOError('size mismatch in put!  %d != %d' % (s.st_size, size))
        else:
            s = SFTPAttributes()
        return s

    def put(self, localpath, remotepath, callback=None, confirm=True):
        """
        Copy a local file (``localpath``) to the SFTP server as ``remotepath``.
        Any exception raised by operations will be passed through.  This
        method is primarily provided as a convenience.

        The SFTP operations use pipelining for speed.

        :param str localpath: the local file to copy
        :param str remotepath: the destination path on the SFTP server
        :param callable callback:
            optional callback function (form: ``func(int, int)``) that accepts
            the bytes transferred so far and the total bytes to be transferred
        :param bool confirm:
            whether to do a stat() on the file afterwards to confirm the file
            size

        :return: an `.SFTPAttributes` object containing attributes about the given file

        .. versionadded:: 1.4
        .. versionchanged:: 1.7.4
            ``callback`` and rich attribute return value added.   
        .. versionchanged:: 1.7.7
            ``confirm`` param added.
        """
        file_size = os.stat(localpath).st_size
        with open(localpath, 'rb') as fl:
            return self.putfo(fl, remotepath, os.stat(localpath).st_size, callback, confirm)

    def getfo(self, remotepath, fl, callback=None):
        """
        Copy a remote file (``remotepath``) from the SFTP server and write to
        an open file or file-like object, ``fl``.  Any exception raised by
        operations will be passed through.  This method is primarily provided
        as a convenience.

        :param object remotepath: opened file or file-like object to copy to
        :param str fl:
            the destination path on the local host or open file object
        :param callable callback:
            optional callback function (form: ``func(int, int)``) that accepts
            the bytes transferred so far and the total bytes to be transferred
        :return: the `number <int>` of bytes written to the opened file object

        .. versionadded:: 1.4
        .. versionchanged:: 1.7.4
            Added the ``callable`` param.
        """
        with self.open(remotepath, 'rb') as fr:
            file_size = self.stat(remotepath).st_size
            fr.prefetch()
            size = 0
            while True:
                data = fr.read(32768)
                fl.write(data)
                size += len(data)
                if callback is not None:
                    callback(size, file_size)
                if len(data) == 0:
                    break
        return size

    def get(self, remotepath, localpath, callback=None):
        """
        Copy a remote file (``remotepath``) from the SFTP server to the local
        host as ``localpath``.  Any exception raised by operations will be
        passed through.  This method is primarily provided as a convenience.

        :param str remotepath: the remote file to copy
        :param str localpath: the destination path on the local host
        :param callable callback:
            optional callback function (form: ``func(int, int)``) that accepts
            the bytes transferred so far and the total bytes to be transferred

        .. versionadded:: 1.4
        .. versionchanged:: 1.7.4
            Added the ``callback`` param
        """
        file_size = self.stat(remotepath).st_size
        with open(localpath, 'wb') as fl:
            size = self.getfo(remotepath, fl, callback)
        s = os.stat(localpath)
        if s.st_size != size:
            raise IOError('size mismatch in get!  %d != %d' % (s.st_size, size))

    ###  internals...

    def _request(self, t, *arg):
        num = self._async_request(type(None), t, *arg)
        return self._read_response(num)

    def _async_request(self, fileobj, t, *arg):
        # this method may be called from other threads (prefetch)
        self._lock.acquire()
        try:
            msg = Message()
            msg.add_int(self.request_number)
            for item in arg:
                if isinstance(item, long):
                    msg.add_int64(item)
                elif isinstance(item, int):
                    msg.add_int(item)
                elif isinstance(item, (string_types, bytes_types)):
                    msg.add_string(item)
                elif isinstance(item, SFTPAttributes):
                    item._pack(msg)
                else:
                    raise Exception('unknown type for %r type %r' % (item, type(item)))
            num = self.request_number
            self._expecting[num] = fileobj
            self._send_packet(t, msg)
            self.request_number += 1
        finally:
            self._lock.release()
        return num

    def _read_response(self, waitfor=None):
        while True:
            try:
                t, data = self._read_packet()
            except EOFError as e:
                raise SSHException('Server connection dropped: %s' % str(e))
            msg = Message(data)
            num = msg.get_int()
            if num not in self._expecting:
                # might be response for a file that was closed before responses came back
                self._log(DEBUG, 'Unexpected response #%d' % (num,))
                if waitfor is None:
                    # just doing a single check
                    break
                continue
            fileobj = self._expecting[num]
            del self._expecting[num]
            if num == waitfor:
                # synchronous
                if t == CMD_STATUS:
                    self._convert_status(msg)
                return t, msg
            if fileobj is not type(None):
                fileobj._async_response(t, msg, num)
            if waitfor is None:
                # just doing a single check
                break
        return None, None

    def _finish_responses(self, fileobj):
        while fileobj in self._expecting.values():
            self._read_response()
            fileobj._check_exception()

    def _convert_status(self, msg):
        """
        Raises EOFError or IOError on error status; otherwise does nothing.
        """
        code = msg.get_int()
        text = msg.get_text()
        if code == SFTP_OK:
            return
        elif code == SFTP_EOF:
            raise EOFError(text)
        elif code == SFTP_NO_SUCH_FILE:
            # clever idea from john a. meinel: map the error codes to errno
            raise IOError(errno.ENOENT, text)
        elif code == SFTP_PERMISSION_DENIED:
            raise IOError(errno.EACCES, text)
        else:
            raise IOError(text)

    def _adjust_cwd(self, path):
        """
        Return an adjusted path if we're emulating a "current working
        directory" for the server.
        """
        path = b(path)
        if self._cwd is None:
            return path
        if len(path) and path[0:1] == b_slash:
            # absolute path
            return path
        if self._cwd == b_slash:
            return self._cwd + path
        return self._cwd + b_slash + path


class SFTP(SFTPClient):
    """
    An alias for `.SFTPClient` for backwards compatability.
    """
    pass

########NEW FILE########
__FILENAME__ = sftp_file
# Copyright (C) 2003-2007  Robey Pointer <robeypointer@gmail.com>
#
# This file is part of paramiko.
#
# Paramiko is free software; you can redistribute it and/or modify it under the
# terms of the GNU Lesser General Public License as published by the Free
# Software Foundation; either version 2.1 of the License, or (at your option)
# any later version.
#
# Paramiko is distributed in the hope that it will be useful, but WITHOUT ANY
# WARRANTY; without even the implied warranty of MERCHANTABILITY or FITNESS FOR
# A PARTICULAR PURPOSE.  See the GNU Lesser General Public License for more
# details.
#
# You should have received a copy of the GNU Lesser General Public License
# along with Paramiko; if not, write to the Free Software Foundation, Inc.,
# 59 Temple Place, Suite 330, Boston, MA  02111-1307  USA.

"""
SFTP file object
"""

from __future__ import with_statement

from binascii import hexlify
from collections import deque
import socket
import threading
import time
from paramiko.common import DEBUG

from paramiko.file import BufferedFile
from paramiko.py3compat import long
from paramiko.sftp import CMD_CLOSE, CMD_READ, CMD_DATA, SFTPError, CMD_WRITE, \
    CMD_STATUS, CMD_FSTAT, CMD_ATTRS, CMD_FSETSTAT, CMD_EXTENDED
from paramiko.sftp_attr import SFTPAttributes


class SFTPFile (BufferedFile):
    """
    Proxy object for a file on the remote server, in client mode SFTP.

    Instances of this class may be used as context managers in the same way
    that built-in Python file objects are.
    """

    # Some sftp servers will choke if you send read/write requests larger than
    # this size.
    MAX_REQUEST_SIZE = 32768

    def __init__(self, sftp, handle, mode='r', bufsize=-1):
        BufferedFile.__init__(self)
        self.sftp = sftp
        self.handle = handle
        BufferedFile._set_mode(self, mode, bufsize)
        self.pipelined = False
        self._prefetching = False
        self._prefetch_done = False
        self._prefetch_data = {}
        self._prefetch_extents = {}
        self._prefetch_lock = threading.Lock()
        self._saved_exception = None
        self._reqs = deque()

    def __del__(self):
        self._close(async=True)
    
    def close(self):
        """
        Close the file.
        """
        self._close(async=False)
        
    def _close(self, async=False):
        # We allow double-close without signaling an error, because real
        # Python file objects do.  However, we must protect against actually
        # sending multiple CMD_CLOSE packets, because after we close our
        # handle, the same handle may be re-allocated by the server, and we
        # may end up mysteriously closing some random other file.  (This is
        # especially important because we unconditionally call close() from
        # __del__.)
        if self._closed:
            return
        self.sftp._log(DEBUG, 'close(%s)' % hexlify(self.handle))
        if self.pipelined:
            self.sftp._finish_responses(self)
        BufferedFile.close(self)
        try:
            if async:
                # GC'd file handle could be called from an arbitrary thread -- don't wait for a response
                self.sftp._async_request(type(None), CMD_CLOSE, self.handle)
            else:
                self.sftp._request(CMD_CLOSE, self.handle)
        except EOFError:
            # may have outlived the Transport connection
            pass
        except (IOError, socket.error):
            # may have outlived the Transport connection
            pass

    def _data_in_prefetch_requests(self, offset, size):
        k = [x for x in list(self._prefetch_extents.values()) if x[0] <= offset]
        if len(k) == 0:
            return False
        k.sort(key=lambda x: x[0])
        buf_offset, buf_size = k[-1]
        if buf_offset + buf_size <= offset:
            # prefetch request ends before this one begins
            return False
        if buf_offset + buf_size >= offset + size:
            # inclusive
            return True
        # well, we have part of the request.  see if another chunk has the rest.
        return self._data_in_prefetch_requests(buf_offset + buf_size, offset + size - buf_offset - buf_size)
    
    def _data_in_prefetch_buffers(self, offset):
        """
        if a block of data is present in the prefetch buffers, at the given
        offset, return the offset of the relevant prefetch buffer.  otherwise,
        return None.  this guarantees nothing about the number of bytes
        collected in the prefetch buffer so far.
        """
        k = [i for i in self._prefetch_data.keys() if i <= offset]
        if len(k) == 0:
            return None
        index = max(k)
        buf_offset = offset - index
        if buf_offset >= len(self._prefetch_data[index]):
            # it's not here
            return None
        return index
        
    def _read_prefetch(self, size):
        """
        read data out of the prefetch buffer, if possible.  if the data isn't
        in the buffer, return None.  otherwise, behaves like a normal read.
        """
        # while not closed, and haven't fetched past the current position, and haven't reached EOF...
        while True:
            offset = self._data_in_prefetch_buffers(self._realpos)
            if offset is not None:
                break
            if self._prefetch_done or self._closed:
                break
            self.sftp._read_response()
            self._check_exception()
        if offset is None:
            self._prefetching = False
            return None
        prefetch = self._prefetch_data[offset]
        del self._prefetch_data[offset]
        
        buf_offset = self._realpos - offset
        if buf_offset > 0:
            self._prefetch_data[offset] = prefetch[:buf_offset]
            prefetch = prefetch[buf_offset:]
        if size < len(prefetch):
            self._prefetch_data[self._realpos + size] = prefetch[size:]
            prefetch = prefetch[:size]
        return prefetch
        
    def _read(self, size):
        size = min(size, self.MAX_REQUEST_SIZE)
        if self._prefetching:
            data = self._read_prefetch(size)
            if data is not None:
                return data
        t, msg = self.sftp._request(CMD_READ, self.handle, long(self._realpos), int(size))
        if t != CMD_DATA:
            raise SFTPError('Expected data')
        return msg.get_string()

    def _write(self, data):
        # may write less than requested if it would exceed max packet size
        chunk = min(len(data), self.MAX_REQUEST_SIZE)
        self._reqs.append(self.sftp._async_request(type(None), CMD_WRITE, self.handle, long(self._realpos), data[:chunk]))
        if not self.pipelined or (len(self._reqs) > 100 and self.sftp.sock.recv_ready()):
            while len(self._reqs):
                req = self._reqs.popleft()
                t, msg = self.sftp._read_response(req)
                if t != CMD_STATUS:
                    raise SFTPError('Expected status')
                # convert_status already called
        return chunk

    def settimeout(self, timeout):
        """
        Set a timeout on read/write operations on the underlying socket or
        ssh `.Channel`.

        :param float timeout:
            seconds to wait for a pending read/write operation before raising
            ``socket.timeout``, or ``None`` for no timeout

        .. seealso:: `.Channel.settimeout`
        """
        self.sftp.sock.settimeout(timeout)

    def gettimeout(self):
        """
        Returns the timeout in seconds (as a `float`) associated with the
        socket or ssh `.Channel` used for this file.

        .. seealso:: `.Channel.gettimeout`
        """
        return self.sftp.sock.gettimeout()

    def setblocking(self, blocking):
        """
        Set blocking or non-blocking mode on the underiying socket or ssh
        `.Channel`.

        :param int blocking:
            0 to set non-blocking mode; non-0 to set blocking mode.

        .. seealso:: `.Channel.setblocking`
        """
        self.sftp.sock.setblocking(blocking)

    def seek(self, offset, whence=0):
        self.flush()
        if whence == self.SEEK_SET:
            self._realpos = self._pos = offset
        elif whence == self.SEEK_CUR:
            self._pos += offset
            self._realpos = self._pos
        else:
            self._realpos = self._pos = self._get_size() + offset
        self._rbuffer = bytes()

    def stat(self):
        """
        Retrieve information about this file from the remote system.  This is
        exactly like `.SFTPClient.stat`, except that it operates on an
        already-open file.

        :return: an `.SFTPAttributes` object containing attributes about this file.
        """
        t, msg = self.sftp._request(CMD_FSTAT, self.handle)
        if t != CMD_ATTRS:
            raise SFTPError('Expected attributes')
        return SFTPAttributes._from_msg(msg)

    def chmod(self, mode):
        """
        Change the mode (permissions) of this file.  The permissions are
        unix-style and identical to those used by Python's `os.chmod`
        function.

        :param int mode: new permissions
        """
        self.sftp._log(DEBUG, 'chmod(%s, %r)' % (hexlify(self.handle), mode))
        attr = SFTPAttributes()
        attr.st_mode = mode
        self.sftp._request(CMD_FSETSTAT, self.handle, attr)
        
    def chown(self, uid, gid):
        """
        Change the owner (``uid``) and group (``gid``) of this file.  As with
        Python's `os.chown` function, you must pass both arguments, so if you
        only want to change one, use `stat` first to retrieve the current
        owner and group.

        :param int uid: new owner's uid
        :param int gid: new group id
        """
        self.sftp._log(DEBUG, 'chown(%s, %r, %r)' % (hexlify(self.handle), uid, gid))
        attr = SFTPAttributes()
        attr.st_uid, attr.st_gid = uid, gid
        self.sftp._request(CMD_FSETSTAT, self.handle, attr)

    def utime(self, times):
        """
        Set the access and modified times of this file.  If
        ``times`` is ``None``, then the file's access and modified times are set
        to the current time.  Otherwise, ``times`` must be a 2-tuple of numbers,
        of the form ``(atime, mtime)``, which is used to set the access and
        modified times, respectively.  This bizarre API is mimicked from Python
        for the sake of consistency -- I apologize.

        :param tuple times:
            ``None`` or a tuple of (access time, modified time) in standard
            internet epoch time (seconds since 01 January 1970 GMT)
        """
        if times is None:
            times = (time.time(), time.time())
        self.sftp._log(DEBUG, 'utime(%s, %r)' % (hexlify(self.handle), times))
        attr = SFTPAttributes()
        attr.st_atime, attr.st_mtime = times
        self.sftp._request(CMD_FSETSTAT, self.handle, attr)

    def truncate(self, size):
        """
        Change the size of this file.  This usually extends
        or shrinks the size of the file, just like the ``truncate()`` method on
        Python file objects.
        
        :param size: the new size of the file
        :type size: int or long
        """
        self.sftp._log(DEBUG, 'truncate(%s, %r)' % (hexlify(self.handle), size))
        attr = SFTPAttributes()
        attr.st_size = size
        self.sftp._request(CMD_FSETSTAT, self.handle, attr)
    
    def check(self, hash_algorithm, offset=0, length=0, block_size=0):
        """
        Ask the server for a hash of a section of this file.  This can be used
        to verify a successful upload or download, or for various rsync-like
        operations.
        
        The file is hashed from ``offset``, for ``length`` bytes.  If ``length``
        is 0, the remainder of the file is hashed.  Thus, if both ``offset``
        and ``length`` are zero, the entire file is hashed.
        
        Normally, ``block_size`` will be 0 (the default), and this method will
        return a byte string representing the requested hash (for example, a
        string of length 16 for MD5, or 20 for SHA-1).  If a non-zero
        ``block_size`` is given, each chunk of the file (from ``offset`` to
        ``offset + length``) of ``block_size`` bytes is computed as a separate
        hash.  The hash results are all concatenated and returned as a single
        string.
        
        For example, ``check('sha1', 0, 1024, 512)`` will return a string of
        length 40.  The first 20 bytes will be the SHA-1 of the first 512 bytes
        of the file, and the last 20 bytes will be the SHA-1 of the next 512
        bytes.
        
        :param str hash_algorithm:
            the name of the hash algorithm to use (normally ``"sha1"`` or
            ``"md5"``)
        :param offset:
            offset into the file to begin hashing (0 means to start from the
            beginning)
        :type offset: int or long
        :param length:
            number of bytes to hash (0 means continue to the end of the file)
        :type length: int or long
        :param int block_size:
            number of bytes to hash per result (must not be less than 256; 0
            means to compute only one hash of the entire segment)
        :type block_size: int
        :return:
            `str` of bytes representing the hash of each block, concatenated
            together
        
        :raises IOError: if the server doesn't support the "check-file"
            extension, or possibly doesn't support the hash algorithm
            requested
            
        .. note:: Many (most?) servers don't support this extension yet.
        
        .. versionadded:: 1.4
        """
        t, msg = self.sftp._request(CMD_EXTENDED, 'check-file', self.handle,
                                    hash_algorithm, long(offset), long(length), block_size)
        ext = msg.get_text()
        alg = msg.get_text()
        data = msg.get_remainder()
        return data
    
    def set_pipelined(self, pipelined=True):
        """
        Turn on/off the pipelining of write operations to this file.  When
        pipelining is on, paramiko won't wait for the server response after
        each write operation.  Instead, they're collected as they come in. At
        the first non-write operation (including `.close`), all remaining
        server responses are collected.  This means that if there was an error
        with one of your later writes, an exception might be thrown from within
        `.close` instead of `.write`.
        
        By default, files are not pipelined.
        
        :param bool pipelined:
            ``True`` if pipelining should be turned on for this file; ``False``
            otherwise
        
        .. versionadded:: 1.5
        """
        self.pipelined = pipelined
    
    def prefetch(self):
        """
        Pre-fetch the remaining contents of this file in anticipation of future
        `.read` calls.  If reading the entire file, pre-fetching can
        dramatically improve the download speed by avoiding roundtrip latency.
        The file's contents are incrementally buffered in a background thread.
        
        The prefetched data is stored in a buffer until read via the `.read`
        method.  Once data has been read, it's removed from the buffer.  The
        data may be read in a random order (using `.seek`); chunks of the
        buffer that haven't been read will continue to be buffered.

        .. versionadded:: 1.5.1
        """
        size = self.stat().st_size
        # queue up async reads for the rest of the file
        chunks = []
        n = self._realpos
        while n < size:
            chunk = min(self.MAX_REQUEST_SIZE, size - n)
            chunks.append((n, chunk))
            n += chunk
        if len(chunks) > 0:
            self._start_prefetch(chunks)
    
    def readv(self, chunks):
        """
        Read a set of blocks from the file by (offset, length).  This is more
        efficient than doing a series of `.seek` and `.read` calls, since the
        prefetch machinery is used to retrieve all the requested blocks at
        once.
        
        :param chunks:
            a list of (offset, length) tuples indicating which sections of the
            file to read
        :type chunks: list(tuple(long, int))
        :return: a list of blocks read, in the same order as in ``chunks``
        
        .. versionadded:: 1.5.4
        """
        self.sftp._log(DEBUG, 'readv(%s, %r)' % (hexlify(self.handle), chunks))

        read_chunks = []
        for offset, size in chunks:
            # don't fetch data that's already in the prefetch buffer
            if self._data_in_prefetch_buffers(offset) or self._data_in_prefetch_requests(offset, size):
                continue

            # break up anything larger than the max read size
            while size > 0:
                chunk_size = min(size, self.MAX_REQUEST_SIZE)
                read_chunks.append((offset, chunk_size))
                offset += chunk_size
                size -= chunk_size

        self._start_prefetch(read_chunks)
        # now we can just devolve to a bunch of read()s :)
        for x in chunks:
            self.seek(x[0])
            yield self.read(x[1])

    ###  internals...

    def _get_size(self):
        try:
            return self.stat().st_size
        except:
            return 0

    def _start_prefetch(self, chunks):
        self._prefetching = True
        self._prefetch_done = False

        t = threading.Thread(target=self._prefetch_thread, args=(chunks,))
        t.setDaemon(True)
        t.start()
        
    def _prefetch_thread(self, chunks):
        # do these read requests in a temporary thread because there may be
        # a lot of them, so it may block.
        for offset, length in chunks:
            with self._prefetch_lock:
                num = self.sftp._async_request(self, CMD_READ, self.handle, long(offset), int(length))
                self._prefetch_extents[num] = (offset, length)

    def _async_response(self, t, msg, num):
        if t == CMD_STATUS:
            # save exception and re-raise it on next file operation
            try:
                self.sftp._convert_status(msg)
            except Exception as e:
                self._saved_exception = e
            return
        if t != CMD_DATA:
            raise SFTPError('Expected data')
        data = msg.get_string()
        with self._prefetch_lock:
            offset, length = self._prefetch_extents[num]
            self._prefetch_data[offset] = data
            del self._prefetch_extents[num]
            if len(self._prefetch_extents) == 0:
                self._prefetch_done = True
    
    def _check_exception(self):
        """if there's a saved exception, raise & clear it"""
        if self._saved_exception is not None:
            x = self._saved_exception
            self._saved_exception = None
            raise x
            
    def __enter__(self):
        return self

    def __exit__(self, type, value, traceback):
        self.close()

########NEW FILE########
__FILENAME__ = sftp_handle
# Copyright (C) 2003-2007  Robey Pointer <robeypointer@gmail.com>
#
# This file is part of paramiko.
#
# Paramiko is free software; you can redistribute it and/or modify it under the
# terms of the GNU Lesser General Public License as published by the Free
# Software Foundation; either version 2.1 of the License, or (at your option)
# any later version.
#
# Paramiko is distributed in the hope that it will be useful, but WITHOUT ANY
# WARRANTY; without even the implied warranty of MERCHANTABILITY or FITNESS FOR
# A PARTICULAR PURPOSE.  See the GNU Lesser General Public License for more
# details.
#
# You should have received a copy of the GNU Lesser General Public License
# along with Paramiko; if not, write to the Free Software Foundation, Inc.,
# 59 Temple Place, Suite 330, Boston, MA  02111-1307  USA.

"""
Abstraction of an SFTP file handle (for server mode).
"""

import os
from paramiko.sftp import SFTP_OP_UNSUPPORTED, SFTP_OK


class SFTPHandle (object):
    """
    Abstract object representing a handle to an open file (or folder) in an
    SFTP server implementation.  Each handle has a string representation used
    by the client to refer to the underlying file.
    
    Server implementations can (and should) subclass SFTPHandle to implement
    features of a file handle, like `stat` or `chattr`.
    """
    def __init__(self, flags=0):
        """
        Create a new file handle representing a local file being served over
        SFTP.  If ``flags`` is passed in, it's used to determine if the file
        is open in append mode.
        
        :param int flags: optional flags as passed to `.SFTPServerInterface.open`
        """
        self.__flags = flags
        self.__name = None
        # only for handles to folders:
        self.__files = {}
        self.__tell = None

    def close(self):
        """
        When a client closes a file, this method is called on the handle.
        Normally you would use this method to close the underlying OS level
        file object(s).
        
        The default implementation checks for attributes on ``self`` named
        ``readfile`` and/or ``writefile``, and if either or both are present,
        their ``close()`` methods are called.  This means that if you are
        using the default implementations of `read` and `write`, this
        method's default implementation should be fine also.
        """
        readfile = getattr(self, 'readfile', None)
        if readfile is not None:
            readfile.close()
        writefile = getattr(self, 'writefile', None)
        if writefile is not None:
            writefile.close()

    def read(self, offset, length):
        """
        Read up to ``length`` bytes from this file, starting at position
        ``offset``.  The offset may be a Python long, since SFTP allows it
        to be 64 bits.

        If the end of the file has been reached, this method may return an
        empty string to signify EOF, or it may also return `.SFTP_EOF`.

        The default implementation checks for an attribute on ``self`` named
        ``readfile``, and if present, performs the read operation on the Python
        file-like object found there.  (This is meant as a time saver for the
        common case where you are wrapping a Python file object.)

        :param offset: position in the file to start reading from.
        :type offset: int or long
        :param int length: number of bytes to attempt to read.
        :return: data read from the file, or an SFTP error code, as a `str`.
        """
        readfile = getattr(self, 'readfile', None)
        if readfile is None:
            return SFTP_OP_UNSUPPORTED
        try:
            if self.__tell is None:
                self.__tell = readfile.tell()
            if offset != self.__tell:
                readfile.seek(offset)
                self.__tell = offset
            data = readfile.read(length)
        except IOError as e:
            self.__tell = None
            return SFTPServer.convert_errno(e.errno)
        self.__tell += len(data)
        return data

    def write(self, offset, data):
        """
        Write ``data`` into this file at position ``offset``.  Extending the
        file past its original end is expected.  Unlike Python's normal
        ``write()`` methods, this method cannot do a partial write: it must
        write all of ``data`` or else return an error.

        The default implementation checks for an attribute on ``self`` named
        ``writefile``, and if present, performs the write operation on the
        Python file-like object found there.  The attribute is named
        differently from ``readfile`` to make it easy to implement read-only
        (or write-only) files, but if both attributes are present, they should
        refer to the same file.
        
        :param offset: position in the file to start reading from.
        :type offset: int or long
        :param str data: data to write into the file.
        :return: an SFTP error code like `.SFTP_OK`.
        """
        writefile = getattr(self, 'writefile', None)
        if writefile is None:
            return SFTP_OP_UNSUPPORTED
        try:
            # in append mode, don't care about seeking
            if (self.__flags & os.O_APPEND) == 0:
                if self.__tell is None:
                    self.__tell = writefile.tell()
                if offset != self.__tell:
                    writefile.seek(offset)
                    self.__tell = offset
            writefile.write(data)
            writefile.flush()
        except IOError as e:
            self.__tell = None
            return SFTPServer.convert_errno(e.errno)
        if self.__tell is not None:
            self.__tell += len(data)
        return SFTP_OK

    def stat(self):
        """
        Return an `.SFTPAttributes` object referring to this open file, or an
        error code.  This is equivalent to `.SFTPServerInterface.stat`, except
        it's called on an open file instead of a path.

        :return:
            an attributes object for the given file, or an SFTP error code
            (like `.SFTP_PERMISSION_DENIED`).
        :rtype: `.SFTPAttributes` or error code
        """
        return SFTP_OP_UNSUPPORTED

    def chattr(self, attr):
        """
        Change the attributes of this file.  The ``attr`` object will contain
        only those fields provided by the client in its request, so you should
        check for the presence of fields before using them.

        :param .SFTPAttributes attr: the attributes to change on this file.
        :return: an `int` error code like `.SFTP_OK`.
        """
        return SFTP_OP_UNSUPPORTED

    ###  internals...

    def _set_files(self, files):
        """
        Used by the SFTP server code to cache a directory listing.  (In
        the SFTP protocol, listing a directory is a multi-stage process
        requiring a temporary handle.)
        """
        self.__files = files

    def _get_next_files(self):
        """
        Used by the SFTP server code to retreive a cached directory
        listing.
        """
        fnlist = self.__files[:16]
        self.__files = self.__files[16:]
        return fnlist

    def _get_name(self):
        return self.__name

    def _set_name(self, name):
        self.__name = name


from paramiko.sftp_server import SFTPServer

########NEW FILE########
__FILENAME__ = sftp_server
# Copyright (C) 2003-2007  Robey Pointer <robeypointer@gmail.com>
#
# This file is part of paramiko.
#
# Paramiko is free software; you can redistribute it and/or modify it under the
# terms of the GNU Lesser General Public License as published by the Free
# Software Foundation; either version 2.1 of the License, or (at your option)
# any later version.
#
# Paramiko is distributed in the hope that it will be useful, but WITHOUT ANY
# WARRANTY; without even the implied warranty of MERCHANTABILITY or FITNESS FOR
# A PARTICULAR PURPOSE.  See the GNU Lesser General Public License for more
# details.
#
# You should have received a copy of the GNU Lesser General Public License
# along with Paramiko; if not, write to the Free Software Foundation, Inc.,
# 59 Temple Place, Suite 330, Boston, MA  02111-1307  USA.

"""
Server-mode SFTP support.
"""

import os
import errno
import sys
from hashlib import md5, sha1

from paramiko import util
from paramiko.sftp import BaseSFTP, Message, SFTP_FAILURE, \
    SFTP_PERMISSION_DENIED, SFTP_NO_SUCH_FILE
from paramiko.sftp_si import SFTPServerInterface
from paramiko.sftp_attr import SFTPAttributes
from paramiko.common import DEBUG
from paramiko.py3compat import long, string_types, bytes_types, b
from paramiko.server import SubsystemHandler


# known hash algorithms for the "check-file" extension
from paramiko.sftp import CMD_HANDLE, SFTP_DESC, CMD_STATUS, SFTP_EOF, CMD_NAME, \
    SFTP_BAD_MESSAGE, CMD_EXTENDED_REPLY, SFTP_FLAG_READ, SFTP_FLAG_WRITE, \
    SFTP_FLAG_APPEND, SFTP_FLAG_CREATE, SFTP_FLAG_TRUNC, SFTP_FLAG_EXCL, \
    CMD_NAMES, CMD_OPEN, CMD_CLOSE, SFTP_OK, CMD_READ, CMD_DATA, CMD_WRITE, \
    CMD_REMOVE, CMD_RENAME, CMD_MKDIR, CMD_RMDIR, CMD_OPENDIR, CMD_READDIR, \
    CMD_STAT, CMD_ATTRS, CMD_LSTAT, CMD_FSTAT, CMD_SETSTAT, CMD_FSETSTAT, \
    CMD_READLINK, CMD_SYMLINK, CMD_REALPATH, CMD_EXTENDED, SFTP_OP_UNSUPPORTED

_hash_class = {
    'sha1': sha1,
    'md5': md5,
}


class SFTPServer (BaseSFTP, SubsystemHandler):
    """
    Server-side SFTP subsystem support.  Since this is a `.SubsystemHandler`,
    it can be (and is meant to be) set as the handler for ``"sftp"`` requests.
    Use `.Transport.set_subsystem_handler` to activate this class.
    """

    def __init__(self, channel, name, server, sftp_si=SFTPServerInterface, *largs, **kwargs):
        """
        The constructor for SFTPServer is meant to be called from within the
        `.Transport` as a subsystem handler.  ``server`` and any additional
        parameters or keyword parameters are passed from the original call to
        `.Transport.set_subsystem_handler`.

        :param .Channel channel: channel passed from the `.Transport`.
        :param str name: name of the requested subsystem.
        :param .ServerInterface server:
            the server object associated with this channel and subsystem
        :param class sftp_si:
            a subclass of `.SFTPServerInterface` to use for handling individual
            requests.
        """
        BaseSFTP.__init__(self)
        SubsystemHandler.__init__(self, channel, name, server)
        transport = channel.get_transport()
        self.logger = util.get_logger(transport.get_log_channel() + '.sftp')
        self.ultra_debug = transport.get_hexdump()
        self.next_handle = 1
        # map of handle-string to SFTPHandle for files & folders:
        self.file_table = {}
        self.folder_table = {}
        self.server = sftp_si(server, *largs, **kwargs)

    def _log(self, level, msg):
        if issubclass(type(msg), list):
            for m in msg:
                super(SFTPServer, self)._log(level, "[chan " + self.sock.get_name() + "] " + m)
        else:
            super(SFTPServer, self)._log(level, "[chan " + self.sock.get_name() + "] " + msg)

    def start_subsystem(self, name, transport, channel):
        self.sock = channel
        self._log(DEBUG, 'Started sftp server on channel %s' % repr(channel))
        self._send_server_version()
        self.server.session_started()
        while True:
            try:
                t, data = self._read_packet()
            except EOFError:
                self._log(DEBUG, 'EOF -- end of session')
                return
            except Exception as e:
                self._log(DEBUG, 'Exception on channel: ' + str(e))
                self._log(DEBUG, util.tb_strings())
                return
            msg = Message(data)
            request_number = msg.get_int()
            try:
                self._process(t, request_number, msg)
            except Exception as e:
                self._log(DEBUG, 'Exception in server processing: ' + str(e))
                self._log(DEBUG, util.tb_strings())
                # send some kind of failure message, at least
                try:
                    self._send_status(request_number, SFTP_FAILURE)
                except:
                    pass

    def finish_subsystem(self):
        self.server.session_ended()
        super(SFTPServer, self).finish_subsystem()
        # close any file handles that were left open (so we can return them to the OS quickly)
        for f in self.file_table.values():
            f.close()
        for f in self.folder_table.values():
            f.close()
        self.file_table = {}
        self.folder_table = {}

    def convert_errno(e):
        """
        Convert an errno value (as from an ``OSError`` or ``IOError``) into a
        standard SFTP result code.  This is a convenience function for trapping
        exceptions in server code and returning an appropriate result.

        :param int e: an errno code, as from ``OSError.errno``.
        :return: an `int` SFTP error code like ``SFTP_NO_SUCH_FILE``.
        """
        if e == errno.EACCES:
            # permission denied
            return SFTP_PERMISSION_DENIED
        elif (e == errno.ENOENT) or (e == errno.ENOTDIR):
            # no such file
            return SFTP_NO_SUCH_FILE
        else:
            return SFTP_FAILURE
    convert_errno = staticmethod(convert_errno)

    def set_file_attr(filename, attr):
        """
        Change a file's attributes on the local filesystem.  The contents of
        ``attr`` are used to change the permissions, owner, group ownership,
        and/or modification & access time of the file, depending on which
        attributes are present in ``attr``.

        This is meant to be a handy helper function for translating SFTP file
        requests into local file operations.

        :param str filename:
            name of the file to alter (should usually be an absolute path).
        :param .SFTPAttributes attr: attributes to change.
        """
        if sys.platform != 'win32':
            # mode operations are meaningless on win32
            if attr._flags & attr.FLAG_PERMISSIONS:
                os.chmod(filename, attr.st_mode)
            if attr._flags & attr.FLAG_UIDGID:
                os.chown(filename, attr.st_uid, attr.st_gid)
        if attr._flags & attr.FLAG_AMTIME:
            os.utime(filename, (attr.st_atime, attr.st_mtime))
        if attr._flags & attr.FLAG_SIZE:
            with open(filename, 'w+') as f:
                f.truncate(attr.st_size)
    set_file_attr = staticmethod(set_file_attr)

    ###  internals...

    def _response(self, request_number, t, *arg):
        msg = Message()
        msg.add_int(request_number)
        for item in arg:
            if isinstance(item, long):
                msg.add_int64(item)
            elif isinstance(item, int):
                msg.add_int(item)
            elif isinstance(item, (string_types, bytes_types)):
                msg.add_string(item)
            elif type(item) is SFTPAttributes:
                item._pack(msg)
            else:
                raise Exception('unknown type for ' + repr(item) + ' type ' + repr(type(item)))
        self._send_packet(t, msg)

    def _send_handle_response(self, request_number, handle, folder=False):
        if not issubclass(type(handle), SFTPHandle):
            # must be error code
            self._send_status(request_number, handle)
            return
        handle._set_name(b('hx%d' % self.next_handle))
        self.next_handle += 1
        if folder:
            self.folder_table[handle._get_name()] = handle
        else:
            self.file_table[handle._get_name()] = handle
        self._response(request_number, CMD_HANDLE, handle._get_name())

    def _send_status(self, request_number, code, desc=None):
        if desc is None:
            try:
                desc = SFTP_DESC[code]
            except IndexError:
                desc = 'Unknown'
        # some clients expect a "langauge" tag at the end (but don't mind it being blank)
        self._response(request_number, CMD_STATUS, code, desc, '')

    def _open_folder(self, request_number, path):
        resp = self.server.list_folder(path)
        if issubclass(type(resp), list):
            # got an actual list of filenames in the folder
            folder = SFTPHandle()
            folder._set_files(resp)
            self._send_handle_response(request_number, folder, True)
            return
        # must be an error code
        self._send_status(request_number, resp)

    def _read_folder(self, request_number, folder):
        flist = folder._get_next_files()
        if len(flist) == 0:
            self._send_status(request_number, SFTP_EOF)
            return
        msg = Message()
        msg.add_int(request_number)
        msg.add_int(len(flist))
        for attr in flist:
            msg.add_string(attr.filename)
            msg.add_string(attr)
            attr._pack(msg)
        self._send_packet(CMD_NAME, msg)

    def _check_file(self, request_number, msg):
        # this extension actually comes from v6 protocol, but since it's an
        # extension, i feel like we can reasonably support it backported.
        # it's very useful for verifying uploaded files or checking for
        # rsync-like differences between local and remote files.
        handle = msg.get_binary()
        alg_list = msg.get_list()
        start = msg.get_int64()
        length = msg.get_int64()
        block_size = msg.get_int()
        if handle not in self.file_table:
            self._send_status(request_number, SFTP_BAD_MESSAGE, 'Invalid handle')
            return
        f = self.file_table[handle]
        for x in alg_list:
            if x in _hash_class:
                algname = x
                alg = _hash_class[x]
                break
        else:
            self._send_status(request_number, SFTP_FAILURE, 'No supported hash types found')
            return
        if length == 0:
            st = f.stat()
            if not issubclass(type(st), SFTPAttributes):
                self._send_status(request_number, st, 'Unable to stat file')
                return
            length = st.st_size - start
        if block_size == 0:
            block_size = length
        if block_size < 256:
            self._send_status(request_number, SFTP_FAILURE, 'Block size too small')
            return

        sum_out = bytes()
        offset = start
        while offset < start + length:
            blocklen = min(block_size, start + length - offset)
            # don't try to read more than about 64KB at a time
            chunklen = min(blocklen, 65536)
            count = 0
            hash_obj = alg()
            while count < blocklen:
                data = f.read(offset, chunklen)
                if not isinstance(data, bytes_types):
                    self._send_status(request_number, data, 'Unable to hash file')
                    return
                hash_obj.update(data)
                count += len(data)
                offset += count
            sum_out += hash_obj.digest()

        msg = Message()
        msg.add_int(request_number)
        msg.add_string('check-file')
        msg.add_string(algname)
        msg.add_bytes(sum_out)
        self._send_packet(CMD_EXTENDED_REPLY, msg)

    def _convert_pflags(self, pflags):
        """convert SFTP-style open() flags to Python's os.open() flags"""
        if (pflags & SFTP_FLAG_READ) and (pflags & SFTP_FLAG_WRITE):
            flags = os.O_RDWR
        elif pflags & SFTP_FLAG_WRITE:
            flags = os.O_WRONLY
        else:
            flags = os.O_RDONLY
        if pflags & SFTP_FLAG_APPEND:
            flags |= os.O_APPEND
        if pflags & SFTP_FLAG_CREATE:
            flags |= os.O_CREAT
        if pflags & SFTP_FLAG_TRUNC:
            flags |= os.O_TRUNC
        if pflags & SFTP_FLAG_EXCL:
            flags |= os.O_EXCL
        return flags

    def _process(self, t, request_number, msg):
        self._log(DEBUG, 'Request: %s' % CMD_NAMES[t])
        if t == CMD_OPEN:
            path = msg.get_text()
            flags = self._convert_pflags(msg.get_int())
            attr = SFTPAttributes._from_msg(msg)
            self._send_handle_response(request_number, self.server.open(path, flags, attr))
        elif t == CMD_CLOSE:
            handle = msg.get_binary()
            if handle in self.folder_table:
                del self.folder_table[handle]
                self._send_status(request_number, SFTP_OK)
                return
            if handle in self.file_table:
                self.file_table[handle].close()
                del self.file_table[handle]
                self._send_status(request_number, SFTP_OK)
                return
            self._send_status(request_number, SFTP_BAD_MESSAGE, 'Invalid handle')
        elif t == CMD_READ:
            handle = msg.get_binary()
            offset = msg.get_int64()
            length = msg.get_int()
            if handle not in self.file_table:
                self._send_status(request_number, SFTP_BAD_MESSAGE, 'Invalid handle')
                return
            data = self.file_table[handle].read(offset, length)
            if isinstance(data, (bytes_types, string_types)):
                if len(data) == 0:
                    self._send_status(request_number, SFTP_EOF)
                else:
                    self._response(request_number, CMD_DATA, data)
            else:
                self._send_status(request_number, data)
        elif t == CMD_WRITE:
            handle = msg.get_binary()
            offset = msg.get_int64()
            data = msg.get_binary()
            if handle not in self.file_table:
                self._send_status(request_number, SFTP_BAD_MESSAGE, 'Invalid handle')
                return
            self._send_status(request_number, self.file_table[handle].write(offset, data))
        elif t == CMD_REMOVE:
            path = msg.get_text()
            self._send_status(request_number, self.server.remove(path))
        elif t == CMD_RENAME:
            oldpath = msg.get_text()
            newpath = msg.get_text()
            self._send_status(request_number, self.server.rename(oldpath, newpath))
        elif t == CMD_MKDIR:
            path = msg.get_text()
            attr = SFTPAttributes._from_msg(msg)
            self._send_status(request_number, self.server.mkdir(path, attr))
        elif t == CMD_RMDIR:
            path = msg.get_text()
            self._send_status(request_number, self.server.rmdir(path))
        elif t == CMD_OPENDIR:
            path = msg.get_text()
            self._open_folder(request_number, path)
            return
        elif t == CMD_READDIR:
            handle = msg.get_binary()
            if handle not in self.folder_table:
                self._send_status(request_number, SFTP_BAD_MESSAGE, 'Invalid handle')
                return
            folder = self.folder_table[handle]
            self._read_folder(request_number, folder)
        elif t == CMD_STAT:
            path = msg.get_text()
            resp = self.server.stat(path)
            if issubclass(type(resp), SFTPAttributes):
                self._response(request_number, CMD_ATTRS, resp)
            else:
                self._send_status(request_number, resp)
        elif t == CMD_LSTAT:
            path = msg.get_text()
            resp = self.server.lstat(path)
            if issubclass(type(resp), SFTPAttributes):
                self._response(request_number, CMD_ATTRS, resp)
            else:
                self._send_status(request_number, resp)
        elif t == CMD_FSTAT:
            handle = msg.get_binary()
            if handle not in self.file_table:
                self._send_status(request_number, SFTP_BAD_MESSAGE, 'Invalid handle')
                return
            resp = self.file_table[handle].stat()
            if issubclass(type(resp), SFTPAttributes):
                self._response(request_number, CMD_ATTRS, resp)
            else:
                self._send_status(request_number, resp)
        elif t == CMD_SETSTAT:
            path = msg.get_text()
            attr = SFTPAttributes._from_msg(msg)
            self._send_status(request_number, self.server.chattr(path, attr))
        elif t == CMD_FSETSTAT:
            handle = msg.get_binary()
            attr = SFTPAttributes._from_msg(msg)
            if handle not in self.file_table:
                self._response(request_number, SFTP_BAD_MESSAGE, 'Invalid handle')
                return
            self._send_status(request_number, self.file_table[handle].chattr(attr))
        elif t == CMD_READLINK:
            path = msg.get_text()
            resp = self.server.readlink(path)
            if isinstance(resp, (bytes_types, string_types)):
                self._response(request_number, CMD_NAME, 1, resp, '', SFTPAttributes())
            else:
                self._send_status(request_number, resp)
        elif t == CMD_SYMLINK:
            # the sftp 2 draft is incorrect here!  path always follows target_path
            target_path = msg.get_text()
            path = msg.get_text()
            self._send_status(request_number, self.server.symlink(target_path, path))
        elif t == CMD_REALPATH:
            path = msg.get_text()
            rpath = self.server.canonicalize(path)
            self._response(request_number, CMD_NAME, 1, rpath, '', SFTPAttributes())
        elif t == CMD_EXTENDED:
            tag = msg.get_text()
            if tag == 'check-file':
                self._check_file(request_number, msg)
            else:
                self._send_status(request_number, SFTP_OP_UNSUPPORTED)
        else:
            self._send_status(request_number, SFTP_OP_UNSUPPORTED)


from paramiko.sftp_handle import SFTPHandle

########NEW FILE########
__FILENAME__ = sftp_si
# Copyright (C) 2003-2007  Robey Pointer <robeypointer@gmail.com>
#
# This file is part of paramiko.
#
# Paramiko is free software; you can redistribute it and/or modify it under the
# terms of the GNU Lesser General Public License as published by the Free
# Software Foundation; either version 2.1 of the License, or (at your option)
# any later version.
#
# Paramiko is distributed in the hope that it will be useful, but WITHOUT ANY
# WARRANTY; without even the implied warranty of MERCHANTABILITY or FITNESS FOR
# A PARTICULAR PURPOSE.  See the GNU Lesser General Public License for more
# details.
#
# You should have received a copy of the GNU Lesser General Public License
# along with Paramiko; if not, write to the Free Software Foundation, Inc.,
# 59 Temple Place, Suite 330, Boston, MA  02111-1307  USA.

"""
An interface to override for SFTP server support.
"""

import os
import sys
from paramiko.sftp import SFTP_OP_UNSUPPORTED


class SFTPServerInterface (object):
    """
    This class defines an interface for controlling the behavior of paramiko
    when using the `.SFTPServer` subsystem to provide an SFTP server.

    Methods on this class are called from the SFTP session's thread, so you can
    block as long as necessary without affecting other sessions (even other
    SFTP sessions).  However, raising an exception will usually cause the SFTP
    session to abruptly end, so you will usually want to catch exceptions and
    return an appropriate error code.
    
    All paths are in string form instead of unicode because not all SFTP
    clients & servers obey the requirement that paths be encoded in UTF-8.
    """
    
    def __init__(self, server, *largs, **kwargs):
        """
        Create a new SFTPServerInterface object.  This method does nothing by
        default and is meant to be overridden by subclasses.
        
        :param .ServerInterface server:
            the server object associated with this channel and SFTP subsystem
        """
        super(SFTPServerInterface, self).__init__(*largs, **kwargs)

    def session_started(self):
        """
        The SFTP server session has just started.  This method is meant to be
        overridden to perform any necessary setup before handling callbacks
        from SFTP operations.
        """
        pass

    def session_ended(self):
        """
        The SFTP server session has just ended, either cleanly or via an
        exception.  This method is meant to be overridden to perform any
        necessary cleanup before this `.SFTPServerInterface` object is
        destroyed.
        """
        pass

    def open(self, path, flags, attr):
        """
        Open a file on the server and create a handle for future operations
        on that file.  On success, a new object subclassed from `.SFTPHandle`
        should be returned.  This handle will be used for future operations
        on the file (read, write, etc).  On failure, an error code such as
        `.SFTP_PERMISSION_DENIED` should be returned.

        ``flags`` contains the requested mode for opening (read-only,
        write-append, etc) as a bitset of flags from the ``os`` module:

            - ``os.O_RDONLY``
            - ``os.O_WRONLY``
            - ``os.O_RDWR``
            - ``os.O_APPEND``
            - ``os.O_CREAT``
            - ``os.O_TRUNC``
            - ``os.O_EXCL``

        (One of ``os.O_RDONLY``, ``os.O_WRONLY``, or ``os.O_RDWR`` will always
        be set.)

        The ``attr`` object contains requested attributes of the file if it
        has to be created.  Some or all attribute fields may be missing if
        the client didn't specify them.
        
        .. note:: The SFTP protocol defines all files to be in "binary" mode.
            There is no equivalent to Python's "text" mode.

        :param str path:
            the requested path (relative or absolute) of the file to be opened.
        :param int flags:
            flags or'd together from the ``os`` module indicating the requested
            mode for opening the file.
        :param .SFTPAttributes attr:
            requested attributes of the file if it is newly created.
        :return: a new `.SFTPHandle` or error code.
        """
        return SFTP_OP_UNSUPPORTED

    def list_folder(self, path):
        """
        Return a list of files within a given folder.  The ``path`` will use
        posix notation (``"/"`` separates folder names) and may be an absolute
        or relative path.

        The list of files is expected to be a list of `.SFTPAttributes`
        objects, which are similar in structure to the objects returned by
        ``os.stat``.  In addition, each object should have its ``filename``
        field filled in, since this is important to a directory listing and
        not normally present in ``os.stat`` results.  The method
        `.SFTPAttributes.from_stat` will usually do what you want.

        In case of an error, you should return one of the ``SFTP_*`` error
        codes, such as `.SFTP_PERMISSION_DENIED`.

        :param str path: the requested path (relative or absolute) to be listed.
        :return:
            a list of the files in the given folder, using `.SFTPAttributes`
            objects.
        
        .. note::
            You should normalize the given ``path`` first (see the `os.path`
            module) and check appropriate permissions before returning the list
            of files.  Be careful of malicious clients attempting to use
            relative paths to escape restricted folders, if you're doing a
            direct translation from the SFTP server path to your local
            filesystem.
        """
        return SFTP_OP_UNSUPPORTED

    def stat(self, path):
        """
        Return an `.SFTPAttributes` object for a path on the server, or an
        error code.  If your server supports symbolic links (also known as
        "aliases"), you should follow them.  (`lstat` is the corresponding
        call that doesn't follow symlinks/aliases.)

        :param str path:
            the requested path (relative or absolute) to fetch file statistics
            for.
        :return:
            an `.SFTPAttributes` object for the given file, or an SFTP error
            code (like `.SFTP_PERMISSION_DENIED`).
        """
        return SFTP_OP_UNSUPPORTED

    def lstat(self, path):
        """
        Return an `.SFTPAttributes` object for a path on the server, or an
        error code.  If your server supports symbolic links (also known as
        "aliases"), you should not follow them -- instead, you should
        return data on the symlink or alias itself.  (`stat` is the
        corresponding call that follows symlinks/aliases.)

        :param str path:
            the requested path (relative or absolute) to fetch file statistics
            for.
        :type path: str
        :return:
            an `.SFTPAttributes` object for the given file, or an SFTP error
            code (like `.SFTP_PERMISSION_DENIED`).
        """
        return SFTP_OP_UNSUPPORTED

    def remove(self, path):
        """
        Delete a file, if possible.

        :param str path:
            the requested path (relative or absolute) of the file to delete.
        :return: an SFTP error code `int` like `.SFTP_OK`.
        """
        return SFTP_OP_UNSUPPORTED

    def rename(self, oldpath, newpath):
        """
        Rename (or move) a file.  The SFTP specification implies that this
        method can be used to move an existing file into a different folder,
        and since there's no other (easy) way to move files via SFTP, it's
        probably a good idea to implement "move" in this method too, even for
        files that cross disk partition boundaries, if at all possible.
        
        .. note:: You should return an error if a file with the same name as
            ``newpath`` already exists.  (The rename operation should be
            non-desctructive.)

        :param str oldpath:
            the requested path (relative or absolute) of the existing file.
        :param str newpath: the requested new path of the file.
        :return: an SFTP error code `int` like `.SFTP_OK`.
        """
        return SFTP_OP_UNSUPPORTED

    def mkdir(self, path, attr):
        """
        Create a new directory with the given attributes.  The ``attr``
        object may be considered a "hint" and ignored.

        The ``attr`` object will contain only those fields provided by the
        client in its request, so you should use ``hasattr`` to check for
        the presense of fields before using them.  In some cases, the ``attr``
        object may be completely empty.

        :param str path:
            requested path (relative or absolute) of the new folder.
        :param .SFTPAttributes attr: requested attributes of the new folder.
        :return: an SFTP error code `int` like `.SFTP_OK`.
        """
        return SFTP_OP_UNSUPPORTED

    def rmdir(self, path):
        """
        Remove a directory if it exists.  The ``path`` should refer to an
        existing, empty folder -- otherwise this method should return an
        error.

        :param str path:
            requested path (relative or absolute) of the folder to remove.
        :return: an SFTP error code `int` like `.SFTP_OK`.
        """
        return SFTP_OP_UNSUPPORTED

    def chattr(self, path, attr):
        """
        Change the attributes of a file.  The ``attr`` object will contain
        only those fields provided by the client in its request, so you
        should check for the presence of fields before using them.

        :param str path:
            requested path (relative or absolute) of the file to change.
        :param attr:
            requested attributes to change on the file (an `.SFTPAttributes`
            object)
        :return: an error code `int` like `.SFTP_OK`.
        """
        return SFTP_OP_UNSUPPORTED

    def canonicalize(self, path):
        """
        Return the canonical form of a path on the server.  For example,
        if the server's home folder is ``/home/foo``, the path
        ``"../betty"`` would be canonicalized to ``"/home/betty"``.  Note
        the obvious security issues: if you're serving files only from a
        specific folder, you probably don't want this method to reveal path
        names outside that folder.

        You may find the Python methods in ``os.path`` useful, especially
        ``os.path.normpath`` and ``os.path.realpath``.

        The default implementation returns ``os.path.normpath('/' + path)``.
        """
        if os.path.isabs(path):
            out = os.path.normpath(path)
        else:
            out = os.path.normpath('/' + path)
        if sys.platform == 'win32':
            # on windows, normalize backslashes to sftp/posix format
            out = out.replace('\\', '/')
        return out
    
    def readlink(self, path):
        """
        Return the target of a symbolic link (or shortcut) on the server.
        If the specified path doesn't refer to a symbolic link, an error
        should be returned.
        
        :param str path: path (relative or absolute) of the symbolic link.
        :return:
            the target `str` path of the symbolic link, or an error code like
            `.SFTP_NO_SUCH_FILE`.
        """
        return SFTP_OP_UNSUPPORTED
    
    def symlink(self, target_path, path):
        """
        Create a symbolic link on the server, as new pathname ``path``,
        with ``target_path`` as the target of the link.
        
        :param str target_path:
            path (relative or absolute) of the target for this new symbolic
            link.
        :param str path:
            path (relative or absolute) of the symbolic link to create.
        :return: an error code `int` like ``SFTP_OK``.
        """
        return SFTP_OP_UNSUPPORTED

########NEW FILE########
__FILENAME__ = ssh_exception
# Copyright (C) 2003-2007  Robey Pointer <robeypointer@gmail.com>
#
# This file is part of paramiko.
#
# Paramiko is free software; you can redistribute it and/or modify it under the
# terms of the GNU Lesser General Public License as published by the Free
# Software Foundation; either version 2.1 of the License, or (at your option)
# any later version.
#
# Paramiko is distributed in the hope that it will be useful, but WITHOUT ANY
# WARRANTY; without even the implied warranty of MERCHANTABILITY or FITNESS FOR
# A PARTICULAR PURPOSE.  See the GNU Lesser General Public License for more
# details.
#
# You should have received a copy of the GNU Lesser General Public License
# along with Paramiko; if not, write to the Free Software Foundation, Inc.,
# 59 Temple Place, Suite 330, Boston, MA  02111-1307  USA.


class SSHException (Exception):
    """
    Exception raised by failures in SSH2 protocol negotiation or logic errors.
    """
    pass


class AuthenticationException (SSHException):
    """
    Exception raised when authentication failed for some reason.  It may be
    possible to retry with different credentials.  (Other classes specify more
    specific reasons.)
    
    .. versionadded:: 1.6
    """
    pass
    

class PasswordRequiredException (AuthenticationException):
    """
    Exception raised when a password is needed to unlock a private key file.
    """
    pass


class BadAuthenticationType (AuthenticationException):
    """
    Exception raised when an authentication type (like password) is used, but
    the server isn't allowing that type.  (It may only allow public-key, for
    example.)
    
    :ivar list allowed_types:
        list of allowed authentication types provided by the server (possible
        values are: ``"none"``, ``"password"``, and ``"publickey"``).
    
    .. versionadded:: 1.1
    """
    allowed_types = []
    
    def __init__(self, explanation, types):
        AuthenticationException.__init__(self, explanation)
        self.allowed_types = types
        # for unpickling
        self.args = (explanation, types, )

    def __str__(self):
        return SSHException.__str__(self) + ' (allowed_types=%r)' % self.allowed_types


class PartialAuthentication (AuthenticationException):
    """
    An internal exception thrown in the case of partial authentication.
    """
    allowed_types = []
    
    def __init__(self, types):
        AuthenticationException.__init__(self, 'partial authentication')
        self.allowed_types = types
        # for unpickling
        self.args = (types, )


class ChannelException (SSHException):
    """
    Exception raised when an attempt to open a new `.Channel` fails.
    
    :ivar int code: the error code returned by the server
    
    .. versionadded:: 1.6
    """
    def __init__(self, code, text):
        SSHException.__init__(self, text)
        self.code = code
        # for unpickling
        self.args = (code, text, )


class BadHostKeyException (SSHException):
    """
    The host key given by the SSH server did not match what we were expecting.
    
    :ivar str hostname: the hostname of the SSH server
    :ivar PKey got_key: the host key presented by the server
    :ivar PKey expected_key: the host key expected
    
    .. versionadded:: 1.6
    """
    def __init__(self, hostname, got_key, expected_key):
        SSHException.__init__(self, 'Host key for server %s does not match!' % hostname)
        self.hostname = hostname
        self.key = got_key
        self.expected_key = expected_key
        # for unpickling
        self.args = (hostname, got_key, expected_key, )


class ProxyCommandFailure (SSHException):
    """
    The "ProxyCommand" found in the .ssh/config file returned an error.

    :ivar str command: The command line that is generating this exception.
    :ivar str error: The error captured from the proxy command output.
    """
    def __init__(self, command, error):
        SSHException.__init__(self,
            '"ProxyCommand (%s)" returned non-zero exit status: %s' % (
                command, error
            )
        )
        self.error = error
        # for unpickling
        self.args = (command, error, )

########NEW FILE########
__FILENAME__ = transport
# Copyright (C) 2003-2007  Robey Pointer <robeypointer@gmail.com>
#
# This file is part of paramiko.
#
# Paramiko is free software; you can redistribute it and/or modify it under the
# terms of the GNU Lesser General Public License as published by the Free
# Software Foundation; either version 2.1 of the License, or (at your option)
# any later version.
#
# Paramiko is distributed in the hope that it will be useful, but WITHOUT ANY
# WARRANTY; without even the implied warranty of MERCHANTABILITY or FITNESS FOR
# A PARTICULAR PURPOSE.  See the GNU Lesser General Public License for more
# details.
#
# You should have received a copy of the GNU Lesser General Public License
# along with Paramiko; if not, write to the Free Software Foundation, Inc.,
# 59 Temple Place, Suite 330, Boston, MA  02111-1307  USA.

"""
Core protocol implementation
"""

import os
import socket
import sys
import threading
import time
import weakref
from hashlib import md5, sha1

import paramiko
from paramiko import util
from paramiko.auth_handler import AuthHandler
from paramiko.channel import Channel
from paramiko.common import xffffffff, cMSG_CHANNEL_OPEN, cMSG_IGNORE, \
    cMSG_GLOBAL_REQUEST, DEBUG, MSG_KEXINIT, MSG_IGNORE, MSG_DISCONNECT, \
    MSG_DEBUG, ERROR, WARNING, cMSG_UNIMPLEMENTED, INFO, cMSG_KEXINIT, \
    cMSG_NEWKEYS, MSG_NEWKEYS, cMSG_REQUEST_SUCCESS, cMSG_REQUEST_FAILURE, \
    CONNECTION_FAILED_CODE, OPEN_FAILED_ADMINISTRATIVELY_PROHIBITED, \
    OPEN_SUCCEEDED, cMSG_CHANNEL_OPEN_FAILURE, cMSG_CHANNEL_OPEN_SUCCESS, \
    MSG_GLOBAL_REQUEST, MSG_REQUEST_SUCCESS, MSG_REQUEST_FAILURE, \
    MSG_CHANNEL_OPEN_SUCCESS, MSG_CHANNEL_OPEN_FAILURE, MSG_CHANNEL_OPEN, \
    MSG_CHANNEL_SUCCESS, MSG_CHANNEL_FAILURE, MSG_CHANNEL_DATA, \
    MSG_CHANNEL_EXTENDED_DATA, MSG_CHANNEL_WINDOW_ADJUST, MSG_CHANNEL_REQUEST, \
    MSG_CHANNEL_EOF, MSG_CHANNEL_CLOSE
from paramiko.compress import ZlibCompressor, ZlibDecompressor
from paramiko.dsskey import DSSKey
from paramiko.kex_gex import KexGex
from paramiko.kex_group1 import KexGroup1
from paramiko.message import Message
from paramiko.packet import Packetizer, NeedRekeyException
from paramiko.primes import ModulusPack
from paramiko.py3compat import string_types, long, byte_ord, b
from paramiko.rsakey import RSAKey
from paramiko.ecdsakey import ECDSAKey
from paramiko.server import ServerInterface
from paramiko.sftp_client import SFTPClient
from paramiko.ssh_exception import (SSHException, BadAuthenticationType,
                                    ChannelException, ProxyCommandFailure)
from paramiko.util import retry_on_signal

from Crypto.Cipher import Blowfish, AES, DES3, ARC4
try:
    from Crypto.Util import Counter
except ImportError:
    from paramiko.util import Counter


# for thread cleanup
_active_threads = []

def _join_lingering_threads():
    for thr in _active_threads:
        thr.stop_thread()

import atexit
atexit.register(_join_lingering_threads)


class Transport (threading.Thread):
    """
    An SSH Transport attaches to a stream (usually a socket), negotiates an
    encrypted session, authenticates, and then creates stream tunnels, called
    `channels <.Channel>`, across the session.  Multiple channels can be
    multiplexed across a single session (and often are, in the case of port
    forwardings).
    """
    _PROTO_ID = '2.0'
    _CLIENT_ID = 'paramiko_%s' % paramiko.__version__

    _preferred_ciphers = ('aes128-ctr', 'aes256-ctr', 'aes128-cbc', 'blowfish-cbc',
                          'aes256-cbc', '3des-cbc', 'arcfour128', 'arcfour256')
    _preferred_macs = ('hmac-sha1', 'hmac-md5', 'hmac-sha1-96', 'hmac-md5-96')
    _preferred_keys = ('ssh-rsa', 'ssh-dss', 'ecdsa-sha2-nistp256')
    _preferred_kex = ('diffie-hellman-group1-sha1', 'diffie-hellman-group-exchange-sha1')
    _preferred_compression = ('none',)

    _cipher_info = {
        'aes128-ctr': {'class': AES, 'mode': AES.MODE_CTR, 'block-size': 16, 'key-size': 16},
        'aes256-ctr': {'class': AES, 'mode': AES.MODE_CTR, 'block-size': 16, 'key-size': 32},
        'blowfish-cbc': {'class': Blowfish, 'mode': Blowfish.MODE_CBC, 'block-size': 8, 'key-size': 16},
        'aes128-cbc': {'class': AES, 'mode': AES.MODE_CBC, 'block-size': 16, 'key-size': 16},
        'aes256-cbc': {'class': AES, 'mode': AES.MODE_CBC, 'block-size': 16, 'key-size': 32},
        '3des-cbc': {'class': DES3, 'mode': DES3.MODE_CBC, 'block-size': 8, 'key-size': 24},
        'arcfour128': {'class': ARC4, 'mode': None, 'block-size': 8, 'key-size': 16},
        'arcfour256': {'class': ARC4, 'mode': None, 'block-size': 8, 'key-size': 32},
    }

    _mac_info = {
        'hmac-sha1': {'class': sha1, 'size': 20},
        'hmac-sha1-96': {'class': sha1, 'size': 12},
        'hmac-md5': {'class': md5, 'size': 16},
        'hmac-md5-96': {'class': md5, 'size': 12},
    }

    _key_info = {
        'ssh-rsa': RSAKey,
        'ssh-dss': DSSKey,
        'ecdsa-sha2-nistp256': ECDSAKey,
    }

    _kex_info = {
        'diffie-hellman-group1-sha1': KexGroup1,
        'diffie-hellman-group-exchange-sha1': KexGex,
    }

    _compression_info = {
        # zlib@openssh.com is just zlib, but only turned on after a successful
        # authentication.  openssh servers may only offer this type because
        # they've had troubles with security holes in zlib in the past.
        'zlib@openssh.com': (ZlibCompressor, ZlibDecompressor),
        'zlib': (ZlibCompressor, ZlibDecompressor),
        'none': (None, None),
    }

    _modulus_pack = None

    def __init__(self, sock):
        """
        Create a new SSH session over an existing socket, or socket-like
        object.  This only creates the `.Transport` object; it doesn't begin the
        SSH session yet.  Use `connect` or `start_client` to begin a client
        session, or `start_server` to begin a server session.

        If the object is not actually a socket, it must have the following
        methods:

        - ``send(str)``: Writes from 1 to ``len(str)`` bytes, and returns an
          int representing the number of bytes written.  Returns
          0 or raises ``EOFError`` if the stream has been closed.
        - ``recv(int)``: Reads from 1 to ``int`` bytes and returns them as a
          string.  Returns 0 or raises ``EOFError`` if the stream has been
          closed.
        - ``close()``: Closes the socket.
        - ``settimeout(n)``: Sets a (float) timeout on I/O operations.

        For ease of use, you may also pass in an address (as a tuple) or a host
        string as the ``sock`` argument.  (A host string is a hostname with an
        optional port (separated by ``":"``) which will be converted into a
        tuple of ``(hostname, port)``.)  A socket will be connected to this
        address and used for communication.  Exceptions from the ``socket``
        call may be thrown in this case.

        :param socket sock:
            a socket or socket-like object to create the session over.
        """
        if isinstance(sock, string_types):
            # convert "host:port" into (host, port)
            hl = sock.split(':', 1)
            if len(hl) == 1:
                sock = (hl[0], 22)
            else:
                sock = (hl[0], int(hl[1]))
        if type(sock) is tuple:
            # connect to the given (host, port)
            hostname, port = sock
            reason = 'No suitable address family'
            for (family, socktype, proto, canonname, sockaddr) in socket.getaddrinfo(hostname, port, socket.AF_UNSPEC, socket.SOCK_STREAM):
                if socktype == socket.SOCK_STREAM:
                    af = family
                    addr = sockaddr
                    sock = socket.socket(af, socket.SOCK_STREAM)
                    try:
                        retry_on_signal(lambda: sock.connect((hostname, port)))
                    except socket.error as e:
                        reason = str(e)
                    else:
                        break
            else:
                raise SSHException(
                    'Unable to connect to %s: %s' % (hostname, reason))
        # okay, normal socket-ish flow here...
        threading.Thread.__init__(self)
        self.setDaemon(True)
        self.sock = sock
        # Python < 2.3 doesn't have the settimeout method - RogerB
        try:
            # we set the timeout so we can check self.active periodically to
            # see if we should bail.  socket.timeout exception is never
            # propagated.
            self.sock.settimeout(0.1)
        except AttributeError:
            pass

        # negotiated crypto parameters
        self.packetizer = Packetizer(sock)
        self.local_version = 'SSH-' + self._PROTO_ID + '-' + self._CLIENT_ID
        self.remote_version = ''
        self.local_cipher = self.remote_cipher = ''
        self.local_kex_init = self.remote_kex_init = None
        self.local_mac = self.remote_mac = None
        self.local_compression = self.remote_compression = None
        self.session_id = None
        self.host_key_type = None
        self.host_key = None

        # state used during negotiation
        self.kex_engine = None
        self.H = None
        self.K = None

        self.active = False
        self.initial_kex_done = False
        self.in_kex = False
        self.authenticated = False
        self._expected_packet = tuple()
        self.lock = threading.Lock()    # synchronization (always higher level than write_lock)

        # tracking open channels
        self._channels = ChannelMap()
        self.channel_events = {}       # (id -> Event)
        self.channels_seen = {}        # (id -> True)
        self._channel_counter = 1
        self.window_size = 65536
        self.max_packet_size = 34816
        self._forward_agent_handler = None
        self._x11_handler = None
        self._tcp_handler = None

        self.saved_exception = None
        self.clear_to_send = threading.Event()
        self.clear_to_send_lock = threading.Lock()
        self.clear_to_send_timeout = 30.0
        self.log_name = 'paramiko.transport'
        self.logger = util.get_logger(self.log_name)
        self.packetizer.set_log(self.logger)
        self.auth_handler = None
        self.global_response = None     # response Message from an arbitrary global request
        self.completion_event = None    # user-defined event callbacks
        self.banner_timeout = 15        # how long (seconds) to wait for the SSH banner

        # server mode:
        self.server_mode = False
        self.server_object = None
        self.server_key_dict = {}
        self.server_accepts = []
        self.server_accept_cv = threading.Condition(self.lock)
        self.subsystem_table = {}

    def __repr__(self):
        """
        Returns a string representation of this object, for debugging.
        """
        out = '<paramiko.Transport at %s' % hex(long(id(self)) & xffffffff)
        if not self.active:
            out += ' (unconnected)'
        else:
            if self.local_cipher != '':
                out += ' (cipher %s, %d bits)' % (self.local_cipher,
                                                  self._cipher_info[self.local_cipher]['key-size'] * 8)
            if self.is_authenticated():
                out += ' (active; %d open channel(s))' % len(self._channels)
            elif self.initial_kex_done:
                out += ' (connected; awaiting auth)'
            else:
                out += ' (connecting)'
        out += '>'
        return out

    def atfork(self):
        """
        Terminate this Transport without closing the session.  On posix
        systems, if a Transport is open during process forking, both parent
        and child will share the underlying socket, but only one process can
        use the connection (without corrupting the session).  Use this method
        to clean up a Transport object without disrupting the other process.

        .. versionadded:: 1.5.3
        """
        self.close()

    def get_security_options(self):
        """
        Return a `.SecurityOptions` object which can be used to tweak the
        encryption algorithms this transport will permit (for encryption,
        digest/hash operations, public keys, and key exchanges) and the order
        of preference for them.
        """
        return SecurityOptions(self)

    def start_client(self, event=None):
        """
        Negotiate a new SSH2 session as a client.  This is the first step after
        creating a new `.Transport`.  A separate thread is created for protocol
        negotiation.

        If an event is passed in, this method returns immediately.  When
        negotiation is done (successful or not), the given ``Event`` will
        be triggered.  On failure, `is_active` will return ``False``.

        (Since 1.4) If ``event`` is ``None``, this method will not return until
        negotation is done.  On success, the method returns normally.
        Otherwise an SSHException is raised.

        After a successful negotiation, you will usually want to authenticate,
        calling `auth_password <Transport.auth_password>` or
        `auth_publickey <Transport.auth_publickey>`.

        .. note:: `connect` is a simpler method for connecting as a client.

        .. note:: After calling this method (or `start_server` or `connect`),
            you should no longer directly read from or write to the original
            socket object.

        :param .threading.Event event:
            an event to trigger when negotiation is complete (optional)

        :raises SSHException: if negotiation fails (and no ``event`` was passed
            in)
        """
        self.active = True
        if event is not None:
            # async, return immediately and let the app poll for completion
            self.completion_event = event
            self.start()
            return

        # synchronous, wait for a result
        self.completion_event = event = threading.Event()
        self.start()
        while True:
            event.wait(0.1)
            if not self.active:
                e = self.get_exception()
                if e is not None:
                    raise e
                raise SSHException('Negotiation failed.')
            if event.isSet():
                break

    def start_server(self, event=None, server=None):
        """
        Negotiate a new SSH2 session as a server.  This is the first step after
        creating a new `.Transport` and setting up your server host key(s).  A
        separate thread is created for protocol negotiation.

        If an event is passed in, this method returns immediately.  When
        negotiation is done (successful or not), the given ``Event`` will
        be triggered.  On failure, `is_active` will return ``False``.

        (Since 1.4) If ``event`` is ``None``, this method will not return until
        negotation is done.  On success, the method returns normally.
        Otherwise an SSHException is raised.

        After a successful negotiation, the client will need to authenticate.
        Override the methods `get_allowed_auths
        <.ServerInterface.get_allowed_auths>`, `check_auth_none
        <.ServerInterface.check_auth_none>`, `check_auth_password
        <.ServerInterface.check_auth_password>`, and `check_auth_publickey
        <.ServerInterface.check_auth_publickey>` in the given ``server`` object
        to control the authentication process.

        After a successful authentication, the client should request to open a
        channel.  Override `check_channel_request
        <.ServerInterface.check_channel_request>` in the given ``server``
        object to allow channels to be opened.

        .. note::
            After calling this method (or `start_client` or `connect`), you
            should no longer directly read from or write to the original socket
            object.

        :param .threading.Event event:
            an event to trigger when negotiation is complete.
        :param .ServerInterface server:
            an object used to perform authentication and create `channels
            <.Channel>`

        :raises SSHException: if negotiation fails (and no ``event`` was passed
            in)
        """
        if server is None:
            server = ServerInterface()
        self.server_mode = True
        self.server_object = server
        self.active = True
        if event is not None:
            # async, return immediately and let the app poll for completion
            self.completion_event = event
            self.start()
            return

        # synchronous, wait for a result
        self.completion_event = event = threading.Event()
        self.start()
        while True:
            event.wait(0.1)
            if not self.active:
                e = self.get_exception()
                if e is not None:
                    raise e
                raise SSHException('Negotiation failed.')
            if event.isSet():
                break

    def add_server_key(self, key):
        """
        Add a host key to the list of keys used for server mode.  When behaving
        as a server, the host key is used to sign certain packets during the
        SSH2 negotiation, so that the client can trust that we are who we say
        we are.  Because this is used for signing, the key must contain private
        key info, not just the public half.  Only one key of each type (RSA or
        DSS) is kept.

        :param .PKey key:
            the host key to add, usually an `.RSAKey` or `.DSSKey`.
        """
        self.server_key_dict[key.get_name()] = key

    def get_server_key(self):
        """
        Return the active host key, in server mode.  After negotiating with the
        client, this method will return the negotiated host key.  If only one
        type of host key was set with `add_server_key`, that's the only key
        that will ever be returned.  But in cases where you have set more than
        one type of host key (for example, an RSA key and a DSS key), the key
        type will be negotiated by the client, and this method will return the
        key of the type agreed on.  If the host key has not been negotiated
        yet, ``None`` is returned.  In client mode, the behavior is undefined.

        :return:
            host key (`.PKey`) of the type negotiated by the client, or
            ``None``.
        """
        try:
            return self.server_key_dict[self.host_key_type]
        except KeyError:
            pass
        return None

    def load_server_moduli(filename=None):
        """
        (optional)
        Load a file of prime moduli for use in doing group-exchange key
        negotiation in server mode.  It's a rather obscure option and can be
        safely ignored.

        In server mode, the remote client may request "group-exchange" key
        negotiation, which asks the server to send a random prime number that
        fits certain criteria.  These primes are pretty difficult to compute,
        so they can't be generated on demand.  But many systems contain a file
        of suitable primes (usually named something like ``/etc/ssh/moduli``).
        If you call `load_server_moduli` and it returns ``True``, then this
        file of primes has been loaded and we will support "group-exchange" in
        server mode.  Otherwise server mode will just claim that it doesn't
        support that method of key negotiation.

        :param str filename:
            optional path to the moduli file, if you happen to know that it's
            not in a standard location.
        :return:
            True if a moduli file was successfully loaded; False otherwise.

        .. note:: This has no effect when used in client mode.
        """
        Transport._modulus_pack = ModulusPack()
        # places to look for the openssh "moduli" file
        file_list = ['/etc/ssh/moduli', '/usr/local/etc/moduli']
        if filename is not None:
            file_list.insert(0, filename)
        for fn in file_list:
            try:
                Transport._modulus_pack.read_file(fn)
                return True
            except IOError:
                pass
        # none succeeded
        Transport._modulus_pack = None
        return False
    load_server_moduli = staticmethod(load_server_moduli)

    def close(self):
        """
        Close this session, and any open channels that are tied to it.
        """
        if not self.active:
            return
        self.stop_thread()
        for chan in list(self._channels.values()):
            chan._unlink()
        self.sock.close()

    def get_remote_server_key(self):
        """
        Return the host key of the server (in client mode).

        .. note::
            Previously this call returned a tuple of ``(key type, key
            string)``. You can get the same effect by calling `.PKey.get_name`
            for the key type, and ``str(key)`` for the key string.

        :raises SSHException: if no session is currently active.

        :return: public key (`.PKey`) of the remote server
        """
        if (not self.active) or (not self.initial_kex_done):
            raise SSHException('No existing session')
        return self.host_key

    def is_active(self):
        """
        Return true if this session is active (open).

        :return:
            True if the session is still active (open); False if the session is
            closed
        """
        return self.active

    def open_session(self):
        """
        Request a new channel to the server, of type ``"session"``.  This is
        just an alias for calling `open_channel` with an argument of
        ``"session"``.

        :return: a new `.Channel`

        :raises SSHException: if the request is rejected or the session ends
            prematurely
        """
        return self.open_channel('session')

    def open_x11_channel(self, src_addr=None):
        """
        Request a new channel to the client, of type ``"x11"``.  This
        is just an alias for ``open_channel('x11', src_addr=src_addr)``.

        :param tuple src_addr:
            the source address (``(str, int)``) of the x11 server (port is the
            x11 port, ie. 6010)
        :return: a new `.Channel`

        :raises SSHException: if the request is rejected or the session ends
            prematurely
        """
        return self.open_channel('x11', src_addr=src_addr)

    def open_forward_agent_channel(self):
        """
        Request a new channel to the client, of type
        ``"auth-agent@openssh.com"``.

        This is just an alias for ``open_channel('auth-agent@openssh.com')``.

        :return: a new `.Channel`

        :raises SSHException:
            if the request is rejected or the session ends prematurely
        """
        return self.open_channel('auth-agent@openssh.com')

    def open_forwarded_tcpip_channel(self, src_addr, dest_addr):
        """
        Request a new channel back to the client, of type ``"forwarded-tcpip"``.
        This is used after a client has requested port forwarding, for sending
        incoming connections back to the client.

        :param src_addr: originator's address
        :param dest_addr: local (server) connected address
        """
        return self.open_channel('forwarded-tcpip', dest_addr, src_addr)

    def open_channel(self, kind, dest_addr=None, src_addr=None):
        """
        Request a new channel to the server. `Channels <.Channel>` are
        socket-like objects used for the actual transfer of data across the
        session. You may only request a channel after negotiating encryption
        (using `connect` or `start_client`) and authenticating.

        :param str kind:
            the kind of channel requested (usually ``"session"``,
            ``"forwarded-tcpip"``, ``"direct-tcpip"``, or ``"x11"``)
        :param tuple dest_addr:
            the destination address (address + port tuple) of this port
            forwarding, if ``kind`` is ``"forwarded-tcpip"`` or
            ``"direct-tcpip"`` (ignored for other channel types)
        :param src_addr: the source address of this port forwarding, if
            ``kind`` is ``"forwarded-tcpip"``, ``"direct-tcpip"``, or ``"x11"``
        :return: a new `.Channel` on success

        :raises SSHException: if the request is rejected or the session ends
            prematurely
        """
        if not self.active:
            raise SSHException('SSH session not active')
        self.lock.acquire()
        try:
            chanid = self._next_channel()
            m = Message()
            m.add_byte(cMSG_CHANNEL_OPEN)
            m.add_string(kind)
            m.add_int(chanid)
            m.add_int(self.window_size)
            m.add_int(self.max_packet_size)
            if (kind == 'forwarded-tcpip') or (kind == 'direct-tcpip'):
                m.add_string(dest_addr[0])
                m.add_int(dest_addr[1])
                m.add_string(src_addr[0])
                m.add_int(src_addr[1])
            elif kind == 'x11':
                m.add_string(src_addr[0])
                m.add_int(src_addr[1])
            chan = Channel(chanid)
            self._channels.put(chanid, chan)
            self.channel_events[chanid] = event = threading.Event()
            self.channels_seen[chanid] = True
            chan._set_transport(self)
            chan._set_window(self.window_size, self.max_packet_size)
        finally:
            self.lock.release()
        self._send_user_message(m)
        while True:
            event.wait(0.1)
            if not self.active:
                e = self.get_exception()
                if e is None:
                    e = SSHException('Unable to open channel.')
                raise e
            if event.isSet():
                break
        chan = self._channels.get(chanid)
        if chan is not None:
            return chan
        e = self.get_exception()
        if e is None:
            e = SSHException('Unable to open channel.')
        raise e

    def request_port_forward(self, address, port, handler=None):
        """
        Ask the server to forward TCP connections from a listening port on
        the server, across this SSH session.

        If a handler is given, that handler is called from a different thread
        whenever a forwarded connection arrives.  The handler parameters are::

            handler(channel, (origin_addr, origin_port), (server_addr, server_port))

        where ``server_addr`` and ``server_port`` are the address and port that
        the server was listening on.

        If no handler is set, the default behavior is to send new incoming
        forwarded connections into the accept queue, to be picked up via
        `accept`.

        :param str address: the address to bind when forwarding
        :param int port:
            the port to forward, or 0 to ask the server to allocate any port
        :param callable handler:
            optional handler for incoming forwarded connections, of the form
            ``func(Channel, (str, int), (str, int))``.
        :return: the port number (`int`) allocated by the server

        :raises SSHException: if the server refused the TCP forward request
        """
        if not self.active:
            raise SSHException('SSH session not active')
        port = int(port)
        response = self.global_request('tcpip-forward', (address, port), wait=True)
        if response is None:
            raise SSHException('TCP forwarding request denied')
        if port == 0:
            port = response.get_int()
        if handler is None:
            def default_handler(channel, src_addr, dest_addr_port):
                #src_addr, src_port = src_addr_port
                #dest_addr, dest_port = dest_addr_port
                self._queue_incoming_channel(channel)
            handler = default_handler
        self._tcp_handler = handler
        return port

    def cancel_port_forward(self, address, port):
        """
        Ask the server to cancel a previous port-forwarding request.  No more
        connections to the given address & port will be forwarded across this
        ssh connection.

        :param str address: the address to stop forwarding
        :param int port: the port to stop forwarding
        """
        if not self.active:
            return
        self._tcp_handler = None
        self.global_request('cancel-tcpip-forward', (address, port), wait=True)

    def open_sftp_client(self):
        """
        Create an SFTP client channel from an open transport.  On success, an
        SFTP session will be opened with the remote host, and a new
        `.SFTPClient` object will be returned.

        :return:
            a new `.SFTPClient` referring to an sftp session (channel) across
            this transport
        """
        return SFTPClient.from_transport(self)

    def send_ignore(self, byte_count=None):
        """
        Send a junk packet across the encrypted link.  This is sometimes used
        to add "noise" to a connection to confuse would-be attackers.  It can
        also be used as a keep-alive for long lived connections traversing
        firewalls.

        :param int byte_count:
            the number of random bytes to send in the payload of the ignored
            packet -- defaults to a random number from 10 to 41.
        """
        m = Message()
        m.add_byte(cMSG_IGNORE)
        if byte_count is None:
            byte_count = (byte_ord(os.urandom(1)) % 32) + 10
        m.add_bytes(os.urandom(byte_count))
        self._send_user_message(m)

    def renegotiate_keys(self):
        """
        Force this session to switch to new keys.  Normally this is done
        automatically after the session hits a certain number of packets or
        bytes sent or received, but this method gives you the option of forcing
        new keys whenever you want.  Negotiating new keys causes a pause in
        traffic both ways as the two sides swap keys and do computations.  This
        method returns when the session has switched to new keys.

        :raises SSHException: if the key renegotiation failed (which causes the
            session to end)
        """
        self.completion_event = threading.Event()
        self._send_kex_init()
        while True:
            self.completion_event.wait(0.1)
            if not self.active:
                e = self.get_exception()
                if e is not None:
                    raise e
                raise SSHException('Negotiation failed.')
            if self.completion_event.isSet():
                break
        return

    def set_keepalive(self, interval):
        """
        Turn on/off keepalive packets (default is off).  If this is set, after
        ``interval`` seconds without sending any data over the connection, a
        "keepalive" packet will be sent (and ignored by the remote host).  This
        can be useful to keep connections alive over a NAT, for example.

        :param int interval:
            seconds to wait before sending a keepalive packet (or
            0 to disable keepalives).
        """
        self.packetizer.set_keepalive(interval,
                                      lambda x=weakref.proxy(self): x.global_request('keepalive@lag.net', wait=False))

    def global_request(self, kind, data=None, wait=True):
        """
        Make a global request to the remote host.  These are normally
        extensions to the SSH2 protocol.

        :param str kind: name of the request.
        :param tuple data:
            an optional tuple containing additional data to attach to the
            request.
        :param bool wait:
            ``True`` if this method should not return until a response is
            received; ``False`` otherwise.
        :return:
            a `.Message` containing possible additional data if the request was
            successful (or an empty `.Message` if ``wait`` was ``False``);
            ``None`` if the request was denied.
        """
        if wait:
            self.completion_event = threading.Event()
        m = Message()
        m.add_byte(cMSG_GLOBAL_REQUEST)
        m.add_string(kind)
        m.add_boolean(wait)
        if data is not None:
            m.add(*data)
        self._log(DEBUG, 'Sending global request "%s"' % kind)
        self._send_user_message(m)
        if not wait:
            return None
        while True:
            self.completion_event.wait(0.1)
            if not self.active:
                return None
            if self.completion_event.isSet():
                break
        return self.global_response

    def accept(self, timeout=None):
        """
        Return the next channel opened by the client over this transport, in
        server mode.  If no channel is opened before the given timeout, ``None``
        is returned.

        :param int timeout:
            seconds to wait for a channel, or ``None`` to wait forever
        :return: a new `.Channel` opened by the client
        """
        self.lock.acquire()
        try:
            if len(self.server_accepts) > 0:
                chan = self.server_accepts.pop(0)
            else:
                self.server_accept_cv.wait(timeout)
                if len(self.server_accepts) > 0:
                    chan = self.server_accepts.pop(0)
                else:
                    # timeout
                    chan = None
        finally:
            self.lock.release()
        return chan

    def connect(self, hostkey=None, username='', password=None, pkey=None):
        """
        Negotiate an SSH2 session, and optionally verify the server's host key
        and authenticate using a password or private key.  This is a shortcut
        for `start_client`, `get_remote_server_key`, and
        `Transport.auth_password` or `Transport.auth_publickey`.  Use those
        methods if you want more control.

        You can use this method immediately after creating a Transport to
        negotiate encryption with a server.  If it fails, an exception will be
        thrown.  On success, the method will return cleanly, and an encrypted
        session exists.  You may immediately call `open_channel` or
        `open_session` to get a `.Channel` object, which is used for data
        transfer.

        .. note::
            If you fail to supply a password or private key, this method may
            succeed, but a subsequent `open_channel` or `open_session` call may
            fail because you haven't authenticated yet.

        :param .PKey hostkey:
            the host key expected from the server, or ``None`` if you don't
            want to do host key verification.
        :param str username: the username to authenticate as.
        :param str password:
            a password to use for authentication, if you want to use password
            authentication; otherwise ``None``.
        :param .PKey pkey:
            a private key to use for authentication, if you want to use private
            key authentication; otherwise ``None``.

        :raises SSHException: if the SSH2 negotiation fails, the host key
            supplied by the server is incorrect, or authentication fails.
        """
        if hostkey is not None:
            self._preferred_keys = [hostkey.get_name()]

        self.start_client()

        # check host key if we were given one
        if hostkey is not None:
            key = self.get_remote_server_key()
            if (key.get_name() != hostkey.get_name()) or (key.asbytes() != hostkey.asbytes()):
                self._log(DEBUG, 'Bad host key from server')
                self._log(DEBUG, 'Expected: %s: %s' % (hostkey.get_name(), repr(hostkey.asbytes())))
                self._log(DEBUG, 'Got     : %s: %s' % (key.get_name(), repr(key.asbytes())))
                raise SSHException('Bad host key from server')
            self._log(DEBUG, 'Host key verified (%s)' % hostkey.get_name())

        if (pkey is not None) or (password is not None):
            if password is not None:
                self._log(DEBUG, 'Attempting password auth...')
                self.auth_password(username, password)
            else:
                self._log(DEBUG, 'Attempting public-key auth...')
                self.auth_publickey(username, pkey)

        return

    def get_exception(self):
        """
        Return any exception that happened during the last server request.
        This can be used to fetch more specific error information after using
        calls like `start_client`.  The exception (if any) is cleared after
        this call.

        :return:
            an exception, or ``None`` if there is no stored exception.

        .. versionadded:: 1.1
        """
        self.lock.acquire()
        try:
            e = self.saved_exception
            self.saved_exception = None
            return e
        finally:
            self.lock.release()

    def set_subsystem_handler(self, name, handler, *larg, **kwarg):
        """
        Set the handler class for a subsystem in server mode.  If a request
        for this subsystem is made on an open ssh channel later, this handler
        will be constructed and called -- see `.SubsystemHandler` for more
        detailed documentation.

        Any extra parameters (including keyword arguments) are saved and
        passed to the `.SubsystemHandler` constructor later.

        :param str name: name of the subsystem.
        :param class handler:
            subclass of `.SubsystemHandler` that handles this subsystem.
        """
        try:
            self.lock.acquire()
            self.subsystem_table[name] = (handler, larg, kwarg)
        finally:
            self.lock.release()

    def is_authenticated(self):
        """
        Return true if this session is active and authenticated.

        :return:
            True if the session is still open and has been authenticated
            successfully; False if authentication failed and/or the session is
            closed.
        """
        return self.active and (self.auth_handler is not None) and self.auth_handler.is_authenticated()

    def get_username(self):
        """
        Return the username this connection is authenticated for.  If the
        session is not authenticated (or authentication failed), this method
        returns ``None``.

        :return: username that was authenticated (a `str`), or ``None``.
        """
        if not self.active or (self.auth_handler is None):
            return None
        return self.auth_handler.get_username()

    def get_banner(self):
        """
        Return the banner supplied by the server upon connect. If no banner is
        supplied, this method returns C{None}.

        @return: server supplied banner, or C{None}.
        @rtype: string
        """
        if not self.active or (self.auth_handler is None):
            return None
        return self.auth_handler.banner

    def auth_none(self, username):
        """
        Try to authenticate to the server using no authentication at all.
        This will almost always fail.  It may be useful for determining the
        list of authentication types supported by the server, by catching the
        `.BadAuthenticationType` exception raised.

        :param str username: the username to authenticate as
        :return:
            `list` of auth types permissible for the next stage of
            authentication (normally empty)

        :raises BadAuthenticationType: if "none" authentication isn't allowed
            by the server for this user
        :raises SSHException: if the authentication failed due to a network
            error

        .. versionadded:: 1.5
        """
        if (not self.active) or (not self.initial_kex_done):
            raise SSHException('No existing session')
        my_event = threading.Event()
        self.auth_handler = AuthHandler(self)
        self.auth_handler.auth_none(username, my_event)
        return self.auth_handler.wait_for_response(my_event)

    def auth_password(self, username, password, event=None, fallback=True):
        """
        Authenticate to the server using a password.  The username and password
        are sent over an encrypted link.

        If an ``event`` is passed in, this method will return immediately, and
        the event will be triggered once authentication succeeds or fails.  On
        success, `is_authenticated` will return ``True``.  On failure, you may
        use `get_exception` to get more detailed error information.

        Since 1.1, if no event is passed, this method will block until the
        authentication succeeds or fails.  On failure, an exception is raised.
        Otherwise, the method simply returns.

        Since 1.5, if no event is passed and ``fallback`` is ``True`` (the
        default), if the server doesn't support plain password authentication
        but does support so-called "keyboard-interactive" mode, an attempt
        will be made to authenticate using this interactive mode.  If it fails,
        the normal exception will be thrown as if the attempt had never been
        made.  This is useful for some recent Gentoo and Debian distributions,
        which turn off plain password authentication in a misguided belief
        that interactive authentication is "more secure".  (It's not.)

        If the server requires multi-step authentication (which is very rare),
        this method will return a list of auth types permissible for the next
        step.  Otherwise, in the normal case, an empty list is returned.

        :param str username: the username to authenticate as
        :param basestring password: the password to authenticate with
        :param .threading.Event event:
            an event to trigger when the authentication attempt is complete
            (whether it was successful or not)
        :param bool fallback:
            ``True`` if an attempt at an automated "interactive" password auth
            should be made if the server doesn't support normal password auth
        :return:
            `list` of auth types permissible for the next stage of
            authentication (normally empty)

        :raises BadAuthenticationType: if password authentication isn't
            allowed by the server for this user (and no event was passed in)
        :raises AuthenticationException: if the authentication failed (and no
            event was passed in)
        :raises SSHException: if there was a network error
        """
        if (not self.active) or (not self.initial_kex_done):
            # we should never try to send the password unless we're on a secure link
            raise SSHException('No existing session')
        if event is None:
            my_event = threading.Event()
        else:
            my_event = event
        self.auth_handler = AuthHandler(self)
        self.auth_handler.auth_password(username, password, my_event)
        if event is not None:
            # caller wants to wait for event themselves
            return []
        try:
            return self.auth_handler.wait_for_response(my_event)
        except BadAuthenticationType as e:
            # if password auth isn't allowed, but keyboard-interactive *is*, try to fudge it
            if not fallback or ('keyboard-interactive' not in e.allowed_types):
                raise
            try:
                def handler(title, instructions, fields):
                    if len(fields) > 1:
                        raise SSHException('Fallback authentication failed.')
                    if len(fields) == 0:
                        # for some reason, at least on os x, a 2nd request will
                        # be made with zero fields requested.  maybe it's just
                        # to try to fake out automated scripting of the exact
                        # type we're doing here.  *shrug* :)
                        return []
                    return [password]
                return self.auth_interactive(username, handler)
            except SSHException:
                # attempt failed; just raise the original exception
                raise e

    def auth_publickey(self, username, key, event=None):
        """
        Authenticate to the server using a private key.  The key is used to
        sign data from the server, so it must include the private part.

        If an ``event`` is passed in, this method will return immediately, and
        the event will be triggered once authentication succeeds or fails.  On
        success, `is_authenticated` will return ``True``.  On failure, you may
        use `get_exception` to get more detailed error information.

        Since 1.1, if no event is passed, this method will block until the
        authentication succeeds or fails.  On failure, an exception is raised.
        Otherwise, the method simply returns.

        If the server requires multi-step authentication (which is very rare),
        this method will return a list of auth types permissible for the next
        step.  Otherwise, in the normal case, an empty list is returned.

        :param str username: the username to authenticate as
        :param .PKey key: the private key to authenticate with
        :param .threading.Event event:
            an event to trigger when the authentication attempt is complete
            (whether it was successful or not)
        :return:
            `list` of auth types permissible for the next stage of
            authentication (normally empty)

        :raises BadAuthenticationType: if public-key authentication isn't
            allowed by the server for this user (and no event was passed in)
        :raises AuthenticationException: if the authentication failed (and no
            event was passed in)
        :raises SSHException: if there was a network error
        """
        if (not self.active) or (not self.initial_kex_done):
            # we should never try to authenticate unless we're on a secure link
            raise SSHException('No existing session')
        if event is None:
            my_event = threading.Event()
        else:
            my_event = event
        self.auth_handler = AuthHandler(self)
        self.auth_handler.auth_publickey(username, key, my_event)
        if event is not None:
            # caller wants to wait for event themselves
            return []
        return self.auth_handler.wait_for_response(my_event)

    def auth_interactive(self, username, handler, submethods=''):
        """
        Authenticate to the server interactively.  A handler is used to answer
        arbitrary questions from the server.  On many servers, this is just a
        dumb wrapper around PAM.

        This method will block until the authentication succeeds or fails,
        peroidically calling the handler asynchronously to get answers to
        authentication questions.  The handler may be called more than once
        if the server continues to ask questions.

        The handler is expected to be a callable that will handle calls of the
        form: ``handler(title, instructions, prompt_list)``.  The ``title`` is
        meant to be a dialog-window title, and the ``instructions`` are user
        instructions (both are strings).  ``prompt_list`` will be a list of
        prompts, each prompt being a tuple of ``(str, bool)``.  The string is
        the prompt and the boolean indicates whether the user text should be
        echoed.

        A sample call would thus be:
        ``handler('title', 'instructions', [('Password:', False)])``.

        The handler should return a list or tuple of answers to the server's
        questions.

        If the server requires multi-step authentication (which is very rare),
        this method will return a list of auth types permissible for the next
        step.  Otherwise, in the normal case, an empty list is returned.

        :param str username: the username to authenticate as
        :param callable handler: a handler for responding to server questions
        :param str submethods: a string list of desired submethods (optional)
        :return:
            `list` of auth types permissible for the next stage of
            authentication (normally empty).

        :raises BadAuthenticationType: if public-key authentication isn't
            allowed by the server for this user
        :raises AuthenticationException: if the authentication failed
        :raises SSHException: if there was a network error

        .. versionadded:: 1.5
        """
        if (not self.active) or (not self.initial_kex_done):
            # we should never try to authenticate unless we're on a secure link
            raise SSHException('No existing session')
        my_event = threading.Event()
        self.auth_handler = AuthHandler(self)
        self.auth_handler.auth_interactive(username, handler, my_event, submethods)
        return self.auth_handler.wait_for_response(my_event)

    def set_log_channel(self, name):
        """
        Set the channel for this transport's logging.  The default is
        ``"paramiko.transport"`` but it can be set to anything you want. (See
        the `.logging` module for more info.)  SSH Channels will log to a
        sub-channel of the one specified.

        :param str name: new channel name for logging

        .. versionadded:: 1.1
        """
        self.log_name = name
        self.logger = util.get_logger(name)
        self.packetizer.set_log(self.logger)

    def get_log_channel(self):
        """
        Return the channel name used for this transport's logging.

        :return: channel name as a `str`

        .. versionadded:: 1.2
        """
        return self.log_name

    def set_hexdump(self, hexdump):
        """
        Turn on/off logging a hex dump of protocol traffic at DEBUG level in
        the logs.  Normally you would want this off (which is the default),
        but if you are debugging something, it may be useful.

        :param bool hexdump:
            ``True`` to log protocol traffix (in hex) to the log; ``False``
            otherwise.
        """
        self.packetizer.set_hexdump(hexdump)

    def get_hexdump(self):
        """
        Return ``True`` if the transport is currently logging hex dumps of
        protocol traffic.

        :return: ``True`` if hex dumps are being logged, else ``False``.

        .. versionadded:: 1.4
        """
        return self.packetizer.get_hexdump()

    def use_compression(self, compress=True):
        """
        Turn on/off compression.  This will only have an affect before starting
        the transport (ie before calling `connect`, etc).  By default,
        compression is off since it negatively affects interactive sessions.

        :param bool compress:
            ``True`` to ask the remote client/server to compress traffic;
            ``False`` to refuse compression

        .. versionadded:: 1.5.2
        """
        if compress:
            self._preferred_compression = ('zlib@openssh.com', 'zlib', 'none')
        else:
            self._preferred_compression = ('none',)

    def getpeername(self):
        """
        Return the address of the remote side of this Transport, if possible.
        This is effectively a wrapper around ``'getpeername'`` on the underlying
        socket.  If the socket-like object has no ``'getpeername'`` method,
        then ``("unknown", 0)`` is returned.

        :return:
            the address of the remote host, if known, as a ``(str, int)``
            tuple.
        """
        gp = getattr(self.sock, 'getpeername', None)
        if gp is None:
            return 'unknown', 0
        return gp()

    def stop_thread(self):
        self.active = False
        self.packetizer.close()
        while self.isAlive():
            self.join(10)

    ###  internals...

    def _log(self, level, msg, *args):
        if issubclass(type(msg), list):
            for m in msg:
                self.logger.log(level, m)
        else:
            self.logger.log(level, msg, *args)

    def _get_modulus_pack(self):
        """used by KexGex to find primes for group exchange"""
        return self._modulus_pack

    def _next_channel(self):
        """you are holding the lock"""
        chanid = self._channel_counter
        while self._channels.get(chanid) is not None:
            self._channel_counter = (self._channel_counter + 1) & 0xffffff
            chanid = self._channel_counter
        self._channel_counter = (self._channel_counter + 1) & 0xffffff
        return chanid

    def _unlink_channel(self, chanid):
        """used by a Channel to remove itself from the active channel list"""
        self._channels.delete(chanid)

    def _send_message(self, data):
        self.packetizer.send_message(data)

    def _send_user_message(self, data):
        """
        send a message, but block if we're in key negotiation.  this is used
        for user-initiated requests.
        """
        start = time.time()
        while True:
            self.clear_to_send.wait(0.1)
            if not self.active:
                self._log(DEBUG, 'Dropping user packet because connection is dead.')
                return
            self.clear_to_send_lock.acquire()
            if self.clear_to_send.isSet():
                break
            self.clear_to_send_lock.release()
            if time.time() > start + self.clear_to_send_timeout:
                raise SSHException('Key-exchange timed out waiting for key negotiation')
        try:
            self._send_message(data)
        finally:
            self.clear_to_send_lock.release()

    def _set_K_H(self, k, h):
        """used by a kex object to set the K (root key) and H (exchange hash)"""
        self.K = k
        self.H = h
        if self.session_id is None:
            self.session_id = h

    def _expect_packet(self, *ptypes):
        """used by a kex object to register the next packet type it expects to see"""
        self._expected_packet = tuple(ptypes)

    def _verify_key(self, host_key, sig):
        key = self._key_info[self.host_key_type](Message(host_key))
        if key is None:
            raise SSHException('Unknown host key type')
        if not key.verify_ssh_sig(self.H, Message(sig)):
            raise SSHException('Signature verification (%s) failed.' % self.host_key_type)
        self.host_key = key

    def _compute_key(self, id, nbytes):
        """id is 'A' - 'F' for the various keys used by ssh"""
        m = Message()
        m.add_mpint(self.K)
        m.add_bytes(self.H)
        m.add_byte(b(id))
        m.add_bytes(self.session_id)
        out = sofar = sha1(m.asbytes()).digest()
        while len(out) < nbytes:
            m = Message()
            m.add_mpint(self.K)
            m.add_bytes(self.H)
            m.add_bytes(sofar)
            digest = sha1(m.asbytes()).digest()
            out += digest
            sofar += digest
        return out[:nbytes]

    def _get_cipher(self, name, key, iv):
        if name not in self._cipher_info:
            raise SSHException('Unknown client cipher ' + name)
        if name in ('arcfour128', 'arcfour256'):
            # arcfour cipher
            cipher = self._cipher_info[name]['class'].new(key)
            # as per RFC 4345, the first 1536 bytes of keystream
            # generated by the cipher MUST be discarded
            cipher.encrypt(" " * 1536)
            return cipher
        elif name.endswith("-ctr"):
            # CTR modes, we need a counter
            counter = Counter.new(nbits=self._cipher_info[name]['block-size'] * 8, initial_value=util.inflate_long(iv, True))
            return self._cipher_info[name]['class'].new(key, self._cipher_info[name]['mode'], iv, counter)
        else:
            return self._cipher_info[name]['class'].new(key, self._cipher_info[name]['mode'], iv)

    def _set_forward_agent_handler(self, handler):
        if handler is None:
            def default_handler(channel):
                self._queue_incoming_channel(channel)
            self._forward_agent_handler = default_handler
        else:
            self._forward_agent_handler = handler

    def _set_x11_handler(self, handler):
        # only called if a channel has turned on x11 forwarding
        if handler is None:
            # by default, use the same mechanism as accept()
            def default_handler(channel, src_addr_port):
                self._queue_incoming_channel(channel)
            self._x11_handler = default_handler
        else:
            self._x11_handler = handler

    def _queue_incoming_channel(self, channel):
        self.lock.acquire()
        try:
            self.server_accepts.append(channel)
            self.server_accept_cv.notify()
        finally:
            self.lock.release()

    def run(self):
        # (use the exposed "run" method, because if we specify a thread target
        # of a private method, threading.Thread will keep a reference to it
        # indefinitely, creating a GC cycle and not letting Transport ever be
        # GC'd. it's a bug in Thread.)

        # Hold reference to 'sys' so we can test sys.modules to detect
        # interpreter shutdown.
        self.sys = sys

        # active=True occurs before the thread is launched, to avoid a race
        _active_threads.append(self)
        if self.server_mode:
            self._log(DEBUG, 'starting thread (server mode): %s' % hex(long(id(self)) & xffffffff))
        else:
            self._log(DEBUG, 'starting thread (client mode): %s' % hex(long(id(self)) & xffffffff))
        try:
            try:
                self.packetizer.write_all(b(self.local_version + '\r\n'))
                self._check_banner()
                self._send_kex_init()
                self._expect_packet(MSG_KEXINIT)

                while self.active:
                    if self.packetizer.need_rekey() and not self.in_kex:
                        self._send_kex_init()
                    try:
                        ptype, m = self.packetizer.read_message()
                    except NeedRekeyException:
                        continue
                    if ptype == MSG_IGNORE:
                        continue
                    elif ptype == MSG_DISCONNECT:
                        self._parse_disconnect(m)
                        self.active = False
                        self.packetizer.close()
                        break
                    elif ptype == MSG_DEBUG:
                        self._parse_debug(m)
                        continue
                    if len(self._expected_packet) > 0:
                        if ptype not in self._expected_packet:
                            raise SSHException('Expecting packet from %r, got %d' % (self._expected_packet, ptype))
                        self._expected_packet = tuple()
                        if (ptype >= 30) and (ptype <= 39):
                            self.kex_engine.parse_next(ptype, m)
                            continue

                    if ptype in self._handler_table:
                        self._handler_table[ptype](self, m)
                    elif ptype in self._channel_handler_table:
                        chanid = m.get_int()
                        chan = self._channels.get(chanid)
                        if chan is not None:
                            self._channel_handler_table[ptype](chan, m)
                        elif chanid in self.channels_seen:
                            self._log(DEBUG, 'Ignoring message for dead channel %d' % chanid)
                        else:
                            self._log(ERROR, 'Channel request for unknown channel %d' % chanid)
                            self.active = False
                            self.packetizer.close()
                    elif (self.auth_handler is not None) and (ptype in self.auth_handler._handler_table):
                        self.auth_handler._handler_table[ptype](self.auth_handler, m)
                    else:
                        self._log(WARNING, 'Oops, unhandled type %d' % ptype)
                        msg = Message()
                        msg.add_byte(cMSG_UNIMPLEMENTED)
                        msg.add_int(m.seqno)
                        self._send_message(msg)
            except SSHException as e:
                self._log(ERROR, 'Exception: ' + str(e))
                self._log(ERROR, util.tb_strings())
                self.saved_exception = e
            except EOFError as e:
                self._log(DEBUG, 'EOF in transport thread')
                #self._log(DEBUG, util.tb_strings())
                self.saved_exception = e
            except socket.error as e:
                if type(e.args) is tuple:
                    if e.args:
                        emsg = '%s (%d)' % (e.args[1], e.args[0])
                    else:  # empty tuple, e.g. socket.timeout
                        emsg = str(e) or repr(e)
                else:
                    emsg = e.args
                self._log(ERROR, 'Socket exception: ' + emsg)
                self.saved_exception = e
            except Exception as e:
                self._log(ERROR, 'Unknown exception: ' + str(e))
                self._log(ERROR, util.tb_strings())
                self.saved_exception = e
            _active_threads.remove(self)
            for chan in list(self._channels.values()):
                chan._unlink()
            if self.active:
                self.active = False
                self.packetizer.close()
                if self.completion_event is not None:
                    self.completion_event.set()
                if self.auth_handler is not None:
                    self.auth_handler.abort()
                for event in self.channel_events.values():
                    event.set()
                try:
                    self.lock.acquire()
                    self.server_accept_cv.notify()
                finally:
                    self.lock.release()
            self.sock.close()
        except:
            # Don't raise spurious 'NoneType has no attribute X' errors when we
            # wake up during interpreter shutdown. Or rather -- raise
            # everything *if* sys.modules (used as a convenient sentinel)
            # appears to still exist.
            if self.sys.modules is not None:
                raise

    ###  protocol stages

    def _negotiate_keys(self, m):
        # throws SSHException on anything unusual
        self.clear_to_send_lock.acquire()
        try:
            self.clear_to_send.clear()
        finally:
            self.clear_to_send_lock.release()
        if self.local_kex_init is None:
            # remote side wants to renegotiate
            self._send_kex_init()
        self._parse_kex_init(m)
        self.kex_engine.start_kex()

    def _check_banner(self):
        # this is slow, but we only have to do it once
        for i in range(100):
            # give them 15 seconds for the first line, then just 2 seconds
            # each additional line.  (some sites have very high latency.)
            if i == 0:
                timeout = self.banner_timeout
            else:
                timeout = 2
            try:
                buf = self.packetizer.readline(timeout)
            except ProxyCommandFailure:
                raise
            except Exception as e:
                raise SSHException('Error reading SSH protocol banner' + str(e))
            if buf[:4] == 'SSH-':
                break
            self._log(DEBUG, 'Banner: ' + buf)
        if buf[:4] != 'SSH-':
            raise SSHException('Indecipherable protocol version "' + buf + '"')
        # save this server version string for later
        self.remote_version = buf
        # pull off any attached comment
        comment = ''
        i = buf.find(' ')
        if i >= 0:
            comment = buf[i+1:]
            buf = buf[:i]
        # parse out version string and make sure it matches
        segs = buf.split('-', 2)
        if len(segs) < 3:
            raise SSHException('Invalid SSH banner')
        version = segs[1]
        client = segs[2]
        if version != '1.99' and version != '2.0':
            raise SSHException('Incompatible version (%s instead of 2.0)' % (version,))
        self._log(INFO, 'Connected (version %s, client %s)' % (version, client))

    def _send_kex_init(self):
        """
        announce to the other side that we'd like to negotiate keys, and what
        kind of key negotiation we support.
        """
        self.clear_to_send_lock.acquire()
        try:
            self.clear_to_send.clear()
        finally:
            self.clear_to_send_lock.release()
        self.in_kex = True
        if self.server_mode:
            if (self._modulus_pack is None) and ('diffie-hellman-group-exchange-sha1' in self._preferred_kex):
                # can't do group-exchange if we don't have a pack of potential primes
                pkex = list(self.get_security_options().kex)
                pkex.remove('diffie-hellman-group-exchange-sha1')
                self.get_security_options().kex = pkex
            available_server_keys = list(filter(list(self.server_key_dict.keys()).__contains__,
                                                self._preferred_keys))
        else:
            available_server_keys = self._preferred_keys

        m = Message()
        m.add_byte(cMSG_KEXINIT)
        m.add_bytes(os.urandom(16))
        m.add_list(self._preferred_kex)
        m.add_list(available_server_keys)
        m.add_list(self._preferred_ciphers)
        m.add_list(self._preferred_ciphers)
        m.add_list(self._preferred_macs)
        m.add_list(self._preferred_macs)
        m.add_list(self._preferred_compression)
        m.add_list(self._preferred_compression)
        m.add_string(bytes())
        m.add_string(bytes())
        m.add_boolean(False)
        m.add_int(0)
        # save a copy for later (needed to compute a hash)
        self.local_kex_init = m.asbytes()
        self._send_message(m)

    def _parse_kex_init(self, m):
        cookie = m.get_bytes(16)
        kex_algo_list = m.get_list()
        server_key_algo_list = m.get_list()
        client_encrypt_algo_list = m.get_list()
        server_encrypt_algo_list = m.get_list()
        client_mac_algo_list = m.get_list()
        server_mac_algo_list = m.get_list()
        client_compress_algo_list = m.get_list()
        server_compress_algo_list = m.get_list()
        client_lang_list = m.get_list()
        server_lang_list = m.get_list()
        kex_follows = m.get_boolean()
        unused = m.get_int()

        self._log(DEBUG, 'kex algos:' + str(kex_algo_list) + ' server key:' + str(server_key_algo_list) +
                  ' client encrypt:' + str(client_encrypt_algo_list) +
                  ' server encrypt:' + str(server_encrypt_algo_list) +
                  ' client mac:' + str(client_mac_algo_list) +
                  ' server mac:' + str(server_mac_algo_list) +
                  ' client compress:' + str(client_compress_algo_list) +
                  ' server compress:' + str(server_compress_algo_list) +
                  ' client lang:' + str(client_lang_list) +
                  ' server lang:' + str(server_lang_list) +
                  ' kex follows?' + str(kex_follows))

        # as a server, we pick the first item in the client's list that we support.
        # as a client, we pick the first item in our list that the server supports.
        if self.server_mode:
            agreed_kex = list(filter(self._preferred_kex.__contains__, kex_algo_list))
        else:
            agreed_kex = list(filter(kex_algo_list.__contains__, self._preferred_kex))
        if len(agreed_kex) == 0:
            raise SSHException('Incompatible ssh peer (no acceptable kex algorithm)')
        self.kex_engine = self._kex_info[agreed_kex[0]](self)

        if self.server_mode:
            available_server_keys = list(filter(list(self.server_key_dict.keys()).__contains__,
                                                self._preferred_keys))
            agreed_keys = list(filter(available_server_keys.__contains__, server_key_algo_list))
        else:
            agreed_keys = list(filter(server_key_algo_list.__contains__, self._preferred_keys))
        if len(agreed_keys) == 0:
            raise SSHException('Incompatible ssh peer (no acceptable host key)')
        self.host_key_type = agreed_keys[0]
        if self.server_mode and (self.get_server_key() is None):
            raise SSHException('Incompatible ssh peer (can\'t match requested host key type)')

        if self.server_mode:
            agreed_local_ciphers = list(filter(self._preferred_ciphers.__contains__,
                                           server_encrypt_algo_list))
            agreed_remote_ciphers = list(filter(self._preferred_ciphers.__contains__,
                                          client_encrypt_algo_list))
        else:
            agreed_local_ciphers = list(filter(client_encrypt_algo_list.__contains__,
                                          self._preferred_ciphers))
            agreed_remote_ciphers = list(filter(server_encrypt_algo_list.__contains__,
                                           self._preferred_ciphers))
        if (len(agreed_local_ciphers) == 0) or (len(agreed_remote_ciphers) == 0):
            raise SSHException('Incompatible ssh server (no acceptable ciphers)')
        self.local_cipher = agreed_local_ciphers[0]
        self.remote_cipher = agreed_remote_ciphers[0]
        self._log(DEBUG, 'Ciphers agreed: local=%s, remote=%s' % (self.local_cipher, self.remote_cipher))

        if self.server_mode:
            agreed_remote_macs = list(filter(self._preferred_macs.__contains__, client_mac_algo_list))
            agreed_local_macs = list(filter(self._preferred_macs.__contains__, server_mac_algo_list))
        else:
            agreed_local_macs = list(filter(client_mac_algo_list.__contains__, self._preferred_macs))
            agreed_remote_macs = list(filter(server_mac_algo_list.__contains__, self._preferred_macs))
        if (len(agreed_local_macs) == 0) or (len(agreed_remote_macs) == 0):
            raise SSHException('Incompatible ssh server (no acceptable macs)')
        self.local_mac = agreed_local_macs[0]
        self.remote_mac = agreed_remote_macs[0]

        if self.server_mode:
            agreed_remote_compression = list(filter(self._preferred_compression.__contains__, client_compress_algo_list))
            agreed_local_compression = list(filter(self._preferred_compression.__contains__, server_compress_algo_list))
        else:
            agreed_local_compression = list(filter(client_compress_algo_list.__contains__, self._preferred_compression))
            agreed_remote_compression = list(filter(server_compress_algo_list.__contains__, self._preferred_compression))
        if (len(agreed_local_compression) == 0) or (len(agreed_remote_compression) == 0):
            raise SSHException('Incompatible ssh server (no acceptable compression) %r %r %r' % (agreed_local_compression, agreed_remote_compression, self._preferred_compression))
        self.local_compression = agreed_local_compression[0]
        self.remote_compression = agreed_remote_compression[0]

        self._log(DEBUG, 'using kex %s; server key type %s; cipher: local %s, remote %s; mac: local %s, remote %s; compression: local %s, remote %s' %
                  (agreed_kex[0], self.host_key_type, self.local_cipher, self.remote_cipher, self.local_mac,
                   self.remote_mac, self.local_compression, self.remote_compression))

        # save for computing hash later...
        # now wait!  openssh has a bug (and others might too) where there are
        # actually some extra bytes (one NUL byte in openssh's case) added to
        # the end of the packet but not parsed.  turns out we need to throw
        # away those bytes because they aren't part of the hash.
        self.remote_kex_init = cMSG_KEXINIT + m.get_so_far()

    def _activate_inbound(self):
        """switch on newly negotiated encryption parameters for inbound traffic"""
        block_size = self._cipher_info[self.remote_cipher]['block-size']
        if self.server_mode:
            IV_in = self._compute_key('A', block_size)
            key_in = self._compute_key('C', self._cipher_info[self.remote_cipher]['key-size'])
        else:
            IV_in = self._compute_key('B', block_size)
            key_in = self._compute_key('D', self._cipher_info[self.remote_cipher]['key-size'])
        engine = self._get_cipher(self.remote_cipher, key_in, IV_in)
        mac_size = self._mac_info[self.remote_mac]['size']
        mac_engine = self._mac_info[self.remote_mac]['class']
        # initial mac keys are done in the hash's natural size (not the potentially truncated
        # transmission size)
        if self.server_mode:
            mac_key = self._compute_key('E', mac_engine().digest_size)
        else:
            mac_key = self._compute_key('F', mac_engine().digest_size)
        self.packetizer.set_inbound_cipher(engine, block_size, mac_engine, mac_size, mac_key)
        compress_in = self._compression_info[self.remote_compression][1]
        if (compress_in is not None) and ((self.remote_compression != 'zlib@openssh.com') or self.authenticated):
            self._log(DEBUG, 'Switching on inbound compression ...')
            self.packetizer.set_inbound_compressor(compress_in())

    def _activate_outbound(self):
        """switch on newly negotiated encryption parameters for outbound traffic"""
        m = Message()
        m.add_byte(cMSG_NEWKEYS)
        self._send_message(m)
        block_size = self._cipher_info[self.local_cipher]['block-size']
        if self.server_mode:
            IV_out = self._compute_key('B', block_size)
            key_out = self._compute_key('D', self._cipher_info[self.local_cipher]['key-size'])
        else:
            IV_out = self._compute_key('A', block_size)
            key_out = self._compute_key('C', self._cipher_info[self.local_cipher]['key-size'])
        engine = self._get_cipher(self.local_cipher, key_out, IV_out)
        mac_size = self._mac_info[self.local_mac]['size']
        mac_engine = self._mac_info[self.local_mac]['class']
        # initial mac keys are done in the hash's natural size (not the potentially truncated
        # transmission size)
        if self.server_mode:
            mac_key = self._compute_key('F', mac_engine().digest_size)
        else:
            mac_key = self._compute_key('E', mac_engine().digest_size)
        sdctr = self.local_cipher.endswith('-ctr')
        self.packetizer.set_outbound_cipher(engine, block_size, mac_engine, mac_size, mac_key, sdctr)
        compress_out = self._compression_info[self.local_compression][0]
        if (compress_out is not None) and ((self.local_compression != 'zlib@openssh.com') or self.authenticated):
            self._log(DEBUG, 'Switching on outbound compression ...')
            self.packetizer.set_outbound_compressor(compress_out())
        if not self.packetizer.need_rekey():
            self.in_kex = False
        # we always expect to receive NEWKEYS now
        self._expect_packet(MSG_NEWKEYS)

    def _auth_trigger(self):
        self.authenticated = True
        # delayed initiation of compression
        if self.local_compression == 'zlib@openssh.com':
            compress_out = self._compression_info[self.local_compression][0]
            self._log(DEBUG, 'Switching on outbound compression ...')
            self.packetizer.set_outbound_compressor(compress_out())
        if self.remote_compression == 'zlib@openssh.com':
            compress_in = self._compression_info[self.remote_compression][1]
            self._log(DEBUG, 'Switching on inbound compression ...')
            self.packetizer.set_inbound_compressor(compress_in())

    def _parse_newkeys(self, m):
        self._log(DEBUG, 'Switch to new keys ...')
        self._activate_inbound()
        # can also free a bunch of stuff here
        self.local_kex_init = self.remote_kex_init = None
        self.K = None
        self.kex_engine = None
        if self.server_mode and (self.auth_handler is None):
            # create auth handler for server mode
            self.auth_handler = AuthHandler(self)
        if not self.initial_kex_done:
            # this was the first key exchange
            self.initial_kex_done = True
        # send an event?
        if self.completion_event is not None:
            self.completion_event.set()
        # it's now okay to send data again (if this was a re-key)
        if not self.packetizer.need_rekey():
            self.in_kex = False
        self.clear_to_send_lock.acquire()
        try:
            self.clear_to_send.set()
        finally:
            self.clear_to_send_lock.release()
        return

    def _parse_disconnect(self, m):
        code = m.get_int()
        desc = m.get_text()
        self._log(INFO, 'Disconnect (code %d): %s' % (code, desc))

    def _parse_global_request(self, m):
        kind = m.get_text()
        self._log(DEBUG, 'Received global request "%s"' % kind)
        want_reply = m.get_boolean()
        if not self.server_mode:
            self._log(DEBUG, 'Rejecting "%s" global request from server.' % kind)
            ok = False
        elif kind == 'tcpip-forward':
            address = m.get_text()
            port = m.get_int()
            ok = self.server_object.check_port_forward_request(address, port)
            if ok:
                ok = (ok,)
        elif kind == 'cancel-tcpip-forward':
            address = m.get_text()
            port = m.get_int()
            self.server_object.cancel_port_forward_request(address, port)
            ok = True
        else:
            ok = self.server_object.check_global_request(kind, m)
        extra = ()
        if type(ok) is tuple:
            extra = ok
            ok = True
        if want_reply:
            msg = Message()
            if ok:
                msg.add_byte(cMSG_REQUEST_SUCCESS)
                msg.add(*extra)
            else:
                msg.add_byte(cMSG_REQUEST_FAILURE)
            self._send_message(msg)

    def _parse_request_success(self, m):
        self._log(DEBUG, 'Global request successful.')
        self.global_response = m
        if self.completion_event is not None:
            self.completion_event.set()

    def _parse_request_failure(self, m):
        self._log(DEBUG, 'Global request denied.')
        self.global_response = None
        if self.completion_event is not None:
            self.completion_event.set()

    def _parse_channel_open_success(self, m):
        chanid = m.get_int()
        server_chanid = m.get_int()
        server_window_size = m.get_int()
        server_max_packet_size = m.get_int()
        chan = self._channels.get(chanid)
        if chan is None:
            self._log(WARNING, 'Success for unrequested channel! [??]')
            return
        self.lock.acquire()
        try:
            chan._set_remote_channel(server_chanid, server_window_size, server_max_packet_size)
            self._log(INFO, 'Secsh channel %d opened.' % chanid)
            if chanid in self.channel_events:
                self.channel_events[chanid].set()
                del self.channel_events[chanid]
        finally:
            self.lock.release()
        return

    def _parse_channel_open_failure(self, m):
        chanid = m.get_int()
        reason = m.get_int()
        reason_str = m.get_text()
        lang = m.get_text()
        reason_text = CONNECTION_FAILED_CODE.get(reason, '(unknown code)')
        self._log(INFO, 'Secsh channel %d open FAILED: %s: %s' % (chanid, reason_str, reason_text))
        self.lock.acquire()
        try:
            self.saved_exception = ChannelException(reason, reason_text)
            if chanid in self.channel_events:
                self._channels.delete(chanid)
                if chanid in self.channel_events:
                    self.channel_events[chanid].set()
                    del self.channel_events[chanid]
        finally:
            self.lock.release()
        return

    def _parse_channel_open(self, m):
        kind = m.get_text()
        chanid = m.get_int()
        initial_window_size = m.get_int()
        max_packet_size = m.get_int()
        reject = False
        if (kind == 'auth-agent@openssh.com') and (self._forward_agent_handler is not None):
            self._log(DEBUG, 'Incoming forward agent connection')
            self.lock.acquire()
            try:
                my_chanid = self._next_channel()
            finally:
                self.lock.release()
        elif (kind == 'x11') and (self._x11_handler is not None):
            origin_addr = m.get_text()
            origin_port = m.get_int()
            self._log(DEBUG, 'Incoming x11 connection from %s:%d' % (origin_addr, origin_port))
            self.lock.acquire()
            try:
                my_chanid = self._next_channel()
            finally:
                self.lock.release()
        elif (kind == 'forwarded-tcpip') and (self._tcp_handler is not None):
            server_addr = m.get_text()
            server_port = m.get_int()
            origin_addr = m.get_text()
            origin_port = m.get_int()
            self._log(DEBUG, 'Incoming tcp forwarded connection from %s:%d' % (origin_addr, origin_port))
            self.lock.acquire()
            try:
                my_chanid = self._next_channel()
            finally:
                self.lock.release()
        elif not self.server_mode:
            self._log(DEBUG, 'Rejecting "%s" channel request from server.' % kind)
            reject = True
            reason = OPEN_FAILED_ADMINISTRATIVELY_PROHIBITED
        else:
            self.lock.acquire()
            try:
                my_chanid = self._next_channel()
            finally:
                self.lock.release()
            if kind == 'direct-tcpip':
                # handle direct-tcpip requests comming from the client
                dest_addr = m.get_text()
                dest_port = m.get_int()
                origin_addr = m.get_text()
                origin_port = m.get_int()
                reason = self.server_object.check_channel_direct_tcpip_request(
                    my_chanid, (origin_addr, origin_port), (dest_addr, dest_port))
            else:
                reason = self.server_object.check_channel_request(kind, my_chanid)
            if reason != OPEN_SUCCEEDED:
                self._log(DEBUG, 'Rejecting "%s" channel request from client.' % kind)
                reject = True
        if reject:
            msg = Message()
            msg.add_byte(cMSG_CHANNEL_OPEN_FAILURE)
            msg.add_int(chanid)
            msg.add_int(reason)
            msg.add_string('')
            msg.add_string('en')
            self._send_message(msg)
            return

        chan = Channel(my_chanid)
        self.lock.acquire()
        try:
            self._channels.put(my_chanid, chan)
            self.channels_seen[my_chanid] = True
            chan._set_transport(self)
            chan._set_window(self.window_size, self.max_packet_size)
            chan._set_remote_channel(chanid, initial_window_size, max_packet_size)
        finally:
            self.lock.release()
        m = Message()
        m.add_byte(cMSG_CHANNEL_OPEN_SUCCESS)
        m.add_int(chanid)
        m.add_int(my_chanid)
        m.add_int(self.window_size)
        m.add_int(self.max_packet_size)
        self._send_message(m)
        self._log(INFO, 'Secsh channel %d (%s) opened.', my_chanid, kind)
        if kind == 'auth-agent@openssh.com':
            self._forward_agent_handler(chan)
        elif kind == 'x11':
            self._x11_handler(chan, (origin_addr, origin_port))
        elif kind == 'forwarded-tcpip':
            chan.origin_addr = (origin_addr, origin_port)
            self._tcp_handler(chan, (origin_addr, origin_port), (server_addr, server_port))
        else:
            self._queue_incoming_channel(chan)

    def _parse_debug(self, m):
        always_display = m.get_boolean()
        msg = m.get_string()
        lang = m.get_string()
        self._log(DEBUG, 'Debug msg: ' + util.safe_string(msg))

    def _get_subsystem_handler(self, name):
        try:
            self.lock.acquire()
            if name not in self.subsystem_table:
                return None, [], {}
            return self.subsystem_table[name]
        finally:
            self.lock.release()

    _handler_table = {
        MSG_NEWKEYS: _parse_newkeys,
        MSG_GLOBAL_REQUEST: _parse_global_request,
        MSG_REQUEST_SUCCESS: _parse_request_success,
        MSG_REQUEST_FAILURE: _parse_request_failure,
        MSG_CHANNEL_OPEN_SUCCESS: _parse_channel_open_success,
        MSG_CHANNEL_OPEN_FAILURE: _parse_channel_open_failure,
        MSG_CHANNEL_OPEN: _parse_channel_open,
        MSG_KEXINIT: _negotiate_keys,
    }

    _channel_handler_table = {
        MSG_CHANNEL_SUCCESS: Channel._request_success,
        MSG_CHANNEL_FAILURE: Channel._request_failed,
        MSG_CHANNEL_DATA: Channel._feed,
        MSG_CHANNEL_EXTENDED_DATA: Channel._feed_extended,
        MSG_CHANNEL_WINDOW_ADJUST: Channel._window_adjust,
        MSG_CHANNEL_REQUEST: Channel._handle_request,
        MSG_CHANNEL_EOF: Channel._handle_eof,
        MSG_CHANNEL_CLOSE: Channel._handle_close,
    }


class SecurityOptions (object):
    """
    Simple object containing the security preferences of an ssh transport.
    These are tuples of acceptable ciphers, digests, key types, and key
    exchange algorithms, listed in order of preference.

    Changing the contents and/or order of these fields affects the underlying
    `.Transport` (but only if you change them before starting the session).
    If you try to add an algorithm that paramiko doesn't recognize,
    ``ValueError`` will be raised.  If you try to assign something besides a
    tuple to one of the fields, ``TypeError`` will be raised.
    """
    #__slots__ = [ 'ciphers', 'digests', 'key_types', 'kex', 'compression', '_transport' ]
    __slots__ = '_transport'

    def __init__(self, transport):
        self._transport = transport

    def __repr__(self):
        """
        Returns a string representation of this object, for debugging.
        """
        return '<paramiko.SecurityOptions for %s>' % repr(self._transport)

    def _get_ciphers(self):
        return self._transport._preferred_ciphers

    def _get_digests(self):
        return self._transport._preferred_macs

    def _get_key_types(self):
        return self._transport._preferred_keys

    def _get_kex(self):
        return self._transport._preferred_kex

    def _get_compression(self):
        return self._transport._preferred_compression

    def _set(self, name, orig, x):
        if type(x) is list:
            x = tuple(x)
        if type(x) is not tuple:
            raise TypeError('expected tuple or list')
        possible = list(getattr(self._transport, orig).keys())
        forbidden = [n for n in x if n not in possible]
        if len(forbidden) > 0:
            raise ValueError('unknown cipher')
        setattr(self._transport, name, x)

    def _set_ciphers(self, x):
        self._set('_preferred_ciphers', '_cipher_info', x)

    def _set_digests(self, x):
        self._set('_preferred_macs', '_mac_info', x)

    def _set_key_types(self, x):
        self._set('_preferred_keys', '_key_info', x)

    def _set_kex(self, x):
        self._set('_preferred_kex', '_kex_info', x)

    def _set_compression(self, x):
        self._set('_preferred_compression', '_compression_info', x)

    ciphers = property(_get_ciphers, _set_ciphers, None,
                       "Symmetric encryption ciphers")
    digests = property(_get_digests, _set_digests, None,
                       "Digest (one-way hash) algorithms")
    key_types = property(_get_key_types, _set_key_types, None,
                         "Public-key algorithms")
    kex = property(_get_kex, _set_kex, None, "Key exchange algorithms")
    compression = property(_get_compression, _set_compression, None,
                           "Compression algorithms")


class ChannelMap (object):
    def __init__(self):
        # (id -> Channel)
        self._map = weakref.WeakValueDictionary()
        self._lock = threading.Lock()

    def put(self, chanid, chan):
        self._lock.acquire()
        try:
            self._map[chanid] = chan
        finally:
            self._lock.release()

    def get(self, chanid):
        self._lock.acquire()
        try:
            return self._map.get(chanid, None)
        finally:
            self._lock.release()

    def delete(self, chanid):
        self._lock.acquire()
        try:
            try:
                del self._map[chanid]
            except KeyError:
                pass
        finally:
            self._lock.release()

    def values(self):
        self._lock.acquire()
        try:
            return list(self._map.values())
        finally:
            self._lock.release()

    def __len__(self):
        self._lock.acquire()
        try:
            return len(self._map)
        finally:
            self._lock.release()

########NEW FILE########
__FILENAME__ = util
# Copyright (C) 2003-2007  Robey Pointer <robeypointer@gmail.com>
#
# This file is part of paramiko.
#
# Paramiko is free software; you can redistribute it and/or modify it under the
# terms of the GNU Lesser General Public License as published by the Free
# Software Foundation; either version 2.1 of the License, or (at your option)
# any later version.
#
# Paramiko is distributed in the hope that it will be useful, but WITHOUT ANY
# WARRANTY; without even the implied warranty of MERCHANTABILITY or FITNESS FOR
# A PARTICULAR PURPOSE.  See the GNU Lesser General Public License for more
# details.
#
# You should have received a copy of the GNU Lesser General Public License
# along with Paramiko; if not, write to the Free Software Foundation, Inc.,
# 59 Temple Place, Suite 330, Boston, MA  02111-1307  USA.

"""
Useful functions used by the rest of paramiko.
"""

from __future__ import generators

import array
from binascii import hexlify, unhexlify
import errno
import sys
import struct
import traceback
import threading
import logging

from paramiko.common import DEBUG, zero_byte, xffffffff, max_byte
from paramiko.py3compat import PY2, long, byte_ord, b, byte_chr
from paramiko.config import SSHConfig


def inflate_long(s, always_positive=False):
    """turns a normalized byte string into a long-int (adapted from Crypto.Util.number)"""
    out = long(0)
    negative = 0
    if not always_positive and (len(s) > 0) and (byte_ord(s[0]) >= 0x80):
        negative = 1
    if len(s) % 4:
        filler = zero_byte
        if negative:
            filler = max_byte
        # never convert this to ``s +=`` because this is a string, not a number
        # noinspection PyAugmentAssignment
        s = filler * (4 - len(s) % 4) + s
    for i in range(0, len(s), 4):
        out = (out << 32) + struct.unpack('>I', s[i:i+4])[0]
    if negative:
        out -= (long(1) << (8 * len(s)))
    return out

deflate_zero = zero_byte if PY2 else 0
deflate_ff = max_byte if PY2 else 0xff


def deflate_long(n, add_sign_padding=True):
    """turns a long-int into a normalized byte string (adapted from Crypto.Util.number)"""
    # after much testing, this algorithm was deemed to be the fastest
    s = bytes()
    n = long(n)
    while (n != 0) and (n != -1):
        s = struct.pack('>I', n & xffffffff) + s
        n >>= 32
    # strip off leading zeros, FFs
    for i in enumerate(s):
        if (n == 0) and (i[1] != deflate_zero):
            break
        if (n == -1) and (i[1] != deflate_ff):
            break
    else:
        # degenerate case, n was either 0 or -1
        i = (0,)
        if n == 0:
            s = zero_byte
        else:
            s = max_byte
    s = s[i[0]:]
    if add_sign_padding:
        if (n == 0) and (byte_ord(s[0]) >= 0x80):
            s = zero_byte + s
        if (n == -1) and (byte_ord(s[0]) < 0x80):
            s = max_byte + s
    return s


def format_binary(data, prefix=''):
    x = 0
    out = []
    while len(data) > x + 16:
        out.append(format_binary_line(data[x:x+16]))
        x += 16
    if x < len(data):
        out.append(format_binary_line(data[x:]))
    return [prefix + x for x in out]


def format_binary_line(data):
    left = ' '.join(['%02X' % byte_ord(c) for c in data])
    right = ''.join([('.%c..' % c)[(byte_ord(c)+63)//95] for c in data])
    return '%-50s %s' % (left, right)


def hexify(s):
    return hexlify(s).upper()


def unhexify(s):
    return unhexlify(s)


def safe_string(s):
    out = ''
    for c in s:
        if (byte_ord(c) >= 32) and (byte_ord(c) <= 127):
            out += c
        else:
            out += '%%%02X' % byte_ord(c)
    return out


def bit_length(n):
    try:
        return n.bitlength()
    except AttributeError:
        norm = deflate_long(n, False)
        hbyte = byte_ord(norm[0])
        if hbyte == 0:
            return 1
        bitlen = len(norm) * 8
        while not (hbyte & 0x80):
            hbyte <<= 1
            bitlen -= 1
        return bitlen


def tb_strings():
    return ''.join(traceback.format_exception(*sys.exc_info())).split('\n')


def generate_key_bytes(hash_alg, salt, key, nbytes):
    """
    Given a password, passphrase, or other human-source key, scramble it
    through a secure hash into some keyworthy bytes.  This specific algorithm
    is used for encrypting/decrypting private key files.

    :param function hash_alg: A function which creates a new hash object, such
        as ``hashlib.sha256``.
    :param salt: data to salt the hash with.
    :type salt: byte string
    :param str key: human-entered password or passphrase.
    :param int nbytes: number of bytes to generate.
    :return: Key data `str`
    """
    keydata = bytes()
    digest = bytes()
    if len(salt) > 8:
        salt = salt[:8]
    while nbytes > 0:
        hash_obj = hash_alg()
        if len(digest) > 0:
            hash_obj.update(digest)
        hash_obj.update(b(key))
        hash_obj.update(salt)
        digest = hash_obj.digest()
        size = min(nbytes, len(digest))
        keydata += digest[:size]
        nbytes -= size
    return keydata


def load_host_keys(filename):
    """
    Read a file of known SSH host keys, in the format used by openssh, and
    return a compound dict of ``hostname -> keytype ->`` `PKey
    <paramiko.pkey.PKey>`. The hostname may be an IP address or DNS name.  The
    keytype will be either ``"ssh-rsa"`` or ``"ssh-dss"``.

    This type of file unfortunately doesn't exist on Windows, but on posix,
    it will usually be stored in ``os.path.expanduser("~/.ssh/known_hosts")``.

    Since 1.5.3, this is just a wrapper around `.HostKeys`.

    :param str filename: name of the file to read host keys from
    :return:
        nested dict of `.PKey` objects, indexed by hostname and then keytype
    """
    from paramiko.hostkeys import HostKeys
    return HostKeys(filename)


def parse_ssh_config(file_obj):
    """
    Provided only as a backward-compatible wrapper around `.SSHConfig`.
    """
    config = SSHConfig()
    config.parse(file_obj)
    return config


def lookup_ssh_host_config(hostname, config):
    """
    Provided only as a backward-compatible wrapper around `.SSHConfig`.
    """
    return config.lookup(hostname)


def mod_inverse(x, m):
    # it's crazy how small Python can make this function.
    u1, u2, u3 = 1, 0, m
    v1, v2, v3 = 0, 1, x

    while v3 > 0:
        q = u3 // v3
        u1, v1 = v1, u1 - v1 * q
        u2, v2 = v2, u2 - v2 * q
        u3, v3 = v3, u3 - v3 * q
    if u2 < 0:
        u2 += m
    return u2

_g_thread_ids = {}
_g_thread_counter = 0
_g_thread_lock = threading.Lock()


def get_thread_id():
    global _g_thread_ids, _g_thread_counter, _g_thread_lock
    tid = id(threading.currentThread())
    try:
        return _g_thread_ids[tid]
    except KeyError:
        _g_thread_lock.acquire()
        try:
            _g_thread_counter += 1
            ret = _g_thread_ids[tid] = _g_thread_counter
        finally:
            _g_thread_lock.release()
        return ret


def log_to_file(filename, level=DEBUG):
    """send paramiko logs to a logfile, if they're not already going somewhere"""
    l = logging.getLogger("paramiko")
    if len(l.handlers) > 0:
        return
    l.setLevel(level)
    f = open(filename, 'w')
    lh = logging.StreamHandler(f)
    lh.setFormatter(logging.Formatter('%(levelname)-.3s [%(asctime)s.%(msecs)03d] thr=%(_threadid)-3d %(name)s: %(message)s',
                                      '%Y%m%d-%H:%M:%S'))
    l.addHandler(lh)


# make only one filter object, so it doesn't get applied more than once
class PFilter (object):
    def filter(self, record):
        record._threadid = get_thread_id()
        return True
_pfilter = PFilter()


def get_logger(name):
    l = logging.getLogger(name)
    l.addFilter(_pfilter)
    return l


def retry_on_signal(function):
    """Retries function until it doesn't raise an EINTR error"""
    while True:
        try:
            return function()
        except EnvironmentError as e:
            if e.errno != errno.EINTR:
                raise


class Counter (object):
    """Stateful counter for CTR mode crypto"""
    def __init__(self, nbits, initial_value=long(1), overflow=long(0)):
        self.blocksize = nbits / 8
        self.overflow = overflow
        # start with value - 1 so we don't have to store intermediate values when counting
        # could the iv be 0?
        if initial_value == 0:
            self.value = array.array('c', max_byte * self.blocksize)
        else:
            x = deflate_long(initial_value - 1, add_sign_padding=False)
            self.value = array.array('c', zero_byte * (self.blocksize - len(x)) + x)

    def __call__(self):
        """Increament the counter and return the new value"""
        i = self.blocksize - 1
        while i > -1:
            c = self.value[i] = byte_chr((byte_ord(self.value[i]) + 1) % 256)
            if c != zero_byte:
                return self.value.tostring()
            i -= 1
        # counter reset
        x = deflate_long(self.overflow, add_sign_padding=False)
        self.value = array.array('c', zero_byte * (self.blocksize - len(x)) + x)
        return self.value.tostring()

    def new(cls, nbits, initial_value=long(1), overflow=long(0)):
        return cls(nbits, initial_value=initial_value, overflow=overflow)
    new = classmethod(new)


def constant_time_bytes_eq(a, b):
    if len(a) != len(b):
        return False
    res = 0
    # noinspection PyUnresolvedReferences
    for i in (xrange if PY2 else range)(len(a)):
        res |= byte_ord(a[i]) ^ byte_ord(b[i])
    return res == 0

########NEW FILE########
__FILENAME__ = win_pageant
# Copyright (C) 2005 John Arbash-Meinel <john@arbash-meinel.com>
# Modified up by: Todd Whiteman <ToddW@ActiveState.com>
#
# This file is part of paramiko.
#
# Paramiko is free software; you can redistribute it and/or modify it under the
# terms of the GNU Lesser General Public License as published by the Free
# Software Foundation; either version 2.1 of the License, or (at your option)
# any later version.
#
# Paramiko is distributed in the hope that it will be useful, but WITHOUT ANY
# WARRANTY; without even the implied warranty of MERCHANTABILITY or FITNESS FOR
# A PARTICULAR PURPOSE.  See the GNU Lesser General Public License for more
# details.
#
# You should have received a copy of the GNU Lesser General Public License
# along with Paramiko; if not, write to the Free Software Foundation, Inc.,
# 59 Temple Place, Suite 330, Boston, MA  02111-1307  USA.

"""
Functions for communicating with Pageant, the basic windows ssh agent program.
"""

import array
import ctypes.wintypes
import platform
import struct
from paramiko.util import *

try:
    import _thread as thread # Python 3.x
except ImportError:
    import thread # Python 2.5-2.7

from . import _winapi


_AGENT_COPYDATA_ID = 0x804e50ba
_AGENT_MAX_MSGLEN = 8192
# Note: The WM_COPYDATA value is pulled from win32con, as a workaround
# so we do not have to import this huge library just for this one variable.
win32con_WM_COPYDATA = 74


def _get_pageant_window_object():
    return ctypes.windll.user32.FindWindowA('Pageant', 'Pageant')


def can_talk_to_agent():
    """
    Check to see if there is a "Pageant" agent we can talk to.

    This checks both if we have the required libraries (win32all or ctypes)
    and if there is a Pageant currently running.
    """
    return bool(_get_pageant_window_object())


ULONG_PTR = ctypes.c_uint64 if platform.architecture()[0] == '64bit' else ctypes.c_uint32


class COPYDATASTRUCT(ctypes.Structure):
    """
    ctypes implementation of
    http://msdn.microsoft.com/en-us/library/windows/desktop/ms649010%28v=vs.85%29.aspx
    """
    _fields_ = [
        ('num_data', ULONG_PTR),
        ('data_size', ctypes.wintypes.DWORD),
        ('data_loc', ctypes.c_void_p),
    ]


def _query_pageant(msg):
    """
    Communication with the Pageant process is done through a shared
    memory-mapped file.
    """
    hwnd = _get_pageant_window_object()
    if not hwnd:
        # Raise a failure to connect exception, pageant isn't running anymore!
        return None

    # create a name for the mmap
    map_name = 'PageantRequest%08x' % thread.get_ident()

    pymap = _winapi.MemoryMap(map_name, _AGENT_MAX_MSGLEN,
        _winapi.get_security_attributes_for_user(),
        )
    with pymap:
        pymap.write(msg)
        # Create an array buffer containing the mapped filename
        char_buffer = array.array("c", b(map_name) + zero_byte)
        char_buffer_address, char_buffer_size = char_buffer.buffer_info()
        # Create a string to use for the SendMessage function call
        cds = COPYDATASTRUCT(_AGENT_COPYDATA_ID, char_buffer_size,
            char_buffer_address)

        response = ctypes.windll.user32.SendMessageA(hwnd,
            win32con_WM_COPYDATA, ctypes.sizeof(cds), ctypes.byref(cds))

        if response > 0:
            pymap.seek(0)
            datalen = pymap.read(4)
            retlen = struct.unpack('>I', datalen)[0]
            return datalen + pymap.read(retlen)
        return None


class PageantConnection(object):
    """
    Mock "connection" to an agent which roughly approximates the behavior of
    a unix local-domain socket (as used by Agent).  Requests are sent to the
    pageant daemon via special Windows magick, and responses are buffered back
    for subsequent reads.
    """

    def __init__(self):
        self._response = None

    def send(self, data):
        self._response = _query_pageant(data)

    def recv(self, n):
        if self._response is None:
            return ''
        ret = self._response[:n]
        self._response = self._response[n:]
        if self._response == '':
            self._response = None
        return ret

    def close(self):
        pass

########NEW FILE########
__FILENAME__ = _winapi
"""
Windows API functions implemented as ctypes functions and classes as found
in jaraco.windows (2.10).

If you encounter issues with this module, please consider reporting the issues
in jaraco.windows and asking the author to port the fixes back here.
"""

import ctypes
import ctypes.wintypes
from paramiko.py3compat import u
try:
    import builtins
except ImportError:
    import __builtin__ as builtins

try:
    USHORT = ctypes.wintypes.USHORT
except AttributeError:
    USHORT = ctypes.c_ushort

######################
# jaraco.windows.error

def format_system_message(errno):
    """
    Call FormatMessage with a system error number to retrieve
    the descriptive error message.
    """
    # first some flags used by FormatMessageW
    ALLOCATE_BUFFER = 0x100
    ARGUMENT_ARRAY = 0x2000
    FROM_HMODULE = 0x800
    FROM_STRING = 0x400
    FROM_SYSTEM = 0x1000
    IGNORE_INSERTS = 0x200

    # Let FormatMessageW allocate the buffer (we'll free it below)
    # Also, let it know we want a system error message.
    flags = ALLOCATE_BUFFER | FROM_SYSTEM
    source = None
    message_id = errno
    language_id = 0
    result_buffer = ctypes.wintypes.LPWSTR()
    buffer_size = 0
    arguments = None
    format_bytes = ctypes.windll.kernel32.FormatMessageW(
        flags,
        source,
        message_id,
        language_id,
        ctypes.byref(result_buffer),
        buffer_size,
        arguments,
    )
    # note the following will cause an infinite loop if GetLastError
    #  repeatedly returns an error that cannot be formatted, although
    #  this should not happen.
    handle_nonzero_success(format_bytes)
    message = result_buffer.value
    ctypes.windll.kernel32.LocalFree(result_buffer)
    return message


class WindowsError(builtins.WindowsError):
    "more info about errors at http://msdn.microsoft.com/en-us/library/ms681381(VS.85).aspx"

    def __init__(self, value=None):
        if value is None:
            value = ctypes.windll.kernel32.GetLastError()
        strerror = format_system_message(value)
        super(WindowsError, self).__init__(value, strerror)

    @property
    def message(self):
        return self.strerror

    @property
    def code(self):
        return self.winerror

    def __str__(self):
        return self.message

    def __repr__(self):
        return '{self.__class__.__name__}({self.winerror})'.format(**vars())

def handle_nonzero_success(result):
    if result == 0:
        raise WindowsError()


CreateFileMapping = ctypes.windll.kernel32.CreateFileMappingW
CreateFileMapping.argtypes = [
    ctypes.wintypes.HANDLE,
    ctypes.c_void_p,
    ctypes.wintypes.DWORD,
    ctypes.wintypes.DWORD,
    ctypes.wintypes.DWORD,
    ctypes.wintypes.LPWSTR,
]
CreateFileMapping.restype = ctypes.wintypes.HANDLE

MapViewOfFile = ctypes.windll.kernel32.MapViewOfFile
MapViewOfFile.restype = ctypes.wintypes.HANDLE

class MemoryMap(object):
    """
    A memory map object which can have security attributes overrideden.
    """
    def __init__(self, name, length, security_attributes=None):
        self.name = name
        self.length = length
        self.security_attributes = security_attributes
        self.pos = 0

    def __enter__(self):
        p_SA = (
            ctypes.byref(self.security_attributes)
            if self.security_attributes else None
        )
        INVALID_HANDLE_VALUE = -1
        PAGE_READWRITE = 0x4
        FILE_MAP_WRITE = 0x2
        filemap = ctypes.windll.kernel32.CreateFileMappingW(
            INVALID_HANDLE_VALUE, p_SA, PAGE_READWRITE, 0, self.length,
            u(self.name))
        handle_nonzero_success(filemap)
        if filemap == INVALID_HANDLE_VALUE:
            raise Exception("Failed to create file mapping")
        self.filemap = filemap
        self.view = MapViewOfFile(filemap, FILE_MAP_WRITE, 0, 0, 0)
        return self

    def seek(self, pos):
        self.pos = pos

    def write(self, msg):
        n = len(msg)
        if self.pos + n >= self.length:  # A little safety.
            raise ValueError("Refusing to write %d bytes" % n)
        ctypes.windll.kernel32.RtlMoveMemory(self.view + self.pos, msg, n)
        self.pos += n

    def read(self, n):
        """
        Read n bytes from mapped view.
        """
        out = ctypes.create_string_buffer(n)
        ctypes.windll.kernel32.RtlMoveMemory(out, self.view + self.pos, n)
        self.pos += n
        return out.raw

    def __exit__(self, exc_type, exc_val, tb):
        ctypes.windll.kernel32.UnmapViewOfFile(self.view)
        ctypes.windll.kernel32.CloseHandle(self.filemap)

#########################
# jaraco.windows.security

class TokenInformationClass:
    TokenUser = 1

class TOKEN_USER(ctypes.Structure):
    num = 1
    _fields_ = [
        ('SID', ctypes.c_void_p),
        ('ATTRIBUTES', ctypes.wintypes.DWORD),
    ]


class SECURITY_DESCRIPTOR(ctypes.Structure):
    """
    typedef struct _SECURITY_DESCRIPTOR
        {
        UCHAR Revision;
        UCHAR Sbz1;
        SECURITY_DESCRIPTOR_CONTROL Control;
        PSID Owner;
        PSID Group;
        PACL Sacl;
        PACL Dacl;
        }   SECURITY_DESCRIPTOR;
    """
    SECURITY_DESCRIPTOR_CONTROL = USHORT
    REVISION = 1

    _fields_ = [
        ('Revision', ctypes.c_ubyte),
        ('Sbz1', ctypes.c_ubyte),
        ('Control', SECURITY_DESCRIPTOR_CONTROL),
        ('Owner', ctypes.c_void_p),
        ('Group', ctypes.c_void_p),
        ('Sacl', ctypes.c_void_p),
        ('Dacl', ctypes.c_void_p),
    ]

class SECURITY_ATTRIBUTES(ctypes.Structure):
    """
    typedef struct _SECURITY_ATTRIBUTES {
        DWORD  nLength;
        LPVOID lpSecurityDescriptor;
        BOOL   bInheritHandle;
    } SECURITY_ATTRIBUTES;
    """
    _fields_ = [
        ('nLength', ctypes.wintypes.DWORD),
        ('lpSecurityDescriptor', ctypes.c_void_p),
        ('bInheritHandle', ctypes.wintypes.BOOL),
    ]

    def __init__(self, *args, **kwargs):
        super(SECURITY_ATTRIBUTES, self).__init__(*args, **kwargs)
        self.nLength = ctypes.sizeof(SECURITY_ATTRIBUTES)

    def _get_descriptor(self):
        return self._descriptor
    def _set_descriptor(self, descriptor):
        self._descriptor = descriptor
        self.lpSecurityDescriptor = ctypes.addressof(descriptor)
    descriptor = property(_get_descriptor, _set_descriptor)

def GetTokenInformation(token, information_class):
    """
    Given a token, get the token information for it.
    """
    data_size = ctypes.wintypes.DWORD()
    ctypes.windll.advapi32.GetTokenInformation(token, information_class.num,
        0, 0, ctypes.byref(data_size))
    data = ctypes.create_string_buffer(data_size.value)
    handle_nonzero_success(ctypes.windll.advapi32.GetTokenInformation(token,
        information_class.num,
        ctypes.byref(data), ctypes.sizeof(data),
        ctypes.byref(data_size)))
    return ctypes.cast(data, ctypes.POINTER(TOKEN_USER)).contents

class TokenAccess:
    TOKEN_QUERY = 0x8

def OpenProcessToken(proc_handle, access):
    result = ctypes.wintypes.HANDLE()
    proc_handle = ctypes.wintypes.HANDLE(proc_handle)
    handle_nonzero_success(ctypes.windll.advapi32.OpenProcessToken(
        proc_handle, access, ctypes.byref(result)))
    return result

def get_current_user():
    """
    Return a TOKEN_USER for the owner of this process.
    """
    process = OpenProcessToken(
        ctypes.windll.kernel32.GetCurrentProcess(),
        TokenAccess.TOKEN_QUERY,
    )
    return GetTokenInformation(process, TOKEN_USER)

def get_security_attributes_for_user(user=None):
    """
    Return a SECURITY_ATTRIBUTES structure with the SID set to the
    specified user (uses current user if none is specified).
    """
    if user is None:
        user = get_current_user()

    assert isinstance(user, TOKEN_USER), "user must be TOKEN_USER instance"

    SD = SECURITY_DESCRIPTOR()
    SA = SECURITY_ATTRIBUTES()
    # by attaching the actual security descriptor, it will be garbage-
    # collected with the security attributes
    SA.descriptor = SD
    SA.bInheritHandle = 1

    ctypes.windll.advapi32.InitializeSecurityDescriptor(ctypes.byref(SD),
        SECURITY_DESCRIPTOR.REVISION)
    ctypes.windll.advapi32.SetSecurityDescriptorOwner(ctypes.byref(SD),
        user.SID, 0)
    return SA

########NEW FILE########
__FILENAME__ = conf
# Obtain shared config values
import os, sys
sys.path.append(os.path.abspath('..'))
sys.path.append(os.path.abspath('../..'))
from shared_conf import *

# Enable autodoc, intersphinx
extensions.extend(['sphinx.ext.autodoc'])

# Autodoc settings
autodoc_default_flags = ['members', 'special-members']

# Sister-site links to WWW
html_theme_options['extra_nav_links'] = {
    "Main website": 'http://www.paramiko.org',
}

########NEW FILE########
__FILENAME__ = shared_conf
from datetime import datetime

import alabaster


# Alabaster theme + mini-extension
html_theme_path = [alabaster.get_path()]
extensions = ['alabaster', 'sphinx.ext.intersphinx']
# Paths relative to invoking conf.py - not this shared file
html_theme = 'alabaster'
html_theme_options = {
    'description': "A Python implementation of SSHv2.",
    'github_user': 'paramiko',
    'github_repo': 'paramiko',
    'gittip_user': 'bitprophet',
    'analytics_id': 'UA-18486793-2',
    'travis_button': True,
}
html_sidebars = {
    '**': [
        'about.html',
        'navigation.html',
        'searchbox.html',
        'donate.html',
    ]
}

# Everything intersphinx's to Python
intersphinx_mapping = {
    'python': ('http://docs.python.org/2.6', None),
}

# Regular settings
project = 'Paramiko'
year = datetime.now().year
copyright = '%d Jeff Forcier' % year
master_doc = 'index'
templates_path = ['_templates']
exclude_trees = ['_build']
source_suffix = '.rst'
default_role = 'obj'

########NEW FILE########
__FILENAME__ = conf
# Obtain shared config values
import sys
import os
from os.path import abspath, join, dirname

sys.path.append(abspath(join(dirname(__file__), '..')))
from shared_conf import *

# Releases changelog extension
extensions.append('releases')
# Paramiko 1.x tags start with 'v'. Meh.
releases_release_uri = "https://github.com/paramiko/paramiko/tree/v%s"
releases_issue_uri = "https://github.com/paramiko/paramiko/issues/%s"

# Intersphinx for referencing API/usage docs
extensions.append('sphinx.ext.intersphinx')
# Default is 'local' building, but reference the public docs site when building
# under RTD.
target = join(dirname(__file__), '..', 'docs', '_build')
if os.environ.get('READTHEDOCS') == 'True':
    # TODO: switch to docs.paramiko.org post go-live of sphinx API docs
    target = 'http://docs.paramiko.org/en/latest/'
intersphinx_mapping['docs'] = (target, None)

# Sister-site links to API docs
html_theme_options['extra_nav_links'] = {
    "API Docs": 'http://docs.paramiko.org',
}

########NEW FILE########
__FILENAME__ = tasks
from os import mkdir
from os.path import join
from shutil import rmtree, copytree

from invoke import Collection, ctask as task
from invocations import docs as _docs
from invocations.packaging import publish


d = 'sites'

# Usage doc/API site (published as docs.paramiko.org)
docs_path = join(d, 'docs')
docs_build = join(docs_path, '_build')
docs = Collection.from_module(_docs, name='docs', config={
    'sphinx.source': docs_path,
    'sphinx.target': docs_build,
})

# Main/about/changelog site ((www.)?paramiko.org)
www_path = join(d, 'www')
www = Collection.from_module(_docs, name='www', config={
    'sphinx.source': www_path,
    'sphinx.target': join(www_path, '_build'),
})


# Until we move to spec-based testing
@task
def test(ctx):
    ctx.run("python test.py --verbose")

@task
def coverage(ctx):
    ctx.run("coverage run --source=paramiko test.py --verbose")


# Until we stop bundling docs w/ releases. Need to discover use cases first.
@task('docs') # Will invoke the API doc site build
def release(ctx):
    # Move the built docs into where Epydocs used to live
    target = 'docs'
    rmtree(target, ignore_errors=True)
    copytree(docs_build, target)
    # Publish
    publish(ctx, wheel=True)


ns = Collection(test, coverage, release, docs=docs, www=www)

########NEW FILE########
__FILENAME__ = test
#!/usr/bin/env python

# Copyright (C) 2003-2007  Robey Pointer <robeypointer@gmail.com>
#
# This file is part of paramiko.
#
# Paramiko is free software; you can redistribute it and/or modify it under the
# terms of the GNU Lesser General Public License as published by the Free
# Software Foundation; either version 2.1 of the License, or (at your option)
# any later version.
#
# Paramiko is distributed in the hope that it will be useful, but WITHOUT ANY
# WARRANTY; without even the implied warranty of MERCHANTABILITY or FITNESS FOR
# A PARTICULAR PURPOSE.  See the GNU Lesser General Public License for more
# details.
#
# You should have received a copy of the GNU Lesser General Public License
# along with Paramiko; if not, write to the Free Software Foundation, Inc.,
# 59 Temple Place, Suite 330, Boston, MA  02111-1307  USA.

"""
do the unit tests!
"""

import os
import re
import sys
import unittest
from optparse import OptionParser
import paramiko
import threading
from paramiko.py3compat import PY2

sys.path.append('tests')

from tests.test_message import MessageTest
from tests.test_file import BufferedFileTest
from tests.test_buffered_pipe import BufferedPipeTest
from tests.test_util import UtilTest
from tests.test_hostkeys import HostKeysTest
from tests.test_pkey import KeyTest
from tests.test_kex import KexTest
from tests.test_packetizer import PacketizerTest
from tests.test_auth import AuthTest
from tests.test_transport import TransportTest
from tests.test_client import SSHClientTest

default_host = 'localhost'
default_user = os.environ.get('USER', 'nobody')
default_keyfile = os.path.join(os.environ.get('HOME', '/'), '.ssh/id_rsa')
default_passwd = None


def iter_suite_tests(suite):
    """Return all tests in a suite, recursing through nested suites"""
    for item in suite._tests:
        if isinstance(item, unittest.TestCase):
            yield item
        elif isinstance(item, unittest.TestSuite):
            for r in iter_suite_tests(item):
                yield r
        else:
            raise Exception('unknown object %r inside test suite %r'
                            % (item, suite))


def filter_suite_by_re(suite, pattern):
    result = unittest.TestSuite()
    filter_re = re.compile(pattern)
    for test in iter_suite_tests(suite):
        if filter_re.search(test.id()):
            result.addTest(test)
    return result


def main():
    parser = OptionParser('usage: %prog [options]')
    parser.add_option('--verbose', action='store_true', dest='verbose', default=False,
                      help='verbose display (one line per test)')
    parser.add_option('--no-pkey', action='store_false', dest='use_pkey', default=True,
                      help='skip RSA/DSS private key tests (which can take a while)')
    parser.add_option('--no-transport', action='store_false', dest='use_transport', default=True,
                      help='skip transport tests (which can take a while)')
    parser.add_option('--no-sftp', action='store_false', dest='use_sftp', default=True,
                      help='skip SFTP client/server tests, which can be slow')
    parser.add_option('--no-big-file', action='store_false', dest='use_big_file', default=True,
                      help='skip big file SFTP tests, which are slow as molasses')
    parser.add_option('-R', action='store_false', dest='use_loopback_sftp', default=True,
                      help='perform SFTP tests against a remote server (by default, SFTP tests ' +
                      'are done through a loopback socket)')
    parser.add_option('-H', '--sftp-host', dest='hostname', type='string', default=default_host,
                      metavar='<host>',
                      help='[with -R] host for remote sftp tests (default: %s)' % default_host)
    parser.add_option('-U', '--sftp-user', dest='username', type='string', default=default_user,
                      metavar='<username>',
                      help='[with -R] username for remote sftp tests (default: %s)' % default_user)
    parser.add_option('-K', '--sftp-key', dest='keyfile', type='string', default=default_keyfile,
                      metavar='<keyfile>',
                      help='[with -R] location of private key for remote sftp tests (default: %s)' %
                      default_keyfile)
    parser.add_option('-P', '--sftp-passwd', dest='password', type='string', default=default_passwd,
                      metavar='<password>',
                      help='[with -R] (optional) password to unlock the private key for remote sftp tests')

    options, args = parser.parse_args()

    # setup logging
    paramiko.util.log_to_file('test.log')

    if options.use_sftp:
        from tests.test_sftp import SFTPTest
        if options.use_loopback_sftp:
            SFTPTest.init_loopback()
        else:
            SFTPTest.init(options.hostname, options.username, options.keyfile, options.password)
        if not options.use_big_file:
            SFTPTest.set_big_file_test(False)
    if options.use_big_file:
        from tests.test_sftp_big import BigSFTPTest

    suite = unittest.TestSuite()
    suite.addTest(unittest.makeSuite(MessageTest))
    suite.addTest(unittest.makeSuite(BufferedFileTest))
    suite.addTest(unittest.makeSuite(BufferedPipeTest))
    suite.addTest(unittest.makeSuite(UtilTest))
    suite.addTest(unittest.makeSuite(HostKeysTest))
    if options.use_pkey:
        suite.addTest(unittest.makeSuite(KeyTest))
    suite.addTest(unittest.makeSuite(KexTest))
    suite.addTest(unittest.makeSuite(PacketizerTest))
    if options.use_transport:
        suite.addTest(unittest.makeSuite(AuthTest))
        suite.addTest(unittest.makeSuite(TransportTest))
    suite.addTest(unittest.makeSuite(SSHClientTest))
    if options.use_sftp:
        suite.addTest(unittest.makeSuite(SFTPTest))
    if options.use_big_file:
        suite.addTest(unittest.makeSuite(BigSFTPTest))
    verbosity = 1
    if options.verbose:
        verbosity = 2

    runner = unittest.TextTestRunner(verbosity=verbosity)
    if len(args) > 0:
        filter = '|'.join(args)
        suite = filter_suite_by_re(suite, filter)
    result = runner.run(suite)
    # Clean up stale threads from poorly cleaned-up tests.
    # TODO: make that not a problem, jeez
    for thread in threading.enumerate():
        if thread is not threading.currentThread():
            if PY2:
                thread._Thread__stop()
            else:
                thread._stop()
    # Exit correctly
    if not result.wasSuccessful():
        sys.exit(1)


if __name__ == '__main__':
    main()

########NEW FILE########
__FILENAME__ = loop
# Copyright (C) 2003-2009  Robey Pointer <robeypointer@gmail.com>
#
# This file is part of paramiko.
#
# Paramiko is free software; you can redistribute it and/or modify it under the
# terms of the GNU Lesser General Public License as published by the Free
# Software Foundation; either version 2.1 of the License, or (at your option)
# any later version.
#
# Paramiko is distributed in the hope that it will be useful, but WITHOUT ANY
# WARRANTY; without even the implied warranty of MERCHANTABILITY or FITNESS FOR
# A PARTICULAR PURPOSE.  See the GNU Lesser General Public License for more
# details.
#
# You should have received a copy of the GNU Lesser General Public License
# along with Paramiko; if not, write to the Free Software Foundation, Inc.,
# 59 Temple Place, Suite 330, Boston, MA  02111-1307  USA.

"""
...
"""

import threading, socket
from paramiko.common import asbytes


class LoopSocket (object):
    """
    A LoopSocket looks like a normal socket, but all data written to it is
    delivered on the read-end of another LoopSocket, and vice versa.  It's
    like a software "socketpair".
    """
    
    def __init__(self):
        self.__in_buffer = bytes()
        self.__lock = threading.Lock()
        self.__cv = threading.Condition(self.__lock)
        self.__timeout = None
        self.__mate = None

    def close(self):
        self.__unlink()
        try:
            self.__lock.acquire()
            self.__in_buffer = bytes()
        finally:
            self.__lock.release()

    def send(self, data):
        data = asbytes(data)
        if self.__mate is None:
            # EOF
            raise EOFError()
        self.__mate.__feed(data)
        return len(data)

    def recv(self, n):
        self.__lock.acquire()
        try:
            if self.__mate is None:
                # EOF
                return bytes()
            if len(self.__in_buffer) == 0:
                self.__cv.wait(self.__timeout)
            if len(self.__in_buffer) == 0:
                raise socket.timeout
            out = self.__in_buffer[:n]
            self.__in_buffer = self.__in_buffer[n:]
            return out
        finally:
            self.__lock.release()

    def settimeout(self, n):
        self.__timeout = n

    def link(self, other):
        self.__mate = other
        self.__mate.__mate = self

    def __feed(self, data):
        self.__lock.acquire()
        try:
            self.__in_buffer += data
            self.__cv.notifyAll()
        finally:
            self.__lock.release()
            
    def __unlink(self):
        m = None
        self.__lock.acquire()
        try:
            if self.__mate is not None:
                m = self.__mate
                self.__mate = None
        finally:
            self.__lock.release()
        if m is not None:
            m.__unlink()



########NEW FILE########
__FILENAME__ = stub_sftp
# Copyright (C) 2003-2009  Robey Pointer <robeypointer@gmail.com>
#
# This file is part of paramiko.
#
# Paramiko is free software; you can redistribute it and/or modify it under the
# terms of the GNU Lesser General Public License as published by the Free
# Software Foundation; either version 2.1 of the License, or (at your option)
# any later version.
#
# Paramiko is distributed in the hope that it will be useful, but WITHOUT ANY
# WARRANTY; without even the implied warranty of MERCHANTABILITY or FITNESS FOR
# A PARTICULAR PURPOSE.  See the GNU Lesser General Public License for more
# details.
#
# You should have received a copy of the GNU Lesser General Public License
# along with Paramiko; if not, write to the Free Software Foundation, Inc.,
# 59 Temple Place, Suite 330, Boston, MA  02111-1307  USA.

"""
A stub SFTP server for loopback SFTP testing.
"""

import os
from paramiko import ServerInterface, SFTPServerInterface, SFTPServer, SFTPAttributes, \
    SFTPHandle, SFTP_OK, AUTH_SUCCESSFUL, OPEN_SUCCEEDED
from paramiko.common import o666


class StubServer (ServerInterface):
    def check_auth_password(self, username, password):
        # all are allowed
        return AUTH_SUCCESSFUL

    def check_channel_request(self, kind, chanid):
        return OPEN_SUCCEEDED


class StubSFTPHandle (SFTPHandle):
    def stat(self):
        try:
            return SFTPAttributes.from_stat(os.fstat(self.readfile.fileno()))
        except OSError as e:
            return SFTPServer.convert_errno(e.errno)

    def chattr(self, attr):
        # python doesn't have equivalents to fchown or fchmod, so we have to
        # use the stored filename
        try:
            SFTPServer.set_file_attr(self.filename, attr)
            return SFTP_OK
        except OSError as e:
            return SFTPServer.convert_errno(e.errno)


class StubSFTPServer (SFTPServerInterface):
    # assume current folder is a fine root
    # (the tests always create and eventualy delete a subfolder, so there shouldn't be any mess)
    ROOT = os.getcwd()
        
    def _realpath(self, path):
        return self.ROOT + self.canonicalize(path)

    def list_folder(self, path):
        path = self._realpath(path)
        try:
            out = []
            flist = os.listdir(path)
            for fname in flist:
                attr = SFTPAttributes.from_stat(os.stat(os.path.join(path, fname)))
                attr.filename = fname
                out.append(attr)
            return out
        except OSError as e:
            return SFTPServer.convert_errno(e.errno)

    def stat(self, path):
        path = self._realpath(path)
        try:
            return SFTPAttributes.from_stat(os.stat(path))
        except OSError as e:
            return SFTPServer.convert_errno(e.errno)

    def lstat(self, path):
        path = self._realpath(path)
        try:
            return SFTPAttributes.from_stat(os.lstat(path))
        except OSError as e:
            return SFTPServer.convert_errno(e.errno)

    def open(self, path, flags, attr):
        path = self._realpath(path)
        try:
            binary_flag = getattr(os, 'O_BINARY', 0)
            flags |= binary_flag
            mode = getattr(attr, 'st_mode', None)
            if mode is not None:
                fd = os.open(path, flags, mode)
            else:
                # os.open() defaults to 0777 which is
                # an odd default mode for files
                fd = os.open(path, flags, o666)
        except OSError as e:
            return SFTPServer.convert_errno(e.errno)
        if (flags & os.O_CREAT) and (attr is not None):
            attr._flags &= ~attr.FLAG_PERMISSIONS
            SFTPServer.set_file_attr(path, attr)
        if flags & os.O_WRONLY:
            if flags & os.O_APPEND:
                fstr = 'ab'
            else:
                fstr = 'wb'
        elif flags & os.O_RDWR:
            if flags & os.O_APPEND:
                fstr = 'a+b'
            else:
                fstr = 'r+b'
        else:
            # O_RDONLY (== 0)
            fstr = 'rb'
        try:
            f = os.fdopen(fd, fstr)
        except OSError as e:
            return SFTPServer.convert_errno(e.errno)
        fobj = StubSFTPHandle(flags)
        fobj.filename = path
        fobj.readfile = f
        fobj.writefile = f
        return fobj

    def remove(self, path):
        path = self._realpath(path)
        try:
            os.remove(path)
        except OSError as e:
            return SFTPServer.convert_errno(e.errno)
        return SFTP_OK

    def rename(self, oldpath, newpath):
        oldpath = self._realpath(oldpath)
        newpath = self._realpath(newpath)
        try:
            os.rename(oldpath, newpath)
        except OSError as e:
            return SFTPServer.convert_errno(e.errno)
        return SFTP_OK

    def mkdir(self, path, attr):
        path = self._realpath(path)
        try:
            os.mkdir(path)
            if attr is not None:
                SFTPServer.set_file_attr(path, attr)
        except OSError as e:
            return SFTPServer.convert_errno(e.errno)
        return SFTP_OK

    def rmdir(self, path):
        path = self._realpath(path)
        try:
            os.rmdir(path)
        except OSError as e:
            return SFTPServer.convert_errno(e.errno)
        return SFTP_OK

    def chattr(self, path, attr):
        path = self._realpath(path)
        try:
            SFTPServer.set_file_attr(path, attr)
        except OSError as e:
            return SFTPServer.convert_errno(e.errno)
        return SFTP_OK

    def symlink(self, target_path, path):
        path = self._realpath(path)
        if (len(target_path) > 0) and (target_path[0] == '/'):
            # absolute symlink
            target_path = os.path.join(self.ROOT, target_path[1:])
            if target_path[:2] == '//':
                # bug in os.path.join
                target_path = target_path[1:]
        else:
            # compute relative to path
            abspath = os.path.join(os.path.dirname(path), target_path)
            if abspath[:len(self.ROOT)] != self.ROOT:
                # this symlink isn't going to work anyway -- just break it immediately
                target_path = '<error>'
        try:
            os.symlink(target_path, path)
        except OSError as e:
            return SFTPServer.convert_errno(e.errno)
        return SFTP_OK

    def readlink(self, path):
        path = self._realpath(path)
        try:
            symlink = os.readlink(path)
        except OSError as e:
            return SFTPServer.convert_errno(e.errno)
        # if it's absolute, remove the root
        if os.path.isabs(symlink):
            if symlink[:len(self.ROOT)] == self.ROOT:
                symlink = symlink[len(self.ROOT):]
                if (len(symlink) == 0) or (symlink[0] != '/'):
                    symlink = '/' + symlink
            else:
                symlink = '<error>'
        return symlink

########NEW FILE########
__FILENAME__ = test_auth
# Copyright (C) 2008  Robey Pointer <robeypointer@gmail.com>
#
# This file is part of paramiko.
#
# Paramiko is free software; you can redistribute it and/or modify it under the
# terms of the GNU Lesser General Public License as published by the Free
# Software Foundation; either version 2.1 of the License, or (at your option)
# any later version.
#
# Paramiko is distributed in the hope that it will be useful, but WITHOUT ANY
# WARRANTY; without even the implied warranty of MERCHANTABILITY or FITNESS FOR
# A PARTICULAR PURPOSE.  See the GNU Lesser General Public License for more
# details.
#
# You should have received a copy of the GNU Lesser General Public License
# along with Paramiko; if not, write to the Free Software Foundation, Inc.,
# 59 Temple Place, Suite 330, Boston, MA  02111-1307  USA.

"""
Some unit tests for authenticating over a Transport.
"""

import sys
import threading
import unittest

from paramiko import Transport, ServerInterface, RSAKey, DSSKey, \
    BadAuthenticationType, InteractiveQuery, \
    AuthenticationException
from paramiko import AUTH_FAILED, AUTH_PARTIALLY_SUCCESSFUL, AUTH_SUCCESSFUL
from paramiko.py3compat import u
from tests.loop import LoopSocket
from tests.util import test_path

_pwd = u('\u2022')


class NullServer (ServerInterface):
    paranoid_did_password = False
    paranoid_did_public_key = False
    paranoid_key = DSSKey.from_private_key_file(test_path('test_dss.key'))

    def get_allowed_auths(self, username):
        if username == 'slowdive':
            return 'publickey,password'
        if username == 'paranoid':
            if not self.paranoid_did_password and not self.paranoid_did_public_key:
                return 'publickey,password'
            elif self.paranoid_did_password:
                return 'publickey'
            else:
                return 'password'
        if username == 'commie':
            return 'keyboard-interactive'
        if username == 'utf8':
            return 'password'
        if username == 'non-utf8':
            return 'password'
        return 'publickey'

    def check_auth_password(self, username, password):
        if (username == 'slowdive') and (password == 'pygmalion'):
            return AUTH_SUCCESSFUL
        if (username == 'paranoid') and (password == 'paranoid'):
            # 2-part auth (even openssh doesn't support this)
            self.paranoid_did_password = True
            if self.paranoid_did_public_key:
                return AUTH_SUCCESSFUL
            return AUTH_PARTIALLY_SUCCESSFUL
        if (username == 'utf8') and (password == _pwd):
            return AUTH_SUCCESSFUL
        if (username == 'non-utf8') and (password == '\xff'):
            return AUTH_SUCCESSFUL
        if username == 'bad-server':
            raise Exception("Ack!")
        return AUTH_FAILED

    def check_auth_publickey(self, username, key):
        if (username == 'paranoid') and (key == self.paranoid_key):
            # 2-part auth
            self.paranoid_did_public_key = True
            if self.paranoid_did_password:
                return AUTH_SUCCESSFUL
            return AUTH_PARTIALLY_SUCCESSFUL
        return AUTH_FAILED
    
    def check_auth_interactive(self, username, submethods):
        if username == 'commie':
            self.username = username
            return InteractiveQuery('password', 'Please enter a password.', ('Password', False))
        return AUTH_FAILED
    
    def check_auth_interactive_response(self, responses):
        if self.username == 'commie':
            if (len(responses) == 1) and (responses[0] == 'cat'):
                return AUTH_SUCCESSFUL
        return AUTH_FAILED


class AuthTest (unittest.TestCase):

    def setUp(self):
        self.socks = LoopSocket()
        self.sockc = LoopSocket()
        self.sockc.link(self.socks)
        self.tc = Transport(self.sockc)
        self.ts = Transport(self.socks)

    def tearDown(self):
        self.tc.close()
        self.ts.close()
        self.socks.close()
        self.sockc.close()
    
    def start_server(self):
        host_key = RSAKey.from_private_key_file(test_path('test_rsa.key'))
        self.public_host_key = RSAKey(data=host_key.asbytes())
        self.ts.add_server_key(host_key)
        self.event = threading.Event()
        self.server = NullServer()
        self.assertTrue(not self.event.isSet())
        self.ts.start_server(self.event, self.server)
    
    def verify_finished(self):
        self.event.wait(1.0)
        self.assertTrue(self.event.isSet())
        self.assertTrue(self.ts.is_active())

    def test_1_bad_auth_type(self):
        """
        verify that we get the right exception when an unsupported auth
        type is requested.
        """
        self.start_server()
        try:
            self.tc.connect(hostkey=self.public_host_key,
                            username='unknown', password='error')
            self.assertTrue(False)
        except:
            etype, evalue, etb = sys.exc_info()
            self.assertEqual(BadAuthenticationType, etype)
            self.assertEqual(['publickey'], evalue.allowed_types)

    def test_2_bad_password(self):
        """
        verify that a bad password gets the right exception, and that a retry
        with the right password works.
        """
        self.start_server()
        self.tc.connect(hostkey=self.public_host_key)
        try:
            self.tc.auth_password(username='slowdive', password='error')
            self.assertTrue(False)
        except:
            etype, evalue, etb = sys.exc_info()
            self.assertTrue(issubclass(etype, AuthenticationException))
        self.tc.auth_password(username='slowdive', password='pygmalion')
        self.verify_finished()
    
    def test_3_multipart_auth(self):
        """
        verify that multipart auth works.
        """
        self.start_server()
        self.tc.connect(hostkey=self.public_host_key)
        remain = self.tc.auth_password(username='paranoid', password='paranoid')
        self.assertEqual(['publickey'], remain)
        key = DSSKey.from_private_key_file(test_path('test_dss.key'))
        remain = self.tc.auth_publickey(username='paranoid', key=key)
        self.assertEqual([], remain)
        self.verify_finished()

    def test_4_interactive_auth(self):
        """
        verify keyboard-interactive auth works.
        """
        self.start_server()
        self.tc.connect(hostkey=self.public_host_key)

        def handler(title, instructions, prompts):
            self.got_title = title
            self.got_instructions = instructions
            self.got_prompts = prompts
            return ['cat']
        remain = self.tc.auth_interactive('commie', handler)
        self.assertEqual(self.got_title, 'password')
        self.assertEqual(self.got_prompts, [('Password', False)])
        self.assertEqual([], remain)
        self.verify_finished()
        
    def test_5_interactive_auth_fallback(self):
        """
        verify that a password auth attempt will fallback to "interactive"
        if password auth isn't supported but interactive is.
        """
        self.start_server()
        self.tc.connect(hostkey=self.public_host_key)
        remain = self.tc.auth_password('commie', 'cat')
        self.assertEqual([], remain)
        self.verify_finished()

    def test_6_auth_utf8(self):
        """
        verify that utf-8 encoding happens in authentication.
        """
        self.start_server()
        self.tc.connect(hostkey=self.public_host_key)
        remain = self.tc.auth_password('utf8', _pwd)
        self.assertEqual([], remain)
        self.verify_finished()

    def test_7_auth_non_utf8(self):
        """
        verify that non-utf-8 encoded passwords can be used for broken
        servers.
        """
        self.start_server()
        self.tc.connect(hostkey=self.public_host_key)
        remain = self.tc.auth_password('non-utf8', '\xff')
        self.assertEqual([], remain)
        self.verify_finished()

    def test_8_auth_gets_disconnected(self):
        """
        verify that we catch a server disconnecting during auth, and report
        it as an auth failure.
        """
        self.start_server()
        self.tc.connect(hostkey=self.public_host_key)
        try:
            remain = self.tc.auth_password('bad-server', 'hello')
        except:
            etype, evalue, etb = sys.exc_info()
            self.assertTrue(issubclass(etype, AuthenticationException))

########NEW FILE########
__FILENAME__ = test_buffered_pipe
# Copyright (C) 2006-2007  Robey Pointer <robeypointer@gmail.com>
#
# This file is part of paramiko.
#
# Paramiko is free software; you can redistribute it and/or modify it under the
# terms of the GNU Lesser General Public License as published by the Free
# Software Foundation; either version 2.1 of the License, or (at your option)
# any later version.
#
# Paramiko is distributed in the hope that it will be useful, but WITHOUT ANY
# WARRANTY; without even the implied warranty of MERCHANTABILITY or FITNESS FOR
# A PARTICULAR PURPOSE.  See the GNU Lesser General Public License for more
# details.
#
# You should have received a copy of the GNU Lesser General Public License
# along with Paramiko; if not, write to the Free Software Foundation, Inc.,
# 59 Temple Place, Suite 330, Boston, MA  02111-1307  USA.

"""
Some unit tests for BufferedPipe.
"""

import threading
import time
from paramiko.buffered_pipe import BufferedPipe, PipeTimeout
from paramiko import pipe

from tests.util import ParamikoTest


def delay_thread(p):
    p.feed('a')
    time.sleep(0.5)
    p.feed('b')
    p.close()


def close_thread(p):
    time.sleep(0.2)
    p.close()


class BufferedPipeTest(ParamikoTest):
    def test_1_buffered_pipe(self):
        p = BufferedPipe()
        self.assertTrue(not p.read_ready())
        p.feed('hello.')
        self.assertTrue(p.read_ready())
        data = p.read(6)
        self.assertEqual(b'hello.', data)
        
        p.feed('plus/minus')
        self.assertEqual(b'plu', p.read(3))
        self.assertEqual(b's/m', p.read(3))
        self.assertEqual(b'inus', p.read(4))
        
        p.close()
        self.assertTrue(not p.read_ready())
        self.assertEqual(b'', p.read(1))

    def test_2_delay(self):
        p = BufferedPipe()
        self.assertTrue(not p.read_ready())
        threading.Thread(target=delay_thread, args=(p,)).start()
        self.assertEqual(b'a', p.read(1, 0.1))
        try:
            p.read(1, 0.1)
            self.assertTrue(False)
        except PipeTimeout:
            pass
        self.assertEqual(b'b', p.read(1, 1.0))
        self.assertEqual(b'', p.read(1))

    def test_3_close_while_reading(self):
        p = BufferedPipe()
        threading.Thread(target=close_thread, args=(p,)).start()
        data = p.read(1, 1.0)
        self.assertEqual(b'', data)

    def test_4_or_pipe(self):
        p = pipe.make_pipe()
        p1, p2 = pipe.make_or_pipe(p)
        self.assertFalse(p._set)
        p1.set()
        self.assertTrue(p._set)
        p2.set()
        self.assertTrue(p._set)
        p1.clear()
        self.assertTrue(p._set)
        p2.clear()
        self.assertFalse(p._set)

########NEW FILE########
__FILENAME__ = test_client
# Copyright (C) 2003-2009  Robey Pointer <robeypointer@gmail.com>
#
# This file is part of paramiko.
#
# Paramiko is free software; you can redistribute it and/or modify it under the
# terms of the GNU Lesser General Public License as published by the Free
# Software Foundation; either version 2.1 of the License, or (at your option)
# any later version.
#
# Paramiko is distributed in the hope that it will be useful, but WITHOUT ANY
# WARRANTY; without even the implied warranty of MERCHANTABILITY or FITNESS FOR
# A PARTICULAR PURPOSE.  See the GNU Lesser General Public License for more
# details.
#
# You should have received a copy of the GNU Lesser General Public License
# along with Paramiko; if not, write to the Free Software Foundation, Inc.,
# 59 Temple Place, Suite 330, Boston, MA  02111-1307  USA.

"""
Some unit tests for SSHClient.
"""

import socket
from tempfile import mkstemp
import threading
import unittest
import weakref
import warnings
import os
from tests.util import test_path
import paramiko
from paramiko.common import PY2


class NullServer (paramiko.ServerInterface):

    def get_allowed_auths(self, username):
        if username == 'slowdive':
            return 'publickey,password'
        return 'publickey'

    def check_auth_password(self, username, password):
        if (username == 'slowdive') and (password == 'pygmalion'):
            return paramiko.AUTH_SUCCESSFUL
        return paramiko.AUTH_FAILED

    def check_auth_publickey(self, username, key):
        if (key.get_name() == 'ssh-dss') and key.get_fingerprint() == b'\x44\x78\xf0\xb9\xa2\x3c\xc5\x18\x20\x09\xff\x75\x5b\xc1\xd2\x6c':
            return paramiko.AUTH_SUCCESSFUL
        return paramiko.AUTH_FAILED

    def check_channel_request(self, kind, chanid):
        return paramiko.OPEN_SUCCEEDED

    def check_channel_exec_request(self, channel, command):
        if command != 'yes':
            return False
        return True


class SSHClientTest (unittest.TestCase):

    def setUp(self):
        self.sockl = socket.socket()
        self.sockl.bind(('localhost', 0))
        self.sockl.listen(1)
        self.addr, self.port = self.sockl.getsockname()
        self.event = threading.Event()

    def tearDown(self):
        for attr in "tc ts socks sockl".split():
            if hasattr(self, attr):
                getattr(self, attr).close()

    def _run(self):
        self.socks, addr = self.sockl.accept()
        self.ts = paramiko.Transport(self.socks)
        host_key = paramiko.RSAKey.from_private_key_file(test_path('test_rsa.key'))
        self.ts.add_server_key(host_key)
        server = NullServer()
        self.ts.start_server(self.event, server)

    def test_1_client(self):
        """
        verify that the SSHClient stuff works too.
        """
        threading.Thread(target=self._run).start()
        host_key = paramiko.RSAKey.from_private_key_file(test_path('test_rsa.key'))
        public_host_key = paramiko.RSAKey(data=host_key.asbytes())

        self.tc = paramiko.SSHClient()
        self.tc.get_host_keys().add('[%s]:%d' % (self.addr, self.port), 'ssh-rsa', public_host_key)
        self.tc.connect(self.addr, self.port, username='slowdive', password='pygmalion')

        self.event.wait(1.0)
        self.assertTrue(self.event.isSet())
        self.assertTrue(self.ts.is_active())
        self.assertEqual('slowdive', self.ts.get_username())
        self.assertEqual(True, self.ts.is_authenticated())

        stdin, stdout, stderr = self.tc.exec_command('yes')
        schan = self.ts.accept(1.0)

        schan.send('Hello there.\n')
        schan.send_stderr('This is on stderr.\n')
        schan.close()

        self.assertEqual('Hello there.\n', stdout.readline())
        self.assertEqual('', stdout.readline())
        self.assertEqual('This is on stderr.\n', stderr.readline())
        self.assertEqual('', stderr.readline())

        stdin.close()
        stdout.close()
        stderr.close()

    def test_2_client_dsa(self):
        """
        verify that SSHClient works with a DSA key.
        """
        threading.Thread(target=self._run).start()
        host_key = paramiko.RSAKey.from_private_key_file(test_path('test_rsa.key'))
        public_host_key = paramiko.RSAKey(data=host_key.asbytes())

        self.tc = paramiko.SSHClient()
        self.tc.get_host_keys().add('[%s]:%d' % (self.addr, self.port), 'ssh-rsa', public_host_key)
        self.tc.connect(self.addr, self.port, username='slowdive', key_filename=test_path('test_dss.key'))

        self.event.wait(1.0)
        self.assertTrue(self.event.isSet())
        self.assertTrue(self.ts.is_active())
        self.assertEqual('slowdive', self.ts.get_username())
        self.assertEqual(True, self.ts.is_authenticated())

        stdin, stdout, stderr = self.tc.exec_command('yes')
        schan = self.ts.accept(1.0)

        schan.send('Hello there.\n')
        schan.send_stderr('This is on stderr.\n')
        schan.close()

        self.assertEqual('Hello there.\n', stdout.readline())
        self.assertEqual('', stdout.readline())
        self.assertEqual('This is on stderr.\n', stderr.readline())
        self.assertEqual('', stderr.readline())

        stdin.close()
        stdout.close()
        stderr.close()

    def test_3_multiple_key_files(self):
        """
        verify that SSHClient accepts and tries multiple key files.
        """
        threading.Thread(target=self._run).start()
        host_key = paramiko.RSAKey.from_private_key_file(test_path('test_rsa.key'))
        public_host_key = paramiko.RSAKey(data=host_key.asbytes())

        self.tc = paramiko.SSHClient()
        self.tc.get_host_keys().add('[%s]:%d' % (self.addr, self.port), 'ssh-rsa', public_host_key)
        self.tc.connect(self.addr, self.port, username='slowdive', key_filename=[test_path('test_rsa.key'), test_path('test_dss.key')])

        self.event.wait(1.0)
        self.assertTrue(self.event.isSet())
        self.assertTrue(self.ts.is_active())
        self.assertEqual('slowdive', self.ts.get_username())
        self.assertEqual(True, self.ts.is_authenticated())

    def test_4_auto_add_policy(self):
        """
        verify that SSHClient's AutoAddPolicy works.
        """
        threading.Thread(target=self._run).start()
        host_key = paramiko.RSAKey.from_private_key_file(test_path('test_rsa.key'))
        public_host_key = paramiko.RSAKey(data=host_key.asbytes())

        self.tc = paramiko.SSHClient()
        self.tc.set_missing_host_key_policy(paramiko.AutoAddPolicy())
        self.assertEqual(0, len(self.tc.get_host_keys()))
        self.tc.connect(self.addr, self.port, username='slowdive', password='pygmalion')

        self.event.wait(1.0)
        self.assertTrue(self.event.isSet())
        self.assertTrue(self.ts.is_active())
        self.assertEqual('slowdive', self.ts.get_username())
        self.assertEqual(True, self.ts.is_authenticated())
        self.assertEqual(1, len(self.tc.get_host_keys()))
        self.assertEqual(public_host_key, self.tc.get_host_keys()['[%s]:%d' % (self.addr, self.port)]['ssh-rsa'])

    def test_5_save_host_keys(self):
        """
        verify that SSHClient correctly saves a known_hosts file.
        """
        warnings.filterwarnings('ignore', 'tempnam.*')

        host_key = paramiko.RSAKey.from_private_key_file(test_path('test_rsa.key'))
        public_host_key = paramiko.RSAKey(data=host_key.asbytes())
        fd, localname = mkstemp()
        os.close(fd)

        client = paramiko.SSHClient()
        self.assertEquals(0, len(client.get_host_keys()))

        host_id = '[%s]:%d' % (self.addr, self.port)

        client.get_host_keys().add(host_id, 'ssh-rsa', public_host_key)
        self.assertEquals(1, len(client.get_host_keys()))
        self.assertEquals(public_host_key, client.get_host_keys()[host_id]['ssh-rsa'])

        client.save_host_keys(localname)

        with open(localname) as fd:
            assert host_id in fd.read()

        os.unlink(localname)

    def test_6_cleanup(self):
        """
        verify that when an SSHClient is collected, its transport (and the
        transport's packetizer) is closed.
        """
        # Unclear why this is borked on Py3, but it is, and does not seem worth
        # pursuing at the moment.
        if not PY2:
            return
        threading.Thread(target=self._run).start()
        host_key = paramiko.RSAKey.from_private_key_file(test_path('test_rsa.key'))
        public_host_key = paramiko.RSAKey(data=host_key.asbytes())

        self.tc = paramiko.SSHClient()
        self.tc.set_missing_host_key_policy(paramiko.AutoAddPolicy())
        self.assertEqual(0, len(self.tc.get_host_keys()))
        self.tc.connect(self.addr, self.port, username='slowdive', password='pygmalion')

        self.event.wait(1.0)
        self.assertTrue(self.event.isSet())
        self.assertTrue(self.ts.is_active())

        p = weakref.ref(self.tc._transport.packetizer)
        self.assertTrue(p() is not None)
        self.tc.close()
        del self.tc

        # hrm, sometimes p isn't cleared right away.  why is that?
        #st = time.time()
        #while (time.time() - st < 5.0) and (p() is not None):
        #    time.sleep(0.1)

        # instead of dumbly waiting for the GC to collect, force a collection
        # to see whether the SSHClient object is deallocated correctly
        import gc
        gc.collect()

        self.assertTrue(p() is None)

########NEW FILE########
__FILENAME__ = test_file
# Copyright (C) 2003-2009  Robey Pointer <robeypointer@gmail.com>
#
# This file is part of paramiko.
#
# Paramiko is free software; you can redistribute it and/or modify it under the
# terms of the GNU Lesser General Public License as published by the Free
# Software Foundation; either version 2.1 of the License, or (at your option)
# any later version.
#
# Paramiko is distributed in the hope that it will be useful, but WITHOUT ANY
# WARRANTY; without even the implied warranty of MERCHANTABILITY or FITNESS FOR
# A PARTICULAR PURPOSE.  See the GNU Lesser General Public License for more
# details.
#
# You should have received a copy of the GNU Lesser General Public License
# along with Paramiko; if not, write to the Free Software Foundation, Inc.,
# 59 Temple Place, Suite 330, Boston, MA  02111-1307  USA.

"""
Some unit tests for the BufferedFile abstraction.
"""

import unittest
from paramiko.file import BufferedFile
from paramiko.common import linefeed_byte, crlf, cr_byte


class LoopbackFile (BufferedFile):
    """
    BufferedFile object that you can write data into, and then read it back.
    """
    def __init__(self, mode='r', bufsize=-1):
        BufferedFile.__init__(self)
        self._set_mode(mode, bufsize)
        self.buffer = bytes()

    def _read(self, size):
        if len(self.buffer) == 0:
            return None
        if size > len(self.buffer):
            size = len(self.buffer)
        data = self.buffer[:size]
        self.buffer = self.buffer[size:]
        return data

    def _write(self, data):
        self.buffer += data
        return len(data)


class BufferedFileTest (unittest.TestCase):

    def test_1_simple(self):
        f = LoopbackFile('r')
        try:
            f.write(b'hi')
            self.assertTrue(False, 'no exception on write to read-only file')
        except:
            pass
        f.close()

        f = LoopbackFile('w')
        try:
            f.read(1)
            self.assertTrue(False, 'no exception to read from write-only file')
        except:
            pass
        f.close()

    def test_2_readline(self):
        f = LoopbackFile('r+U')
        f.write(b'First line.\nSecond line.\r\nThird line.\nFinal line non-terminated.')
        self.assertEqual(f.readline(), 'First line.\n')
        # universal newline mode should convert this linefeed:
        self.assertEqual(f.readline(), 'Second line.\n')
        # truncated line:
        self.assertEqual(f.readline(7), 'Third l')
        self.assertEqual(f.readline(), 'ine.\n')
        self.assertEqual(f.readline(), 'Final line non-terminated.')
        self.assertEqual(f.readline(), '')
        f.close()
        try:
            f.readline()
            self.assertTrue(False, 'no exception on readline of closed file')
        except IOError:
            pass
        self.assertTrue(linefeed_byte in f.newlines)
        self.assertTrue(crlf in f.newlines)
        self.assertTrue(cr_byte not in f.newlines)

    def test_3_lf(self):
        """
        try to trick the linefeed detector.
        """
        f = LoopbackFile('r+U')
        f.write(b'First line.\r')
        self.assertEqual(f.readline(), 'First line.\n')
        f.write(b'\nSecond.\r\n')
        self.assertEqual(f.readline(), 'Second.\n')
        f.close()
        self.assertEqual(f.newlines, crlf)

    def test_4_write(self):
        """
        verify that write buffering is on.
        """
        f = LoopbackFile('r+', 1)
        f.write(b'Complete line.\nIncomplete line.')
        self.assertEqual(f.readline(), 'Complete line.\n')
        self.assertEqual(f.readline(), '')
        f.write('..\n')
        self.assertEqual(f.readline(), 'Incomplete line...\n')
        f.close()

    def test_5_flush(self):
        """
        verify that flush will force a write.
        """
        f = LoopbackFile('r+', 512)
        f.write('Not\nquite\n512 bytes.\n')
        self.assertEqual(f.read(1), b'')
        f.flush()
        self.assertEqual(f.read(5), b'Not\nq')
        self.assertEqual(f.read(10), b'uite\n512 b')
        self.assertEqual(f.read(9), b'ytes.\n')
        self.assertEqual(f.read(3), b'')
        f.close()

    def test_6_buffering(self):
        """
        verify that flushing happens automatically on buffer crossing.
        """
        f = LoopbackFile('r+', 16)
        f.write(b'Too small.')
        self.assertEqual(f.read(4), b'')
        f.write(b'  ')
        self.assertEqual(f.read(4), b'')
        f.write(b'Enough.')
        self.assertEqual(f.read(20), b'Too small.  Enough.')
        f.close()

    def test_7_read_all(self):
        """
        verify that read(-1) returns everything left in the file.
        """
        f = LoopbackFile('r+', 16)
        f.write(b'The first thing you need to do is open your eyes. ')
        f.write(b'Then, you need to close them again.\n')
        s = f.read(-1)
        self.assertEqual(s, b'The first thing you need to do is open your eyes. Then, you ' +
                            b'need to close them again.\n')
        f.close()

if __name__ == '__main__':
    from unittest import main
    main()


########NEW FILE########
__FILENAME__ = test_hostkeys
# Copyright (C) 2006-2007  Robey Pointer <robeypointer@gmail.com>
#
# This file is part of paramiko.
#
# Paramiko is free software; you can redistribute it and/or modify it under the
# terms of the GNU Lesser General Public License as published by the Free
# Software Foundation; either version 2.1 of the License, or (at your option)
# any later version.
#
# Paramiko is distributed in the hope that it will be useful, but WITHOUT ANY
# WARRANTY; without even the implied warranty of MERCHANTABILITY or FITNESS FOR
# A PARTICULAR PURPOSE.  See the GNU Lesser General Public License for more
# details.
#
# You should have received a copy of the GNU Lesser General Public License
# along with Paramiko; if not, write to the Free Software Foundation, Inc.,
# 59 Temple Place, Suite 330, Boston, MA  02111-1307  USA.

"""
Some unit tests for HostKeys.
"""

from binascii import hexlify
import os
import unittest
import paramiko
from paramiko.py3compat import decodebytes


test_hosts_file = """\
secure.example.com ssh-rsa AAAAB3NzaC1yc2EAAAABIwAAAIEA1PD6U2/TVxET6lkpKhOk5r\
9q/kAYG6sP9f5zuUYP8i7FOFp/6ncCEbbtg/lB+A3iidyxoSWl+9jtoyyDOOVX4UIDV9G11Ml8om3\
D+jrpI9cycZHqilK0HmxDeCuxbwyMuaCygU9gS2qoRvNLWZk70OpIKSSpBo0Wl3/XUmz9uhc=
happy.example.com ssh-rsa AAAAB3NzaC1yc2EAAAABIwAAAIEA8bP1ZA7DCZDB9J0s50l31M\
BGQ3GQ/Fc7SX6gkpXkwcZryoi4kNFhHu5LvHcZPdxXV1D+uTMfGS1eyd2Yz/DoNWXNAl8TI0cAsW\
5ymME3bQ4J/k1IKxCtz/bAlAqFgKoc+EolMziDYqWIATtW0rYTJvzGAzTmMj80/QpsFH+Pc2M=
"""

keyblob = b"""\
AAAAB3NzaC1yc2EAAAABIwAAAIEA8bP1ZA7DCZDB9J0s50l31MBGQ3GQ/Fc7SX6gkpXkwcZryoi4k\
NFhHu5LvHcZPdxXV1D+uTMfGS1eyd2Yz/DoNWXNAl8TI0cAsW5ymME3bQ4J/k1IKxCtz/bAlAqFgK\
oc+EolMziDYqWIATtW0rYTJvzGAzTmMj80/QpsFH+Pc2M="""

keyblob_dss = b"""\
AAAAB3NzaC1kc3MAAACBAOeBpgNnfRzr/twmAQRu2XwWAp3CFtrVnug6s6fgwj/oLjYbVtjAy6pl/\
h0EKCWx2rf1IetyNsTxWrniA9I6HeDj65X1FyDkg6g8tvCnaNB8Xp/UUhuzHuGsMIipRxBxw9LF60\
8EqZcj1E3ytktoW5B5OcjrkEoz3xG7C+rpIjYvAAAAFQDwz4UnmsGiSNu5iqjn3uTzwUpshwAAAIE\
AkxfFeY8P2wZpDjX0MimZl5wkoFQDL25cPzGBuB4OnB8NoUk/yjAHIIpEShw8V+LzouMK5CTJQo5+\
Ngw3qIch/WgRmMHy4kBq1SsXMjQCte1So6HBMvBPIW5SiMTmjCfZZiw4AYHK+B/JaOwaG9yRg2Ejg\
4Ok10+XFDxlqZo8Y+wAAACARmR7CCPjodxASvRbIyzaVpZoJ/Z6x7dAumV+ysrV1BVYd0lYukmnjO\
1kKBWApqpH1ve9XDQYN8zgxM4b16L21kpoWQnZtXrY3GZ4/it9kUgyB7+NwacIBlXa8cMDL7Q/69o\
0d54U0X/NeX5QxuYR6OMJlrkQB7oiW/P/1mwjQgE="""


class HostKeysTest (unittest.TestCase):

    def setUp(self):
        with open('hostfile.temp', 'w') as f:
            f.write(test_hosts_file)

    def tearDown(self):
        os.unlink('hostfile.temp')

    def test_1_load(self):
        hostdict = paramiko.HostKeys('hostfile.temp')
        self.assertEqual(2, len(hostdict))
        self.assertEqual(1, len(list(hostdict.values())[0]))
        self.assertEqual(1, len(list(hostdict.values())[1]))
        fp = hexlify(hostdict['secure.example.com']['ssh-rsa'].get_fingerprint()).upper()
        self.assertEqual(b'E6684DB30E109B67B70FF1DC5C7F1363', fp)

    def test_2_add(self):
        hostdict = paramiko.HostKeys('hostfile.temp')
        hh = '|1|BMsIC6cUIP2zBuXR3t2LRcJYjzM=|hpkJMysjTk/+zzUUzxQEa2ieq6c='
        key = paramiko.RSAKey(data=decodebytes(keyblob))
        hostdict.add(hh, 'ssh-rsa', key)
        self.assertEqual(3, len(list(hostdict)))
        x = hostdict['foo.example.com']
        fp = hexlify(x['ssh-rsa'].get_fingerprint()).upper()
        self.assertEqual(b'7EC91BB336CB6D810B124B1353C32396', fp)
        self.assertTrue(hostdict.check('foo.example.com', key))

    def test_3_dict(self):
        hostdict = paramiko.HostKeys('hostfile.temp')
        self.assertTrue('secure.example.com' in hostdict)
        self.assertTrue('not.example.com' not in hostdict)
        self.assertTrue('secure.example.com' in hostdict)
        self.assertTrue('not.example.com' not in hostdict)
        x = hostdict.get('secure.example.com', None)
        self.assertTrue(x is not None)
        fp = hexlify(x['ssh-rsa'].get_fingerprint()).upper()
        self.assertEqual(b'E6684DB30E109B67B70FF1DC5C7F1363', fp)
        i = 0
        for key in hostdict:
            i += 1
        self.assertEqual(2, i)
        
    def test_4_dict_set(self):
        hostdict = paramiko.HostKeys('hostfile.temp')
        key = paramiko.RSAKey(data=decodebytes(keyblob))
        key_dss = paramiko.DSSKey(data=decodebytes(keyblob_dss))
        hostdict['secure.example.com'] = {
            'ssh-rsa': key,
            'ssh-dss': key_dss
        }
        hostdict['fake.example.com'] = {}
        hostdict['fake.example.com']['ssh-rsa'] = key
        
        self.assertEqual(3, len(hostdict))
        self.assertEqual(2, len(list(hostdict.values())[0]))
        self.assertEqual(1, len(list(hostdict.values())[1]))
        self.assertEqual(1, len(list(hostdict.values())[2]))
        fp = hexlify(hostdict['secure.example.com']['ssh-rsa'].get_fingerprint()).upper()
        self.assertEqual(b'7EC91BB336CB6D810B124B1353C32396', fp)
        fp = hexlify(hostdict['secure.example.com']['ssh-dss'].get_fingerprint()).upper()
        self.assertEqual(b'4478F0B9A23CC5182009FF755BC1D26C', fp)

########NEW FILE########
__FILENAME__ = test_kex
# Copyright (C) 2003-2009  Robey Pointer <robeypointer@gmail.com>
#
# This file is part of paramiko.
#
# Paramiko is free software; you can redistribute it and/or modify it under the
# terms of the GNU Lesser General Public License as published by the Free
# Software Foundation; either version 2.1 of the License, or (at your option)
# any later version.
#
# Paramiko is distributed in the hope that it will be useful, but WITHOUT ANY
# WARRANTY; without even the implied warranty of MERCHANTABILITY or FITNESS FOR
# A PARTICULAR PURPOSE.  See the GNU Lesser General Public License for more
# details.
#
# You should have received a copy of the GNU Lesser General Public License
# along with Paramiko; if not, write to the Free Software Foundation, Inc.,
# 59 Temple Place, Suite 330, Boston, MA  02111-1307  USA.

"""
Some unit tests for the key exchange protocols.
"""

from binascii import hexlify
import os
import unittest

import paramiko.util
from paramiko.kex_group1 import KexGroup1
from paramiko.kex_gex import KexGex
from paramiko import Message
from paramiko.common import byte_chr


def dummy_urandom(n):
    return byte_chr(0xcc) * n


class FakeKey (object):
    def __str__(self):
        return 'fake-key'

    def asbytes(self):
        return b'fake-key'

    def sign_ssh_data(self, H):
        return b'fake-sig'


class FakeModulusPack (object):
    P = 0xFFFFFFFFFFFFFFFFC90FDAA22168C234C4C6628B80DC1CD129024E088A67CC74020BBEA63B139B22514A08798E3404DDEF9519B3CD3A431B302B0A6DF25F14374FE1356D6D51C245E485B576625E7EC6F44C42E9A637ED6B0BFF5CB6F406B7EDEE386BFB5A899FA5AE9F24117C4B1FE649286651ECE65381FFFFFFFFFFFFFFFF
    G = 2

    def get_modulus(self, min, ask, max):
        return self.G, self.P


class FakeTransport(object):
    local_version = 'SSH-2.0-paramiko_1.0'
    remote_version = 'SSH-2.0-lame'
    local_kex_init = 'local-kex-init'
    remote_kex_init = 'remote-kex-init'

    def _send_message(self, m):
        self._message = m

    def _expect_packet(self, *t):
        self._expect = t

    def _set_K_H(self, K, H):
        self._K = K
        self._H = H

    def _verify_key(self, host_key, sig):
        self._verify = (host_key, sig)

    def _activate_outbound(self):
        self._activated = True

    def _log(self, level, s):
        pass

    def get_server_key(self):
        return FakeKey()

    def _get_modulus_pack(self):
        return FakeModulusPack()


class KexTest (unittest.TestCase):

    K = 14730343317708716439807310032871972459448364195094179797249681733965528989482751523943515690110179031004049109375612685505881911274101441415545039654102474376472240501616988799699744135291070488314748284283496055223852115360852283821334858541043710301057312858051901453919067023103730011648890038847384890504

    def setUp(self):
        self._original_urandom = os.urandom
        os.urandom = dummy_urandom

    def tearDown(self):
        os.urandom = self._original_urandom

    def test_1_group1_client(self):
        transport = FakeTransport()
        transport.server_mode = False
        kex = KexGroup1(transport)
        kex.start_kex()
        x = b'1E000000807E2DDB1743F3487D6545F04F1C8476092FB912B013626AB5BCEB764257D88BBA64243B9F348DF7B41B8C814A995E00299913503456983FFB9178D3CD79EB6D55522418A8ABF65375872E55938AB99A84A0B5FC8A1ECC66A7C3766E7E0F80B7CE2C9225FC2DD683F4764244B72963BBB383F529DCF0C5D17740B8A2ADBE9208D4'
        self.assertEqual(x, hexlify(transport._message.asbytes()).upper())
        self.assertEqual((paramiko.kex_group1._MSG_KEXDH_REPLY,), transport._expect)

        # fake "reply"
        msg = Message()
        msg.add_string('fake-host-key')
        msg.add_mpint(69)
        msg.add_string('fake-sig')
        msg.rewind()
        kex.parse_next(paramiko.kex_group1._MSG_KEXDH_REPLY, msg)
        H = b'03079780F3D3AD0B3C6DB30C8D21685F367A86D2'
        self.assertEqual(self.K, transport._K)
        self.assertEqual(H, hexlify(transport._H).upper())
        self.assertEqual((b'fake-host-key', b'fake-sig'), transport._verify)
        self.assertTrue(transport._activated)

    def test_2_group1_server(self):
        transport = FakeTransport()
        transport.server_mode = True
        kex = KexGroup1(transport)
        kex.start_kex()
        self.assertEqual((paramiko.kex_group1._MSG_KEXDH_INIT,), transport._expect)

        msg = Message()
        msg.add_mpint(69)
        msg.rewind()
        kex.parse_next(paramiko.kex_group1._MSG_KEXDH_INIT, msg)
        H = b'B16BF34DD10945EDE84E9C1EF24A14BFDC843389'
        x = b'1F0000000866616B652D6B6579000000807E2DDB1743F3487D6545F04F1C8476092FB912B013626AB5BCEB764257D88BBA64243B9F348DF7B41B8C814A995E00299913503456983FFB9178D3CD79EB6D55522418A8ABF65375872E55938AB99A84A0B5FC8A1ECC66A7C3766E7E0F80B7CE2C9225FC2DD683F4764244B72963BBB383F529DCF0C5D17740B8A2ADBE9208D40000000866616B652D736967'
        self.assertEqual(self.K, transport._K)
        self.assertEqual(H, hexlify(transport._H).upper())
        self.assertEqual(x, hexlify(transport._message.asbytes()).upper())
        self.assertTrue(transport._activated)

    def test_3_gex_client(self):
        transport = FakeTransport()
        transport.server_mode = False
        kex = KexGex(transport)
        kex.start_kex()
        x = b'22000004000000080000002000'
        self.assertEqual(x, hexlify(transport._message.asbytes()).upper())
        self.assertEqual((paramiko.kex_gex._MSG_KEXDH_GEX_GROUP,), transport._expect)

        msg = Message()
        msg.add_mpint(FakeModulusPack.P)
        msg.add_mpint(FakeModulusPack.G)
        msg.rewind()
        kex.parse_next(paramiko.kex_gex._MSG_KEXDH_GEX_GROUP, msg)
        x = b'20000000807E2DDB1743F3487D6545F04F1C8476092FB912B013626AB5BCEB764257D88BBA64243B9F348DF7B41B8C814A995E00299913503456983FFB9178D3CD79EB6D55522418A8ABF65375872E55938AB99A84A0B5FC8A1ECC66A7C3766E7E0F80B7CE2C9225FC2DD683F4764244B72963BBB383F529DCF0C5D17740B8A2ADBE9208D4'
        self.assertEqual(x, hexlify(transport._message.asbytes()).upper())
        self.assertEqual((paramiko.kex_gex._MSG_KEXDH_GEX_REPLY,), transport._expect)

        msg = Message()
        msg.add_string('fake-host-key')
        msg.add_mpint(69)
        msg.add_string('fake-sig')
        msg.rewind()
        kex.parse_next(paramiko.kex_gex._MSG_KEXDH_GEX_REPLY, msg)
        H = b'A265563F2FA87F1A89BF007EE90D58BE2E4A4BD0'
        self.assertEqual(self.K, transport._K)
        self.assertEqual(H, hexlify(transport._H).upper())
        self.assertEqual((b'fake-host-key', b'fake-sig'), transport._verify)
        self.assertTrue(transport._activated)

    def test_4_gex_old_client(self):
        transport = FakeTransport()
        transport.server_mode = False
        kex = KexGex(transport)
        kex.start_kex(_test_old_style=True)
        x = b'1E00000800'
        self.assertEqual(x, hexlify(transport._message.asbytes()).upper())
        self.assertEqual((paramiko.kex_gex._MSG_KEXDH_GEX_GROUP,), transport._expect)

        msg = Message()
        msg.add_mpint(FakeModulusPack.P)
        msg.add_mpint(FakeModulusPack.G)
        msg.rewind()
        kex.parse_next(paramiko.kex_gex._MSG_KEXDH_GEX_GROUP, msg)
        x = b'20000000807E2DDB1743F3487D6545F04F1C8476092FB912B013626AB5BCEB764257D88BBA64243B9F348DF7B41B8C814A995E00299913503456983FFB9178D3CD79EB6D55522418A8ABF65375872E55938AB99A84A0B5FC8A1ECC66A7C3766E7E0F80B7CE2C9225FC2DD683F4764244B72963BBB383F529DCF0C5D17740B8A2ADBE9208D4'
        self.assertEqual(x, hexlify(transport._message.asbytes()).upper())
        self.assertEqual((paramiko.kex_gex._MSG_KEXDH_GEX_REPLY,), transport._expect)

        msg = Message()
        msg.add_string('fake-host-key')
        msg.add_mpint(69)
        msg.add_string('fake-sig')
        msg.rewind()
        kex.parse_next(paramiko.kex_gex._MSG_KEXDH_GEX_REPLY, msg)
        H = b'807F87B269EF7AC5EC7E75676808776A27D5864C'
        self.assertEqual(self.K, transport._K)
        self.assertEqual(H, hexlify(transport._H).upper())
        self.assertEqual((b'fake-host-key', b'fake-sig'), transport._verify)
        self.assertTrue(transport._activated)
        
    def test_5_gex_server(self):
        transport = FakeTransport()
        transport.server_mode = True
        kex = KexGex(transport)
        kex.start_kex()
        self.assertEqual((paramiko.kex_gex._MSG_KEXDH_GEX_REQUEST, paramiko.kex_gex._MSG_KEXDH_GEX_REQUEST_OLD), transport._expect)

        msg = Message()
        msg.add_int(1024)
        msg.add_int(2048)
        msg.add_int(4096)
        msg.rewind()
        kex.parse_next(paramiko.kex_gex._MSG_KEXDH_GEX_REQUEST, msg)
        x = b'1F0000008100FFFFFFFFFFFFFFFFC90FDAA22168C234C4C6628B80DC1CD129024E088A67CC74020BBEA63B139B22514A08798E3404DDEF9519B3CD3A431B302B0A6DF25F14374FE1356D6D51C245E485B576625E7EC6F44C42E9A637ED6B0BFF5CB6F406B7EDEE386BFB5A899FA5AE9F24117C4B1FE649286651ECE65381FFFFFFFFFFFFFFFF0000000102'
        self.assertEqual(x, hexlify(transport._message.asbytes()).upper())
        self.assertEqual((paramiko.kex_gex._MSG_KEXDH_GEX_INIT,), transport._expect)

        msg = Message()
        msg.add_mpint(12345)
        msg.rewind()
        kex.parse_next(paramiko.kex_gex._MSG_KEXDH_GEX_INIT, msg)
        K = 67592995013596137876033460028393339951879041140378510871612128162185209509220726296697886624612526735888348020498716482757677848959420073720160491114319163078862905400020959196386947926388406687288901564192071077389283980347784184487280885335302632305026248574716290537036069329724382811853044654824945750581
        H = b'CE754197C21BF3452863B4F44D0B3951F12516EF'
        x = b'210000000866616B652D6B6579000000807E2DDB1743F3487D6545F04F1C8476092FB912B013626AB5BCEB764257D88BBA64243B9F348DF7B41B8C814A995E00299913503456983FFB9178D3CD79EB6D55522418A8ABF65375872E55938AB99A84A0B5FC8A1ECC66A7C3766E7E0F80B7CE2C9225FC2DD683F4764244B72963BBB383F529DCF0C5D17740B8A2ADBE9208D40000000866616B652D736967'
        self.assertEqual(K, transport._K)
        self.assertEqual(H, hexlify(transport._H).upper())
        self.assertEqual(x, hexlify(transport._message.asbytes()).upper())
        self.assertTrue(transport._activated)

    def test_6_gex_server_with_old_client(self):
        transport = FakeTransport()
        transport.server_mode = True
        kex = KexGex(transport)
        kex.start_kex()
        self.assertEqual((paramiko.kex_gex._MSG_KEXDH_GEX_REQUEST, paramiko.kex_gex._MSG_KEXDH_GEX_REQUEST_OLD), transport._expect)

        msg = Message()
        msg.add_int(2048)
        msg.rewind()
        kex.parse_next(paramiko.kex_gex._MSG_KEXDH_GEX_REQUEST_OLD, msg)
        x = b'1F0000008100FFFFFFFFFFFFFFFFC90FDAA22168C234C4C6628B80DC1CD129024E088A67CC74020BBEA63B139B22514A08798E3404DDEF9519B3CD3A431B302B0A6DF25F14374FE1356D6D51C245E485B576625E7EC6F44C42E9A637ED6B0BFF5CB6F406B7EDEE386BFB5A899FA5AE9F24117C4B1FE649286651ECE65381FFFFFFFFFFFFFFFF0000000102'
        self.assertEqual(x, hexlify(transport._message.asbytes()).upper())
        self.assertEqual((paramiko.kex_gex._MSG_KEXDH_GEX_INIT,), transport._expect)

        msg = Message()
        msg.add_mpint(12345)
        msg.rewind()
        kex.parse_next(paramiko.kex_gex._MSG_KEXDH_GEX_INIT, msg)
        K = 67592995013596137876033460028393339951879041140378510871612128162185209509220726296697886624612526735888348020498716482757677848959420073720160491114319163078862905400020959196386947926388406687288901564192071077389283980347784184487280885335302632305026248574716290537036069329724382811853044654824945750581
        H = b'B41A06B2E59043CEFC1AE16EC31F1E2D12EC455B'
        x = b'210000000866616B652D6B6579000000807E2DDB1743F3487D6545F04F1C8476092FB912B013626AB5BCEB764257D88BBA64243B9F348DF7B41B8C814A995E00299913503456983FFB9178D3CD79EB6D55522418A8ABF65375872E55938AB99A84A0B5FC8A1ECC66A7C3766E7E0F80B7CE2C9225FC2DD683F4764244B72963BBB383F529DCF0C5D17740B8A2ADBE9208D40000000866616B652D736967'
        self.assertEqual(K, transport._K)
        self.assertEqual(H, hexlify(transport._H).upper())
        self.assertEqual(x, hexlify(transport._message.asbytes()).upper())
        self.assertTrue(transport._activated)

########NEW FILE########
__FILENAME__ = test_message
# Copyright (C) 2003-2009  Robey Pointer <robeypointer@gmail.com>
#
# This file is part of paramiko.
#
# Paramiko is free software; you can redistribute it and/or modify it under the
# terms of the GNU Lesser General Public License as published by the Free
# Software Foundation; either version 2.1 of the License, or (at your option)
# any later version.
#
# Paramiko is distributed in the hope that it will be useful, but WITHOUT ANY
# WARRANTY; without even the implied warranty of MERCHANTABILITY or FITNESS FOR
# A PARTICULAR PURPOSE.  See the GNU Lesser General Public License for more
# details.
#
# You should have received a copy of the GNU Lesser General Public License
# along with Paramiko; if not, write to the Free Software Foundation, Inc.,
# 59 Temple Place, Suite 330, Boston, MA  02111-1307  USA.

"""
Some unit tests for ssh protocol message blocks.
"""

import unittest
from paramiko.message import Message
from paramiko.common import byte_chr, zero_byte


class MessageTest (unittest.TestCase):

    __a = b'\x00\x00\x00\x17\x07\x60\xe0\x90\x00\x00\x00\x01\x71\x00\x00\x00\x05\x68\x65\x6c\x6c\x6f\x00\x00\x03\xe8' + b'x' * 1000
    __b = b'\x01\x00\xf3\x00\x3f\x00\x00\x00\x10\x68\x75\x65\x79\x2c\x64\x65\x77\x65\x79\x2c\x6c\x6f\x75\x69\x65'
    __c = b'\x00\x00\x00\x00\x00\x00\x00\x05\x00\x00\xf5\xe4\xd3\xc2\xb1\x09\x00\x00\x00\x01\x11\x00\x00\x00\x07\x00\xf5\xe4\xd3\xc2\xb1\x09\x00\x00\x00\x06\x9a\x1b\x2c\x3d\x4e\xf7'
    __d = b'\x00\x00\x00\x05\xff\x00\x00\x00\x05\x11\x22\x33\x44\x55\xff\x00\x00\x00\x0a\x00\xf0\x00\x00\x00\x00\x00\x00\x00\x00\x01\x00\x00\x00\x03\x63\x61\x74\x00\x00\x00\x03\x61\x2c\x62'

    def test_1_encode(self):
        msg = Message()
        msg.add_int(23)
        msg.add_int(123789456)
        msg.add_string('q')
        msg.add_string('hello')
        msg.add_string('x' * 1000)
        self.assertEqual(msg.asbytes(), self.__a)

        msg = Message()
        msg.add_boolean(True)
        msg.add_boolean(False)
        msg.add_byte(byte_chr(0xf3))

        msg.add_bytes(zero_byte + byte_chr(0x3f))
        msg.add_list(['huey', 'dewey', 'louie'])
        self.assertEqual(msg.asbytes(), self.__b)

        msg = Message()
        msg.add_int64(5)
        msg.add_int64(0xf5e4d3c2b109)
        msg.add_mpint(17)
        msg.add_mpint(0xf5e4d3c2b109)
        msg.add_mpint(-0x65e4d3c2b109)
        self.assertEqual(msg.asbytes(), self.__c)

    def test_2_decode(self):
        msg = Message(self.__a)
        self.assertEqual(msg.get_int(), 23)
        self.assertEqual(msg.get_int(), 123789456)
        self.assertEqual(msg.get_text(), 'q')
        self.assertEqual(msg.get_text(), 'hello')
        self.assertEqual(msg.get_text(), 'x' * 1000)

        msg = Message(self.__b)
        self.assertEqual(msg.get_boolean(), True)
        self.assertEqual(msg.get_boolean(), False)
        self.assertEqual(msg.get_byte(), byte_chr(0xf3))
        self.assertEqual(msg.get_bytes(2), zero_byte + byte_chr(0x3f))
        self.assertEqual(msg.get_list(), ['huey', 'dewey', 'louie'])

        msg = Message(self.__c)
        self.assertEqual(msg.get_int64(), 5)
        self.assertEqual(msg.get_int64(), 0xf5e4d3c2b109)
        self.assertEqual(msg.get_mpint(), 17)
        self.assertEqual(msg.get_mpint(), 0xf5e4d3c2b109)
        self.assertEqual(msg.get_mpint(), -0x65e4d3c2b109)

    def test_3_add(self):
        msg = Message()
        msg.add(5)
        msg.add(0x1122334455)
        msg.add(0xf00000000000000000)
        msg.add(True)
        msg.add('cat')
        msg.add(['a', 'b'])
        self.assertEqual(msg.asbytes(), self.__d)

    def test_4_misc(self):
        msg = Message(self.__d)
        self.assertEqual(msg.get_int(), 5)
        self.assertEqual(msg.get_int(), 0x1122334455)
        self.assertEqual(msg.get_int(), 0xf00000000000000000)
        self.assertEqual(msg.get_so_far(), self.__d[:29])
        self.assertEqual(msg.get_remainder(), self.__d[29:])
        msg.rewind()
        self.assertEqual(msg.get_int(), 5)
        self.assertEqual(msg.get_so_far(), self.__d[:4])
        self.assertEqual(msg.get_remainder(), self.__d[4:])

########NEW FILE########
__FILENAME__ = test_packetizer
# Copyright (C) 2003-2009  Robey Pointer <robeypointer@gmail.com>
#
# This file is part of paramiko.
#
# Paramiko is free software; you can redistribute it and/or modify it under the
# terms of the GNU Lesser General Public License as published by the Free
# Software Foundation; either version 2.1 of the License, or (at your option)
# any later version.
#
# Paramiko is distributed in the hope that it will be useful, but WITHOUT ANY
# WARRANTY; without even the implied warranty of MERCHANTABILITY or FITNESS FOR
# A PARTICULAR PURPOSE.  See the GNU Lesser General Public License for more
# details.
#
# You should have received a copy of the GNU Lesser General Public License
# along with Paramiko; if not, write to the Free Software Foundation, Inc.,
# 59 Temple Place, Suite 330, Boston, MA  02111-1307  USA.

"""
Some unit tests for the ssh2 protocol in Transport.
"""

import unittest
from hashlib import sha1

from tests.loop import LoopSocket

from Crypto.Cipher import AES

from paramiko import Message, Packetizer, util
from paramiko.common import byte_chr, zero_byte

x55 = byte_chr(0x55)
x1f = byte_chr(0x1f)


class PacketizerTest (unittest.TestCase):

    def test_1_write(self):
        rsock = LoopSocket()
        wsock = LoopSocket()
        rsock.link(wsock)
        p = Packetizer(wsock)
        p.set_log(util.get_logger('paramiko.transport'))
        p.set_hexdump(True)
        cipher = AES.new(zero_byte * 16, AES.MODE_CBC, x55 * 16)
        p.set_outbound_cipher(cipher, 16, sha1, 12, x1f * 20)

        # message has to be at least 16 bytes long, so we'll have at least one
        # block of data encrypted that contains zero random padding bytes
        m = Message()
        m.add_byte(byte_chr(100))
        m.add_int(100)
        m.add_int(1)
        m.add_int(900)
        p.send_message(m)
        data = rsock.recv(100)
        # 32 + 12 bytes of MAC = 44
        self.assertEqual(44, len(data))
        self.assertEqual(b'\x43\x91\x97\xbd\x5b\x50\xac\x25\x87\xc2\xc4\x6b\xc7\xe9\x38\xc0', data[:16])

    def test_2_read(self):
        rsock = LoopSocket()
        wsock = LoopSocket()
        rsock.link(wsock)
        p = Packetizer(rsock)
        p.set_log(util.get_logger('paramiko.transport'))
        p.set_hexdump(True)
        cipher = AES.new(zero_byte * 16, AES.MODE_CBC, x55 * 16)
        p.set_inbound_cipher(cipher, 16, sha1, 12, x1f * 20)
        wsock.send(b'\x43\x91\x97\xbd\x5b\x50\xac\x25\x87\xc2\xc4\x6b\xc7\xe9\x38\xc0\x90\xd2\x16\x56\x0d\x71\x73\x61\x38\x7c\x4c\x3d\xfb\x97\x7d\xe2\x6e\x03\xb1\xa0\xc2\x1c\xd6\x41\x41\x4c\xb4\x59')
        cmd, m = p.read_message()
        self.assertEqual(100, cmd)
        self.assertEqual(100, m.get_int())
        self.assertEqual(1, m.get_int())
        self.assertEqual(900, m.get_int())

########NEW FILE########
__FILENAME__ = test_pkey
# Copyright (C) 2003-2009  Robey Pointer <robeypointer@gmail.com>
#
# This file is part of paramiko.
#
# Paramiko is free software; you can redistribute it and/or modify it under the
# terms of the GNU Lesser General Public License as published by the Free
# Software Foundation; either version 2.1 of the License, or (at your option)
# any later version.
#
# Paramiko is distributed in the hope that it will be useful, but WITHOUT ANY
# WARRANTY; without even the implied warranty of MERCHANTABILITY or FITNESS FOR
# A PARTICULAR PURPOSE.  See the GNU Lesser General Public License for more
# details.
#
# You should have received a copy of the GNU Lesser General Public License
# along with Paramiko; if not, write to the Free Software Foundation, Inc.,
# 59 Temple Place, Suite 330, Boston, MA  02111-1307  USA.

"""
Some unit tests for public/private key objects.
"""

import unittest
from binascii import hexlify
from hashlib import md5

from paramiko import RSAKey, DSSKey, ECDSAKey, Message, util
from paramiko.py3compat import StringIO, byte_chr, b, bytes

from tests.util import test_path

# from openssh's ssh-keygen
PUB_RSA = 'ssh-rsa AAAAB3NzaC1yc2EAAAABIwAAAIEA049W6geFpmsljTwfvI1UmKWWJPNFI74+vNKTk4dmzkQY2yAMs6FhlvhlI8ysU4oj71ZsRYMecHbBbxdN79+JRFVYTKaLqjwGENeTd+yv4q+V2PvZv3fLnzApI3l7EJCqhWwJUHJ1jAkZzqDx0tyOL4uoZpww3nmE0kb3y21tH4c='
PUB_DSS = 'ssh-dss AAAAB3NzaC1kc3MAAACBAOeBpgNnfRzr/twmAQRu2XwWAp3CFtrVnug6s6fgwj/oLjYbVtjAy6pl/h0EKCWx2rf1IetyNsTxWrniA9I6HeDj65X1FyDkg6g8tvCnaNB8Xp/UUhuzHuGsMIipRxBxw9LF608EqZcj1E3ytktoW5B5OcjrkEoz3xG7C+rpIjYvAAAAFQDwz4UnmsGiSNu5iqjn3uTzwUpshwAAAIEAkxfFeY8P2wZpDjX0MimZl5wkoFQDL25cPzGBuB4OnB8NoUk/yjAHIIpEShw8V+LzouMK5CTJQo5+Ngw3qIch/WgRmMHy4kBq1SsXMjQCte1So6HBMvBPIW5SiMTmjCfZZiw4AYHK+B/JaOwaG9yRg2Ejg4Ok10+XFDxlqZo8Y+wAAACARmR7CCPjodxASvRbIyzaVpZoJ/Z6x7dAumV+ysrV1BVYd0lYukmnjO1kKBWApqpH1ve9XDQYN8zgxM4b16L21kpoWQnZtXrY3GZ4/it9kUgyB7+NwacIBlXa8cMDL7Q/69o0d54U0X/NeX5QxuYR6OMJlrkQB7oiW/P/1mwjQgE='
PUB_ECDSA = 'ecdsa-sha2-nistp256 AAAAE2VjZHNhLXNoYTItbmlzdHAyNTYAAAAIbmlzdHAyNTYAAABBBJSPZm3ZWkvk/Zx8WP+fZRZ5/NBBHnGQwR6uIC6XHGPDIHuWUzIjAwA0bzqkOUffEsbLe+uQgKl5kbc/L8KA/eo='

FINGER_RSA = '1024 60:73:38:44:cb:51:86:65:7f:de:da:a2:2b:5a:57:d5'
FINGER_DSS = '1024 44:78:f0:b9:a2:3c:c5:18:20:09:ff:75:5b:c1:d2:6c'
FINGER_ECDSA = '256 25:19:eb:55:e6:a1:47:ff:4f:38:d2:75:6f:a5:d5:60'
SIGNED_RSA = '20:d7:8a:31:21:cb:f7:92:12:f2:a4:89:37:f5:78:af:e6:16:b6:25:b9:97:3d:a2:cd:5f:ca:20:21:73:4c:ad:34:73:8f:20:77:28:e2:94:15:08:d8:91:40:7a:85:83:bf:18:37:95:dc:54:1a:9b:88:29:6c:73:ca:38:b4:04:f1:56:b9:f2:42:9d:52:1b:29:29:b4:4f:fd:c9:2d:af:47:d2:40:76:30:f3:63:45:0c:d9:1d:43:86:0f:1c:70:e2:93:12:34:f3:ac:c5:0a:2f:14:50:66:59:f1:88:ee:c1:4a:e9:d1:9c:4e:46:f0:0e:47:6f:38:74:f1:44:a8'

RSA_PRIVATE_OUT = """\
-----BEGIN RSA PRIVATE KEY-----
MIICXAIBAAKCAIEA049W6geFpmsljTwfvI1UmKWWJPNFI74+vNKTk4dmzkQY2yAM
s6FhlvhlI8ysU4oj71ZsRYMecHbBbxdN79+JRFVYTKaLqjwGENeTd+yv4q+V2PvZ
v3fLnzApI3l7EJCqhWwJUHJ1jAkZzqDx0tyOL4uoZpww3nmE0kb3y21tH4cCASMC
ggCAEiI6plhqipt4P05L3PYr0pHZq2VPEbE4k9eI/gRKo/c1VJxY3DJnc1cenKsk
trQRtW3OxCEufqsX5PNec6VyKkW+Ox6beJjMKm4KF8ZDpKi9Nw6MdX3P6Gele9D9
+ieyhVFljrnAqcXsgChTBOYlL2imqCs3qRGAJ3cMBIAx3VsCQQD3pIFVYW398kE0
n0e1icEpkbDRV4c5iZVhu8xKy2yyfy6f6lClSb2+Ub9uns7F3+b5v0pYSHbE9+/r
OpRq83AfAkEA2rMZlr8SnMXgnyka2LuggA9QgMYy18hyao1dUxySubNDa9N+q2QR
mwDisTUgRFHKIlDHoQmzPbXAmYZX1YlDmQJBAPCRLS5epV0XOAc7pL762OaNhzHC
veAfQKgVhKBt105PqaKpGyQ5AXcNlWQlPeTK4GBTbMrKDPna6RBkyrEJvV8CQBK+
5O+p+kfztCrmRCE0p1tvBuZ3Y3GU1ptrM+KNa6mEZN1bRV8l1Z+SXJLYqv6Kquz/
nBUeFq2Em3rfoSDugiMCQDyG3cxD5dKX3IgkhLyBWls/FLDk4x/DQ+NUTu0F1Cu6
JJye+5ARLkL0EweMXf0tmIYfWItDLsWB0fKg/56h0js=
-----END RSA PRIVATE KEY-----
"""

DSS_PRIVATE_OUT = """\
-----BEGIN DSA PRIVATE KEY-----
MIIBvgIBAAKCAIEA54GmA2d9HOv+3CYBBG7ZfBYCncIW2tWe6Dqzp+DCP+guNhtW
2MDLqmX+HQQoJbHat/Uh63I2xPFaueID0jod4OPrlfUXIOSDqDy28Kdo0Hxen9RS
G7Me4awwiKlHEHHD0sXrTwSplyPUTfK2S2hbkHk5yOuQSjPfEbsL6ukiNi8CFQDw
z4UnmsGiSNu5iqjn3uTzwUpshwKCAIEAkxfFeY8P2wZpDjX0MimZl5wkoFQDL25c
PzGBuB4OnB8NoUk/yjAHIIpEShw8V+LzouMK5CTJQo5+Ngw3qIch/WgRmMHy4kBq
1SsXMjQCte1So6HBMvBPIW5SiMTmjCfZZiw4AYHK+B/JaOwaG9yRg2Ejg4Ok10+X
FDxlqZo8Y+wCggCARmR7CCPjodxASvRbIyzaVpZoJ/Z6x7dAumV+ysrV1BVYd0lY
ukmnjO1kKBWApqpH1ve9XDQYN8zgxM4b16L21kpoWQnZtXrY3GZ4/it9kUgyB7+N
wacIBlXa8cMDL7Q/69o0d54U0X/NeX5QxuYR6OMJlrkQB7oiW/P/1mwjQgECFGI9
QPSch9pT9XHqn+1rZ4bK+QGA
-----END DSA PRIVATE KEY-----
"""

ECDSA_PRIVATE_OUT = """\
-----BEGIN EC PRIVATE KEY-----
MHcCAQEEIKB6ty3yVyKEnfF/zprx0qwC76MsMlHY4HXCnqho2eKioAoGCCqGSM49
AwEHoUQDQgAElI9mbdlaS+T9nHxY/59lFnn80EEecZDBHq4gLpccY8Mge5ZTMiMD
ADRvOqQ5R98Sxst765CAqXmRtz8vwoD96g==
-----END EC PRIVATE KEY-----
"""

x1234 = b'\x01\x02\x03\x04'


class KeyTest (unittest.TestCase):

    def setUp(self):
        pass

    def tearDown(self):
        pass

    def test_1_generate_key_bytes(self):
        key = util.generate_key_bytes(md5, x1234, 'happy birthday', 30)
        exp = b'\x61\xE1\xF2\x72\xF4\xC1\xC4\x56\x15\x86\xBD\x32\x24\x98\xC0\xE9\x24\x67\x27\x80\xF4\x7B\xB3\x7D\xDA\x7D\x54\x01\x9E\x64'
        self.assertEqual(exp, key)

    def test_2_load_rsa(self):
        key = RSAKey.from_private_key_file(test_path('test_rsa.key'))
        self.assertEqual('ssh-rsa', key.get_name())
        exp_rsa = b(FINGER_RSA.split()[1].replace(':', ''))
        my_rsa = hexlify(key.get_fingerprint())
        self.assertEqual(exp_rsa, my_rsa)
        self.assertEqual(PUB_RSA.split()[1], key.get_base64())
        self.assertEqual(1024, key.get_bits())

        s = StringIO()
        key.write_private_key(s)
        self.assertEqual(RSA_PRIVATE_OUT, s.getvalue())
        s.seek(0)
        key2 = RSAKey.from_private_key(s)
        self.assertEqual(key, key2)

    def test_3_load_rsa_password(self):
        key = RSAKey.from_private_key_file(test_path('test_rsa_password.key'), 'television')
        self.assertEqual('ssh-rsa', key.get_name())
        exp_rsa = b(FINGER_RSA.split()[1].replace(':', ''))
        my_rsa = hexlify(key.get_fingerprint())
        self.assertEqual(exp_rsa, my_rsa)
        self.assertEqual(PUB_RSA.split()[1], key.get_base64())
        self.assertEqual(1024, key.get_bits())
        
    def test_4_load_dss(self):
        key = DSSKey.from_private_key_file(test_path('test_dss.key'))
        self.assertEqual('ssh-dss', key.get_name())
        exp_dss = b(FINGER_DSS.split()[1].replace(':', ''))
        my_dss = hexlify(key.get_fingerprint())
        self.assertEqual(exp_dss, my_dss)
        self.assertEqual(PUB_DSS.split()[1], key.get_base64())
        self.assertEqual(1024, key.get_bits())

        s = StringIO()
        key.write_private_key(s)
        self.assertEqual(DSS_PRIVATE_OUT, s.getvalue())
        s.seek(0)
        key2 = DSSKey.from_private_key(s)
        self.assertEqual(key, key2)

    def test_5_load_dss_password(self):
        key = DSSKey.from_private_key_file(test_path('test_dss_password.key'), 'television')
        self.assertEqual('ssh-dss', key.get_name())
        exp_dss = b(FINGER_DSS.split()[1].replace(':', ''))
        my_dss = hexlify(key.get_fingerprint())
        self.assertEqual(exp_dss, my_dss)
        self.assertEqual(PUB_DSS.split()[1], key.get_base64())
        self.assertEqual(1024, key.get_bits())

    def test_6_compare_rsa(self):
        # verify that the private & public keys compare equal
        key = RSAKey.from_private_key_file(test_path('test_rsa.key'))
        self.assertEqual(key, key)
        pub = RSAKey(data=key.asbytes())
        self.assertTrue(key.can_sign())
        self.assertTrue(not pub.can_sign())
        self.assertEqual(key, pub)

    def test_7_compare_dss(self):
        # verify that the private & public keys compare equal
        key = DSSKey.from_private_key_file(test_path('test_dss.key'))
        self.assertEqual(key, key)
        pub = DSSKey(data=key.asbytes())
        self.assertTrue(key.can_sign())
        self.assertTrue(not pub.can_sign())
        self.assertEqual(key, pub)

    def test_8_sign_rsa(self):
        # verify that the rsa private key can sign and verify
        key = RSAKey.from_private_key_file(test_path('test_rsa.key'))
        msg = key.sign_ssh_data(b'ice weasels')
        self.assertTrue(type(msg) is Message)
        msg.rewind()
        self.assertEqual('ssh-rsa', msg.get_text())
        sig = bytes().join([byte_chr(int(x, 16)) for x in SIGNED_RSA.split(':')])
        self.assertEqual(sig, msg.get_binary())
        msg.rewind()
        pub = RSAKey(data=key.asbytes())
        self.assertTrue(pub.verify_ssh_sig(b'ice weasels', msg))

    def test_9_sign_dss(self):
        # verify that the dss private key can sign and verify
        key = DSSKey.from_private_key_file(test_path('test_dss.key'))
        msg = key.sign_ssh_data(b'ice weasels')
        self.assertTrue(type(msg) is Message)
        msg.rewind()
        self.assertEqual('ssh-dss', msg.get_text())
        # can't do the same test as we do for RSA, because DSS signatures
        # are usually different each time.  but we can test verification
        # anyway so it's ok.
        self.assertEqual(40, len(msg.get_binary()))
        msg.rewind()
        pub = DSSKey(data=key.asbytes())
        self.assertTrue(pub.verify_ssh_sig(b'ice weasels', msg))

    def test_A_generate_rsa(self):
        key = RSAKey.generate(1024)
        msg = key.sign_ssh_data(b'jerri blank')
        msg.rewind()
        self.assertTrue(key.verify_ssh_sig(b'jerri blank', msg))

    def test_B_generate_dss(self):
        key = DSSKey.generate(1024)
        msg = key.sign_ssh_data(b'jerri blank')
        msg.rewind()
        self.assertTrue(key.verify_ssh_sig(b'jerri blank', msg))

    def test_10_load_ecdsa(self):
        key = ECDSAKey.from_private_key_file(test_path('test_ecdsa.key'))
        self.assertEqual('ecdsa-sha2-nistp256', key.get_name())
        exp_ecdsa = b(FINGER_ECDSA.split()[1].replace(':', ''))
        my_ecdsa = hexlify(key.get_fingerprint())
        self.assertEqual(exp_ecdsa, my_ecdsa)
        self.assertEqual(PUB_ECDSA.split()[1], key.get_base64())
        self.assertEqual(256, key.get_bits())

        s = StringIO()
        key.write_private_key(s)
        self.assertEqual(ECDSA_PRIVATE_OUT, s.getvalue())
        s.seek(0)
        key2 = ECDSAKey.from_private_key(s)
        self.assertEqual(key, key2)

    def test_11_load_ecdsa_password(self):
        key = ECDSAKey.from_private_key_file(test_path('test_ecdsa_password.key'), b'television')
        self.assertEqual('ecdsa-sha2-nistp256', key.get_name())
        exp_ecdsa = b(FINGER_ECDSA.split()[1].replace(':', ''))
        my_ecdsa = hexlify(key.get_fingerprint())
        self.assertEqual(exp_ecdsa, my_ecdsa)
        self.assertEqual(PUB_ECDSA.split()[1], key.get_base64())
        self.assertEqual(256, key.get_bits())

    def test_12_compare_ecdsa(self):
        # verify that the private & public keys compare equal
        key = ECDSAKey.from_private_key_file(test_path('test_ecdsa.key'))
        self.assertEqual(key, key)
        pub = ECDSAKey(data=key.asbytes())
        self.assertTrue(key.can_sign())
        self.assertTrue(not pub.can_sign())
        self.assertEqual(key, pub)

    def test_13_sign_ecdsa(self):
        # verify that the rsa private key can sign and verify
        key = ECDSAKey.from_private_key_file(test_path('test_ecdsa.key'))
        msg = key.sign_ssh_data(b'ice weasels')
        self.assertTrue(type(msg) is Message)
        msg.rewind()
        self.assertEqual('ecdsa-sha2-nistp256', msg.get_text())
        # ECDSA signatures, like DSS signatures, tend to be different
        # each time, so we can't compare against a "known correct"
        # signature.
        # Even the length of the signature can change.

        msg.rewind()
        pub = ECDSAKey(data=key.asbytes())
        self.assertTrue(pub.verify_ssh_sig(b'ice weasels', msg))

########NEW FILE########
__FILENAME__ = test_sftp
# Copyright (C) 2003-2009  Robey Pointer <robeypointer@gmail.com>
#
# This file is part of paramiko.
#
# Paramiko is free software; you can redistribute it and/or modify it under the
# terms of the GNU Lesser General Public License as published by the Free
# Software Foundation; either version 2.1 of the License, or (at your option)
# any later version.
#
# Paramiko is distributed in the hope that it will be useful, but WITHOUT ANY
# WARRANTY; without even the implied warranty of MERCHANTABILITY or FITNESS FOR
# A PARTICULAR PURPOSE.  See the GNU Lesser General Public License for more
# details.
#
# You should have received a copy of the GNU Lesser General Public License
# along with Paramiko; if not, write to the Free Software Foundation, Inc.,
# 59 Temple Place, Suite 330, Boston, MA  02111-1307  USA.

"""
some unit tests to make sure sftp works.

a real actual sftp server is contacted, and a new folder is created there to
do test file operations in (so no existing files will be harmed).
"""

from binascii import hexlify
import os
import sys
import warnings
import threading
import unittest
from tempfile import mkstemp

import paramiko
from paramiko.py3compat import PY2, b, u, StringIO
from paramiko.common import o777, o600, o666, o644
from tests.stub_sftp import StubServer, StubSFTPServer
from tests.loop import LoopSocket
from tests.util import test_path
import paramiko.util
from paramiko.sftp_attr import SFTPAttributes

ARTICLE = '''
Insulin sensitivity and liver insulin receptor structure in ducks from two
genera

T. Constans, B. Chevalier, M. Derouet and J. Simon
Station de Recherches Avicoles, Institut National de la Recherche Agronomique,
Nouzilly, France.

Insulin sensitivity and liver insulin receptor structure were studied in
5-wk-old ducks from two genera (Muscovy and Pekin). In the fasting state, both
duck types were equally resistant to exogenous insulin compared with chicken.
Despite the low potency of duck insulin, the number of insulin receptors was
lower in Muscovy duck and similar in Pekin duck and chicken liver membranes.
After 125I-insulin cross-linking, the size of the alpha-subunit of the
receptors from the three species was 135,000. Wheat germ agglutinin-purified
receptors from the three species were contaminated by an active and unusual
adenosinetriphosphatase (ATPase) contaminant (highest activity in Muscovy
duck). Sequential purification of solubilized receptor from both duck types on
lentil and then wheat germ agglutinin lectins led to a fraction of receptors
very poor in ATPase activity that exhibited a beta-subunit size (95,000) and
tyrosine kinase activity similar to those of ATPase-free chicken insulin
receptors. Therefore the ducks from the two genera exhibit an alpha-beta-
structure for liver insulin receptors and a clear difference in the number of
liver insulin receptors. Their sensitivity to insulin is, however, similarly
decreased compared with chicken.
'''


# Here is how unicode characters are encoded over 1 to 6 bytes in utf-8
# U-00000000 - U-0000007F: 0xxxxxxx
# U-00000080 - U-000007FF: 110xxxxx 10xxxxxx
# U-00000800 - U-0000FFFF: 1110xxxx 10xxxxxx 10xxxxxx
# U-00010000 - U-001FFFFF: 11110xxx 10xxxxxx 10xxxxxx 10xxxxxx
# U-00200000 - U-03FFFFFF: 111110xx 10xxxxxx 10xxxxxx 10xxxxxx 10xxxxxx
# U-04000000 - U-7FFFFFFF: 1111110x 10xxxxxx 10xxxxxx 10xxxxxx 10xxxxxx 10xxxxxx
# Note that: hex(int('11000011',2)) == '0xc3'
# Thus, the following 2-bytes sequence is not valid utf8: "invalid continuation byte"
NON_UTF8_DATA = b'\xC3\xC3'

FOLDER = os.environ.get('TEST_FOLDER', 'temp-testing000')

sftp = None
tc = None
g_big_file_test = True
# we need to use eval(compile()) here because Py3.2 doesn't support the 'u' marker for unicode
# this test is the only line in the entire program that has to be treated specially to support Py3.2
unicode_folder = eval(compile(r"u'\u00fcnic\u00f8de'" if PY2 else r"'\u00fcnic\u00f8de'", 'test_sftp.py', 'eval'))
utf8_folder = b'/\xc3\xbcnic\xc3\xb8\x64\x65'


def get_sftp():
    global sftp
    return sftp


class SFTPTest (unittest.TestCase):

    def init(hostname, username, keyfile, passwd):
        global sftp, tc

        t = paramiko.Transport(hostname)
        tc = t
        try:
            key = paramiko.RSAKey.from_private_key_file(keyfile, passwd)
        except paramiko.PasswordRequiredException:
            sys.stderr.write('\n\nparamiko.RSAKey.from_private_key_file REQUIRES PASSWORD.\n')
            sys.stderr.write('You have two options:\n')
            sys.stderr.write('* Use the "-K" option to point to a different (non-password-protected)\n')
            sys.stderr.write('  private key file.\n')
            sys.stderr.write('* Use the "-P" option to provide the password needed to unlock this private\n')
            sys.stderr.write('  key.\n')
            sys.stderr.write('\n')
            sys.exit(1)
        try:
            t.connect(username=username, pkey=key)
        except paramiko.SSHException:
            t.close()
            sys.stderr.write('\n\nparamiko.Transport.connect FAILED.\n')
            sys.stderr.write('There are several possible reasons why it might fail so quickly:\n\n')
            sys.stderr.write('* The host to connect to (%s) is not a valid SSH server.\n' % hostname)
            sys.stderr.write('  (Use the "-H" option to change the host.)\n')
            sys.stderr.write('* The username to auth as (%s) is invalid.\n' % username)
            sys.stderr.write('  (Use the "-U" option to change the username.)\n')
            sys.stderr.write('* The private key given (%s) is not accepted by the server.\n' % keyfile)
            sys.stderr.write('  (Use the "-K" option to provide a different key file.)\n')
            sys.stderr.write('\n')
            sys.exit(1)
        sftp = paramiko.SFTP.from_transport(t)
    init = staticmethod(init)

    def init_loopback():
        global sftp, tc

        socks = LoopSocket()
        sockc = LoopSocket()
        sockc.link(socks)
        tc = paramiko.Transport(sockc)
        ts = paramiko.Transport(socks)

        host_key = paramiko.RSAKey.from_private_key_file(test_path('test_rsa.key'))
        ts.add_server_key(host_key)
        event = threading.Event()
        server = StubServer()
        ts.set_subsystem_handler('sftp', paramiko.SFTPServer, StubSFTPServer)
        ts.start_server(event, server)
        tc.connect(username='slowdive', password='pygmalion')
        event.wait(1.0)

        sftp = paramiko.SFTP.from_transport(tc)
    init_loopback = staticmethod(init_loopback)

    def set_big_file_test(onoff):
        global g_big_file_test
        g_big_file_test = onoff
    set_big_file_test = staticmethod(set_big_file_test)

    def setUp(self):
        global FOLDER
        for i in range(1000):
            FOLDER = FOLDER[:-3] + '%03d' % i
            try:
                sftp.mkdir(FOLDER)
                break
            except (IOError, OSError):
                pass

    def tearDown(self):
        #sftp.chdir()
        sftp.rmdir(FOLDER)

    def test_1_file(self):
        """
        verify that we can create a file.
        """
        f = sftp.open(FOLDER + '/test', 'w')
        try:
            self.assertEqual(f.stat().st_size, 0)
        finally:
            f.close()
            sftp.remove(FOLDER + '/test')

    def test_2_close(self):
        """
        verify that closing the sftp session doesn't do anything bad, and that
        a new one can be opened.
        """
        global sftp
        sftp.close()
        try:
            sftp.open(FOLDER + '/test2', 'w')
            self.fail('expected exception')
        except:
            pass
        sftp = paramiko.SFTP.from_transport(tc)

    def test_3_write(self):
        """
        verify that a file can be created and written, and the size is correct.
        """
        try:
            with sftp.open(FOLDER + '/duck.txt', 'w') as f:
                f.write(ARTICLE)
            self.assertEqual(sftp.stat(FOLDER + '/duck.txt').st_size, 1483)
        finally:
            sftp.remove(FOLDER + '/duck.txt')

    def test_3_sftp_file_can_be_used_as_context_manager(self):
        """
        verify that an opened file can be used as a context manager
        """
        try:
            with sftp.open(FOLDER + '/duck.txt', 'w') as f:
                f.write(ARTICLE)
            self.assertEqual(sftp.stat(FOLDER + '/duck.txt').st_size, 1483)
        finally:
            sftp.remove(FOLDER + '/duck.txt')

    def test_4_append(self):
        """
        verify that a file can be opened for append, and tell() still works.
        """
        try:
            with sftp.open(FOLDER + '/append.txt', 'w') as f:
                f.write('first line\nsecond line\n')
                self.assertEqual(f.tell(), 23)

            with sftp.open(FOLDER + '/append.txt', 'a+') as f:
                f.write('third line!!!\n')
                self.assertEqual(f.tell(), 37)
                self.assertEqual(f.stat().st_size, 37)
                f.seek(-26, f.SEEK_CUR)
                self.assertEqual(f.readline(), 'second line\n')
        finally:
            sftp.remove(FOLDER + '/append.txt')

    def test_5_rename(self):
        """
        verify that renaming a file works.
        """
        try:
            with sftp.open(FOLDER + '/first.txt', 'w') as f:
                f.write('content!\n')
            sftp.rename(FOLDER + '/first.txt', FOLDER + '/second.txt')
            try:
                sftp.open(FOLDER + '/first.txt', 'r')
                self.assertTrue(False, 'no exception on reading nonexistent file')
            except IOError:
                pass
            with sftp.open(FOLDER + '/second.txt', 'r') as f:
                f.seek(-6, f.SEEK_END)
                self.assertEqual(u(f.read(4)), 'tent')
        finally:
            try:
                sftp.remove(FOLDER + '/first.txt')
            except:
                pass
            try:
                sftp.remove(FOLDER + '/second.txt')
            except:
                pass

    def test_6_folder(self):
        """
        create a temporary folder, verify that we can create a file in it, then
        remove the folder and verify that we can't create a file in it anymore.
        """
        sftp.mkdir(FOLDER + '/subfolder')
        sftp.open(FOLDER + '/subfolder/test', 'w').close()
        sftp.remove(FOLDER + '/subfolder/test')
        sftp.rmdir(FOLDER + '/subfolder')
        try:
            sftp.open(FOLDER + '/subfolder/test')
            # shouldn't be able to create that file
            self.assertTrue(False, 'no exception at dummy file creation')
        except IOError:
            pass

    def test_7_listdir(self):
        """
        verify that a folder can be created, a bunch of files can be placed in it,
        and those files show up in sftp.listdir.
        """
        try:
            sftp.open(FOLDER + '/duck.txt', 'w').close()
            sftp.open(FOLDER + '/fish.txt', 'w').close()
            sftp.open(FOLDER + '/tertiary.py', 'w').close()

            x = sftp.listdir(FOLDER)
            self.assertEqual(len(x), 3)
            self.assertTrue('duck.txt' in x)
            self.assertTrue('fish.txt' in x)
            self.assertTrue('tertiary.py' in x)
            self.assertTrue('random' not in x)
        finally:
            sftp.remove(FOLDER + '/duck.txt')
            sftp.remove(FOLDER + '/fish.txt')
            sftp.remove(FOLDER + '/tertiary.py')

    def test_8_setstat(self):
        """
        verify that the setstat functions (chown, chmod, utime, truncate) work.
        """
        try:
            with sftp.open(FOLDER + '/special', 'w') as f:
                f.write('x' * 1024)

            stat = sftp.stat(FOLDER + '/special')
            sftp.chmod(FOLDER + '/special', (stat.st_mode & ~o777) | o600)
            stat = sftp.stat(FOLDER + '/special')
            expected_mode = o600
            if sys.platform == 'win32':
                # chmod not really functional on windows
                expected_mode = o666
            if sys.platform == 'cygwin':
                # even worse.
                expected_mode = o644
            self.assertEqual(stat.st_mode & o777, expected_mode)
            self.assertEqual(stat.st_size, 1024)

            mtime = stat.st_mtime - 3600
            atime = stat.st_atime - 1800
            sftp.utime(FOLDER + '/special', (atime, mtime))
            stat = sftp.stat(FOLDER + '/special')
            self.assertEqual(stat.st_mtime, mtime)
            if sys.platform not in ('win32', 'cygwin'):
                self.assertEqual(stat.st_atime, atime)

            # can't really test chown, since we'd have to know a valid uid.

            sftp.truncate(FOLDER + '/special', 512)
            stat = sftp.stat(FOLDER + '/special')
            self.assertEqual(stat.st_size, 512)
        finally:
            sftp.remove(FOLDER + '/special')

    def test_9_fsetstat(self):
        """
        verify that the fsetstat functions (chown, chmod, utime, truncate)
        work on open files.
        """
        try:
            with sftp.open(FOLDER + '/special', 'w') as f:
                f.write('x' * 1024)

            with sftp.open(FOLDER + '/special', 'r+') as f:
                stat = f.stat()
                f.chmod((stat.st_mode & ~o777) | o600)
                stat = f.stat()

                expected_mode = o600
                if sys.platform == 'win32':
                    # chmod not really functional on windows
                    expected_mode = o666
                if sys.platform == 'cygwin':
                    # even worse.
                    expected_mode = o644
                self.assertEqual(stat.st_mode & o777, expected_mode)
                self.assertEqual(stat.st_size, 1024)

                mtime = stat.st_mtime - 3600
                atime = stat.st_atime - 1800
                f.utime((atime, mtime))
                stat = f.stat()
                self.assertEqual(stat.st_mtime, mtime)
                if sys.platform not in ('win32', 'cygwin'):
                    self.assertEqual(stat.st_atime, atime)

                # can't really test chown, since we'd have to know a valid uid.

                f.truncate(512)
                stat = f.stat()
                self.assertEqual(stat.st_size, 512)
        finally:
            sftp.remove(FOLDER + '/special')

    def test_A_readline_seek(self):
        """
        create a text file and write a bunch of text into it.  then count the lines
        in the file, and seek around to retreive particular lines.  this should
        verify that read buffering and 'tell' work well together, and that read
        buffering is reset on 'seek'.
        """
        try:
            with sftp.open(FOLDER + '/duck.txt', 'w') as f:
                f.write(ARTICLE)

            with sftp.open(FOLDER + '/duck.txt', 'r+') as f:
                line_number = 0
                loc = 0
                pos_list = []
                for line in f:
                    line_number += 1
                    pos_list.append(loc)
                    loc = f.tell()
                f.seek(pos_list[6], f.SEEK_SET)
                self.assertEqual(f.readline(), 'Nouzilly, France.\n')
                f.seek(pos_list[17], f.SEEK_SET)
                self.assertEqual(f.readline()[:4], 'duck')
                f.seek(pos_list[10], f.SEEK_SET)
                self.assertEqual(f.readline(), 'duck types were equally resistant to exogenous insulin compared with chicken.\n')
        finally:
            sftp.remove(FOLDER + '/duck.txt')

    def test_B_write_seek(self):
        """
        create a text file, seek back and change part of it, and verify that the
        changes worked.
        """
        try:
            with sftp.open(FOLDER + '/testing.txt', 'w') as f:
                f.write('hello kitty.\n')
                f.seek(-5, f.SEEK_CUR)
                f.write('dd')

            self.assertEqual(sftp.stat(FOLDER + '/testing.txt').st_size, 13)
            with sftp.open(FOLDER + '/testing.txt', 'r') as f:
                data = f.read(20)
            self.assertEqual(data, b'hello kiddy.\n')
        finally:
            sftp.remove(FOLDER + '/testing.txt')

    def test_C_symlink(self):
        """
        create a symlink and then check that lstat doesn't follow it.
        """
        if not hasattr(os, "symlink"):
            # skip symlink tests on windows
            return

        try:
            with sftp.open(FOLDER + '/original.txt', 'w') as f:
                f.write('original\n')
            sftp.symlink('original.txt', FOLDER + '/link.txt')
            self.assertEqual(sftp.readlink(FOLDER + '/link.txt'), 'original.txt')

            with sftp.open(FOLDER + '/link.txt', 'r') as f:
                self.assertEqual(f.readlines(), ['original\n'])

            cwd = sftp.normalize('.')
            if cwd[-1] == '/':
                cwd = cwd[:-1]
            abs_path = cwd + '/' + FOLDER + '/original.txt'
            sftp.symlink(abs_path, FOLDER + '/link2.txt')
            self.assertEqual(abs_path, sftp.readlink(FOLDER + '/link2.txt'))

            self.assertEqual(sftp.lstat(FOLDER + '/link.txt').st_size, 12)
            self.assertEqual(sftp.stat(FOLDER + '/link.txt').st_size, 9)
            # the sftp server may be hiding extra path members from us, so the
            # length may be longer than we expect:
            self.assertTrue(sftp.lstat(FOLDER + '/link2.txt').st_size >= len(abs_path))
            self.assertEqual(sftp.stat(FOLDER + '/link2.txt').st_size, 9)
            self.assertEqual(sftp.stat(FOLDER + '/original.txt').st_size, 9)
        finally:
            try:
                sftp.remove(FOLDER + '/link.txt')
            except:
                pass
            try:
                sftp.remove(FOLDER + '/link2.txt')
            except:
                pass
            try:
                sftp.remove(FOLDER + '/original.txt')
            except:
                pass

    def test_D_flush_seek(self):
        """
        verify that buffered writes are automatically flushed on seek.
        """
        try:
            with sftp.open(FOLDER + '/happy.txt', 'w', 1) as f:
                f.write('full line.\n')
                f.write('partial')
                f.seek(9, f.SEEK_SET)
                f.write('?\n')

            with sftp.open(FOLDER + '/happy.txt', 'r') as f:
                self.assertEqual(f.readline(), u('full line?\n'))
                self.assertEqual(f.read(7), b'partial')
        finally:
            try:
                sftp.remove(FOLDER + '/happy.txt')
            except:
                pass

    def test_E_realpath(self):
        """
        test that realpath is returning something non-empty and not an
        error.
        """
        pwd = sftp.normalize('.')
        self.assertTrue(len(pwd) > 0)
        f = sftp.normalize('./' + FOLDER)
        self.assertTrue(len(f) > 0)
        self.assertEqual(os.path.join(pwd, FOLDER), f)

    def test_F_mkdir(self):
        """
        verify that mkdir/rmdir work.
        """
        try:
            sftp.mkdir(FOLDER + '/subfolder')
        except:
            self.assertTrue(False, 'exception creating subfolder')
        try:
            sftp.mkdir(FOLDER + '/subfolder')
            self.assertTrue(False, 'no exception overwriting subfolder')
        except IOError:
            pass
        try:
            sftp.rmdir(FOLDER + '/subfolder')
        except:
            self.assertTrue(False, 'exception removing subfolder')
        try:
            sftp.rmdir(FOLDER + '/subfolder')
            self.assertTrue(False, 'no exception removing nonexistent subfolder')
        except IOError:
            pass

    def test_G_chdir(self):
        """
        verify that chdir/getcwd work.
        """
        root = sftp.normalize('.')
        if root[-1] != '/':
            root += '/'
        try:
            sftp.mkdir(FOLDER + '/alpha')
            sftp.chdir(FOLDER + '/alpha')
            sftp.mkdir('beta')
            self.assertEqual(root + FOLDER + '/alpha', sftp.getcwd())
            self.assertEqual(['beta'], sftp.listdir('.'))

            sftp.chdir('beta')
            with sftp.open('fish', 'w') as f:
                f.write('hello\n')
            sftp.chdir('..')
            self.assertEqual(['fish'], sftp.listdir('beta'))
            sftp.chdir('..')
            self.assertEqual(['fish'], sftp.listdir('alpha/beta'))
        finally:
            sftp.chdir(root)
            try:
                sftp.unlink(FOLDER + '/alpha/beta/fish')
            except:
                pass
            try:
                sftp.rmdir(FOLDER + '/alpha/beta')
            except:
                pass
            try:
                sftp.rmdir(FOLDER + '/alpha')
            except:
                pass

    def test_H_get_put(self):
        """
        verify that get/put work.
        """
        warnings.filterwarnings('ignore', 'tempnam.*')

        fd, localname = mkstemp()
        os.close(fd)
        text = b'All I wanted was a plastic bunny rabbit.\n'
        with open(localname, 'wb') as f:
            f.write(text)
        saved_progress = []

        def progress_callback(x, y):
            saved_progress.append((x, y))
        sftp.put(localname, FOLDER + '/bunny.txt', progress_callback)

        with sftp.open(FOLDER + '/bunny.txt', 'rb') as f:
            self.assertEqual(text, f.read(128))
        self.assertEqual((41, 41), saved_progress[-1])

        os.unlink(localname)
        fd, localname = mkstemp()
        os.close(fd)
        saved_progress = []
        sftp.get(FOLDER + '/bunny.txt', localname, progress_callback)

        with open(localname, 'rb') as f:
            self.assertEqual(text, f.read(128))
        self.assertEqual((41, 41), saved_progress[-1])

        os.unlink(localname)
        sftp.unlink(FOLDER + '/bunny.txt')

    def test_I_check(self):
        """
        verify that file.check() works against our own server.
        (it's an sftp extension that we support, and may be the only ones who
        support it.)
        """
        with sftp.open(FOLDER + '/kitty.txt', 'w') as f:
            f.write('here kitty kitty' * 64)

        try:
            with sftp.open(FOLDER + '/kitty.txt', 'r') as f:
                sum = f.check('sha1')
                self.assertEqual('91059CFC6615941378D413CB5ADAF4C5EB293402', u(hexlify(sum)).upper())
                sum = f.check('md5', 0, 512)
                self.assertEqual('93DE4788FCA28D471516963A1FE3856A', u(hexlify(sum)).upper())
                sum = f.check('md5', 0, 0, 510)
                self.assertEqual('EB3B45B8CD55A0707D99B177544A319F373183D241432BB2157AB9E46358C4AC90370B5CADE5D90336FC1716F90B36D6',
                                 u(hexlify(sum)).upper())
        finally:
            sftp.unlink(FOLDER + '/kitty.txt')

    def test_J_x_flag(self):
        """
        verify that the 'x' flag works when opening a file.
        """
        sftp.open(FOLDER + '/unusual.txt', 'wx').close()

        try:
            try:
                sftp.open(FOLDER + '/unusual.txt', 'wx')
                self.fail('expected exception')
            except IOError:
                pass
        finally:
            sftp.unlink(FOLDER + '/unusual.txt')

    def test_K_utf8(self):
        """
        verify that unicode strings are encoded into utf8 correctly.
        """
        with sftp.open(FOLDER + '/something', 'w') as f:
            f.write('okay')

        try:
            sftp.rename(FOLDER + '/something', FOLDER + '/' + unicode_folder)
            sftp.open(b(FOLDER) + utf8_folder, 'r')
        except Exception as e:
            self.fail('exception ' + str(e))
        sftp.unlink(b(FOLDER) + utf8_folder)

    def test_L_utf8_chdir(self):
        sftp.mkdir(FOLDER + '/' + unicode_folder)
        try:
            sftp.chdir(FOLDER + '/' + unicode_folder)
            with sftp.open('something', 'w') as f:
                f.write('okay')
            sftp.unlink('something')
        finally:
            sftp.chdir()
            sftp.rmdir(FOLDER + '/' + unicode_folder)

    def test_M_bad_readv(self):
        """
        verify that readv at the end of the file doesn't essplode.
        """
        sftp.open(FOLDER + '/zero', 'w').close()
        try:
            with sftp.open(FOLDER + '/zero', 'r') as f:
                f.readv([(0, 12)])

            with sftp.open(FOLDER + '/zero', 'r') as f:
                f.prefetch()
                f.read(100)
        finally:
            sftp.unlink(FOLDER + '/zero')

    def test_N_put_without_confirm(self):
        """
        verify that get/put work without confirmation.
        """
        warnings.filterwarnings('ignore', 'tempnam.*')

        fd, localname = mkstemp()
        os.close(fd)
        text = b'All I wanted was a plastic bunny rabbit.\n'
        with open(localname, 'wb') as f:
            f.write(text)
        saved_progress = []

        def progress_callback(x, y):
            saved_progress.append((x, y))
        res = sftp.put(localname, FOLDER + '/bunny.txt', progress_callback, False)

        self.assertEqual(SFTPAttributes().attr, res.attr)

        with sftp.open(FOLDER + '/bunny.txt', 'r') as f:
            self.assertEqual(text, f.read(128))
        self.assertEqual((41, 41), saved_progress[-1])

        os.unlink(localname)
        sftp.unlink(FOLDER + '/bunny.txt')

    def test_O_getcwd(self):
        """
        verify that chdir/getcwd work.
        """
        self.assertEqual(None, sftp.getcwd())
        root = sftp.normalize('.')
        if root[-1] != '/':
            root += '/'
        try:
            sftp.mkdir(FOLDER + '/alpha')
            sftp.chdir(FOLDER + '/alpha')
            self.assertEqual('/' + FOLDER + '/alpha', sftp.getcwd())
        finally:
            sftp.chdir(root)
            try:
                sftp.rmdir(FOLDER + '/alpha')
            except:
                pass

    def XXX_test_M_seek_append(self):
        """
        verify that seek does't affect writes during append.

        does not work except through paramiko.  :(  openssh fails.
        """
        try:
            with sftp.open(FOLDER + '/append.txt', 'a') as f:
                f.write('first line\nsecond line\n')
                f.seek(11, f.SEEK_SET)
                f.write('third line\n')

            with sftp.open(FOLDER + '/append.txt', 'r') as f:
                self.assertEqual(f.stat().st_size, 34)
                self.assertEqual(f.readline(), 'first line\n')
                self.assertEqual(f.readline(), 'second line\n')
                self.assertEqual(f.readline(), 'third line\n')
        finally:
            sftp.remove(FOLDER + '/append.txt')

    def test_putfo_empty_file(self):
        """
        Send an empty file and confirm it is sent.
        """
        target = FOLDER + '/empty file.txt'
        stream = StringIO()
        try:
            attrs = sftp.putfo(stream, target)
            # the returned attributes should not be null
            self.assertNotEqual(attrs, None)
        finally:
            sftp.remove(target)


    def test_N_file_with_percent(self):
        """
        verify that we can create a file with a '%' in the filename.
        ( it needs to be properly escaped by _log() )
        """
        self.assertTrue( paramiko.util.get_logger("paramiko").handlers, "This unit test requires logging to be enabled" )
        f = sftp.open(FOLDER + '/test%file', 'w')
        try:
            self.assertEqual(f.stat().st_size, 0)
        finally:
            f.close()
            sftp.remove(FOLDER + '/test%file')


    def test_O_non_utf8_data(self):
        """Test write() and read() of non utf8 data"""
        try:
            with sftp.open('%s/nonutf8data' % FOLDER, 'w') as f:
                f.write(NON_UTF8_DATA)
            with sftp.open('%s/nonutf8data' % FOLDER, 'r') as f:
                data = f.read()
            self.assertEqual(data, NON_UTF8_DATA)
            with sftp.open('%s/nonutf8data' % FOLDER, 'wb') as f:
                f.write(NON_UTF8_DATA)
            with sftp.open('%s/nonutf8data' % FOLDER, 'rb') as f:
                data = f.read()
            self.assertEqual(data, NON_UTF8_DATA)
        finally:
            sftp.remove('%s/nonutf8data' % FOLDER)


if __name__ == '__main__':
    SFTPTest.init_loopback()
    # logging is required by test_N_file_with_percent
    paramiko.util.log_to_file('test_sftp.log')
    from unittest import main
    main()

########NEW FILE########
__FILENAME__ = test_sftp_big
# Copyright (C) 2003-2009  Robey Pointer <robeypointer@gmail.com>
#
# This file is part of paramiko.
#
# Paramiko is free software; you can redistribute it and/or modify it under the
# terms of the GNU Lesser General Public License as published by the Free
# Software Foundation; either version 2.1 of the License, or (at your option)
# any later version.
#
# Paramiko is distributed in the hope that it will be useful, but WITHOUT ANY
# WARRANTY; without even the implied warranty of MERCHANTABILITY or FITNESS FOR
# A PARTICULAR PURPOSE.  See the GNU Lesser General Public License for more
# details.
#
# You should have received a copy of the GNU Lesser General Public License
# along with Paramiko; if not, write to the Free Software Foundation, Inc.,
# 59 Temple Place, Suite 330, Boston, MA  02111-1307  USA.

"""
some unit tests to make sure sftp works well with large files.

a real actual sftp server is contacted, and a new folder is created there to
do test file operations in (so no existing files will be harmed).
"""

import os
import random
import struct
import sys
import time
import unittest

from paramiko.common import o660
from tests.test_sftp import get_sftp

FOLDER = os.environ.get('TEST_FOLDER', 'temp-testing000')


class BigSFTPTest (unittest.TestCase):

    def setUp(self):
        global FOLDER
        sftp = get_sftp()
        for i in range(1000):
            FOLDER = FOLDER[:-3] + '%03d' % i
            try:
                sftp.mkdir(FOLDER)
                break
            except (IOError, OSError):
                pass

    def tearDown(self):
        sftp = get_sftp()
        sftp.rmdir(FOLDER)

    def test_1_lots_of_files(self):
        """
        create a bunch of files over the same session.
        """
        sftp = get_sftp()
        numfiles = 100
        try:
            for i in range(numfiles):
                with sftp.open('%s/file%d.txt' % (FOLDER, i), 'w', 1) as f:
                    f.write('this is file #%d.\n' % i)
                sftp.chmod('%s/file%d.txt' % (FOLDER, i), o660)

            # now make sure every file is there, by creating a list of filenmes
            # and reading them in random order.
            numlist = list(range(numfiles))
            while len(numlist) > 0:
                r = numlist[random.randint(0, len(numlist) - 1)]
                with sftp.open('%s/file%d.txt' % (FOLDER, r)) as f:
                    self.assertEqual(f.readline(), 'this is file #%d.\n' % r)
                numlist.remove(r)
        finally:
            for i in range(numfiles):
                try:
                    sftp.remove('%s/file%d.txt' % (FOLDER, i))
                except:
                    pass

    def test_2_big_file(self):
        """
        write a 1MB file with no buffering.
        """
        sftp = get_sftp()
        kblob = (1024 * b'x')
        start = time.time()
        try:
            with sftp.open('%s/hongry.txt' % FOLDER, 'w') as f:
                for n in range(1024):
                    f.write(kblob)
                    if n % 128 == 0:
                        sys.stderr.write('.')
            sys.stderr.write(' ')

            self.assertEqual(sftp.stat('%s/hongry.txt' % FOLDER).st_size, 1024 * 1024)
            end = time.time()
            sys.stderr.write('%ds ' % round(end - start))
            
            start = time.time()
            with sftp.open('%s/hongry.txt' % FOLDER, 'r') as f:
                for n in range(1024):
                    data = f.read(1024)
                    self.assertEqual(data, kblob)

            end = time.time()
            sys.stderr.write('%ds ' % round(end - start))
        finally:
            sftp.remove('%s/hongry.txt' % FOLDER)

    def test_3_big_file_pipelined(self):
        """
        write a 1MB file, with no linefeeds, using pipelining.
        """
        sftp = get_sftp()
        kblob = bytes().join([struct.pack('>H', n) for n in range(512)])
        start = time.time()
        try:
            with sftp.open('%s/hongry.txt' % FOLDER, 'wb') as f:
                f.set_pipelined(True)
                for n in range(1024):
                    f.write(kblob)
                    if n % 128 == 0:
                        sys.stderr.write('.')
            sys.stderr.write(' ')

            self.assertEqual(sftp.stat('%s/hongry.txt' % FOLDER).st_size, 1024 * 1024)
            end = time.time()
            sys.stderr.write('%ds ' % round(end - start))
            
            start = time.time()
            with sftp.open('%s/hongry.txt' % FOLDER, 'rb') as f:
                f.prefetch()

                # read on odd boundaries to make sure the bytes aren't getting scrambled
                n = 0
                k2blob = kblob + kblob
                chunk = 629
                size = 1024 * 1024
                while n < size:
                    if n + chunk > size:
                        chunk = size - n
                    data = f.read(chunk)
                    offset = n % 1024
                    self.assertEqual(data, k2blob[offset:offset + chunk])
                    n += chunk

            end = time.time()
            sys.stderr.write('%ds ' % round(end - start))
        finally:
            sftp.remove('%s/hongry.txt' % FOLDER)

    def test_4_prefetch_seek(self):
        sftp = get_sftp()
        kblob = bytes().join([struct.pack('>H', n) for n in range(512)])
        try:
            with sftp.open('%s/hongry.txt' % FOLDER, 'wb') as f:
                f.set_pipelined(True)
                for n in range(1024):
                    f.write(kblob)
                    if n % 128 == 0:
                        sys.stderr.write('.')
            sys.stderr.write(' ')
            
            self.assertEqual(sftp.stat('%s/hongry.txt' % FOLDER).st_size, 1024 * 1024)
            
            start = time.time()
            k2blob = kblob + kblob
            chunk = 793
            for i in range(10):
                with sftp.open('%s/hongry.txt' % FOLDER, 'rb') as f:
                    f.prefetch()
                    base_offset = (512 * 1024) + 17 * random.randint(1000, 2000)
                    offsets = [base_offset + j * chunk for j in range(100)]
                    # randomly seek around and read them out
                    for j in range(100):
                        offset = offsets[random.randint(0, len(offsets) - 1)]
                        offsets.remove(offset)
                        f.seek(offset)
                        data = f.read(chunk)
                        n_offset = offset % 1024
                        self.assertEqual(data, k2blob[n_offset:n_offset + chunk])
                        offset += chunk
            end = time.time()
            sys.stderr.write('%ds ' % round(end - start))
        finally:
            sftp.remove('%s/hongry.txt' % FOLDER)

    def test_5_readv_seek(self):
        sftp = get_sftp()
        kblob = bytes().join([struct.pack('>H', n) for n in range(512)])
        try:
            with sftp.open('%s/hongry.txt' % FOLDER, 'wb') as f:
                f.set_pipelined(True)
                for n in range(1024):
                    f.write(kblob)
                    if n % 128 == 0:
                        sys.stderr.write('.')
            sys.stderr.write(' ')

            self.assertEqual(sftp.stat('%s/hongry.txt' % FOLDER).st_size, 1024 * 1024)

            start = time.time()
            k2blob = kblob + kblob
            chunk = 793
            for i in range(10):
                with sftp.open('%s/hongry.txt' % FOLDER, 'rb') as f:
                    base_offset = (512 * 1024) + 17 * random.randint(1000, 2000)
                    # make a bunch of offsets and put them in random order
                    offsets = [base_offset + j * chunk for j in range(100)]
                    readv_list = []
                    for j in range(100):
                        o = offsets[random.randint(0, len(offsets) - 1)]
                        offsets.remove(o)
                        readv_list.append((o, chunk))
                    ret = f.readv(readv_list)
                    for i in range(len(readv_list)):
                        offset = readv_list[i][0]
                        n_offset = offset % 1024
                        self.assertEqual(next(ret), k2blob[n_offset:n_offset + chunk])
            end = time.time()
            sys.stderr.write('%ds ' % round(end - start))
        finally:
            sftp.remove('%s/hongry.txt' % FOLDER)

    def test_6_lots_of_prefetching(self):
        """
        prefetch a 1MB file a bunch of times, discarding the file object
        without using it, to verify that paramiko doesn't get confused.
        """
        sftp = get_sftp()
        kblob = (1024 * b'x')
        try:
            with sftp.open('%s/hongry.txt' % FOLDER, 'w') as f:
                f.set_pipelined(True)
                for n in range(1024):
                    f.write(kblob)
                    if n % 128 == 0:
                        sys.stderr.write('.')
            sys.stderr.write(' ')

            self.assertEqual(sftp.stat('%s/hongry.txt' % FOLDER).st_size, 1024 * 1024)

            for i in range(10):
                with sftp.open('%s/hongry.txt' % FOLDER, 'r') as f:
                    f.prefetch()
            with sftp.open('%s/hongry.txt' % FOLDER, 'r') as f:
                f.prefetch()
                for n in range(1024):
                    data = f.read(1024)
                    self.assertEqual(data, kblob)
                    if n % 128 == 0:
                        sys.stderr.write('.')
            sys.stderr.write(' ')
        finally:
            sftp.remove('%s/hongry.txt' % FOLDER)
    
    def test_7_prefetch_readv(self):
        """
        verify that prefetch and readv don't conflict with each other.
        """
        sftp = get_sftp()
        kblob = bytes().join([struct.pack('>H', n) for n in range(512)])
        try:
            with sftp.open('%s/hongry.txt' % FOLDER, 'wb') as f:
                f.set_pipelined(True)
                for n in range(1024):
                    f.write(kblob)
                    if n % 128 == 0:
                        sys.stderr.write('.')
            sys.stderr.write(' ')
            
            self.assertEqual(sftp.stat('%s/hongry.txt' % FOLDER).st_size, 1024 * 1024)

            with sftp.open('%s/hongry.txt' % FOLDER, 'rb') as f:
                f.prefetch()
                data = f.read(1024)
                self.assertEqual(data, kblob)

                chunk_size = 793
                base_offset = 512 * 1024
                k2blob = kblob + kblob
                chunks = [(base_offset + (chunk_size * i), chunk_size) for i in range(20)]
                for data in f.readv(chunks):
                    offset = base_offset % 1024
                    self.assertEqual(chunk_size, len(data))
                    self.assertEqual(k2blob[offset:offset + chunk_size], data)
                    base_offset += chunk_size

            sys.stderr.write(' ')
        finally:
            sftp.remove('%s/hongry.txt' % FOLDER)
    
    def test_8_large_readv(self):
        """
        verify that a very large readv is broken up correctly and still
        returned as a single blob.
        """
        sftp = get_sftp()
        kblob = bytes().join([struct.pack('>H', n) for n in range(512)])
        try:
            with sftp.open('%s/hongry.txt' % FOLDER, 'wb') as f:
                f.set_pipelined(True)
                for n in range(1024):
                    f.write(kblob)
                    if n % 128 == 0:
                        sys.stderr.write('.')
            sys.stderr.write(' ')

            self.assertEqual(sftp.stat('%s/hongry.txt' % FOLDER).st_size, 1024 * 1024)
            
            with sftp.open('%s/hongry.txt' % FOLDER, 'rb') as f:
                data = list(f.readv([(23 * 1024, 128 * 1024)]))
                self.assertEqual(1, len(data))
                data = data[0]
                self.assertEqual(128 * 1024, len(data))
            
            sys.stderr.write(' ')
        finally:
            sftp.remove('%s/hongry.txt' % FOLDER)
    
    def test_9_big_file_big_buffer(self):
        """
        write a 1MB file, with no linefeeds, and a big buffer.
        """
        sftp = get_sftp()
        mblob = (1024 * 1024 * 'x')
        try:
            with sftp.open('%s/hongry.txt' % FOLDER, 'w', 128 * 1024) as f:
                f.write(mblob)

            self.assertEqual(sftp.stat('%s/hongry.txt' % FOLDER).st_size, 1024 * 1024)
        finally:
            sftp.remove('%s/hongry.txt' % FOLDER)
    
    def test_A_big_file_renegotiate(self):
        """
        write a 1MB file, forcing key renegotiation in the middle.
        """
        sftp = get_sftp()
        t = sftp.sock.get_transport()
        t.packetizer.REKEY_BYTES = 512 * 1024
        k32blob = (32 * 1024 * 'x')
        try:
            with sftp.open('%s/hongry.txt' % FOLDER, 'w', 128 * 1024) as f:
                for i in range(32):
                    f.write(k32blob)

            self.assertEqual(sftp.stat('%s/hongry.txt' % FOLDER).st_size, 1024 * 1024)
            self.assertNotEqual(t.H, t.session_id)
            
            # try to read it too.
            with sftp.open('%s/hongry.txt' % FOLDER, 'r', 128 * 1024) as f:
                f.prefetch()
                total = 0
                while total < 1024 * 1024:
                    total += len(f.read(32 * 1024))
        finally:
            sftp.remove('%s/hongry.txt' % FOLDER)
            t.packetizer.REKEY_BYTES = pow(2, 30)


if __name__ == '__main__':
    from tests.test_sftp import SFTPTest
    SFTPTest.init_loopback()
    from unittest import main
    main()

########NEW FILE########
__FILENAME__ = test_transport
# Copyright (C) 2003-2009  Robey Pointer <robeypointer@gmail.com>
#
# This file is part of paramiko.
#
# Paramiko is free software; you can redistribute it and/or modify it under the
# terms of the GNU Lesser General Public License as published by the Free
# Software Foundation; either version 2.1 of the License, or (at your option)
# any later version.
#
# Paramiko is distributed in the hope that it will be useful, but WITHOUT ANY
# WARRANTY; without even the implied warranty of MERCHANTABILITY or FITNESS FOR
# A PARTICULAR PURPOSE.  See the GNU Lesser General Public License for more
# details.
#
# You should have received a copy of the GNU Lesser General Public License
# along with Paramiko; if not, write to the Free Software Foundation, Inc.,
# 59 Temple Place, Suite 330, Boston, MA  02111-1307  USA.

"""
Some unit tests for the ssh2 protocol in Transport.
"""

from binascii import hexlify
import select
import socket
import time
import threading
import random

from paramiko import Transport, SecurityOptions, ServerInterface, RSAKey, DSSKey, \
    SSHException, ChannelException
from paramiko import AUTH_FAILED, AUTH_SUCCESSFUL
from paramiko import OPEN_SUCCEEDED, OPEN_FAILED_ADMINISTRATIVELY_PROHIBITED
from paramiko.common import MSG_KEXINIT, cMSG_CHANNEL_WINDOW_ADJUST
from paramiko.py3compat import bytes
from paramiko.message import Message
from tests.loop import LoopSocket
from tests.util import ParamikoTest, test_path


LONG_BANNER = """\
Welcome to the super-fun-land BBS, where our MOTD is the primary thing we
provide. All rights reserved. Offer void in Tennessee. Stunt drivers were
used. Do not attempt at home. Some restrictions apply.

Happy birthday to Commie the cat!

Note: An SSH banner may eventually appear.

Maybe.
"""


class NullServer (ServerInterface):
    paranoid_did_password = False
    paranoid_did_public_key = False
    paranoid_key = DSSKey.from_private_key_file(test_path('test_dss.key'))
    
    def get_allowed_auths(self, username):
        if username == 'slowdive':
            return 'publickey,password'
        return 'publickey'

    def check_auth_password(self, username, password):
        if (username == 'slowdive') and (password == 'pygmalion'):
            return AUTH_SUCCESSFUL
        return AUTH_FAILED

    def check_channel_request(self, kind, chanid):
        if kind == 'bogus':
            return OPEN_FAILED_ADMINISTRATIVELY_PROHIBITED
        return OPEN_SUCCEEDED

    def check_channel_exec_request(self, channel, command):
        if command != 'yes':
            return False
        return True

    def check_channel_shell_request(self, channel):
        return True
    
    def check_global_request(self, kind, msg):
        self._global_request = kind
        return False
    
    def check_channel_x11_request(self, channel, single_connection, auth_protocol, auth_cookie, screen_number):
        self._x11_single_connection = single_connection
        self._x11_auth_protocol = auth_protocol
        self._x11_auth_cookie = auth_cookie
        self._x11_screen_number = screen_number
        return True
    
    def check_port_forward_request(self, addr, port):
        self._listen = socket.socket()
        self._listen.bind(('127.0.0.1', 0))
        self._listen.listen(1)
        return self._listen.getsockname()[1]
    
    def cancel_port_forward_request(self, addr, port):
        self._listen.close()
        self._listen = None

    def check_channel_direct_tcpip_request(self, chanid, origin, destination):
        self._tcpip_dest = destination
        return OPEN_SUCCEEDED


class TransportTest(ParamikoTest):
    def setUp(self):
        self.socks = LoopSocket()
        self.sockc = LoopSocket()
        self.sockc.link(self.socks)
        self.tc = Transport(self.sockc)
        self.ts = Transport(self.socks)

    def tearDown(self):
        self.tc.close()
        self.ts.close()
        self.socks.close()
        self.sockc.close()

    def setup_test_server(self, client_options=None, server_options=None):
        host_key = RSAKey.from_private_key_file(test_path('test_rsa.key'))
        public_host_key = RSAKey(data=host_key.asbytes())
        self.ts.add_server_key(host_key)
        
        if client_options is not None:
            client_options(self.tc.get_security_options())
        if server_options is not None:
            server_options(self.ts.get_security_options())
        
        event = threading.Event()
        self.server = NullServer()
        self.assertTrue(not event.isSet())
        self.ts.start_server(event, self.server)
        self.tc.connect(hostkey=public_host_key,
                        username='slowdive', password='pygmalion')
        event.wait(1.0)
        self.assertTrue(event.isSet())
        self.assertTrue(self.ts.is_active())

    def test_1_security_options(self):
        o = self.tc.get_security_options()
        self.assertEqual(type(o), SecurityOptions)
        self.assertTrue(('aes256-cbc', 'blowfish-cbc') != o.ciphers)
        o.ciphers = ('aes256-cbc', 'blowfish-cbc')
        self.assertEqual(('aes256-cbc', 'blowfish-cbc'), o.ciphers)
        try:
            o.ciphers = ('aes256-cbc', 'made-up-cipher')
            self.assertTrue(False)
        except ValueError:
            pass
        try:
            o.ciphers = 23
            self.assertTrue(False)
        except TypeError:
            pass
            
    def test_2_compute_key(self):
        self.tc.K = 123281095979686581523377256114209720774539068973101330872763622971399429481072519713536292772709507296759612401802191955568143056534122385270077606457721553469730659233569339356140085284052436697480759510519672848743794433460113118986816826624865291116513647975790797391795651716378444844877749505443714557929
        self.tc.H = b'\x0C\x83\x07\xCD\xE6\x85\x6F\xF3\x0B\xA9\x36\x84\xEB\x0F\x04\xC2\x52\x0E\x9E\xD3'
        self.tc.session_id = self.tc.H
        key = self.tc._compute_key('C', 32)
        self.assertEqual(b'207E66594CA87C44ECCBA3B3CD39FDDB378E6FDB0F97C54B2AA0CFBF900CD995',
                          hexlify(key).upper())

    def test_3_simple(self):
        """
        verify that we can establish an ssh link with ourselves across the
        loopback sockets.  this is hardly "simple" but it's simpler than the
        later tests. :)
        """
        host_key = RSAKey.from_private_key_file(test_path('test_rsa.key'))
        public_host_key = RSAKey(data=host_key.asbytes())
        self.ts.add_server_key(host_key)
        event = threading.Event()
        server = NullServer()
        self.assertTrue(not event.isSet())
        self.assertEqual(None, self.tc.get_username())
        self.assertEqual(None, self.ts.get_username())
        self.assertEqual(False, self.tc.is_authenticated())
        self.assertEqual(False, self.ts.is_authenticated())
        self.ts.start_server(event, server)
        self.tc.connect(hostkey=public_host_key,
                        username='slowdive', password='pygmalion')
        event.wait(1.0)
        self.assertTrue(event.isSet())
        self.assertTrue(self.ts.is_active())
        self.assertEqual('slowdive', self.tc.get_username())
        self.assertEqual('slowdive', self.ts.get_username())
        self.assertEqual(True, self.tc.is_authenticated())
        self.assertEqual(True, self.ts.is_authenticated())

    def test_3a_long_banner(self):
        """
        verify that a long banner doesn't mess up the handshake.
        """
        host_key = RSAKey.from_private_key_file(test_path('test_rsa.key'))
        public_host_key = RSAKey(data=host_key.asbytes())
        self.ts.add_server_key(host_key)
        event = threading.Event()
        server = NullServer()
        self.assertTrue(not event.isSet())
        self.socks.send(LONG_BANNER)
        self.ts.start_server(event, server)
        self.tc.connect(hostkey=public_host_key,
                        username='slowdive', password='pygmalion')
        event.wait(1.0)
        self.assertTrue(event.isSet())
        self.assertTrue(self.ts.is_active())
        
    def test_4_special(self):
        """
        verify that the client can demand odd handshake settings, and can
        renegotiate keys in mid-stream.
        """
        def force_algorithms(options):
            options.ciphers = ('aes256-cbc',)
            options.digests = ('hmac-md5-96',)
        self.setup_test_server(client_options=force_algorithms)
        self.assertEqual('aes256-cbc', self.tc.local_cipher)
        self.assertEqual('aes256-cbc', self.tc.remote_cipher)
        self.assertEqual(12, self.tc.packetizer.get_mac_size_out())
        self.assertEqual(12, self.tc.packetizer.get_mac_size_in())
        
        self.tc.send_ignore(1024)
        self.tc.renegotiate_keys()
        self.ts.send_ignore(1024)

    def test_5_keepalive(self):
        """
        verify that the keepalive will be sent.
        """
        self.setup_test_server()
        self.assertEqual(None, getattr(self.server, '_global_request', None))
        self.tc.set_keepalive(1)
        time.sleep(2)
        self.assertEqual('keepalive@lag.net', self.server._global_request)
        
    def test_6_exec_command(self):
        """
        verify that exec_command() does something reasonable.
        """
        self.setup_test_server()

        chan = self.tc.open_session()
        schan = self.ts.accept(1.0)
        try:
            chan.exec_command('no')
            self.assertTrue(False)
        except SSHException:
            pass
        
        chan = self.tc.open_session()
        chan.exec_command('yes')
        schan = self.ts.accept(1.0)
        schan.send('Hello there.\n')
        schan.send_stderr('This is on stderr.\n')
        schan.close()

        f = chan.makefile()
        self.assertEqual('Hello there.\n', f.readline())
        self.assertEqual('', f.readline())
        f = chan.makefile_stderr()
        self.assertEqual('This is on stderr.\n', f.readline())
        self.assertEqual('', f.readline())
        
        # now try it with combined stdout/stderr
        chan = self.tc.open_session()
        chan.exec_command('yes')
        schan = self.ts.accept(1.0)
        schan.send('Hello there.\n')
        schan.send_stderr('This is on stderr.\n')
        schan.close()

        chan.set_combine_stderr(True)        
        f = chan.makefile()
        self.assertEqual('Hello there.\n', f.readline())
        self.assertEqual('This is on stderr.\n', f.readline())
        self.assertEqual('', f.readline())

    def test_7_invoke_shell(self):
        """
        verify that invoke_shell() does something reasonable.
        """
        self.setup_test_server()
        chan = self.tc.open_session()
        chan.invoke_shell()
        schan = self.ts.accept(1.0)
        chan.send('communist j. cat\n')
        f = schan.makefile()
        self.assertEqual('communist j. cat\n', f.readline())
        chan.close()
        self.assertEqual('', f.readline())

    def test_8_channel_exception(self):
        """
        verify that ChannelException is thrown for a bad open-channel request.
        """
        self.setup_test_server()
        try:
            chan = self.tc.open_channel('bogus')
            self.fail('expected exception')
        except ChannelException as e:
            self.assertTrue(e.code == OPEN_FAILED_ADMINISTRATIVELY_PROHIBITED)

    def test_9_exit_status(self):
        """
        verify that get_exit_status() works.
        """
        self.setup_test_server()

        chan = self.tc.open_session()
        schan = self.ts.accept(1.0)
        chan.exec_command('yes')
        schan.send('Hello there.\n')
        self.assertTrue(not chan.exit_status_ready())
        # trigger an EOF
        schan.shutdown_read()
        schan.shutdown_write()
        schan.send_exit_status(23)
        schan.close()
        
        f = chan.makefile()
        self.assertEqual('Hello there.\n', f.readline())
        self.assertEqual('', f.readline())
        count = 0
        while not chan.exit_status_ready():
            time.sleep(0.1)
            count += 1
            if count > 50:
                raise Exception("timeout")
        self.assertEqual(23, chan.recv_exit_status())
        chan.close()

    def test_A_select(self):
        """
        verify that select() on a channel works.
        """
        self.setup_test_server()
        chan = self.tc.open_session()
        chan.invoke_shell()
        schan = self.ts.accept(1.0)

        # nothing should be ready        
        r, w, e = select.select([chan], [], [], 0.1)
        self.assertEqual([], r)
        self.assertEqual([], w)
        self.assertEqual([], e)
        
        schan.send('hello\n')
        
        # something should be ready now (give it 1 second to appear)
        for i in range(10):
            r, w, e = select.select([chan], [], [], 0.1)
            if chan in r:
                break
            time.sleep(0.1)
        self.assertEqual([chan], r)
        self.assertEqual([], w)
        self.assertEqual([], e)

        self.assertEqual(b'hello\n', chan.recv(6))
        
        # and, should be dead again now
        r, w, e = select.select([chan], [], [], 0.1)
        self.assertEqual([], r)
        self.assertEqual([], w)
        self.assertEqual([], e)

        schan.close()
        
        # detect eof?
        for i in range(10):
            r, w, e = select.select([chan], [], [], 0.1)
            if chan in r:
                break
            time.sleep(0.1)
        self.assertEqual([chan], r)
        self.assertEqual([], w)
        self.assertEqual([], e)
        self.assertEqual(bytes(), chan.recv(16))
        
        # make sure the pipe is still open for now...
        p = chan._pipe
        self.assertEqual(False, p._closed)
        chan.close()
        # ...and now is closed.
        self.assertEqual(True, p._closed)
   
    def test_B_renegotiate(self):
        """
        verify that a transport can correctly renegotiate mid-stream.
        """
        self.setup_test_server()
        self.tc.packetizer.REKEY_BYTES = 16384
        chan = self.tc.open_session()
        chan.exec_command('yes')
        schan = self.ts.accept(1.0)

        self.assertEqual(self.tc.H, self.tc.session_id)
        for i in range(20):
            chan.send('x' * 1024)
        chan.close()
        
        # allow a few seconds for the rekeying to complete
        for i in range(50):
            if self.tc.H != self.tc.session_id:
                break
            time.sleep(0.1)
        self.assertNotEqual(self.tc.H, self.tc.session_id)

        schan.close()

    def test_C_compression(self):
        """
        verify that zlib compression is basically working.
        """
        def force_compression(o):
            o.compression = ('zlib',)
        self.setup_test_server(force_compression, force_compression)
        chan = self.tc.open_session()
        chan.exec_command('yes')
        schan = self.ts.accept(1.0)

        bytes = self.tc.packetizer._Packetizer__sent_bytes
        chan.send('x' * 1024)
        bytes2 = self.tc.packetizer._Packetizer__sent_bytes
        # tests show this is actually compressed to *52 bytes*!  including packet overhead!  nice!! :)
        self.assertTrue(bytes2 - bytes < 1024)
        self.assertEqual(52, bytes2 - bytes)

        chan.close()
        schan.close()

    def test_D_x11(self):
        """
        verify that an x11 port can be requested and opened.
        """
        self.setup_test_server()
        chan = self.tc.open_session()
        chan.exec_command('yes')
        schan = self.ts.accept(1.0)
        
        requested = []
        def handler(c, addr_port):
            addr, port = addr_port
            requested.append((addr, port))
            self.tc._queue_incoming_channel(c)
            
        self.assertEqual(None, getattr(self.server, '_x11_screen_number', None))
        cookie = chan.request_x11(0, single_connection=True, handler=handler)
        self.assertEqual(0, self.server._x11_screen_number)
        self.assertEqual('MIT-MAGIC-COOKIE-1', self.server._x11_auth_protocol)
        self.assertEqual(cookie, self.server._x11_auth_cookie)
        self.assertEqual(True, self.server._x11_single_connection)
        
        x11_server = self.ts.open_x11_channel(('localhost', 6093))
        x11_client = self.tc.accept()
        self.assertEqual('localhost', requested[0][0])
        self.assertEqual(6093, requested[0][1])
        
        x11_server.send('hello')
        self.assertEqual(b'hello', x11_client.recv(5))
        
        x11_server.close()
        x11_client.close()
        chan.close()
        schan.close()

    def test_E_reverse_port_forwarding(self):
        """
        verify that a client can ask the server to open a reverse port for
        forwarding.
        """
        self.setup_test_server()
        chan = self.tc.open_session()
        chan.exec_command('yes')
        schan = self.ts.accept(1.0)
        
        requested = []
        def handler(c, origin_addr_port, server_addr_port):
            requested.append(origin_addr_port)
            requested.append(server_addr_port)
            self.tc._queue_incoming_channel(c)
            
        port = self.tc.request_port_forward('127.0.0.1', 0, handler)
        self.assertEqual(port, self.server._listen.getsockname()[1])

        cs = socket.socket()
        cs.connect(('127.0.0.1', port))
        ss, _ = self.server._listen.accept()
        sch = self.ts.open_forwarded_tcpip_channel(ss.getsockname(), ss.getpeername())
        cch = self.tc.accept()
        
        sch.send('hello')
        self.assertEqual(b'hello', cch.recv(5))
        sch.close()
        cch.close()
        ss.close()
        cs.close()
        
        # now cancel it.
        self.tc.cancel_port_forward('127.0.0.1', port)
        self.assertTrue(self.server._listen is None)

    def test_F_port_forwarding(self):
        """
        verify that a client can forward new connections from a locally-
        forwarded port.
        """
        self.setup_test_server()
        chan = self.tc.open_session()
        chan.exec_command('yes')
        schan = self.ts.accept(1.0)
        
        # open a port on the "server" that the client will ask to forward to.
        greeting_server = socket.socket()
        greeting_server.bind(('127.0.0.1', 0))
        greeting_server.listen(1)
        greeting_port = greeting_server.getsockname()[1]

        cs = self.tc.open_channel('direct-tcpip', ('127.0.0.1', greeting_port), ('', 9000))
        sch = self.ts.accept(1.0)
        cch = socket.socket()
        cch.connect(self.server._tcpip_dest)
        
        ss, _ = greeting_server.accept()
        ss.send(b'Hello!\n')
        ss.close()
        sch.send(cch.recv(8192))
        sch.close()
        
        self.assertEqual(b'Hello!\n', cs.recv(7))
        cs.close()

    def test_G_stderr_select(self):
        """
        verify that select() on a channel works even if only stderr is
        receiving data.
        """
        self.setup_test_server()
        chan = self.tc.open_session()
        chan.invoke_shell()
        schan = self.ts.accept(1.0)

        # nothing should be ready        
        r, w, e = select.select([chan], [], [], 0.1)
        self.assertEqual([], r)
        self.assertEqual([], w)
        self.assertEqual([], e)
        
        schan.send_stderr('hello\n')
        
        # something should be ready now (give it 1 second to appear)
        for i in range(10):
            r, w, e = select.select([chan], [], [], 0.1)
            if chan in r:
                break
            time.sleep(0.1)
        self.assertEqual([chan], r)
        self.assertEqual([], w)
        self.assertEqual([], e)

        self.assertEqual(b'hello\n', chan.recv_stderr(6))
        
        # and, should be dead again now
        r, w, e = select.select([chan], [], [], 0.1)
        self.assertEqual([], r)
        self.assertEqual([], w)
        self.assertEqual([], e)

        schan.close()
        chan.close()

    def test_H_send_ready(self):
        """
        verify that send_ready() indicates when a send would not block.
        """
        self.setup_test_server()
        chan = self.tc.open_session()
        chan.invoke_shell()
        schan = self.ts.accept(1.0)

        self.assertEqual(chan.send_ready(), True)
        total = 0
        K = '*' * 1024
        while total < 1024 * 1024:
            chan.send(K)
            total += len(K)
            if not chan.send_ready():
                break
        self.assertTrue(total < 1024 * 1024)

        schan.close()
        chan.close()
        self.assertEqual(chan.send_ready(), True)

    def test_I_rekey_deadlock(self):
        """
        Regression test for deadlock when in-transit messages are received after MSG_KEXINIT is sent
        
        Note: When this test fails, it may leak threads.
        """
        
        # Test for an obscure deadlocking bug that can occur if we receive
        # certain messages while initiating a key exchange.
        #
        # The deadlock occurs as follows:
        #
        # In the main thread:
        #   1. The user's program calls Channel.send(), which sends
        #      MSG_CHANNEL_DATA to the remote host.
        #   2. Packetizer discovers that REKEY_BYTES has been exceeded, and
        #      sets the __need_rekey flag.
        #
        # In the Transport thread:
        #   3. Packetizer notices that the __need_rekey flag is set, and raises
        #      NeedRekeyException.
        #   4. In response to NeedRekeyException, the transport thread sends
        #      MSG_KEXINIT to the remote host.
        # 
        # On the remote host (using any SSH implementation):
        #   5. The MSG_CHANNEL_DATA is received, and MSG_CHANNEL_WINDOW_ADJUST is sent.
        #   6. The MSG_KEXINIT is received, and a corresponding MSG_KEXINIT is sent.
        #
        # In the main thread:
        #   7. The user's program calls Channel.send().
        #   8. Channel.send acquires Channel.lock, then calls Transport._send_user_message().
        #   9. Transport._send_user_message waits for Transport.clear_to_send
        #      to be set (i.e., it waits for re-keying to complete).
        #      Channel.lock is still held.
        #
        # In the Transport thread:
        #   10. MSG_CHANNEL_WINDOW_ADJUST is received; Channel._window_adjust
        #       is called to handle it.
        #   11. Channel._window_adjust tries to acquire Channel.lock, but it
        #       blocks because the lock is already held by the main thread.
        #
        # The result is that the Transport thread never processes the remote
        # host's MSG_KEXINIT packet, because it becomes deadlocked while
        # handling the preceding MSG_CHANNEL_WINDOW_ADJUST message.

        # We set up two separate threads for sending and receiving packets,
        # while the main thread acts as a watchdog timer.  If the timer
        # expires, a deadlock is assumed.

        class SendThread(threading.Thread):
            def __init__(self, chan, iterations, done_event):
                threading.Thread.__init__(self, None, None, self.__class__.__name__)
                self.setDaemon(True)
                self.chan = chan
                self.iterations = iterations
                self.done_event = done_event
                self.watchdog_event = threading.Event()
                self.last = None
            
            def run(self):
                try:
                    for i in range(1, 1+self.iterations):
                        if self.done_event.isSet():
                            break
                        self.watchdog_event.set()
                        #print i, "SEND"
                        self.chan.send("x" * 2048)
                finally:
                    self.done_event.set()
                    self.watchdog_event.set()
        
        class ReceiveThread(threading.Thread):
            def __init__(self, chan, done_event):
                threading.Thread.__init__(self, None, None, self.__class__.__name__)
                self.setDaemon(True)
                self.chan = chan
                self.done_event = done_event
                self.watchdog_event = threading.Event()
            
            def run(self):
                try:
                    while not self.done_event.isSet():
                        if self.chan.recv_ready():
                            chan.recv(65536)
                            self.watchdog_event.set()
                        else:
                            if random.randint(0, 1):
                                time.sleep(random.randint(0, 500) / 1000.0)
                finally:
                    self.done_event.set()
                    self.watchdog_event.set()
        
        self.setup_test_server()
        self.ts.packetizer.REKEY_BYTES = 2048
        
        chan = self.tc.open_session()
        chan.exec_command('yes')
        schan = self.ts.accept(1.0)

        # Monkey patch the client's Transport._handler_table so that the client
        # sends MSG_CHANNEL_WINDOW_ADJUST whenever it receives an initial
        # MSG_KEXINIT.  This is used to simulate the effect of network latency
        # on a real MSG_CHANNEL_WINDOW_ADJUST message.
        self.tc._handler_table = self.tc._handler_table.copy()  # copy per-class dictionary
        _negotiate_keys = self.tc._handler_table[MSG_KEXINIT]
        def _negotiate_keys_wrapper(self, m):
            if self.local_kex_init is None: # Remote side sent KEXINIT
                # Simulate in-transit MSG_CHANNEL_WINDOW_ADJUST by sending it
                # before responding to the incoming MSG_KEXINIT.
                m2 = Message()
                m2.add_byte(cMSG_CHANNEL_WINDOW_ADJUST)
                m2.add_int(chan.remote_chanid)
                m2.add_int(1)    # bytes to add
                self._send_message(m2)
            return _negotiate_keys(self, m)
        self.tc._handler_table[MSG_KEXINIT] = _negotiate_keys_wrapper
        
        # Parameters for the test
        iterations = 500    # The deadlock does not happen every time, but it
                            # should after many iterations.
        timeout = 5

        # This event is set when the test is completed
        done_event = threading.Event()

        # Start the sending thread
        st = SendThread(schan, iterations, done_event)
        st.start()
        
        # Start the receiving thread
        rt = ReceiveThread(chan, done_event)
        rt.start()

        # Act as a watchdog timer, checking 
        deadlocked = False
        while not deadlocked and not done_event.isSet():
            for event in (st.watchdog_event, rt.watchdog_event):
                event.wait(timeout)
                if done_event.isSet():
                    break
                if not event.isSet():
                    deadlocked = True
                    break
                event.clear()
        
        # Tell the threads to stop (if they haven't already stopped).  Note
        # that if one or more threads are deadlocked, they might hang around
        # forever (until the process exits).
        done_event.set()

        # Assertion: We must not have detected a timeout.
        self.assertFalse(deadlocked)

        # Close the channels
        schan.close()
        chan.close()

########NEW FILE########
__FILENAME__ = test_util
# Copyright (C) 2003-2009  Robey Pointer <robeypointer@gmail.com>
#
# This file is part of paramiko.
#
# Paramiko is free software; you can redistribute it and/or modify it under the
# terms of the GNU Lesser General Public License as published by the Free
# Software Foundation; either version 2.1 of the License, or (at your option)
# any later version.
#
# Paramiko is distributed in the hope that it will be useful, but WITHOUT ANY
# WARRANTY; without even the implied warranty of MERCHANTABILITY or FITNESS FOR
# A PARTICULAR PURPOSE.  See the GNU Lesser General Public License for more
# details.
#
# You should have received a copy of the GNU Lesser General Public License
# along with Paramiko; if not, write to the Free Software Foundation, Inc.,
# 59 Temple Place, Suite 330, Boston, MA  02111-1307  USA.

"""
Some unit tests for utility functions.
"""

from binascii import hexlify
import errno
import os
from hashlib import sha1

import paramiko.util
from paramiko.util import lookup_ssh_host_config as host_config
from paramiko.py3compat import StringIO, byte_ord

from tests.util import ParamikoTest

test_config_file = """\
Host *
    User robey
    IdentityFile    =~/.ssh/id_rsa

# comment
Host *.example.com
    \tUser bjork
Port=3333
Host *
 \t  \t Crazy something dumb  
Host spoo.example.com
Crazy something else
"""

test_hosts_file = """\
secure.example.com ssh-rsa AAAAB3NzaC1yc2EAAAABIwAAAIEA1PD6U2/TVxET6lkpKhOk5r\
9q/kAYG6sP9f5zuUYP8i7FOFp/6ncCEbbtg/lB+A3iidyxoSWl+9jtoyyDOOVX4UIDV9G11Ml8om3\
D+jrpI9cycZHqilK0HmxDeCuxbwyMuaCygU9gS2qoRvNLWZk70OpIKSSpBo0Wl3/XUmz9uhc=
happy.example.com ssh-rsa AAAAB3NzaC1yc2EAAAABIwAAAIEA8bP1ZA7DCZDB9J0s50l31M\
BGQ3GQ/Fc7SX6gkpXkwcZryoi4kNFhHu5LvHcZPdxXV1D+uTMfGS1eyd2Yz/DoNWXNAl8TI0cAsW\
5ymME3bQ4J/k1IKxCtz/bAlAqFgKoc+EolMziDYqWIATtW0rYTJvzGAzTmMj80/QpsFH+Pc2M=
"""


# for test 1:
from paramiko import *


class UtilTest(ParamikoTest):
    def test_1_import(self):
        """
        verify that all the classes can be imported from paramiko.
        """
        symbols = list(globals().keys())
        self.assertTrue('Transport' in symbols)
        self.assertTrue('SSHClient' in symbols)
        self.assertTrue('MissingHostKeyPolicy' in symbols)
        self.assertTrue('AutoAddPolicy' in symbols)
        self.assertTrue('RejectPolicy' in symbols)
        self.assertTrue('WarningPolicy' in symbols)
        self.assertTrue('SecurityOptions' in symbols)
        self.assertTrue('SubsystemHandler' in symbols)
        self.assertTrue('Channel' in symbols)
        self.assertTrue('RSAKey' in symbols)
        self.assertTrue('DSSKey' in symbols)
        self.assertTrue('Message' in symbols)
        self.assertTrue('SSHException' in symbols)
        self.assertTrue('AuthenticationException' in symbols)
        self.assertTrue('PasswordRequiredException' in symbols)
        self.assertTrue('BadAuthenticationType' in symbols)
        self.assertTrue('ChannelException' in symbols)
        self.assertTrue('SFTP' in symbols)
        self.assertTrue('SFTPFile' in symbols)
        self.assertTrue('SFTPHandle' in symbols)
        self.assertTrue('SFTPClient' in symbols)
        self.assertTrue('SFTPServer' in symbols)
        self.assertTrue('SFTPError' in symbols)
        self.assertTrue('SFTPAttributes' in symbols)
        self.assertTrue('SFTPServerInterface' in symbols)
        self.assertTrue('ServerInterface' in symbols)
        self.assertTrue('BufferedFile' in symbols)
        self.assertTrue('Agent' in symbols)
        self.assertTrue('AgentKey' in symbols)
        self.assertTrue('HostKeys' in symbols)
        self.assertTrue('SSHConfig' in symbols)
        self.assertTrue('util' in symbols)

    def test_2_parse_config(self):
        global test_config_file
        f = StringIO(test_config_file)
        config = paramiko.util.parse_ssh_config(f)
        self.assertEqual(config._config,
            [{'host': ['*'], 'config': {}}, {'host': ['*'], 'config': {'identityfile': ['~/.ssh/id_rsa'], 'user': 'robey'}},
            {'host': ['*.example.com'], 'config': {'user': 'bjork', 'port': '3333'}},
            {'host': ['*'], 'config': {'crazy': 'something dumb  '}},
            {'host': ['spoo.example.com'], 'config': {'crazy': 'something else'}}])

    def test_3_host_config(self):
        global test_config_file
        f = StringIO(test_config_file)
        config = paramiko.util.parse_ssh_config(f)

        for host, values in {
            'irc.danger.com':   {'crazy': 'something dumb  ',
                                'hostname': 'irc.danger.com',
                                'user': 'robey'},
            'irc.example.com':  {'crazy': 'something dumb  ',
                                'hostname': 'irc.example.com',
                                'user': 'robey',
                                'port': '3333'},
            'spoo.example.com': {'crazy': 'something dumb  ',
                                'hostname': 'spoo.example.com',
                                'user': 'robey',
                                'port': '3333'}
        }.items():
            values = dict(values,
                hostname=host,
                identityfile=[os.path.expanduser("~/.ssh/id_rsa")]
            )
            self.assertEqual(
                paramiko.util.lookup_ssh_host_config(host, config),
                values
            )

    def test_4_generate_key_bytes(self):
        x = paramiko.util.generate_key_bytes(sha1, b'ABCDEFGH', 'This is my secret passphrase.', 64)
        hex = ''.join(['%02x' % byte_ord(c) for c in x])
        self.assertEqual(hex, '9110e2f6793b69363e58173e9436b13a5a4b339005741d5c680e505f57d871347b4239f14fb5c46e857d5e100424873ba849ac699cea98d729e57b3e84378e8b')

    def test_5_host_keys(self):
        with open('hostfile.temp', 'w') as f:
            f.write(test_hosts_file)
        try:
            hostdict = paramiko.util.load_host_keys('hostfile.temp')
            self.assertEqual(2, len(hostdict))
            self.assertEqual(1, len(list(hostdict.values())[0]))
            self.assertEqual(1, len(list(hostdict.values())[1]))
            fp = hexlify(hostdict['secure.example.com']['ssh-rsa'].get_fingerprint()).upper()
            self.assertEqual(b'E6684DB30E109B67B70FF1DC5C7F1363', fp)
        finally:
            os.unlink('hostfile.temp')

    def test_7_host_config_expose_issue_33(self):
        test_config_file = """
Host www13.*
    Port 22

Host *.example.com
    Port 2222

Host *
    Port 3333
    """
        f = StringIO(test_config_file)
        config = paramiko.util.parse_ssh_config(f)
        host = 'www13.example.com'
        self.assertEqual(
            paramiko.util.lookup_ssh_host_config(host, config),
            {'hostname': host, 'port': '22'}
        )

    def test_8_eintr_retry(self):
        self.assertEqual('foo', paramiko.util.retry_on_signal(lambda: 'foo'))

        # Variables that are set by raises_intr
        intr_errors_remaining = [3]
        call_count = [0]
        def raises_intr():
            call_count[0] += 1
            if intr_errors_remaining[0] > 0:
                intr_errors_remaining[0] -= 1
                raise IOError(errno.EINTR, 'file', 'interrupted system call')
        self.assertTrue(paramiko.util.retry_on_signal(raises_intr) is None)
        self.assertEqual(0, intr_errors_remaining[0])
        self.assertEqual(4, call_count[0])

        def raises_ioerror_not_eintr():
            raise IOError(errno.ENOENT, 'file', 'file not found')
        self.assertRaises(IOError,
                          lambda: paramiko.util.retry_on_signal(raises_ioerror_not_eintr))

        def raises_other_exception():
            raise AssertionError('foo')
        self.assertRaises(AssertionError,
                          lambda: paramiko.util.retry_on_signal(raises_other_exception))

    def test_9_proxycommand_config_equals_parsing(self):
        """
        ProxyCommand should not split on equals signs within the value.
        """
        conf = """
Host space-delimited
    ProxyCommand foo bar=biz baz

Host equals-delimited
    ProxyCommand=foo bar=biz baz
"""
        f = StringIO(conf)
        config = paramiko.util.parse_ssh_config(f)
        for host in ('space-delimited', 'equals-delimited'):
            self.assertEqual(
                host_config(host, config)['proxycommand'],
                'foo bar=biz baz'
            )

    def test_10_proxycommand_interpolation(self):
        """
        ProxyCommand should perform interpolation on the value
        """
        config = paramiko.util.parse_ssh_config(StringIO("""
Host specific
    Port 37
    ProxyCommand host %h port %p lol

Host portonly
    Port 155

Host *
    Port 25
    ProxyCommand host %h port %p
"""))
        for host, val in (
            ('foo.com', "host foo.com port 25"),
            ('specific', "host specific port 37 lol"),
            ('portonly', "host portonly port 155"),
        ):
            self.assertEqual(
                host_config(host, config)['proxycommand'],
                val
            )

    def test_11_host_config_test_negation(self):
        test_config_file = """
Host www13.* !*.example.com
    Port 22

Host *.example.com !www13.*
    Port 2222

Host www13.*
    Port 8080

Host *
    Port 3333
    """
        f = StringIO(test_config_file)
        config = paramiko.util.parse_ssh_config(f)
        host = 'www13.example.com'
        self.assertEqual(
            paramiko.util.lookup_ssh_host_config(host, config),
            {'hostname': host, 'port': '8080'}
        )

    def test_12_host_config_test_proxycommand(self):
        test_config_file = """
Host proxy-with-equal-divisor-and-space
ProxyCommand = foo=bar

Host proxy-with-equal-divisor-and-no-space
ProxyCommand=foo=bar

Host proxy-without-equal-divisor
ProxyCommand foo=bar:%h-%p
    """
        for host, values in {
            'proxy-with-equal-divisor-and-space'   :{'hostname': 'proxy-with-equal-divisor-and-space',
                                                     'proxycommand': 'foo=bar'},
            'proxy-with-equal-divisor-and-no-space':{'hostname': 'proxy-with-equal-divisor-and-no-space',
                                                     'proxycommand': 'foo=bar'},
            'proxy-without-equal-divisor'          :{'hostname': 'proxy-without-equal-divisor',
                                                     'proxycommand':
                                                     'foo=bar:proxy-without-equal-divisor-22'}
        }.items():

            f = StringIO(test_config_file)
            config = paramiko.util.parse_ssh_config(f)
            self.assertEqual(
                paramiko.util.lookup_ssh_host_config(host, config),
                values
            )

    def test_11_host_config_test_identityfile(self):
        test_config_file = """

IdentityFile id_dsa0

Host *
IdentityFile id_dsa1

Host dsa2
IdentityFile id_dsa2

Host dsa2*
IdentityFile id_dsa22
    """
        for host, values in {
            'foo'   :{'hostname': 'foo',
                      'identityfile': ['id_dsa0', 'id_dsa1']},
            'dsa2'  :{'hostname': 'dsa2',
                      'identityfile': ['id_dsa0', 'id_dsa1', 'id_dsa2', 'id_dsa22']},
            'dsa22' :{'hostname': 'dsa22',
                      'identityfile': ['id_dsa0', 'id_dsa1', 'id_dsa22']}
        }.items():

            f = StringIO(test_config_file)
            config = paramiko.util.parse_ssh_config(f)
            self.assertEqual(
                paramiko.util.lookup_ssh_host_config(host, config),
                values
            )

    def test_12_config_addressfamily_and_lazy_fqdn(self):
        """
        Ensure the code path honoring non-'all' AddressFamily doesn't asplode
        """
        test_config = """
AddressFamily inet
IdentityFile something_%l_using_fqdn
"""
        config = paramiko.util.parse_ssh_config(StringIO(test_config))
        assert config.lookup('meh')  # will die during lookup() if bug regresses

########NEW FILE########
__FILENAME__ = util
import os
import unittest

root_path = os.path.dirname(os.path.realpath(__file__))


class ParamikoTest(unittest.TestCase):
    # for Python 2.3 and below
    if not hasattr(unittest.TestCase, 'assertTrue'):
        assertTrue = unittest.TestCase.failUnless
    if not hasattr(unittest.TestCase, 'assertFalse'):
        assertFalse = unittest.TestCase.failIf


def test_path(filename):
    return os.path.join(root_path, filename)


########NEW FILE########