import json
import sqlite3
import clr
import psutil
from flask import Flask, render_template
from apscheduler.schedulers.background import BackgroundScheduler
import datetime

app = Flask(__name__)
scheduler = BackgroundScheduler()

conn = sqlite3.connect('system_info.db')
cursor = conn.cursor()

hwtypes = ['Cpu', 'Memory', 'Storage']

system_stats = {
    'param1_disk': 'None',
    'param2_disk': 'None',
    'param3_disk': 'None',
    'param4_disk': 'None',
    'param1_cpu' : 'None',
    'param2_cpu' : 'None',
    'param3_cpu' : 'None',
    'param1_ram' : 'None',
    'param2_ram' : 'None',
    'param3_ram' : 'None'
}
def initialize_openhardwaremonitor():
    clr.AddReference('LibreHardwareMonitorLib')

    from LibreHardwareMonitor import Hardware
    handle = Hardware.Computer()
    handle.IsCpuEnabled = True
    handle.IsMemoryEnabled = True
    handle.IsStorageEnabled = True
    handle.Open()
    return handle

HardwareHandle = initialize_openhardwaremonitor()
def create_tables():
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS disk_stats
        (id INTEGER PRIMARY KEY AUTOINCREMENT, Name TEXT, DescribeSensor TEXT, ValueSensor TEXT, TotalStorageSize TEXT, CreationTime TEXT)
    ''')

    cursor.execute('''
        CREATE TABLE IF NOT EXISTS cpu_stats
        (id INTEGER PRIMARY KEY AUTOINCREMENT, Name TEXT, DescribeSensor TEXT, ValueSensor TEXT, CreationTime TEXT)
    ''')

    cursor.execute('''
        CREATE TABLE IF NOT EXISTS ram_stats
        (id INTEGER PRIMARY KEY AUTOINCREMENT, Name TEXT, DescribeSensor TEXT, ValueSensor TEXT, CreationTime TEXT)
    ''')
    conn.commit()
    cursor.close()
    conn.close()


def create_json_file():
    conn = sqlite3.connect('system_info.db')
    cursor = conn.cursor()
    cursor.execute("SELECT name FROM sqlite_master WHERE type='table';")
    tables = cursor.fetchall()
    data = {}

    for table_name in tables:
        cursor.execute(f"SELECT * FROM {table_name[0]} ORDER BY RowId DESC LIMIT 70")
        rows = cursor.fetchall()
        columns = [column[0] for column in cursor.description]
        table_data = []
        for row in rows:
            table_data.append(dict(zip(columns, row)))
        data[table_name[0]] = table_data

    with open('data.json', 'w') as json_file:
        json.dump(data, json_file)

    conn.commit()
    cursor.close()
    conn.close()



def delete_sql_records():
    conn = sqlite3.connect('system_info.db')
    cursor = conn.cursor()
    expire_period = datetime.timedelta(weeks=1)
    current_time = datetime.datetime.now()
    for table_name in ['disk_stats', 'cpu_stats', 'ram_stats']:
        cursor.execute(f"DELETE FROM {table_name} WHERE datetime(CreationTime) < ?", (current_time - expire_period,))


    conn.commit()
    cursor.close()
    conn.close()

def fetch_stats(handle):
    for i in handle.Hardware:
        i.Update()
        for sensor in i.Sensors:
            get_disk_stats(sensor)
            get_cpu_stats(sensor)
            get_ram_stats(sensor)
        for j in i.SubHardware:
            j.Update()
            for subsensor in j.Sensors:
                get_disk_stats(subsensor)
                get_cpu_stats(subsensor)
                get_ram_stats(subsensor)


def get_disk_stats(sensor):
    if sensor.Value:
        if str(sensor.Hardware.HardwareType) == 'Storage':
            system_stats['param1_disk'] = sensor.Hardware.Name
            system_stats['param2_disk'] = sensor.Name
            system_stats['param3_disk'] = sensor.Value
            system_stats['param4_disk'] = psutil.disk_usage('C:\\').total / (1024 ** 3)
            save_to_database_storage('disk_stats', [system_stats['param1_disk'], system_stats['param2_disk'], system_stats['param3_disk'], system_stats['param4_disk']])

def get_cpu_stats(sensor):
    if sensor.Value:
        if str(sensor.Hardware.HardwareType) == 'Cpu':
            system_stats['param1_cpu'] = sensor.Hardware.Name
            system_stats['param2_cpu'] = sensor.Name
            system_stats['param3_cpu'] = sensor.Value
            save_to_database('cpu_stats', [system_stats['param1_cpu'], system_stats['param2_cpu'], system_stats['param3_cpu']])

def get_ram_stats(sensor):
    if sensor.Value:
        if str(sensor.Hardware.HardwareType) == 'Memory':
            system_stats['param1_ram'] = sensor.Hardware.Name
            system_stats['param2_ram'] = sensor.Name
            system_stats['param3_ram'] = sensor.Value
            save_to_database('ram_stats', [system_stats['param1_ram'], system_stats['param2_ram'], system_stats['param3_ram']])

def save_to_database(table, data):
    conn = sqlite3.connect('system_info.db')
    cursor = conn.cursor()
    placeholders = ', '.join(['?' for _ in range(len(data))])
    cursor.execute(f'INSERT INTO {table} (Name, DescribeSensor, ValueSensor, CreationTime) VALUES ({placeholders}, ?)', data + [str(datetime.datetime.now())])
    conn.commit()

def save_to_database_storage(table, data):
    conn = sqlite3.connect('system_info.db')
    cursor = conn.cursor()
    placeholders = ', '.join(['?' for _ in range(len(data))])
    cursor.execute(f'INSERT INTO {table} (Name, DescribeSensor, ValueSensor, TotalStorageSize, CreationTime) VALUES ({placeholders}, ?)', data + [str(datetime.datetime.now())])
    conn.commit()

@app.route('/')
def index():
    conn = sqlite3.connect('system_info.db')
    cursor = conn.cursor()
    cursor.execute("SELECT name FROM sqlite_master WHERE type='table';")
    tables = cursor.fetchall()

    cursor.close()
    conn.close()

    return render_template('index.html', tables=tables)

@app.route('/table/<table_name>')
def view_table(table_name):
    conn = sqlite3.connect('system_info.db')
    cursor = conn.cursor()
    limit = 70
    cursor.execute(f"SELECT * FROM {table_name} ORDER BY id DESC LIMIT {limit}")
    data = cursor.fetchall()
    cursor.execute(f"PRAGMA table_info({table_name})")
    columns = [column[1] for column in cursor.fetchall()]

    cursor.close()
    conn.close()

    return render_template('index.html', table_name=table_name, data=data, columns=columns)


if __name__ == "__main__":
    create_tables()
    scheduler.add_job(fetch_stats, 'interval', seconds=5, misfire_grace_time=30, args=[HardwareHandle])
    scheduler.add_job(delete_sql_records, 'interval', weeks=1)
    scheduler.add_job(create_json_file, 'interval',  seconds=10, misfire_grace_time=30)
    scheduler.start()
    app.run()