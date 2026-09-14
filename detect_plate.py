import cv2

plate_cascade = cv2.CascadeClassifier(
    cv2.data.haarcascades + "haarcascade_russian_plate_number.xml"
)

if plate_cascade.empty():
    raise RuntimeError("Could not load number-plate Haar cascade.")


def is_valid_box(x, y, w, h, image_width, image_height):
    if w < 60 or h < 18:
        return False

    ratio = w / float(h)

    # Normal single-line Indian plates are usually wide rectangles.
    if ratio < 2.0 or ratio > 7.5:
        return False

    if w > image_width * 0.95 or h > image_height * 0.45:
        return False

    return True


def crop_plate(frame, x, y, w, h):
    height, width = frame.shape[:2]

    pad_x = int(w * 0.10)
    pad_y = int(h * 0.25)

    x1 = max(0, x - pad_x)
    y1 = max(0, y - pad_y)
    x2 = min(width, x + w + pad_x)
    y2 = min(height, y + h + pad_y)

    return frame[y1:y2, x1:x2]


def detect_plate(frame):
    if frame is None or frame.size == 0:
        return []

    original_height, original_width = frame.shape[:2]

    # Fast detection image; crop still comes from the original clear frame.
    detection_width = 720
    scale = min(1.0, detection_width / original_width)

    if scale < 1.0:
        small = cv2.resize(
            frame,
            (int(original_width * scale), int(original_height * scale)),
            interpolation=cv2.INTER_AREA
        )
    else:
        small = frame

    gray = cv2.cvtColor(small, cv2.COLOR_BGR2GRAY)

    # Better in poor lighting and mild blur.
    enhanced = cv2.createCLAHE(
        clipLimit=2.0,
        tileGridSize=(8, 8)
    ).apply(gray)

    detected = []

    # Try both normal and contrast-improved images.
    for image in (gray, enhanced):
        plates = plate_cascade.detectMultiScale(
            image,
            scaleFactor=1.08,
            minNeighbors=4,
            minSize=(60, 18),
            maxSize=(360, 150)
        )

        for x, y, w, h in plates:
            if not is_valid_box(
                x, y, w, h,
                small.shape[1],
                small.shape[0]
            ):
                continue

            detected.append((x, y, w, h))

    if not detected:
        return []

    # Prefer the largest valid Haar detection.
    x, y, w, h = max(detected, key=lambda box: box[2] * box[3])

    inverse_scale = 1.0 / scale

    x = int(x * inverse_scale)
    y = int(y * inverse_scale)
    w = int(w * inverse_scale)
    h = int(h * inverse_scale)

    plate = crop_plate(frame, x, y, w, h)

    return [plate] if plate.size > 0 else []