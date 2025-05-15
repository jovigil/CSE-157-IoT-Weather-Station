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
    "temperature":list(float()),
    "humidity":list(float()),
    "soil_temp":list(float()),
    "soil_moist":list(float()),
    "wind_speed":list(float())
}

# Configuration for each Pi
CONFIG = {
    1: {"listen_port": 65517, "next_ip": "192.168.1.1", "next_port": 6553},
    2: {"listen_port": 6551, "next_ip": "192.168.1.2", "next_port": 6553},
    3: {"listen_port": 6553, "next_ip": "192.168.1.17", "next_port": 65517},
}

def read_wind_speed(voltage):
    voltage = max(min(voltage, V_MAX), V_MIN)
    return map_range(voltage, V_MIN, V_MAX, WIND_MIN, WIND_MAX)


pi_id = int(sys.argv[1])
my_config = CONFIG[pi_id]

def sense_and_marshall(sensor_data_) -> str:
    sensor_data = json.loads(sensor_data_)

    try:
        # sht30
        temperature = sht30.temperature
        humidity = sht30.relative_humidity
        sensor_data["temperature"][my_config-1] = temperature
        sensor_data["humidity"][my_config-1] = humidity

        # stemma
        soil_moisture = soil_sensor.moisture_read()
        soil_temp = soil_sensor.get_temp()
        sensor_data["soil_moist"][my_config-1] = soil_moisture
        sensor_data["soil_temp"][my_config-1] = soil_temp

        # adc/windspeed
        voltage = windspeed_channel.voltage
        wind_speed = read_wind_speed(voltage)
        sensor_data["wind_speed"][my_config-1] = wind_speed

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
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as server:
        server.bind(('', my_config["listen_port"]))
        server.listen(1)
        while True:
            conn, addr = server.accept()
            with conn:
                data = conn.recv(1024).decode()
                print(f"Received: {data}")
                if pi_id == 3:
                    if data[:4] == "token":
                        payload = data[5:]
                        new_payload = sense_and_marshall(payload)
                        print("plot goes here")
                        packet = "token"
                        send_packet(packet.encode())
                else:
                    if data[:4] == "token":
                        payload = data[5:]
                        new_payload = sense_and_marshall(payload)
                        time.sleep(1)
                        packet = "token" + new_payload
                        send_packet(packet.encode())


def send_packet(msg):
    """Send a token and sensor data to the next Pi."""
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
        global sensor_data
        time.sleep(5)  # Wait for others to be ready
        payload = sense_and_marshall(sensor_data)
        packet = "token" + payload
        send_packet(packet.encode())

    # Keep the main thread alive
    while True:
        time.sleep(1)


if __name__ == "__main__":
    start()
