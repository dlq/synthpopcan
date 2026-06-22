export async function readZipEntries(arrayBuffer) {
  const bytes = new Uint8Array(arrayBuffer);
  const view = new DataView(bytes.buffer, bytes.byteOffset, bytes.byteLength);
  const endOffset = findEndOfCentralDirectory(view);
  const centralDirectorySize = view.getUint32(endOffset + 12, true);
  const centralDirectoryOffset = view.getUint32(endOffset + 16, true);
  const entries = [];
  let offset = centralDirectoryOffset;
  const end = centralDirectoryOffset + centralDirectorySize;

  while (offset < end) {
    if (view.getUint32(offset, true) !== 0x02014b50) {
      throw new Error("ZIP central directory is not readable.");
    }
    const compressionMethod = view.getUint16(offset + 10, true);
    const compressedSize = view.getUint32(offset + 20, true);
    const uncompressedSize = view.getUint32(offset + 24, true);
    const nameLength = view.getUint16(offset + 28, true);
    const extraLength = view.getUint16(offset + 30, true);
    const commentLength = view.getUint16(offset + 32, true);
    const localHeaderOffset = view.getUint32(offset + 42, true);
    const name = decodeText(bytes.slice(offset + 46, offset + 46 + nameLength));
    if (!name.endsWith("/")) {
      entries.push({
        name,
        text: decodeText(
          await readLocalFile(
            bytes,
            view,
            localHeaderOffset,
            compressionMethod,
            compressedSize,
            uncompressedSize,
          ),
        ),
      });
    }
    offset += 46 + nameLength + extraLength + commentLength;
  }
  return entries;
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
  if (view.getUint32(offset, true) !== 0x04034b50) {
    throw new Error("ZIP local file header is not readable.");
  }
  const nameLength = view.getUint16(offset + 26, true);
  const extraLength = view.getUint16(offset + 28, true);
  const dataOffset = offset + 30 + nameLength + extraLength;
  const compressed = bytes.slice(dataOffset, dataOffset + compressedSize);
  if (compressionMethod === 0) {
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
  const minimumOffset = Math.max(0, view.byteLength - 65557);
  for (let offset = view.byteLength - 22; offset >= minimumOffset; offset -= 1) {
    if (view.getUint32(offset, true) === 0x06054b50) {
      return offset;
    }
  }
  throw new Error("ZIP end-of-central-directory record was not found.");
}

function decodeText(bytes) {
  return new TextDecoder("utf-8").decode(bytes).replace(/^\uFEFF/, "");
}
