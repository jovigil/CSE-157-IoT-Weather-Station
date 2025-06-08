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

tables = ['sensor_readings1', 'sensor_readings2', 'sensor_readings3']

def generate_sensor_readings():
    sensor_readings = {}
    #generate timestamps
    timestamps = []
    for i in range(100):
        now = datetime.now()
        timestamps.append(now)
        time.sleep(1)
        print(i)
        
    for table in tables:
        temp_val = 10
        humidity_val = 50
        windspeed_val = 5
        soil_moisture_val = 30
        sensor_readings[table] = []
        for i in range(100):
            if random.randint(0,10) > 9:
                continue #skip this reading
            temp_val += random.uniform(-0.5, 0.5)
            humidity_val += random.uniform(-0.3, 0.3)
            windspeed_val += random.uniform(-0.5, 0.5)
            soil_moisture_val += random.uniform(-0.2, 0.2)
            sensor_readings[table].append((timestamps[i], round(temp_val, 2), round(humidity_val, 2), round(windspeed_val, 2), round(soil_moisture_val, 2)))
    return sensor_readings


def insert_sensor_readings(sensor_readings):
    for table in tables:
        with cnx.cursor() as cursor:
            for reading in sensor_readings[table]:
                cursor.execute(f"INSERT INTO {table} (timestamp, temperature, humidity, windspeed, `soil moisture`) VALUES (%s, %s, %s, %s, %s)", reading)
    cnx.commit()



clear_all_tables()

sensor_readings = generate_sensor_readings()

insert_sensor_readings(sensor_readings)

with cnx.cursor() as cursor:
    cursor.execute("select * from sensor_readings2")
    for row in cursor.fetchall():
        print(row)

