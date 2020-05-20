import fakeredis
from services.origin_service import Service
import threading
from socket import socket, timeout, AF_INET, SOCK_STREAM, SHUT_RDWR


class RedisServer(object):
    def __init__(self, socket, logger, name, port):
        self.socket = socket
        self.logger = logger
        self.command = ['get', 'set', 'config', 'quit', 'ping', 'del', "save"]
        self.name = name
        self.port = port
        self.r = fakeredis.FakeStrictRedis()

    def data_received(self, rcvdata):
        command = rcvdata
        position = command.find('\n')
        if position == 0:
            pass
        else:
            data = command.split()
            msg = None
            self.logger.info("received command: %s" % str(command))
            if data[0] in self.command:
                if data[0].lower() == "quit":
                    self.socket.shutdown(SHUT_RDWR)
                    self.socket.close()
                elif data[0].lower() == "ping":
                    msg = b"+PONG\n"
                    self.logger.info("send message: %s" % msg)
                    self.socket.send(msg)
                elif data[0].lower() == "save" or data[0].lower() == "flushall" or data[0].lower() == "flushdb":
                    msg = b"+OK\n"
                    self.logger.info("send message: %s" % msg)
                    self.socket.send(msg)
                else:
                    if command.lower().startswith('config get') and len(data) == 3:
                        msg = "-(error) ERR Unsupported CONFIG parameter: {0}\n".format(data[2]).encode('utf-8')
                        self.logger.info("send message: %s" % msg)
                        self.socket.send(msg)
                    elif command.lower().startswith('config set') and len(data) == 4:
                        msg = "-(error) ERR Unsupported CONFIG parameter: {0}".format(data[2]).encode('utf-8')
                        self.logger.info("send message: %s\n" % msg)
                        self.socket.send(msg)
                    elif data[0].lower() == "set" and len(data) == 3:
                        if self.r.set(data[1], data[2]):
                            msg = b"+OK\n"
                            self.logger.info("send message: %s" % msg)
                            self.socket.send(msg)
                    elif data[0].lower().startswith('del') and len(data) == 2:
                        if self.r.delete(data[1]):
                            msg = b"+(integer) 1\n"
                            self.logger.info("send message: %s" % msg)
                            self.socket.send(msg)
                        else:
                            msg = b"+(integer) 0\n"
                            self.logger.info("send message: %s" % msg)
                            self.socket.send(msg)
                    elif data[0].lower() == 'get' and len(data) == 2:
                        if self.r.get(data[1]):
                            s = self.r.get(data[1])
                            msg = "+{0}\n".format(s).encode('utf-8')
                            self.logger.info("send message: %s" % msg)
                            self.socket.send(msg)
                        else:
                            msg = b"+(nil)\n"
                            self.logger.info("send message: %s" % msg)
                            self.socket.send(msg)
                    else:
                        msg = "-ERR wrong number of arguments for '{0}' command\n".format(data[0]).encode('utf-8')
                        self.logger.info("send message: %s" % msg)
                        self.socket.send(msg)
            else:
                msg = "-ERR unknown command '{0}'\n".format(data[0]).encode('utf-8')
                self.logger.info("send message: %s" % msg)
                self.socket.send(msg)


def handle_connection(client_socket, logger, name, port):
    manager = RedisServer(client_socket, logger, name, port)
    while True:
        msg = "redis 127.0.0.1:" + str(port) + " > "
        client_socket.send(msg.encode())
        rcvdata = str(client_socket.recv(1024), "utf-8")
        if rcvdata == "quit":
            client_socket.shutdown(SHUT_RDWR)
            client_socket.close()
            break
        manager.data_received(rcvdata)


class Redis(Service):
    def __init__(self, bind_ip, ports, log_filepath, name):
        super().__init__(bind_ip, ports, log_filepath, name)
        self.service_start()

    def service_start(self):
        print(self.name, "started on port", self.ports)
        self.start_listen()

    def start_listen(self):
        listener = socket(AF_INET, SOCK_STREAM)
        listener.bind((self.bind_ip, int(self.ports)))
        listener.listen(5)
        while True:
            client, addr = listener.accept()
            self.connection_response(client, self.ports, addr[0], addr[1])
            client_handler = threading.Thread(target=self.connection_response,
                                              args=(client, self.ports, addr[0], addr[1]))
            client_handler.start()

    def connection_response(self, client_socket, port, ip, remote_port):
        self.logger.info("Connection received to service %s:%d  %s:%d" % (self.name, port, ip, remote_port))
        client_socket.settimeout(30)
        try:
            handle_connection(client_socket, self.logger, self.name, self.ports)
        except timeout:
            print('timeout, terminating...')
            pass
        except KeyboardInterrupt:
            print('Detected interruption, terminating...')
            client_socket.close()
        except Exception as e:
            pass
        client_socket.close()
