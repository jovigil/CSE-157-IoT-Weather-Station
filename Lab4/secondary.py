import socket
import asyncio
import logging
import time
import datetime
import board
import busio
import json
import sys
from adafruit_sht31d import SHT31D
from adafruit_seesaw.seesaw import Seesaw
from adafruit_ads1x15.analog_in import AnalogIn
import adafruit_ads1x15.ads1015 as ADS
from simpleio import map_range
import mysql.connector



cnx = mysql.connector.connect(user='root', password='',
                              host='172.20.10.2',
                              database='piSenseDB')

config = {
    'TIMEOUT_INT': 3
}


def check_config():
    print("Checking config...")
    with cnx.cursor() as cursor:
        cursor.execute("SELECT SECONDARY_TIMEOUT FROM PrimConfig WHERE ID = (SELECT MAX(ID) FROM PrimConfig)")
        result = cursor.fetchone()
        print(result)
        if result:
            config['TIMEOUT_INT'] = result[0]
        else:
            print("No TIMEOUT found, using default values.")
    cnx.commit()



i2c = busio.I2C(board.SCL, board.SDA)

sht30 = SHT31D(i2c)
soil_sensor = Seesaw(i2c, addr=0x36)
ads = ADS.ADS1015(i2c)
windspeed_channel = AnalogIn(ads, ADS.P0)

V_MIN = 0.4
V_MAX = 2.0
WIND_MIN = 0.0
WIND_MAX = 32.4


HOST = "172.20.10.13"

user_ip = sys.argv[1]
MY_IP = f"172.20.10.{user_ip}"
print("User IP is " + MY_IP)

PORT = 65404  # Port to listen on 


sensor_data = {
    "temperature":float(),
    "humidity":float(),
    "soil_moist":float(),
    "wind_speed":float()
}


def start():
    while(True):
        try:
            s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)

            s.connect((HOST, PORT))

            s.sendall(b"Hello, world")
            s.close()
            return
        except socket.error as e:
            print(f"Socket error: {e}")
            time.sleep(1)

def read_wind_speed(voltage):
    voltage = max(min(voltage, V_MAX), V_MIN)
    return map_range(voltage, V_MIN, V_MAX, WIND_MIN, WIND_MAX)

def read_sht30():
    temperature = sht30.temperature
    humidity = sht30.relative_humidity
    sensor_data["temperature"] = temperature
    sensor_data["humidity"] = humidity

def read_stemma():
    soil_moisture = soil_sensor.moisture_read()
    sensor_data["soil_moist"] = soil_moisture
        
def read_adc():
    voltage = windspeed_channel.voltage
    wind_speed = read_wind_speed(voltage)
    sensor_data["wind_speed"] = wind_speed

async def main():
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    start()
    global PORT
    s.bind((MY_IP, PORT))
    s.listen()
    i = 0
    while True:
        check_config()
        print(config['TIMEOUT_INT'])
        s.settimeout(config['TIMEOUT_INT'])
        i += 1
        try:
            conn, addr = s.accept()
            with conn:
                data = conn.recv(1024)
                print(f"Received {data!r} from {addr}")
                read_sht30()
                read_stemma()
                read_adc()
                conn.send(json.dumps(sensor_data).encode())
        except (socket.timeout, ConnectionResetError, BrokenPipeError, OSError) as e:
            print(f"Error: {e}, reconnecting...")
            start()
            s.listen()

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
        print("\nExiting program...")
        exit(0)


