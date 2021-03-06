import sys
import os
from pathlib import Path
from datetime import datetime
from socket import socket, timeout
from pyftpdlib.authorizers import DummyAuthorizer
from pyftpdlib.handlers import FTPHandler
from pyftpdlib.servers import FTPServer
from Honeypot.services import origin_service

sys.path.append('..')


class FakeAuthorizer(DummyAuthorizer):
    def __init__(self, logger, logs, ip):
        super().__init__()
        self.user_table = {}
        self.logger = logger
        self.ip = ip
        self.logs = logs

    def add_user(self, username, password, homedir, perm='',
                 msg_login="Login successful.", msg_quit="Goodbye."):
        if self.has_user(username):
            raise ValueError('user %r already exists' % username)
        if not os.path.isdir(homedir):
            raise ValueError('no such directory: %r' % homedir)
        homedir = os.path.realpath(homedir)
        self._check_permissions(username, perm)
        dic = {'pwd': str(password),
               'home': homedir,
               'perm': perm,
               'operms': {},
               'msg_login': str(msg_login),
               'msg_quit': str(msg_quit)
               }
        self.user_table[username] = dic

    def validate_authentication(self, username, password, handler):
        """Raises AuthenticationFailed if supplied username and
        password don't match the stored credentials, else return
        None.
        """
        self.add_user(username,password,'.')
        now = datetime.now()
        info = {"time": now, "service": "ftp", "type": "login", "ip": self.ip, "username": username,
                "password": password, "command": ""}
        self.logs.put(info)
        self.logger.info("New login -  - username:" + username + " - - " + "password:" + password)

    def get_home_dir(self, username):
        """Return the user's home directory.
        Since this is called during authentication (PASS),
        AuthenticationFailed can be freely raised by subclasses in case
        the provided username no longer exists.
        """
        return "."

    def impersonate_user(self, username, password):
        """Impersonate another user (noop).
        It is always called before accessing the filesystem.
        By default it does nothing.  The subclass overriding this
        method is expected to provide a mechanism to change the
        current user.
        """

    def terminate_impersonation(self, username):
        """Terminate impersonation (noop).
        It is always called after having accessed the filesystem.
        By default it does nothing.  The subclass overriding this
        method is expected to provide a mechanism to switch back
        to the original user.
        """

    def get_msg_login(self, username):
        """Return the user's login message."""
        return self.user_table[username]['msg_login']

    def get_msg_quit(self, username):
        """Return the user's quitting message."""
        try:
            return self.user_table[username]['msg_quit']
        except KeyError:
            return "Goodbye."


# to do: 
# revise the FTPhandler so that it log the commend the user enters
# chromn anonylums login 
# change banner
# restrain permission
# 
class FTP(origin_service.Service):
    def __init__(self, bind_ip, ports, log_filepath, name, logs):
        super().__init__(bind_ip, ports, log_filepath, name, logs)
        self.service_start()

    def service_start(self):
        print(self.name, "started on port", self.ports)
        self.start_listen()

    def start_listen(self):
        # authorizer = DummyAuthorizer()
        try:
            authorizer = FakeAuthorizer(self.logger, self.logs, self.bind_ip)
            handler = FTPHandler
            handler.banner = "FTP service is ready"
            handler.authorizer = authorizer
            address = (self.bind_ip, self.ports)
            server = FTPServer(address, handler)
            handler.timeout = 600
            server.max_cons = 256
            server.max_cons_per_ip = 5
            server.serve_forever()
        except timeout:
            pass
        except OSError:
            print("service", self.name, "find ports", self.ports, "already in used, please check again")
            print("close service", self.name)
            exit()
        except KeyboardInterrupt:
            print('Detected interruption, terminating...')
        except Exception as e:
            print(e)
            pass
