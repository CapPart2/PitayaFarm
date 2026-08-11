"""Real-time dragonfruit maturity detection from webcam or Android IP camera.

Usage examples (from project root):

    python yield_realtime_camera.py --source 0
    python yield_realtime_camera.py --source "http://PHONE_IP:PORT/video"

Requires the same YOLO weights and ultralytics setup as dashboard_api.py.
"""

import argparse
import os

import cv2
from ultralytics import YOLO

from dashboard_api import MODEL_PATHS


def load_yolo_model():
    for p in MODEL_PATHS:
        if os.path.exists(p):
            return YOLO(p)
    raise FileNotFoundError("No YOLO weights found in expected locations. Check Yield_detection folder.")


def main(source):
    model = load_yolo_model()
    names = getattr(model, "names", {}) or {}
    mature_ids = {i for i, n in names.items() if str(n).strip().lower() == "mature"}
    if not mature_ids:
        mature_ids = {0}

    cap = cv2.VideoCapture(source)
    if not cap.isOpened():
        raise RuntimeError(f"Could not open video source: {source}")

    total_ids = set()

    while True:
        ret, frame = cap.read()
        if not ret:
            break

        results = model.track(frame, conf=0.25, persist=True, verbose=False)
        annotated = frame
        for r in results:
            boxes = getattr(r, "boxes", None)
            if boxes is None or len(boxes) == 0:
                continue
            clss = boxes.cls.tolist()
            ids = boxes.id.tolist() if getattr(boxes, "id", None) is not None else [None] * len(clss)
            for box, cls_id, track_id in zip(boxes.xyxy.tolist(), clss, ids):
                x1, y1, x2, y2 = map(int, box)
                label = str(names.get(int(cls_id), int(cls_id)))
                color = (0, 255, 0)
                if int(cls_id) in mature_ids:
                    color = (255, 0, 0)
                    if track_id is not None:
                        total_ids.add(int(track_id))
                cv2.rectangle(annotated, (x1, y1), (x2, y2), color, 2)
                cv2.putText(
                    annotated,
                    label,
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
