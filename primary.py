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


sensor_data = {
    "temperature":[],
    "humidity":[],
    "soil_temp":[],
    "soil_moist":[],
    "wind_speed":[]
}

def compile_sensor_data(data_):
    data = json.loads(data_)
    for key in sensor_data:
        sensor_data[key].append(data[key])

logging.basicConfig(format='[%(asctime)s] (%(name)s) %(levelname)s: %(message)s',)
logger_server = logging.getLogger('Server_logger')
logger_client = logging.getLogger('Client_logger')

logger_server.setLevel(logging.INFO)
logger_client.setLevel(logging.INFO)


file_handler = logging.FileHandler('primary.log')
file_handler.setLevel(logging.INFO)
logger_server.addHandler(file_handler)
logger_client.addHandler(file_handler)


HOST = "169.233.1.9" 
PORT = 65404  # Port to listen on 


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
                data = c.recv(2048)
                print(data)
                compile_sensor_data(data)
                c.close()
            except (socket.timeout, ConnectionRefusedError) as e:
                logger_client.info(f"Error: {e}, on port {PORT}")
                c.close()
                CLIENTS.remove(CLIENT)
        if CLIENTS:
            #I think here we might need to also plot the sensor data of the primary pi
            if len(CLIENTS) >= 2:
                round_number += 1
                plot_data(round_number)
                print(f"Round {round_number} complete     plotting data...")
            for entry in sensor_data.values():
                entry.clear()
        await asyncio.sleep(1)


async def main():
    """ 
    The main coroutine
    """
    await asyncio.gather(
            server(),
            get_pi_readings()
    )

def plot_data(round_number):
    """
    Plot sensor data using matplotlib
    """
    for key in sensor_data:
        sensor_data[key].append(5)

    print(sensor_data)
    data = sensor_data #json.loads(sensor_data)
    temps = data["temperature"]
    hums = data["humidity"]
    soil_moists = data["soil_moist"]
    wind_speeds = data["wind_speed"]
    print(("wind speed data: ", data["wind_speed"]))
    graphs = [temps, hums,
              soil_moists, wind_speeds]
    x_vals = np.array(["Sec1", "Sec2", "Primary", "Avg"]) #1 is sec1, 2 is sec2,
                                     #3 is primary and 4 is avg val
    colors = np.array(["blue", "green", "yellow", "pink"])
    titles = np.array(["Temperature", "Humidity",
                       "Soil Moisture", "Wind Speed"])

    fig, axs = plt.subplots(1,4,figsize=(16,12))
    fig.suptitle(f"Raspberry Pi Sensor Data - Round {round_number}")
    ind = 0
    for dataset in graphs:
        avg = 0
        for val in dataset:
            avg += val
        avg = avg / len(dataset)
        dataset.append(avg)
        print(dataset)
        y_vals = np.array(dataset)
        ax = axs[ind]
        ax.scatter(x_vals,y_vals,c=colors)
        ax.set_title(titles[ind])
        print(titles[ind])
        ind = ind + 1

    fname = f"polling-plot-{round_number}.png"
    plt.savefig(fname)

    #clear all the sensor data and start a new round
    
    

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
