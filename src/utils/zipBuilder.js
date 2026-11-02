// Pure JavaScript in-browser / client-side ZIP generator (Store mode, no dependencies)

function createCrcTable() {
  const table = new Uint32Array(256);
  for (let i = 0; i < 256; i++) {
    let c = i;
    for (let k = 0; k < 8; k++) {
      c = (c & 1) ? (0xedb88320 ^ (c >>> 1)) : (c >>> 1);
    }
    table[i] = c >>> 0;
  }
  return table;
}

const crcTable = createCrcTable();

function crc32(buf) {
  let crc = 0xffffffff;
  for (let i = 0; i < buf.length; i++) {
    crc = (crc >>> 8) ^ crcTable[(crc ^ buf[i]) & 0xff];
  }
  return (crc ^ 0xffffffff) >>> 0;
}

/**
 * Builds a standard valid PKZIP binary Uint8Array from a list of files.
 * @param {Array<{name: string, content: string}>} files
 * @returns {Uint8Array}
 */
export function buildZipBinary(files) {
  const encoder = new TextEncoder();
  const fileEntries = [];
  let totalLength = 0;

  const preparedFiles = files.map(f => {
    // Normalize path separators to forward slash
    const cleanName = f.name.replace(/\\/g, '/');
    const nameBytes = encoder.encode(cleanName);
    const dataBytes = encoder.encode(f.content || '');
    const crc = crc32(dataBytes);
    const size = dataBytes.length;
    return { nameBytes, dataBytes, crc, size };
  });

  // Calculate total size needed
  let offset = 0;
  preparedFiles.forEach(f => {
    f.offset = offset;
    offset += 30 + f.nameBytes.length + f.size;
  });

  const centralDirStart = offset;
  let centralDirSize = 0;
  preparedFiles.forEach(f => {
    centralDirSize += 46 + f.nameBytes.length;
  });

  const eocdSize = 22;
  const totalZipSize = centralDirStart + centralDirSize + eocdSize;
  const out = new Uint8Array(totalZipSize);
  const view = new DataView(out.buffer);

  // 1. Write Local File Headers + File Data
  preparedFiles.forEach(f => {
    let pos = f.offset;
    view.setUint32(pos, 0x04034b50, true); // Local file header signature
    view.setUint16(pos + 4, 10, true);     // Version needed (1.0)
    view.setUint16(pos + 6, 0x0800, true); // UTF-8 filename flag
    view.setUint16(pos + 8, 0, true);      // Compression: Store (0)
    view.setUint16(pos + 10, 0x4821, true);// Mod time
    view.setUint16(pos + 12, 0x5821, true);// Mod date
    view.setUint32(pos + 14, f.crc, true); // CRC-32
    view.setUint32(pos + 18, f.size, true);// Compressed size
    view.setUint32(pos + 22, f.size, true);// Uncompressed size
    view.setUint16(pos + 26, f.nameBytes.length, true); // Filename length
    view.setUint16(pos + 28, 0, true);     // Extra field length
    out.set(f.nameBytes, pos + 30);
    out.set(f.dataBytes, pos + 30 + f.nameBytes.length);
  });

  // 2. Write Central Directory Headers
  let cdPos = centralDirStart;
  preparedFiles.forEach(f => {
    view.setUint32(cdPos, 0x02014b50, true); // Central directory header signature
    view.setUint16(cdPos + 4, 20, true);     // Version made by
    view.setUint16(cdPos + 6, 10, true);     // Version needed
    view.setUint16(cdPos + 8, 0x0800, true); // UTF-8 filename flag
    view.setUint16(cdPos + 10, 0, true);     // Compression: Store
    view.setUint16(cdPos + 12, 0x4821, true);// Mod time
    view.setUint16(cdPos + 14, 0x5821, true);// Mod date
    view.setUint32(cdPos + 16, f.crc, true); // CRC-32
    view.setUint32(cdPos + 20, f.size, true);// Compressed size
    view.setUint32(cdPos + 24, f.size, true);// Uncompressed size
    view.setUint16(cdPos + 28, f.nameBytes.length, true); // Filename length
    view.setUint16(cdPos + 30, 0, true);     // Extra field length
    view.setUint16(cdPos + 32, 0, true);     // Comment length
    view.setUint16(cdPos + 34, 0, true);     // Disk number start
    view.setUint16(cdPos + 36, 0, true);     // Internal file attributes
    view.setUint32(cdPos + 38, 0, true);     // External file attributes
    view.setUint32(cdPos + 42, f.offset, true); // Relative offset of local header
    out.set(f.nameBytes, cdPos + 46);
    cdPos += 46 + f.nameBytes.length;
  });

  // 3. Write End of Central Directory Record (EOCD)
  view.setUint32(cdPos, 0x06054b50, true); // EOCD signature
  view.setUint16(cdPos + 4, 0, true);      // Number of this disk
  view.setUint16(cdPos + 6, 0, true);      // Disk with start of CD
  view.setUint16(cdPos + 8, preparedFiles.length, true);  // Number of entries on disk
  view.setUint16(cdPos + 10, preparedFiles.length, true); // Total entries
  view.setUint32(cdPos + 12, centralDirSize, true);        // Size of CD
  view.setUint32(cdPos + 16, centralDirStart, true);       // Offset of CD
  view.setUint16(cdPos + 20, 0, true);     // Comment length

  return out;
}

/**
 * Downloads a list of files as a ZIP archive directly in the browser.
 * @param {Array<{name: string, content: string}>} files
 * @param {string} filename
 */
export function downloadZipClient(files, filename = 'dietcode_codebase.zip') {
  const binary = buildZipBinary(files);
  const blob = new Blob([binary], { type: 'application/zip' });
  const url = URL.createObjectURL(blob);
  const a = document.createElement('a');
  a.href = url;
  a.download = filename.endsWith('.zip') ? filename : `${filename}.zip`;
  document.body.appendChild(a);
  a.click();
  document.body.removeChild(a);
  setTimeout(() => URL.revokeObjectURL(url), 1500);
}

