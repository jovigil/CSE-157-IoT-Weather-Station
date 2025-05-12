import socket
import random
# First send request to pi 1 for readings
# Wait for response

# Send request to pi 2 for readings
# Wait for response

# Get its own sensor readings
# Plot the readings

# Repeat

import asyncio
import datetime
import logging
import board
import busio
import time
import simpleio
# i2c = busio.I2C(board.SCL, board.SDA)

# import adafruit_ads1x15.ads1015 as ADS

# from adafruit_ads1x15.analog_in import AnalogIn


# import adafruit_sht31d

# # Create sensor object, communicating over the board's default I2C bus
# # i2c = board.STEMMA_I2C()  # For using the built-in STEMMA QT connector on a microcontroller
# temp_sensor = adafruit_sht31d.SHT31D(i2c)


# from adafruit_seesaw.seesaw import Seesaw

# ss = Seesaw(i2c, addr=0x36)

# ads = ADS.ADS1015(i2c)
# chan = AnalogIn(ads, ADS.P0)


# Setting up our default logging format.
logging.basicConfig(format='[%(asctime)s] (%(name)s) %(levelname)s: %(message)s',)
# Set up loggers for each of our concurrent functions.
logger_server = logging.getLogger('Server_logger')
logger_client = logging.getLogger('Client_logger')

# Set the logging level for each of our concurrent functions to INFO.
logger_server.setLevel(logging.INFO)
logger_client.setLevel(logging.INFO)


# We will set up a common file handler for all of our loggers, and set it to INFO.
file_handler = logging.FileHandler('primary.log')
file_handler.setLevel(logging.INFO)
# Add the file handler to each of our loggers.
logger_server.addHandler(file_handler)
logger_client.addHandler(file_handler)





HOST = "127.0.0.1"  # Standard loopback interface address (localhost)
PORT = 65429  # Port to listen on (non-privileged ports are > 1023)



used_ports = set()
s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
s.settimeout(1)
s.bind((HOST, PORT))
async def server():
    global used_ports
    global s
    while True:
        s.listen()
        try:
            conn, addr = s.accept()
            data = conn.recv(1024)
            logger_server.info(f"Received {data!r} from {addr}")

            #generate port number
            port = random.randint(1024, 65535)
            while port in used_ports:
                port = random.randint(1024, 65535)
            used_ports.add(port)
            conn.sendall(port.to_bytes(2, byteorder='big'))
            conn.close()
            time.sleep(0.5) #let client set up there server on new port
        except socket.timeout:
            pass
        await asyncio.sleep(1)




async def get_pi_readings():
    global c
    global used_ports
    round_number = 0
    while True:
        for PORT in list(used_ports):
            c = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            c.settimeout(2)
            try:
                c.connect((HOST, PORT))
                c.sendall(b"Requesting data")
                data = c.recv(1024)
                logger_client.info(f"Received {int.from_bytes(data, byteorder='big')!r}")
                c.close()
            except (socket.timeout, ConnectionRefusedError) as e:
                logger_client.info(f"Error: {e}, on port {PORT}")
                c.close()
                used_ports.remove(PORT)
        if used_ports:
            round_number += 1
            print(f"Round {round_number} complete     plotting data...")
        await asyncio.sleep(1)


async def main():
    """ 
    The main coroutine
    """
    await asyncio.gather(
            server(),
            get_pi_readings()
    )

if __name__ == "__main__":
    # We will use a try/except block to catch the KeyboardInterrupt.
    try:
        """
        Once we have defined our main coroutine, we will run it using asyncio.run().
        """
        asyncio.run(main())
    except KeyboardInterrupt:
        """
        If the user presses Ctrl+C, we will gracefully exit the program.
        """
        print("Exiting program...")
        c.close()
        s.close()
        exit(0)
