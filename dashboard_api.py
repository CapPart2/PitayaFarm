# flake8: noqa
# Dashboard API Endpoints - Clean Version
# Flask API for database-driven dashboard charts

from flask import Flask, jsonify, request, send_file, send_from_directory
from flask_cors import CORS
from datetime import datetime, timedelta
import json
import csv
import io
import os
import uuid
from werkzeug.utils import secure_filename
from reportlab.lib.pagesizes import letter, A4
from reportlab.platypus import (
    SimpleDocTemplate,
    Paragraph,
    Spacer,
    Table,
    TableStyle,
    Image as RLImage,
)
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import inch
from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER, TA_LEFT

from database_models import db_manager

import base64
from PIL import Image, ImageDraw, ImageFont
import cv2
import numpy as np
import subprocess

# Lazy-load YOLO model when first used
MODEL = None
MODEL_PATHS = [
    "Yield_detection/runs/detect/dragonfruit_maturity5/weights/best.pt",
    "Yield_detection/runs/detect/dragonfruit_maturity5/weights/last.pt",
    "Yield_detection/yolov8n.pt",
]


def load_yolo_model():
    global MODEL
    if MODEL is not None:
        return MODEL
    try:
        from ultralytics import YOLO
    except Exception:
        raise RuntimeError(
            "ultralytics package not installed. Please pip install ultralytics and torch"
        )

    weight = None
    for p in MODEL_PATHS:
        if os.path.exists(p):
            weight = p
            break

    if weight is None:
        raise FileNotFoundError("No YOLO weights found in expected locations")

    MODEL = YOLO(weight)
    return MODEL


def detect_mature_fruits_hsv(frame_bgr):
    """Exact same HSV detection used for still image capture.
    Returns (annotated_bgr, mature_boxes, immature_boxes).
    mature_boxes / immature_boxes are lists of (x, y, w, h).
    """
    img_h, img_w = frame_bgr.shape[:2]
    img_hsv = cv2.cvtColor(frame_bgr, cv2.COLOR_BGR2HSV)

    lower_green = np.array([28, 70, 60])
    upper_green = np.array([80, 255, 255])
    lower_red1 = np.array([0, 85, 100])
    upper_red1 = np.array([12, 255, 255])
    lower_red2 = np.array([145, 85, 100])
    upper_red2 = np.array([180, 255, 255])

    mask_green = cv2.inRange(img_hsv, lower_green, upper_green)
    mask_red1 = cv2.inRange(img_hsv, lower_red1, upper_red1)
    mask_red2 = cv2.inRange(img_hsv, lower_red2, upper_red2)
    mask_pink = cv2.bitwise_or(mask_red1, mask_red2)

    kernel = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (5, 5))
    mask_green = cv2.morphologyEx(mask_green, cv2.MORPH_CLOSE, kernel)
    mask_pink = cv2.morphologyEx(mask_pink, cv2.MORPH_CLOSE, kernel)

    # Immature (green) detection disabled; only process pink/mature fruits.
    contours_pink, _ = cv2.findContours(
        mask_pink, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE
    )

    immature_boxes = []
    mature_boxes = []

    for cnt in contours_pink:
        area = cv2.contourArea(cnt)
        if area > 150:
            x, y, w_fruit, h_fruit = cv2.boundingRect(cnt)
            if not is_fully_mature_fruit(frame_bgr, (x, y, x + w_fruit, y + h_fruit)):
                continue
            mature_boxes.append((x, y, w_fruit, h_fruit))

    mature_boxes = suppress_overlapping_boxes(
        [(x, y, x + w_fruit, y + h_fruit) for x, y, w_fruit, h_fruit in mature_boxes]
    )
    mature_boxes = [(x1, y1, x2 - x1, y2 - y1) for x1, y1, x2, y2 in mature_boxes]

    annotated = frame_bgr.copy()
    for x, y, w_f, h_f in mature_boxes:
        # Draw mature fruits with blue boxes only (no text label)
        cv2.rectangle(annotated, (x, y), (x + w_f, y + h_f), (255, 0, 0), 3)

    return annotated, mature_boxes, immature_boxes


def box_iou(box_a, box_b):
    ax1, ay1, ax2, ay2 = map(float, box_a)
    bx1, by1, bx2, by2 = map(float, box_b)

    inter_x1 = max(ax1, bx1)
    inter_y1 = max(ay1, by1)
    inter_x2 = min(ax2, bx2)
    inter_y2 = min(ay2, by2)

    inter_w = max(0.0, inter_x2 - inter_x1)
    inter_h = max(0.0, inter_y2 - inter_y1)
    inter_area = inter_w * inter_h

    area_a = max(0.0, ax2 - ax1) * max(0.0, ay2 - ay1)
    area_b = max(0.0, bx2 - bx1) * max(0.0, by2 - by1)
    union_area = area_a + area_b - inter_area
    if union_area <= 0:
        return 0.0
    return inter_area / union_area


def suppress_overlapping_detections(detections, iou_threshold: float = 0.42):
    kept = []
    for detection in sorted(
        detections, key=lambda item: float(item.get("confidence", 0.0)), reverse=True
    ):
        if any(
            box_iou(detection["box"], other["box"]) >= iou_threshold for other in kept
        ):
            continue
        kept.append(detection)
    return kept


def suppress_overlapping_boxes(boxes, iou_threshold: float = 0.42):
    kept = []
    for box in boxes:
        if any(
            box_iou(
                (box[0], box[1], box[2], box[3]),
                (other[0], other[1], other[2], other[3]),
            )
            >= iou_threshold
            for other in kept
        ):
            continue
        kept.append(box)
    return kept


def is_fully_mature_fruit(frame_bgr, box):
    """Return True only when the box is uniformly mature across the fruit body."""
    x1, y1, x2, y2 = map(int, box)
    x1 = max(0, x1)
    y1 = max(0, y1)
    x2 = min(frame_bgr.shape[1], x2)
    y2 = min(frame_bgr.shape[0], y2)

    if x2 <= x1 or y2 <= y1:
        return False

    roi = frame_bgr[y1:y2, x1:x2]
    if roi.size == 0:
        return False

    roi_h, roi_w = roi.shape[:2]
    body = roi[int(roi_h * 0.25) : roi_h, int(roi_w * 0.12) : int(roi_w * 0.88)]
    if body.size == 0:
        return False

    box_area = float(roi.shape[0] * roi.shape[1])
    frame_area = float(frame_bgr.shape[0] * frame_bgr.shape[1])
    aspect_ratio = roi_w / float(max(roi_h, 1))

    if box_area < frame_area * 0.001 or box_area > frame_area * 0.18:
        return False
    if aspect_ratio < 0.45 or aspect_ratio > 2.1:
        return False

    hsv = cv2.cvtColor(body, cv2.COLOR_BGR2HSV)
    center = body[
        int(body.shape[0] * 0.2) : int(body.shape[0] * 0.8),
        int(body.shape[1] * 0.2) : int(body.shape[1] * 0.8),
    ]
    if center.size == 0:
        return False

    center_hsv = cv2.cvtColor(center, cv2.COLOR_BGR2HSV)

    body_area = float(body.shape[0] * body.shape[1])
    center_area = float(center.shape[0] * center.shape[1])

    red1 = cv2.inRange(hsv, np.array([0, 70, 80]), np.array([12, 255, 255]))
    red2 = cv2.inRange(hsv, np.array([145, 70, 80]), np.array([180, 255, 255]))
    green = cv2.inRange(hsv, np.array([28, 60, 50]), np.array([85, 255, 255]))
    center_red1 = cv2.inRange(
        center_hsv, np.array([0, 80, 90]), np.array([12, 255, 255])
    )
    center_red2 = cv2.inRange(
        center_hsv, np.array([145, 80, 90]), np.array([180, 255, 255])
    )

    top_half = body[: body.shape[0] // 2, :]
    bottom_half = body[body.shape[0] // 2 :, :]
    top_hsv = cv2.cvtColor(top_half, cv2.COLOR_BGR2HSV) if top_half.size else None
    bottom_hsv = (
        cv2.cvtColor(bottom_half, cv2.COLOR_BGR2HSV) if bottom_half.size else None
    )
    top_green_ratio = 1.0
    bottom_red_ratio = 0.0
    if top_hsv is not None:
        top_green = cv2.inRange(
            top_hsv, np.array([28, 60, 50]), np.array([85, 255, 255])
        )
        top_green_ratio = cv2.countNonZero(top_green) / float(
            top_half.shape[0] * top_half.shape[1]
        )
    if bottom_hsv is not None:
        bottom_red1 = cv2.inRange(
            bottom_hsv, np.array([0, 80, 90]), np.array([12, 255, 255])
        )
        bottom_red2 = cv2.inRange(
            bottom_hsv, np.array([145, 80, 90]), np.array([180, 255, 255])
        )
        bottom_red_ratio = (
            cv2.countNonZero(bottom_red1) + cv2.countNonZero(bottom_red2)
        ) / float(bottom_half.shape[0] * bottom_half.shape[1])

    red_mask = cv2.bitwise_or(red1, red2)
    red_mask = cv2.morphologyEx(
        red_mask, cv2.MORPH_OPEN, cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (3, 3))
    )
    num_labels, labels, stats, _ = cv2.connectedComponentsWithStats(
        red_mask, connectivity=8
    )
    largest_blob_ratio = 0.0
    if num_labels > 1:
        blob_areas = stats[1:, cv2.CC_STAT_AREA]
        largest_blob_ratio = (
            float(blob_areas.max()) / body_area if blob_areas.size else 0.0
        )

    red_ratio = (cv2.countNonZero(red1) + cv2.countNonZero(red2)) / body_area
    green_ratio = cv2.countNonZero(green) / body_area
    center_red_ratio = (
        cv2.countNonZero(center_red1) + cv2.countNonZero(center_red2)
    ) / center_area
    saturation_mean = float(np.mean(hsv[:, :, 1]))

    quadrant_hits = 0
    quadrants = [
        body[: body.shape[0] // 2, : body.shape[1] // 2],
        body[: body.shape[0] // 2, body.shape[1] // 2 :],
        body[body.shape[0] // 2 :, : body.shape[1] // 2],
        body[body.shape[0] // 2 :, body.shape[1] // 2 :],
    ]
    for quadrant in quadrants:
        if quadrant.size == 0:
            continue
        quadrant_hsv = cv2.cvtColor(quadrant, cv2.COLOR_BGR2HSV)
        q_red1 = cv2.inRange(
            quadrant_hsv, np.array([0, 80, 90]), np.array([12, 255, 255])
        )
        q_red2 = cv2.inRange(
            quadrant_hsv, np.array([145, 80, 90]), np.array([180, 255, 255])
        )
        q_green = cv2.inRange(
            quadrant_hsv, np.array([28, 60, 50]), np.array([85, 255, 255])
        )
        q_area = float(quadrant.shape[0] * quadrant.shape[1])
        q_red_ratio = (cv2.countNonZero(q_red1) + cv2.countNonZero(q_red2)) / q_area
        q_green_ratio = cv2.countNonZero(q_green) / q_area
        if q_red_ratio >= 0.10 and q_green_ratio <= 0.12:
            quadrant_hits += 1

    return (
        red_ratio >= 0.28
        and center_red_ratio >= 0.40
        and red_ratio >= green_ratio * 3.0
        and green_ratio <= 0.06
        and top_green_ratio <= 0.08
        and bottom_red_ratio >= 0.18
        and saturation_mean >= 76.0
        and largest_blob_ratio >= 0.10
        and quadrant_hits >= 3
    )


def count_mature_in_video(
    model, source, conf: float = 0.25, max_frames: int = 0
) -> dict:
    """Run YOLO tracking on a video/stream and count unique mature fruits.

    Args:
        model: Loaded YOLO model.
        source: Path/URL passed directly to model.track (file, webcam index, or IP stream).
        conf: Confidence threshold.
        max_frames: Optional safety limit; 0 means process full video.

    Returns:
        Dictionary with total unique mature fruits and metadata.
    """
    # Determine which class IDs correspond to "mature" in the model's names mapping
    names = getattr(model, "names", {}) or {}
    mature_class_ids = {
        i for i, n in names.items() if str(n).strip().lower() == "mature"
    }
    if not mature_class_ids:
        mature_class_ids = {0}

    unique_ids = set()
    frame_count = 0

    try:
        # Use built-in tracking so the same fruit keeps the same ID across frames
        results_iter = model.track(
            source=source,
            conf=conf,
            stream=True,
            verbose=False,
            save=False,
            show=False,
            persist=True,
        )
    except Exception as e:
        raise RuntimeError(f"YOLO tracking failed: {e}")

    for r in results_iter:
        frame_count += 1
        if max_frames and frame_count > max_frames:
            break

        boxes = getattr(r, "boxes", None)
        if boxes is None or len(boxes) == 0:
            continue

        xyxys = boxes.xyxy.tolist() if getattr(boxes, "xyxy", None) is not None else []
        clss = boxes.cls.tolist()
        ids = (
            boxes.id.tolist()
            if getattr(boxes, "id", None) is not None
            else [None] * len(clss)
        )
        frame_bgr = r.orig_img if getattr(r, "orig_img", None) is not None else None

        for index, (cls_id, track_id) in enumerate(zip(clss, ids)):
            if track_id is None:
                continue
            if int(cls_id) in mature_class_ids:
                if frame_bgr is not None and index < len(xyxys):
                    if not is_fully_mature_fruit(frame_bgr, xyxys[index]):
                        continue
                unique_ids.add(int(track_id))

    return {
        "total_mature_fruits": len(unique_ids),
        "frame_count": frame_count,
        "mature_class_ids": sorted(list(mature_class_ids)),
    }


def convert_to_browser_compatible_mp4(input_path: str, output_path: str) -> bool:
    """Convert video to H.264 MP4 format using ffmpeg for browser compatibility."""
    try:
        # Try to use ffmpeg to convert to H.264
        cmd = [
            "ffmpeg",
            "-y",  # Overwrite output file
            "-i",
            input_path,
            "-c:v",
            "libx264",  # H.264 codec
            "-preset",
            "fast",
            "-crf",
            "23",
            "-c:a",
            "aac",  # AAC audio codec
            "-movflags",
            "+faststart",  # Fast start for web streaming
            output_path,
        ]
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=300)
        if result.returncode == 0:
            return True
        else:
            print(f"ffmpeg conversion failed: {result.stderr}")
            return False
    except FileNotFoundError:
        print("ffmpeg not found, skipping conversion")
        return False
    except Exception as e:
        print(f"ffmpeg conversion error: {e}")
        return False


def annotate_video_and_count(
    model, source, output_path: str, conf: float = 0.4, method: str = "color"
) -> dict:
    """Process each frame with the same HSV detection used for still images (method='color'),
    OR with YOLO tracking (method='yolo').
    Writes an annotated video file and returns the maximum unique mature count seen in any frame.
    """
    names = getattr(model, "names", {}) or {}
    mature_class_ids = {
        i for i, n in names.items() if str(n).strip().lower() == "mature"
    }
    if not mature_class_ids:
        mature_class_ids = {0}

    unique_ids = set()
    frame_count = 0
    writer = None

    # Try to infer FPS and frame size from the original video when source is a file path
    fps = 20.0
    frame_size = None
    if isinstance(source, str) and os.path.exists(source):
        cap = cv2.VideoCapture(source)
        if cap.isOpened():
            cap_fps = cap.get(cv2.CAP_PROP_FPS)
            if cap_fps and cap_fps > 1e-2:
                fps = float(cap_fps)
            w = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
            h = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
            if w > 0 and h > 0:
                frame_size = (w, h)
        cap.release()

    # ── HSV color mode (same as image capture) ──────────────────────────────
    if method == "color":
        cap = cv2.VideoCapture(source)
        if not cap.isOpened():
            raise RuntimeError(f"Cannot open video source: {source}")
        if frame_size is None:
            w = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
            h = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
            if w > 0 and h > 0:
                frame_size = (w, h)

        max_mature_in_frame = 0  # peak count across all frames (avoids double-count)

        while True:
            ret, frame = cap.read()
            if not ret:
                break
            frame_count += 1

            if frame_size is None:
                fh, fw = frame.shape[:2]
                frame_size = (fw, fh)

            if writer is None:
                # Try different codecs for browser compatibility
                # First try H.264 (if available), then mp4v, then MJPG
                codecs_to_try = [
                    ("H264", "H264"),
                    ("mp4v", "mp4v"),
                    ("MJPG", "MJPG"),
                    ("XVID", "XVID"),
                ]
                for codec_name, fourcc_code in codecs_to_try:
                    try:
                        fourcc = cv2.VideoWriter_fourcc(*fourcc_code)
                        writer = cv2.VideoWriter(output_path, fourcc, fps, frame_size)
                        if writer is not None and writer.isOpened():
                            print(
                                f"Successfully initialized VideoWriter with codec: {codec_name}"
                            )
                            break
                    except Exception as e:
                        print(f"Failed to initialize codec {codec_name}: {e}")
                        continue

            annotated, mature_boxes, _ = detect_mature_fruits_hsv(frame)

            mature_boxes = [
                (x, y, w_fruit, h_fruit)
                for x, y, w_fruit, h_fruit in mature_boxes
                if is_fully_mature_fruit(frame, (x, y, x + w_fruit, y + h_fruit))
            ]

            # Running max: the largest number of mature fruits visible at once
            if len(mature_boxes) > max_mature_in_frame:
                max_mature_in_frame = len(mature_boxes)

            count_label = f"Mature fruit count: {max_mature_in_frame}"
            cv2.rectangle(
                annotated, (6, 6), (len(count_label) * 11 + 12, 36), (0, 0, 0), -1
            )
            cv2.putText(
                annotated,
                count_label,
                (10, 28),
                cv2.FONT_HERSHEY_SIMPLEX,
                0.7,
                (0, 255, 100),
                2,
                cv2.LINE_AA,
            )

            if writer is not None and writer.isOpened():
                writer.write(cv2.resize(annotated, frame_size))

        cap.release()
        if writer is not None:
            writer.release()

        # Convert to browser-compatible MP4 if ffmpeg is available
        browser_compatible_path = output_path
        temp_path = output_path + ".temp.mp4"
        if convert_to_browser_compatible_mp4(output_path, temp_path):
            # Replace original with converted version
            import shutil

            shutil.move(temp_path, output_path)
            browser_compatible_path = output_path

        return {
            "total_mature_fruits": max_mature_in_frame,
            "frame_count": frame_count,
            "mature_class_ids": [],
        }

    # ── YOLO tracking mode ───────────────────────────────────────────────────
    try:
        results_iter = model.track(
            source=source,
            conf=conf,
            iou=0.45,
            stream=True,
            verbose=False,
            save=False,
            show=False,
            persist=True,
        )
    except Exception as e:
        raise RuntimeError(f"YOLO tracking failed: {e}")

    for r in results_iter:
        orig = (
            r.orig_img.copy()
            if hasattr(r, "orig_img") and r.orig_img is not None
            else None
        )
        frame_count += 1
        if orig is None:
            continue

        if frame_size is None:
            fh, fw = orig.shape[:2]
            frame_size = (fw, fh)

        if writer is None:
            # Try different codecs for browser compatibility
            # First try H.264 (if available), then mp4v, then MJPG
            codecs_to_try = [
                ("H264", "H264"),
                ("mp4v", "mp4v"),
                ("MJPG", "MJPG"),
                ("XVID", "XVID"),
            ]
            for codec_name, fourcc_code in codecs_to_try:
                try:
                    fourcc = cv2.VideoWriter_fourcc(*fourcc_code)
                    writer = cv2.VideoWriter(output_path, fourcc, fps, frame_size)
                    if writer is not None and writer.isOpened():
                        print(
                            f"Successfully initialized VideoWriter with codec: {codec_name}"
                        )
                        break
                except Exception as e:
                    print(f"Failed to initialize codec {codec_name}: {e}")
                    continue
        if writer is None or not writer.isOpened():
            writer = None

        frame_area = (frame_size[0] * frame_size[1]) if frame_size else 1
        annotated = orig.copy()
        boxes = getattr(r, "boxes", None)
        if boxes is not None and len(boxes) > 0:
            xyxys = boxes.xyxy.tolist()
            confs_list = boxes.conf.tolist()
            clss = boxes.cls.tolist()
            ids = (
                boxes.id.tolist()
                if getattr(boxes, "id", None) is not None
                else [None] * len(clss)
            )
            for xyxy, box_conf, cls_id, track_id in zip(xyxys, confs_list, clss, ids):
                x1, y1, x2, y2 = map(int, xyxy)
                box_w = x2 - x1
                box_h = y2 - y1
                if frame_area > 0 and (box_w * box_h / frame_area) > 0.55:
                    continue
                if box_w < 20 or box_h < 20:
                    continue
                if not is_fully_mature_fruit(orig, (x1, y1, x2, y2)):
                    continue
                is_mature = int(cls_id) in mature_class_ids
                # Always draw detection boxes in blue for consistency
                color = (255, 0, 0)
                if is_mature and track_id is not None:
                    unique_ids.add(int(track_id))
                cv2.rectangle(annotated, (x1, y1), (x2, y2), color, 2)
                tid_str = f" id:{int(track_id)}" if track_id is not None else ""
                # Build label text without the class name to avoid showing 'MATURE'
                label = f"{tid_str.strip()} {box_conf:.2f}".strip()
                (tw, th), _ = cv2.getTextSize(label, cv2.FONT_HERSHEY_SIMPLEX, 0.55, 1)
                ly = max(y1 - 6, th + 4)
                cv2.rectangle(
                    annotated, (x1, ly - th - 4), (x1 + tw + 4, ly), color, -1
                )
                cv2.putText(
                    annotated,
                    label,
                    (x1 + 2, ly - 2),
                    cv2.FONT_HERSHEY_SIMPLEX,
                    0.55,
                    (255, 255, 255),
                    1,
                    cv2.LINE_AA,
                )

        # Summary label without the word 'mature'
        count_label = f"Fruit count: {len(unique_ids)}"
        cv2.rectangle(
            annotated, (6, 6), (len(count_label) * 11 + 12, 36), (0, 0, 0), -1
        )
        cv2.putText(
            annotated,
            count_label,
            (10, 28),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.7,
            (0, 255, 100),
            2,
            cv2.LINE_AA,
        )

        if writer is not None and writer.isOpened():
            writer.write(cv2.resize(annotated, frame_size))

    if writer is not None:
        writer.release()

    # Convert to browser-compatible MP4 if ffmpeg is available
    browser_compatible_path = output_path
    temp_path = output_path + ".temp.mp4"
    if convert_to_browser_compatible_mp4(output_path, temp_path):
        # Replace original with converted version
        import shutil

        shutil.move(temp_path, output_path)
        browser_compatible_path = output_path

    return {
        "total_mature_fruits": len(unique_ids),
        "frame_count": frame_count,
        "mature_class_ids": sorted(list(mature_class_ids)),
    }


app = Flask(__name__)
CORS(
    app,
    supports_credentials=True,
    origins="*",
    allow_headers=["Content-Type", "X-CSRFToken"],
    methods=["GET", "POST", "PUT", "DELETE", "OPTIONS"],
)


@app.route("/uploads/<path:filename>")
def serve_uploaded_file(filename):
    """Serve files from the uploads directory (images, annotated videos, etc.)."""
    upload_root = os.path.join(os.getcwd(), "uploads")

    # Determine MIME type based on file extension
    if filename.lower().endswith(".mp4"):
        return send_from_directory(upload_root, filename, mimetype="video/mp4")
    elif filename.lower().endswith(".avi"):
        return send_from_directory(upload_root, filename, mimetype="video/x-msvideo")
    elif filename.lower().endswith((".jpg", ".jpeg")):
        return send_from_directory(upload_root, filename, mimetype="image/jpeg")
    elif filename.lower().endswith(".png"):
        return send_from_directory(upload_root, filename, mimetype="image/png")
    else:
        return send_from_directory(upload_root, filename)


@app.route("/api/dashboard/health", methods=["GET"])
def health_check():
    """Health check endpoint"""
    return jsonify(
        {
            "success": True,
            "message": "Dashboard API is running",
            "timestamp": datetime.now().isoformat(),
        }
    )


@app.route("/api/library/", methods=["GET"])
def get_disease_library():
    """Get comprehensive disease library data"""
    try:
        import sqlite3

        conn = sqlite3.connect("pitaya_database.db")
        cursor = conn.cursor()

        # Get comprehensive disease library data
        cursor.execute("""
            SELECT disease_name, scientific_name, description, symptoms,
                   causes, prevention_methods, recommended_treatments,
                   image_path, severity_level, economic_impact,
                   description_tagalog, symptoms_tagalog, causes_tagalog,
                   prevention_methods_tagalog, recommended_treatments_tagalog
            FROM disease_library
            ORDER BY disease_name
        """)

        diseases = []
        for row in cursor.fetchall():
            try:
                # Special case for Stem Canker due to JSON parsing issues
                if row[0] == "Stem Canker":
                    disease = {
                        "name": row[0],
                        "scientific_name": row[1],
                        "description": row[2],
                        "symptoms": {
                            "visible_signs": [
                                "Deep and dark lesions on stems",
                                "Raised or cracked lesion edges",
                                "Lesions wrapping around stem blocking sap flow",
                                "Dieback of affected branches",
                                "Wilting and weakening of stem",
                                "Decline in plant vigor and yield",
                            ],
                            "color_changes": [
                                "Color changes from brown to black on lesions",
                                "Darkening of lesion edges",
                                "Yellowing of adjacent tissue",
                            ],
                            "lesions": "Deep, dark canker lesions with raised edges that may girdle the stem",
                            "abnormal_growth": "Dieback and cessation of normal growth",
                        },
                        "causes": {
                            "pathogen_type": "Fungal infection",
                            "causal_organism": "Colletotrichum spp. and related fungi",
                            "environmental_factors": [
                                "Hot and humid environment",
                                "Wounds from pruning or physical damage",
                                "Contaminated tools and cutting equipment",
                                "Poor air circulation around plants",
                            ],
                            "spread_methods": [
                                "Airborne spores",
                                "Water splash",
                                "Contaminated cutting tools",
                                "Plant wounds",
                            ],
                        },
                        "prevention_methods": {
                            "farm_sanitation": [
                                "Disinfect tools before each cut",
                                "Remove infected plant parts immediately",
                                "Use clean planting material",
                                "Maintain clean farm environment",
                            ],
                            "drainage_spacing": [
                                "Improve air circulation",
                                "Provide adequate spacing between plants",
                                "Avoid overcrowding of plants",
                                "Use trellis system for better ventilation",
                            ],
                            "cultural_practices": [
                                "Prune in dry conditions",
                                "Avoid pruning when wet or raining",
                                "Maintain plant health",
                                "Regularly monitor plants for disease",
                            ],
                            "preventive_spraying": [
                                "Apply copper-based fungicide as preventive measure",
                                "Use systemic fungicides for protection",
                                "Apply in early morning for best efficacy",
                                "Rotate fungicide classes to prevent resistance",
                            ],
                        },
                        "recommended_treatments": {
                            "approved_fungicides": [
                                {
                                    "product": "Copper-based fungicides",
                                    "dosage": "According to label",
                                    "frequency": "Every 7-10 days",
                                    "notes": "Preventive and curative for stem canker",
                                },
                                {
                                    "product": "Systemic fungicides",
                                    "dosage": "According to label",
                                    "frequency": "Every 14 days",
                                    "notes": "For systemic protection",
                                },
                            ],
                            "non_chemical_methods": [
                                "Biological control using beneficial microorganisms",
                                "Proper pruning techniques",
                                "Proper environment management",
                                "Organic fungicide solutions",
                            ],
                            "best_practices": [
                                "Immediately cut and remove affected stems",
                                "Disinfect tools before each cut",
                                "Apply copper-based or systemic fungicides as preventive and curative treatment",
                                "Improve air circulation and reduce humidity",
                                "Avoid pruning when wet or raining",
                                "Regularly observe plants for early detection of symptoms",
                            ],
                        },
                        "image_path": row[7],
                        "severity_level": row[8],
                        "economic_impact": row[9],
                        "description_tagalog": row[10]
                        or "Ang Stem Canker ay isang mapanganib na sakit na dulot ng Colletotrichum spp. na nagdudulot ng malalim at maitim na sugat sa mga tangkay ng dragon fruit. Nakakaapekto ito sa daloy ng sustansya sa loob ng halaman at maaaring humantong sa pagkatuyo at pagkamatay ng halaman kung hindi agad gagamutin.",
                        "symptoms_tagalog": {
                            "visible_signs": [
                                "Malalalim at maitim na sugat sa mga tangkay",
                                "May nakaangat o bitak-bitak na gilid ng sugat",
                                "Pagkapulupot ng sugat sa tangkay na humahadlang sa daloy ng katas",
                                "Pagkatuyo (dieback) ng mga apektadong sanga",
                                "Paglalanta at panghihina ng tangkay",
                                "Pagbaba ng sigla at ani ng halaman",
                            ],
                            "color_changes": [
                                "Pagbabago mula kayumanggi hanggang itim ng mga sugat",
                                "Paglala ng gilid ng mga sugat",
                                "Paninilaw ng mga katabing tisyu",
                            ],
                            "lesions": "Malalalim, maitim na sugat na may nakaangat na gilid na maaaring pumalibot sa tangkay",
                            "abnormal_growth": "Pagkatuyo (dieback) at paghinto sa normal na paglaki",
                        },
                        "causes_tagalog": {
                            "pathogen_type": "Impeksiyong dulot ng fungus",
                            "causal_organism": "Colletotrichum spp. at kaugnay na fungi",
                            "environmental_factors": [
                                "Mainit at mahalumigmig na kapaligiran",
                                "Mga sugat mula sa pruning o pisikal na pinsala",
                                "Kontaminadong kagamitan at gamit sa pagpuputol",
                                "Mahinang sirkulasyon ng hangin sa paligid ng halaman",
                            ],
                            "spread_methods": [
                                "Mga spores na dala ng hangin",
                                "Talsik ng tubig",
                                "Kontaminadong mga kagamitan sa pagpuputol",
                                "Mga sugat ng halaman",
                            ],
                        },
                        "prevention_methods_tagalog": {
                            "farm_sanitation": [
                                "I-disinfect ang mga kagamitan sa bawat pagputol",
                                "Alisin ang mga nahawaang bahagi ng halaman kaagad",
                                "Gumamit ng malinis na planting material",
                                "Panatilihin ang malinis na kapaligiran",
                            ],
                            "drainage_spacing": [
                                "Pagandahin ang sirkulasyon ng hangin",
                                "Magbigay ng sapat na pagitan sa pagitan ng mga halaman",
                                "Iwasan ang overcrowding ng mga tanim",
                                "Gamitin ang trellis system para sa mas maayos na bentilasyon",
                            ],
                            "cultural_practices": [
                                "Mag-prune sa tuyo na kondisyon",
                                "Iwasan ang pagprune kapag basa o umuulan",
                                "Panatilihin ang kalusugan ng halaman",
                                "Regular na bantayan ang halaman para sa mga sakit",
                            ],
                            "preventive_spraying": [
                                "Mag-apply ng copper-based fungicide bilang pang-iwas",
                                "Gamitin ang mga systemic fungicide para sa proteksyon",
                                "Mag-apply sa maagang umaga para sa mas epektibong paggamot",
                                "I-rotate ang mga klase ng fungicide upang maiwasan ang resistance",
                            ],
                        },
                        "recommended_treatments_tagalog": {
                            "approved_fungicides": [
                                {
                                    "product": "Copper-based fungicides",
                                    "dosage": "Ayon sa label",
                                    "frequency": "Bawat 7-10 araw",
                                    "notes": "Pang-iwas at paggamot laban sa stem canker",
                                },
                                {
                                    "product": "Systemic fungicides",
                                    "dosage": "Ayon sa label",
                                    "frequency": "Bawat 14 araw",
                                    "notes": "Para sa panloob na proteksyon",
                                },
                            ],
                            "non_chemical_methods": [
                                "Biological control gamit ang mga beneficial microorganisms",
                                "Proper pruning techniques",
                                "Maayos na pamamahala ng kapaligiran",
                                "Organic fungicide solutions",
                            ],
                            "best_practices": [
                                "Agad putulin at alisin ang mga apektadong tangkay",
                                "I-disinfect ang mga kagamitan sa bawat pagputol",
                                "Mag-apply ng copper-based o systemic fungicides bilang pang-iwas at paggamot",
                                "Pagandahin ang sirkulasyon ng hangin at bawasan ang halumigmig",
                                "Iwasan ang pruning kapag basa o umuulan",
                                "Regular na obserbahan ang halaman para sa maagang pagtuklas ng sintomas",
                            ],
                        },
                    }
                else:
                    disease = {
                        "name": row[0],
                        "scientific_name": row[1],
                        "description": row[2],
                        "symptoms": (
                            json.loads(row[3]) if row[3] and row[3].strip() else {}
                        ),
                        "causes": (
                            json.loads(row[4]) if row[4] and row[4].strip() else {}
                        ),
                        "prevention_methods": (
                            json.loads(row[5]) if row[5] and row[5].strip() else {}
                        ),
                        "recommended_treatments": (
                            json.loads(row[6]) if row[6] and row[6].strip() else {}
                        ),
                        "image_path": row[7],
                        "severity_level": row[8],
                        "economic_impact": row[9],
                        "description_tagalog": row[10],
                        "symptoms_tagalog": (
                            json.loads(row[11]) if row[11] and row[11].strip() else {}
                        ),
                        "causes_tagalog": (
                            json.loads(row[12]) if row[12] and row[12].strip() else {}
                        ),
                        "prevention_methods_tagalog": (
                            json.loads(row[13]) if row[13] and row[13].strip() else {}
                        ),
                        "recommended_treatments_tagalog": (
                            json.loads(row[14]) if row[14] and row[14].strip() else {}
                        ),
                    }
                diseases.append(disease)
            except json.JSONDecodeError as e:
                print(f"JSON decode error for {row[0]}: {e}")
                # Skip this disease or use empty dict
                disease = {
                    "name": row[0],
                    "scientific_name": row[1],
                    "description": row[2],
                    "symptoms": {},
                    "causes": {},
                    "prevention_methods": {},
                    "recommended_treatments": {},
                    "image_path": row[7],
                    "severity_level": row[8],
                    "economic_impact": row[9],
                    "description_tagalog": row[10],
                    "symptoms_tagalog": {},
                    "causes_tagalog": {},
                    "prevention_methods_tagalog": {},
                    "recommended_treatments_tagalog": {},
                }
                diseases.append(disease)

        conn.close()

        return jsonify(
            {
                "success": True,
                "data": diseases,
                "count": len(diseases),
                "source": "comprehensive_disease_library",
                "educational_purpose": "Reference module for dragon fruit diseases",
            }
        )
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500


@app.route("/api/library/<path:disease_name>", methods=["GET"])
@app.route("/api/library/<path:disease_name>/", methods=["GET"])
def get_disease_library_detail(disease_name):
    """Get a single disease record by name (for Alert Details / Library deep links)."""
    try:
        import sqlite3

        conn = sqlite3.connect("pitaya_database.db")
        cursor = conn.cursor()

        # Normalize disease name: replace underscores with spaces
        normalized_name = disease_name.replace("_", " ")

        cursor.execute(
            """
            SELECT disease_name, scientific_name, description, symptoms,
                   causes, prevention_methods, recommended_treatments,
                   image_path, severity_level, economic_impact,
                   description_tagalog, symptoms_tagalog, causes_tagalog,
                   prevention_methods_tagalog, recommended_treatments_tagalog
            FROM disease_library
            WHERE disease_name = ? COLLATE NOCASE
            LIMIT 1
            """,
            (normalized_name,),
        )
        row = cursor.fetchone()
        conn.close()

        if not row:
            return jsonify({"success": False, "error": "Disease not found"}), 404

        try:
            if row[0] == "Stem Canker":
                disease = {
                    "name": row[0],
                    "scientific_name": row[1],
                    "description": row[2],
                    "symptoms": {
                        "visible_signs": [
                            "Deep and dark lesions on stems",
                            "Raised or cracked lesion edges",
                            "Lesions wrapping around stem blocking sap flow",
                            "Dieback of affected branches",
                            "Wilting and weakening of stem",
                            "Decline in plant vigor and yield",
                        ],
                        "color_changes": [
                            "Color changes from brown to black on lesions",
                            "Darkening of lesion edges",
                            "Yellowing of adjacent tissue",
                        ],
                        "lesions": "Deep, dark canker lesions with raised edges that may girdle the stem",
                        "abnormal_growth": "Dieback and cessation of normal growth",
                    },
                    "causes": {
                        "pathogen_type": "Fungal infection",
                        "causal_organism": "Colletotrichum spp. and related fungi",
                        "environmental_factors": [
                            "Hot and humid environment",
                            "Wounds from pruning or physical damage",
                            "Contaminated tools and cutting equipment",
                            "Poor air circulation around plants",
                        ],
                        "spread_methods": [
                            "Airborne spores",
                            "Water splash",
                            "Contaminated cutting tools",
                            "Plant wounds",
                        ],
                    },
                    "prevention_methods": {
                        "farm_sanitation": [
                            "Disinfect tools before each cut",
                            "Remove infected plant parts immediately",
                            "Use clean planting material",
                            "Maintain clean farm environment",
                        ],
                        "drainage_spacing": [
                            "Improve air circulation",
                            "Provide adequate spacing between plants",
                            "Avoid overcrowding of plants",
                            "Use trellis system for better ventilation",
                        ],
                        "cultural_practices": [
                            "Prune in dry conditions",
                            "Avoid pruning when wet or raining",
                            "Maintain plant health",
                            "Regularly monitor plants for disease",
                        ],
                        "preventive_spraying": [
                            "Apply copper-based fungicide as preventive measure",
                            "Use systemic fungicides for protection",
                            "Apply in early morning for best efficacy",
                            "Rotate fungicide classes to prevent resistance",
                        ],
                    },
                    "recommended_treatments": {
                        "approved_fungicides": [
                            {
                                "product": "Copper-based fungicides",
                                "dosage": "According to label",
                                "frequency": "Every 7-10 days",
                                "notes": "Preventive and curative for stem canker",
                            },
                            {
                                "product": "Systemic fungicides",
                                "dosage": "According to label",
                                "frequency": "Every 14 days",
                                "notes": "For systemic protection",
                            },
                        ],
                        "non_chemical_methods": [
                            "Biological control using beneficial microorganisms",
                            "Proper pruning techniques",
                            "Proper environment management",
                            "Organic fungicide solutions",
                        ],
                        "best_practices": [
                            "Immediately cut and remove affected stems",
                            "Disinfect tools before each cut",
                            "Apply copper-based or systemic fungicides as preventive and curative treatment",
                            "Improve air circulation and reduce humidity",
                            "Avoid pruning when wet or raining",
                            "Regularly observe plants for early detection of symptoms",
                        ],
                    },
                    "image_path": row[7],
                    "severity_level": row[8],
                    "economic_impact": row[9],
                    "description_tagalog": row[10]
                    or "Ang Stem Canker ay isang mapanganib na sakit na dulot ng Colletotrichum spp. na nagdudulot ng malalim at maitim na sugat sa mga tangkay ng dragon fruit. Nakakaapekto ito sa daloy ng sustansya sa loob ng halaman at maaaring humantong sa pagkatuyo at pagkamatay ng halaman kung hindi agad gagamutin.",
                    "symptoms_tagalog": {
                        "visible_signs": [
                            "Malalalim at maitim na sugat sa mga tangkay",
                            "May nakaangat o bitak-bitak na gilid ng sugat",
                            "Pagkapulupot ng sugat sa tangkay na humahadlang sa daloy ng katas",
                            "Pagkatuyo (dieback) ng mga apektadong sanga",
                            "Paglalanta at panghihina ng tangkay",
                            "Pagbaba ng sigla at ani ng halaman",
                        ],
                        "color_changes": [
                            "Pagbabago mula kayumanggi hanggang itim ng mga sugat",
                            "Paglala ng gilid ng mga sugat",
                            "Paninilaw ng mga katabing tisyu",
                        ],
                        "lesions": "Malalalim, maitim na sugat na may nakaangat na gilid na maaaring pumalibot sa tangkay",
                        "abnormal_growth": "Pagkatuyo (dieback) at paghinto sa normal na paglaki",
                    },
                    "causes_tagalog": {
                        "pathogen_type": "Impeksiyong dulot ng fungus",
                        "causal_organism": "Colletotrichum spp. at kaugnay na fungi",
                        "environmental_factors": [
                            "Mainit at mahalumigmig na kapaligiran",
                            "Mga sugat mula sa pruning o pisikal na pinsala",
                            "Kontaminadong kagamitan at gamit sa pagpuputol",
                            "Mahinang sirkulasyon ng hangin sa paligid ng halaman",
                        ],
                        "spread_methods": [
                            "Mga spores na dala ng hangin",
                            "Talsik ng tubig",
                            "Kontaminadong mga kagamitan sa pagpuputol",
                            "Mga sugat ng halaman",
                        ],
                    },
                    "prevention_methods_tagalog": {
                        "farm_sanitation": [
                            "I-disinfect ang mga kagamitan sa bawat pagputol",
                            "Alisin ang mga nahawaang bahagi ng halaman kaagad",
                            "Gumamit ng malinis na planting material",
                            "Panatilihin ang malinis na kapaligiran",
                        ],
                        "drainage_spacing": [
                            "Pagandahin ang sirkulasyon ng hangin",
                            "Magbigay ng sapat na pagitan sa pagitan ng mga halaman",
                            "Iwasan ang overcrowding ng mga tanim",
                            "Gamitin ang trellis system para sa mas maayos na bentilasyon",
                        ],
                        "cultural_practices": [
                            "Mag-prune sa tuyo na kondisyon",
                            "Iwasan ang pagprune kapag basa o umuulan",
                            "Panatilihin ang kalusugan ng halaman",
                            "Regular na bantayan ang halaman para sa mga sakit",
                        ],
                        "preventive_spraying": [
                            "Mag-apply ng copper-based fungicide bilang pang-iwas",
                            "Gamitin ang mga systemic fungicide para sa proteksyon",
                            "Mag-apply sa maagang umaga para sa mas epektibong paggamot",
                            "I-rotate ang mga klase ng fungicide upang maiwasan ang resistance",
                        ],
                    },
                    "recommended_treatments_tagalog": {
                        "approved_fungicides": [
                            {
                                "product": "Copper-based fungicides",
                                "dosage": "Ayon sa label",
                                "frequency": "Bawat 7-10 araw",
                                "notes": "Pang-iwas at paggamot laban sa stem canker",
                            },
                            {
                                "product": "Systemic fungicides",
                                "dosage": "Ayon sa label",
                                "frequency": "Bawat 14 araw",
                                "notes": "Para sa panloob na proteksyon",
                            },
                        ],
                        "non_chemical_methods": [
                            "Biological control gamit ang mga beneficial microorganisms",
                            "Proper pruning techniques",
                            "Maayos na pamamahala ng kapaligiran",
                            "Organic fungicide solutions",
                        ],
                        "best_practices": [
                            "Agad putulin at alisin ang mga apektadong tangkay",
                            "I-disinfect ang mga kagamitan sa bawat pagputol",
                            "Mag-apply ng copper-based o systemic fungicides bilang pang-iwas at paggamot",
                            "Pagandahin ang sirkulasyon ng hangin at bawasan ang halumigmig",
                            "Iwasan ang pruning kapag basa o umuulan",
                            "Regular na obserbahan ang halaman para sa maagang pagtuklas ng sintomas",
                        ],
                    },
                }
            else:
                disease = {
                    "name": row[0],
                    "scientific_name": row[1],
                    "description": row[2],
                    "symptoms": json.loads(row[3]) if row[3] and row[3].strip() else {},
                    "causes": json.loads(row[4]) if row[4] and row[4].strip() else {},
                    "prevention_methods": (
                        json.loads(row[5]) if row[5] and row[5].strip() else {}
                    ),
                    "recommended_treatments": (
                        json.loads(row[6]) if row[6] and row[6].strip() else {}
                    ),
                    "image_path": row[7],
                    "severity_level": row[8],
                    "economic_impact": row[9],
                    "description_tagalog": row[10],
                    "symptoms_tagalog": (
                        json.loads(row[11]) if row[11] and row[11].strip() else {}
                    ),
                    "causes_tagalog": (
                        json.loads(row[12]) if row[12] and row[12].strip() else {}
                    ),
                    "prevention_methods_tagalog": (
                        json.loads(row[13]) if row[13] and row[13].strip() else {}
                    ),
                    "recommended_treatments_tagalog": (
                        json.loads(row[14]) if row[14] and row[14].strip() else {}
                    ),
                }
        except json.JSONDecodeError as e:
            print(f"JSON decode error for {row[0]}: {e}")
            disease = {
                "name": row[0],
                "scientific_name": row[1],
                "description": row[2],
                "symptoms": {},
                "causes": {},
                "prevention_methods": {},
                "recommended_treatments": {},
                "image_path": row[7],
                "severity_level": row[8],
                "economic_impact": row[9],
                "description_tagalog": row[10],
                "symptoms_tagalog": {},
                "causes_tagalog": {},
                "prevention_methods_tagalog": {},
                "recommended_treatments_tagalog": {},
            }

        return jsonify({"success": True, "data": disease})
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500


@app.route("/api/csrf/", methods=["GET"])
def get_csrf_token():
    """Get CSRF token for form submissions"""
    try:
        # Generate a simple CSRF token
        import secrets

        token = secrets.token_urlsafe(32)

        return jsonify({"csrfToken": token, "timestamp": datetime.now().isoformat()})
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/api/dashboard/summary", methods=["GET"])
def get_dashboard_summary():
    """Get comprehensive dashboard summary data - Single Source of Truth"""
    try:
        # Use new data integrity methods
        metrics = db_manager.get_dashboard_metrics()
        alerts = db_manager.get_all_alerts_with_detections()
        yield_stats = db_manager.get_yield_statistics()

        # Count unread alerts
        unread_alerts = len([a for a in alerts if a["Status"] == "Unread"])

        # avg_confidence may already be stored as 0–100 percentage; round to 1 decimal
        avg_conf_pct = round(yield_stats["avg_confidence"], 1)

        data = {
            "totalDetections": metrics["total_detections"],
            "highSeverityCases": yield_stats[
                "high_severity_cases"
            ],  # Real data from database
            "unreadAlerts": unread_alerts,
            "avgConfidence": avg_conf_pct,  # Avg confidence of disease detections (%)
            "totalYieldRecords": yield_stats[
                "total_predictions"
            ],  # Total yield prediction records
            "totalFruits": yield_stats["total_fruits"],  # Sum of all predicted fruits
            "totalPredictions": yield_stats["total_predictions"],
            "diseaseDistribution": metrics["disease_distribution"],
            "severityDistribution": metrics["severity_distribution"],
        }

        return jsonify(
            {"success": True, "data": data, "timestamp": datetime.now().isoformat()}
        )
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500


@app.route("/api/dashboard/disease-stats", methods=["GET"])
def get_disease_statistics():
    """Get disease detection statistics"""
    try:
        stats = db_manager.get_disease_statistics()
        return jsonify(
            {"success": True, "data": stats, "timestamp": datetime.now().isoformat()}
        )
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500


@app.route("/api/dashboard/yield-stats", methods=["GET"])
def get_yield_statistics():
    """Get yield prediction statistics"""
    try:
        stats = db_manager.get_yield_statistics()
        return jsonify(
            {"success": True, "data": stats, "timestamp": datetime.now().isoformat()}
        )
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500


@app.route("/api/dashboard/yield-prediction", methods=["POST"])
def save_yield_prediction():
    """Save a yield detection result to the chart database"""
    try:
        body = request.get_json(force=True) or {}
        mature_fruits = body.get("mature_fruits")
        if mature_fruits is None:
            return (
                jsonify({"success": False, "error": "mature_fruits is required"}),
                400,
            )
        predicted_yield = float(mature_fruits)
        location = str(body.get("location", "Field"))
        season = body.get("season") or None
        upload_type = str(body.get("upload_type", "image"))
        new_id = db_manager.add_yield_prediction(
            predicted_yield=predicted_yield,
            location=location,
            season=season,
            upload_type=upload_type,
        )
        return jsonify(
            {
                "success": True,
                "id": new_id,
                "message": f"Saved {predicted_yield} kg to chart",
                "timestamp": datetime.now().isoformat(),
            }
        )
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500


@app.route("/api/dashboard/yield-predictions", methods=["GET"])
def list_yield_predictions():
    """List all yield prediction records for the Yield Report page"""
    try:
        records = db_manager.get_all_yield_predictions()
        return jsonify(
            {
                "success": True,
                "data": records,
                "count": len(records),
                "timestamp": datetime.now().isoformat(),
            }
        )
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500


@app.route("/api/dashboard/yield-predictions/<int:record_id>", methods=["DELETE"])
def delete_yield_prediction(record_id):
    """Delete a yield prediction record"""
    try:
        deleted = db_manager.delete_yield_prediction(record_id)
        if deleted:
            return jsonify({"success": True, "message": "Record deleted"})
        return jsonify({"success": False, "error": "Record not found"}), 404
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500


@app.route("/api/dashboard/yield-predictions/<int:record_id>/download", methods=["GET"])
def download_yield_prediction(record_id):
    """Download a single yield prediction record as CSV"""
    try:
        records = db_manager.get_all_yield_predictions()
        record = next((r for r in records if r["id"] == record_id), None)
        if not record:
            return jsonify({"success": False, "error": "Record not found"}), 404
        output = io.StringIO()
        writer = csv.writer(output)
        writer.writerow(
            [
                "ID",
                "Date",
                "Location/Block",
                "Fruits Detected (kg)",
                "Season",
                "Actual Yield",
                "Accuracy Score",
                "Created At",
            ]
        )
        writer.writerow(
            [
                record["id"],
                record["prediction_date"],
                record["location"],
                record["predicted_yield"],
                record["season"] or "",
                record["actual_yield"] or "",
                record["accuracy_score"] or "",
                record["created_at"],
            ]
        )
        output.seek(0)
        return send_file(
            io.BytesIO(output.getvalue().encode()),
            mimetype="text/csv",
            as_attachment=True,
            download_name=f"yield_report_{record_id}.csv",
        )
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500


@app.route("/api/dashboard/yield-predictions/download-all", methods=["GET"])
def download_all_yield_predictions():
    """Download all yield prediction records as CSV"""
    try:
        records = db_manager.get_all_yield_predictions()
        output = io.StringIO()
        writer = csv.writer(output)
        writer.writerow(
            [
                "ID",
                "Date",
                "Location/Block",
                "Fruits Detected (kg)",
                "Season",
                "Actual Yield",
                "Accuracy Score",
                "Created At",
            ]
        )
        for r in records:
            writer.writerow(
                [
                    r["id"],
                    r["prediction_date"],
                    r["location"],
                    r["predicted_yield"],
                    r["season"] or "",
                    r["actual_yield"] or "",
                    r["accuracy_score"] or "",
                    r["created_at"],
                ]
            )
        output.seek(0)
        return send_file(
            io.BytesIO(output.getvalue().encode()),
            mimetype="text/csv",
            as_attachment=True,
            download_name="yield_report_all.csv",
        )
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500


@app.route("/api/dashboard/alerts", methods=["GET"])
def get_alerts():
    """Get alerts for dashboard - Full History from Disease_Detections"""
    try:
        unread_only = request.args.get("unread_only", "false").lower() == "true"
        alerts = db_manager.get_all_alerts_with_detections()

        if unread_only:
            alerts = [alert for alert in alerts if alert["Status"] == "Unread"]

        return jsonify(
            {"success": True, "data": alerts, "timestamp": datetime.now().isoformat()}
        )
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500


@app.route("/api/dashboard/alerts/unread-count", methods=["GET"])
def get_unread_alert_count():
    """Get count of unread alerts"""
    try:
        count = db_manager.get_unread_alert_count()
        return jsonify(
            {
                "success": True,
                "data": {"count": count},
                "timestamp": datetime.now().isoformat(),
            }
        )
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500


@app.route("/api/dashboard/alerts/<int:alert_id>/read", methods=["POST"])
def mark_alert_read(alert_id):
    """Mark an alert as read - maintains 1:1 relationship"""
    try:
        success = db_manager.mark_alert_read(alert_id)
        if success:
            return jsonify({"success": True, "message": "Alert marked as read"})
        else:
            return jsonify({"success": False, "error": "Alert not found"}), 404
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500


@app.route("/api/dashboard/detections", methods=["GET"])
def get_all_detections():
    """Get all disease detections"""
    try:
        detections = db_manager.get_all_disease_detections()

        # Format the response
        formatted_detections = []
        for detection in detections:
            formatted_detections.append(
                {
                    "id": detection.get("DetectionID"),
                    "disease_type": detection.get("DiseaseType"),
                    "severity": detection.get("Severity"),
                    "confidence": detection.get("Confidence"),
                    "date_time": detection.get("DateTime"),
                    "location": detection.get("Location", "Unknown"),
                    "image_path": detection.get("ImagePath"),
                    "user_id": detection.get("UserID", "default_user"),
                    "created_at": detection.get("CreatedAt"),
                }
            )

        return jsonify(
            {
                "success": True,
                "data": formatted_detections,
                "count": len(formatted_detections),
                "timestamp": datetime.now().isoformat(),
            }
        )
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500


@app.route("/api/dashboard/reports", methods=["GET"])
def get_reports():
    """Get all reports - from Disease_Detections (Single Source of Truth)"""
    try:
        start_date = request.args.get("start_date")
        end_date = request.args.get("end_date")
        reports = db_manager.get_reports_data(start_date=start_date, end_date=end_date)
        return jsonify(
            {"success": True, "data": reports, "timestamp": datetime.now().isoformat()}
        )
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500


# Chart Endpoints
@app.route("/api/dashboard/charts/disease-distribution", methods=["GET"])
def get_disease_distribution_chart():
    """Get data for disease distribution chart - from Disease_Detections"""
    try:
        metrics = db_manager.get_dashboard_metrics()

        # Format data for Chart.js
        chart_data = {
            "labels": list(metrics["disease_distribution"].keys()),
            "datasets": [
                {
                    "label": "Disease Count",
                    "data": list(metrics["disease_distribution"].values()),
                    "backgroundColor": [
                        "#FF6384",
                        "#36A2EB",
                        "#FFCE56",
                        "#4BC0C0",
                        "#9966FF",
                        "#FF9F40",
                        "#FF6B6B",
                        "#4ECDC4",
                        "#95E1D3",
                    ],
                    "borderWidth": 2,
                    "borderColor": "#fff",
                }
            ],
        }

        return jsonify(
            {
                "success": True,
                "data": chart_data,
                "timestamp": datetime.now().isoformat(),
            }
        )
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500


@app.route("/api/dashboard/charts/severity-distribution", methods=["GET"])
def get_severity_distribution_chart():
    """Get data for severity distribution chart - from Disease_Detections"""
    try:
        metrics = db_manager.get_dashboard_metrics()

        # Format data for Chart.js
        chart_data = {
            "labels": list(metrics["severity_distribution"].keys()),
            "datasets": [
                {
                    "label": "Cases by Severity",
                    "data": list(metrics["severity_distribution"].values()),
                    "backgroundColor": [
                        "#FF6384",
                        "#FFCE56",
                        "#4BC0C0",
                    ],  # Red, Yellow, Green
                    "borderWidth": 2,
                }
            ],
        }

        return jsonify(
            {
                "success": True,
                "data": chart_data,
                "timestamp": datetime.now().isoformat(),
            }
        )
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500


@app.route("/api/dashboard/charts/yield-trend", methods=["GET"])
def get_yield_trend_chart():
    """Get data for yield trend chart - from yield predictions"""
    try:
        stats = db_manager.get_yield_statistics()

        # Format data for Chart.js
        chart_data = {
            "labels": [item["date"] for item in stats["yield_trend"]],
            "datasets": [
                {
                    "label": "Predicted Yield",
                    "data": [item["predicted"] for item in stats["yield_trend"]],
                    "borderColor": "#36A2EB",
                    "backgroundColor": "rgba(54, 162, 235, 0.1)",
                    "fill": True,
                    "tension": 0.4,
                },
                {
                    "label": "Actual Yield",
                    "data": [item["actual"] for item in stats["yield_trend"]],
                    "borderColor": "#4BC0C0",
                    "backgroundColor": "rgba(75, 192, 192, 0.1)",
                    "fill": True,
                    "tension": 0.4,
                },
            ],
        }

        return jsonify(
            {
                "success": True,
                "data": chart_data,
                "timestamp": datetime.now().isoformat(),
            }
        )
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500


@app.route("/api/dashboard/charts/daily-detections", methods=["GET"])
def get_daily_detections_chart():
    """Get data for daily detections trend chart - from Disease_Detections"""
    try:
        metrics = db_manager.get_dashboard_metrics()

        # Convert daily detections to list format
        daily_data = []
        for date, count in metrics["daily_detections"].items():
            daily_data.append({"date": date, "count": count})

        # Sort by date
        daily_data.sort(key=lambda x: x["date"])

        # Format data for Chart.js
        chart_data = {
            "labels": [item["date"] for item in daily_data],
            "datasets": [
                {
                    "label": "Daily Detections",
                    "data": [item["count"] for item in daily_data],
                    "borderColor": "#FF6384",
                    "backgroundColor": "rgba(255, 99, 132, 0.1)",
                    "fill": True,
                    "tension": 0.4,
                }
            ],
        }

        return jsonify(
            {
                "success": True,
                "data": chart_data,
                "timestamp": datetime.now().isoformat(),
            }
        )
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500


@app.route("/api/dashboard/integrity-check", methods=["GET"])
def verify_data_integrity():
    """Verify data integrity across all modules"""
    try:
        integrity_report = db_manager.verify_alert_detection_integrity()

        return jsonify(
            {
                "success": True,
                "data": integrity_report,
                "timestamp": datetime.now().isoformat(),
            }
        )
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500


@app.route("/api/dashboard/detections/<int:detection_id>", methods=["GET"])
def get_detection_details(detection_id):
    """Get detailed information for a specific detection"""
    try:
        # Get all detections to find the specific one
        detections = db_manager.get_all_disease_detections()

        # Find the detection with the matching ID
        detection = None
        for d in detections:
            if d.get("DetectionID") == detection_id:
                detection = d
                break

        if not detection:
            return jsonify({"success": False, "error": "Detection not found"}), 404

        # Get associated alert if exists
        alerts = db_manager.get_all_alerts_with_detections()
        alert = None
        for a in alerts:
            if a.get("DetectionID") == detection_id:
                alert = a
                break

        # Format the response
        response_data = {
            "success": True,
            "data": {
                "detection_id": detection.get("DetectionID"),
                "disease_type": detection.get("DiseaseType"),
                "severity": detection.get("Severity"),
                "confidence": detection.get("Confidence"),
                "date_time": detection.get("DateTime"),
                "location": detection.get("Location", "Unknown"),
                "image_path": detection.get("ImagePath"),
                "user_id": detection.get("UserID", "default_user"),
                "created_at": detection.get("CreatedAt"),
                "alert": alert if alert else None,
            },
            "timestamp": datetime.now().isoformat(),
        }

        return jsonify(response_data)

    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500


@app.route("/api/dashboard/detections/<detection_id>", methods=["DELETE"])
def delete_detection(detection_id):
    """Delete a disease detection record with cascade to alert"""
    try:
        # Try to match by DetectionID (integer) or session_id (string)
        detections = db_manager.get_all_disease_detections()
        target_detection = None

        for detection in detections:
            if str(detection["DetectionID"]) == str(detection_id) or detection.get(
                "session_id"
            ) == str(detection_id):
                target_detection = detection
                break

        if not target_detection:
            return jsonify({"success": False, "error": "Detection not found"}), 404

        # Delete all detections with the same session_id if it's a session-based deletion
        if target_detection.get("session_id") and str(
            target_detection["session_id"]
        ) == str(detection_id):
            session_id = target_detection["session_id"]
            deleted_count = 0
            for detection in detections:
                if detection.get("session_id") == session_id:
                    success = db_manager.delete_detection(detection["DetectionID"])
                    if success:
                        deleted_count += 1

            if deleted_count > 0:
                return jsonify(
                    {
                        "success": True,
                        "message": f"{deleted_count} detection(s) deleted successfully",
                        "timestamp": datetime.now().isoformat(),
                    }
                )
            else:
                return jsonify({"success": False, "error": "Detection not found"}), 404
        else:
            # Single detection deletion
            success = db_manager.delete_detection(target_detection["DetectionID"])
            if success:
                return jsonify(
                    {
                        "success": True,
                        "message": f"Detection {target_detection['DetectionID']} deleted successfully",
                        "timestamp": datetime.now().isoformat(),
                    }
                )
            else:
                return jsonify({"success": False, "error": "Detection not found"}), 404
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500


@app.route("/api/dashboard/detection-statistics", methods=["GET"])
def get_detection_statistics():
    """Get comprehensive detection statistics for all components"""
    try:
        stats = db_manager.get_detection_statistics()
        return jsonify(
            {"success": True, "data": stats, "timestamp": datetime.now().isoformat()}
        )
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500


import os
import glob


@app.route("/api/disease-images/<disease_name>", methods=["GET"])
def get_disease_images(disease_name):
    """Get additional images for a specific disease from oversample folders"""
    try:
        import sqlite3
        import random

        # Map disease names to folder names and fallback images
        folder_mapping = {
            "Anthracnose": "Anthracnose",
            "Stem Canker": "Stem_Canker",  # Updated from Black Rot
            "Black Spot": "Black Spot",  # Fixed: Black Spot should use Black Spot folder
            "Brown Spot": "Brown Spot",  # Fixed: Brown Spot should use Brown Spot folder
            "Root Rot": "Root Rot",
            "Soft Rot": "Soft Rot",
            "Stem Rot": "Stem Rot",
            "Twig Blight": "Twig Blight",
            "White Spot": "White Spot",
        }

        # Get the folder name for this disease
        folder_name = folder_mapping.get(disease_name, disease_name)

        # Look for images in the public folder served by Vite
        oversample_path = f"frontend/public/oversample/Leaf/{folder_name}"
        image_urls = []  # Initialize here

        if os.path.exists(oversample_path):
            # Get all image files
            image_extensions = ["*.jpg", "*.jpeg", "*.png", "*.webp"]
            image_paths = []
            for ext in image_extensions:
                image_paths.extend(glob.glob(os.path.join(oversample_path, ext)))

            # Sort and take first 5 images
            image_paths.sort()
            selected_images = image_paths[:5]

            # Convert to URLs - strip 'frontend/public' prefix since Vite serves it as web root
            for img_path in selected_images:
                relative_path = os.path.relpath(img_path).replace("\\", "/")
                # Remove 'frontend/public' prefix so URL works from browser
                if relative_path.startswith("frontend/public/"):
                    relative_path = relative_path[len("frontend/public") :]
                # Encode only spaces (not parentheses or other common chars)
                url_path = relative_path.replace(" ", "%20")
                image_urls.append(url_path)
        else:
            # Fallback to All Disease folder if no oversample images
            all_disease_path = "All Disease"
            if os.path.exists(all_disease_path):
                # Try to find matching image in All Disease folder
                image_extensions = ["jpg", "jpeg", "png", "webp"]
                found_images = []

                for ext in image_extensions:
                    # Try different naming patterns
                    patterns = [
                        f"{folder_name}.{ext}",
                        f"{folder_name}*.{ext}",
                        f'{disease_name.replace(" ", "").lower()}.{ext}',
                        f'{disease_name.replace(" ", "_").lower()}.{ext}',
                    ]

                    for pattern in patterns:
                        images = glob.glob(os.path.join(all_disease_path, pattern))
                        found_images.extend(images)

                # Remove duplicates and take first 5
                unique_images = list(set(found_images))[:5]
                for img_path in unique_images:
                    relative_path = os.path.relpath(img_path)
                    image_urls.append(f'/{relative_path.replace("\\", "/")}')

        return (
            jsonify(
                {
                    "success": True,
                    "data": {
                        "disease_name": disease_name,
                        "images": image_urls,
                        "count": len(image_urls),
                    },
                }
            ),
            200,
        )

    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500


@app.route("/api/dashboard/disease-library", methods=["GET"])
def get_disease_library_data():
    """Get disease data for library component with detection counts"""
    try:
        diseases = db_manager.get_disease_library_data()
        return jsonify(
            {"success": True, "data": diseases, "timestamp": datetime.now().isoformat()}
        )
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500


@app.route("/api/dashboard/reports/<report_id>/download", methods=["GET"])
def download_report(report_id):
    """Download a single report as CSV or PDF"""
    try:
        format_type = request.args.get("format", "csv").lower()

        # Get the specific detection data
        detections = db_manager.get_all_disease_detections()
        report_data = None

        # Try to match by DetectionID (integer) or session_id (string)
        for detection in detections:
            if str(detection["DetectionID"]) == str(report_id) or detection.get(
                "session_id"
            ) == str(report_id):
                report_data = detection
                break

        if not report_data:
            return jsonify({"success": False, "error": "Report not found"}), 404

        if format_type == "pdf":
            return generate_pdf_report(report_data, report_id)
        else:
            return generate_csv_report(report_data, report_id)

    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500


@app.route("/api/dashboard/reports/<report_id>/preview", methods=["GET"])
def preview_report(report_id):
    """Preview a single report as CSV or PDF content"""
    try:
        format_type = request.args.get("format", "csv").lower()

        # Get the specific detection data
        detections = db_manager.get_all_disease_detections()
        report_data = None

        # Try to match by DetectionID (integer) or session_id (string)
        for detection in detections:
            if str(detection["DetectionID"]) == str(report_id) or detection.get(
                "session_id"
            ) == str(report_id):
                report_data = detection
                break

        if not report_data:
            return jsonify({"success": False, "error": "Report not found"}), 404

        if format_type == "pdf":
            # For PDF preview, return base64 encoded content
            pdf_content = generate_pdf_content(report_data, report_id)
            return jsonify(
                {
                    "success": True,
                    "data": {
                        "content": pdf_content,
                        "format": "pdf",
                        "filename": f"disease_report_{report_id}.pdf",
                    },
                }
            )
        else:
            # For CSV preview, return text content
            csv_content = generate_csv_content(report_data, report_id)
            return jsonify(
                {
                    "success": True,
                    "data": {
                        "content": csv_content,
                        "format": "csv",
                        "filename": f"disease_report_{report_id}.csv",
                    },
                }
            )

    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500


def generate_csv_report(report_data, report_id):
    """Generate CSV report"""
    csv_content = io.StringIO()
    writer = csv.writer(csv_content)

    # Check if this is a session-based multi-detection
    session_id = report_data.get("session_id")
    if session_id:
        # Get all detections with this session_id
        detections = db_manager.get_all_disease_detections()
        session_detections = [
            d for d in detections if d.get("session_id") == session_id
        ]

        # Calculate combined values matching frontend logic
        disease_names = ", ".join([d["DiseaseType"] for d in session_detections])
        sum_confidence = sum([d["Confidence"] for d in session_detections])
        max_severity = (
            "high"
            if any(d["Severity"] == "high" for d in session_detections)
            else (
                "medium"
                if any(d["Severity"] == "medium" for d in session_detections)
                else "low"
            )
        )

        # Write header for combined report
        writer.writerow(
            [
                "Session ID",
                "Disease Names",
                "Severity",
                "Total Confidence",
                "Date Time",
                "Location",
                "Image Path",
            ]
        )

        # Write combined row
        writer.writerow(
            [
                session_id,
                disease_names,
                max_severity.upper(),
                f"{sum_confidence:.2f}%",
                report_data["DateTime"],
                report_data.get("Location", "Unknown"),
                report_data.get("ImagePath", ""),
            ]
        )

        # Add individual disease details
        writer.writerow([])
        writer.writerow(["Individual Disease Details:"])
        writer.writerow(["Detection ID", "Disease Type", "Severity", "Confidence"])

        for detection in session_detections:
            writer.writerow(
                [
                    detection["DetectionID"],
                    detection["DiseaseType"],
                    detection["Severity"].upper(),
                    f"{detection['Confidence']:.2f}%",
                ]
            )
    else:
        # Single detection
        writer.writerow(
            [
                "Detection ID",
                "Disease Type",
                "Severity",
                "Confidence",
                "Date Time",
                "Location",
                "Image Path",
            ]
        )

        writer.writerow(
            [
                report_data["DetectionID"],
                report_data["DiseaseType"],
                report_data["Severity"].upper(),
                f"{report_data['Confidence']:.2f}%",
                report_data["DateTime"],
                report_data.get("Location", "Unknown"),
                report_data.get("ImagePath", ""),
            ]
        )

    # Create response
    output = csv_content.getvalue()
    csv_content.close()

    return send_file(
        io.BytesIO(output.encode("utf-8")),
        mimetype="text/csv",
        as_attachment=True,
        download_name=f"disease_report_{report_id}.csv",
    )


def generate_csv_content(report_data, report_id):
    """Generate CSV content as string for preview"""
    csv_content = io.StringIO()
    writer = csv.writer(csv_content)

    # Write header
    writer.writerow(
        [
            "Detection ID",
            "Disease Type",
            "Severity",
            "Confidence",
            "Date Time",
            "Location",
        ]
    )

    # Write data
    writer.writerow(
        [
            report_data["DetectionID"],
            report_data["DiseaseType"],
            report_data["Severity"],
            report_data["Confidence"],
            report_data["DateTime"],
            report_data.get("Location", "Unknown"),
        ]
    )

    # Get content as string
    content = csv_content.getvalue()
    csv_content.close()

    return content


@app.route("/api/dashboard/yield-detect", methods=["POST"])
def yield_image_detect():
    """Upload an image and run YOLO detection (returns boxes, scores, labels and an annotated image as base64)"""
    try:
        # Accept multipart/form-data image file under key 'image'
        if "image" not in request.files:
            return (
                jsonify(
                    {
                        "success": False,
                        "error": "No image file provided (field name: image)",
                    }
                ),
                400,
            )

        img_file = request.files["image"]
        if img_file.filename == "":
            return jsonify({"success": False, "error": "Empty filename"}), 400

        filename = secure_filename(img_file.filename or "")
        save_dir = os.path.join("uploads", "yield")
        os.makedirs(save_dir, exist_ok=True)
        img_path = os.path.join(save_dir, f"{uuid.uuid4().hex}_{filename}")
        img_file.save(img_path)

        # optional confidence threshold
        conf = float(request.form.get("conf", 0.25))
        method = (request.form.get("method") or "yolo").lower()

        # If caller requests classic color-based detection, run it and return
        if method == "color":
            # Use classical color-based HSV detection (user-provided algorithm)
            img_bgr = cv2.imread(img_path)
            if img_bgr is None:
                return (
                    jsonify({"success": False, "error": "Failed to read saved image"}),
                    500,
                )

            img_h, img_w = img_bgr.shape[:2]
            img_hsv = cv2.cvtColor(img_bgr, cv2.COLOR_BGR2HSV)

            # Color ranges
            lower_green = np.array([28, 70, 60])
            upper_green = np.array([80, 255, 255])
            lower_red1 = np.array([0, 85, 100])
            upper_red1 = np.array([12, 255, 255])
            lower_red2 = np.array([145, 85, 100])
            upper_red2 = np.array([180, 255, 255])

            mask_green = cv2.inRange(img_hsv, lower_green, upper_green)
            mask_red1 = cv2.inRange(img_hsv, lower_red1, upper_red1)
            mask_red2 = cv2.inRange(img_hsv, lower_red2, upper_red2)
            mask_pink = cv2.bitwise_or(mask_red1, mask_red2)

            kernel = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (5, 5))
            mask_green = cv2.morphologyEx(mask_green, cv2.MORPH_CLOSE, kernel)
            mask_pink = cv2.morphologyEx(mask_pink, cv2.MORPH_CLOSE, kernel)

            # Immature (green) fruit detection disabled; only process pink/mature fruits.
            _, _ = cv2.findContours(
                mask_green, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE
            )
            contours_pink, _ = cv2.findContours(
                mask_pink, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE
            )

            immature_fruits = []
            mature_fruits = []

            for cnt in contours_pink:
                area = cv2.contourArea(cnt)
                if area > 150:
                    x, y, w_fruit, h_fruit = cv2.boundingRect(cnt)
                    if is_fully_mature_fruit(img_bgr, (x, y, x + w_fruit, y + h_fruit)):
                        mature_fruits.append((x, y, w_fruit, h_fruit))

            mature_boxes = suppress_overlapping_boxes(
                [
                    (x, y, x + w_fruit, y + h_fruit)
                    for x, y, w_fruit, h_fruit in mature_fruits
                ]
            )
            mature_fruits = [
                (x1, y1, x2 - x1, y2 - y1) for x1, y1, x2, y2 in mature_boxes
            ]

            # Draw boxes on BGR image
            annotated_bgr = img_bgr.copy()
            detections = []
            for x, y, w_fruit, h_fruit in mature_fruits:
                # Draw mature fruits in blue, but do not render the 'MATURE' text on the image
                cv2.rectangle(
                    annotated_bgr, (x, y), (x + w_fruit, y + h_fruit), (255, 0, 0), 3
                )
                detections.append(
                    {
                        "box": [
                            float(x),
                            float(y),
                            float(x + w_fruit),
                            float(y + h_fruit),
                        ],
                        "confidence": 0.99,
                        "label": "MATURE",
                    }
                )

            detections = suppress_overlapping_detections(detections)

            success, encoded_img = cv2.imencode(".jpg", annotated_bgr)
            if not success:
                return (
                    jsonify(
                        {"success": False, "error": "Failed to encode annotated image"}
                    ),
                    500,
                )
            encoded_b64 = base64.b64encode(encoded_img.tobytes()).decode("ascii")

            return jsonify(
                {
                    "success": True,
                    "data": {
                        "detections": detections,
                        "annotated_image": f"data:image/jpeg;base64,{encoded_b64}",
                        "source_path": img_path,
                    },
                }
            )

        # Load model
        try:
            model = load_yolo_model()
        except Exception as e:
            return jsonify({"success": False, "error": str(e)}), 500

        # Run prediction
        results = list(
            model.predict(source=img_path, conf=conf, save=False, verbose=False)
        )
        if not results:
            return jsonify(
                {"success": True, "data": {"detections": [], "annotated_image": None}}
            )

        r = results[0]

        detections = []
        # r.boxes.xyxy, r.boxes.conf, r.boxes.cls
        boxes = getattr(r, "boxes", None)
        names = getattr(model, "names", {}) or {}
        mature_class_ids = {
            i for i, n in names.items() if str(n).strip().lower() == "mature"
        }
        if not mature_class_ids and names:
            mature_class_ids = {0}
        if boxes is not None and len(boxes) > 0:
            xyxy = boxes.xyxy.tolist()
            confs = boxes.conf.tolist()
            clss = boxes.cls.tolist()
            frame_bgr = getattr(r, "orig_img", None)
            if frame_bgr is None:
                frame_bgr = cv2.imread(img_path)

            for b, c, cl in zip(xyxy, confs, clss):
                if mature_class_ids and int(cl) not in mature_class_ids:
                    continue
                if frame_bgr is not None and not is_fully_mature_fruit(frame_bgr, b):
                    continue
                detections.append(
                    {
                        "box": [float(b[0]), float(b[1]), float(b[2]), float(b[3])],
                        "confidence": float(c),
                        "class_id": int(cl),
                        "label": "MATURE",
                    }
                )

        detections = suppress_overlapping_detections(detections)

        # Create annotated image (PIL)
        pil = Image.open(img_path).convert("RGB")
        draw = ImageDraw.Draw(pil)
        try:
            font = ImageFont.truetype("arial.ttf", 18)
        except Exception:
            font = ImageFont.load_default()

        for det in detections:
            x1, y1, x2, y2 = det["box"]
            label = f"{det['label']} {det['confidence']:.2f}"
            draw.rectangle([x1, y1, x2, y2], outline="red", width=3)
            # Compute text size in a way compatible with Pillow versions
            try:
                bbox = draw.textbbox((0, 0), label, font=font)
                text_width = bbox[2] - bbox[0]
                text_height = bbox[3] - bbox[1]
            except AttributeError:
                text_width, text_height = (len(label) * 6, 14)

            text_bg = [x1, max(0, y1 - text_height - 4), x1 + text_width + 6, y1]
            draw.rectangle(text_bg, fill="red")
            draw.text(
                (x1 + 3, max(0, y1 - text_height - 2)), label, fill="white", font=font
            )

        buffered = io.BytesIO()
        pil.save(buffered, format="JPEG")
        encoded_img = base64.b64encode(buffered.getvalue()).decode("ascii")

        response = {
            "success": True,
            "data": {
                "detections": detections,
                "annotated_image": f"data:image/jpeg;base64,{encoded_img}",
                "source_path": img_path,
            },
        }

        return jsonify(response)

    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500


@app.route("/api/dashboard/yield-video-detect", methods=["POST"])
def yield_video_detect():
    """Upload a video or provide a stream URL and count mature fruits using YOLO tracking.

    Request options (multipart/form-data or query/JSON):
      - video: uploaded video file (field name: "video")
      - stream_url: optional URL for IP camera / Android phone stream
      - conf: optional confidence threshold (default 0.25)
    """
    try:
        # Confidence threshold (form or query param)
        conf = float(request.form.get("conf", request.args.get("conf", 0.25)))

        stream_url = request.form.get("stream_url") or request.args.get("stream_url")
        video_path = None

        if stream_url:
            source = stream_url
        else:
            # Expect a video file upload
            if "video" not in request.files:
                return (
                    jsonify(
                        {
                            "success": False,
                            "error": "No video file provided (field name: video)",
                        }
                    ),
                    400,
                )

            video_file = request.files["video"]
            if video_file.filename == "":
                return jsonify({"success": False, "error": "Empty filename"}), 400

            filename = secure_filename(video_file.filename or "")
            save_dir = os.path.join("uploads", "yield", "videos")
            os.makedirs(save_dir, exist_ok=True)
            video_path = os.path.join(save_dir, f"{uuid.uuid4().hex}_{filename}")
            video_file.save(video_path)
            source = video_path

        # Load YOLO model
        try:
            model = load_yolo_model()
        except Exception as e:
            return jsonify({"success": False, "error": str(e)}), 500

        annotated_rel = None
        stats = None
        # Default to HSV color mode (same algorithm as image capture = most accurate)
        method = (request.form.get("method") or "color").lower()
        if stream_url:
            # For stream URLs, just count without saving annotated video
            stats = count_mature_in_video(model, source=source, conf=conf)
        else:
            annotated_dir = os.path.join("uploads", "yield", "videos", "annotated")
            os.makedirs(annotated_dir, exist_ok=True)
            annotated_filename = f"annotated_{uuid.uuid4().hex}.mp4"
            annotated_path = os.path.join(annotated_dir, annotated_filename)
            stats = annotate_video_and_count(
                model,
                source=source,
                output_path=annotated_path,
                conf=conf,
                method=method,
            )
            annotated_rel = os.path.join(
                "uploads", "yield", "videos", "annotated", annotated_filename
            ).replace("\\", "/")

        # Generate URL for original video
        original_video_url = None
        if video_path:
            original_video_url = (
                f"/uploads/{os.path.relpath(video_path, 'uploads').replace('\\', '/')}"
            )

        return jsonify(
            {
                "success": True,
                "data": {
                    "total_mature_fruits": stats.get("total_mature_fruits", 0),
                    "frame_count": stats.get("frame_count", 0),
                    "mature_class_ids": stats.get("mature_class_ids", []),
                    "source_type": "stream" if stream_url else "upload",
                    "saved_video_path": video_path,
                    "original_video_url": original_video_url,
                    "annotated_video_url": (
                        f"/uploads/{os.path.relpath(annotated_rel, 'uploads').replace('\\', '/')}"
                        if annotated_rel
                        else None
                    ),
                    "conf": conf,
                },
            }
        )
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500


def generate_pdf_report(report_data, report_id):
    """Generate PDF report optimized for single page with professional design"""
    buffer = io.BytesIO()
    doc = SimpleDocTemplate(
        buffer,
        pagesize=A4,
        leftMargin=0.6 * inch,
        rightMargin=0.6 * inch,
        topMargin=0.6 * inch,
        bottomMargin=0.6 * inch,
    )

    # Get styles
    styles = getSampleStyleSheet()

    # Professional color scheme
    primary_color = colors.HexColor("#1e3a5f")  # Deep blue
    secondary_color = colors.HexColor("#2d5a87")  # Medium blue
    accent_color = colors.HexColor("#e8f1f8")  # Light blue
    text_color = colors.HexColor("#333333")  # Dark gray
    light_gray = colors.HexColor("#f5f5f5")  # Very light gray

    # Title style - professional header
    title_style = ParagraphStyle(
        "CustomTitle",
        parent=styles["Heading1"],
        fontSize=20,
        spaceAfter=12,
        alignment=TA_CENTER,
        textColor=primary_color,
        fontName="Helvetica-Bold",
    )

    # Subtitle style
    subtitle_style = ParagraphStyle(
        "CustomSubtitle",
        parent=styles["Normal"],
        fontSize=10,
        spaceAfter=15,
        alignment=TA_CENTER,
        textColor=colors.gray,
        fontName="Helvetica",
    )

    # Section heading style
    heading_style = ParagraphStyle(
        "CustomHeading",
        parent=styles["Heading2"],
        fontSize=11,
        spaceAfter=6,
        textColor=primary_color,
        fontName="Helvetica-Bold",
        borderPadding=5,
        borderBackColor=accent_color,
    )

    # Normal text style
    normal_style = ParagraphStyle(
        "CustomNormal",
        parent=styles["Normal"],
        fontSize=9,
        spaceAfter=4,
        textColor=text_color,
        fontName="Helvetica",
    )

    # Small text style
    small_style = ParagraphStyle(
        "CustomSmall",
        parent=styles["Normal"],
        fontSize=8,
        spaceAfter=3,
        textColor=text_color,
        fontName="Helvetica",
    )

    # Build PDF content
    story = []

    # Professional header with title and subtitle
    story.append(Paragraph("Disease Detection Report", title_style))
    story.append(Paragraph("Dragon Fruit Disease Analysis System", subtitle_style))
    story.append(Spacer(1, 8))

    # Check if this is a session-based multi-detection
    session_id = report_data.get("session_id")
    if session_id:
        # Get all detections with this session_id
        detections = db_manager.get_all_disease_detections()
        session_detections = [
            d for d in detections if d.get("session_id") == session_id
        ]

        # Multi-disease report - calculate combined values
        disease_names = ", ".join([d["DiseaseType"] for d in session_detections])
        sum_confidence = sum([d["Confidence"] for d in session_detections])
        avg_confidence = (
            sum_confidence / len(session_detections) if session_detections else 0
        )
        max_severity = (
            "high"
            if any(d["Severity"] == "high" for d in session_detections)
            else (
                "medium"
                if any(d["Severity"] == "medium" for d in session_detections)
                else "low"
            )
        )

        report_info_data = [
            ["Session ID:", str(session_id)],
            ["Diseases Detected:", f"{len(session_detections)} disease(s)"],
            ["Disease Names:", disease_names],
            ["Overall Severity:", max_severity.upper()],
            ["Total Confidence:", f"{sum_confidence:.1f}%"],
            ["Date & Time:", report_data["DateTime"]],
            ["Location:", report_data.get("Location", "Unknown")],
        ]
    else:
        # Single detection report
        report_info_data = [
            ["Detection ID:", str(report_data["DetectionID"])],
            ["Disease Type:", report_data["DiseaseType"]],
            ["Severity:", report_data["Severity"].upper()],
            ["Confidence:", f"{report_data['Confidence']:.1f}%"],
            ["Date & Time:", report_data["DateTime"]],
            ["Location:", report_data.get("Location", "Unknown")],
        ]

    # Professional table styling
    report_table = Table(report_info_data, colWidths=[1.6 * inch, 4.0 * inch])
    report_table.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (0, -1), accent_color),
                ("BACKGROUND", (1, 0), (1, -1), colors.white),
                ("TEXTCOLOR", (0, 0), (0, -1), primary_color),
                ("TEXTCOLOR", (1, 0), (1, -1), text_color),
                ("ALIGN", (0, 0), (-1, -1), "LEFT"),
                ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
                ("FONTNAME", (0, 0), (0, -1), "Helvetica-Bold"),
                ("FONTNAME", (1, 0), (1, -1), "Helvetica"),
                ("FONTSIZE", (0, 0), (-1, -1), 9),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
                ("TOPPADDING", (0, 0), (-1, -1), 6),
                ("LEFTPADDING", (0, 0), (-1, -1), 8),
                ("RIGHTPADDING", (0, 0), (-1, -1), 8),
                ("LINEBELOW", (0, 0), (-1, -1), 0.5, colors.lightgrey),
                ("LINEABOVE", (0, 0), (-1, -1), 0.5, colors.lightgrey),
            ]
        )
    )

    story.append(report_table)
    story.append(Spacer(1, 10))

    # Add Disease Detection Image if available (compact)
    if report_data.get("ImagePath"):
        try:
            image_path = report_data["ImagePath"]
            if not os.path.isabs(image_path):
                possible_paths = [
                    image_path,
                    os.path.join("uploads", image_path),
                    os.path.join("uploads/yield", image_path),
                    os.path.join("uploads/yield/videos", image_path),
                ]
                image_path = None
                for path in possible_paths:
                    if os.path.exists(path):
                        image_path = path
                        break

            if image_path and os.path.exists(image_path):
                story.append(Paragraph("Detection Image", heading_style))
                try:
                    from PIL import Image as PILImage

                    pil_img = PILImage.open(image_path)
                    img_width, img_height = pil_img.size

                    # Compact image sizing for single page
                    max_width = 3.5 * inch
                    aspect_ratio = img_height / img_width
                    display_width = max_width
                    display_height = max_width * aspect_ratio

                    max_height = 1.8 * inch
                    if display_height > max_height:
                        display_height = max_height
                        display_width = max_height / aspect_ratio

                    img = RLImage(
                        image_path, width=display_width, height=display_height
                    )
                    story.append(img)
                    story.append(Spacer(1, 6))
                except Exception as img_error:
                    story.append(
                        Paragraph(
                            f"Note: Could not load image. ({str(img_error)})",
                            small_style,
                        )
                    )
                    story.append(Spacer(1, 6))
        except Exception as e:
            pass

    # Disease Information Section (compact)
    story.append(Paragraph("Disease Information", heading_style))

    # Get disease details - handle multi-disease case
    if session_id:
        # For multi-disease, get info for each disease
        for detection in session_detections:
            try:
                import sqlite3

                conn = sqlite3.connect("pitaya_database.db")
                cursor = conn.cursor()
                cursor.execute(
                    """
                    SELECT description, scientific_name
                    FROM disease_library
                    WHERE disease_name = ?
                """,
                    (detection["DiseaseType"],),
                )
                disease_info = cursor.fetchone()
                conn.close()

                if disease_info:
                    desc, scientific = disease_info
                    story.append(
                        Paragraph(
                            f"<b>{detection['DiseaseType']}</b> <i>({scientific or 'N/A'})</i>",
                            small_style,
                        )
                    )
                    if desc:
                        # Truncate description for compact layout
                        truncated_desc = desc[:150] + "..." if len(desc) > 150 else desc
                        story.append(Paragraph(truncated_desc, small_style))
                    story.append(Spacer(1, 3))
            except:
                pass
    else:
        # Single disease
        try:
            import sqlite3

            conn = sqlite3.connect("pitaya_database.db")
            cursor = conn.cursor()

            cursor.execute(
                """
                SELECT description, scientific_name
                FROM disease_library
                WHERE disease_name = ?
            """,
                (report_data["DiseaseType"],),
            )

            disease_info = cursor.fetchone()
            conn.close()

            if disease_info:
                desc, scientific = disease_info
                story.append(
                    Paragraph(
                        f"<b>Scientific Name:</b> {scientific or 'N/A'}", small_style
                    )
                )
                if desc:
                    truncated_desc = desc[:200] + "..." if len(desc) > 200 else desc
                    story.append(
                        Paragraph(f"<b>Description:</b> {truncated_desc}", small_style)
                    )
                story.append(Spacer(1, 4))
        except:
            pass

    # Footer with timestamp
    story.append(Spacer(1, 10))
    footer_text = f"Generated on {datetime.now().strftime('%Y-%m-%d %H:%M:%S')} | Report ID: {report_id}"
    story.append(Paragraph(footer_text, small_style))

    # Build PDF
    doc.build(story)
    buffer.seek(0)

    return send_file(
        buffer,
        mimetype="application/pdf",
        as_attachment=True,
        download_name=f"disease_report_{report_id}.pdf",
    )


def generate_pdf_content(report_data, report_id):
    """Generate PDF content as base64 for preview with professional design"""
    import base64

    buffer = io.BytesIO()
    doc = SimpleDocTemplate(
        buffer,
        pagesize=A4,
        leftMargin=0.6 * inch,
        rightMargin=0.6 * inch,
        topMargin=0.6 * inch,
        bottomMargin=0.6 * inch,
    )

    # Get styles
    styles = getSampleStyleSheet()

    # Professional color scheme (same as generate_pdf_report)
    primary_color = colors.HexColor("#1e3a5f")
    secondary_color = colors.HexColor("#2d5a87")
    accent_color = colors.HexColor("#e8f1f8")
    text_color = colors.HexColor("#333333")
    light_gray = colors.HexColor("#f5f5f5")

    # Title style
    title_style = ParagraphStyle(
        "CustomTitle",
        parent=styles["Heading1"],
        fontSize=20,
        spaceAfter=12,
        alignment=TA_CENTER,
        textColor=primary_color,
        fontName="Helvetica-Bold",
    )

    # Subtitle style
    subtitle_style = ParagraphStyle(
        "CustomSubtitle",
        parent=styles["Normal"],
        fontSize=10,
        spaceAfter=15,
        alignment=TA_CENTER,
        textColor=colors.gray,
        fontName="Helvetica",
    )

    # Section heading style
    heading_style = ParagraphStyle(
        "CustomHeading",
        parent=styles["Heading2"],
        fontSize=11,
        spaceAfter=6,
        textColor=primary_color,
        fontName="Helvetica-Bold",
    )

    # Normal text style
    normal_style = ParagraphStyle(
        "CustomNormal",
        parent=styles["Normal"],
        fontSize=9,
        spaceAfter=4,
        textColor=text_color,
        fontName="Helvetica",
    )

    # Small text style
    small_style = ParagraphStyle(
        "CustomSmall",
        parent=styles["Normal"],
        fontSize=8,
        spaceAfter=3,
        textColor=text_color,
        fontName="Helvetica",
    )

    # Build PDF content
    story = []

    # Professional header
    story.append(Paragraph("Disease Detection Report", title_style))
    story.append(Paragraph("Dragon Fruit Disease Analysis System", subtitle_style))
    story.append(Spacer(1, 8))

    # Check if this is a session-based multi-detection
    session_id = report_data.get("session_id")
    if session_id:
        # Get all detections with this session_id
        detections = db_manager.get_all_disease_detections()
        session_detections = [
            d for d in detections if d.get("session_id") == session_id
        ]

        # Multi-disease report
        disease_names = ", ".join([d["DiseaseType"] for d in session_detections])
        sum_confidence = sum([d["Confidence"] for d in session_detections])
        avg_confidence = (
            sum_confidence / len(session_detections) if session_detections else 0
        )
        max_severity = (
            "high"
            if any(d["Severity"] == "high" for d in session_detections)
            else (
                "medium"
                if any(d["Severity"] == "medium" for d in session_detections)
                else "low"
            )
        )

        report_info_data = [
            ["Session ID:", str(session_id)],
            ["Diseases Detected:", f"{len(session_detections)} disease(s)"],
            ["Disease Names:", disease_names],
            ["Overall Severity:", max_severity.upper()],
            ["Total Confidence:", f"{sum_confidence:.1f}%"],
            ["Date & Time:", report_data["DateTime"]],
            ["Location:", report_data.get("Location", "Unknown")],
        ]
    else:
        # Single detection report
        report_info_data = [
            ["Detection ID:", str(report_data["DetectionID"])],
            ["Disease Type:", report_data["DiseaseType"]],
            ["Severity:", report_data["Severity"].upper()],
            ["Confidence:", f"{report_data['Confidence']:.1f}%"],
            ["Date & Time:", report_data["DateTime"]],
            ["Location:", report_data.get("Location", "Unknown")],
        ]

    # Professional table styling
    report_table = Table(report_info_data, colWidths=[1.6 * inch, 4.0 * inch])
    report_table.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (0, -1), accent_color),
                ("BACKGROUND", (1, 0), (1, -1), colors.white),
                ("TEXTCOLOR", (0, 0), (0, -1), primary_color),
                ("TEXTCOLOR", (1, 0), (1, -1), text_color),
                ("ALIGN", (0, 0), (-1, -1), "LEFT"),
                ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
                ("FONTNAME", (0, 0), (0, -1), "Helvetica-Bold"),
                ("FONTNAME", (1, 0), (1, -1), "Helvetica"),
                ("FONTSIZE", (0, 0), (-1, -1), 9),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
                ("TOPPADDING", (0, 0), (-1, -1), 6),
                ("LEFTPADDING", (0, 0), (-1, -1), 8),
                ("RIGHTPADDING", (0, 0), (-1, -1), 8),
                ("LINEBELOW", (0, 0), (-1, -1), 0.5, colors.lightgrey),
                ("LINEABOVE", (0, 0), (-1, -1), 0.5, colors.lightgrey),
            ]
        )
    )

    story.append(report_table)
    story.append(Spacer(1, 10))

    # Add Disease Detection Image if available (compact)
    if report_data.get("ImagePath"):
        try:
            image_path = report_data["ImagePath"]
            if not os.path.isabs(image_path):
                possible_paths = [
                    image_path,
                    os.path.join("uploads", image_path),
                    os.path.join("uploads/yield", image_path),
                    os.path.join("uploads/yield/videos", image_path),
                ]
                image_path = None
                for path in possible_paths:
                    if os.path.exists(path):
                        image_path = path
                        break

            if image_path and os.path.exists(image_path):
                story.append(Paragraph("Detection Image", heading_style))
                try:
                    from PIL import Image as PILImage

                    pil_img = PILImage.open(image_path)
                    img_width, img_height = pil_img.size

                    # Compact image sizing for single page
                    max_width = 3.5 * inch
                    aspect_ratio = img_height / img_width
                    display_width = max_width
                    display_height = max_width * aspect_ratio

                    max_height = 1.8 * inch
                    if display_height > max_height:
                        display_height = max_height
                        display_width = max_height / aspect_ratio

                    img = RLImage(
                        image_path, width=display_width, height=display_height
                    )
                    story.append(img)
                    story.append(Spacer(1, 6))
                except Exception as img_error:
                    story.append(
                        Paragraph(
                            f"Note: Could not load image. ({str(img_error)})",
                            small_style,
                        )
                    )
                    story.append(Spacer(1, 6))
        except Exception as e:
            pass

    # Disease Information Section (compact)
    story.append(Paragraph("Disease Information", heading_style))

    # Get disease details - handle multi-disease case
    if session_id:
        # For multi-disease, get info for each disease
        for detection in session_detections:
            try:
                import sqlite3

                conn = sqlite3.connect("pitaya_database.db")
                cursor = conn.cursor()
                cursor.execute(
                    """
                    SELECT description, scientific_name
                    FROM disease_library
                    WHERE disease_name = ?
                """,
                    (detection["DiseaseType"],),
                )
                disease_info = cursor.fetchone()
                conn.close()

                if disease_info:
                    desc, scientific = disease_info
                    story.append(
                        Paragraph(
                            f"<b>{detection['DiseaseType']}</b> <i>({scientific or 'N/A'})</i>",
                            small_style,
                        )
                    )
                    if desc:
                        # Truncate description for compact layout
                        truncated_desc = desc[:150] + "..." if len(desc) > 150 else desc
                        story.append(Paragraph(truncated_desc, small_style))
                    story.append(Spacer(1, 3))
            except:
                pass
    else:
        # Single disease
        try:
            import sqlite3

            conn = sqlite3.connect("pitaya_database.db")
            cursor = conn.cursor()

            cursor.execute(
                """
                SELECT description, scientific_name
                FROM disease_library
                WHERE disease_name = ?
            """,
                (report_data["DiseaseType"],),
            )

            disease_info = cursor.fetchone()
            conn.close()

            if disease_info:
                desc, scientific = disease_info
                story.append(
                    Paragraph(
                        f"<b>Scientific Name:</b> {scientific or 'N/A'}", small_style
                    )
                )
                if desc:
                    truncated_desc = desc[:200] + "..." if len(desc) > 200 else desc
                    story.append(
                        Paragraph(f"<b>Description:</b> {truncated_desc}", small_style)
                    )
                story.append(Spacer(1, 4))
        except:
            pass

    # Footer with timestamp
    story.append(Spacer(1, 10))
    footer_text = f"Generated on {datetime.now().strftime('%Y-%m-%d %H:%M:%S')} | Report ID: {report_id}"
    story.append(Paragraph(footer_text, small_style))

    # Build PDF
    doc.build(story)
    buffer.seek(0)

    # Convert to base64
    pdf_bytes = buffer.getvalue()
    base64_content = base64.b64encode(pdf_bytes).decode("utf-8")
    buffer.close()

    return base64_content


@app.route("/api/translate", methods=["POST"])
def translate_disease():
    """Translate disease content to Tagalog"""
    try:
        data = request.get_json()

        # Validate required fields
        required_fields = ["disease_name", "field_name", "target_language"]
        for field in required_fields:
            if field not in data:
                return (
                    jsonify(
                        {"success": False, "error": f"Missing required field: {field}"}
                    ),
                    400,
                )

        disease_name = data["disease_name"]
        field_name = data["field_name"]
        target_language = data["target_language"]

        # Get translation from database
        import sqlite3

        conn = sqlite3.connect("pitaya_database.db")
        cursor = conn.cursor()

        cursor.execute(
            """
            SELECT translated_text FROM translations
            WHERE disease_name = ? AND field_name = ? AND language_code = ?
        """,
            (disease_name, field_name, target_language),
        )

        result = cursor.fetchone()
        conn.close()

        if result:
            translated_text = result[0]

            # Return translation
            return jsonify(
                {
                    "success": True,
                    "data": {
                        "disease_name": disease_name,
                        "field_name": field_name,
                        "target_language": target_language,
                        "translated_text": translated_text,
                    },
                    "timestamp": datetime.now().isoformat(),
                }
            )
        else:
            # If no translation found, return original text
            return jsonify(
                {
                    "success": True,
                    "data": {
                        "disease_name": disease_name,
                        "field_name": field_name,
                        "target_language": target_language,
                        "translated_text": f"Translation not available for {disease_name} - {field_name}",
                    },
                    "timestamp": datetime.now().isoformat(),
                }
            )

    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500


@app.route("/api/translate/batch", methods=["POST"])
def translate_diseases_batch():
    """Translate multiple diseases at once"""
    try:
        data = request.get_json()

        # Validate required fields
        required_fields = ["diseases", "target_language"]
        for field in required_fields:
            if field not in data:
                return (
                    jsonify(
                        {"success": False, "error": f"Missing required field: {field}"}
                    ),
                    400,
                )

        diseases = data["diseases"]
        target_language = data["target_language"]

        # Get translations from database
        import sqlite3

        conn = sqlite3.connect("pitaya_database.db")
        cursor = conn.cursor()

        translations = {}
        for disease_name in diseases:
            cursor.execute(
                """
                SELECT field_name, translated_text FROM translations
                WHERE disease_name = ? AND language_code = ?
            """,
                (disease_name, target_language),
            )

            results = cursor.fetchall()
            if results:
                translations[disease_name] = {
                    field_name: translated_text
                    for field_name, translated_text in results
                }

        conn.close()

        return jsonify(
            {
                "success": True,
                "data": translations,
                "count": len(translations),
                "target_language": target_language,
                "timestamp": datetime.now().isoformat(),
            }
        )

    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500


@app.route("/api/user/preferences", methods=["GET", "POST"])
def user_preferences():
    """Get or update profile and notification preferences."""
    try:
        if request.method == "GET":
            prefs = db_manager.get_user_preferences("default_user")

            return jsonify(
                {
                    "success": True,
                    "data": {
                        "user_id": "default_user",
                        "preferred_language": prefs.get("preferred_language", "en"),
                        "notification_email": prefs.get("notification_email"),
                        "farm_name": prefs.get("farm_name"),
                        "email_notifications_enabled": prefs.get(
                            "email_notifications_enabled", True
                        ),
                    },
                    "timestamp": datetime.now().isoformat(),
                }
            )

        elif request.method == "POST":
            data = request.get_json(silent=True) or {}
            preferred_language = data.get("preferred_language", "en")
            notification_email = (data.get("notification_email") or "").strip() or None
            farm_name = (data.get("farm_name") or "").strip() or None
            email_notifications_enabled = data.get("email_notifications_enabled", True)

            if notification_email:
                import re

                email_regex = r"^[^\s@]+@[^\s@]+\.[^\s@]+$"
                if not re.match(email_regex, notification_email):
                    return (
                        jsonify(
                            {
                                "success": False,
                                "error": "Please enter a valid email address",
                            }
                        ),
                        400,
                    )

            db_manager.save_user_preferences(
                user_id="default_user",
                preferred_language=preferred_language,
                notification_email=notification_email,
                farm_name=farm_name,
                email_notifications_enabled=1 if email_notifications_enabled else 0,
            )

            return jsonify(
                {
                    "success": True,
                    "data": {
                        "user_id": "default_user",
                        "preferred_language": preferred_language,
                        "notification_email": notification_email,
                        "farm_name": farm_name,
                        "email_notifications_enabled": bool(
                            email_notifications_enabled
                        ),
                    },
                    "message": "Profile preferences updated",
                    "timestamp": datetime.now().isoformat(),
                }
            )

        return jsonify({"success": False, "error": "Method not allowed"}), 405

    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500


@app.route("/api/dashboard/disease-detection", methods=["POST"])
def add_disease_detection():
    """Add a new disease detection record"""
    try:
        payload = request.get_json(silent=True) or {}

        # Accept either JSON or form submissions so the frontend can post either shape.
        disease_type = payload.get("disease_type") or request.form.get("disease_type")
        severity = payload.get("severity") or request.form.get("severity")
        confidence = payload.get("confidence") or request.form.get("confidence")
        location = payload.get("location") or request.form.get("location")
        image_path = payload.get("image_path") or ""

        # Validate required fields
        required_fields = {
            "disease_type": disease_type,
            "severity": severity,
            "confidence": confidence,
            "location": location,
        }
        for field, value in required_fields.items():
            if not value:
                return (
                    jsonify(
                        {"success": False, "error": f"Missing required field: {field}"}
                    ),
                    400,
                )

        # Handle file upload
        if "image" in request.files:
            file = request.files["image"]
            if file and file.filename != "":
                try:
                    # Validate file type
                    if (
                        not (file.filename or "")
                        .lower()
                        .endswith((".png", ".jpg", ".jpeg", ".gif", ".bmp"))
                    ):
                        return (
                            jsonify(
                                {
                                    "success": False,
                                    "error": "Invalid file type. Please upload an image file.",
                                }
                            ),
                            400,
                        )

                    # Create upload directory if it doesn't exist
                    upload_folder = "uploads"
                    if not os.path.exists(upload_folder):
                        os.makedirs(upload_folder)

                    # Save file with unique name
                    filename = secure_filename(file.filename or "")
                    unique_filename = f"{uuid.uuid4()}_{filename}"
                    file_path = os.path.join(upload_folder, unique_filename)
                    file.save(file_path)

                    # Store relative path in database
                    image_path = file_path
                    print(f"Image saved to: {image_path}")
                except Exception as e:
                    print(f"File upload error: {str(e)}")
                    # Continue without image if upload fails
                    image_path = ""

        # Add detection to database
        disease_type = str(disease_type)
        severity = str(severity)
        location = str(location)
        confidence_value = float(str(confidence))

        # Get session_id from form data for grouping related detections
        session_id = request.form.get("session_id") or payload.get("session_id")

        detection_id = db_manager.add_disease_detection(
            disease_type=disease_type,
            severity=severity,
            confidence=confidence_value,
            location=location,
            image_path=image_path,
            session_id=session_id,
        )

        return jsonify(
            {
                "success": True,
                "data": {
                    "detection_id": detection_id,
                    "message": "Disease detection added successfully",
                },
                "timestamp": datetime.now().isoformat(),
            }
        )
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500


@app.route("/predict", methods=["POST"])
def predict_disease():
    """Handle image upload and disease detection"""
    try:
        # Check if file was uploaded
        if "file" not in request.files:
            return jsonify({"success": False, "error": "No file uploaded"}), 400

        file = request.files["file"]
        if file.filename == "":
            return jsonify({"success": False, "error": "No file selected"}), 400

        # Validate file type
        if (
            not (file.filename or "")
            .lower()
            .endswith((".png", ".jpg", ".jpeg", ".gif", ".bmp"))
        ):
            return (
                jsonify(
                    {
                        "success": False,
                        "error": "Invalid file type. Please upload an image file.",
                    }
                ),
                400,
            )

        # Save uploaded file
        filename = secure_filename(file.filename or "")
        unique_filename = f"{uuid.uuid4()}_{filename}"
        upload_folder = "uploads"

        # Create upload folder if it doesn't exist
        if not os.path.exists(upload_folder):
            os.makedirs(upload_folder)

        file_path = os.path.join(upload_folder, unique_filename)
        file.save(file_path)

        # Mock disease detection (in real implementation, this would use ML model)
        import random

        diseases = [
            {
                "name": "Anthracnose",
                "severity": "high",
                "confidence": random.uniform(85, 95),
            },
            {
                "name": "Brown Spot",
                "severity": "medium",
                "confidence": random.uniform(75, 90),
            },
            {
                "name": "Root Rot",
                "severity": "high",
                "confidence": random.uniform(80, 95),
            },
            {
                "name": "Stem Rot",
                "severity": "medium",
                "confidence": random.uniform(70, 85),
            },
            {
                "name": "Leaf Blight",
                "severity": "low",
                "confidence": random.uniform(60, 80),
            },
        ]

        # Randomly select a disease (70% chance of disease, 30% chance of healthy)
        if random.random() < 0.7:
            selected_disease = random.choice(diseases)
            disease_name = selected_disease["name"]
            severity = selected_disease["severity"]
            confidence = selected_disease["confidence"]

            # DO NOT automatically save to database - wait for user confirmation
            # The frontend will call the disease-detection endpoint to save

            # Create response with preview data
            response = {
                "success": True,
                "detection": {
                    "disease_name": disease_name,
                    "confidence_level": f"{confidence:.1f}%",
                    "severity": severity,
                    "symptoms": [
                        f"Leaf spots visible on {random.choice(['upper', 'lower'])} leaf surface",
                        f"Yellowing around affected areas",
                        f"Possible {severity} damage if untreated",
                    ],
                    "causes": [
                        f"Fungal infection common in humid conditions",
                        "Poor air circulation around plants",
                    ],
                    "treatment": [
                        f"Apply fungicide suitable for {disease_name}",
                        "Remove affected leaves to prevent spread",
                        "Improve ventilation and reduce humidity",
                    ],
                },
                "alert": {
                    "type": "disease_detected",
                    "message": f"{disease_name} detected with {confidence:.1f}% confidence",
                    "severity": severity,
                },
                "report_id": None,  # Will be assigned when user confirms detection
            }
        else:
            # No disease detected
            confidence = random.uniform(60, 80)
            response = {
                "success": True,
                "detection": {
                    "disease_name": None,
                    "confidence_level": f"{confidence:.1f}%",
                    "severity": "low",
                    "message": "No visible disease detected. Plant appears healthy.",
                    "symptoms": [],
                    "causes": [],
                    "treatment": [],
                },
                "alert": None,
                "report_id": None,
            }

        return jsonify(response)

    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500


if __name__ == "__main__":
    print("Starting Dashboard API Server...")
    print("Database initialized with sample data")
    app.run(debug=True, host="0.0.0.0", port=5001)
