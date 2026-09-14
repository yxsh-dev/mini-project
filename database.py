### `database.py`


import mysql.connector


def get_connection():
    return mysql.connector.connect(
        host="localhost",
        user="root",
        password="654321",
        database="bus_anpr"
    )


def save_bus_number(bus_number):

    conn = get_connection()
    cursor = conn.cursor()

    check_query = """
    SELECT status
    FROM bus_entries
    WHERE bus_number = %s
    ORDER BY entry_time DESC
    LIMIT 1
    """

    cursor.execute(check_query, (bus_number,))
    result = cursor.fetchone()

    if result is None:
        status = "Entry"
    elif result[0] == "Entry":
        status = "Exit"
    else:
        status = "Entry"

    insert_query = """
    INSERT INTO bus_entries (bus_number, status)
    VALUES (%s, %s)
    """

    cursor.execute(insert_query, (bus_number, status))
    conn.commit()

    cursor.close()
    conn.close()

    print(bus_number, "-", status)

    return status


def get_all_entries():

    conn = get_connection()
    cursor = conn.cursor()

    query = """
    SELECT bus_number, entry_time, status
    FROM bus_entries
    ORDER BY entry_time DESC
    """

    cursor.execute(query)
    data = cursor.fetchall()

    cursor.close()
    conn.close()

    return data




### `main.py`


import subprocess
import webbrowser
import time
import sys
import urllib.request


def wait_for_server():

    url = "http://127.0.0.1:5000/health"

    for _ in range(30):

        try:
            urllib.request.urlopen(url, timeout=1)
            return True

        except:
            time.sleep(1)

    return False


def main():

    print("Starting Bus ANPR System...")

    process = subprocess.Popen(
        [sys.executable, "app.py"]
    )

    if wait_for_server():

        print("Dashboard started.")
        print("Opening Chrome...")

        webbrowser.open_new("http://127.0.0.1:5000")

    else:

        print("Could not start dashboard.")
        process.terminate()
        return

    try:

        process.wait()

    except KeyboardInterrupt:

        print("\nStopping Bus ANPR System...")

        process.terminate()
        process.wait()

        print("System stopped.")


if __name__ == "__main__":
    main()
