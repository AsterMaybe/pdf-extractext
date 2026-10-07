# Plan: microservicio-io

## Implementation Order (by dependency)

1. **Set up Go module** (`main.go`, `go.mod`) — foundational; all other layers depend on module name and entry point
2. **PDF extraction adapter** (`external/pdf/extractor.go`) — low-level PDF text extraction; depends on nothing external except the Go PDF library
3. **Error types and RFC 9457 conversion** (`internal/error/`) — defines problem details; depends on nothing; reusable by all handlers
4. **Response models** (`internal/model/`) — request/response structs; depends on nothing; pure data types
5. **HTTP handler** (`internal/handler/extract.go`) — binds request, delegates to service, converts errors; depends on `model`, `error`, `service`
6. **Health handler** (`internal/handler/health.go`) — simple liveness/readiness check; depends on nothing
7. **Router setup** (`main.go`) — Gin router with middleware (error conversion, CORS if needed); depends on all handlers
8. **Dockerfile** — multi-stage build; depends on compiled binary from step 5
9. **docker-compose.yml** — Traefik service definition; depends on Docker image
10. **Tests** — unit + integration test suite; depends on all implementation layers

## Risks and Mitigation

| Risk | Mitigation |
|---|---|
| PDF library cannot extract text from certain PDFs | Start with library evaluation; add fallback to monolith's PyMuPDF if critical PDFs fail |
| RFC 9457 error mapping misses a code | Write tests first for each error code; map covers known codes from `RemotePdfProcessor` |
| Go binary size too large for Docker | Use multi-stage build: `golang:1.22-slim` builder + `distroless` runner; strip debug info |
| Traefik routing misconfiguration | Traefik stays in monolith; microservice only needs to expose `:8080`; test with `localhost:8080` locally |

## Parallelization Opportunities

- **Steps 3, 4, 6** (error models, data models, health handler) are independent and can be implemented in parallel since they have no dependencies on each other.
- **Steps 5** (extract handler) depends on steps 3 and 4 being complete.
- **Steps 1** must be first; **Step 9** must be last.

## Verification Checkpoints

| Checkpoint | When | Criteria |
|---|---|---|
| Module setup | After step 1 | `go mod init` creates `go.mod`; `go vet` passes |
| PDF adapter ready | After step 2 | `go test -run PDF` extracts text from fixture PDFs |
| Error handling complete | After step 3 | All 5 RFC 9457 error codes map correctly |
| Handler works | After step 5 | `go test -run Extract` passes with table-driven tests |
| Full HTTP round-trip | After step 7 | `go test -run Integration` sends POST multipart, gets 200 + text |
| Docker build | After step 8 | `docker build` succeeds, image < 50MB |
| End-to-end with monolith | After step 10 | `RemotePdfProcessor.extract_text()` works against live microservice |

## Task List (tasks/todo.md)

Each task below is scoped to ~1-3 files and can be completed in a single focused session.

- [ ] **Task: Initialize Go module and directory structure**
  - Acceptance: `go.mod` created with module name `microservicio-io`; `internal/`, `external/`, `docker/` directories exist
  - Verify: `go mod tidy` runs without errors; `go vet` passes
  - Files: `go.mod`, `main.go`, `internal/`, `external/`, `docker/`

- [ ] **Task: Implement PDF text extraction adapter**
  - Acceptance: Extracts text from a known-valid PDF fixture; returns empty string for non-extractable PDFs
  - Verify: `go test -run PDFExtraction` passes with fixture comparisons
  - Files: `external/pdf/extractor.go`, `external/pdf/fixtures_test.go`

- [ ] **Task: Implement error types and RFC 9457 conversion**
  - Acceptance: Five error codes (`invalid-file`, `malformed-pdf`, `too-large`, `timeout`, `server-error`) produce correct `ProblemDetails` JSON with `type`, `title`, `status`, `detail` fields
  - Verify: Unit tests for each code's JSON output
  - Files: `internal/error/errors.go`, `internal/error/problem.go`

- [ ] **Task: Implement request/response models**
  - Acceptance: `ExtractRequest` accepts `file` bytes and `filename`; `ExtractResponse` has `filename`, `extension`, `mime_type`, `text` fields
  - Verify: Models marshal/unmarshal correctly to/from JSON
  - Files: `internal/model/extract.go`

- [ ] **Task: Implement HTTP extract handler**
  - Acceptance: Binds multipart `file` field, validates PDF magic bytes, calls service, returns 200 with text or RFC 9457 error
  - Verify: `go test -run ExtractHandler` passes all table-driven scenarios (valid, invalid format, too large, etc.)
  - Files: `internal/handler/extract.go`

- [ ] **Task: Implement health handler**
  - Acceptance: `GET /health` returns `200 {"status":"ok"}`
  - Verify: curl or browser test returns expected JSON
  - Files: `internal/handler/health.go`, `main.go` (router registration)

- [ ] **Task: Set up router and middleware in main.go**
  - Acceptance: Gin router registers `/health` and `/api/v1/extract` endpoints with correct methods; error conversion middleware converts any unhandled error to RFC 9457
  - Verify: `go run main.go` starts server responding to both endpoints
  - Files: `main.go`

- [ ] **Task: Create Dockerfile for multi-stage build**
  - Acceptance: `docker build -t microservicio-io .` succeeds; running container listens on `:8080`
  - Verify: Container healthcheck passes
  - Files: `docker/Dockerfile`

- [ ] **Task: Create docker-compose.yml with Traefik labels**
  - Acceptance: Service `microservicio-io` exposed on port 8080 with Traefik router rule `Host('io.localhost')` and error delegation middleware
  - Verify: `docker compose up -d` starts service; Traefik routes traffic correctly
  - Files: `docker-compose.yml`

- [ ] **Task: Write unit and integration test suite**
  - Acceptance: `go test ./...` passes with >= 80% coverage on `internal/` and `external/`
  - Verify: Coverage report shows threshold met; all error codes tested end-to-end
  - Files: `internal/*_test.go`, `external/*_test.go`

- [ ] **Task: Verify end-to-end with monolith's RemotePdfProcessor**
  - Acceptance: Start microservice locally; configure `PDF_EXTRACT_SERVICE_URL=http://localhost:8080`; run monolith's `TestRemotePdfProcessorExtractText` and pass
  - Verify: No modifications to monolith's `remote_pdf_processor.py` or related test fixtures
  - Files: (no new files — verification across repos)

## Build Order Enforcement

```
1. Go module → 2. PDF adapter → 3. Error models → 4. Data models → 5. Handler → 6. Router → 7. Docker → 8. Compose → 9. Tests → 10. E2E
```

Each task depends only on the immediately preceding tasks. Tasks 3 and 4 can run in parallel after task 1; task 5 depends on 3 and 4; task 6 depends on 5; etc.