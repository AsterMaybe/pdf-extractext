// Shared by the k6 spike tests in this folder.
//
// The extractor caches on the SHA-256 of the uploaded bytes
// (microservicio-go/application/extract_text.go), so re-uploading one document
// measures the Redis path instead of MuPDF. Appending a unique, fixed-length
// ASCII tail after the file's final %%EOF gives every request its own SHA-256
// while keeping the PDF valid and its parse cost identical:
//
//   - the magic check only looks at the first five bytes, so "%PDF-" still passes;
//   - the tail lands after all content, so no xref offset moves and MuPDF stops
//     at the original EOF: the parse work is unchanged;
//   - a constant tail length keeps every request exactly the same size.

const MARKER_LEN = 64;

function padMarker(s) {
  if (s.length >= MARKER_LEN) {
    return s.slice(0, MARKER_LEN);
  }
  return s + '.'.repeat(MARKER_LEN - s.length);
}

// makeUniquePdf returns an ArrayBuffer ready for http.file(): the bytes of `base`
// with a unique 64-byte ASCII tail appended. `base` is a Uint8Array; `unique` is
// any string whose value differs per request.
export function makeUniquePdf(base /* Uint8Array */, unique /* string */) {
  const marker = padMarker(unique);
  const buf = new Uint8Array(base.length + MARKER_LEN);
  buf.set(base, 0);
  for (let i = 0; i < MARKER_LEN; i++) {
    buf[base.length + i] = marker.charCodeAt(i) & 0x7f;
  }
  return buf.buffer;
}
