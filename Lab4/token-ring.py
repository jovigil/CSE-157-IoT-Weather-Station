import socket
import threading
import time
import sys
import board
import busio
import json
import mysql.connector
from adafruit_sht31d import SHT31D
from adafruit_seesaw.seesaw import Seesaw
from adafruit_ads1x15.analog_in import AnalogIn
import adafruit_ads1x15.ads1015 as ADS
from simpleio import map_range
import numpy as np
import matplotlib.pyplot as plt
import copy
from datetime import datetime
import time
i2c = busio.I2C(board.SCL, board.SDA)

sht30 = SHT31D(i2c)
soil_sensor = Seesaw(i2c, addr=0x36)
ads = ADS.ADS1015(i2c)
windspeed_channel = AnalogIn(ads, ADS.P0)

log_file = "polling-log.txt"

V_MIN = 0.4
V_MAX = 2.0
WIND_MIN = 0.0
WIND_MAX = 32.4

DB_CONNECTOR = 3 # pi that sends data to XAMPP server's id


sensor_data = {
    "temperature":[0,0,0],
    "humidity":[0,0,0],
    "soil_moist":[0,0,0],
    "wind_speed":[0,0,0],
    "RESET":0,
    "DB_CONNECTOR":DB_CONNECTOR
}

sensor_data_fields = ["temperature",
                      "humidity",
                      "soil_moist",
                      "wind_speed"]

PORT = 65432
# Configuration for each Pi
CONFIG = {
    1: {
        "previous_ip": "172.20.10.13",
        "this_ip": "172.20.10.11",
        "next_ip": "172.20.10.14",
        "CONN_ATTEMPTS": 10,
        "POLL_DELAY": 1,
        "TIMEOUT_INT": 5,
    },
    2: {
        "previous_ip": "172.20.10.11",
        "this_ip": "172.20.10.14",
        "next_ip": "172.20.10.13",
        "CONN_ATTEMPTS": 10,
        "POLL_DELAY": 1,
        "TIMEOUT_INT": 5,
    },
    3: {
        "previous_ip": "172.20.10.14",
        "this_ip": "172.20.10.13",
        "next_ip": "172.20.10.11",
        "CONN_ATTEMPTS": 10,
        "POLL_DELAY": 1,
        "TIMEOUT_INT": 5,
    },
}



pi_id = int(sys.argv[1])
my_config = CONFIG[pi_id].copy()


def check_db_config():
    cnx = mysql.connector.connect(user='root', password='',
                              host='172.20.10.2',
                              database='piSenseDB')
    with cnx.cursor() as cursor:
        cursor.execute("SELECT POLLDELAY, Timeout, CONNATTEMPTS FROM TokenConfig WHERE ID = (SELECT MAX(ID) FROM TokenConfig)")
        result = cursor.fetchone()
        if result:
            my_config['POLL_DELAY'] = result[0]
        else:
            my_config['POLL_DELAY'] = 2
            print("No POLL_DELAY found, using default values.")
        if result[1]:
            my_config['TIMEOUT_INT'] = result[1]
        else:
            my_config['TIMEOUT_INT'] = 3
            print("No TIMEOUT found, using default values.")
        if result[2]:
            my_config['CONN_ATTEMPTS'] = result[2]
        else:
            my_config['CONN_ATTEMPTS'] = 10
            print("No CONN_ATTEMPTS found, using default values.")

        cursor.execute("SELECT NUM_CONNECTIONS FROM TokenConfig WHERE ID = (SELECT MAX(ID) FROM TokenConfig)")
        result = cursor.fetchone()
    cnx.commit()
    cnx.close()

def reconfigure():
    """Change next_ip to pi_id + 1's next_ip in the case
    of host dropout."""
    cnx = mysql.connector.connect(user='root', password='',
                              host='172.20.10.2',
                              database='piSenseDB')
    global my_config
    global DB_CONNECTOR
    if CONFIG[pi_id]["next_ip"] != my_config["next_ip"]:
        print("Going back to original config")
        DB_CONNECTOR = 3
        my_config = CONFIG[pi_id].copy()
        with cnx.cursor() as cursor:
            cursor.execute("""
    INSERT INTO TokenConfig (NUM_CONNECTIONS, TIMEOUT, CONNATTEMPTS, USER)
    SELECT %s, POLL_DELAY, %s * POLL_DELAY, %s
    FROM PrimConfig
    ORDER BY ID DESC
    LIMIT 1;
""", (3, 3,f"pi_id: {pi_id}"))
        cnx.commit()
        cnx.close()
        return
    
    new_next_ip = CONFIG[pi_id % 3 + 1]["next_ip"]
    my_config["next_ip"] = new_next_ip
    if(pi_id == sensor_data["DB_CONNECTOR"] - 1):
        print("Reconfiguring DB_CONNECTOR")
        DB_CONNECTOR = pi_id
    with cnx.cursor() as cursor:
            cursor.execute("""
    INSERT INTO TokenConfig (NUM_CONNECTIONS, TIMEOUT, CONNATTEMPTS, USER)
    SELECT %s, POLL_DELAY, %s * POLL_DELAY, %s
    FROM PrimConfig
    ORDER BY ID DESC
    LIMIT 1;
    """, (2, 2,f"pi_id: {pi_id}"))
    cnx.commit()
    cnx.close()
def read_wind_speed(voltage):
    voltage = max(min(voltage, V_MAX), V_MIN)
    return map_range(voltage, V_MIN, V_MAX, WIND_MIN, WIND_MAX)

def sense_and_marshall(sensor_data_, reset=False) -> str:
    global my_config
    global DB_CONNECTOR
    
    sensor_data = json.loads(sensor_data_)
    print(sensor_data)
    try:
        # sht30
        temperature = sht30.temperature
        humidity = sht30.relative_humidity
        sensor_data["temperature"][pi_id-1] = temperature
        sensor_data["humidity"][pi_id-1] = humidity

        # stemma
        soil_moisture = soil_sensor.moisture_read()
        sensor_data["soil_moist"][pi_id-1] = soil_moisture

        # adc/windspeed
        voltage = windspeed_channel.voltage
        wind_speed = read_wind_speed(voltage)
        sensor_data["wind_speed"][pi_id-1] = wind_speed
        
        if sensor_data["RESET"] == 1:
            print("RESET RECIEVED")
            DB_CONNECTOR = 3
            my_config = CONFIG[pi_id].copy()
            print(my_config)

        if reset:
            sensor_data["RESET"] = 1
            sensor_data["DB_CONNECTOR"] = DB_CONNECTOR
        else:
            sensor_data["RESET"] = 0

        if DB_CONNECTOR == pi_id:
            print("Writing to DB")
            print(sensor_data)
            write_to_db(sensor_data)


        timestamp = datetime.now()
        log_entry = (
            f"Josette Vigil\n"
            f"{timestamp}\n"
            f"Temperature: {temperature:.2f} C\n"
            f"Humidity: {humidity:.2f} %\n"
            f"Soil Moisture: {soil_moisture}\n"
            f"Wind speed: {wind_speed:.2f} m/s\n\n"
        )

        # print(log_entry.strip())
        with open(log_file, "a") as file:
            file.write(log_entry)
        return json.dumps(sensor_data)
    
    except Exception as e:
        print(f"Error: {e}")

def handle_connection():
    """Listen for incoming message and forward it."""
    global my_config
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as server:
        server.bind((my_config["this_ip"], PORT))
        round_number = 0
        last_addr = my_config["previous_ip"]
        while True:
            RESET = False
            check_db_config()
            server.listen(5)
            server.settimeout(my_config["TIMEOUT_INT"])
            try:
                conn, addr = server.accept()
                print(addr[0], last_addr)
                if addr[0] == my_config["previous_ip"] and last_addr != my_config["previous_ip"]:
                    my_config = CONFIG[pi_id].copy()
                    RESET = True
                    print("IN RESET TO TRUE IF STATEMENT")
                last_addr = addr[0]
                with conn:
                    data = conn.recv(1024).decode()
                    # print(f"Received: {data}")
                    if pi_id == 3:
                        if data[:5] == "token":
                            payload = data[5:]
                            print(payload)
                            final_data = sense_and_marshall(payload)
                        # final_data = payload
                            print(final_data)
                            #plot_data(final_data, round_number)
                            if RESET:
                                sensor_data["RESET"] = 1
                            empty_data = json.dumps(sensor_data)
                            sensor_data["RESET"] = 0
                            packet = "token" + empty_data
                            send_packet(packet)
                            round_number += 1
                    else:
                        if data[:5] == "token":
                            payload = data[5:]
                            new_payload = sense_and_marshall(payload,
                                                            reset=RESET)
                            time.sleep(1)
                            packet = "token" + new_payload
                            send_packet(packet)
                time.sleep(my_config["POLL_DELAY"])
            except socket.timeout:
                print("Timeout occurred while listening. Sending packet downstream...")
                empty_data = json.dumps(sensor_data)
                packet = "token" + empty_data
                send_packet(packet)


def send_packet(msg):
    """Send a token and sensor data to the next Pi."""
    retries = 0
    while True:
        print(my_config["next_ip"])
        try:
            with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
                s.connect((my_config["next_ip"], PORT))
                s.sendall(msg.encode())
             #   print(f"Sent: {msg} to {my_config['next_ip']}")
                s.close()
                break
        except (ConnectionRefusedError, OSError) as e:
            retries += 1
            print(my_config)
            if retries >= my_config['CONN_ATTEMPTS']:
                retries = 0
                print("Reconfiguring due to connection failure...")
                reconfigure()
            print("Connection failure:")
            print(e)
            time.sleep(1)

def write_to_db(sensor_data_):
    sensor_data = sensor_data_
    print(sensor_data)
    timestamp = datetime.now()
    cnx = mysql.connector.connect(user='root', password='',
                              host='172.20.10.2',
                              database='piSenseDB')
    for i in range(len(sensor_data["wind_speed"])):
        pis_readings = []
        pis_readings.append(timestamp)
        for value in sensor_data.values():
            if isinstance(value, list):
                pis_readings.append(value[i])

        print(pis_readings)
        if(pis_readings[1] == 0 and 
            pis_readings[2] == 0 and 
            pis_readings[3] == 0 and 
            pis_readings[4] == 0):
            print("Skipping empty readings")
            continue
        with cnx.cursor() as cursor:
            table = f"sensor_readings{i+1}"
            cursor.execute(f"INSERT INTO {table} (timestamp, temperature, humidity,`soil moisture`, windspeed) VALUES (%s, %s, %s, %s, %s)", pis_readings)
    cnx.commit()
    cnx.close()

def plot_data(sensor_data_,round_number):
    """
    Plot sensor data using matplotlib
    """
    print(sensor_data_)
    data = json.loads(sensor_data_)
    temps = data["temperature"]
    hums = data["humidity"]
    soil_moists = data["soil_moist"]
    wind_speeds = data["wind_speed"]
    # print(("wind speed data: ", data["wind_speed"]))
    graphs = [temps, hums,
              soil_moists, wind_speeds]
    x_vals = np.array(["Pi 1", "Pi 2", "Pi 3", "Avg"]) #1 is sec1, 2 is sec2,
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
        # print(dataset)
        y_vals = np.array(dataset)
        ax = axs[ind]
        ax.scatter(x_vals,y_vals,c=colors)
        ax.set_title(titles[ind])
        # print(titles[ind])
        ind = ind + 1

    fname = f"polling-plot-{round_number}.png"
    plt.savefig(fname)

def start():
    threading.Thread(target=handle_connection, daemon=True).start()

    # Pi #1 starts the communication
    if pi_id == 1:
        global sensor_data
        time.sleep(5)  # Wait for others to be ready
        empty_data = json.dumps(sensor_data)
        print(empty_data)
        payload = sense_and_marshall(empty_data)
        packet = "token" + payload
        send_packet(packet)

    # Keep the main thread alive
    while True:
        time.sleep(1)


if __name__ == "__main__":
    start()
