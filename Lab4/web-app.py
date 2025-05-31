import mysql.connector
import random
from datetime import datetime
from flask import Flask, render_template, request, jsonify
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import numpy as np
import json

app = Flask(__name__)

tables = ['sensor_readings1', 'sensor_readings2', 'sensor_readings3']

def get_sensor_data(sql_connection, table_name):
    with sql_connection.cursor(dictionary=True) as cursor:
        cursor.execute(f"select * from {table_name}")
        sensor_data = cursor.fetchall()
    return sensor_data

def plot_data():
    """
    Plot sensor data using matplotlib
    """

    with mysql.connector.connect(user='root', password='',
                              host='127.0.0.1',
                              database='piSenseDB') as sql_connection:
        all_sensors = []
        for table in tables:
            data = get_sensor_data(sql_connection, table)
            all_sensors.append(data)
            timestamps = [row['timestamp'] for row in data]
            temperatures = [row['temperature'] for row in data]
            humidities = [row['humidity'] for row in data]
            soil_moisture = [row['soil moisture'] for row in data]
            wind_speeds = [row['windspeed'] for row in data]

            plt.figure(figsize=(12, 8))
            plt.plot(timestamps, temperatures, label='Temperature')
            plt.plot(timestamps, humidities, label='Humidity')
            plt.plot(timestamps, soil_moisture, label='Soil Moisture')
            plt.plot(timestamps, wind_speeds, label='Windspeed')
            
            plt.xlabel('Timestamp')
            plt.ylabel('Sensor Values')
            plt.title(f'Sensor Readings from {table}')
            plt.xticks(rotation=45)
            plt.legend()
            plt.tight_layout()
            plt.xlim(min(timestamps), max(timestamps))
            fname = f"static/{table}.png"
            plt.savefig(fname)

    #plot average values
    avg_temperatures = [np.mean([row['temperature'] for row in all_sensors[i]]) for i in range(len(all_sensors))]
    avg_humidities = [np.mean([row['humidity'] for row in all_sensors[i]]) for i in range(len(all_sensors))]
    avg_soil_moisture = [np.mean([row['soil moisture'] for row in all_sensors[i]]) for i in range(len(all_sensors))]
    avg_wind_speeds = [np.mean([row['windspeed'] for row in all_sensors[i]]) for i in range(len(all_sensors))]

    plt.figure(figsize=(12, 8))
    plt.plot(timestamps, temperatures, label='Temperature')
    plt.plot(timestamps, humidities, label='Humidity')
    plt.plot(timestamps, soil_moisture, label='Soil Moisture')
    plt.plot(timestamps, wind_speeds, label='Windspeed')
    
    plt.xlabel('Timestamp')
    plt.ylabel('Sensor Values')
    plt.title(f'Average Sensor Readings')
    plt.xticks(rotation=45)
    plt.legend()
    plt.tight_layout()
    plt.xlim(min(timestamps), max(timestamps))
    fname = f"static/avgs.png"
    plt.savefig(fname)




@app.route("/", methods=['GET'])
def return_home():
    plot_data()
    plots = ['sensor_readings1.png', 'sensor_readings2.png', 'sensor_readings3.png', 'avgs.png']
    return render_template('index.html', plots=plots)



if __name__ == "__main__":
    app.run(debug=True, port=5006)

