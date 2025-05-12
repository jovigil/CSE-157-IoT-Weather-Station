import socket
import time
# Wait for request from primary pi
# Send data 

# Repeat


HOST = "127.0.0.1"  # Standard loopback interface address (localhost)
PORT = 65429  # Port to listen on (non-privileged ports are > 1023)


def get_port_assigned():
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)

    s.connect((HOST, PORT))

    s.sendall(b"Hello, world")
    UPORT = int.from_bytes(s.recv(1024), byteorder='big')
    print(f"Received port number {UPORT}")
    s.close()
    return UPORT


s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
UPORT = get_port_assigned()
s.bind((HOST, UPORT))
s.listen()
s.settimeout(5)
i = 0
while True:
    i += 1
    try:
        conn, addr = s.accept()
        with conn:
            data = conn.recv(1024)
            print(f"Received {data!r} from {addr}")
            if i == 5:
                time.sleep(5)
            conn.sendall(b"150")
    except (socket.timeout, ConnectionResetError, BrokenPipeError, OSError) as e:
        print(f"Error: {e}, getting a new port")
        UPORT = get_port_assigned()
        s.close()
        s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        s.bind((HOST, UPORT))
        s.listen()
        s.settimeout(3)




