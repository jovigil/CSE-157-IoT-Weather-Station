import socket
import random
import asyncio
import datetime
import logging
import board
import busio
import time
import simpleio
import matplotlib.pyplot as plt
import numpy as np
import json


logging.basicConfig(format='[%(asctime)s] (%(name)s) %(levelname)s: %(message)s',)
logger_server = logging.getLogger('Server_logger')
logger_client = logging.getLogger('Client_logger')

logger_server.setLevel(logging.INFO)
logger_client.setLevel(logging.INFO)


file_handler = logging.FileHandler('primary.log')
file_handler.setLevel(logging.INFO)
logger_server.addHandler(file_handler)
logger_client.addHandler(file_handler)


HOST = "169.233.1.17" 
PORT = 65421  # Port to listen on 


CLIENTS = set()
s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
s.settimeout(1)
s.bind((HOST, PORT))

async def server():
    global CLIENTS
    global s
    while True:
        s.listen()
        try:
            conn, addr = s.accept()
            CLIENTS.add(addr[0])
            data = conn.recv(1024)
            logger_server.info(f"Received {data!r} from {addr}")

            # #generate port number
            # port = random.randint(1024, 65535)
            # while port in used_ports:
            #     port = random.randint(1024, 65535)
            # used_ports.add(port)
            conn.sendall(b'Recieved connection')
            conn.close()
            time.sleep(0.5) #let client set up there server on new port
        except socket.timeout:
            pass
        await asyncio.sleep(1)




async def get_pi_readings():
    global c
    global CLIENTS
    global PORT
    round_number = 0
    while True:
        for CLIENT in list(CLIENTS):
            c = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            c.settimeout(2)
            try:
                print(CLIENT)
                c.connect((CLIENT, PORT))
                c.sendall(b"Requesting data")
                sensor_data = c.recv(2048)
                print(sensor_data)
                plot_data(sensor_data)
                c.close()
            except (socket.timeout, ConnectionRefusedError) as e:
                logger_client.info(f"Error: {e}, on port {PORT}")
                c.close()
                CLIENTS.remove(CLIENT)
        if CLIENTS:
            #I think here we might need to also plot the sensor data of the primary pi
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

def plot_data(sensor_data_str):
    """
    Plot Pi #2's sensor data using matplotlib
    """
    data = json.loads(sensor_data_str)
    temp = data["temperature"]
    hum = data["humidity"]
    soil_temp = data["soil_temp"]
    soil_moist = data["soil_moist"]
    wind_speed = data["wind_speed"]
    
    x_temp = np.linspace(0, 35)
    x_hum = np.linspace(0,100)
    x_soil_temp = np.linspace(0, 35)
    x_soil_moist = np.linspace(0, 2000)
    x_wind_speed = np.linspace(0, 20)
    
#     fig, axs = plt.subplots(5,1)
#     fig.suptitle(f"Raspberry Pi Sensor Data")
#     axs[0].plot(x_temp, temp)
#     axs[0].set_title("Temperature")
#     axs[1].plot(x_hum, hum)
#     axs[1].set_title("Humidity")
#     axs[2].plot(x_soil_temp, soil_temp)
#     axs[2].set_title("Soil Temperature")
#     axs[3].plot(x_soil_moist, soil_moist)
#     axs[3].set_title("Soil Moisture")
#     axs[4].plot(x_wind_speed, wind_speed)
#     axs[4].set_title("Wind Speed")
    
    
    

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
