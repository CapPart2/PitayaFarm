from flask import Flask, request, jsonify, send_file, send_from_directory
from flask_cors import CORS
from functools import wraps
from PIL import Image
from io import BytesIO
import tensorflow as tf
import keras
import numpy as np
import cv2
import os
import logging
import json
import datetime
import hashlib
import secrets
import smtplib
import sqlite3
import shutil
from email.message import EmailMessage
from disease_database import (
    get_disease_info,
    get_all_diseases,
    get_diseases_by_severity,
)
from database_models import DatabaseManager
import uuid
from collections import defaultdict
import csv
import io as StringIO
import requests
from datetime import timedelta
from werkzeug.utils import secure_filename

# Setup logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = Flask(__name__)
CORS(
    app,
    origins="*",
    allow_headers=[
        "Content-Type",
        "X-CSRFToken",
        "X-Pitaya-User",
        "x-pitaya-user",
        "Authorization",
    ],
    methods=["GET", "POST", "PUT", "DELETE", "OPTIONS"],
)

# Database manager for alerts and translations
db_manager = DatabaseManager()

# In-memory storage for demonstration (in production, use proper database)
# alerts = []
# reports = []
detection_history = defaultdict(list)

# Configuration
image_size = (224, 224)
class_names = [
    "Anthracnose",
    "Black Spot",
    "Brown Spot",
    "Root Rot",
    "Soft Rot",
    "Stem Rot",
    "Stem_Canker",
    "Twig Blight",
    "White Spot",
]

# Upload configuration
# Use the Railway volume when configured so uploaded evidence survives a
# redeploy.  Local development continues to use the existing uploads folder.
UPLOAD_FOLDER = os.path.join(os.environ.get("PITAYA_DATA_DIR", "."), "uploads")
ALLOWED_EXTENSIONS = {"png", "jpg", "jpeg", "gif"}
MAX_UPLOAD_MIGRATION_CHUNK_BYTES = 25 * 1024 * 1024
if not os.path.exists(UPLOAD_FOLDER):
    os.makedirs(UPLOAD_FOLDER)

FACE_CASCADE = cv2.CascadeClassifier(
    os.path.join(cv2.data.haarcascades, "haarcascade_frontalface_default.xml")
)


def allowed_file(filename):
    return "." in filename and filename.rsplit(".", 1)[1].lower() in ALLOWED_EXTENSIONS


def save_uploaded_file(file):
    """Save uploaded file and return the filename"""
    if file and allowed_file(file.filename):
        # Generate unique filename
        original_extension = file.filename.rsplit(".", 1)[1].lower()
        unique_filename = f"{uuid.uuid4().hex}.{original_extension}"
        filepath = os.path.join(UPLOAD_FOLDER, unique_filename)

        # Save the file
        file.save(filepath)
        return unique_filename
    return None


def get_request_user_id(default=None):
    user_id = request.headers.get("X-Pitaya-User") or request.form.get("user_id")
    if user_id:
        user_id = str(user_id).strip()
        if user_id:
            return user_id
    if default is not None:
        return default
    # Keep user data isolated when scope header is missing.
    return "__missing_user_scope__"


def validate_dragonfruit_stem_image(image_path):
    """Reject obvious non-stem uploads without rejecting damaged yellow stems.

    Disease images often contain little green tissue: a severely infected
    dragon-fruit stem may be yellow, tan, or brown, with only a small green
    section left.  The old RGB-only rule required 8% bright green pixels and
    consequently rejected exactly those images before the disease model ran.
    """
    try:
        image = Image.open(image_path).convert("RGB")
        arr = np.array(image, dtype=np.uint8)

        gray_for_faces = cv2.cvtColor(arr, cv2.COLOR_RGB2GRAY)
        faces = FACE_CASCADE.detectMultiScale(
            gray_for_faces,
            scaleFactor=1.1,
            minNeighbors=5,
            minSize=(40, 40),
        )
        if len(faces) > 0:
            return {
                "valid": False,
                "document_like": False,
                "reason": "person_detected",
                "face_count": int(len(faces)),
            }

        r = arr[:, :, 0].astype(np.int16)
        g = arr[:, :, 1].astype(np.int16)
        b = arr[:, :, 2].astype(np.int16)

        max_rgb = np.maximum(np.maximum(r, g), b)
        min_rgb = np.minimum(np.minimum(r, g), b)
        chroma = max_rgb - min_rgb

        mean_brightness = float(np.mean((r + g + b) / 3.0))
        mean_chroma = float(np.mean(chroma))

        # Paper/doc-like areas are usually bright and near-neutral.
        paper_like = (mean_brightness >= 160) & (chroma <= 20)
        paper_ratio = float(np.mean(paper_like))

        # Stem-like colors: green and brown regions.
        green_mask = (g >= r + 14) & (g >= b + 14) & (g >= 50)
        brown_mask = (r >= 72) & (g >= 40) & (b <= 125) & ((r - g) >= 8)
        # Yellow/tan is an important stem colour in photos of rot/canker. It
        # must be included in the subject check even though it is not "green".
        yellow_mask = (
            (r >= 90)
            & (g >= 70)
            & (b <= 160)
            & ((r - b) >= 35)
            & ((g - b) >= 20)
        )
        plant_mask = green_mask | brown_mask | yellow_mask
        green_ratio = float(np.mean(green_mask))
        brown_ratio = float(np.mean(brown_mask))
        yellow_ratio = float(np.mean(yellow_mask))
        plant_ratio = float(np.mean(plant_mask))

        gray = (0.299 * r + 0.587 * g + 0.114 * b).astype(np.float32)
        gray_std = float(np.std(gray))

        # Simple edge-energy proxy to avoid flat paper surfaces.
        gx = np.abs(np.diff(gray, axis=1))
        gy = np.abs(np.diff(gray, axis=0))
        edge_energy = float(np.mean(gx) + np.mean(gy))

        document_like = (
            (paper_ratio >= 0.62 and plant_ratio <= 0.10)
            or (paper_ratio >= 0.52 and mean_chroma <= 18)
            or (paper_ratio >= 0.45 and plant_ratio <= 0.05 and edge_energy <= 12)
        )

        # Brown/yellow pixels alone also occur in people, furniture, soil, and
        # patterned fabric. The classifier contains disease labels only, so it
        # cannot safely decide that those subjects are a diseased stem. Require
        # visible cactus-green tissue in every accepted image and let a close,
        # focused stem photo include the damaged brown/yellow sections.
        # Camera frames are commonly tighter and darker than uploads. A real
        # diseased stem can therefore have only a narrow healthy-green edge.
        # Keep a plant-colour requirement, but make it attainable for a close
        # stem capture; the deeper centred-stem extractor performs the final
        # background rejection before the disease model is called.
        center_y0, center_y1 = arr.shape[0] // 6, (arr.shape[0] * 5) // 6
        center_x0, center_x1 = arr.shape[1] // 6, (arr.shape[1] * 5) // 6
        central_mask = plant_mask[center_y0:center_y1, center_x0:center_x1]
        central_plant_ratio = float(np.mean(central_mask))
        # A severely diseased stem can be entirely yellow/brown. Accept this
        # only when that material forms a tall, textured subject in the middle
        # of the camera frame--not a face, shirt, or empty background.
        central_row_coverage = float(np.mean(np.mean(central_mask, axis=1) >= 0.10))
        central_dark_ratio = float(
            np.mean(max_rgb[center_y0:center_y1, center_x0:center_x1] <= 100)
        )
        diseased_stem_candidate = (
            plant_ratio >= 0.06
            and central_plant_ratio >= 0.14
            and central_row_coverage >= 0.48
            and central_dark_ratio >= 0.012
        )
        valid = (
            (
                (plant_ratio >= 0.07)
                and central_plant_ratio >= 0.06
                and green_ratio >= 0.01
            )
            or diseased_stem_candidate
            and (paper_ratio <= 0.78)
            and (gray_std >= 16 or edge_energy >= 12)
            and (not document_like)
        )

        return {
            "valid": bool(valid),
            "document_like": bool(document_like),
            "plant_ratio": plant_ratio,
            "central_plant_ratio": central_plant_ratio,
            "central_row_coverage": central_row_coverage,
            "central_dark_ratio": central_dark_ratio,
            "diseased_stem_candidate": bool(diseased_stem_candidate),
            "paper_ratio": paper_ratio,
            "green_ratio": green_ratio,
            "brown_ratio": brown_ratio,
            "yellow_ratio": yellow_ratio,
            "mean_brightness": mean_brightness,
            "mean_chroma": mean_chroma,
            "gray_std": gray_std,
            "edge_energy": edge_energy,
        }
    except Exception as e:
        logger.error(f"Stem subject validation error: {str(e)}")
        return {"valid": False, "document_like": True, "error": str(e)}


# Model paths (try both .keras and .h5)
model_paths = [
    "leaf_disease_model.keras",  # Main model from Disease.ipynb
]

# Load model once at startup
model = None


def init_model():
    """Load the trained model from Disease.ipynb"""
    global model
    if model is None:
        for model_path in model_paths:
            if os.path.exists(model_path):
                try:
                    # The production model was saved by Keras 3.  Loading with
                    # standalone Keras (rather than legacy tf.keras) keeps its
                    # architecture format compatible on Railway.
                    model = keras.models.load_model(model_path, compile=False)
                    logger.info(f" Model loaded: {model_path}")
                    logger.info(f"   Model input shape: {model.input_shape}")
                    logger.info(f"   Model output shape: {model.output_shape}")
                    logger.info(f"   Total parameters: {model.count_params():,}")
                    logger.info(f"   Disease.ipynb model successfully loaded")
                    return model
                except Exception as e:
                    logger.warning(f" Failed to load {model_path}: {str(e)}")

        logger.error(" No model file found!")
        logger.error(f"   Looking for: {model_paths}")
        logger.error("   Please ensure the Disease.ipynb trained model is available")
        raise FileNotFoundError(f"Model not found in: {model_paths}")
    return model


# ===== HEALTH CHECK =====
@app.route("/health", methods=["GET"])
def health():
    return jsonify({"status": "healthy", "message": "API is running!"}), 200


def _android_apk_path():
    """Return the current Android Studio APK from persistent or local storage."""
    configured_path = os.environ.get("PITAYA_ANDROID_APK_PATH")
    candidates = [
        configured_path,
        os.path.join(UPLOAD_FOLDER, "downloads", "app-debug.apk"),
        os.path.join("frontend", "public", "downloads", "app-debug.apk"),
    ]
    for candidate in candidates:
        if candidate and os.path.isfile(candidate):
            return candidate
    return None


@app.route("/downloads/app-debug.apk", methods=["GET"])
def download_android_apk():
    """Download the real Android Studio APK without exposing the data-volume path."""
    apk_path = _android_apk_path()
    if not apk_path:
        return (
            jsonify(
                {
                    "success": False,
                    "error": "The Android APK has not been uploaded to this deployment yet.",
                }
            ),
            404,
        )

    return send_file(
        apk_path,
        as_attachment=True,
        download_name="PITAYA-app-debug.apk",
        mimetype="application/vnd.android.package-archive",
        conditional=True,
    )


@app.route("/api/csrf/", methods=["GET"])
def get_csrf_token():
    """Get CSRF token for form submissions"""
    try:
        import secrets

        token = secrets.token_urlsafe(32)

        return jsonify(
            {"csrfToken": token, "timestamp": datetime.datetime.now().isoformat()}
        )
    except Exception as e:
        return jsonify({"error": str(e)}), 500


# ===== LIBRARY ENDPOINTS =====
@app.route("/library/<path:disease_name>", methods=["GET"])
def get_disease_detail(disease_name):
    try:
        disease = get_disease_info(disease_name)
        if disease:
            return jsonify(disease), 200
        return jsonify({"error": "Disease not found"}), 404
    except Exception as e:
        logger.error(f"Disease detail error: {str(e)}")
        return jsonify({"error": str(e)}), 500


# ===== PRECISE DISEASE DIAGNOSIS =====

# Initialize precise diagnosis system

# ===== PREDICT ENDPOINT =====
# ===== DIRECT DISEASE.IPYNB INTEGRATION =====

# Initialize direct Disease.ipynb integration

# ===== SIMPLE ACCURATE DETECTION =====
from improved_disease_detection import create_improved_predict_function

# Initialize improved detection
simple_predict = create_improved_predict_function()


@app.route("/predict", methods=["POST"])
def predict():
    """Simple and accurate disease detection"""
    try:
        user_id = get_request_user_id()
        if "file" not in request.files:
            return jsonify({"error": "No file part"}), 400

        file = request.files["file"]
        if file.filename == "":
            return jsonify({"error": "No selected file"}), 400

        # Validate file type
        allowed_extensions = {"png", "jpg", "jpeg", "gif"}
        if not (
            "." in file.filename
            and file.filename.rsplit(".", 1)[1].lower() in allowed_extensions
        ):
            return (
                jsonify({"error": "Invalid file type. Allowed: png, jpg, jpeg, gif"}),
                400,
            )

        # Save uploaded file and get filename
        saved_filename = save_uploaded_file(file)
        if not saved_filename:
            return jsonify({"error": "Failed to save uploaded file"}), 400

        saved_file_path = os.path.join(UPLOAD_FOLDER, saved_filename)

        # Hard reject obvious non-stem uploads before running the model.
        subject_check = validate_dragonfruit_stem_image(saved_file_path)
        if not subject_check.get("valid", False):
            # The classifier has no "other subject" class, so a non-stem image
            # must never be forced into one of the disease labels or saved as a
            # detection. Return a successful, explicit no-detection result for
            # the UI instead of an HTTP error.
            return jsonify(
                {
                    "success": True,
                    "detection": {
                        "disease_name": None,
                        "confidence_level": 0,
                        "severity": "none",
                        "message": (
                            "No dragon fruit stem detected. Upload or capture "
                            "a clear dragon fruit stem image."
                        ),
                        "reason": "invalid_subject",
                    },
                    "prediction_details": {
                        "detected_diseases": [],
                        "subject_validation": subject_check,
                    },
                }
            ), 200

        # Use simple accurate detection
        with open(saved_file_path, "rb") as image_file:
            result = simple_predict(image_file)

        logger.info(f"Prediction result: {result.get('success', False)}")

        if result["success"]:
            detection = result["detection"]
            prediction_details = result.get("prediction_details", {})

            if detection and detection.get("reason") == "invalid_subject":
                detection["disease_name"] = None
                detection["confidence_level"] = 0
                detection["severity"] = "none"
                detection["message"] = (
                    "No dragon fruit stem detected. Upload or capture a clear "
                    "dragon fruit stem image."
                )
                return jsonify(
                    {
                        "success": True,
                        "detection": detection,
                        "prediction_details": prediction_details,
                    }
                ), 200

            # Check if multiple diseases were detected
            detected_diseases = prediction_details.get("detected_diseases", [])
            logger.info(f"Detected diseases count: {len(detected_diseases)}")
            if detected_diseases:
                logger.info(
                    f"Detected diseases: {[d['disease_name'] for d in detected_diseases]}"
                )

            if detected_diseases and len(detected_diseases) > 1:
                # Multiple diseases detected - get info for all
                diseases_info = []
                for disease_data in detected_diseases:
                    disease_info = get_disease_info(disease_data["disease_name"])
                    diseases_info.append(
                        {
                            "disease_name": disease_data["disease_name"],
                            "confidence_level": disease_data["confidence"] * 100,
                            "severity": disease_data["severity"],
                            "evidence": disease_data.get("evidence", "whole_stem"),
                            "tile_support": disease_data.get("tile_support", 0),
                            "symptoms": (
                                disease_info.get("symptoms", []) if disease_info else []
                            ),
                            "causes": (
                                disease_info.get("causes", []) if disease_info else []
                            ),
                            "treatment": (
                                disease_info.get("treatment", [])
                                if disease_info
                                else []
                            ),
                            "message": f"{disease_data['disease_name']} detected with {disease_data['confidence']:.1%} confidence",
                        }
                    )

                # This is a preview only. Persisting a detection creates its
                # matching alert and can send a high-severity email, so that
                # must happen only after the user presses "Add Detection".
                alert = {
                    "disease_name": detected_diseases[0]["disease_name"],
                    "severity": detected_diseases[0]["severity"],
                    "confidence": detected_diseases[0]["confidence"],
                    "message": f"Multiple diseases detected! Primary: {detected_diseases[0]['disease_name']}",
                }

                return (
                    jsonify(
                        {
                            "success": True,
                            "detection": {
                                "disease_name": detected_diseases[0][
                                    "disease_name"
                                ],  # Primary disease
                                "confidence_level": detected_diseases[0]["confidence"]
                                * 100,
                                "severity": detected_diseases[0]["severity"],
                                "message": detection["message"],
                                "multiple_diseases": diseases_info,
                            },
                            "alert": alert,
                            "prediction_details": prediction_details,
                        }
                    ),
                    200,
                )

            elif detection["disease_name"]:
                # Single disease detected - maintain backward compatibility
                disease_info = get_disease_info(detection["disease_name"])

                # Keep this alert as preview information. The real alert and
                # any high-severity email are created only by Add Detection.
                alert = {
                    "disease_name": detection["disease_name"],
                    "severity": detection["severity"],
                    "confidence": detection["confidence_level"],
                    "message": detection["message"],
                }

                return (
                    jsonify(
                        {
                            "success": True,
                            "detection": {
                                "disease_name": detection["disease_name"],
                                "confidence_level": detection["confidence_level"],
                                "symptoms": (
                                    disease_info.get("symptoms", [])
                                    if disease_info
                                    else []
                                ),
                                "causes": (
                                    disease_info.get("causes", [])
                                    if disease_info
                                    else []
                                ),
                                "treatment": (
                                    disease_info.get("treatment", [])
                                    if disease_info
                                    else []
                                ),
                                "severity": detection["severity"],
                                "message": detection["message"],
                            },
                            "alert": alert,
                            "prediction_details": prediction_details,
                        }
                    ),
                    200,
                )
            else:
                # No disease detected
                return (
                    jsonify(
                        {
                            "success": True,
                            "detection": detection,
                            "prediction_details": prediction_details,
                        }
                    ),
                    200,
                )
        else:
            return jsonify(result), 400

    except Exception as e:
        logger.error(f"Prediction error: {str(e)}")
        return jsonify({"error": str(e)}), 500


@app.route("/uploads/<path:filename>")
def serve_uploaded_file(filename):
    """Serve files from the uploads directory"""
    try:
        return send_from_directory(UPLOAD_FOLDER, filename)
    except Exception as e:
        logger.error(f"Error serving file {filename}: {str(e)}")
        return jsonify({"error": "File not found"}), 404


@app.errorhandler(404)
def page_not_found(e):
    return jsonify({"error": "Endpoint not found"}), 404


@app.errorhandler(500)
def internal_error(e):
    return jsonify({"error": "Internal server error"}), 500


# ===== ALERT ENDPOINTS =====
@app.route("/api/alerts/unread-count", methods=["GET"])
def get_unread_alerts_count():
    """Get unread alerts count - Database-driven notification count"""
    try:
        count = db_manager.get_unread_alerts_count()
        return jsonify({"success": True, "data": {"count": count}}), 200
    except Exception as e:
        logger.error(f"Unread count error: {str(e)}")
        return jsonify({"success": False, "error": str(e)}), 500


@app.route("/api/alerts/mark-read/<int:alert_id>", methods=["POST"])
def mark_alert_read(alert_id):
    """Mark alert as read - Update Status (Unread → Read)"""
    try:
        success = db_manager.mark_alert_read(alert_id)
        if success:
            # Get updated count
            new_count = db_manager.get_unread_alerts_count()
            return (
                jsonify(
                    {
                        "success": True,
                        "message": "Alert marked as read",
                        "data": {"unread_count": new_count},
                    }
                ),
                200,
            )
        else:
            return jsonify({"success": False, "error": "Alert not found"}), 404
    except Exception as e:
        logger.error(f"Mark read error: {str(e)}")
        return jsonify({"success": False, "error": str(e)}), 500


@app.route("/api/alerts/verify-integrity", methods=["GET"])
def verify_alert_integrity():
    """Verify 1:1 relationship between detections and alerts"""
    try:
        integrity = db_manager.verify_alert_detection_integrity()
        return jsonify({"success": True, "data": integrity}), 200
    except Exception as e:
        logger.error(f"Integrity check error: {str(e)}")
        return jsonify({"success": False, "error": str(e)}), 500


# ===== TRANSLATION ENDPOINTS =====
@app.route("/api/translate/check/<int:disease_id>", methods=["GET"])
def check_translation(disease_id):
    """Check existing translation - Single Source of Truth"""
    try:
        translation = db_manager.get_disease_translation(disease_id)
        if translation:
            return (
                jsonify(
                    {
                        "success": True,
                        "data": {"exists": True, "translation": translation},
                    }
                ),
                200,
            )
        else:
            return (
                jsonify(
                    {"success": True, "data": {"exists": False, "translation": None}}
                ),
                200,
            )
    except Exception as e:
        logger.error(f"Translation check error: {str(e)}")
        return jsonify({"success": False, "error": str(e)}), 500


@app.route("/api/translate/save", methods=["POST"])
def save_translation():
    try:
        auth_header = request.headers.get("Authorization")
        if not auth_header or not auth_header.startswith("Bearer "):
            return (
                jsonify(
                    {"success": False, "error": "Unauthorized - Admin token required"}
                ),
                401,
            )

        token = auth_header.split(" ")[1]
        if token != os.environ.get("ADMIN_TOKEN", "admin-secret-token-12345"):
            return jsonify({"success": False, "error": "Invalid admin token"}), 403

        data = request.get_json()

        required_fields = [
            "disease_id",
            "tagalog_description",
            "tagalog_symptoms",
            "tagalog_causes",
            "tagalog_prevention",
            "tagalog_treatment",
        ]

        for field in required_fields:
            if field not in data:
                return (
                    jsonify({"success": False, "error": f"Missing field: {field}"}),
                    400,
                )

        success = db_manager.save_disease_translation(
            disease_id=data["disease_id"],
            tagalog_description=data["tagalog_description"],
            tagalog_symptoms=data["tagalog_symptoms"],
            tagalog_causes=data["tagalog_causes"],
            tagalog_prevention=data["tagalog_prevention"],
            tagalog_treatment=data["tagalog_treatment"],
            quality_score=data.get("quality_score", 0.0),
        )

        if success:
            return (
                jsonify({"success": True, "message": "Translation saved successfully"}),
                200,
            )
        else:
            return (
                jsonify({"success": False, "error": "Failed to save translation"}),
                500,
            )

    except Exception as e:
        logger.error(f"Save translation error: {str(e)}")
        return jsonify({"success": False, "error": str(e)}), 500


@app.route("/api/translate/batch", methods=["POST"])
def batch_translate():
    """Batch translate multiple diseases - Generate Once Store Forever"""
    try:
        auth_header = request.headers.get("Authorization")
        if not auth_header or not auth_header.startswith("Bearer "):
            return (
                jsonify(
                    {"success": False, "error": "Unauthorized - Admin token required"}
                ),
                401,
            )

        token = auth_header.split(" ")[1]
        if token != os.environ.get("ADMIN_TOKEN", "admin-secret-token-12345"):
            return jsonify({"success": False, "error": "Invalid admin token"}), 403

        data = request.get_json()

        if "diseases" not in data:
            return jsonify({"success": False, "error": "Missing diseases field"}), 400

        disease_names = data["diseases"]
        target_language = data.get("target_language", "tagalog")

        if not isinstance(disease_names, list):
            return (
                jsonify({"success": False, "error": "Diseases must be an array"}),
                400,
            )

        results = []

        for disease_name in disease_names:
            try:
                # Get disease from database
                disease = db_manager.get_disease_by_name(disease_name)

                if not disease:
                    results.append(
                        {
                            "disease_name": disease_name,
                            "success": False,
                            "error": "Disease not found",
                        }
                    )
                    continue

                # Check if translation already exists
                existing_translation = db_manager.get_disease_translation(disease["id"])

                if existing_translation:
                    results.append(
                        {
                            "disease_name": disease_name,
                            "success": True,
                            "translation": existing_translation,
                            "cached": True,
                        }
                    )
                    continue

                # Generate translation (simulated - in real app, this would call translation API)
                tagalog_translation = {
                    "tagalog_description": f"Ang {disease_name} ay isang sakit na nakakaapekto sa pitaya plants.",
                    "tagalog_symptoms": "Mga sintomas: pagkakulay ng dahon, mga spots, at paglala.",
                    "tagalog_causes": "Dahilan: fungal, bacterial, o viral infection.",
                    "tagalog_prevention": "Pag-iwas: proper sanitation at regular inspection.",
                    "tagalog_treatment": "Paggamot: appropriate fungicides o treatment methods.",
                    "quality_score": 0.95,
                }

                # Save translation
                success = db_manager.save_disease_translation(
                    disease_id=disease["id"], **tagalog_translation
                )

                if success:
                    results.append(
                        {
                            "disease_name": disease_name,
                            "success": True,
                            "translation": db_manager.get_disease_translation(
                                disease["id"]
                            ),
                            "cached": False,
                        }
                    )
                else:
                    results.append(
                        {
                            "disease_name": disease_name,
                            "success": False,
                            "error": "Failed to save translation",
                        }
                    )

            except Exception as e:
                logger.error(f"Error translating {disease_name}: {str(e)}")
                results.append(
                    {"disease_name": disease_name, "success": False, "error": str(e)}
                )

        return (
            jsonify(
                {
                    "success": True,
                    "data": {
                        "results": results,
                        "total_processed": len(results),
                        "successful": sum(1 for r in results if r["success"]),
                        "failed": sum(1 for r in results if not r["success"]),
                        "target_language": target_language,
                    },
                }
            ),
            200,
        )

    except Exception as e:
        logger.error(f"Batch translation error: {str(e)}")
        return jsonify({"success": False, "error": str(e)}), 500


@app.route("/api/library/with-translations", methods=["GET"])
def get_library_with_translations():
    """Get all diseases with translations - Toggle Without Reprocessing"""
    try:
        diseases = db_manager.get_disease_library_with_translations()
        return (
            jsonify(
                {
                    "success": True,
                    "data": {"diseases": diseases, "total_count": len(diseases)},
                }
            ),
            200,
        )
    except Exception as e:
        logger.error(f"Library with translations error: {str(e)}")
        return jsonify({"success": False, "error": str(e)}), 500


# ===== LIBRARY ENDPOINT =====
@app.route("/api/library", methods=["GET"])
@app.route("/api/library/", methods=["GET"])
def get_library_api():
    """Return the disease library in the array format used by the web app."""
    try:
        diseases = []
        for disease_name in get_all_diseases():
            disease_info = get_disease_info(disease_name)
            if disease_info:
                # The original disease reference uses concise field names
                # (prevention, treatment, severity), while the Library UI uses
                # the database-style names below.  Send one consistent shape so
                # cards and full details never fall back to empty placeholders.
                diseases.append(
                    {
                        "name": disease_name.replace("_", " "),
                        "description": disease_info.get("description", ""),
                        "symptoms": disease_info.get("symptoms", []),
                        "causes": disease_info.get("causes", []),
                        "prevention_methods": disease_info.get("prevention", []),
                        "recommended_treatments": disease_info.get("treatment", []),
                        "severity_level": disease_info.get("severity", "medium"),
                    }
                )
        return jsonify({"success": True, "data": diseases}), 200
    except Exception as e:
        logger.error(f"Library API error: {str(e)}")
        return jsonify({"success": False, "error": str(e)}), 500


@app.route("/library", methods=["GET"])
def get_library():
    """Get all disease information for library module with persistent counts"""
    try:
        # Get real-time stats from Dashboard API
        disease_counts = {}
        try:
            # Assuming Dashboard API is running on localhost:5001
            response = requests.get(
                "http://127.0.0.1:5001/api/dashboard/disease-stats", timeout=1
            )
            if response.status_code == 200:
                root = response.json()
                data = root.get("data", {})
                # Map disease name to count
                for item in data.get("disease_distribution", []):
                    disease_name_key = item["disease"]
                    current_count = disease_counts.get(disease_name_key, 0)
                    disease_counts[disease_name_key] = current_count + item["count"]
        except Exception as e:
            logger.warning(f"Failed to fetch library stats: {str(e)}")

        all_diseases = {}
        for disease_name in get_all_diseases():
            disease_info = get_disease_info(disease_name)
            if disease_info:
                # Use persistent count if available, otherwise fall back to 0
                count = disease_counts.get(disease_name, 0)

                # Keep local history for timestamp if needed, or just use current time
                history = detection_history.get(disease_name, [])
                last_detected = history[-1]["timestamp"] if history else None

                all_diseases[disease_name] = {
                    **disease_info,
                    "detection_count": count,
                    "last_detected": last_detected,
                }

        return (
            jsonify({"diseases": all_diseases, "total_diseases": len(all_diseases)}),
            200,
        )
    except Exception as e:
        logger.error(f" Library error: {str(e)}")
        return jsonify({"error": str(e)}), 500


# ===== ADMIN AUTHENTICATION MIDDLEWARE =====


def admin_required(f):
    """Decorator to require admin authentication"""

    @wraps(f)
    def decorated_function(*args, **kwargs):
        # Check for admin token in headers
        auth_header = request.headers.get("Authorization")
        if not auth_header or not auth_header.startswith("Bearer "):
            return jsonify({"error": "Unauthorized - Admin token required"}), 401

        token = auth_header.split(" ")[1]

        # Simple token validation (in production, use JWT or proper session management)
        # For now, we'll use a simple token stored in session or environment
        if token != os.environ.get("ADMIN_TOKEN", "admin-secret-token-12345"):
            return jsonify({"error": "Invalid admin token"}), 403

        return f(*args, **kwargs)

    return decorated_function


def get_client_ip():
    """Get client IP address"""
    if request.headers.getlist("X-Forwarded-For"):
        return request.headers.getlist("X-Forwarded-For")[0]
    return request.remote_addr


def init_login_verification_table():
    """Create table for short-lived login verification codes."""
    conn = sqlite3.connect(db_manager.db_path)
    cur = conn.cursor()
    cur.execute("""
        CREATE TABLE IF NOT EXISTS login_verification_codes (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            challenge_id TEXT NOT NULL UNIQUE,
            user_id INTEGER NOT NULL,
            email TEXT NOT NULL,
            code_hash TEXT NOT NULL,
            expires_at TEXT NOT NULL,
            attempts INTEGER DEFAULT 0,
            used INTEGER DEFAULT 0,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP
        )
        """)
    conn.commit()
    conn.close()


def init_signup_verification_table():
    """Create storage for the email confirmation required after registration."""
    conn = sqlite3.connect(db_manager.db_path)
    cur = conn.cursor()
    cur.execute(
        """
        CREATE TABLE IF NOT EXISTS signup_verification_codes (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            challenge_id TEXT NOT NULL UNIQUE,
            user_id INTEGER NOT NULL,
            email TEXT NOT NULL,
            code_hash TEXT NOT NULL,
            expires_at TEXT NOT NULL,
            attempts INTEGER DEFAULT 0,
            used INTEGER DEFAULT 0,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP
        )
        """
    )
    conn.commit()
    conn.close()


def mask_email(email: str) -> str:
    """Return a masked email for API responses."""
    if not email or "@" not in email:
        return ""
    local, domain = email.split("@", 1)
    if len(local) <= 2:
        masked_local = local[:1] + "*"
    else:
        masked_local = local[:2] + "*" * max(1, len(local) - 2)
    return f"{masked_local}@{domain}"


def send_login_verification_email(recipient_email: str, code: str) -> None:
    """Send a one-time login verification code to the user's email."""
    smtp_host = os.getenv("SMTP_HOST", "smtp.gmail.com")
    smtp_port = int(os.getenv("SMTP_PORT", "587"))
    smtp_username = os.getenv("SMTP_USERNAME", "jacofarm1@gmail.com")
    smtp_password = os.getenv("SMTP_PASSWORD", "daml mkle iehe ybny")

    message = EmailMessage()
    message["Subject"] = "PITAYA Login Verification Code"
    message["From"] = f"PITAYA Application <{smtp_username}>"
    message["To"] = recipient_email
    message.set_content(
        (
            "Your PITAYA login verification code is: "
            f"{code}\n\n"
            "This code expires in 10 minutes. If you did not request this login, ignore this email."
        )
    )

    with smtplib.SMTP(smtp_host, smtp_port, timeout=20) as smtp:
        smtp.starttls()
        smtp.login(smtp_username, smtp_password)
        smtp.send_message(message)


def send_signup_verification_email(recipient_email: str, code: str) -> None:
    """Send the code that confirms ownership of a new account's email address."""
    smtp_host = os.getenv("SMTP_HOST", "smtp.gmail.com")
    smtp_port = int(os.getenv("SMTP_PORT", "587"))
    smtp_username = os.getenv("SMTP_USERNAME", "jacofarm1@gmail.com")
    smtp_password = os.getenv("SMTP_PASSWORD", "daml mkle iehe ybny")

    message = EmailMessage()
    message["Subject"] = "Confirm your PITAYA email address"
    message["From"] = f"PITAYA Application <{smtp_username}>"
    message["To"] = recipient_email
    message.set_content(
        "Confirm your PITAYA account with this code: "
        f"{code}\n\n"
        "This code expires in 10 minutes. If you did not create this account, you can ignore this email."
    )

    with smtplib.SMTP(smtp_host, smtp_port, timeout=20) as smtp:
        smtp.starttls()
        smtp.login(smtp_username, smtp_password)
        smtp.send_message(message)


def create_signup_verification_challenge(user_id: int, email: str) -> dict:
    """Create a new confirmation code for a pending registration and email it."""
    init_signup_verification_table()
    raw_code = f"{secrets.randbelow(1000000):06d}"
    code_hash = hashlib.sha256(raw_code.encode("utf-8")).hexdigest()
    challenge_id = uuid.uuid4().hex
    expires_at = (datetime.datetime.now() + datetime.timedelta(minutes=10)).isoformat()

    conn = sqlite3.connect(db_manager.db_path)
    cur = conn.cursor()
    cur.execute(
        "UPDATE signup_verification_codes SET used = 1 WHERE user_id = ? AND used = 0",
        (user_id,),
    )
    cur.execute(
        """
        INSERT INTO signup_verification_codes
        (challenge_id, user_id, email, code_hash, expires_at, attempts, used)
        VALUES (?, ?, ?, ?, ?, 0, 0)
        """,
        (challenge_id, user_id, email, code_hash, expires_at),
    )
    conn.commit()
    conn.close()

    send_signup_verification_email(email, raw_code)
    return {"challenge_id": challenge_id, "email": email, "expires_in_seconds": 600}


def create_login_verification_challenge(user: dict) -> dict:
    """Create and persist a short-lived verification challenge for login."""
    user_id = int(user.get("UserID"))
    email = str((user.get("Email") or "").strip())
    if not email:
        raise ValueError("No email is set for this account")

    raw_code = f"{secrets.randbelow(1000000):06d}"
    code_hash = hashlib.sha256(raw_code.encode("utf-8")).hexdigest()
    challenge_id = uuid.uuid4().hex
    expires_at = (datetime.datetime.now() + datetime.timedelta(minutes=10)).isoformat()

    conn = sqlite3.connect(db_manager.db_path)
    cur = conn.cursor()
    cur.execute(
        "UPDATE login_verification_codes SET used = 1 WHERE user_id = ? AND used = 0",
        (user_id,),
    )
    cur.execute(
        """
        INSERT INTO login_verification_codes (challenge_id, user_id, email, code_hash, expires_at, attempts, used)
        VALUES (?, ?, ?, ?, ?, 0, 0)
        """,
        (challenge_id, user_id, email, code_hash, expires_at),
    )
    conn.commit()
    conn.close()

    send_login_verification_email(email, raw_code)

    return {
        "challenge_id": challenge_id,
        "email": email,
        "expires_in_seconds": 600,
    }


def build_login_success_payload(user: dict) -> dict:
    """Build the response payload returned after successful authentication."""
    is_admin = str(user.get("Role") or "").lower() == "admin"
    payload = {
        "success": True,
        "user": {
            "UserID": user.get("UserID"),
            "Username": user.get("Username"),
            "Email": user.get("Email"),
            "FirstName": user.get("FirstName"),
            "LastName": user.get("LastName"),
            "Role": user.get("Role"),
            "Status": user.get("Status"),
        },
    }
    if is_admin:
        payload["adminToken"] = os.environ.get(
            "ADMIN_TOKEN", "admin-secret-token-12345"
        )
    return payload


# ===== ADMIN API ENDPOINTS =====


@app.route("/api/admin/login", methods=["POST"])
def admin_login():
    """Admin login endpoint - redirects to main login with admin role handling"""
    try:
        data = request.get_json()
        username = data.get("username")
        password = data.get("password")

        if not username or not password:
            return jsonify({"error": "Username and password required"}), 400

        # Verify credentials using database manager
        user = db_manager.verify_user_credentials(username, password)

        if not user:
            return jsonify({"error": "Invalid credentials"}), 401

        if user.get("Role") != "admin":
            return jsonify({"error": "Access denied - Admin only"}), 403

        # Log the login
        db_manager.create_user_log(
            user_id=user.get("UserID"),
            action="LOGIN",
            description=f"Admin {username} logged in",
            ip_address=get_client_ip(),
            user_agent=request.headers.get("User-Agent"),
        )

        # Return admin token for compatibility with frontend
        admin_token = os.environ.get("ADMIN_TOKEN", "admin-secret-token-12345")
        return jsonify({"success": True, "user": user, "adminToken": admin_token}), 200

    except Exception as e:
        logger.error(f"Admin login error: {str(e)}")
        return jsonify({"error": str(e)}), 500


# ===== PUBLIC AUTH API =====
@app.route("/api/auth/register", methods=["POST"])
def api_register():
    try:
        data = request.get_json() or {}
        email = (data.get("email") or "").strip()
        username = (data.get("username") or "").strip()
        password = data.get("password") or ""
        confirm_password = data.get("confirm_password") or ""
        name = (data.get("name") or "").strip()

        if not email or not username or not password or not confirm_password or not name:
            return (
                jsonify(
                    {
                        "success": False,
                        "error": "All fields are required, including password confirmation.",
                    }
                ),
                400,
            )

        # Basic email validation
        import re

        email_re = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")
        if not email_re.match(email):
            return jsonify({"success": False, "error": "Invalid email format"}), 400

        if len(password) < 8:
            return (
                jsonify(
                    {"success": False, "error": "Password must be at least 8 characters."}
                ),
                400,
            )

        if password != confirm_password:
            return jsonify({"success": False, "error": "Passwords do not match."}), 400

        # Prevent duplicate username/email
        conn = __import__("sqlite3").connect(db_manager.db_path)
        cur = conn.cursor()
        cur.execute("SELECT COUNT(*) FROM users WHERE Username = ?", (username,))
        if cur.fetchone()[0] > 0:
            conn.close()
            return jsonify({"success": False, "error": "Username already exists"}), 400
        cur.execute("SELECT COUNT(*) FROM users WHERE Email = ?", (email,))
        if cur.fetchone()[0] > 0:
            conn.close()
            return jsonify({"success": False, "error": "Email already registered"}), 400

        # Split name
        parts = name.split(None, 1)
        first_name = parts[0]
        last_name = parts[1] if len(parts) > 1 else ""

        # The account remains pending until the owner confirms their email address.
        user_id = db_manager.create_user(
            username=username,
            password=password,
            email=email,
            first_name=first_name,
            last_name=last_name,
            role="user",
            status="pending",
        )

        # Log user creation
        db_manager.create_user_log(
            user_id=user_id,
            action="REGISTER",
            description=f"New user registration: {username}",
            ip_address=get_client_ip(),
            user_agent=request.headers.get("User-Agent"),
        )

        conn.close()

        try:
            challenge = create_signup_verification_challenge(user_id, email)
        except Exception:
            logger.exception("Failed to send signup confirmation email")
            return (
                jsonify(
                    {
                        "success": False,
                        "error": "We could not send the confirmation email. Please try again later.",
                    }
                ),
                500,
            )

        return (
            jsonify(
                {
                    "success": True,
                    "message": "Account created. Confirm your email address to finish signing up.",
                    "verification": {
                        "challenge_id": challenge["challenge_id"],
                        "masked_email": mask_email(challenge["email"]),
                        "expires_in_seconds": challenge["expires_in_seconds"],
                    },
                }
            ),
            201,
        )
    except Exception as e:
        logger.error(f"Register error: {str(e)}")
        return jsonify({"success": False, "error": str(e)}), 500


@app.route("/api/auth/verify-signup-email", methods=["POST"])
def api_verify_signup_email():
    """Confirm a newly registered user's email and activate the account."""
    try:
        data = request.get_json() or {}
        challenge_id = str(data.get("challenge_id") or "").strip()
        code = str(data.get("code") or "").strip()
        if not challenge_id or not code:
            return jsonify({"success": False, "error": "Confirmation code is required."}), 400
        if not code.isdigit() or len(code) != 6:
            return jsonify({"success": False, "error": "Enter the 6-digit confirmation code."}), 400

        init_signup_verification_table()
        conn = sqlite3.connect(db_manager.db_path)
        conn.row_factory = sqlite3.Row
        cur = conn.cursor()
        cur.execute(
            """
            SELECT id, user_id, code_hash, expires_at, attempts, used
            FROM signup_verification_codes WHERE challenge_id = ?
            """,
            (challenge_id,),
        )
        row = cur.fetchone()
        if not row:
            conn.close()
            return jsonify({"success": False, "error": "Confirmation request not found."}), 404
        if int(row["used"]):
            conn.close()
            return jsonify({"success": False, "error": "This confirmation code has already been used."}), 400
        if int(row["attempts"]) >= 5:
            conn.close()
            return jsonify({"success": False, "error": "Too many attempts. Request a new code."}), 429
        if datetime.datetime.now() > datetime.datetime.fromisoformat(str(row["expires_at"])):
            cur.execute("UPDATE signup_verification_codes SET used = 1 WHERE id = ?", (row["id"],))
            conn.commit()
            conn.close()
            return jsonify({"success": False, "error": "This code has expired. Request a new code."}), 400

        if hashlib.sha256(code.encode("utf-8")).hexdigest() != row["code_hash"]:
            cur.execute("UPDATE signup_verification_codes SET attempts = attempts + 1 WHERE id = ?", (row["id"],))
            conn.commit()
            conn.close()
            return jsonify({"success": False, "error": "That confirmation code is incorrect."}), 401

        cur.execute("UPDATE signup_verification_codes SET used = 1 WHERE id = ?", (row["id"],))
        conn.commit()
        conn.close()

        user = db_manager.get_user_by_id(int(row["user_id"]))
        if not user:
            return jsonify({"success": False, "error": "Account not found."}), 404
        db_manager.update_user(user_id=user.get("UserID"), status="active")
        db_manager.create_user_log(
            user_id=user.get("UserID"),
            action="EMAIL_CONFIRMED",
            description=f"Email address confirmed for {user.get('Username')}",
            ip_address=get_client_ip(),
            user_agent=request.headers.get("User-Agent"),
        )
        return jsonify({"success": True, "message": "Email confirmed. You can now log in."}), 200
    except Exception:
        logger.exception("Signup email verification error")
        return jsonify({"success": False, "error": "Unable to confirm email right now."}), 500


@app.route("/api/auth/resend-signup-code", methods=["POST"])
def api_resend_signup_code():
    """Send a fresh confirmation code for an unconfirmed account."""
    try:
        data = request.get_json() or {}
        email = str(data.get("email") or "").strip()
        if not email:
            return jsonify({"success": False, "error": "Email is required."}), 400
        user = db_manager.get_user_by_email(email)
        if not user or (user.get("Status") or "").lower() != "pending":
            return jsonify({"success": False, "error": "No unconfirmed account was found for this email."}), 404
        challenge = create_signup_verification_challenge(int(user["UserID"]), email)
        return jsonify({
            "success": True,
            "message": "A new confirmation code has been sent.",
            "verification": {
                "challenge_id": challenge["challenge_id"],
                "masked_email": mask_email(challenge["email"]),
                "expires_in_seconds": challenge["expires_in_seconds"],
            },
        }), 200
    except Exception:
        logger.exception("Resend signup confirmation error")
        return jsonify({"success": False, "error": "Unable to resend the code right now."}), 500


@app.route("/api/auth/login", methods=["POST"])
def api_login():
    try:
        data = request.get_json() or {}
        logger.info(f"Client IP: {get_client_ip()}")
        # Current clients send ``email`` while the legacy login page sends
        # ``username``.  Accept either one so existing accounts can sign in.
        identifier = (data.get("email") or data.get("username") or "").strip()
        password = data.get("password") or ""

        if not identifier or not password:
            return (
                jsonify(
                    {
                        "success": False,
                        "error": "Email or username and password are required",
                    }
                ),
                400,
            )

        user = db_manager.get_user_by_login_identifier(identifier)
        if not user:
            return (
                jsonify(
                    {"success": False, "error": "Invalid email or password"}
                ),
                401,
            )

        pw_hash = hashlib.sha256(password.encode()).hexdigest()
        if pw_hash != user.get("PasswordHash"):
            return (
                jsonify(
                    {"success": False, "error": "Invalid email or password"}
                ),
                401,
            )

        status = (user.get("Status") or "").lower()
        if status == "pending":
            return (
                jsonify(
                    {
                        "success": False,
                        "error": "Please confirm your email address before logging in.",
                    }
                ),
                403,
            )
        if status == "rejected":
            return (
                jsonify({"success": False, "error": "Your account has been rejected."}),
                403,
            )
        if status not in ("active", "verified"):
            # Treat unknown statuses as inactive
            return jsonify({"success": False, "error": "Account is not active"}), 403

        # Email is confirmed during sign-up; login needs only email and password.
        conn = sqlite3.connect(db_manager.db_path)
        cur = conn.cursor()
        cur.execute(
            "UPDATE users SET LastLogin = ? WHERE UserID = ?",
            (datetime.datetime.now().isoformat(), user.get("UserID")),
        )
        conn.commit()
        conn.close()
        db_manager.create_user_log(
            user_id=user.get("UserID"),
            action="LOGIN",
            description=f"User {user.get('Username')} logged in",
            ip_address=get_client_ip(),
            user_agent=request.headers.get("User-Agent"),
        )
        return jsonify(build_login_success_payload(user)), 200

    except Exception as e:
        logger.exception("Login error")
        return jsonify({"success": False, "error": "Internal server error"}), 500


@app.route("/api/auth/verify-login-code", methods=["POST"])
def api_verify_login_code():
    """Verify one-time code and complete login."""
    try:
        init_login_verification_table()
        data = request.get_json() or {}
        challenge_id = str(data.get("challenge_id") or "").strip()
        code = str(data.get("code") or "").strip()

        if not challenge_id or not code:
            return (
                jsonify(
                    {"success": False, "error": "challenge_id and code are required"}
                ),
                400,
            )

        # Check if this is an admin user trying to bypass verification
        # Get the user from the challenge first
        conn = sqlite3.connect(db_manager.db_path)
        conn.row_factory = sqlite3.Row
        cur = conn.cursor()
        cur.execute(
            """
            SELECT user_id FROM login_verification_codes
            WHERE challenge_id = ?
            """,
            (challenge_id,),
        )
        row = cur.fetchone()
        conn.close()

        if not row:
            return (
                jsonify(
                    {"success": False, "error": "Verification challenge not found"}
                ),
                404,
            )

        user = db_manager.get_user_by_id(int(row["user_id"]))
        if not user:
            return jsonify({"success": False, "error": "User not found"}), 404

        # If user is admin, allow login without code verification
        if (user.get("Role") or "").lower() == "admin":
            logger.info(
                f"Admin user {user.get('Username')} bypassing email verification"
            )
            # Mark the challenge as used
            conn = sqlite3.connect(db_manager.db_path)
            cur = conn.cursor()
            cur.execute(
                "UPDATE login_verification_codes SET used = 1 WHERE challenge_id = ?",
                (challenge_id,),
            )
            conn.commit()
            conn.close()

            db_manager.create_user_log(
                user_id=user.get("UserID"),
                action="LOGIN",
                description=f"Admin {user.get('Username')} logged in",
                ip_address=get_client_ip(),
                user_agent=request.headers.get("User-Agent"),
            )
            return jsonify(build_login_success_payload(user)), 200

        # Regular users must provide valid code
        if not code.isdigit() or len(code) != 6:
            return jsonify({"success": False, "error": "Invalid code format"}), 400

        conn = sqlite3.connect(db_manager.db_path)
        conn.row_factory = sqlite3.Row
        cur = conn.cursor()
        cur.execute(
            """
            SELECT id, user_id, code_hash, expires_at, attempts, used
            FROM login_verification_codes
            WHERE challenge_id = ?
            """,
            (challenge_id,),
        )
        row = cur.fetchone()

        if not row:
            conn.close()
            return (
                jsonify(
                    {"success": False, "error": "Verification challenge not found"}
                ),
                404,
            )
        if int(row["used"]) == 1:
            conn.close()
            return (
                jsonify({"success": False, "error": "Verification code already used"}),
                400,
            )
        if int(row["attempts"]) >= 5:
            conn.close()
            return (
                jsonify(
                    {
                        "success": False,
                        "error": "Too many attempts. Please login again.",
                    }
                ),
                429,
            )

        expires_at = datetime.datetime.fromisoformat(str(row["expires_at"]))
        if datetime.datetime.now() > expires_at:
            cur.execute(
                "UPDATE login_verification_codes SET used = 1 WHERE id = ?",
                (row["id"],),
            )
            conn.commit()
            conn.close()
            return (
                jsonify(
                    {
                        "success": False,
                        "error": "Verification code expired. Please login again.",
                    }
                ),
                400,
            )

        code_hash = hashlib.sha256(code.encode("utf-8")).hexdigest()
        if code_hash != row["code_hash"]:
            cur.execute(
                "UPDATE login_verification_codes SET attempts = attempts + 1 WHERE id = ?",
                (row["id"],),
            )
            conn.commit()
            conn.close()
            return (
                jsonify({"success": False, "error": "Invalid verification code"}),
                401,
            )

        cur.execute(
            "UPDATE login_verification_codes SET used = 1 WHERE id = ?", (row["id"],)
        )
        conn.commit()
        conn.close()

        user = db_manager.get_user_by_id(int(row["user_id"]))
        if not user:
            return jsonify({"success": False, "error": "User not found"}), 404

        db_manager.update_user(user_id=user.get("UserID"), password=None, status=None)
        db_manager.create_user_log(
            user_id=user.get("UserID"),
            action="LOGIN",
            description=f"User {user.get('Username')} logged in (email verified)",
            ip_address=get_client_ip(),
            user_agent=request.headers.get("User-Agent"),
        )

        return jsonify(build_login_success_payload(user)), 200
    except Exception:
        logger.exception("Verify login code error")
        return jsonify({"success": False, "error": "Internal server error"}), 500


# Serve auth static pages (optional simple flow)
@app.route("/auth/login", methods=["GET"])
def serve_login_page():
    try:
        return send_file("auth/login.html")
    except Exception:
        return jsonify({"error": "Login page not found"}), 404


@app.route("/auth/register", methods=["GET"])
def serve_register_page():
    try:
        return send_file("auth/register.html")
    except Exception:
        return jsonify({"error": "Register page not found"}), 404


@app.route("/api/user/preferences", methods=["GET", "POST"])
def user_preferences():
    """Get or update profile and notification preferences."""
    try:
        user_id = get_request_user_id()

        if request.method == "GET":
            prefs = db_manager.get_user_preferences(user_id)

            return (
                jsonify(
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
                        "timestamp": datetime.datetime.now().isoformat(),
                    }
                ),
                200,
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

            return (
                jsonify(
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
                        "timestamp": datetime.datetime.now().isoformat(),
                    }
                ),
                200,
            )

        return jsonify({"success": False, "error": "Method not allowed"}), 405

    except Exception as e:
        logger.exception("Preferences error")
        return jsonify({"success": False, "error": str(e)}), 500


@app.route("/api/admin/dashboard/metrics", methods=["GET"])
@admin_required
def get_admin_dashboard_metrics():
    """Get admin dashboard metrics"""
    try:
        metrics = db_manager.get_admin_dashboard_metrics()
        return jsonify({"success": True, "data": metrics}), 200
    except Exception as e:
        logger.error(f"Admin dashboard metrics error: {str(e)}")
        return jsonify({"success": False, "error": str(e)}), 500


@app.route("/api/admin/database/restore", methods=["POST"])
@admin_required
def restore_database_backup():
    """Restore a verified SQLite backup into the persistent production volume.

    This endpoint is intentionally admin-token protected. It is used for a
    controlled migration from the local capstone database and keeps a timestamped
    copy of the current production database before replacing it.
    """
    backup_file = request.files.get("database")
    if not backup_file or not backup_file.filename:
        return jsonify({"success": False, "error": "Database file is required"}), 400

    if not backup_file.filename.lower().endswith(".db"):
        return jsonify({"success": False, "error": "Only SQLite .db files are allowed"}), 400

    target_path = db_manager.db_path
    temp_path = f"{target_path}.restore-{uuid.uuid4().hex}.tmp"
    try:
        backup_file.save(temp_path)

        # Do not replace production data with a corrupt or unrelated upload.
        conn = sqlite3.connect(temp_path)
        integrity = conn.execute("PRAGMA integrity_check").fetchone()[0]
        tables = {
            row[0]
            for row in conn.execute(
                "SELECT name FROM sqlite_master WHERE type = 'table'"
            )
        }
        conn.close()
        required_tables = {"users", "disease_detections", "yield_predictions"}
        if integrity != "ok" or not required_tables.issubset(tables):
            return (
                jsonify({"success": False, "error": "Invalid PITAYA database backup"}),
                400,
            )

        if os.path.exists(target_path):
            timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
            shutil.copy2(target_path, f"{target_path}.backup_{timestamp}")
        os.replace(temp_path, target_path)
        logger.info("Production database restored from verified admin backup")
        return jsonify({"success": True, "message": "Database restored successfully"}), 200
    except Exception as e:
        logger.exception("Database restore failed")
        return jsonify({"success": False, "error": str(e)}), 500
    finally:
        if os.path.exists(temp_path):
            os.remove(temp_path)


def _migration_destination(relative_path):
    """Return a safe path within the persistent uploads volume."""
    normalized = str(relative_path or "").replace("\\", "/").lstrip("/")
    parts = [part for part in normalized.split("/") if part and part not in (".", "..")]
    if not parts or len(parts) != len(normalized.split("/")):
        raise ValueError("Invalid upload path")

    upload_root = os.path.abspath(UPLOAD_FOLDER)
    destination = os.path.abspath(os.path.join(upload_root, *parts))
    if os.path.commonpath([upload_root, destination]) != upload_root:
        raise ValueError("Upload path is outside the data volume")
    return destination


@app.route("/api/admin/uploads/migration-status", methods=["POST"])
@admin_required
def get_upload_migration_status():
    """Report the resumable offset for one protected upload migration file."""
    payload = request.get_json(silent=True) or {}
    try:
        destination = _migration_destination(payload.get("path"))
        expected_size = int(payload.get("size", -1))
        if expected_size < 0:
            raise ValueError("A valid file size is required")

        if os.path.isfile(destination) and os.path.getsize(destination) == expected_size:
            return jsonify({"success": True, "complete": True, "offset": expected_size})

        temporary_path = f"{destination}.migrating"
        offset = os.path.getsize(temporary_path) if os.path.isfile(temporary_path) else 0
        return jsonify({"success": True, "complete": False, "offset": offset})
    except (TypeError, ValueError) as error:
        return jsonify({"success": False, "error": str(error)}), 400


@app.route("/api/admin/uploads/migrate-chunk", methods=["POST"])
@admin_required
def migrate_upload_chunk():
    """Write one ordered upload chunk into the persistent Railway volume."""
    uploaded_chunk = request.files.get("chunk")
    try:
        destination = _migration_destination(request.form.get("path"))
        offset = int(request.form.get("offset", -1))
        total_size = int(request.form.get("total_size", -1))
        if not uploaded_chunk or offset < 0 or total_size < 0:
            raise ValueError("Path, offset, total size, and chunk are required")

        chunk_data = uploaded_chunk.read(MAX_UPLOAD_MIGRATION_CHUNK_BYTES + 1)
        if not chunk_data or len(chunk_data) > MAX_UPLOAD_MIGRATION_CHUNK_BYTES:
            raise ValueError("Invalid migration chunk size")
        if offset + len(chunk_data) > total_size:
            raise ValueError("Chunk exceeds the declared file size")

        os.makedirs(os.path.dirname(destination), exist_ok=True)
        if os.path.isfile(destination) and os.path.getsize(destination) == total_size:
            return jsonify({"success": True, "complete": True, "offset": total_size})

        temporary_path = f"{destination}.migrating"
        current_size = os.path.getsize(temporary_path) if os.path.isfile(temporary_path) else 0
        if offset > current_size:
            return jsonify({"success": False, "error": "Chunk is out of order", "offset": current_size}), 409
        if offset < current_size and offset + len(chunk_data) < current_size:
            return jsonify({"success": True, "complete": False, "offset": current_size})

        mode = "r+b" if os.path.exists(temporary_path) else "wb"
        with open(temporary_path, mode) as target:
            target.seek(offset)
            target.write(chunk_data)

        received_size = os.path.getsize(temporary_path)
        if received_size == total_size:
            os.replace(temporary_path, destination)
            return jsonify({"success": True, "complete": True, "offset": total_size})
        return jsonify({"success": True, "complete": False, "offset": received_size})
    except (TypeError, ValueError) as error:
        return jsonify({"success": False, "error": str(error)}), 400
    except Exception as error:
        logger.exception("Upload migration chunk failed")
        return jsonify({"success": False, "error": str(error)}), 500


# ===== ADMIN: USER MANAGEMENT ENDPOINTS =====


@app.route("/api/admin/users", methods=["GET"])
@admin_required
def get_all_users():
    """Get all users"""
    try:
        users = db_manager.get_all_users()
        return jsonify({"success": True, "data": users}), 200
    except Exception as e:
        logger.error(f"Get users error: {str(e)}")
        return jsonify({"success": False, "error": str(e)}), 500


@app.route("/api/admin/users/<int:user_id>", methods=["GET"])
@admin_required
def get_user(user_id):
    """Get user by ID"""
    try:
        user = db_manager.get_user_by_id(user_id)
        if not user:
            return jsonify({"success": False, "error": "User not found"}), 404
        return jsonify({"success": True, "data": user}), 200
    except Exception as e:
        logger.error(f"Get user error: {str(e)}")
        return jsonify({"success": False, "error": str(e)}), 500


@app.route("/api/admin/users", methods=["POST"])
@admin_required
def create_user():
    """Create a new user"""
    try:
        data = request.get_json()

        required_fields = ["username", "password"]
        for field in required_fields:
            if field not in data:
                return (
                    jsonify({"success": False, "error": f"Missing field: {field}"}),
                    400,
                )

        user_id = db_manager.create_user(
            username=data["username"],
            password=data["password"],
            email=data.get("email"),
            first_name=data.get("first_name"),
            last_name=data.get("last_name"),
            role=data.get("role", "user"),
            status=data.get("status", "active"),
        )

        # Log the action
        db_manager.create_user_log(
            user_id=None,  # Admin user ID would be from token in production
            action="CREATE_USER",
            description=f"Created user {data['username']}",
            ip_address=get_client_ip(),
            user_agent=request.headers.get("User-Agent"),
        )

        return jsonify({"success": True, "data": {"user_id": user_id}}), 201
    except Exception as e:
        logger.error(f"Create user error: {str(e)}")
        return jsonify({"success": False, "error": str(e)}), 500


@app.route("/api/admin/users/<int:user_id>", methods=["PUT"])
@admin_required
def update_user(user_id):
    """Update user"""
    try:
        data = request.get_json()

        success = db_manager.update_user(
            user_id=user_id,
            email=data.get("email"),
            first_name=data.get("first_name"),
            last_name=data.get("last_name"),
            role=data.get("role"),
            status=data.get("status"),
            password=data.get("password"),
        )

        if not success:
            return (
                jsonify(
                    {"success": False, "error": "User not found or no changes made"}
                ),
                404,
            )

        # Log the action
        db_manager.create_user_log(
            user_id=None,
            action="UPDATE_USER",
            description=f"Updated user {user_id}",
            ip_address=get_client_ip(),
            user_agent=request.headers.get("User-Agent"),
        )

        return jsonify({"success": True, "message": "User updated successfully"}), 200
    except Exception as e:
        logger.error(f"Update user error: {str(e)}")
        return jsonify({"success": False, "error": str(e)}), 500


@app.route("/api/admin/users/<int:user_id>", methods=["DELETE"])
@admin_required
def delete_user(user_id):
    """Delete user"""
    try:
        success = db_manager.delete_user(user_id)

        if not success:
            return jsonify({"success": False, "error": "User not found"}), 404

        # Log the action
        db_manager.create_user_log(
            user_id=None,
            action="DELETE_USER",
            description=f"Deleted user {user_id}",
            ip_address=get_client_ip(),
            user_agent=request.headers.get("User-Agent"),
        )

        return jsonify({"success": True, "message": "User deleted successfully"}), 200
    except Exception as e:
        logger.error(f"Delete user error: {str(e)}")
        return jsonify({"success": False, "error": str(e)}), 500


# ===== ADMIN: USER LOGS ENDPOINTS =====


@app.route("/api/admin/logs", methods=["GET"])
@admin_required
def get_user_logs():
    """Get user logs with optional filters"""
    try:
        start_date = request.args.get("start_date")
        end_date = request.args.get("end_date")
        user_id = request.args.get("user_id")
        action = request.args.get("action")
        limit = int(request.args.get("limit", 100))

        logs = db_manager.get_all_user_logs(
            start_date=start_date,
            end_date=end_date,
            user_id=int(user_id) if user_id else None,
            action=action,
            limit=limit,
        )

        return jsonify({"success": True, "data": logs}), 200
    except Exception as e:
        logger.error(f"Get user logs error: {str(e)}")
        return jsonify({"success": False, "error": str(e)}), 500


# ===== ADMIN: SITE SETTINGS ENDPOINTS =====


@app.route("/api/admin/settings", methods=["GET"])
@admin_required
def get_site_settings():
    """Get site settings"""
    try:
        category = request.args.get("category")
        settings = db_manager.get_site_settings(category=category)
        return jsonify({"success": True, "data": settings}), 200
    except Exception as e:
        logger.error(f"Get site settings error: {str(e)}")
        return jsonify({"success": False, "error": str(e)}), 500


@app.route("/api/admin/settings/<setting_key>", methods=["PUT"])
@admin_required
def update_site_setting(setting_key):
    """Update site setting"""
    try:
        data = request.get_json()
        setting_value = data.get("value")

        if not setting_value:
            return jsonify({"success": False, "error": "Value is required"}), 400

        success = db_manager.update_site_setting(setting_key, setting_value)

        if not success:
            return jsonify({"success": False, "error": "Setting not found"}), 404

        # Log the action
        db_manager.create_user_log(
            user_id=None,
            action="UPDATE_SETTING",
            description=f"Updated setting {setting_key}",
            ip_address=get_client_ip(),
            user_agent=request.headers.get("User-Agent"),
        )

        return (
            jsonify({"success": True, "message": "Setting updated successfully"}),
            200,
        )
    except Exception as e:
        logger.error(f"Update site setting error: {str(e)}")
        return jsonify({"success": False, "error": str(e)}), 500


# ===== ADMIN: DISEASE DETECTIONS MANAGEMENT =====


@app.route("/api/admin/detections", methods=["GET"])
@admin_required
def get_all_detections_admin():
    """Get all disease detections (admin view)"""
    try:
        start_date = request.args.get("start_date")
        end_date = request.args.get("end_date")

        detections = db_manager.get_all_disease_detections(
            start_date=start_date, end_date=end_date
        )

        return jsonify({"success": True, "data": detections}), 200
    except Exception as e:
        logger.error(f"Get detections admin error: {str(e)}")
        return jsonify({"success": False, "error": str(e)}), 500


@app.route("/api/admin/detections/<int:detection_id>", methods=["DELETE"])
@admin_required
def delete_detection_admin(detection_id):
    """Delete disease detection (admin)"""
    try:
        success = db_manager.delete_detection(detection_id)

        if not success:
            return jsonify({"success": False, "error": "Detection not found"}), 404

        # Log the action
        db_manager.create_user_log(
            user_id=None,
            action="DELETE_DETECTION",
            description=f"Deleted detection {detection_id}",
            ip_address=get_client_ip(),
            user_agent=request.headers.get("User-Agent"),
        )

        return (
            jsonify({"success": True, "message": "Detection deleted successfully"}),
            200,
        )
    except Exception as e:
        logger.error(f"Delete detection admin error: {str(e)}")
        return jsonify({"success": False, "error": str(e)}), 500


# ===== ADMIN: YIELD PREDICTIONS MANAGEMENT =====


@app.route("/api/admin/yield-predictions", methods=["GET"])
@admin_required
def get_all_yield_predictions_admin():
    """Get all yield predictions (admin view)"""
    try:
        predictions = db_manager.get_all_yield_predictions()
        return jsonify({"success": True, "data": predictions}), 200
    except Exception as e:
        logger.error(f"Get yield predictions admin error: {str(e)}")
        return jsonify({"success": False, "error": str(e)}), 500


@app.route("/api/admin/yield-predictions/<int:prediction_id>", methods=["DELETE"])
@admin_required
def delete_yield_prediction_admin(prediction_id):
    """Delete yield prediction (admin)"""
    try:
        success = db_manager.delete_yield_prediction(prediction_id)

        if not success:
            return jsonify({"success": False, "error": "Prediction not found"}), 404

        # Log the action
        db_manager.create_user_log(
            user_id=None,
            action="DELETE_YIELD_PREDICTION",
            description=f"Deleted yield prediction {prediction_id}",
            ip_address=get_client_ip(),
            user_agent=request.headers.get("User-Agent"),
        )

        return (
            jsonify(
                {"success": True, "message": "Yield prediction deleted successfully"}
            ),
            200,
        )
    except Exception as e:
        logger.error(f"Delete yield prediction admin error: {str(e)}")
        return jsonify({"success": False, "error": str(e)}), 500


# ===== UTILITY FUNCTIONS =====
def load_image(img):
    """
    Preprocess image to match Disease.ipynb training preprocessing exactly.
    Uses the same preprocessing as the ImageDataGenerator in Disease.ipynb
    """
    try:
        # Convert to RGB if necessary (like in Disease.ipynb)
        if img.mode == "RGBA":
            img = img.convert("RGB")
        elif img.mode == "L":
            img = img.convert("RGB")

        # Resize to 224x224 (Disease.ipynb size)
        resized_img = img.resize((224, 224))

        # Convert to numpy array and normalize to [0,1] (Disease.ipynb preprocessing)
        img_array = tf.keras.preprocessing.image.img_to_array(resized_img)
        img_array = img_array / 255.0

        # Add batch dimension
        input_arr = np.expand_dims(img_array, axis=0)

        return input_arr

    except Exception as e:
        logger.error(f" Error in load_image: {str(e)}")
        return None


def classify(imageExpandedArrayShape):
    """
    Classify image using loaded model.
    Matches Disease.ipynb classify() function.
    """
    # Load model once
    model = init_model()

    # Get predictions
    predictions = model.predict(imageExpandedArrayShape, verbose=0)

    # Process predictions
    rounded_predictions = list(np.around(predictions[0] * 100, 2))
    predicted_class_name = class_names[np.argmax(predictions)]
    predicted_class_accuracy = float(np.max(predictions)) * 100

    predicted_infos = {
        "predictions": [float(pred) for pred in predictions[0]],
        "rounded_predictions": [float(val) for val in rounded_predictions],
        "predicted_class_name": predicted_class_name,
        "predicted_class_acuracy": predicted_class_accuracy,
    }

    return predicted_infos


def generate_alert(disease_name, confidence, disease_info):
    """Generate alert for detected disease"""
    severity = disease_info.get("severity", "medium") if disease_info else "medium"

    # Check for recurring disease
    history = detection_history.get(disease_name, [])
    is_recurring = len(history) > 1

    # Determine alert level
    if severity == "high" or confidence > 80:
        alert_level = "critical"
    elif severity == "medium" or confidence > 60:
        alert_level = "warning"
    else:
        alert_level = "info"

    alert = {
        "id": str(uuid.uuid4()),
        "disease_name": disease_name,
        "severity": severity,
        "confidence": round(confidence, 2),
        "alert_level": alert_level,
        "is_recurring": is_recurring,
        "recommended_action": (
            disease_info.get("treatment", ["Consult agricultural specialist"])[:3]
            if disease_info
            else ["Consult agricultural specialist"]
        ),
        "timestamp": datetime.datetime.now().isoformat(),
        "message": f"{alert_level.title()}: {disease_name} detected with {confidence:.1f}% confidence",
    }

    return alert


def create_report(filename, disease_name, confidence, disease_info):
    """Create detailed report"""
    report = {
        "id": str(uuid.uuid4()),
        "filename": filename,
        "disease_name": disease_name,
        "confidence": round(confidence, 2),
        "timestamp": datetime.datetime.now().isoformat(),
        "symptoms": disease_info.get("symptoms", []) if disease_info else [],
        "causes": disease_info.get("causes", []) if disease_info else [],
        "treatment": disease_info.get("treatment", []) if disease_info else [],
        "severity": (
            disease_info.get("severity", "unknown") if disease_info else "unknown"
        ),
    }

    return report


if __name__ == "__main__":
    try:
        # Pre-load model on startup
        init_model()
        print("Flask API starting...")
        print("Health: http://localhost:5000/health")
        print("Predict: http://localhost:5000/predict (POST)")
        app.run(host="0.0.0.0", port=5000, debug=False)
    except Exception as e:
        logger.error(f"Failed to start API: {str(e)}")
        exit(1)
