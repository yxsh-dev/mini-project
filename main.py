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
