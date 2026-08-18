#!/usr/bin/env python3
"""
Create test split for maturity dataset without retraining the model.
This script reorganizes the existing validation set into validation + test splits.
"""

import os
import shutil
import random
from pathlib import Path

# Configuration
DATASET_PATH = r"E:\Final for Capstone\Activity-AppDev\Mature Dragon Fruit"
TRAIN_IMAGES = os.path.join(DATASET_PATH, "train", "images")
VAL_IMAGES = os.path.join(DATASET_PATH, "val", "images")
TEST_IMAGES = os.path.join(DATASET_PATH, "test", "images")

# Split ratios (from existing val set)
VAL_RATIO = 0.7  # 70% of val becomes validation
TEST_RATIO = 0.3  # 30% of val becomes test


def create_test_split():
    """Create test split from existing validation images."""

    print("=== Creating Test Split for Maturity Dataset ===")
    print(f"Dataset path: {DATASET_PATH}")

    # Create test directory
    os.makedirs(TEST_IMAGES, exist_ok=True)

    # Get all validation images
    val_image_files = [
        f
        for f in os.listdir(VAL_IMAGES)
        if f.lower().endswith((".jpg", ".jpeg", ".png"))
    ]

    print(f"\nCurrent validation images: {len(val_image_files)}")

    # Shuffle for random split
    random.seed(42)  # For reproducibility
    random.shuffle(val_image_files)

    # Calculate split
    split_index = int(len(val_image_files) * VAL_RATIO)
    val_keep = val_image_files[:split_index]
    test_move = val_image_files[split_index:]

    print(f"Validation images (keeping): {len(val_keep)}")
    print(f"Test images (moving): {len(test_move)}")

    # Move images to test folder
    moved_count = 0
    for image_file in test_move:
        src = os.path.join(VAL_IMAGES, image_file)
        dst = os.path.join(TEST_IMAGES, image_file)

        try:
            shutil.move(src, dst)
            moved_count += 1
        except Exception as e:
            print(f"Error moving {image_file}: {e}")

    print(f"\nSuccessfully moved {moved_count} images to test split")

    # Verify final counts
    final_val = len(
        [
            f
            for f in os.listdir(VAL_IMAGES)
            if f.lower().endswith((".jpg", ".jpeg", ".png"))
        ]
    )
    final_test = len(
        [
            f
            for f in os.listdir(TEST_IMAGES)
            if f.lower().endswith((".jpg", ".jpeg", ".png"))
        ]
    )
    final_train = len(
        [
            f
            for f in os.listdir(TRAIN_IMAGES)
            if f.lower().endswith((".jpg", ".jpeg", ".png"))
        ]
    )

    print("\n=== Final Dataset Structure ===")
    print(f"Train: {final_train} images")
    print(f"Validation: {final_val} images")
    print(f"Test: {final_test} images")
    print(f"Total: {final_train + final_val + final_test} images")

    # Update YOLO config file
    update_yolo_config()

    print("\nTest split created successfully!")
    print("Note: Model retraining is NOT required for this organizational change.")


def update_yolo_config():
    """Update dragonfruit.yaml to include test split."""
    config_path = (
        r"E:\Final for Capstone\Activity-AppDev\Yield_detection\dragonfruit.yaml"
    )

    config_text = """path: "Mature Dragon Fruit"

train: train/images
val: val/images
test: test/images

names:
  0: fully_red_dragon_fruit"""

    try:
        with open(config_path, "w", encoding="utf-8") as f:
            f.write(config_text)
        print(f"\nUpdated YOLO config: {config_path}")
    except Exception as e:
        print(f"Warning: Could not update YOLO config: {e}")


if __name__ == "__main__":
    create_test_split()
