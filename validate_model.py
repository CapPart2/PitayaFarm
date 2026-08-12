"""Evaluate the deployed disease model on a leakage-free test split.

First create the split with ``scripts/rebuild_clean_disease_splits.py``.  This
script deliberately has no Django or database dependency, so its accuracy is
the model result rather than an application-side report.
"""

import os

import keras
import numpy as np
from tensorflow.keras.preprocessing.image import ImageDataGenerator


MODEL_PATH = "leaf_disease_model.keras"
TEST_DATA_DIR = os.environ.get(
    "PITAYA_TEST_DATA_DIR", os.path.join("oversample", "Leaf_clean", "test")
)
CLASS_NAMES = [
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


def main():
    if not os.path.exists(MODEL_PATH):
        raise SystemExit(f"Model file not found: {MODEL_PATH}")
    if not os.path.isdir(TEST_DATA_DIR):
        raise SystemExit(
            f"Clean test directory not found: {TEST_DATA_DIR}\n"
            "Run: python scripts/rebuild_clean_disease_splits.py"
        )

    model = keras.models.load_model(MODEL_PATH, compile=False)
    test_data = ImageDataGenerator(rescale=1.0 / 255).flow_from_directory(
        TEST_DATA_DIR,
        target_size=(224, 224),
        batch_size=32,
        class_mode="categorical",
        color_mode="rgb",
        shuffle=False,
        classes=CLASS_NAMES,
    )
    if test_data.samples == 0:
        raise SystemExit("The clean test directory contains no images.")

    probabilities = model.predict(test_data, verbose=1)
    predicted = np.argmax(probabilities, axis=1)
    actual = test_data.classes

    accuracy = float(np.mean(predicted == actual))
    print(f"\nClean test accuracy: {accuracy:.2%} ({len(actual)} images)")
    print("\nPer-class recall:")
    for index, class_name in enumerate(CLASS_NAMES):
        class_mask = actual == index
        support = int(np.sum(class_mask))
        recall = float(np.mean(predicted[class_mask] == index)) if support else 0.0
        print(f"  {class_name}: {recall:.2%} ({support} images)")

    print("\nPredicted class distribution:")
    for index, class_name in enumerate(CLASS_NAMES):
        print(f"  {class_name}: {int(np.sum(predicted == index))}")


if __name__ == "__main__":
    main()
