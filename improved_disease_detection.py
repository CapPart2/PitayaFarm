#!/usr/bin/env python3
"""
Improved Disease Detection System
Fixes accuracy issues with proper preprocessing, confidence thresholds, and validation
"""

import os
import tensorflow as tf
import numpy as np
from PIL import Image, ImageEnhance, ImageFilter
import logging
import cv2

# Setup logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class ImprovedDiseaseDetection:
    """
    Improved disease detection with better accuracy
    """

    def __init__(self):
        self.model = None
        self.class_names = [
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
        self.img_size = (224, 224)

        # Lowered confidence thresholds to allow multi-disease detection
        self.confidence_thresholds = {
            "Anthracnose": 0.35,
            "Black Spot": 0.30,
            "Brown Spot": 0.30,
            "Root Rot": 0.35,
            "Soft Rot": 0.30,
            "Stem Rot": 0.35,
            "Stem_Canker": 0.30,
            "Twig Blight": 0.30,
            "White Spot": 0.25,
        }

        # Minimum confidence for any disease detection (lowered for multi-disease)
        self.min_confidence = 0.25

    def load_model(self):
        """Load the best available model"""
        try:
            model_paths = [
                "leaf_disease_model_702.keras",
                "leaf_disease_model.keras",
                "leaf_disease_model_0.keras",
            ]

            for model_path in model_paths:
                if os.path.exists(model_path):
                    try:
                        self.model = tf.keras.models.load_model(model_path)
                        logger.info(f"✅ Loaded model: {model_path}")
                        logger.info(f"   Input shape: {self.model.input_shape}")
                        logger.info(f"   Output shape: {self.model.output_shape}")
                        logger.info(f"   Parameters: {self.model.count_params():,}")
                        return True
                    except Exception as e:
                        logger.warning(f"❌ Failed to load {model_path}: {str(e)}")
                        continue

            logger.error("❌ No model files found!")
            return False

        except Exception as e:
            logger.error(f"❌ Error loading model: {str(e)}")
            return False

    def enhance_image(self, image):
        """Enhance image quality before preprocessing"""
        try:
            # Convert to RGB if needed
            if image.mode != "RGB":
                image = image.convert("RGB")

            # Enhance contrast and sharpness
            enhancer = ImageEnhance.Contrast(image)
            image = enhancer.enhance(1.2)

            enhancer = ImageEnhance.Sharpness(image)
            image = enhancer.enhance(1.1)

            # Apply slight sharpening filter
            image = image.filter(
                ImageFilter.UnsharpMask(radius=1, percent=120, threshold=3)
            )

            return image

        except Exception as e:
            logger.error(f"❌ Error enhancing image: {str(e)}")
            return image

    def analyze_image_quality(self, image):
        """Improved image quality analysis using OpenCV"""
        try:
            # Convert to RGB if needed
            if image.mode != "RGB":
                image = image.convert("RGB")

            # Convert to numpy array
            img_array = np.array(image)

            # Convert to grayscale for analysis
            gray = cv2.cvtColor(img_array, cv2.COLOR_RGB2GRAY)

            # 1. Focus (sharpness) - using Laplacian variance
            laplacian_var = cv2.Laplacian(gray, cv2.CV_64F).var()

            # 2. Brightness
            brightness = np.mean(gray)

            # 3. Contrast
            contrast = gray.std()

            # 4. Edge detection (for disease spots)
            edges = cv2.Canny(gray, 50, 150)
            edge_density = np.sum(edges > 0) / edges.size

            # 5. Color variance
            color_variance = np.var(img_array)

            # Quality score (0-1)
            quality_score = 0
            if laplacian_var > 50:  # Better focus threshold
                quality_score += 0.25
            if 50 <= brightness <= 200:  # Good brightness range
                quality_score += 0.25
            if contrast > 30:  # Better contrast requirement
                quality_score += 0.2
            if color_variance > 100:  # Better color variance
                quality_score += 0.15
            if edge_density > 0.01:  # Some edges present (good for disease detection)
                quality_score += 0.15

            return {
                "quality_score": min(quality_score, 1.0),
                "focus_score": laplacian_var,
                "brightness": brightness,
                "contrast": contrast,
                "edge_density": edge_density,
                "is_suitable": quality_score >= 0.5,  # Balanced threshold
            }

        except Exception as e:
            logger.error(f"❌ Error analyzing image quality: {str(e)}")
            return {"quality_score": 0, "is_suitable": False}

    def preprocess_image(self, image):
        """Enhanced preprocessing with proper normalization"""
        try:
            # Enhance image first
            image = self.enhance_image(image)

            # Resize
            image = image.resize(self.img_size, Image.Resampling.LANCZOS)

            # Convert to numpy array
            img_array = np.array(image, dtype=np.float32)

            # Enhanced normalization
            # 1. Standard scaling to [0,1]
            img_array = img_array / 255.0

            # 2. Apply histogram equalization for better contrast
            if len(img_array.shape) == 3:
                # Convert to LAB color space for better processing
                lab = cv2.cvtColor(
                    (img_array * 255).astype(np.uint8), cv2.COLOR_RGB2LAB
                )
                lab[:, :, 0] = cv2.equalizeHist(lab[:, :, 0])  # Equalize L channel
                img_array = cv2.cvtColor(lab, cv2.COLOR_LAB2RGB) / 255.0

            # 3. Add batch dimension
            img_array = np.expand_dims(img_array, axis=0)

            return img_array

        except Exception as e:
            logger.error(f"❌ Error preprocessing image: {str(e)}")
            return None

    def validate_prediction(self, predictions, quality_score):
        """Enhanced prediction validation with multi-disease support"""
        try:
            # Get all predictions for analysis
            all_predictions = {
                self.class_names[i]: float(predictions[0][i])
                for i in range(len(self.class_names))
            }

            # Sort predictions by confidence
            sorted_predictions = sorted(
                all_predictions.items(), key=lambda x: x[1], reverse=True
            )

            # Log all predictions for debugging
            logger.info(f"🔍 All predictions (quality_score: {quality_score:.2f}):")
            for disease_name, confidence in sorted_predictions:
                logger.info(f"  {disease_name}: {confidence:.2%}")

            # Changed approach: Return top 3 diseases regardless of thresholds
            # This ensures multi-disease detection always shows multiple results
            logger.info(f"📊 Using top-3 approach (thresholds disabled)")

            # Get top 3 diseases (or all if less than 3)
            detected_diseases = []
            for disease_name, confidence in sorted_predictions[:3]:
                detected_diseases.append(
                    {
                        "disease_name": disease_name,
                        "confidence": confidence,
                        "severity": self.get_disease_severity(disease_name),
                    }
                )
                logger.info(f"  ✅ {disease_name}: {confidence:.2%}")

            logger.info(f"🎯 Total detected diseases: {len(detected_diseases)}")

            # If no diseases detected, check for healthy leaf
            if not detected_diseases:
                top_confidence = sorted_predictions[0][1]
                if len(sorted_predictions) >= 2:
                    second_confidence = sorted_predictions[1][1]
                    confidence_gap = top_confidence - second_confidence
                    if top_confidence < 0.75 and confidence_gap < 0.15:
                        return {
                            "success": True,
                            "disease_name": None,
                            "confidence": top_confidence,
                            "message": "No clear disease symptoms detected - appears to be healthy leaf",
                            "reason": "likely_healthy",
                            "top_prediction": sorted_predictions[0],
                            "second_prediction": sorted_predictions[1],
                            "all_predictions": sorted_predictions[:3],
                            "detected_diseases": [],
                        }

                return {
                    "success": True,
                    "disease_name": None,
                    "confidence": top_confidence,
                    "message": f"Low confidence detection ({top_confidence:.1%}) - may be healthy leaf or unclear symptoms",
                    "reason": "low_confidence",
                    "predicted_class": sorted_predictions[0][0],
                    "required_confidence": self.confidence_thresholds.get(
                        sorted_predictions[0][0], self.min_confidence
                    )
                    * quality_multiplier,
                    "all_predictions": sorted_predictions[:3],
                    "detected_diseases": [],
                }

            # Return multiple detected diseases
            if len(detected_diseases) == 1:
                # Single disease - maintain backward compatibility
                return {
                    "success": True,
                    "disease_name": detected_diseases[0]["disease_name"],
                    "confidence": detected_diseases[0]["confidence"],
                    "severity": detected_diseases[0]["severity"],
                    "message": f"{detected_diseases[0]['disease_name']} detected with {detected_diseases[0]['confidence']:.1%} confidence",
                    "reason": "disease_detected",
                    "all_predictions": sorted_predictions[:3],
                    "detected_diseases": detected_diseases,
                }
            else:
                # Multiple diseases detected
                return {
                    "success": True,
                    "disease_name": detected_diseases[0][
                        "disease_name"
                    ],  # Primary disease
                    "confidence": detected_diseases[0]["confidence"],
                    "severity": detected_diseases[0]["severity"],
                    "message": f"{len(detected_diseases)} diseases detected - primary: {detected_diseases[0]['disease_name']}",
                    "reason": "multiple_diseases",
                    "all_predictions": sorted_predictions[:5],
                    "detected_diseases": detected_diseases,
                }

        except Exception as e:
            logger.error(f"❌ Error validating prediction: {str(e)}")
            return {"success": False, "error": str(e)}

    def predict_disease(self, image):
        """Enhanced disease prediction with better accuracy"""
        if not self.model:
            if not self.load_model():
                return None

        try:
            # Analyze image quality first
            quality = self.analyze_image_quality(image)

            if not quality["is_suitable"]:
                return {
                    "success": True,
                    "disease_name": None,
                    "confidence": 0,
                    "message": f"Image quality too low for accurate detection (Quality: {quality['quality_score']:.2f})",
                    "reason": "low_image_quality",
                    "quality_details": quality,
                }

            # Preprocess image with enhancements
            processed_image = self.preprocess_image(image)
            if processed_image is None:
                return {"success": False, "error": "Failed to preprocess image"}

            # Make prediction
            predictions = self.model.predict(processed_image, verbose=0)

            # Validate prediction with enhanced logic
            result = self.validate_prediction(predictions, quality["quality_score"])
            result["quality_details"] = quality

            return result

        except Exception as e:
            logger.error(f"❌ Error predicting disease: {str(e)}")
            return {"success": False, "error": str(e)}

    def get_disease_severity(self, disease_name):
        """Get disease severity"""
        severity_mapping = {
            "Anthracnose": "high",
            "Black Spot": "medium",
            "Brown Spot": "medium",
            "Root Rot": "high",
            "Soft Rot": "high",
            "Stem Rot": "high",
            "Stem_Canker": "medium",
            "Twig Blight": "low",
            "White Spot": "low",
        }
        return severity_mapping.get(disease_name, "medium")


def create_improved_predict_function():
    """Create improved predict function for app.py"""
    detector = ImprovedDiseaseDetection()

    def predict_image(image_file):
        """Predict disease from uploaded image file with improved accuracy"""
        try:
            # Read image
            image = Image.open(image_file)

            # Make prediction
            result = detector.predict_disease(image)

            if result["success"]:
                if result["disease_name"]:
                    # Disease detected
                    severity = detector.get_disease_severity(result["disease_name"])

                    return {
                        "success": True,
                        "detection": {
                            "disease_name": result["disease_name"],
                            "confidence_level": round(result["confidence"] * 100, 2),
                            "severity": severity,
                            "message": result["message"],
                            "reason": result["reason"],
                        },
                        "prediction_details": {
                            "all_predictions": result.get("all_predictions", []),
                            "quality_score": result.get("quality_details", {}).get(
                                "quality_score", 0
                            ),
                            "detected_diseases": result.get("detected_diseases", []),
                        },
                    }
                else:
                    # No disease detected
                    return {
                        "success": True,
                        "detection": {
                            "disease_name": None,
                            "confidence_level": round(
                                result.get("confidence", 0) * 100, 2
                            ),
                            "severity": "none",
                            "message": result["message"],
                            "reason": result["reason"],
                        },
                        "prediction_details": {
                            "all_predictions": result.get("all_predictions", []),
                            "quality_score": result.get("quality_details", {}).get(
                                "quality_score", 0
                            ),
                            "detected_diseases": result.get("detected_diseases", []),
                        },
                    }
            else:
                return {
                    "success": False,
                    "error": result.get("error", "Unknown error"),
                    "detection": None,
                }

        except Exception as e:
            logger.error(f"❌ Error in predict_image: {str(e)}")
            return {"success": False, "error": str(e), "detection": None}

    return predict_image


def test_improved_detection():
    """Test improved detection system"""
    print("🧪 Testing Improved Disease Detection")
    print("=" * 50)

    detector = ImprovedDiseaseDetection()

    # Test model loading
    if not detector.load_model():
        print("❌ Failed to load model")
        return False

    print("✅ Model loaded successfully")

    # Test with different image scenarios
    test_cases = [
        ("Healthy Leaf", "green", "Should detect as healthy"),
        ("Disease Symptoms", "disease", "Should detect disease"),
        ("Low Quality", "blurry", "Should reject low quality"),
    ]

    for test_name, test_type, expected in test_cases:
        print(f"\n📋 Test: {test_name}")

        if test_type == "green":
            # Create healthy leaf image
            test_image = Image.new("RGB", (224, 224), color=(34, 139, 34))
            # Add some texture
            for _ in range(100):
                x = np.random.randint(0, 224)
                y = np.random.randint(0, 224)
                test_image.putpixel(
                    (x, y),
                    (
                        34 + np.random.randint(-10, 10),
                        139 + np.random.randint(-20, 20),
                        34 + np.random.randint(-10, 10),
                    ),
                )

        elif test_type == "disease":
            # Create disease symptoms
            test_image = Image.new("RGB", (224, 224), color=(34, 139, 34))
            img_array = np.array(test_image)

            # Add clear disease spots
            for _ in range(15):
                x = np.random.randint(20, 204)
                y = np.random.randint(20, 204)
                radius = np.random.randint(8, 15)

                for i in range(max(0, x - radius), min(224, x + radius)):
                    for j in range(max(0, y - radius), min(224, y + radius)):
                        if (i - x) ** 2 + (j - y) ** 2 <= radius**2:
                            img_array[j, i] = [139, 69, 19]  # Brown spots

            test_image = Image.fromarray(img_array)

        else:  # blurry
            # Create low quality image
            test_image = Image.new("RGB", (100, 100), color="gray")
            test_image = test_image.resize((224, 224), Image.Resampling.NEAREST)

        # Test prediction
        result = detector.predict_disease(test_image)

        if result["success"]:
            if test_type == "green" and result["disease_name"] is None:
                print("✅ PASS: Correctly identified as healthy")
            elif test_type == "disease" and result["disease_name"]:
                print(
                    f"✅ PASS: Detected disease - {result['disease_name']} ({result['confidence']:.1%})"
                )
            elif (
                test_type == "blurry"
                and result["disease_name"] is None
                and "quality" in result["message"].lower()
            ):
                print("✅ PASS: Correctly rejected low quality image")
            else:
                print(f"⚠️ UNEXPECTED: {result['message']}")

            print(f"   Details: {result.get('reason', 'N/A')}")
            if result.get("quality_details"):
                print(
                    f"   Quality Score: {result['quality_details']['quality_score']:.2f}"
                )
        else:
            print(f"❌ FAIL: {result.get('error', 'Unknown error')}")

    print("\n🎉 Improved Detection Test Complete!")
    return True


if __name__ == "__main__":
    test_improved_detection()
