#!/usr/bin/env python3
"""
Improved Disease Detection System
Fixes accuracy issues with proper preprocessing, confidence thresholds, and validation
"""

import os
import tensorflow as tf
import keras
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

        # Field photos naturally produce softer probabilities than the clean,
        # centred training images.  The old 35-45% floors rejected legitimate
        # diseased stems (including the 26.9% result reported by the app) even
        # after they had passed the stem and image-quality checks.  Keep a
        # modest class floor, with stricter values only for classes that are
        # particularly easy to confuse.
        self.confidence_thresholds = {
            "Anthracnose": 0.25,
            "Black Spot": 0.25,
            "Brown Spot": 0.25,
            "Root Rot": 0.30,
            "Soft Rot": 0.25,
            "Stem Rot": 0.30,
            "Stem_Canker": 0.35,
            "Twig Blight": 0.25,
            "White Spot": 0.25,
        }

        # Minimum confidence for any disease detection.
        self.min_confidence = 0.25
        # Do not require an unrealistically large softmax gap for a real
        # field image. Subject validation and the class floor above are the
        # primary safeguards against unrelated uploads.
        self.min_confidence_gap = 0.02
        # The classifier was trained only on disease classes, so a field image
        # can distribute probability across similar diseases.  A lower score
        # is useful only when independent, overlapping stem tiles agree.
        self.tile_confirmation_confidence = 0.18
        self.tile_confirmation_count = 2

    def required_confidence(self, disease_name, quality_score):
        """Return one consistent confidence floor for every prediction path."""
        base_threshold = self.confidence_thresholds.get(
            disease_name, self.min_confidence
        )
        # Only genuinely poor images need a small confidence penalty.  This
        # avoids a second, stricter fallback rule cancelling a valid result.
        quality_multiplier = 1.0 + max(0.0, 0.35 - float(quality_score)) * 0.10
        return base_threshold * quality_multiplier

    def load_model(self):
        """Load the best available model"""
        try:
            model_paths = ["leaf_disease_model.keras"]

            for model_path in model_paths:
                if os.path.exists(model_path):
                    try:
                        # The .keras file was saved with Keras 3, so use its
                        # native loader instead of the legacy tf.keras loader.
                        self.model = keras.models.load_model(model_path, compile=False)
                        logger.info(f"Loaded model: {model_path}")
                        logger.info(f"   Input shape: {self.model.input_shape}")
                        logger.info(f"   Output shape: {self.model.output_shape}")
                        logger.info(f"   Parameters: {self.model.count_params():,}")
                        return True
                    except Exception as e:
                        logger.warning(f"Failed to load {model_path}: {str(e)}")
                        continue

            logger.error("No model files found!")
            return False

        except Exception as e:
            logger.error(f"Error loading model: {str(e)}")
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
            logger.error(f"Error enhancing image: {str(e)}")
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
            logger.error(f"Error analyzing image quality: {str(e)}")
            return {"quality_score": 0, "is_suitable": False}

    def preprocess_image(self, image):
        """Apply exactly the resize and rescaling used during training."""
        try:
            if image.mode != "RGB":
                image = image.convert("RGB")

            # Disease.ipynb trains with ImageDataGenerator(rescale=1./255).
            # Contrast enhancement, sharpening, and histogram equalisation
            # were not training transformations and shift real uploads away
            # from the distribution the model learned.
            image = image.resize(self.img_size, Image.Resampling.LANCZOS)
            return np.expand_dims(np.asarray(image, dtype=np.float32) / 255.0, axis=0)

        except Exception as e:
            logger.error(f"Error preprocessing image: {str(e)}")
            return None

    def validate_target_subject(self, image):
        """Reject obvious non-plant/non-stem photos (e.g., paper/documents)."""
        try:
            if image.mode != "RGB":
                image = image.convert("RGB")

            img_array = np.array(image)
            hsv = cv2.cvtColor(img_array, cv2.COLOR_RGB2HSV)

            h = hsv[:, :, 0]
            s = hsv[:, :, 1]
            v = hsv[:, :, 2]

            # Dragon-fruit stem imagery typically has moderate/high saturation
            # with green/yellow/brown organic regions, not mostly white paper.
            green_mask = (h >= 25) & (h <= 95) & (s >= 40) & (v >= 25)
            brown_mask = (h >= 5) & (h <= 30) & (s >= 40) & (v >= 20)
            organic_mask = (s >= 40) & (v >= 20) & (v <= 245)
            paper_like_mask = (s <= 28) & (v >= 170)

            green_ratio = float(np.mean(green_mask))
            brown_ratio = float(np.mean(brown_mask))
            organic_ratio = float(np.mean(organic_mask))
            paper_like_ratio = float(np.mean(paper_like_mask))
            plant_ratio = float(np.mean(green_mask | brown_mask))
            center_y0, center_y1 = img_array.shape[0] // 6, (img_array.shape[0] * 5) // 6
            center_x0, center_x1 = img_array.shape[1] // 6, (img_array.shape[1] * 5) // 6
            central_mask = (green_mask | brown_mask)[center_y0:center_y1, center_x0:center_x1]
            central_plant_ratio = float(np.mean(central_mask))
            central_row_coverage = float(
                np.mean(np.mean(central_mask, axis=1) >= 0.10)
            )
            central_dark_ratio = float(np.mean(v[center_y0:center_y1, center_x0:center_x1] <= 100))
            # Permit a close-up of a severely damaged yellow/brown stem even
            # when it has no visible healthy-green edge. The centred, tall,
            # dark-lesion requirement keeps a person, shirt, or background
            # image from becoming a disease-model input.
            diseased_stem_candidate = (
                plant_ratio >= 0.06
                and central_plant_ratio >= 0.14
                and central_row_coverage >= 0.48
                and central_dark_ratio >= 0.012
            )
            mean_saturation = float(np.mean(s))

            gray = cv2.cvtColor(img_array, cv2.COLOR_RGB2GRAY)
            texture_score = float(cv2.Laplacian(gray, cv2.CV_64F).var())

            # Hard rejections for paper/document-like shots.
            # A close stem shot can have a large concrete/sky background that
            # is bright and neutral. Treat it as a document only when that
            # background is present *and* meaningful plant-colour tissue is
            # absent; otherwise a damaged yellow/brown stem is wrongly lost.
            document_like = (
                paper_like_ratio >= 0.72
                and organic_ratio <= 0.20
                and plant_ratio < 0.10
            ) or (
                mean_saturation < 30
                and paper_like_ratio >= 0.58
                and plant_ratio < 0.10
            )

            # Brown/yellow subjects include people, soil, wood, and fabric.
            # Since this classifier has disease classes only (no "other"
            # class), require visible cactus-green tissue before it may assign
            # a disease. A close stem image can still include its brown/yellow
            # lesion; it just must show some healthy stem context as well.
            normal_stem_candidate = (
                not document_like
                and organic_ratio >= 0.18
                # A phone camera can frame a diseased section closely, leaving
                # only a slim healthy-green edge. Require stem-colour tissue
                # in the centre, but do not reject that legitimate close-up.
                and plant_ratio >= 0.07
                and central_plant_ratio >= 0.06
                and green_ratio >= 0.01
                and paper_like_ratio <= 0.68
                and (texture_score >= 18.0 or mean_saturation >= 45.0)
            )
            is_target = (
                not document_like
                and organic_ratio >= 0.18
                and paper_like_ratio <= 0.68
                and (normal_stem_candidate or diseased_stem_candidate)
            )

            return {
                "is_target": bool(is_target),
                "green_ratio": green_ratio,
                "brown_ratio": brown_ratio,
                "plant_ratio": plant_ratio,
                "central_plant_ratio": central_plant_ratio,
                "central_row_coverage": central_row_coverage,
                "central_dark_ratio": central_dark_ratio,
                "diseased_stem_candidate": bool(diseased_stem_candidate),
                "organic_ratio": organic_ratio,
                "paper_like_ratio": paper_like_ratio,
                "mean_saturation": mean_saturation,
                "texture_score": texture_score,
                "document_like": bool(document_like),
            }
        except Exception as e:
            logger.error(f"Error validating target subject: {str(e)}")
            # Fail closed for safety: reject when subject validation breaks.
            return {"is_target": False, "reason": "validator_error"}

    def extract_stem_region(self, image):
        """Find the centered dragon-fruit stem and remove unrelated background.

        The disease model was trained on stem disease imagery and has no
        ``background`` class.  Passing an entire field photo lets foliage,
        soil, or other plants force a disease label.  A capture is therefore
        valid only when it contains one substantial green/brown organic region
        near the centre, where the guided camera/upload view asks the user to
        place the stem.  Only that padded region is sent to the model.
        """
        try:
            if image.mode != "RGB":
                image = image.convert("RGB")

            rgb = np.array(image)
            height, width = rgb.shape[:2]
            if height < 32 or width < 32:
                return None, {"is_stem": False, "reason": "image_too_small"}

            hsv = cv2.cvtColor(rgb, cv2.COLOR_RGB2HSV)
            h, s, v = hsv[:, :, 0], hsv[:, :, 1], hsv[:, :, 2]

            # Keep the saturated green/brown tissue that makes up a pitaya
            # stem.  Lesions remain included later through padding/dilation.
            green = (h >= 25) & (h <= 95) & (s >= 40) & (v >= 25)
            brown = (h >= 5) & (h <= 30) & (s >= 35) & (v >= 20)
            mask = np.where(green | brown, 255, 0).astype(np.uint8)

            kernel_size = max(5, int(round(min(width, height) * 0.025)) | 1)
            kernel = cv2.getStructuringElement(
                cv2.MORPH_ELLIPSE, (kernel_size, kernel_size)
            )
            mask = cv2.morphologyEx(mask, cv2.MORPH_CLOSE, kernel, iterations=2)
            mask = cv2.morphologyEx(mask, cv2.MORPH_OPEN, kernel, iterations=1)

            component_count, labels, stats, centroids = cv2.connectedComponentsWithStats(
                mask, connectivity=8
            )
            image_area = float(width * height)
            center_x, center_y = width / 2.0, height / 2.0
            diagonal = max(float(np.hypot(width, height)), 1.0)
            best = None

            for index in range(1, component_count):
                x, y, component_width, component_height, area = stats[index]
                area_ratio = float(area) / image_area
                # Camera captures can contain a narrow vertical/diagonal stem
                # rather than a large full-frame cactus paddle.
                if area_ratio < 0.018:
                    continue

                cx, cy = centroids[index]
                centre_distance = float(np.hypot(cx - center_x, cy - center_y)) / diagonal
                # Prefer a substantial component close to the centre.  This
                # ignores small background leaves/soil patches at the edges.
                score = area_ratio - (0.35 * centre_distance)
                if best is None or score > best[0]:
                    best = (
                        score,
                        int(index),
                        int(x),
                        int(y),
                        int(component_width),
                        int(component_height),
                        area_ratio,
                        centre_distance,
                    )

            if best is None:
                return None, {"is_stem": False, "reason": "stem_not_found"}

            (
                _,
                component_index,
                x,
                y,
                component_width,
                component_height,
                area_ratio,
                centre_distance,
            ) = best
            # A stem should be reasonably centred; otherwise this is likely a
            # background plant rather than the intended subject.
            if centre_distance > 0.42:
                return None, {
                    "is_stem": False,
                    "reason": "stem_not_centered",
                    "component_area_ratio": area_ratio,
                    "centre_distance": centre_distance,
                }

            padding = max(8, int(round(max(component_width, component_height) * 0.12)))
            left = max(0, x - padding)
            top = max(0, y - padding)
            right = min(width, x + component_width + padding)
            bottom = min(height, y + component_height + padding)

            # Reject an almost-full-frame component. It normally means a broad
            # background scene instead of a close, focused stem capture.
            roi_area_ratio = float((right - left) * (bottom - top)) / image_area
            if roi_area_ratio > 0.92 and area_ratio < 0.45:
                return None, {
                    "is_stem": False,
                    "reason": "stem_not_distinct_from_background",
                    "component_area_ratio": area_ratio,
                    "roi_area_ratio": roi_area_ratio,
                }

            # Mask out every pixel outside the chosen stem component. A plain
            # rectangle still contains soil, leaves, pots, and other objects;
            # a disease-only model can otherwise classify that background.
            component_mask = np.where(labels == component_index, 255, 0).astype(np.uint8)

            # Dark canker/rot lesions may not pass the green-or-brown colour
            # test above.  If they are enclosed by the selected stem, they
            # belong to the subject—not the background—and must reach the
            # classifier.  Flood filling from outside identifies only those
            # enclosed holes without admitting unrelated foliage or soil.
            padded_mask = cv2.copyMakeBorder(
                component_mask, 1, 1, 1, 1, cv2.BORDER_CONSTANT, value=0
            )
            exterior = padded_mask.copy()
            flood_mask = np.zeros(
                (padded_mask.shape[0] + 2, padded_mask.shape[1] + 2),
                dtype=np.uint8,
            )
            cv2.floodFill(exterior, flood_mask, (0, 0), 255)
            enclosed_lesions = cv2.bitwise_not(exterior)[1:-1, 1:-1]
            component_mask = cv2.bitwise_or(component_mask, enclosed_lesions)

            dilation_size = max(3, int(round(min(width, height) * 0.018)) | 1)
            dilation_kernel = cv2.getStructuringElement(
                cv2.MORPH_ELLIPSE, (dilation_size, dilation_size)
            )
            focus_mask = cv2.dilate(component_mask, dilation_kernel, iterations=1)
            focus_crop = focus_mask[top:bottom, left:right] > 0
            rgb_crop = rgb[top:bottom, left:right].copy()
            fill_colour = np.median(rgb[component_mask > 0], axis=0).astype(np.uint8)
            rgb_crop[~focus_crop] = fill_colour

            return Image.fromarray(rgb_crop), {
                "is_stem": True,
                "component_area_ratio": area_ratio,
                "roi_area_ratio": roi_area_ratio,
                "centre_distance": centre_distance,
                "bbox": [left, top, right, bottom],
                "background_masked": True,
                "lesion_pixels_preserved": True,
            }
        except Exception as exc:
            logger.error(f"Error extracting stem region: {str(exc)}")
            return None, {"is_stem": False, "reason": "stem_roi_error"}

    def generate_image_tiles(self, image):
        """Create overlapping tiles so separate stem regions can be analyzed independently."""
        try:
            if image.mode != "RGB":
                image = image.convert("RGB")

            width, height = image.size
            min_dimension = min(width, height)

            if min_dimension <= self.img_size[0]:
                return [(0, image)]

            tile_size = min(max(int(min_dimension * 0.55), 128), min_dimension)
            stride = max(int(tile_size * 0.4), 48)

            x_positions = list(range(0, max(width - tile_size, 0) + 1, stride))
            y_positions = list(range(0, max(height - tile_size, 0) + 1, stride))

            if not x_positions:
                x_positions = [0]
            if x_positions[-1] != width - tile_size:
                x_positions.append(max(0, width - tile_size))

            if not y_positions:
                y_positions = [0]
            if y_positions[-1] != height - tile_size:
                y_positions.append(max(0, height - tile_size))

            tiles = []
            tile_index = 0
            seen_boxes = set()

            for y in y_positions:
                for x in x_positions:
                    box = (x, y, x + tile_size, y + tile_size)
                    if box in seen_boxes:
                        continue
                    seen_boxes.add(box)
                    tiles.append((tile_index, image.crop(box)))
                    tile_index += 1

            return tiles or [(0, image)]

        except Exception as e:
            logger.error(f"Error generating image tiles: {str(e)}")
            return [(0, image)]

    def _build_prediction_summary(self, predictions):
        """Convert model output into a disease->confidence mapping."""
        return {
            self.class_names[i]: float(predictions[0][i])
            for i in range(len(self.class_names))
        }

    def _extract_candidates_from_predictions(
        self, predictions, quality_score, source_tag, minimum_confidence=None,
        max_candidates=4,
    ):
        """Turn one prediction vector into one or more disease candidates."""
        all_predictions = self._build_prediction_summary(predictions)
        sorted_predictions = sorted(
            all_predictions.items(), key=lambda x: x[1], reverse=True
        )

        candidates = []
        for disease_name, confidence in sorted_predictions[:max_candidates]:
            required_confidence = self.required_confidence(
                disease_name, quality_score
            )

            candidate_floor = (
                min(required_confidence, minimum_confidence)
                if minimum_confidence is not None
                else required_confidence
            )
            if confidence < candidate_floor:
                continue

            candidates.append(
                {
                    "disease_name": disease_name,
                    "confidence": confidence,
                    "severity": self.get_disease_severity(disease_name),
                    "source": source_tag,
                }
            )

        return sorted_predictions, candidates

    def _aggregate_tile_candidates(self, tile_candidates):
        """Combine disease evidence from the masked stem and separate tiles.

        A whole-stem result can establish a primary disease.  A secondary
        disease is accepted only when it is independently seen in at least
        two focused tiles, allowing mixed infections without treating a single
        background remnant as another disease.
        """
        grouped = {}
        for candidate in tile_candidates:
            grouped.setdefault(candidate["disease_name"], []).append(candidate)

        scored_diseases = []

        for disease_name, entries in grouped.items():
            whole_image_entries = [
                entry for entry in entries if entry["source"] == "whole_image"
            ]
            tile_entries = [
                entry for entry in entries if entry["source"] != "whole_image"
            ]

            whole_confidence = max(
                (entry["confidence"] for entry in whole_image_entries), default=None
            )
            tile_sources = {entry["source"] for entry in tile_entries}
            tile_support = len(tile_sources)
            tile_confidence = max(
                (entry["confidence"] for entry in tile_entries), default=None
            )
            tile_average = (
                sum(entry["confidence"] for entry in tile_entries) / len(tile_entries)
                if tile_entries
                else None
            )

            if whole_confidence is not None:
                scored_diseases.append(
                    {
                        "disease_name": disease_name,
                        "confidence": whole_confidence,
                        "severity": self.get_disease_severity(disease_name),
                        "tile_support": tile_support,
                        "whole_image_confidence": whole_confidence,
                        "tile_confidence": tile_confidence,
                        "evidence": "whole_stem",
                    }
                )
                continue

            # A secondary disease can be localised to a small portion of the
            # stem and therefore be weak in the full-stem prediction.  Require
            # two distinct tiles and a stronger tile score before surfacing it.
            secondary_floor = max(
                self.confidence_thresholds.get(disease_name, self.min_confidence)
                * 0.75,
                self.tile_confirmation_confidence,
            )
            if (
                tile_support >= self.tile_confirmation_count
                and tile_average is not None
                and tile_average >= secondary_floor
            ):
                scored_diseases.append(
                    {
                        "disease_name": disease_name,
                        "confidence": tile_average,
                        "severity": self.get_disease_severity(disease_name),
                        "tile_support": tile_support,
                        "whole_image_confidence": None,
                        "tile_confidence": tile_confidence,
                        "evidence": "two_tiles",
                    }
                )

        scored_diseases.sort(
            key=lambda item: (item["confidence"], item.get("tile_support", 0)),
            reverse=True,
        )

        if not scored_diseases:
            return []

        # Prefer a complete-stem diagnosis as the primary result. A disease
        # classifier cannot establish a mixed infection from low-confidence
        # tile labels alone, so return the strongest repeatable diagnosis.
        whole_stem_diseases = [
            disease for disease in scored_diseases
            if disease.get("evidence") == "whole_stem"
        ]
        primary = (
            whole_stem_diseases[0] if whole_stem_diseases else scored_diseases[0]
        )
        return [primary]

    def validate_prediction(self, predictions, quality_score):
        """Enhanced prediction validation with multi-disease support"""
        try:
            all_predictions = self._build_prediction_summary(predictions)
            # Sort predictions by confidence
            sorted_predictions = sorted(
                all_predictions.items(), key=lambda x: x[1], reverse=True
            )

            # Log all predictions for debugging
            logger.info(f"All predictions (quality_score: {quality_score:.2f}):")
            for disease_name, confidence in sorted_predictions:
                logger.info(f"  {disease_name}: {confidence:.2%}")

            # Keep only diseases that meet their confidence threshold.
            detected_diseases = []
            for disease_name, confidence in sorted_predictions:
                required_confidence = self.required_confidence(
                    disease_name, quality_score
                )

                if confidence < required_confidence:
                    continue

                detected_diseases.append(
                    {
                        "disease_name": disease_name,
                        "confidence": confidence,
                        "severity": self.get_disease_severity(disease_name),
                    }
                )
                logger.info(f"  {disease_name}: {confidence:.2%}")

                if len(detected_diseases) == 2:
                    break

            logger.info(f"Total detected diseases: {len(detected_diseases)}")

            top_confidence = sorted_predictions[0][1]
            second_confidence = sorted_predictions[1][1] if len(sorted_predictions) >= 2 else 0.0
            top_disease_name = sorted_predictions[0][0]

            # If the best class is clearly above the runner-up and meets its class
            # threshold, return it as a single detection.
            top_required_confidence = self.required_confidence(
                top_disease_name, quality_score
            )
            confidence_gap = top_confidence - second_confidence

            if (
                top_confidence >= top_required_confidence
                and confidence_gap >= self.min_confidence_gap
            ):
                detected_diseases = [
                    {
                        "disease_name": top_disease_name,
                        "confidence": top_confidence,
                        "severity": self.get_disease_severity(top_disease_name),
                    }
                ]
            else:
                detected_diseases = []

            # This is a stem-only detector.  It has no background/healthy class,
            # so every rejected prediction must be exposed as an explicit
            # no-detection result rather than a guessed "healthy leaf" label.
            if not detected_diseases:
                if len(sorted_predictions) >= 2:
                    if top_confidence < 0.75 and confidence_gap < 0.15:
                        return {
                            "success": True,
                            "disease_name": None,
                            "confidence": top_confidence,
                            "message": "No disease detection found.",
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
                    "message": "No disease detection found.",
                    "reason": "low_confidence",
                    "predicted_class": sorted_predictions[0][0],
                    "required_confidence": self.required_confidence(
                        sorted_predictions[0][0], quality_score
                    ),
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
            logger.error(f"Error validating prediction: {str(e)}")
            return {"success": False, "error": str(e)}

    def predict_disease(self, image):
        """Enhanced disease prediction with better accuracy"""
        if not self.model:
            if not self.load_model():
                return None

        try:
            subject_validation = self.validate_target_subject(image)
            if not subject_validation.get("is_target", True):
                return {
                    "success": True,
                    "disease_name": None,
                    "confidence": 0,
                    "message": "Invalid image subject. Please capture dragon fruit stem only.",
                    "reason": "invalid_subject",
                    "subject_validation": subject_validation,
                }

            stem_image, stem_validation = self.extract_stem_region(image)
            subject_validation["stem_region"] = stem_validation
            if stem_image is None:
                return {
                    "success": True,
                    "disease_name": None,
                    "confidence": 0,
                    "message": "No disease detection found.",
                    "reason": stem_validation.get("reason", "stem_not_found"),
                    "subject_validation": subject_validation,
                }

            # From this point forward the model and the tile generator receive
            # only the stem region, never the full scene/background.
            image = stem_image

            # Analyze image quality first
            quality = self.analyze_image_quality(image)

            if not quality["is_suitable"]:
                return {
                    "success": True,
                    "disease_name": None,
                    "confidence": 0,
                    "message": "No disease detection found.",
                    "reason": "low_image_quality",
                    "quality_details": quality,
                }

            # Preprocess image with enhancements
            processed_image = self.preprocess_image(image)
            if processed_image is None:
                return {"success": False, "error": "Failed to preprocess image"}

            whole_image_predictions = self.model.predict(processed_image, verbose=0)
            whole_sorted_predictions, whole_candidates = (
                self._extract_candidates_from_predictions(
                    whole_image_predictions,
                    quality["quality_score"],
                    "whole_image",
                )
            )

            tile_candidates = []
            tile_predictions = []
            for tile_index, tile in self.generate_image_tiles(image):
                tile_quality = self.analyze_image_quality(tile)
                if tile_quality.get("quality_score", 0) < 0.3:
                    continue

                tile_input = self.preprocess_image(tile)
                if tile_input is None:
                    continue

                predictions = self.model.predict(tile_input, verbose=0)
                sorted_predictions, candidates = self._extract_candidates_from_predictions(
                    predictions,
                    tile_quality["quality_score"],
                    f"tile_{tile_index}",
                    self.tile_confirmation_confidence,
                    max_candidates=1,
                )

                tile_predictions.append(sorted_predictions[:3])
                tile_candidates.extend(candidates)

            all_candidates = whole_candidates + tile_candidates
            detected_diseases = self._aggregate_tile_candidates(all_candidates)

            # A disease-only classifier always has a top label.  Keep the
            # no-detection path for uncertain images by requiring separation
            # from the runner-up as well as the class confidence floor.
            if (
                len(detected_diseases) == 1
                and detected_diseases[0].get("evidence") == "whole_stem"
                and len(whole_sorted_predictions) >= 2
            ):
                top_name, top_confidence = whole_sorted_predictions[0]
                second_confidence = whole_sorted_predictions[1][1]
                required_confidence = self.required_confidence(
                    top_name, quality["quality_score"]
                )
                if (
                    top_confidence < required_confidence
                    or top_confidence - second_confidence < self.min_confidence_gap
                ):
                    detected_diseases = []

            if not detected_diseases:
                # Preserve the uncertainty guard for healthy/unclear photos,
                # but do not turn every missing tile match into a 0% result.
                # validate_prediction checks the class floor and the gap from
                # the runner-up before returning a disease.
                result = self.validate_prediction(
                    whole_image_predictions, quality["quality_score"]
                )
            else:
                primary_disease = detected_diseases[0]
                result = {
                    "success": True,
                    "disease_name": primary_disease["disease_name"],
                    "confidence": primary_disease["confidence"],
                    "severity": primary_disease["severity"],
                    "message": (
                        f"{len(detected_diseases)} diseases detected - primary: "
                        f"{primary_disease['disease_name']}"
                    ),
                    "reason": (
                        "multiple_diseases"
                        if len(detected_diseases) > 1
                        else "disease_detected"
                    ),
                    "all_predictions": whole_sorted_predictions[:5],
                    "detected_diseases": detected_diseases,
                }

            result["quality_details"] = quality
            result["detected_diseases"] = result.get("detected_diseases", detected_diseases)
            result["subject_validation"] = subject_validation

            if result.get("detected_diseases") and len(result["detected_diseases"]) > 1:
                result["reason"] = "multiple_diseases"
                result["message"] = (
                    f"{len(result['detected_diseases'])} diseases detected - primary: "
                    f"{result['detected_diseases'][0]['disease_name']}"
                )

            return result

        except Exception as e:
            logger.error(f"Error predicting disease: {str(e)}")
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
            logger.error(f"Error in predict_image: {str(e)}")
            return {"success": False, "error": str(e), "detection": None}

    return predict_image


def test_improved_detection():
    """Test improved detection system"""
    print("🧪 Testing Improved Disease Detection")
    print("=" * 50)

    detector = ImprovedDiseaseDetection()

    # Test model loading
    if not detector.load_model():
        print("Failed to load model")
        return False

    print("Model loaded successfully")

    # Test with different image scenarios
    test_cases = [
        ("Healthy Leaf", "green", "Should detect as healthy"),
        ("Disease Symptoms", "disease", "Should detect disease"),
        ("Low Quality", "blurry", "Should reject low quality"),
    ]

    for test_name, test_type, expected in test_cases:
        print(f"\nTest: {test_name}")

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
                print("PASS: Correctly identified as healthy")
            elif test_type == "disease" and result["disease_name"]:
                print(
                    f"PASS: Detected disease - {result['disease_name']} ({result['confidence']:.1%})"
                )
            elif (
                test_type == "blurry"
                and result["disease_name"] is None
                and "quality" in result["message"].lower()
            ):
                print("PASS: Correctly rejected low quality image")
            else:
                print(f"⚠️ UNEXPECTED: {result['message']}")

            print(f"   Details: {result.get('reason', 'N/A')}")
            if result.get("quality_details"):
                print(
                    f"   Quality Score: {result['quality_details']['quality_score']:.2f}"
                )
        else:
            print(f"FAIL: {result.get('error', 'Unknown error')}")

    print("\n🎉 Improved Detection Test Complete!")
    return True


if __name__ == "__main__":
    test_improved_detection()
