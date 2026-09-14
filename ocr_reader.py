import threading
import cv2
import easyocr

_reader = None
_reader_lock = threading.Lock()


def get_reader():
    global _reader

    with _reader_lock:
        if _reader is None:
            print("Loading OCR...")
            _reader = easyocr.Reader(
                ["en"],
                gpu=False,
                verbose=False
            )
            print("OCR ready.")

    return _reader


def warm_up():
    get_reader()


def read_text(image):
    if image is None or image.size == 0:
        return ""

    height, width = image.shape[:2]

    # Clear enough for OCR without making the crop unnecessarily huge.
    if width < 400:
        scale = 400 / width

        image = cv2.resize(
            image,
            None,
            fx=scale,
            fy=scale,
            interpolation=cv2.INTER_CUBIC
        )

    gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)

    gray = cv2.createCLAHE(
        clipLimit=2.0,
        tileGridSize=(8, 8)
    ).apply(gray)

    soft = cv2.GaussianBlur(gray, (0, 0), 1.2)

    prepared = cv2.addWeighted(
        gray,
        1.6,
        soft,
        -0.6,
        0
    )

    # readtext() is the compatible and reliable EasyOCR method.
    results = get_reader().readtext(
        prepared,
        detail=1,
        paragraph=False,
        decoder="greedy",
        allowlist="ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789"
    )

    if not results:
        return ""

    results.sort(
        key=lambda item: min(point[0] for point in item[0])
    )

    text = ""

    for _, detected_text, confidence in results:
        if confidence >= 0.25:
            text += "".join(
                character
                for character in detected_text.upper()
                if character.isalnum()
            )

    return text