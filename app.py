from flask import Flask, render_template, Response, jsonify
import cv2
import threading
import time
import re
import atexit

from detect_plate import detect_plate
from ocr_reader import read_text, warm_up
from database import save_bus_number, get_all_entries


app = Flask(__name__)

camera = None
latest_frame = None
frame_lock = threading.Lock()

# Vehicle currently shown to the camera.
active_plate = ""
last_plate_seen = 0

# Used to confirm a new plate twice before saving.
candidate_plate = ""
candidate_hits = 0

last_ocr_time = 0

OCR_INTERVAL = 0.6
PLATE_GONE_AFTER = 3


def clean_text(text):
    return re.sub(r"[^A-Z0-9]", "", text.upper())


def letters_only(value):
    fixes = {
        "0": "O",
        "1": "I",
        "2": "Z",
        "5": "S",
        "8": "B"
    }

    return "".join(fixes.get(char, char) for char in value)


def numbers_only(value):
    fixes = {
        "O": "0",
        "Q": "0",
        "D": "0",
        "I": "1",
        "L": "1",
        "Z": "2",
        "S": "5",
        "B": "8"
    }

    return "".join(fixes.get(char, char) for char in value)


def normalise_indian_plate(text):
    text = clean_text(text)

    # Expected format:
    # HR98AA0000
    # MH19EQ0009
    # HR99GX0777
    if len(text) != 10:
        return ""

    state = letters_only(text[:2])
    district = numbers_only(text[2:4])
    series = letters_only(text[4:6])
    number = numbers_only(text[6:10])

    if not (
        state.isalpha()
        and district.isdigit()
        and series.isalpha()
        and number.isdigit()
    ):
        return ""

    return state + district + series + number


def camera_loop():
    global camera
    global latest_frame
    global active_plate
    global last_plate_seen
    global candidate_plate
    global candidate_hits
    global last_ocr_time

    camera = cv2.VideoCapture(0, cv2.CAP_DSHOW)

    if not camera.isOpened():
        print("ERROR: Cannot open camera.")
        return

    camera.set(cv2.CAP_PROP_FRAME_WIDTH, 1280)
    camera.set(cv2.CAP_PROP_FRAME_HEIGHT, 720)
    camera.set(cv2.CAP_PROP_BUFFERSIZE, 1)

    print("Bus ANPR Camera Started")

    last_detection_time = 0
    latest_plate_crop = None

    while True:
        ret, frame = camera.read()

        if not ret:
            time.sleep(0.1)
            continue

        display_frame = frame.copy()
        current_time = time.time()

        # Check for a visible plate five times per second.
        if current_time - last_detection_time >= 0.2:
            last_detection_time = current_time

            plates = detect_plate(frame)

            if plates:
                latest_plate_crop = plates[0]
                last_plate_seen = current_time

        # Keep checking OCR even after the first vehicle.
        # This allows a different upcoming vehicle to be stored.
        if (
            latest_plate_crop is not None
            and current_time - last_plate_seen < 0.5
            and current_time - last_ocr_time >= OCR_INTERVAL
        ):
            last_ocr_time = current_time

            text = normalise_indian_plate(
                read_text(latest_plate_crop)
            )

            if text:
                # Same vehicle remains in view: no duplicate row.
                if text == active_plate:
                    candidate_plate = ""
                    candidate_hits = 0

                # Different vehicle: require two matching OCR reads.
                else:
                    if text == candidate_plate:
                        candidate_hits += 1
                    else:
                        candidate_plate = text
                        candidate_hits = 1

                    if candidate_hits >= 2:
                        status = save_bus_number(text)

                        active_plate = text
                        candidate_plate = ""
                        candidate_hits = 0

                        print("Detected:", text, "-", status)

        # Display the saved active plate on the camera.
        if active_plate:
            cv2.putText(
                display_frame,
                "Bus: " + active_plate,
                (20, 40),
                cv2.FONT_HERSHEY_SIMPLEX,
                1,
                (0, 255, 0),
                2
            )

        # Clears the active vehicle after no plate is visible for 3 seconds.
        if (
            active_plate
            and current_time - last_plate_seen > PLATE_GONE_AFTER
        ):
            print("Vehicle left camera:", active_plate)

            active_plate = ""
            candidate_plate = ""
            candidate_hits = 0
            latest_plate_crop = None

        success, buffer = cv2.imencode(".jpg", display_frame)

        if success:
            with frame_lock:
                latest_frame = buffer.tobytes()


def generate_frames():
    while True:
        with frame_lock:
            frame = latest_frame

        if frame is None:
            time.sleep(0.1)
            continue

        yield (
            b"--frame\r\n"
            b"Content-Type: image/jpeg\r\n\r\n"
            + frame
            + b"\r\n"
        )

        time.sleep(0.03)


@app.route("/")
def dashboard():
    return render_template("dashboard.html")


@app.route("/health")
def health():
    return "OK"


@app.route("/video_feed")
def video_feed():
    return Response(
        generate_frames(),
        mimetype="multipart/x-mixed-replace; boundary=frame"
    )


@app.route("/api/records")
def records():
    data = get_all_entries()
    grouped = {}

    for bus_number, entry_time, status in data:
        date_key = entry_time.strftime("%Y-%m-%d")

        if date_key not in grouped:
            grouped[date_key] = []

        grouped[date_key].append({
            "bus_number": bus_number,
            "time": entry_time.strftime("%I:%M:%S %p"),
            "status": status
        })

    result = []

    for date_key in list(grouped.keys())[:10]:
        date_object = time.strptime(date_key, "%Y-%m-%d")

        result.append({
            "date": time.strftime("%d %B %Y", date_object),
            "records": grouped[date_key]
        })

    return jsonify(result)


def start_camera():
    threading.Thread(target=warm_up, daemon=True).start()

    threading.Thread(
        target=camera_loop,
        daemon=True
    ).start()


def cleanup():
    global camera

    if camera is not None:
        camera.release()


atexit.register(cleanup)


if __name__ == "__main__":
    start_camera()

    app.run(
        host="127.0.0.1",
        port=5000,
        debug=False,
        threaded=True
    )