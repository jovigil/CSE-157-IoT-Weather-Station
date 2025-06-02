import socket
import threading
import time
import sys
import datetime
import board
import busio
import json
from adafruit_sht31d import SHT31D
from adafruit_seesaw.seesaw import Seesaw
from adafruit_ads1x15.analog_in import AnalogIn
import adafruit_ads1x15.ads1015 as ADS
from simpleio import map_range
import numpy as np
import matplotlib.pyplot as plt
import copy
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

sensor_data = {
    "temperature":[0,0,0],
    "humidity":[0,0,0],
    "soil_temp":[0,0,0],
    "soil_moist":[0,0,0],
    "wind_speed":[0,0,0],
    "RESET":0
}

PORT = 65432
# Configuration for each Pi
CONFIG = {
    1: {"previous_ip" : "169.233.1.9", "this_ip": "169.233.1.17","next_ip": "169.233.1.2"},
    2: {"previous_ip" : "169.233.1.17", "this_ip": "169.233.1.2","next_ip": "169.233.1.9"},
    3: {"previous_ip" : "169.233.1.2", "this_ip": "169.233.1.9","next_ip": "169.233.1.17"},
}

pi_id = int(sys.argv[1])
my_config = CONFIG[pi_id].copy()

def reconfigure():
    """Change next_ip to pi_id + 1's next_ip in the case
    of host dropout."""
    global my_config
    new_next_ip = CONFIG[pi_id % 3 + 1]["next_ip"]
    my_config["next_ip"] = new_next_ip
    
def read_wind_speed(voltage):
    voltage = max(min(voltage, V_MAX), V_MIN)
    return map_range(voltage, V_MIN, V_MAX, WIND_MIN, WIND_MAX)

def sense_and_marshall(sensor_data_, reset=False) -> str:
    global my_config
    
    
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
        soil_temp = soil_sensor.get_temp()
        sensor_data["soil_moist"][pi_id-1] = soil_moisture
        sensor_data["soil_temp"][pi_id-1] = soil_temp

        # adc/windspeed
        voltage = windspeed_channel.voltage
        wind_speed = read_wind_speed(voltage)
        sensor_data["wind_speed"][pi_id-1] = wind_speed


        if sensor_data["RESET"] == 1:
            print("RESET RECIEVED")
            my_config = CONFIG[pi_id]
            print(my_config)

        if reset:
            sensor_data["RESET"] = 1
        else:
            sensor_data["RESET"] = 0

        timestamp = datetime.datetime.now()
        log_entry = (
            f"Josette Vigil\n"
            f"{timestamp}\n"
            f"Temperature: {temperature:.2f} C\n"
            f"Humidity: {humidity:.2f} %\n"
            f"Soil Moisture: {soil_moisture}\n"
            f"Soil Temperature: {soil_temp:.2f} C\n"
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
        server.listen(5)
        server.settimeout(10)
        round_number = 0
        last_addr = my_config["previous_ip"]
        while True:
            RESET = False
            try:
                conn, addr = server.accept()
                print(addr[0], last_addr)
                if addr[0] == my_config["previous_ip"] and last_addr != my_config["previous_ip"]:
                    my_config = CONFIG[pi_id]
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
                            plot_data(final_data, round_number)
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
            if retries >= 10:
                reconfigure()
            print("Connection failure:")
            print(e)
            time.sleep(1)

def plot_data(sensor_data_,round_number):
    """
    Plot sensor data using matplotlib
    """
    # print(sensor_data_)
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
