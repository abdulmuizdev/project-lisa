from datetime import datetime
from pathlib import Path

import cv2

CAPTURE_KEY = ord("s")
QUIT_KEYS = {ord("q"), 27}
CAMERA_INDEX = 0
OUTPUT_DIR = Path("captures")
WINDOW_NAME = "Webcam"


def main() -> None:
    OUTPUT_DIR.mkdir(exist_ok=True)

    cap = cv2.VideoCapture(CAMERA_INDEX)
    if not cap.isOpened():
        raise SystemExit(
            f"Could not open camera at index {CAMERA_INDEX}. "
            "Check permissions or try a different CAMERA_INDEX."
        )

    print("Press 's' to capture, 'q' or ESC to quit.")

    try:
        while True:
            ret, frame = cap.read()
            if not ret:
                continue

            frame = cv2.flip(frame, 1)

            cv2.imshow(WINDOW_NAME, frame)
            key = cv2.waitKey(1) & 0xFF

            if key == CAPTURE_KEY:
                filename = OUTPUT_DIR / f"capture_{datetime.now():%Y%m%d_%H%M%S}.jpg"
                cv2.imwrite(str(filename), frame)
                print(f"Saved {filename}")

            if key in QUIT_KEYS:
                break
    finally:
        cap.release()
        cv2.destroyAllWindows()


if __name__ == "__main__":
    main()
