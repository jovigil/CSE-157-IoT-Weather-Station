import socket
import asyncio
import logging
import time
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

V_MIN = 0.4
V_MAX = 2.0
WIND_MIN = 0.0
WIND_MAX = 32.4


HOST = "169.233.1.17" 
PORT = 65425  # Port to listen on 


sensor_data = {
    "temperature":float(),
    "humidity":float(),
    "soil_temp":float(),
    "soil_moist":float(),
    "wind_speed":float()
}


# def get_port_assigned():
#     s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)

#     s.connect((HOST, PORT))

#     s.sendall(b"Hello, world")
#     UPORT = int.from_bytes(s.recv(1024), byteorder='big')
#     print(f"Received port number {UPORT}")
#     s.close()
#     return UPORT

def read_wind_speed(voltage):
    voltage = max(min(voltage, V_MAX), V_MIN)
    return map_range(voltage, V_MIN, V_MAX, WIND_MIN, WIND_MAX)

async def read_sht30():
    while True:
        temperature = sht30.temperature
        humidity = sht30.relative_humidity
        logger_sht30.info(f"{datetime.datetime.now()}\nTemperature: {temperature:.2f} C\nHumidity: {humidity:.2f}%\n")
        sensor_data["temperature"] = temperature
        sensor_data["humidity"] = humidity
        await asyncio.sleep(1)

async def read_stemma():
    while True:
        soil_moisture = soil_sensor.moisture_read()
        soil_temp = soil_sensor.get_temp()
        logger_stemma.info(f"{datetime.datetime.now()}\nSoil Temperature: {soil_temp:.2f} C\nSoil moisture: {soil_moisture:.2f}\n")
        sensor_data["soil_moisture"] = soil_moisture
        sensor_data["soil_temp"] = soil_temp
        await asyncio.sleep(1)

async def read_adc():
    while True:
        voltage = windspeed_channel.voltage
        wind_speed = read_wind_speed(voltage)
        logger_adc.info(f"{datetime.datetime.now()}\nWind speed: {wind_speed:.2f} m/s\n\n")
        sensor_data["wind_speed"] = wind_speed
        await asyncio.sleep(1)

async def main():
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    # UPORT = get_port_assigned()
    global PORT
    s.bind((HOST, PORT))
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
                # if i == 5:  #This is just for testing
                #     time.sleep(5)
                await asyncio.gather(read_sht30(),
                             read_stemma(),
                             read_adc()
                            )
                conn.send(json.dumps(sensor_data).encode())
        except (socket.timeout, ConnectionResetError, BrokenPipeError, OSError) as e:
            print(f"Error: {e}, reconnecting...")
            s.close()
            s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            s.bind((HOST, PORT))
            s.listen()
            s.settimeout(3)


