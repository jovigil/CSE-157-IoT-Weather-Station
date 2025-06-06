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
import mysql.connector
from adafruit_sht31d import SHT31D
from adafruit_seesaw.seesaw import Seesaw
from adafruit_ads1x15.analog_in import AnalogIn
import adafruit_ads1x15.ads1015 as ADS
from simpleio import map_range


cnx = mysql.connector.connect(user='root', password='',
                              host='172.20.10.2',
                              database='piSenseDB')




config = {
    'POLL_DELAY': 1,
    'TIMEOUT_INT': 3
}

CLIENTS = set()

def check_config():
    with cnx.cursor() as cursor:
        cursor.execute("SELECT POLL_DELAY FROM PrimConfig WHERE ID = (SELECT MAX(ID) FROM PrimConfig)")
        result = cursor.fetchone()
        if result:
            config['POLL_DELAY'] = result[0]
        else:
            print("No POLL_DELAY found, using default values.")
        
        cursor.execute("SELECT PRIMARY_TIMEOUT FROM PrimConfig WHERE ID = (SELECT MAX(ID) FROM PrimConfig)")
        result = cursor.fetchone()
        if result:
            config['TIMEOUT_INT'] = result[0]
        else:
            print("No TIMEOUT found, using default values.")
        cursor.execute("SELECT NUM_CONNECTIONS FROM PrimConfig WHERE ID = (SELECT MAX(ID) FROM PrimConfig)")
        result = cursor.fetchone()
        if result[0] != len(CLIENTS) + 1:
            print(f"Updating NUM_CONNECTIONS from {result[0]} to {len(CLIENTS) + 1}")
            cursor.execute("""
    INSERT INTO PrimConfig (NUM_CONNECTIONS, POLL_DELAY, PRIMARY_TIMEOUT, SECONDARY_TIMEOUT, USER)
    SELECT %s, POLL_DELAY, PRIMARY_TIMEOUT, %s * POLL_DELAY, %s
    FROM PrimConfig
    ORDER BY ID DESC
    LIMIT 1;
""", (len(CLIENTS) + 1, len(CLIENTS) + 1,'Primary'))


    cnx.commit()



print("conected")
sensor_data = {
    "temperature":[],
    "humidity":[],
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


HOST = "172.20.10.13" 
PORT = 65404  # Port to listen on 

s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
s.settimeout(1)
s.bind((HOST, PORT))
from datetime import datetime
import time
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
        check_config()
        for CLIENT in list(CLIENTS):
            c = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            c.settimeout(config['TIMEOUT_INT'])
            try:
                print(CLIENT)
                c.connect((CLIENT, PORT))
                c.sendall(b"Requesting data")
                data = c.recv(2048)
                print(data)
                compile_sensor_data(data)
                c.close()
                time.sleep(config['POLL_DELAY'])  
            except (socket.timeout, ConnectionRefusedError) as e:
                logger_client.info(f"Error: {e}, on port {PORT}")
                c.close()
                CLIENTS.remove(CLIENT)

        sense()
        write_to_db() # at least write own data if other pis drop

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


i2c = busio.I2C(board.SCL, board.SDA)

sht30 = SHT31D(i2c)
soil_sensor = Seesaw(i2c, addr=0x36)
ads = ADS.ADS1015(i2c)
windspeed_channel = AnalogIn(ads, ADS.P0)

V_MIN = 0.4
V_MAX = 2.0
WIND_MIN = 0.0
WIND_MAX = 32.4


def read_wind_speed(voltage):
    voltage = max(min(voltage, V_MAX), V_MIN)
    return map_range(voltage, V_MIN, V_MAX, WIND_MIN, WIND_MAX)


def read_sht30():
    temperature = sht30.temperature
    humidity = sht30.relative_humidity
    sensor_data["temperature"].append(temperature)
    sensor_data["humidity"].append(humidity)

def read_stemma():
    soil_moisture = soil_sensor.moisture_read()
    soil_temp = soil_sensor.get_temp()
    sensor_data["soil_moist"].append(soil_moisture)
        
def read_adc():
    voltage = windspeed_channel.voltage
    wind_speed = read_wind_speed(voltage)
    sensor_data["wind_speed"].append(wind_speed)

def write_to_db():
    print(sensor_data)
    timestamp = datetime.now()
    for i in range(len(sensor_data["wind_speed"])):
        pis_readings = []
        pis_readings.append(timestamp)
        for value in sensor_data.values():
            pis_readings.append(value[i])

        print(pis_readings)
        with cnx.cursor() as cursor:
            table = f"sensor_readings{i+1}"
            cursor.execute(f"INSERT INTO {table} (timestamp, temperature, humidity,`soil moisture`, windspeed) VALUES (%s, %s, %s, %s, %s)", pis_readings)
    cnx.commit()


def sense():
    read_sht30()
    read_stemma()
    read_adc()

def plot_data(round_number):
    """
    Plot sensor data using matplotlib
    """
    data = sensor_data
    temps = data["temperature"]
    hums = data["humidity"]
    soil_moists = data["soil_moist"]
    wind_speeds = data["wind_speed"]
    print(sensor_data)
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
