from flask import Flask, request, jsonify, send_file
from flask_cors import CORS
from PIL import Image
from io import BytesIO
import tensorflow as tf
import numpy as np
import os
import logging
import json
import datetime
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

# Setup logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = Flask(__name__)
CORS(app)

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

# Model paths (try both .keras and .h5)
model_paths = [
    "leaf_disease_model.keras",  # Main model from Disease.ipynb
    "leaf_disease_model_702.keras",  # Student ID specific model from Disease.ipynb
    "leaf_disease_model_0.keras",
    "leaf_disease_model_0.h5",
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
                    model = tf.keras.models.load_model(model_path)
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

        # Use simple accurate detection
        result = simple_predict(file)

        logger.info(f"🔍 Prediction result: {result.get('success', False)}")

        if result["success"]:
            detection = result["detection"]
            prediction_details = result.get("prediction_details", {})

            # Check if multiple diseases were detected
            detected_diseases = prediction_details.get("detected_diseases", [])
            logger.info(f"🎯 Detected diseases count: {len(detected_diseases)}")
            if detected_diseases:
                logger.info(
                    f"📋 Detected diseases: {[d['disease_name'] for d in detected_diseases]}"
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

                # Create alert for primary disease
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
                                "message": f"{len(detected_diseases)} diseases detected",
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

                # Create alert
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
        logger.error(f"❌ Prediction error: {str(e)}")
        return jsonify({"error": str(e)}), 500


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
@app.route("/library", methods=["GET"])
def get_library():
    """Get all disease information for library module with persistent counts"""
    try:
        # Get real-time stats from Dashboard API
        disease_counts = {}
        try:
            # Assuming Dashboard API is running on localhost:5001
            response = requests.get(
                "http://localhost:5001/api/dashboard/disease-stats", timeout=1
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
        print("🚀 Flask API starting...")
        print("📍 Health: http://localhost:5000/health")
        print("📍 Predict: http://localhost:5000/predict (POST)")
        app.run(host="0.0.0.0", port=5000, debug=False)
    except Exception as e:
        logger.error(f"Failed to start API: {str(e)}")
        exit(1)
