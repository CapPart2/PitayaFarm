"""Resumable transfer of local upload files to the Railway volume.

Run only after the matching server endpoints have been deployed.  The script
never stores credentials; supply the Railway site URL and admin token at run
time.  It asks the server for each file's current offset, so it can safely be
restarted after a network interruption.
"""

from __future__ import annotations

import argparse
import sys
import time
from pathlib import Path

import requests


CHUNK_SIZE = 20 * 1024 * 1024
RETRY_COUNT = 5


def request_with_retry(method, url, **kwargs):
    last_error = None
    for attempt in range(RETRY_COUNT):
        try:
            response = method(url, timeout=(20, 300), **kwargs)
            if response.status_code < 500:
                return response
            last_error = RuntimeError(f"Server returned {response.status_code}: {response.text[:300]}")
        except requests.RequestException as error:
            last_error = error
        time.sleep(min(30, 2**attempt))
    raise RuntimeError(f"Request failed after {RETRY_COUNT} attempts: {last_error}")


def status(session, base_url, relative_path, size):
    response = request_with_retry(
        session.post,
        f"{base_url}/api/admin/uploads/migration-status",
        json={"path": relative_path, "size": size},
    )
    if not response.ok:
        raise RuntimeError(f"Status failed for {relative_path}: {response.status_code} {response.text}")
    payload = response.json()
    if not payload.get("success"):
        raise RuntimeError(f"Status failed for {relative_path}: {payload.get('error', 'unknown error')}")
    return bool(payload.get("complete")), int(payload.get("offset", 0))


def migrate_file(session, base_url, root, path):
    relative_path = path.relative_to(root).as_posix()
    total_size = path.stat().st_size
    complete, offset = status(session, base_url, relative_path, total_size)
    if complete:
        return total_size, True
    if offset < 0 or offset > total_size:
        raise RuntimeError(f"Invalid resume offset for {relative_path}: {offset}")

    with path.open("rb") as source:
        source.seek(offset)
        while offset < total_size:
            chunk = source.read(min(CHUNK_SIZE, total_size - offset))
            response = request_with_retry(
                session.post,
                f"{base_url}/api/admin/uploads/migrate-chunk",
                data={"path": relative_path, "offset": str(offset), "total_size": str(total_size)},
                files={"chunk": ("chunk.bin", chunk, "application/octet-stream")},
            )
            if response.status_code == 409:
                remote_offset = int(response.json().get("offset", -1))
                if remote_offset < 0 or remote_offset > total_size:
                    raise RuntimeError(f"Invalid conflict offset for {relative_path}: {response.text}")
                offset = remote_offset
                source.seek(offset)
                continue
            if not response.ok:
                raise RuntimeError(f"Upload failed for {relative_path}: {response.status_code} {response.text}")

            payload = response.json()
            if not payload.get("success"):
                raise RuntimeError(f"Upload failed for {relative_path}: {payload.get('error', 'unknown error')}")
            remote_offset = int(payload.get("offset", -1))
            if remote_offset <= offset or remote_offset > total_size:
                raise RuntimeError(f"Invalid upload offset for {relative_path}: {remote_offset}")
            offset = remote_offset
            source.seek(offset)

    complete, final_offset = status(session, base_url, relative_path, total_size)
    if not complete or final_offset != total_size:
        raise RuntimeError(f"Incomplete migration for {relative_path}")
    return total_size, False


def main():
    parser = argparse.ArgumentParser(description="Resumably migrate PITAYA uploads to Railway.")
    parser.add_argument("--url", required=True, help="Railway public app URL")
    parser.add_argument("--admin-token", required=True, help="Railway ADMIN_TOKEN")
    parser.add_argument("--uploads", default="uploads", help="Local uploads folder")
    args = parser.parse_args()

    root = Path(args.uploads).resolve()
    if not root.is_dir():
        raise SystemExit(f"Uploads folder does not exist: {root}")

    files = sorted(path for path in root.rglob("*") if path.is_file())
    total_bytes = sum(path.stat().st_size for path in files)
    print(f"Migrating {len(files):,} files ({total_bytes / 1024**3:.2f} GB). Restarting this command is safe.")

    session = requests.Session()
    session.headers.update({"Authorization": f"Bearer {args.admin_token}"})
    base_url = args.url.rstrip("/")
    migrated_bytes = 0
    skipped_files = 0
    for index, path in enumerate(files, start=1):
        size, skipped = migrate_file(session, base_url, root, path)
        migrated_bytes += size
        skipped_files += int(skipped)
        print(f"[{index}/{len(files)}] {path.relative_to(root)} ({migrated_bytes / 1024**3:.2f}/{total_bytes / 1024**3:.2f} GB)")

    print(f"Complete. {len(files):,} files verified; {skipped_files:,} already existed on Railway.")


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\nPaused safely. Re-run the same command to resume.", file=sys.stderr)
        raise SystemExit(130)
