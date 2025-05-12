import socket
import threading
import time
import sys

# Configuration for each Pi
CONFIG = {
    1: {"listen_port": 65517, "next_ip": "192.168.1.2", "next_port": 6552},
    2: {"listen_port": 5442, "next_ip": "192.168.1.3", "next_port": 65517},
    3: {"listen_port": 65517, "next_ip": "192.168.1.17", "next_port": 6},
}

pi_id = int(sys.argv[1])
my_config = CONFIG[pi_id]


def handle_connection():
    """Listen for incoming message and forward it."""
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as server:
        server.bind(('', my_config["listen_port"]))
        server.listen(1)
        while True:
            conn, addr = server.accept()
            with conn:
                data = conn.recv(1024).decode()
                print(f"Received: {data}")
                if pi_id == 3:
                    if data == "token":
                        print("plot goes here")
                        send_token("token")
                else:
                    if data == "token":
                        time.sleep(1)  
                        send_token("token")


def send_token(msg):
    """Send a token to the next Pi."""
    while True:
        try:
            with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
                s.connect((my_config["next_ip"], my_config["next_port"]))
                s.sendall(msg.encode())
                print(f"Sent: {msg} to {my_config['next_ip']}")
                break
        except ConnectionRefusedError:
            print("Connection refused, retrying...")
            time.sleep(1)


def start():
    threading.Thread(target=handle_connection, daemon=True).start()

    # Pi #1 starts the communication
    if pi_id == 1:
        time.sleep(5)  # Wait for others to be ready
        send_token("token")

    # Keep the main thread alive
    while True:
        time.sleep(1)


if __name__ == "__main__":
    start(
