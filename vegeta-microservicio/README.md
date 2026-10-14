# Vegeta load tests — cache path vs parse path

Two profiles, and the difference between them is the whole point of this folder.

| Profile | Targets file | Documents | What it measures |
|---|---|---|---|
| `parse` | `targets-parse.txt` | 200 distinct, round robin | The MuPDF parser and the CPU budget |
| `cache` | `targets-cache.txt` | 1, replayed | The Redis path only |

## Why one document is not enough

The service caches on the SHA-256 of the uploaded bytes
(`application/extract_text.go:133`), and concurrent misses for the same hash are
coalesced by a singleflight (`:144`). So a test that uploads the same PDF over and
over does not measure the parser:

- the first request parses and warms the cache;
- every later request returns from Redis without touching MuPDF;
- a burst of identical uploads is additionally collapsed into a single parse.

Both effects are defeated by uploading byte-distinct documents, which is what the
`parse` profile does.

The consequence for reporting: the number of genuine parses is `min(N, R)` for N
distinct documents and R requests, so the cache hit rate is
`1 - min(N, R)/R`. Keep N at or above R for a clean parser measurement.

## Prerequisites

1. Docker Desktop running, with the stack up.
2. **`extract.localhost` must resolve to 127.0.0.1.** Traefik routes on
   `Host(extract.localhost)` and publishes port 80, but there is no DNS entry for
   that name and Vegeta has no equivalent of k6's `hosts` option. Add this line to
   `C:\Windows\System32\drivers\etc\hosts` (needs Administrator):

   ```
   127.0.0.1 extract.localhost
   ```

   Requesting `http://127.0.0.1/extract` instead does **not** work: Traefik would
   see `Host: 127.0.0.1`, fail the router rule and return 404.
3. Fixtures generated — see below.

## Generate the fixtures

```powershell
cd ..\loadtest-tools
go run ./gen-variants -source "..\k6-microservicio\2020-Scrum-Guide-Spanish-Latin-South-American.pdf" `
  -n 200 -pdf-dir variants -body-dir bodies `
  -targets "..\vegeta-microservicio" -body-ref "..\loadtest-tools\bodies" `
  -url "http://extract.localhost/extract"
```

Each variant is the source PDF plus a short trailing comment, so every file has a
distinct SHA-256 while its parse cost stays identical. The generator verifies
uniqueness and round-trips each multipart body before exiting.

Disk cost is roughly `2 x N x document size`: 200 variants of the 312 KB PDF is
about 122 MB. Vegeta streams each body from disk per request, so unlike k6 the
pool size costs no client memory — raising `-n` to a few thousand only costs disk.
That is why Vegeta, not k6, is the tool for the authoritative parse-path number.

## Run

Windows blocks unsigned scripts by default, so invoke with a bypass:

```powershell
# Parse path: 200 distinct documents, 300 req/s for 60s
powershell -ExecutionPolicy Bypass -File .\run-variants.ps1 -Profile parse -Rate 300 -Duration 60s

# Cache path: single document, same offered load
powershell -ExecutionPolicy Bypass -File .\run-variants.ps1 -Profile cache -Rate 300 -Duration 60s

# Parse path with a hard request budget, so N can be kept >= R
powershell -ExecutionPolicy Bypass -File .\run-variants.ps1 -Profile parse -RateVsRequests 200
```

Results are written to `results\<profile>-<timestamp>.bin`; re-report at any time
with `vegeta report results\<file>.bin`.

Useful switches: `-Url` to retarget without regenerating, `-Timeout`, `-Workers`,
`-OutputDir`.

## Confirming what actually ran

Do not trust the request count on its own — a run can look healthy while almost
every request was a cache hit. A cache hit returns before
`extractAndCache`, so it never persists anything, which gives you a direct
measurement:

```
real parses = number of documents in MongoDB
hit rate    = 1 - (documents in MongoDB / total requests)
```

- Parse profile, healthy: `documents ≈ requests`.
- Any run, suspicious: a handful of documents against thousands of requests.

`manifest.csv` in `../loadtest-tools/variants` lists the SHA-256 of every
generated document if you need to confirm which ones were sent.

## Notes

- Do not pass `-keepalive true` to `vegeta attack`. It is a bool flag, so the
  separate `true` becomes a stray positional argument, and Vegeta then silently
  ignores `-output` and dumps results to stdout.
- Piping `vegeta attack` into `vegeta report` fails on Windows PowerShell with
  `can't detect encoding of "stdin"`. Write to a file with `-output` and report
  from the file, which is what the runner does.