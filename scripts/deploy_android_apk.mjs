/**
 * Upload the real Android Studio APK to the persistent Railway volume.
 *
 * Required environment variables:
 *   PITAYA_MIGRATION_ADMIN_TOKEN  Railway ADMIN_TOKEN
 * Optional environment variables:
 *   PITAYA_MIGRATION_URL          Deployed PITAYA URL
 *   PITAYA_ANDROID_APK            Local APK path
 */

import { open, stat } from 'node:fs/promises';
import { resolve } from 'node:path';

const CHUNK_SIZE = 20 * 1024 * 1024;
const RETRY_COUNT = 5;
const baseUrl = (process.env.PITAYA_MIGRATION_URL || 'https://pitayafarm-production.up.railway.app').replace(/\/$/, '');
const adminToken = process.env.PITAYA_MIGRATION_ADMIN_TOKEN;
const apkPath = resolve(process.env.PITAYA_ANDROID_APK || 'frontend/android/app/build/outputs/apk/debug/app-debug.apk');
const remotePath = 'downloads/app-debug.apk';

if (!adminToken) throw new Error('PITAYA_MIGRATION_ADMIN_TOKEN is required.');

async function request(path, options = {}) {
  let lastError;
  for (let attempt = 0; attempt < RETRY_COUNT; attempt += 1) {
    try {
      const controller = new AbortController();
      const timer = setTimeout(() => controller.abort(), 300000);
      const response = await fetch(`${baseUrl}${path}`, {
        ...options,
        headers: { Authorization: `Bearer ${adminToken}`, ...(options.headers || {}) },
        signal: controller.signal,
      });
      clearTimeout(timer);
      if (response.status < 500) return response;
      lastError = new Error(`Server returned ${response.status}: ${(await response.text()).slice(0, 300)}`);
    } catch (error) {
      lastError = error;
    }
    await new Promise(wait => setTimeout(wait, Math.min(30000, 2 ** attempt * 1000)));
  }
  throw lastError;
}

async function status(size) {
  const response = await request('/api/admin/uploads/migration-status', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ path: remotePath, size }),
  });
  const payload = await response.json();
  if (!response.ok || !payload.success) throw new Error(payload.error || `Status failed (${response.status})`);
  return payload;
}

const { size } = await stat(apkPath);
let remote = await status(size);
if (remote.complete) {
  console.log('The deployed APK already matches this Android Studio build.');
  process.exit(0);
}

let offset = Number(remote.offset || 0);
if (offset < 0 || offset > size) throw new Error(`Invalid resume offset: ${offset}`);
console.log(`Uploading ${(size / 1024 ** 3).toFixed(2)} GB APK to ${baseUrl}. Restarting this command is safe.`);

const source = await open(apkPath, 'r');
try {
  while (offset < size) {
    const bytes = Math.min(CHUNK_SIZE, size - offset);
    const buffer = Buffer.allocUnsafe(bytes);
    const { bytesRead } = await source.read(buffer, 0, bytes, offset);
    if (!bytesRead) throw new Error(`Unable to read the APK at byte ${offset}`);

    const form = new FormData();
    form.append('path', remotePath);
    form.append('offset', String(offset));
    form.append('total_size', String(size));
    form.append('chunk', new Blob([buffer.subarray(0, bytesRead)], { type: 'application/vnd.android.package-archive' }), 'app-debug.apk');
    const response = await request('/api/admin/uploads/migrate-chunk', { method: 'POST', body: form });
    const payload = await response.json();
    if (response.status === 409) {
      offset = Number(payload.offset);
      continue;
    }
    if (!response.ok || !payload.success) throw new Error(payload.error || `Upload failed (${response.status})`);
    const nextOffset = Number(payload.offset);
    if (nextOffset <= offset || nextOffset > size) throw new Error(`Invalid server offset: ${nextOffset}`);
    offset = nextOffset;
    console.log(`${((offset / size) * 100).toFixed(1)}% uploaded`);
  }
} finally {
  await source.close();
}

remote = await status(size);
if (!remote.complete || Number(remote.offset) !== size) throw new Error('The deployed APK upload did not complete.');
console.log(`Complete: ${baseUrl}/downloads/app-debug.apk`);
