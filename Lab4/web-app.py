import mysql.connector
import random
from datetime import datetime
from flask import Flask, render_template, request, jsonify, session
from flask_session import Session
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import numpy as np
import json
import os
import requests
import sys
from collections import defaultdict


app = Flask(__name__)
app.secret_key = os.urandom(32)
tables = ['sensor_readings1', 'sensor_readings2', 'sensor_readings3']


def getWeather():
    http_req_headers = {"User-Agent":"josette_lab1"}
    endpoint = "https://api.weather.gov/gridpoints/MTR/90,69/forecast"
    failure = False
    try:
        response = requests.get(endpoint, headers=http_req_headers)
    except ConnectionError as err:
        sys.stderr.write(f"Cannot connect to network: {err}\n")
        #sys.exit(0)
        failure = True
    data_raw = response.json()
    if failure:
        report = "Cannot connect to api.weather.gov"
    else:
        report = data_raw["properties"]["periods"][0]["detailedForecast"]
    return report

def get_sensor_data(sql_connection, table_name):
    with sql_connection.cursor(dictionary=True) as cursor:
        cursor.execute(f"select * from {table_name}")
        sensor_data = cursor.fetchall()
    return sensor_data


def update_config(POLL_DELAY):
    with mysql.connector.connect(user='root', password='',
                              host='127.0.0.1',
                              database='piSenseDB') as sql_connection:
        with sql_connection.cursor() as cursor:
            cursor.execute("SELECT NUM_CONNECTIONS FROM PrimConfig WHERE ID = (SELECT MAX(ID) FROM PrimConfig)")
            result = cursor.fetchone()
            if result:
                num_connections = result[0]
            else:
                exit(2)
            new_secondary_timeout = num_connections * POLL_DELAY 

            cursor.execute("""
    INSERT INTO PrimConfig (NUM_CONNECTIONS, POLL_DELAY, PRIMARY_TIMEOUT, SECONDARY_TIMEOUT, USER)
    SELECT NUM_CONNECTIONS, %s, PRIMARY_TIMEOUT, %s, %s
    FROM PrimConfig
    ORDER BY ID DESC
    LIMIT 1;""", (POLL_DELAY, new_secondary_timeout, session.get('user')))
            cursor.execute("SELECT NUM_CONNECTIONS FROM TokenConfig WHERE ID = (SELECT MAX(ID) FROM TokenConfig)")
            result = cursor.fetchone()
            if result:
                num_connections = result[0]
            else:
                exit(2)
            new_timeout = num_connections * POLL_DELAY 

            cursor.execute("""
    INSERT INTO TokenConfig (NUM_CONNECTIONS, POLLDELAY, Timeout, CONNATTEMPTS, USER)
    SELECT NUM_CONNECTIONS, %s, %s, CONNATTEMPTS, %s
    FROM TokenConfig
    ORDER BY ID DESC
    LIMIT 1;""", (POLL_DELAY, new_timeout, session.get('user')))
        sql_connection.commit()
            
        

def get_avg_data(all_data, sensor_type):
    #first value is a timestamp, second value is a list of values from each table at that timestamp
    all_data_of_sensor = []
    for data in all_data.values():
        for entry in data:
            timestamp = entry['timestamp']
            if timestamp in [x[0] for x in all_data_of_sensor]:
                for x in all_data_of_sensor:
                    if x[0] == timestamp:
                        sum = entry[sensor_type]
                        sum += x[1][0]
                        x[1][0] = sum / 2
            else:
                all_data_of_sensor.append((timestamp, [entry[sensor_type]]))

    return sorted(all_data_of_sensor, key=lambda x: x[0])

def plot_data():
    """
    Plot sensor data using matplotlib
    """

    with mysql.connector.connect(user='root', password='',
                              host='127.0.0.1',
                              database='piSenseDB') as sql_connection:
        sensor_types = ['temperature', 'humidity', 'soil moisture', 'windspeed']
        sensor_labels = ['Temperature (°C)', 'Humidity (%)', 'Soil Moisture (%)', 'Wind Speed (m/s)']
        all_data = {}
        all_avg_data = {}
        #This gets all avg data from all tables
        for table in tables:
            all_data[table] = get_sensor_data(sql_connection, table)
        for sensor_type in sensor_types:
            all_avg_data[sensor_type] = get_avg_data(all_data, sensor_type) #This is a tuple of (timestamp, [value])
        print(all_avg_data)
        for sensor_type in sensor_types:
                # Plot each table's data
            plt.figure(figsize=(10, 5))
            for table in tables:
                table_data = all_data[table]
                timestamps = [entry['timestamp'] for entry in table_data]
                values = [entry[sensor_type] for entry in table_data]
                plt.plot(timestamps, values, marker='.', linestyle='--', label=f'{table}')

            timestamps = [entry[0] for entry in all_avg_data[sensor_type]]
            values = [entry[1][0] for entry in all_avg_data[sensor_type]]
            plt.plot(timestamps, values, marker='o', label='Avg')
            plt.xlabel('Timestamp')
            plt.ylabel(sensor_labels[sensor_types.index(sensor_type)])
            plt.title(f'{sensor_labels[sensor_types.index(sensor_type)]} Over Time')
            plt.xticks(rotation=45)
            plt.tight_layout()
            plt.legend()
            plt.grid(True)
            plt.savefig(f'static/{sensor_type.replace(" ", "_")}.png')
            plt.close()
        

@app.route("/", methods=['GET'])
def return_home():
    plot_data()
    plots = [f for f in os.listdir("static") if os.path.isfile(os.path.join("static", f))]
    return render_template('index.html', plots=plots, text=getWeather())


@app.route("/login", methods=['POST'])
def login():
    data = request.get_json()
    username = data.get('username')
    password = data.get('password')

    with mysql.connector.connect(user='root', password='',
                              host='127.0.0.1',
                              database='piSenseDB') as sql_connection:
        with sql_connection.cursor(dictionary=True) as cursor:
            cursor.execute("SELECT * FROM UserAuth WHERE User = %s AND PASSWORD = %s", (username, password))
            user = cursor.fetchone()
            if user:
                session['user'] = user['User']
                return jsonify({"status": "success", "message": "Login successful."}), 200
            else:
                return jsonify({"status": "error", "message": "Invalid username or password."}), 401
    

def get_auth():
    with mysql.connector.connect(user='root', password='',
                              host='127.0.0.1',
                              database='piSenseDB') as sql_connection:
        with sql_connection.cursor(dictionary=True) as cursor:
            cursor.execute("SELECT Auth FROM UserAuth WHERE User = %s", (session.get('user'),))
            auth = cursor.fetchone()
        sql_connection.commit()
    if auth:
            return auth['Auth']


@app.route("/update_config", methods=['POST'])
def update_config_route():
    curr_auth = get_auth()
    print(curr_auth)
    if curr_auth != 'Admin' and curr_auth != 'Editor':
        return jsonify({"status": "error", "message": "Unauthorized access."}), 403

    try:
        data = request.get_json()
        POLL_DELAY = data.get('POLL_DELAY', 5)  # Default to 5 seconds if not provided
        if POLL_DELAY < 2:
            return jsonify({"status": "error", "message": "POLL_DELAY must be at least 2 seconds."}), 400
        update_config(POLL_DELAY)
        return jsonify({"status": "success", "message": "Configuration updated successfully."}), 200
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500

@app.route("/search", methods=["GET","POST"])
def search():
    curr_auth = get_auth()
    print(curr_auth)
    if curr_auth != 'Admin' and curr_auth != 'Editor' and curr_auth != 'Viewer':
        return jsonify({"status": "error", "message": "Unauthorized access."}), 403
    try:
        with mysql.connector.connect(user='root', password='',
                                host='127.0.0.1',
                                database='piSenseDB') as sql_connection:
            cursor = sql_connection.cursor(dictionary=True)
            if request.method == "POST":
                timestamp = request.form["timestamp"]
                date_only = datetime.strptime(timestamp, "%Y-%m-%d").date()
                date_str = date_only.strftime("%Y-%m-%d")
                print(timestamp)
                cursor.execute("""
        SELECT * FROM sensor_readings1 WHERE DATE(timestamp) = %s
        UNION
        SELECT * FROM sensor_readings2 WHERE DATE(timestamp) = %s
        UNION
        SELECT * FROM sensor_readings3 WHERE DATE(timestamp) = %s
    """, (date_only, date_only, date_only))
            data = cursor.fetchall()
            sql_connection.commit()
            if len(data) == 0:
            #     cursor.execute("SELECT * FROM sensor_readings1")
            #     data = cursor.fetchall()
            #     sql_connection.commit()
                return {"status": "error", "message": "No data from this date"}
        return jsonify(data), 200
    except ValueError:
        return "Invalid date format. Please use YYYY-MM-DD", 40
                
        

if __name__ == "__main__":
    app.run(debug=True, port=5006)

