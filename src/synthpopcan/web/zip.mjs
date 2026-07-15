export const DEFAULT_ZIP_LIMITS = Object.freeze({
  maxArchiveBytes: 64 * 1024 * 1024,
  maxEntries: 32,
  maxEntryBytes: 64 * 1024 * 1024,
  maxTotalUncompressedBytes: 128 * 1024 * 1024,
});

export function readZipDirectory(arrayBuffer, limits = {}) {
  const appliedLimits = { ...DEFAULT_ZIP_LIMITS, ...limits };
  const bytes = asBytes(arrayBuffer);
  if (bytes.byteLength > appliedLimits.maxArchiveBytes) {
    throw new Error("ZIP exceeds the browser compressed-size limit.");
  }
  const view = new DataView(bytes.buffer, bytes.byteOffset, bytes.byteLength);
  const endOffset = findEndOfCentralDirectory(view);
  const centralDirectorySize = view.getUint32(endOffset + 12, true);
  const centralDirectoryOffset = view.getUint32(endOffset + 16, true);
  const end = centralDirectoryOffset + centralDirectorySize;
  if (end > view.byteLength) {
    throw new Error("ZIP central directory exceeds the archive bounds.");
  }

  const entries = [];
  let totalUncompressedBytes = 0;
  let offset = centralDirectoryOffset;
  while (offset < end) {
    if (offset + 46 > end || view.getUint32(offset, true) !== 0x02014b50) {
      throw new Error("ZIP central directory is not readable.");
    }
    const flags = view.getUint16(offset + 8, true);
    const compressionMethod = view.getUint16(offset + 10, true);
    const compressedSize = view.getUint32(offset + 20, true);
    const uncompressedSize = view.getUint32(offset + 24, true);
    const nameLength = view.getUint16(offset + 28, true);
    const extraLength = view.getUint16(offset + 30, true);
    const commentLength = view.getUint16(offset + 32, true);
    const localHeaderOffset = view.getUint32(offset + 42, true);
    const nextOffset = offset + 46 + nameLength + extraLength + commentLength;
    if (nextOffset > end) {
      throw new Error("ZIP central directory entry exceeds the archive bounds.");
    }
    if (flags & 0x1) {
      throw new Error("Encrypted ZIP entries are not supported.");
    }
    if (uncompressedSize > appliedLimits.maxEntryBytes) {
      throw new Error("ZIP entry exceeds the browser uncompressed-size limit.");
    }
    const name = decodeText(bytes.slice(offset + 46, offset + 46 + nameLength));
    if (!name.endsWith("/")) {
      entries.push({
        name,
        compressionMethod,
        compressedSize,
        uncompressedSize,
        localHeaderOffset,
      });
      if (entries.length > appliedLimits.maxEntries) {
        throw new Error("ZIP contains too many files for browser processing.");
      }
      totalUncompressedBytes += uncompressedSize;
      if (totalUncompressedBytes > appliedLimits.maxTotalUncompressedBytes) {
        throw new Error("ZIP exceeds the browser aggregate uncompressed-size limit.");
      }
    }
    offset = nextOffset;
  }
  if (offset !== end) {
    throw new Error("ZIP central directory size is inconsistent.");
  }
  return entries;
}

export async function readZipEntry(arrayBuffer, entry, limits = {}) {
  const appliedLimits = { ...DEFAULT_ZIP_LIMITS, ...limits };
  if (entry.uncompressedSize > appliedLimits.maxEntryBytes) {
    throw new Error("ZIP entry exceeds the browser uncompressed-size limit.");
  }
  const bytes = asBytes(arrayBuffer);
  const view = new DataView(bytes.buffer, bytes.byteOffset, bytes.byteLength);
  return decodeText(
    await readLocalFile(
      bytes,
      view,
      entry.localHeaderOffset,
      entry.compressionMethod,
      entry.compressedSize,
      entry.uncompressedSize,
    ),
  );
}

export async function readZipEntries(arrayBuffer, limits = {}) {
  const entries = readZipDirectory(arrayBuffer, limits);
  const output = [];
  for (const entry of entries) {
    output.push({
      name: entry.name,
      text: await readZipEntry(arrayBuffer, entry, limits),
    });
  }
  return output;
}

export function csvEntries(entries) {
  return entries.filter((entry) => entry.name.toLowerCase().endsWith(".csv"));
}

async function readLocalFile(
  bytes,
  view,
  offset,
  compressionMethod,
  compressedSize,
  uncompressedSize,
) {
  if (offset + 30 > view.byteLength || view.getUint32(offset, true) !== 0x04034b50) {
    throw new Error("ZIP local file header is not readable.");
  }
  const nameLength = view.getUint16(offset + 26, true);
  const extraLength = view.getUint16(offset + 28, true);
  const dataOffset = offset + 30 + nameLength + extraLength;
  if (dataOffset + compressedSize > bytes.byteLength) {
    throw new Error("ZIP entry data exceeds the archive bounds.");
  }
  const compressed = bytes.slice(dataOffset, dataOffset + compressedSize);
  if (compressionMethod === 0) {
    if (compressed.byteLength !== uncompressedSize) {
      throw new Error("ZIP entry has an inconsistent stored size.");
    }
    return compressed;
  }
  if (compressionMethod === 8) {
    return inflateRaw(compressed, uncompressedSize);
  }
  throw new Error(`Unsupported ZIP compression method ${compressionMethod}.`);
}

async function inflateRaw(bytes, expectedSize) {
  if (typeof DecompressionStream === "undefined") {
    throw new Error(
      "This browser cannot decompress ZIP entries. Upload an uncompressed CSV or use the CLI.",
    );
  }
  const stream = new Blob([bytes])
    .stream()
    .pipeThrough(new DecompressionStream("deflate-raw"));
  const output = new Uint8Array(await new Response(stream).arrayBuffer());
  if (expectedSize && output.length !== expectedSize) {
    throw new Error("ZIP entry decompressed to an unexpected size.");
  }
  return output;
}

function findEndOfCentralDirectory(view) {
  if (view.byteLength < 22) {
    throw new Error("ZIP end-of-central-directory record was not found.");
  }
  const minimumOffset = Math.max(0, view.byteLength - 65557);
  for (let offset = view.byteLength - 22; offset >= minimumOffset; offset -= 1) {
    if (view.getUint32(offset, true) === 0x06054b50) {
      return offset;
    }
  }
  throw new Error("ZIP end-of-central-directory record was not found.");
}

function asBytes(value) {
  if (value instanceof Uint8Array) return value;
  return new Uint8Array(value);
}

function decodeText(bytes) {
  return new TextDecoder("utf-8").decode(bytes).replace(/^\uFEFF/, "");
}
