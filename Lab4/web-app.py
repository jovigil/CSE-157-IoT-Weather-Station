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
from collections import defaultdict


app = Flask(__name__)
app.secret_key = os.urandom(32)
tables = ['sensor_readings1', 'sensor_readings2', 'sensor_readings3']

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
            
        

def average_by_timestamp(timestamps, values):
    grouped = defaultdict(list)
    for ts, val in zip(timestamps, values):
        grouped[ts].append(val)

    averaged = sorted((ts, sum(vals)/len(vals)) for ts, vals in grouped.items())
    avg_timestamps, avg_values = zip(*averaged)
    return list(avg_timestamps), list(avg_values)

def plot_data():
    """
    Plot sensor data using matplotlib
    """

    with mysql.connector.connect(user='root', password='',
                              host='127.0.0.1',
                              database='piSenseDB') as sql_connection:
        sensor_types = ['temperature', 'humidity', 'soil moisture', 'windspeed']
        sensor_data_by_type = {stype: defaultdict(list) for stype in sensor_types}
        timestamps_by_pi = defaultdict(list)

                # Collect data per Pi
        for table in tables:
            data = get_sensor_data(sql_connection, table)
            if not data:
                print(f"No data found in {table}. Skipping.")
                continue

            timestamps = [row['timestamp'] for row in data]
            timestamps_by_pi[table] = timestamps

            for stype in sensor_types:
                values = [row[stype] for row in data]
                sensor_data_by_type[stype][table] = values

        # Plot per sensor type
        for stype in sensor_types:
            plt.figure(figsize=(12, 8))
            all_avg_values = []
            shared_timestamps = None

            for table, values in sensor_data_by_type[stype].items():
                ts_raw = timestamps_by_pi[table]
                ts_avg, vals_avg = average_by_timestamp(ts_raw, values)

                if shared_timestamps is None:
                    shared_timestamps = ts_avg  # initialize for later averaging
                elif ts_avg != shared_timestamps:
                    print(f"Warning: timestamps for {table} differ, skipping average line.")
                    shared_timestamps = None

                all_avg_values.append(vals_avg)
                plt.plot(ts_avg, vals_avg, label=f'{table}')

            # Compute and plot the average line (only if timestamps are aligned)
            if shared_timestamps and all(len(vals) == len(shared_timestamps) for vals in all_avg_values):
                avg_array = np.mean(np.array(all_avg_values), axis=0)
                plt.plot(shared_timestamps, avg_array, label='Average', linewidth=3, linestyle='--')

            # Axis settings
            plt.xlabel('Timestamp')
            plt.ylabel(stype.title())
            plt.title(f'{stype.title()} vs Time')
            plt.xticks(rotation=45)
            plt.legend()
            plt.tight_layout()

            # Optional: y-axis padding for zoomed-out look
            flat_vals = [v for sublist in all_avg_values for v in sublist]
            if flat_vals:
                ymin, ymax = min(flat_vals), max(flat_vals)
                yrange = ymax - ymin if ymax != ymin else 1
                plt.ylim(ymin - 2 * yrange, ymax + 2 * yrange)

            fname = f'static/{stype}_plot.png'
            plt.savefig(fname)
            plt.close()


@app.route("/", methods=['GET'])
def return_home():
    plot_data()
    plots = [f for f in os.listdir("static") if os.path.isfile(os.path.join("static", f))]
    return render_template('index.html', plots=plots)


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

