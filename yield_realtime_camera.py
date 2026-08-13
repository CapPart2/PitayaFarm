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

from dashboard_api import (
    MODEL_PATHS,
    get_mature_class_ids,
    has_pitaya_fruit_context,
    is_video_mature_fruit,
    validate_dragonfruit_maturity_scene,
)


def load_yolo_model():
    for p in MODEL_PATHS:
        if os.path.exists(p):
            return YOLO(p)
    raise FileNotFoundError("No YOLO weights found in expected locations. Check Yield_detection folder.")


def main(source):
    model = load_yolo_model()
    names = getattr(model, "names", {}) or {}
    # Never assume class 0 means mature: in a generic YOLO model it is a
    # person, so that fallback created false fruit detections.
    mature_ids = get_mature_class_ids(model)

    cap = cv2.VideoCapture(source)
    if not cap.isOpened():
        raise RuntimeError(f"Could not open video source: {source}")

    total_ids = set()

    while True:
        ret, frame = cap.read()
        if not ret:
            break

        results = model.track(frame, conf=0.55, persist=True, verbose=False)
        annotated = frame
        scene_is_valid = validate_dragonfruit_maturity_scene(frame).get("valid", False)
        for r in results:
            boxes = getattr(r, "boxes", None)
            if boxes is None or len(boxes) == 0:
                continue
            clss = boxes.cls.tolist()
            ids = boxes.id.tolist() if getattr(boxes, "id", None) is not None else [None] * len(clss)
            for box, cls_id, track_id in zip(boxes.xyxy.tolist(), clss, ids):
                x1, y1, x2, y2 = map(int, box)
                if not (
                    scene_is_valid
                    and int(cls_id) in mature_ids
                    and is_video_mature_fruit(frame, box)
                    and has_pitaya_fruit_context(frame, x1, y1, x2 - x1, y2 - y1)
                ):
                    # Do not draw a box for a rejected object.  It is not a
                    # mature fruit and must not look like a detection.
                    continue

                label = "Mature fruit"
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
