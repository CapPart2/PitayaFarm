# flake8: noqa
# Dashboard API Endpoints - Clean Version
# Flask API for database-driven dashboard charts

from flask import Flask, jsonify, request, send_file, send_from_directory, Response
from flask_cors import CORS
from datetime import datetime, timedelta
import json
import csv
import io
import os
import sqlite3
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
]
OBJECT_GUARD_PATH = "Yield_detection/yolov8n.pt"
OBJECT_GUARD_MODEL = None
MATURE_CLASS_LABELS = {"mature", "fully_red_dragon_fruit"}
OBJECT_GUARD_LABELS = {
    "person", "bicycle", "car", "motorcycle", "bus", "train", "truck", "boat",
    "bird", "cat", "dog", "horse", "sheep", "cow", "elephant", "bear", "zebra", "giraffe",
    "backpack", "umbrella", "handbag", "tie", "suitcase", "frisbee", "sports ball",
    "baseball bat", "baseball glove", "skateboard", "surfboard", "tennis racket",
    "bottle", "wine glass", "cup", "fork", "knife", "spoon", "bowl",
    "chair", "couch", "bed", "dining table", "toilet", "tv", "laptop", "mouse",
    "remote", "keyboard", "cell phone", "book", "clock", "vase", "scissors",
    "teddy bear", "hair drier", "toothbrush",
}
NO_MATURE_DETECTION_MESSAGE = "No mature detection found."
# A one-class detector must be conservative: it has no explicit "person" or
# "background" label to correct a low-confidence guess.  Do not permit clients
# to lower this threshold for records that may be saved as yield data.
MIN_MATURE_CONFIDENCE = 0.55


def mature_confidence_threshold(
    value, default: float = MIN_MATURE_CONFIDENCE, minimum: float = MIN_MATURE_CONFIDENCE
) -> float:
    """Return a safe mature-fruit confidence threshold from a request value."""
    try:
        requested = float(value)
    except (TypeError, ValueError):
        requested = default
    return min(0.99, max(minimum, requested))


def get_mature_class_ids(model):
    """Return the trained mature-fruit class IDs, never a generic fallback.

    A generic COCO model labels class 0 as ``person``. Treating its class 0 as
    mature fruit was the source of false counts after deployments where the
    custom weight file was absent. A model without our explicit fruit label is
    invalid for yield assessment and must produce no detections.
    """
    names = getattr(model, "names", {}) or {}
    name_items = tuple(names.items() if isinstance(names, dict) else enumerate(names))
    mature_ids = {
        int(class_id)
        for class_id, class_name in name_items
        if str(class_name).strip().lower() in MATURE_CLASS_LABELS
    }
    if not mature_ids:
        available_labels = ", ".join(str(name) for _, name in name_items)
        raise RuntimeError(
            "Configured yield model is not a PITAYA mature-fruit model. "
            f"Expected one of {sorted(MATURE_CLASS_LABELS)}; found: {available_labels or 'no labels'}"
        )
    return mature_ids


def get_request_user_id(default=None):
    user_id = (
        request.headers.get("X-Pitaya-User")
        or request.args.get("user_id")
        or (request.form.get("user_id") if request.form else None)
    )
    if user_id:
        return str(user_id).strip() or default
    if default is not None:
        return default

    # Never fall back to unscoped/global reads when the caller forgot the header.
    # A non-existent sentinel keeps queries user-scoped and returns empty results.
    return "__missing_user_scope__"


def migrate_legacy_user_data(target_user_id):
    if not target_user_id:
        return 0, 0

    conn = sqlite3.connect(db_manager.db_path)
    cursor = conn.cursor()

    cursor.execute(
        "UPDATE disease_detections SET user_id = ? WHERE user_id = 'default_user'",
        (target_user_id,),
    )
    disease_count = cursor.rowcount

    cursor.execute(
        "UPDATE yield_predictions SET user_id = ? WHERE user_id = 'default_user'",
        (target_user_id,),
    )
    yield_count = cursor.rowcount

    conn.commit()
    conn.close()
    return disease_count, yield_count


def make_uploaded_file_url(image_path):
    if not image_path:
        return None

    relative_path = str(image_path).replace("\\", "/")
    if relative_path.startswith("uploads/"):
        relative_path = relative_path[len("uploads/") :]
    elif relative_path.startswith("/uploads/"):
        relative_path = relative_path[len("/uploads/") :]
    elif relative_path.startswith("/"):
        relative_path = relative_path.lstrip("/")

    return f"/uploads/{relative_path}"


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
    # Validate immediately so a wrong or generic model can never start serving
    # fruit detections after a redeploy.
    get_mature_class_ids(MODEL)
    return MODEL


def get_unrelated_object_boxes(frame_bgr):
    """Find person/object boxes that must never be counted as fruit.

    The detector is a guard only: its output does not create any fruit boxes.
    It prevents a red shirt, bag, vehicle, or tool from being accepted when a
    camera frame also contains green vegetation.
    """
    global OBJECT_GUARD_MODEL
    if frame_bgr is None or frame_bgr.size == 0 or not os.path.exists(OBJECT_GUARD_PATH):
        return []

    try:
        if OBJECT_GUARD_MODEL is None:
            from ultralytics import YOLO
            OBJECT_GUARD_MODEL = YOLO(OBJECT_GUARD_PATH)
        result = OBJECT_GUARD_MODEL.predict(frame_bgr, conf=0.45, verbose=False)[0]
        boxes = getattr(result, "boxes", None)
        if boxes is None or len(boxes) == 0:
            return []
        names = getattr(OBJECT_GUARD_MODEL, "names", {}) or {}
        return [
            tuple(map(float, box))
            for box, class_id in zip(boxes.xyxy.tolist(), boxes.cls.tolist())
            if str(names.get(int(class_id), "")).strip().lower() in OBJECT_GUARD_LABELS
        ]
    except Exception as exc:
        # Guard-model issues must not make fruit detection unavailable.
        print(f"Object guard unavailable: {exc}")
        return []


def mature_core_ratio(frame_bgr, x: int, y: int, width: int, height: int) -> float:
    """Return the share of a candidate occupied by the canonical ripe pink/red colour.

    The wider HSV mask used for still photos intentionally includes orange highlights.
    This second measurement stays narrow so an occluded fruit can be accepted without
    turning sunlit grass, dry stems, or soil into an additional fruit.
    """
    roi = frame_bgr[y : y + height, x : x + width]
    if roi.size == 0:
        return 0.0

    hsv = cv2.cvtColor(roi, cv2.COLOR_BGR2HSV)
    red_low = cv2.inRange(hsv, np.array([0, 85, 100]), np.array([12, 255, 255]))
    red_high = cv2.inRange(hsv, np.array([145, 85, 100]), np.array([180, 255, 255]))
    return cv2.countNonZero(cv2.bitwise_or(red_low, red_high)) / float(width * height)


def validate_dragonfruit_maturity_scene(frame_bgr) -> dict:
    """Accept maturity detection only when dragon-fruit plant tissue is visible.

    The maturity model contains a positive mature-fruit class, not an
    "unrelated image" class. This image-level gate therefore prevents a face,
    fabric, vehicle, or another crop from being counted as fruit. It is
    intentionally conservative: a false negative is safer than changing the
    yield record with a false fruit.
    """
    if frame_bgr is None or frame_bgr.size == 0:
        return {"valid": False, "reason": "unreadable_image"}

    hsv = cv2.cvtColor(frame_bgr, cv2.COLOR_BGR2HSV)
    green_mask = cv2.inRange(
        hsv, np.array([25, 65, 45]), np.array([95, 255, 255])
    )
    green_mask = cv2.morphologyEx(
        green_mask,
        cv2.MORPH_CLOSE,
        cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (7, 7)),
    )
    label_count, _, stats, _ = cv2.connectedComponentsWithStats(
        green_mask, connectivity=8
    )
    largest_component = (
        int(stats[1:, cv2.CC_STAT_AREA].max()) if label_count > 1 else 0
    )
    frame_area = float(frame_bgr.shape[0] * frame_bgr.shape[1])
    green_ratio = cv2.countNonZero(green_mask) / frame_area
    largest_component_ratio = largest_component / frame_area
    valid = green_ratio >= 0.035 and largest_component_ratio >= 0.007

    return {
        "valid": bool(valid),
        "reason": None if valid else "dragonfruit_plant_context_not_found",
        "green_ratio": float(green_ratio),
        "largest_green_component_ratio": float(largest_component_ratio),
    }


def has_pitaya_fruit_context(frame_bgr, x: int, y: int, width: int, height: int) -> bool:
    """Require cactus tissue immediately around a proposed mature fruit.

    A global green-background check alone can still accept a red shirt or an
    object in a field. Mature pitaya fruits normally show green bracts/stem in
    the area around the red body, so require a small amount of that local
    context before exposing a mature detection.
    """
    if frame_bgr is None or frame_bgr.size == 0 or width <= 0 or height <= 0:
        return False

    frame_height, frame_width = frame_bgr.shape[:2]
    padding = max(8, int(round(max(width, height) * 0.30)))
    left, top = max(0, x - padding), max(0, y - padding)
    right, bottom = min(frame_width, x + width + padding), min(frame_height, y + height + padding)
    roi = frame_bgr[top:bottom, left:right]
    if roi.size == 0:
        return False

    hsv = cv2.cvtColor(roi, cv2.COLOR_BGR2HSV)
    green = cv2.inRange(hsv, np.array([25, 65, 45]), np.array([95, 255, 255]))

    # Exclude the fruit body itself: the green evidence must be adjacent plant
    # tissue, not a green patch inside an unrelated object.
    fruit_left, fruit_top = x - left, y - top
    fruit_right, fruit_bottom = fruit_left + width, fruit_top + height
    green[fruit_top:fruit_bottom, fruit_left:fruit_right] = 0
    surrounding_area = max(1, (right - left) * (bottom - top) - (width * height))
    return cv2.countNonZero(green) / float(surrounding_area) >= 0.012


def has_dragonfruit_bracts(frame_bgr, box) -> bool:
    """Check for green scale tips inside a close-up mature fruit box.

    This is used for live capture, where a red shirt in front of a plant can
    otherwise satisfy both a one-class model and the surrounding-green check.
    A real dragon fruit normally has a small amount of green bract tissue in
    its bounding box; background vegetation outside the box cannot satisfy it.
    """
    x1, y1, x2, y2 = map(int, box)
    x1, y1 = max(0, x1), max(0, y1)
    x2 = min(frame_bgr.shape[1], x2)
    y2 = min(frame_bgr.shape[0], y2)
    if x2 <= x1 or y2 <= y1:
        return False

    roi = frame_bgr[y1:y2, x1:x2]
    height, width = roi.shape[:2]
    inset_x, inset_y = max(1, int(width * 0.08)), max(1, int(height * 0.08))
    interior = roi[inset_y : height - inset_y, inset_x : width - inset_x]
    if interior.size == 0:
        return False

    hsv = cv2.cvtColor(interior, cv2.COLOR_BGR2HSV)
    green = cv2.inRange(hsv, np.array([28, 65, 45]), np.array([95, 255, 255]))
    green_ratio = cv2.countNonZero(green) / float(interior.shape[0] * interior.shape[1])
    # A close camera view can include several bracts in the fruit box.  The
    # previous 8% upper bound rejected those valid close-ups, which is exactly
    # the framing used by Live Capture.  A red non-fruit object still has to
    # pass the model class, ripe-colour and compact-shape checks before this
    # signal is considered.
    return 0.003 <= green_ratio <= 0.25


def is_mature_dragonfruit_candidate(frame_bgr, box, confidence: float = 0.0) -> bool:
    """Return whether a model box looks like a mature dragon fruit.

    This is deliberately the *same* lightweight validation for uploads,
    camera captures, and video frames.  The previous still-photo-only check
    required an almost uniformly red, unobstructed fruit.  Real ripe fruit on
    the plant is often shaded or partly covered by a cactus arm, so that gate
    rejected the custom YOLO model's real detections.

    The custom model class is the primary decision.  These checks only reject
    implausible model boxes: a broad/skinny object, a box without a ripe-colour
    core, or a red object that has no nearby pitaya-plant context.
    """
    x1, y1, x2, y2 = map(int, box)
    width, height = x2 - x1, y2 - y1
    if width <= 0 or height <= 0:
        return False

    # A fruit is compact/oval. This rejects a broad clothing or torso box,
    # even if it is recorded in front of vegetation.
    aspect_ratio = width / float(height)
    if not 0.40 <= aspect_ratio <= 2.10:
        return False

    # Keep colour validation modest.  It confirms that the detected object is
    # ripe without requiring a fully red body, which is unreliable under
    # shadow, glare, blur, and partial occlusion.
    if mature_core_ratio(frame_bgr, x1, y1, width, height) < 0.08:
        return False

    if has_pitaya_fruit_context(frame_bgr, x1, y1, width, height):
        return True

    # In live capture the fruit is commonly held close to the camera.  There
    # may be no surrounding cactus left in the frame, even though its green
    # bracts are visible inside the fruit box.  Treat that as valid plant
    # evidence rather than rejecting every close-up.  Requiring a sizeable
    # ripe core and a box that occupies a meaningful part of the frame keeps
    # this exception narrow and prevents arbitrary small red regions from
    # becoming fruit detections.
    frame_area = float(frame_bgr.shape[0] * frame_bgr.shape[1])
    box_area = float(width * height)
    if (
        frame_area > 0
        and box_area / frame_area >= 0.025
        and mature_core_ratio(frame_bgr, x1, y1, width, height) >= 0.12
        and has_dragonfruit_bracts(frame_bgr, (x1, y1, x2, y2))
    ):
        return True

    # A close-up may crop out the surrounding cactus tissue.  Do not lose a
    # clearly ripe fruit in that case, but allow it only when the detector is
    # very confident, the ripe core is strong, and the complete scene still
    # contains plant context.  This keeps a low-confidence red shirt/object
    # from being accepted just because it is red.
    return (
        float(confidence) >= 0.75
        and mature_core_ratio(frame_bgr, x1, y1, width, height) >= 0.18
        and validate_dragonfruit_maturity_scene(frame_bgr).get("valid", False)
    )


def is_live_mature_dragonfruit(frame_bgr, box, confidence: float = 0.0) -> bool:
    """Backward-compatible name for the common mature-fruit validator."""
    return is_mature_dragonfruit_candidate(frame_bgr, box, confidence)


def is_hsv_fruit_candidate(
    contour, pink_mask, frame_shape, image_mode: bool = False, frame_bgr=None
) -> bool:
    """Accept a substantial, compact pink/red fruit region; reject ground noise."""
    area = float(cv2.contourArea(contour))
    if area <= 0:
        return False

    x, y, width, height = cv2.boundingRect(contour)
    frame_height, frame_width = frame_shape[:2]
    frame_area = float(frame_height * frame_width)
    box_area = float(width * height)
    if box_area <= 0:
        return False

    # Field noise (flowers, soil specks, and shadows) is much smaller than a
    # countable fruit. Partial objects on the edge cannot be counted reliably.
    min_side = max(36, int(min(frame_width, frame_height) * 0.04))
    # A fruit cut off by the edge has unstable contours and is the usual
    # source of an oversized/nearby box as the camera pans.  Wait until the
    # entire fruit is inside the frame before it can enter the tracker.
    edge_margin = max(16, int(round(min_side * 0.75)))
    if (
        min(width, height) < min_side
        or box_area < max(1800.0, frame_area * 0.0015)
        or x <= edge_margin
        or y <= edge_margin
        or x + width >= frame_width - edge_margin
        or y + height >= frame_height - edge_margin
    ):
        return False

    # The still-image workflow photographs the canopy from above; the lowest
    # portion is ground, the tyre, or the stand. Exclude colour-only candidates
    # there instead of letting those objects be labelled as mature fruit.
    if image_mode and (y + (height / 2.0)) >= frame_height * 0.82:
        return False

    extent = area / box_area
    perimeter = float(cv2.arcLength(contour, True))
    circularity = (4.0 * np.pi * area / (perimeter * perimeter)) if perimeter > 0 else 0.0
    aspect_ratio = width / float(max(height, 1))
    pink_ratio = cv2.countNonZero(pink_mask[y : y + height, x : x + width]) / box_area

    mature_core = (
        mature_core_ratio(frame_bgr, x, y, width, height)
        if frame_bgr is not None
        else 0.0
    )
    if frame_bgr is not None:
        has_internal_bracts = has_dragonfruit_bracts(
            frame_bgr, (x, y, x + width, y + height)
        )
        # Green surrounding vegetation alone is too easy to satisfy in a
        # farm scene: a red tool, flower, or shirt can be beside a plant.
        # A mature pitaya has distinctive green bracts in the fruit body, so
        # make that evidence mandatory. It also lets a true close-up pass when
        # the surrounding stem is cropped out of a live camera frame.
        if not has_internal_bracts:
            return False
    standard_shape = (
        extent >= 0.32
        and circularity >= 0.16
        and 0.40 <= aspect_ratio <= 1.90
        and pink_ratio >= 0.18
    )
    if standard_shape:
        # The broad photo mask also sees orange/brown ground texture. A real
        # mature fruit must contain at least a small amount of the canonical
        # ripe red/pink core. This removes the grass/soil boxes in the supplied
        # photo without removing shaded fruits on the plant.
        if image_mode and mature_core < 0.08:
            return False
        return True

    # A mature fruit can be split into irregular red regions when cactus arms cover
    # it. This is common in the still image supplied by the user: the fruit body is
    # ripe but the external contour is no longer circular. Permit that case only for
    # photographs and only when the box has a substantial canonical ripe-colour core.
    # The core check keeps similarly coloured soil and dried plant material rejected.
    if not image_mode or frame_bgr is None:
        return False

    return (
        extent >= 0.30
        and circularity >= 0.10
        and 0.45 <= aspect_ratio <= 1.45
        and pink_ratio >= 0.25
        and mature_core >= 0.14
    )


def detect_occluded_mature_core_boxes(frame_bgr, rejected_regions):
    """Find individual ripe cores when leaves merge two fruits into one contour.

    The normal broad-pink mask is best for full fruits. In a dense canopy, however,
    two mature fruits can be joined to leaves and grass as one large irregular blob.
    This stricter red/pink core pass recovers the individual fruits without accepting
    orange soil or dry leaves, which do not contain the canonical ripe core.
    """
    frame_height, frame_width = frame_bgr.shape[:2]
    frame_area = float(frame_height * frame_width)
    hsv = cv2.cvtColor(frame_bgr, cv2.COLOR_BGR2HSV)
    core_mask = cv2.bitwise_or(
        cv2.inRange(hsv, np.array([0, 85, 100]), np.array([12, 255, 255])),
        cv2.inRange(hsv, np.array([145, 85, 100]), np.array([180, 255, 255])),
    )
    core_mask = cv2.morphologyEx(
        core_mask,
        cv2.MORPH_CLOSE,
        cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (3, 3)),
    )
    contours, _ = cv2.findContours(
        core_mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE
    )

    min_core_area = max(400.0, frame_area * 0.00035)
    boxes = []
    for contour in contours:
        core_area = float(cv2.contourArea(contour))
        if core_area < min_core_area:
            continue

        x, y, width, height = cv2.boundingRect(contour)
        if x <= 1 or y <= 1 or x + width >= frame_width - 1 or y + height >= frame_height - 1:
            continue

        core_center_x = x + (width / 2.0)
        core_center_y = y + (height / 2.0)
        # Recovery is only for cores inside a contour that the regular detector
        # rejected. Without this constraint, the core of an already detected fruit
        # would create a second, oversized box.
        if not any(
            region_x1 <= core_center_x <= region_x2
            and region_y1 <= core_center_y <= region_y2
            for region_x1, region_y1, region_x2, region_y2 in rejected_regions
        ):
            continue

        # A ripe core is only part of the fruit. Expand from its centre to a
        # fruit-sized proposal, while leaving enough separation for neighbouring
        # fruits to remain distinct.
        proposal_width = max(64, int(round(width * 3.0)))
        proposal_height = max(76, int(round(height * 3.0)))
        x1 = max(0, int(round(core_center_x - proposal_width / 2.0)))
        y1 = max(0, int(round(core_center_y - proposal_height / 2.0)))
        x2 = min(frame_width, x1 + proposal_width)
        y2 = min(frame_height, y1 + proposal_height)

        if (y1 + y2) / 2.0 >= frame_height * 0.82:
            continue
        boxes.append((x1, y1, x2, y2))

    return suppress_overlapping_boxes(boxes, iou_threshold=0.30)


def detect_mature_fruits_hsv(frame_bgr, image_mode: bool = False):
    """Exact same HSV detection used for still image capture.
    Returns (annotated_bgr, mature_boxes, immature_boxes).
    mature_boxes / immature_boxes are lists of (x, y, w, h).
    """
    img_h, img_w = frame_bgr.shape[:2]
    img_hsv = cv2.cvtColor(frame_bgr, cv2.COLOR_BGR2HSV)

    lower_green = np.array([28, 70, 60])
    upper_green = np.array([80, 255, 255])
    # Still photos have stronger shadows and sunlight than the video stream.
    # Accept their orange-pink highlights only in image mode; video retains the
    # narrower colour range that prevents ground detections.
    lower_red1 = np.array([0, 70 if image_mode else 85, 85 if image_mode else 100])
    upper_red1 = np.array([24 if image_mode else 12, 255, 255])
    lower_red2 = np.array([140 if image_mode else 145, 70 if image_mode else 85, 85 if image_mode else 100])
    upper_red2 = np.array([180, 255, 255])

    mask_green = cv2.inRange(img_hsv, lower_green, upper_green)
    mask_red1 = cv2.inRange(img_hsv, lower_red1, upper_red1)
    mask_red2 = cv2.inRange(img_hsv, lower_red2, upper_red2)
    mask_pink = cv2.bitwise_or(mask_red1, mask_red2)

    kernel_size = 9 if image_mode else 5
    kernel = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (kernel_size, kernel_size))
    mask_green = cv2.morphologyEx(mask_green, cv2.MORPH_CLOSE, kernel)
    mask_pink = cv2.morphologyEx(mask_pink, cv2.MORPH_CLOSE, kernel)

    # Immature (green) detection disabled; only process pink/mature fruits.
    contours_pink, _ = cv2.findContours(
        mask_pink, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE
    )

    immature_boxes = []
    mature_boxes = []
    rejected_regions = []

    for cnt in contours_pink:
        area = cv2.contourArea(cnt)
        x, y, w_fruit, h_fruit = cv2.boundingRect(cnt)
        if area <= 150 or not is_hsv_fruit_candidate(
            cnt,
            mask_pink,
            frame_bgr.shape,
            image_mode=image_mode,
            frame_bgr=frame_bgr,
        ):
            if image_mode and area > 150:
                rejected_regions.append((x, y, x + w_fruit, y + h_fruit))
            continue
        mature_boxes.append((x, y, w_fruit, h_fruit))

    mature_boxes = suppress_overlapping_boxes(
        [(x, y, x + w_fruit, y + h_fruit) for x, y, w_fruit, h_fruit in mature_boxes]
    )

    if image_mode:
        # Recover nearby mature fruits that the broad mask merged into a single
        # rejected contour. Existing detections win whenever proposals overlap.
        for core_box in detect_occluded_mature_core_boxes(frame_bgr, rejected_regions):
            if any(box_iou(core_box, existing_box) >= 0.30 for existing_box in mature_boxes):
                continue
            x1, y1, x2, y2 = map(int, core_box)
            width, height = x2 - x1, y2 - y1
            # Recovery proposals used to bypass the mature-fruit validation
            # entirely. That let any small red region inside a rejected large
            # contour become a new count. Apply the same ripe-core and bract
            # evidence required by the primary detector.
            if (
                width <= 0
                or height <= 0
                or mature_core_ratio(frame_bgr, x1, y1, width, height) < 0.14
                or not has_dragonfruit_bracts(frame_bgr, core_box)
            ):
                continue
            mature_boxes.append(core_box)

        mature_boxes = suppress_overlapping_boxes(mature_boxes, iou_threshold=0.30)

    mature_boxes = [(x1, y1, x2 - x1, y2 - y1) for x1, y1, x2, y2 in mature_boxes]

    annotated = frame_bgr.copy()
    for x, y, w_f, h_f in mature_boxes:
        # Draw mature fruits with blue boxes only (no text label)
        cv2.rectangle(annotated, (x, y), (x + w_f, y + h_f), (255, 0, 0), 3)

    return annotated, mature_boxes, immature_boxes


def detect_focused_mature_fruits(frame_bgr, image_mode: bool = True):
    """Return individual mature-fruit detections from a focused plant image.

    The available YOLO weights sometimes return one large box around a whole
    dragon-fruit plant.  That cannot be used as a fruit count.  This detector
    starts from each separate ripe pink/red fruit region and applies the
    existing compact-shape and nearby-pitaya-context checks in
    ``detect_mature_fruits_hsv``.  As a result, people, tools, soil, and the
    background are not emitted as mature-fruit boxes.
    """
    if frame_bgr is None or frame_bgr.size == 0:
        return []

    _, boxes, _ = detect_mature_fruits_hsv(frame_bgr, image_mode=image_mode)
    detections = []
    frame_area = float(frame_bgr.shape[0] * frame_bgr.shape[1])
    object_guard_boxes = get_unrelated_object_boxes(frame_bgr)
    for x, y, width, height in boxes:
        if width <= 0 or height <= 0:
            continue
        core_ratio = mature_core_ratio(frame_bgr, x, y, width, height)
        roi_hsv = cv2.cvtColor(
            frame_bgr[y : y + height, x : x + width], cv2.COLOR_BGR2HSV
        )
        broad_ripe_mask = cv2.bitwise_or(
            cv2.inRange(roi_hsv, np.array([0, 70, 85]), np.array([24, 255, 255])),
            cv2.inRange(roi_hsv, np.array([140, 70, 85]), np.array([180, 255, 255])),
        )
        broad_ripe_ratio = cv2.countNonZero(broad_ripe_mask) / float(width * height)

        # A large orange/brown diseased leaf or ground patch can pass the wide
        # colour mask. A true large mature fruit keeps a substantial canonical
        # pink/red core. Small shaded fruits remain allowed, so this does not
        # lose fruit in a canopy photograph.
        if (
            (width * height) / frame_area >= 0.08
            and core_ratio / max(broad_ripe_ratio, 0.001) < 0.33
        ):
            continue

        x2, y2 = x + width, y + height
        center_x, center_y = x + (width / 2.0), y + (height / 2.0)
        # Do not turn a red region inside a detected person or everyday object
        # into a fruit. Adjacent fruits remain valid because their centre is
        # outside the person/object box.
        if any(
            left <= center_x <= right
            and top <= center_y <= bottom
            and (width * height) <= ((right - left) * (bottom - top)) * 0.65
            for left, top, right, bottom in object_guard_boxes
        ):
            continue
        # This score is for display only. The colour/shape/context tests above
        # are the acceptance rule, not a generic-object confidence score.
        confidence = min(0.99, max(0.60, 0.60 + (core_ratio * 1.20)))
        detections.append(
            {
                "box": [float(x), float(y), float(x2), float(y2)],
                "confidence": float(confidence),
                "class_id": 0,
                "label": "MATURE",
                "source": "fruit_region",
            }
        )
    return suppress_overlapping_detections(detections, iou_threshold=0.30)


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
    brightness_mean = float(np.mean(hsv[:, :, 2]))

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


def is_video_mature_fruit(frame_bgr, box) -> bool:
    """Keep ripe fruits that are partly hidden, while rejecting ground colour noise.

    ``is_fully_mature_fruit`` is deliberately very strict and is useful for clean
    fruit crops. In a moving field video, arms and shadows often cover part of a
    clearly pink fruit, causing that check to fail. The HSV detector has already
    verified a fruit-like contour; a substantial ripe-colour core is a safe second
    route for those occluded detections.
    """
    if is_fully_mature_fruit(frame_bgr, box):
        return True

    x1, y1, x2, y2 = map(int, box)
    x1 = max(0, x1)
    y1 = max(0, y1)
    x2 = min(frame_bgr.shape[1], x2)
    y2 = min(frame_bgr.shape[0], y2)
    if x2 <= x1 or y2 <= y1:
        return False

    return mature_core_ratio(frame_bgr, x1, y1, x2 - x1, y2 - y1) >= 0.14


def count_mature_in_video(
    model, source, conf: float = 0.25, max_frames: int = 0, method: str = "color"
) -> dict:
    """Count unique mature fruits in a video/IP-camera stream.

    Args:
        model: Loaded YOLO model.
        source: Path/URL passed directly to model.track (file, webcam index, or IP stream).
        conf: Confidence threshold.
        max_frames: Optional safety limit; 0 means process full video.

    Returns:
        Dictionary with total unique mature fruits and metadata.
    """
    # For camera streams, use the same individual-fruit detector as image
    # uploads. The custom YOLO file is retained only as a fallback because it
    # can occasionally predict a box around an entire plant rather than each
    # fruit.
    if method == "color":
        cap = cv2.VideoCapture(source)
        if not cap.isOpened():
            raise RuntimeError(f"Cannot open video source: {source}")

        unique_ids = set()
        tracks = []
        next_track_id = 1
        frame_count = 0
        min_confirm_hits = 3
        max_missed_frames = 120
        try:
            while True:
                ok, frame = cap.read()
                if not ok:
                    break
                frame_count += 1
                if max_frames and frame_count > max_frames:
                    break

                # Video has stable successive frames, so use its narrower
                # colour range and never use still-photo recovery boxes.
                detections = detect_focused_mature_fruits(frame, image_mode=False)
                frame_h, frame_w = frame.shape[:2]
                max_distance = max(32.0, float(np.hypot(frame_w, frame_h)) * 0.10)
                matched_ids = set()

                for detection in detections:
                    x1, y1, x2, y2 = detection["box"]
                    cx, cy = (x1 + x2) / 2.0, (y1 + y2) / 2.0
                    match = None
                    match_distance = None
                    for track in tracks:
                        if track["id"] in matched_ids:
                            continue
                        distance = float(np.hypot(track["cx"] - cx, track["cy"] - cy))
                        overlap = box_iou(detection["box"], track["box"])
                        if (distance <= max_distance or overlap >= 0.12) and (
                            match_distance is None or distance < match_distance
                        ):
                            match, match_distance = track, distance

                    if match is None:
                        match = {
                            "id": next_track_id,
                            "cx": cx,
                            "cy": cy,
                            "box": detection["box"],
                            "hits": 0,
                        }
                        next_track_id += 1
                        tracks.append(match)
                    match["cx"], match["cy"], match["box"] = cx, cy, detection["box"]
                    match["last_seen"] = frame_count
                    match["hits"] = int(match.get("hits", 0)) + 1
                    matched_ids.add(match["id"])
                    # Confirm across frames before changing the saved count.
                    if match["hits"] >= min_confirm_hits:
                        unique_ids.add(match["id"])

                # A fruit can blink out during autofocus or be covered by an
                # arm. Retain it long enough to reconnect instead of recounting.
                tracks = [
                    track
                    for track in tracks
                    if frame_count - int(track.get("last_seen", frame_count)) <= max_missed_frames
                ]
        finally:
            cap.release()

        return {
            "total_mature_fruits": len(unique_ids),
            "frame_count": frame_count,
            "mature_class_ids": [],
        }

    # Determine which class IDs correspond to "mature" in the model's names mapping.
    mature_class_ids = get_mature_class_ids(model)

    unique_ids = set()
    track_hits = {}
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
        confs = boxes.conf.tolist()
        ids = (
            boxes.id.tolist()
            if getattr(boxes, "id", None) is not None
            else [None] * len(clss)
        )
        frame_bgr = r.orig_img if getattr(r, "orig_img", None) is not None else None

        for index, (cls_id, track_id, box_conf) in enumerate(zip(clss, ids, confs)):
            if track_id is None:
                continue
            if int(cls_id) in mature_class_ids:
                if frame_bgr is not None and index < len(xyxys):
                    if not is_mature_dragonfruit_candidate(
                        frame_bgr, xyxys[index], box_conf
                    ):
                        continue
                track_id = int(track_id)
                track_hits[track_id] = track_hits.get(track_id, 0) + 1
                # A tracked class prediction must survive several frames
                # before it changes the uploaded-video total.  This removes
                # one-frame false positives without making a stable mature
                # fruit invisible to the user.
                if track_hits[track_id] >= 3:
                    unique_ids.add(track_id)

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
            "-pix_fmt",
            "yuv420p",  # Broadest mobile and browser H.264 compatibility
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


def is_annotated_yield_video(source, sample_frames: int = 5) -> bool:
    """Identify a result video produced by this app before it is counted again.

    Result videos have a black status banner with bright-green ``Fruit count`` text
    at the top-left. Re-uploading one as if it were a raw capture changes the colour
    pixels and creates a second, unreliable count. Use several frames so ordinary
    foliage in the same corner is not mistaken for the banner.
    """
    if not isinstance(source, str) or not os.path.exists(source):
        return False

    capture = cv2.VideoCapture(source)
    if not capture.isOpened():
        return False

    banner_frames = 0
    try:
        for _ in range(sample_frames):
            ok, frame = capture.read()
            if not ok:
                break

            height, width = frame.shape[:2]
            banner = frame[4 : min(40, height), 4 : min(230, width)]
            if banner.size == 0:
                continue

            hsv = cv2.cvtColor(banner, cv2.COLOR_BGR2HSV)
            bright_green = cv2.inRange(
                hsv, np.array([35, 160, 150]), np.array([85, 255, 255])
            )
            green_pixels = cv2.countNonZero(bright_green)
            dark_ratio = float(np.mean(hsv[:, :, 2] < 45))
            if green_pixels >= 600 and dark_ratio >= 0.35:
                banner_frames += 1
    finally:
        capture.release()

    return banner_frames >= max(2, min(sample_frames, 3))


def annotate_video_and_count(
    model, source, output_path: str, conf: float = 0.4, method: str = "color"
) -> dict:
    """Process a video with the strict mature-fruit region detector by default.

    It verifies ripe colour, compact fruit shape, surrounding pitaya tissue,
    and green fruit bracts.  The available YOLO weights are retained as an
    optional mode only because they can return one box around an entire plant.
    Writes an annotated video file and returns a running unique fruit count.
    """
    mature_class_ids = get_mature_class_ids(model) if model is not None else set()

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

        # Motion-aware temporal tracker. A fruit can briefly disappear behind an
        # arm or during autofocus; predicting its position lets the same track be
        # reconnected instead of creating a second count.
        next_track_id = 1
        active_tracks = []
        unique_ids = set()
        # Keep a confirmed track for eight seconds.  This is long enough for
        # focus hunting, dropped frames, or a hand briefly crossing the lens,
        # preventing the same fruit from being assigned a second count.
        # Keep counted identities for the whole practical recording window.
        # A fruit that leaves the frame briefly or is revisited later in the
        # same sweep must reconnect to its original identity, never create a
        # second yield count.
        track_max_missed = max(2160, int(round(fps * 45.0)))
        display_hold_frames = max(6, int(round(fps * 0.25)))
        min_confirm_hits = 3

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

            # The same fruit-region detector is used by image upload, browser
            # camera, and video. It produces one box per mature fruit, never a
            # whole-plant box from the unreliable YOLO model.
            # A moving video must not use the broad still-photo recovery pass:
            # it produces oversized boxes that absorb nearby red regions.
            focused_detections = detect_focused_mature_fruits(frame, image_mode=False)
            mature_boxes = [
                (int(d["box"][0]), int(d["box"][1]),
                 int(d["box"][2] - d["box"][0]), int(d["box"][3] - d["box"][1]))
                for d in focused_detections
            ]
            annotated = frame.copy()

            frame_h, frame_w = frame.shape[:2]
            diag = float(np.hypot(frame_w, frame_h))
            now_tick = frame_count
            used_track_ids = set()
            unmatched_tracks = [t for t in active_tracks]

            for x, y, w_fruit, h_fruit in mature_boxes:
                cx = x + (w_fruit / 2.0)
                cy = y + (h_fruit / 2.0)
                box = (x, y, x + w_fruit, y + h_fruit)

                best_track = None
                best_score = None
                for track in unmatched_tracks:
                    if track["id"] in used_track_ids:
                        continue

                    # Predict where the fruit should be after camera motion. The
                    # old tracker compared only against a frozen box, which is why
                    # a yellow hold box could later become a newly counted fruit.
                    frame_gap = max(
                        1, now_tick - int(track.get("last_seen", now_tick))
                    )
                    predicted_cx = track["cx"] + track.get("vx", 0.0) * frame_gap
                    predicted_cy = track["cy"] + track.get("vy", 0.0) * frame_gap
                    previous_box = track.get("box")
                    shift_x = predicted_cx - track["cx"]
                    shift_y = predicted_cy - track["cy"]
                    predicted_box = (
                        previous_box[0] + shift_x,
                        previous_box[1] + shift_y,
                        previous_box[2] + shift_x,
                        previous_box[3] + shift_y,
                    )
                    dx = predicted_cx - cx
                    dy = predicted_cy - cy
                    dist = float(np.hypot(dx, dy))
                    iou = box_iou(box, predicted_box)
                    current_diag = float(np.hypot(w_fruit, h_fruit))
                    previous_diag = float(
                        np.hypot(
                            previous_box[2] - previous_box[0],
                            previous_box[3] - previous_box[1],
                        )
                    )
                    current_area = max(1.0, float(w_fruit * h_fruit))
                    previous_area = max(
                        1.0,
                        float(
                            (previous_box[2] - previous_box[0])
                            * (previous_box[3] - previous_box[1])
                        ),
                    )
                    size_ratio = min(current_area, previous_area) / max(
                        current_area, previous_area
                    )
                    # A counted fruit may be re-segmented into a much smaller box
                    # after a leaf passes in front of it. Keep that identity unless
                    # its predicted position also disagrees; uncounted tracks stay
                    # stricter so nearby fruits are not merged prematurely.
                    min_size_ratio = 0.12 if track.get("counted") else 0.28
                    if size_ratio < min_size_ratio:
                        continue
                    allowed_distance = max(
                        24.0,
                        min(
                            diag * 0.14,
                            0.85 * max(current_diag, previous_diag)
                            + 10.0 * frame_gap,
                        ),
                    )
                    if iou < 0.08 and dist > allowed_distance:
                        continue

                    score = (dist / allowed_distance) - (iou * 0.75)
                    if best_score is None or score < best_score:
                        best_score = score
                        best_track = track

                if best_track is not None and best_score is not None:
                    frame_gap = max(
                        1, now_tick - int(best_track.get("last_seen", now_tick))
                    )
                    measured_vx = (cx - best_track["cx"]) / frame_gap
                    measured_vy = (cy - best_track["cy"]) / frame_gap
                    best_track["vx"] = (
                        0.70 * measured_vx + 0.30 * best_track.get("vx", 0.0)
                    )
                    best_track["vy"] = (
                        0.70 * measured_vy + 0.30 * best_track.get("vy", 0.0)
                    )
                    best_track["cx"] = cx
                    best_track["cy"] = cy
                    best_track["box"] = box
                    best_track["last_seen"] = now_tick
                    best_track["missed"] = 0
                    best_track["hits"] = int(best_track.get("hits", 0)) + 1
                    best_track["consecutive_hits"] = int(
                        best_track.get("consecutive_hits", 0)
                    ) + 1
                    used_track_ids.add(best_track["id"])
                else:
                    track_id = next_track_id
                    next_track_id += 1
                    active_tracks.append(
                        {
                            "id": track_id,
                            "cx": cx,
                            "cy": cy,
                            "box": box,
                            "last_seen": now_tick,
                            "missed": 0,
                            "hits": 1,
                            "consecutive_hits": 1,
                            "vx": 0.0,
                            "vy": 0.0,
                            "counted": False,
                        }
                    )
                    used_track_ids.add(track_id)

            for track in active_tracks:
                if track["id"] not in used_track_ids:
                    track["missed"] = int(track.get("missed", 0)) + 1
                    track["consecutive_hits"] = 0

            for track in active_tracks:
                if (
                    not track.get("counted")
                    and int(track.get("consecutive_hits", 0)) >= min_confirm_hits
                ):
                    unique_ids.add(track["id"])
                    track["counted"] = True

            # Keep tracks alive long enough to survive short detection blinking.
            active_tracks = [t for t in active_tracks if int(t.get("missed", 0)) <= track_max_missed]

            # Keep a briefly missed fruit visible in the same blue style, at its
            # predicted location. This removes the distracting yellow stale box
            # without creating another detection or changing the total.
            for track in active_tracks:
                if (
                    track["id"] in used_track_ids
                    or int(track.get("missed", 0)) > display_hold_frames
                ):
                    continue
                missed_frames = int(track.get("missed", 0))
                x1, y1, x2, y2 = track["box"]
                shift_x = track.get("vx", 0.0) * missed_frames
                shift_y = track.get("vy", 0.0) * missed_frames
                cv2.rectangle(
                    annotated,
                    (int(x1 + shift_x), int(y1 + shift_y)),
                    (int(x2 + shift_x), int(y2 + shift_y)),
                    (255, 0, 0),
                    2,
                )

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
            "total_mature_fruits": len(unique_ids),
            "total_fruits": len(unique_ids),
            "frame_count": frame_count,
            "mature_class_ids": [],
        }

    # ── YOLO tracking mode ───────────────────────────────────────────────────
    # Do not count a one-frame tracker flicker.  A mature fruit must remain
    # classified as the trained mature-fruit class across three frames.
    track_hits = {}
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
                # Do not draw, count, or expose detections from any other
                # model class. This includes people/background classes if a
                # generic model is ever configured by mistake.
                if int(cls_id) not in mature_class_ids:
                    continue
                x1, y1, x2, y2 = map(int, xyxy)
                box_w = x2 - x1
                box_h = y2 - y1
                if frame_area > 0 and (box_w * box_h / frame_area) > 0.55:
                    continue
                if box_w < 20 or box_h < 20:
                    continue
                if not is_mature_dragonfruit_candidate(
                    orig, (x1, y1, x2, y2), box_conf
                ):
                    continue
                is_mature = True
                # Always draw detection boxes in blue for consistency
                color = (255, 0, 0)
                if is_mature and track_id is not None:
                    track_id = int(track_id)
                    track_hits[track_id] = track_hits.get(track_id, 0) + 1
                    if track_hits[track_id] >= 3:
                        unique_ids.add(track_id)
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
        "total_fruits": len(unique_ids),
        "frame_count": frame_count,
        "mature_class_ids": sorted(list(mature_class_ids)),
    }


app = Flask(__name__)
CORS(
    app,
    supports_credentials=True,
    origins="*",
    allow_headers=["Content-Type", "X-CSRFToken", "X-Pitaya-User"],
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


@app.route("/api/uploads/<path:filename>")
def serve_api_uploaded_file(filename):
    """Serve uploaded files via the /api/uploads/* path for frontend compatibility."""
    upload_root = os.path.join(os.getcwd(), "uploads")

    # Normalize input
    filename = str(filename or "").replace("\\", "/").lstrip("/")

    # If the stored string contains 'uploads/' anywhere (absolute paths or prefixed), strip up to it
    if "uploads/" in filename:
        filename = filename.split("uploads/")[-1]

    # Try a few candidate locations so we can handle absolute paths, prefixed values, and basenames
    candidates = [
        os.path.join(upload_root, filename),
        os.path.join(upload_root, os.path.basename(filename)),
    ]

    found_path = None
    for cand in candidates:
        if os.path.exists(cand):
            found_path = cand
            break

    if not found_path:
        # If file not found, return a simple SVG placeholder served from this host
        svg = (
            '<?xml version="1.0" encoding="UTF-8" standalone="no"?>'
            '<svg xmlns="http://www.w3.org/2000/svg" width="300" height="200">'
            '<rect width="100%" height="100%" fill="#f2f2f2"/>'
            '<text x="50%" y="50%" dominant-baseline="middle" text-anchor="middle" '
            'font-family="Arial, Helvetica, sans-serif" font-size="14" fill="#888">'
            'Image not found</text>'
            '</svg>'
        )
        return Response(svg, mimetype="image/svg+xml")

    # Determine MIME type
    lower = found_path.lower()
    if lower.endswith(".mp4"):
        mimetype = "video/mp4"
    elif lower.endswith(".avi"):
        mimetype = "video/x-msvideo"
    elif lower.endswith((".jpg", ".jpeg")):
        mimetype = "image/jpeg"
    elif lower.endswith(".png"):
        mimetype = "image/png"
    else:
        mimetype = None

    if mimetype:
        return send_file(found_path, mimetype=mimetype)
    else:
        return send_file(found_path)


@app.route("/health", methods=["GET"])  # frontend compatibility (simple root health)
@app.route("/api/health", methods=["GET"])  # common API health path
@app.route("/api/dashboard/health", methods=["GET"])  # existing path kept for backward compatibility
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
        user_id = get_request_user_id()
        # Use new data integrity methods
        metrics = db_manager.get_dashboard_metrics(user_id=user_id)
        alerts = db_manager.get_all_alerts_with_detections(user_id=user_id)
        yield_stats = db_manager.get_yield_statistics(user_id=user_id)

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
        stats = db_manager.get_disease_statistics(user_id=get_request_user_id())
        return jsonify(
            {"success": True, "data": stats, "timestamp": datetime.now().isoformat()}
        )
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500


@app.route("/api/dashboard/yield-stats", methods=["GET"])
def get_yield_statistics():
    """Get yield prediction statistics"""
    try:
        stats = db_manager.get_yield_statistics(user_id=get_request_user_id())
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
        fruit_count = body.get("fruit_count")
        mature_fruits = body.get("mature_fruits", fruit_count)
        if mature_fruits is None:
            return (
                jsonify(
                    {
                        "success": False,
                        "error": "mature_fruits (or fruit_count) is required",
                    }
                ),
                400,
            )
        predicted_yield = float(mature_fruits)
        location = str(body.get("location", "Field"))
        season = body.get("season") or None
        upload_type = str(body.get("upload_type", "image"))
        user_id = str(get_request_user_id(body.get("user_id") or "default_user") or "default_user")
        new_id = db_manager.add_yield_prediction(
            predicted_yield=predicted_yield,
            location=location,
            season=season,
            upload_type=upload_type,
            user_id=user_id,
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
        records = db_manager.get_all_yield_predictions(user_id=get_request_user_id())
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


@app.route("/api/dashboard/legacy/migrate-user-data", methods=["POST"])
def migrate_user_data():
    """Move legacy shared records to a specific user scope."""
    try:
        payload = request.get_json(silent=True) or {}
        target_user_id = (
            request.headers.get("X-Pitaya-User")
            or payload.get("target_user_id")
            or request.form.get("target_user_id")
        )
        target_user_id = str(target_user_id or "").strip()
        if not target_user_id:
            return jsonify({"success": False, "error": "target_user_id is required"}), 400

        disease_count, yield_count = migrate_legacy_user_data(target_user_id)
        return jsonify(
            {
                "success": True,
                "message": "Legacy data migrated",
                "data": {
                    "target_user_id": target_user_id,
                    "disease_records": disease_count,
                    "yield_records": yield_count,
                },
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
        alerts = db_manager.get_all_alerts_with_detections(user_id=get_request_user_id())

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
        count = db_manager.get_unread_alert_count(user_id=get_request_user_id())
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
        user_id = get_request_user_id()
        detections = db_manager.get_all_disease_detections(user_id=user_id)

        # Format the response
        formatted_detections = []
        for detection in detections:
            image_path = detection.get("ImagePath")
            formatted_detections.append(
                {
                    "id": detection.get("DetectionID"),
                    "disease_type": detection.get("DiseaseType"),
                    "severity": detection.get("Severity"),
                    "confidence": detection.get("Confidence"),
                    "date_time": detection.get("DateTime"),
                    "location": detection.get("Location", "Unknown"),
                    "image_path": image_path,
                    "image_url": make_uploaded_file_url(image_path),
                    "user_id": detection.get("user_id")
                    or detection.get("UserID")
                    or "",
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
        user_id = get_request_user_id()
        reports = db_manager.get_reports_data(
            start_date=start_date,
            end_date=end_date,
            user_id=user_id,
        )
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
        metrics = db_manager.get_dashboard_metrics(user_id=get_request_user_id())

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
        metrics = db_manager.get_dashboard_metrics(user_id=get_request_user_id())

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
        stats = db_manager.get_yield_statistics(user_id=get_request_user_id())

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
        metrics = db_manager.get_dashboard_metrics(user_id=get_request_user_id())

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
        user_id = get_request_user_id()
        detections = db_manager.get_all_disease_detections(user_id=user_id)

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
                "image_url": make_uploaded_file_url(detection.get("ImagePath")),
                "user_id": detection.get("user_id")
                or detection.get("UserID")
                or "",
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

        # Look for images in the public folder served by Vite.
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
        if not image_urls:
            # Fallback to the curated library images copied to Vite's public
            # output.  The API itself runs from /app, so use the built folder.
            all_disease_path = os.path.join(
                os.getcwd(), "frontend", "dist", "All Disease"
            )
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
                    filename = os.path.basename(img_path)
                    image_urls.append(f"/All%20Disease/{filename.replace(' ', '%20')}")

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

        # Normalize image path to a URL for CSV
        def _image_url(p):
            if not p:
                return ""
            p = str(p).replace('\\', '/')
            if p.startswith('/uploads/'):
                p = p[len('/uploads/'):]
            if p.startswith('uploads/'):
                p = p[len('uploads/'):]
            return f"/api/uploads/{p}"

        # Write combined row
        writer.writerow(
            [
                session_id,
                disease_names,
                max_severity.upper(),
                f"{sum_confidence:.2f}%",
                report_data["DateTime"],
                report_data.get("Location", "Unknown"),
                _image_url(report_data.get("ImagePath") or report_data.get("image_path")),
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
                _image_url(report_data.get("ImagePath") or report_data.get("image_path")),
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

        # The strict fruit-region detector checks ripe colour, compact shape,
        # plant context and fruit bracts.  This avoids whole-plant boxes from
        # the available YOLO weights and rejects unrelated pink/red objects.
        detection_mode = (request.form.get("detection_mode") or "photo").lower()
        is_live_capture = detection_mode == "live"
        conf = mature_confidence_threshold(
            request.form.get("conf"),
            # A phone display, glare, and camera autofocus make a genuine
            # fruit less confident in live capture than in a still photo.
            # The mature-colour, fruit-shape, plant-context and two-frame
            # gates below keep this lower model threshold from counting a
            # person, unrelated object, or plain background.
            minimum=0.40 if is_live_capture else MIN_MATURE_CONFIDENCE,
        )
        method = (request.form.get("method") or "color").lower()
        if method not in {"hybrid", "color", "yolo"}:
            return jsonify({
                "success": False,
                "error": "Unsupported mature-fruit detection method.",
            }), 400
        # Older clients sent "hybrid". Keep that request format compatible
        # while routing it to the current strict fruit-region detector.
        if method == "hybrid":
            method = "color"
        frame_bgr = cv2.imread(img_path)
        if frame_bgr is None:
            return jsonify({"success": False, "error": "Failed to read saved image"}), 400

        # Keep scene information for diagnostics, but do not reject an entire
        # image before the trained detector sees it. A close-up can contain a
        # real ripe fruit with little visible green plant tissue.
        scene_validation = validate_dragonfruit_maturity_scene(frame_bgr)

        detections = []
        if method == "color":
            detections = detect_focused_mature_fruits(frame_bgr, image_mode=True)
        else:
            model = None
            results = []
            try:
                model = load_yolo_model()
                results = list(
                    model.predict(source=img_path, conf=conf, save=False, verbose=False)
                )
            except Exception as exc:
                return jsonify({"success": False, "error": str(exc)}), 500

            r = results[0] if results else None
            boxes = getattr(r, "boxes", None) if r is not None else None
            mature_class_ids = get_mature_class_ids(model)
            if r is not None and getattr(r, "orig_img", None) is not None:
                frame_bgr = r.orig_img

            if boxes is not None and len(boxes) > 0:
                for b, c, cl in zip(
                    boxes.xyxy.tolist(), boxes.conf.tolist(), boxes.cls.tolist()
                ):
                    if int(cl) not in mature_class_ids:
                        continue
                    if not is_mature_dragonfruit_candidate(frame_bgr, b, c):
                        continue
                    detections.append(
                        {
                            "box": [float(v) for v in b],
                            "confidence": float(c),
                            "class_id": int(cl),
                            "label": "MATURE",
                            "source": "yolo",
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
            draw.rectangle([x1, y1, x2, y2], outline="#0066FF", width=3)
            # Compute text size in a way compatible with Pillow versions
            try:
                bbox = draw.textbbox((0, 0), label, font=font)
                text_width = bbox[2] - bbox[0]
                text_height = bbox[3] - bbox[1]
            except AttributeError:
                text_width, text_height = (len(label) * 6, 14)

            text_bg = [x1, max(0, y1 - text_height - 4), x1 + text_width + 6, y1]
            draw.rectangle(text_bg, fill="#0066FF")
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
                "message": (
                    None
                    if detections
                    else NO_MATURE_DETECTION_MESSAGE
                ),
                "scene_validation": scene_validation,
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
      - conf: optional confidence threshold (minimum 0.55)
    """
    try:
        # Confidence threshold (used only for explicit YOLO fallback mode).
        conf = mature_confidence_threshold(
            request.form.get("conf", request.args.get("conf"))
        )

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

            # An annotated result is useful to download and review, but it is not a
            # valid source for another count. Its rendered count banner and boxes
            # alter the pixels and can produce a different total on a second pass.
            if is_annotated_yield_video(source):
                return (
                    jsonify(
                        {
                            "success": False,
                            "error": (
                                "This is already an annotated detection result. "
                                "Please upload the original, unannotated video."
                            ),
                        }
                    ),
                    400,
                )

        annotated_rel = None
        stats = None
        method = (request.form.get("method") or "color").lower()
        if method not in {"hybrid", "color", "yolo"}:
            return jsonify({
                "success": False,
                "error": "Unsupported mature-fruit detection method.",
            }), 400
        if method == "hybrid":
            method = "color"

        model = None
        if method == "yolo":
            try:
                model = load_yolo_model()
            except Exception as e:
                return jsonify({"success": False, "error": str(e)}), 500
        if stream_url:
            # For stream URLs, just count without saving annotated video
            stats = count_mature_in_video(model, source=source, conf=conf, method=method)
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
            original_video_rel = os.path.relpath(video_path, "uploads").replace("\\", "/")
            original_video_url = f"/uploads/{original_video_rel}"

        annotated_video_url = None
        if annotated_rel:
            annotated_video_rel = os.path.relpath(annotated_rel, "uploads").replace("\\", "/")
            annotated_video_url = f"/uploads/{annotated_video_rel}"

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
                    "annotated_video_url": annotated_video_url,
                    "conf": conf,
                    "message": (
                        None
                        if stats.get("total_mature_fruits", 0) > 0
                        else NO_MATURE_DETECTION_MESSAGE
                    ),
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
        user_id = str(get_request_user_id("default_user") or "default_user")

        if request.method == "GET":
            prefs = db_manager.get_user_preferences(user_id)

            return jsonify(
                {
                    "success": True,
                    "data": {
                        "user_id": user_id,
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
                user_id=user_id,
                preferred_language=preferred_language,
                notification_email=notification_email,
                farm_name=farm_name,
                email_notifications_enabled=1 if email_notifications_enabled else 0,
            )

            return jsonify(
                {
                    "success": True,
                    "data": {
                        "user_id": user_id,
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
        user_id = str(
            get_request_user_id(payload.get("user_id") or "default_user")
            or "default_user"
        )

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
            user_id=user_id,
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
