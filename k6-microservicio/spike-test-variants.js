import http from 'k6/http';
import { check } from 'k6';
import exec from 'k6/execution';
import { textSummary } from 'https://jslib.k6.io/k6-summary/0.0.4/index.js';
import { makeUniquePdf } from './unique-pdf.js';

// Variant counterpart to spike-test-singular.js.
//
// spike-test-singular.js always posts the same document. The service keys its
// cache on the SHA-256 of the uploaded bytes, so after the first parse every
// later request is served straight from Redis and the numbers describe the cache
// path, not MuPDF. Both scripts here defeat that by appending a unique tail to
// every upload, so each request has its own hash and its own parse.
//
// This script rounds-robins over four real documents of different sizes and page
// counts, so the parse mix is broader than the singular run's single file. As in
// the singular script, the appended tail length is constant, so any difference in
// the results comes from the document mix and nothing else.
//
// Options are identical to the singular run on purpose: same stages, same hosts,
// same checks.
//
// Memory note: k6 copies open() fixtures per VU. This pool is the four documents
// in this folder (about 13 MB total), so at the full 100-VU spike that is ~1.3 GB
// of fixtures before any traffic. Use -e SMOKE=1 for a small, fast check.
const FULL_STAGES = [
    { duration: '10s', target: 100 },
    { duration: '20s', target: 100 },
    { duration: '10s', target: 0 },
];
// Tiny profile for a fast local sanity check: SMOKE=1 k6 run spike-test-variants.js
const SMOKE_STAGES = [
    { duration: '3s', target: 5 },
];

export const options = {
    stages: __ENV.SMOKE === '1' ? SMOKE_STAGES : FULL_STAGES,
    // Update this host mapping if your environment uses extract.localhost instead
    hosts: { 'extract.localhost': '127.0.0.1' },
};

const BASE_URL = __ENV.BASE_URL || 'http://extract.localhost';

// new Uint8Array(arrayBuffer) is a view, not a copy, so this does not duplicate
// the fixture bytes in memory.
const sources = [
    open('./2020-Scrum-Guide-Spanish-Latin-South-American.pdf', 'b'),
    open('./Essential-Kanban-Condensed-Spanish.pdf', 'b'),
    open('./Filosofia Lean.pdf', 'b'),
    open('./scrum_manager_historias_usuario.pdf', 'b'),
].map((ab) => new Uint8Array(ab));

function variantName(index) {
    return `doc_${String(index).padStart(3, '0')}.pdf`;
}

// Per-VU counter; iterationInTest already makes each request unique on its own,
// the extra fields just make collisions impossible regardless of clock skew.
let counter = 0;

export default function () {
    // Round robin over the pool instead of a random draw, so early requests in a
    // run are guaranteed to vary. The appended tail then makes every upload
    // byte-distinct even once the pool wraps.
    const index = exec.scenario.iterationInTest % sources.length;
    const unique = `${exec.vu.idInTest}-${exec.scenario.iterationInTest}-${Date.now()}-${counter++}`;
    const fileBytes = makeUniquePdf(sources[index], unique);

    // Mandatory endpoint required by the TP[cite: 2]
    const url = `${BASE_URL}/extract`;

    const data = {
        file: http.file(fileBytes, variantName(index), 'application/pdf'),
    };

    const res = http.post(url, data);

    // Debug print if status is not 200 so you can see why it failed
    if (res.status !== 200) {
        console.log(`Error! Status: ${res.status} - Body: ${res.body}`);
    }

    // Strictly checks for HTTP 200 and the mandatory JSON keys[cite: 2].
    // 429 (overload backpressure) is a failed check on purpose: the spike is
    // meant to record shedding, not to hide it.
    check(res, {
        'status is 200 OK': (r) => r.status === 200,
        'has valid JSON output': (r) => {
            try {
                const body = JSON.parse(r.body);
                return body.content !== undefined && body.page_count !== undefined;
            } catch (e) {
                return false;
            }
        },
    });
}

// Generates the text file summary for your AI agent
export function handleSummary(data) {
    return {
        'stdout': textSummary(data, { indent: ' ', enableColors: true }),
        'k6-results-variants-summary.txt': textSummary(data, { indent: ' ', enableColors: false }),
    };
}
