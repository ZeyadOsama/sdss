import datetime
import socket
import struct
import threading
import time
import uuid

# https://bluesock.org/~willkg/dev/ansi.html
ANSI_RESET = "\u001B[0m"
ANSI_RED = "\u001B[31m"
ANSI_GREEN = "\u001B[32m"
ANSI_YELLOW = "\u001B[33m"
ANSI_BLUE = "\u001B[34m"

_NODE_UUID = str(uuid.uuid4())[:8]


class Constants:
    MAX_RECV = 4096
    DECODE = 'utf-8'


def print_yellow(msg):
    print(f"{ANSI_YELLOW}{msg}{ANSI_RESET}")


def print_blue(msg):
    print(f"{ANSI_BLUE}{msg}{ANSI_RESET}")


def print_red(msg):
    print(f"{ANSI_RED}{msg}{ANSI_RESET}")


def print_green(msg):
    print(f"{ANSI_GREEN}{msg}{ANSI_RESET}")


def get_broadcast_port():
    return 35498


def get_node_uuid():
    return _NODE_UUID


class NeighborInfo(object):
    def __init__(self, delay, last_timestamp, ip=None, tcp_port=None):
        # Ip and port are optional, if you want to store them.
        self.delay = delay
        self.last_timestamp = last_timestamp
        self.ip = ip
        self.tcp_port = tcp_port


############################################
#######  Y  O  U  R     C  O  D  E  ########
############################################


# Don't change any variable's name.
# Use this hashmap to store the information of your neighbor nodes.
neighbor_information = {}

# Leave the server socket as global variable.
server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
server.bind(("", 0))
server.listen(20)

# Leave broadcaster as a global variable.
broadcaster = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)

# Setup the UDP socket
broadcaster.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)
broadcaster.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEPORT, 1)
broadcaster.bind(("", get_broadcast_port()))


def send_broadcast_thread():
    broadcast_msg, broadcast_addr = get_broadcast()
    while True:
        broadcaster.sendto(broadcast_msg, broadcast_addr)
        time.sleep(1)
    pass


def receive_broadcast_thread():
    """
    Receive broadcasts from other nodes,
    launches a thread to connect to new nodes
    and exchange timestamps.
    """
    while True:
        data, (ip, port) = broadcaster.recvfrom(Constants.MAX_RECV)
        print_blue(f'RECV: {data} FROM: {ip}:{port}')
        node_id, tcp_port = parse_data(data)

        if node_id == get_node_uuid():
            continue
        if node_id in neighbor_information:
            neighbor_information[node_id].last_timestamp = neighbor_information[node_id].last_timestamp + 1
            if neighbor_information[node_id].last_timestamp != 10:
                continue
            else:
                neighbor_information[node_id].last_timestamp = 0

        th_exchange = daemon_thread_builder(exchange_timestamps_thread, args=(node_id, ip, tcp_port))
        th_exchange.start()
    pass


def tcp_server_thread():
    """
    Accept connections from other nodes and send them
    this node's timestamp once they connect.
    """
    while True:
        s_client, addr = server.accept()
        s_client.send(get_utc())
        s_client.close()
    pass


def exchange_timestamps_thread(other_uuid: str, other_ip: str, other_tcp_port: int):
    """
    Open a connection to the other_ip, other_tcp_port
    and do the steps to exchange timestamps.
    Then update the neighbor_info map using other node's UUID.
    """
    print_yellow(f"ATTEMPTING TO CONNECT TO {other_uuid}")

    utc = datetime.datetime.utcnow()
    utc_numeric = utc.timestamp()
    b_utc = struct.pack("!d", utc_numeric)

    s_time = socket.socket(socket.AF_INET, socket.SOCK_STREAM)

    try:
        s_time.connect((other_ip, other_tcp_port))
    except ConnectionRefusedError:
        raise Exception(f'[ERROR] ConnectionRefusedError')

    s_time.sendall(b_utc)

    t = s_time.recv(Constants.MAX_RECV)
    time_unpacked = struct.unpack('!d', t)[0]

    delay = time_unpacked - utc_numeric
    delay = delay * 1000
    delay = round(delay, 3)
    print_green(delay)
    neighbor_information[other_uuid] = NeighborInfo(delay, 0)
    return


def parse_data(data: bytes):
    return extract_node_id(data), extract_tcp_port(data)


def extract_node_id(data: bytes):
    node_id = struct.unpack('8s', data[:8])
    node_id = str(node_id[0], Constants.DECODE)
    return node_id


def extract_tcp_port(data: bytes):
    port_len = len(data[12:])
    tcp_port = struct.unpack(str(port_len) + 's', data[12:])
    tcp_port = int(str(tcp_port[0], Constants.DECODE))
    return tcp_port


def get_broadcast():
    node_uuid = get_node_uuid()
    tcp_port = server.getsockname()[1]
    msg = node_uuid + ' ON ' + str(tcp_port)
    broadcast_msg = msg.encode(Constants.DECODE)
    broadcast_addr = ('<broadcast>', get_broadcast_port())
    return broadcast_msg, broadcast_addr


def get_utc() -> bytes:
    utc = datetime.datetime.utcnow()
    b_utc = utc.timestamp()
    b_utc = struct.pack('!d', b_utc)
    return b_utc


def daemon_thread_builder(target, args=()) -> threading.Thread:
    """
    Use this function to make threads. Leave as is.
    """
    th = threading.Thread(target=target, args=args)
    th.setDaemon(True)
    return th


def entrypoint():
    threading.Lock()

    th_tcp_server = daemon_thread_builder(tcp_server_thread)
    th_tcp_server.start()

    th_broadcast_recv = daemon_thread_builder(receive_broadcast_thread)
    th_broadcast_recv.start()

    th_broadcast_send = daemon_thread_builder(send_broadcast_thread)
    th_broadcast_send.start()

    th_broadcast_recv.join()
    th_broadcast_send.join()
    th_tcp_server.join()

    return


############################################
############################################


def main():
    """
    Leave as is.
    """
    print("*" * 50)
    print_red("To terminate this program use: CTRL+C")
    print_red("If the program blocks/throws, you have to terminate it manually.")
    print_green(f"NODE UUID: {get_node_uuid()}")
    print("*" * 50)
    time.sleep(2)  # Wait a little bit.
    entrypoint()


if __name__ == "__main__":
    main()
