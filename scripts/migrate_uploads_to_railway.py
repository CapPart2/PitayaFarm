"""Resumable transfer of local upload files to the Railway volume.

Run only after the matching server endpoints have been deployed.  The script
never stores credentials; supply the Railway site URL and admin token at run
time.  It asks the server for each file's current offset, so it can safely be
restarted after a network interruption.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import time
import uuid
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen


CHUNK_SIZE = 20 * 1024 * 1024
RETRY_COUNT = 5


class HttpResponse:
    def __init__(self, status_code, content):
        self.status_code = status_code
        self.content = content
        self.text = content.decode("utf-8", errors="replace")

    @property
    def ok(self):
        return 200 <= self.status_code < 300

    def json(self):
        return json.loads(self.text)


class MigrationSession:
    """Small standard-library HTTP client so the migrator has no extra dependency."""

    def __init__(self, admin_token):
        self.headers = {"Authorization": f"Bearer {admin_token}"}

    def post(self, url, json=None, data=None, files=None, timeout=None):
        headers = dict(self.headers)
        if json is not None:
            payload = __import__("json").dumps(json).encode("utf-8")
            headers["Content-Type"] = "application/json"
        elif files:
            boundary = f"----pitaya-{uuid.uuid4().hex}"
            headers["Content-Type"] = f"multipart/form-data; boundary={boundary}"
            sections = []
            for name, value in (data or {}).items():
                sections.extend(
                    [
                        f"--{boundary}\r\n".encode(),
                        f'Content-Disposition: form-data; name="{name}"\r\n\r\n'.encode(),
                        str(value).encode(),
                        b"\r\n",
                    ]
                )
            for name, (filename, chunk, content_type) in files.items():
                sections.extend(
                    [
                        f"--{boundary}\r\n".encode(),
                        f'Content-Disposition: form-data; name="{name}"; filename="{filename}"\r\n'.encode(),
                        f"Content-Type: {content_type}\r\n\r\n".encode(),
                        chunk,
                        b"\r\n",
                    ]
                )
            sections.append(f"--{boundary}--\r\n".encode())
            payload = b"".join(sections)
        else:
            payload = b""

        request = Request(url, data=payload, headers=headers, method="POST")
        try:
            with urlopen(request, timeout=300) as response:
                return HttpResponse(response.status, response.read())
        except HTTPError as error:
            return HttpResponse(error.code, error.read())


def request_with_retry(method, url, **kwargs):
    last_error = None
    for attempt in range(RETRY_COUNT):
        try:
            response = method(url, timeout=(20, 300), **kwargs)
            if response.status_code < 500:
                return response
            last_error = RuntimeError(f"Server returned {response.status_code}: {response.text[:300]}")
        except (OSError, URLError) as error:
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
    parser.add_argument(
        "--admin-token",
        default=os.environ.get("PITAYA_MIGRATION_ADMIN_TOKEN"),
        help="Railway ADMIN_TOKEN (or set PITAYA_MIGRATION_ADMIN_TOKEN)",
    )
    parser.add_argument("--uploads", default="uploads", help="Local uploads folder")
    args = parser.parse_args()
    if not args.admin_token:
        parser.error("--admin-token or PITAYA_MIGRATION_ADMIN_TOKEN is required")

    root = Path(args.uploads).resolve()
    if not root.is_dir():
        raise SystemExit(f"Uploads folder does not exist: {root}")

    files = sorted(path for path in root.rglob("*") if path.is_file())
    total_bytes = sum(path.stat().st_size for path in files)
    print(f"Migrating {len(files):,} files ({total_bytes / 1024**3:.2f} GB). Restarting this command is safe.")

    session = MigrationSession(args.admin_token)
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
