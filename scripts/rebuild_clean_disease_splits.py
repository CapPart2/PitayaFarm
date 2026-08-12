#!/usr/bin/env python3
"""Build leakage-free train, validation, and test splits for disease training.

The source directory must contain one folder per disease class, plus the old
``train``, ``validation``, and ``test`` folders.  Source image hashes are
grouped before splitting, so exact duplicate images cannot appear in more than
one split.  The existing splits are never modified.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import random
import shutil
from collections import defaultdict
from pathlib import Path


SPLIT_NAMES = ("train", "validation", "test")
IMAGE_EXTENSIONS = {".jpg", ".jpeg", ".png"}


def image_hash(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as image_file:
        for chunk in iter(lambda: image_file.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def split_counts(total: int) -> tuple[int, int, int]:
    """Return a 70/20/10 split while retaining every unique image."""
    train_count = int(total * 0.70)
    validation_count = int(total * 0.20)
    test_count = total - train_count - validation_count
    return train_count, validation_count, test_count


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--source",
        type=Path,
        default=Path("oversample/Leaf"),
        help="Root containing the original per-class folders.",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=Path("oversample/Leaf_clean"),
        help="New output root. It must not already exist.",
    )
    parser.add_argument("--seed", type=int, default=702)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    source = args.source.resolve()
    output = args.output.resolve()

    if not source.is_dir():
        raise SystemExit(f"Source directory does not exist: {source}")
    if output.exists():
        raise SystemExit(
            f"Output already exists: {output}\n"
            "Choose a new --output path; existing data is intentionally not overwritten."
        )

    class_directories = sorted(
        directory
        for directory in source.iterdir()
        if directory.is_dir() and directory.name not in SPLIT_NAMES
    )
    if not class_directories:
        raise SystemExit("No disease class directories found.")

    randomizer = random.Random(args.seed)
    manifest: dict[str, object] = {
        "seed": args.seed,
        "source": str(source),
        "classes": {},
        "cross_class_duplicates": [],
    }
    assigned_hashes: dict[str, str] = {}

    for class_directory in class_directories:
        grouped_images: defaultdict[str, list[Path]] = defaultdict(list)
        for path in sorted(class_directory.rglob("*")):
            if path.is_file() and path.suffix.lower() in IMAGE_EXTENSIONS:
                grouped_images[image_hash(path)].append(path)

        unique_images: list[tuple[str, Path]] = []
        for digest, paths in grouped_images.items():
            existing_class = assigned_hashes.get(digest)
            if existing_class and existing_class != class_directory.name:
                manifest["cross_class_duplicates"].append(
                    {
                        "hash": digest,
                        "classes": [existing_class, class_directory.name],
                        "files": [str(path) for path in paths],
                    }
                )
                continue
            assigned_hashes[digest] = class_directory.name
            unique_images.append((digest, paths[0]))

        randomizer.shuffle(unique_images)
        train_count, validation_count, _ = split_counts(len(unique_images))
        split_images = {
            "train": unique_images[:train_count],
            "validation": unique_images[train_count : train_count + validation_count],
            "test": unique_images[train_count + validation_count :],
        }

        class_manifest = {
            "source_files": sum(len(paths) for paths in grouped_images.values()),
            "unique_images": len(unique_images),
            "duplicates_removed": sum(len(paths) - 1 for paths in grouped_images.values()),
            "splits": {},
        }
        for split_name, images in split_images.items():
            destination = output / split_name / class_directory.name
            destination.mkdir(parents=True, exist_ok=True)
            for digest, source_path in images:
                destination_path = destination / f"{digest}{source_path.suffix.lower()}"
                shutil.copy2(source_path, destination_path)
            class_manifest["splits"][split_name] = len(images)

        manifest["classes"][class_directory.name] = class_manifest
        print(
            f"{class_directory.name}: "
            f"train={len(split_images['train'])}, "
            f"validation={len(split_images['validation'])}, "
            f"test={len(split_images['test'])}"
        )

    manifest_path = output / "split_manifest.json"
    manifest_path.write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    print(f"Created clean splits in: {output}")
    print(f"Manifest: {manifest_path}")


if __name__ == "__main__":
    main()
