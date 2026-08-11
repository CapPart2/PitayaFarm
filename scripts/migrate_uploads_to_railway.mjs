/**
 * Dependency-free, resumable upload migration for the Railway volume.
 * Requires PITAYA_MIGRATION_ADMIN_TOKEN at runtime; the token is never saved.
 */

import { readdir, open, stat } from 'node:fs/promises';
import { join, relative, resolve, sep } from 'node:path';

const CHUNK_SIZE = 20 * 1024 * 1024;
const RETRY_COUNT = 5;
const baseUrl = (process.env.PITAYA_MIGRATION_URL || 'https://pitayafarm-production.up.railway.app').replace(/\/$/, '');
const adminToken = process.env.PITAYA_MIGRATION_ADMIN_TOKEN;
const uploadsRoot = resolve(process.env.PITAYA_UPLOADS_DIR || 'uploads');

if (!adminToken) throw new Error('PITAYA_MIGRATION_ADMIN_TOKEN is required.');

async function filesIn(directory) {
  const entries = await readdir(directory, { withFileTypes: true });
  const nested = await Promise.all(entries.map(async entry => {
    const path = join(directory, entry.name);
    return entry.isDirectory() ? filesIn(path) : entry.isFile() ? [path] : [];
  }));
  return nested.flat();
}

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
    await new Promise(resolveWait => setTimeout(resolveWait, Math.min(30000, 2 ** attempt * 1000)));
  }
  throw lastError;
}

async function migrationStatus(path, size) {
  const response = await request('/api/admin/uploads/migration-status', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ path, size }),
  });
  const payload = await response.json();
  if (!response.ok || !payload.success) throw new Error(`Status failed for ${path}: ${payload.error || response.status}`);
  return payload;
}

async function migrateFile(path) {
  const relativePath = relative(uploadsRoot, path).split(sep).join('/');
  const { size } = await stat(path);
  let remote = await migrationStatus(relativePath, size);
  if (remote.complete) return { size, skipped: true };
  let offset = Number(remote.offset || 0);
  if (offset < 0 || offset > size) throw new Error(`Invalid resume offset for ${relativePath}: ${offset}`);

  const source = await open(path, 'r');
  try {
    while (offset < size) {
      const bytes = Math.min(CHUNK_SIZE, size - offset);
      const buffer = Buffer.allocUnsafe(bytes);
      const { bytesRead } = await source.read(buffer, 0, bytes, offset);
      if (!bytesRead) throw new Error(`Unable to read ${relativePath} at ${offset}`);

      const form = new FormData();
      form.append('path', relativePath);
      form.append('offset', String(offset));
      form.append('total_size', String(size));
      form.append('chunk', new Blob([buffer.subarray(0, bytesRead)], { type: 'application/octet-stream' }), 'chunk.bin');
      const response = await request('/api/admin/uploads/migrate-chunk', { method: 'POST', body: form });
      const payload = await response.json();
      if (response.status === 409) {
        offset = Number(payload.offset);
        continue;
      }
      if (!response.ok || !payload.success) throw new Error(`Upload failed for ${relativePath}: ${payload.error || response.status}`);
      const nextOffset = Number(payload.offset);
      if (nextOffset <= offset || nextOffset > size) throw new Error(`Invalid remote offset for ${relativePath}: ${nextOffset}`);
      offset = nextOffset;
    }
  } finally {
    await source.close();
  }

  remote = await migrationStatus(relativePath, size);
  if (!remote.complete || Number(remote.offset) !== size) throw new Error(`Incomplete migration for ${relativePath}`);
  return { size, skipped: false };
}

const imageExtensions = new Set(['.jpg', '.jpeg', '.png', '.webp', '.gif']);
const isImage = path => imageExtensions.has(path.slice(path.lastIndexOf('.')).toLowerCase());
const files = (await filesIn(uploadsRoot)).sort((left, right) => {
  const priorityDifference = Number(!isImage(left)) - Number(!isImage(right));
  return priorityDifference || left.localeCompare(right);
});
const totalBytes = (await Promise.all(files.map(file => stat(file)))).reduce((sum, item) => sum + item.size, 0);
console.log(`Migrating ${files.length.toLocaleString()} files (${(totalBytes / 1024 ** 3).toFixed(2)} GB). Restarting is safe.`);

let migratedBytes = 0;
let skippedFiles = 0;
for (let index = 0; index < files.length; index += 1) {
  const result = await migrateFile(files[index]);
  migratedBytes += result.size;
  skippedFiles += Number(result.skipped);
  console.log(`[${index + 1}/${files.length}] ${relative(uploadsRoot, files[index])} (${(migratedBytes / 1024 ** 3).toFixed(2)}/${(totalBytes / 1024 ** 3).toFixed(2)} GB)`);
}
console.log(`Complete. ${files.length.toLocaleString()} files verified; ${skippedFiles.toLocaleString()} already existed on Railway.`);
