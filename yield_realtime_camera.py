"""Real-time dragonfruit maturity detection from webcam or Android IP camera.

Usage examples (from project root):

    python yield_realtime_camera.py --source 0
    python yield_realtime_camera.py --source "http://PHONE_IP:PORT/video"

Requires the same YOLO weights and ultralytics setup as dashboard_api.py.
"""

import argparse
import cv2

from dashboard_api import (
    detect_focused_mature_fruits,
)


def main(source):
    cap = cv2.VideoCapture(source)
    if not cap.isOpened():
        raise RuntimeError(f"Could not open video source: {source}")

    total_ids = set()

    while True:
        ret, frame = cap.read()
        if not ret:
            break

        annotated = frame.copy()
        for detection in detect_focused_mature_fruits(frame, image_mode=True):
            x1, y1, x2, y2 = map(int, detection["box"])
            cx, cy = (x1 + x2) // 2, (y1 + y2) // 2
            # A stable centroid is sufficient for the standalone preview.
            # The browser and uploaded-video flows use their own multi-frame
            # trackers before saving a count.
            fruit_id = (round(cx / 24), round(cy / 24))
            total_ids.add(fruit_id)
            color = (255, 0, 0)
            cv2.rectangle(annotated, (x1, y1), (x2, y2), color, 2)
            cv2.putText(
                annotated,
                "Mature fruit",
                (x1, max(20, y1 - 10)),
                cv2.FONT_HERSHEY_SIMPLEX,
                0.6,
                color,
                2,
            )

        cv2.putText(
            annotated,
            f"Mature count: {len(total_ids)}",
            (10, 30),
            cv2.FONT_HERSHEY_SIMPLEX,
            1.0,
            (0, 255, 0),
            2,
        )

        cv2.imshow("Dragonfruit maturity (q to quit)", annotated)
        key = cv2.waitKey(1) & 0xFF
        if key == ord("q"):
            break

    cap.release()
    cv2.destroyAllWindows()


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--source", default="0", help="Webcam index (0) or IP camera URL")
    args = parser.parse_args()

    src = 0 if args.source.isdigit() else args.source
    main(src)
