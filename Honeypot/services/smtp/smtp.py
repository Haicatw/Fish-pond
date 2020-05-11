import sys
sys.path.append('..')
import asyncore
import smtpd
from services.origin_service import Service
from smtpd import SMTPServer, DebuggingServer
import asynchat


class SMTPChannel(smtpd.SMTPChannel):
    __version__ = '220 ESMTP Postfix (Debian/GNU)'
    version = 0

    def __init__(self, server, conn, addr, data_size_limit, map, utf8, decode_data, logger):
        self.logger = logger
        super().__init__(server, conn, addr, data_size_limit, map, utf8, decode_data)

    def push(self, msg):
        if self.version == 0:
            asynchat.async_chat.push(self, bytes(
                self.__version__ + '\r\n', 'utf-8' if self.require_SMTPUTF8 else 'ascii'))
            self.version = 1
        else:
            self.logger.info("send message: %s" % msg)
            asynchat.async_chat.push(self, bytes(
                msg + '\r\n', 'utf-8' if self.require_SMTPUTF8 else 'ascii'))

    def found_terminator(self):
        self.logger.info("received command: %s" % self.received_lines[0])
        smtpd.SMTPChannel.found_terminator(self)


class fakeServer(DebuggingServer):
    channel_class = SMTPChannel

    def __init__(self, localaddr, remoteaddr, logger, port):
        super().__init__(localaddr, remoteaddr)
        self.logger = logger
        self.port = port

    def handle_accepted(self, conn, addr):
        self.logger.info("Connection received to service %s:%d  %s:%d" % ("smtp", self.port, addr[0], addr[1]))
        channel = self.channel_class(self, conn, addr, self.data_size_limit, self._map, self.enable_SMTPUTF8,
                                     self._decode_data, self.logger)


class SMTP(Service):
    def __init__(self, bind_ip, ports, log_filepath, name):
        super().__init__(bind_ip, ports, log_filepath, name)
        self.service_start()

    def service_start(self):
        print(self.name, "started on port", self.ports)
        self.start_listen()

    def start_listen(self):
        smtp = fakeServer((self.bind_ip, self.ports), None, self.logger, self.ports)
        try:
            asyncore.loop()
        except KeyboardInterrupt:
            print('Detected interruption, terminating...')