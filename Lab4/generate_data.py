import mysql.connector
import random
from datetime import datetime
import time

cnx = mysql.connector.connect(user='root', password='',
                              host='127.0.0.1',
                              database='piSenseDB')
def clear_all_tables():
    with cnx.cursor() as cursor:
        cursor.execute("DELETE FROM sensor_readings1")
        cursor.execute("DELETE FROM sensor_readings2")
        cursor.execute("DELETE FROM sensor_readings3")
    cnx.commit()

def generate_sensor_readings():
    sensor_readings = []
    temp_val = 10
    humidity_val = 50
    windspeed_val = 5
    soil_moisture_val = 30
    for i in range(1000):
        now = datetime.now()
        temp_val += random.uniform(-0.01, 0.05)
        humidity_val += random.uniform(-0.03, 0.05)
        windspeed_val += random.uniform(-0.05, 0.03)
        soil_moisture_val += random.uniform(-0.02, 0.02)
        sensor_readings.append((now, round(temp_val, 2), round(humidity_val, 2), round(windspeed_val, 2), round(soil_moisture_val, 2)))
        time.sleep(0.1)
    return sensor_readings

tables = ['sensor_readings1', 'sensor_readings2', 'sensor_readings3']
def insert_sensor_readings(sensor_readings):
    for table in tables:
        with cnx.cursor() as cursor:
            for reading in sensor_readings:
                cursor.execute(f"INSERT INTO {table} (timestamp, temperature, humidity, windspeed, `soil moisture`) VALUES (%s, %s, %s, %s, %s)", reading)
    cnx.commit()



clear_all_tables()

sensor_readings = generate_sensor_readings()

insert_sensor_readings(sensor_readings)

with cnx.cursor() as cursor:
    cursor.execute("select * from sensor_readings2")
    for row in cursor.fetchall():
        print(row)

