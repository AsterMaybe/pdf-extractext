import http from 'k6/http';
import { check } from 'k6';
import exec from 'k6/execution';
import { textSummary } from 'https://jslib.k6.io/k6-summary/0.0.4/index.js';
import { makeUniquePdf } from './unique-pdf.js';

// Exact Spike test profile required by the assignment[cite: 3]
const FULL_STAGES = [
    { duration: '10s', target: 100 },
    { duration: '20s', target: 100 },
    { duration: '10s', target: 0 },
];
// Tiny profile for a fast local sanity check: SMOKE=1 k6 run spike-test-singular.js
const SMOKE_STAGES = [
    { duration: '3s', target: 5 },
];

export const options = {
    stages: __ENV.SMOKE === '1' ? SMOKE_STAGES : FULL_STAGES,
    // Update this host mapping if your environment uses extract.localhost instead
    hosts: { 'extract.localhost': '127.0.0.1' },
};

const BASE_URL = __ENV.BASE_URL || 'http://extract.localhost';

// One base document, opened once. Every request appends a unique tail so its
// SHA-256 differs from all others: the service's content-hash cache always
// misses and MuPDF actually parses. The tail length is constant, so file size
// and parse cost stay identical across requests.
const baseBytes = new Uint8Array(open('./Essential-Kanban-Condensed-Spanish.pdf', 'b'));

// Per-VU counter; iterationInTest already makes each request unique on its own,
// the extra fields just make collisions impossible regardless of clock skew.
let counter = 0;

export default function () {
    const unique = `${exec.vu.idInTest}-${exec.scenario.iterationInTest}-${Date.now()}-${counter++}`;
    const fileBytes = makeUniquePdf(baseBytes, unique);

    // Mandatory endpoint required by the TP[cite: 2]
    const url = `${BASE_URL}/extract`;

    const data = {
        file: http.file(fileBytes, 'test_document.pdf', 'application/pdf'),
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
        'k6-results-summary.txt': textSummary(data, { indent: ' ', enableColors: false }),
    };
}
