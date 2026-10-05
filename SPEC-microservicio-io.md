# Spec: microservicio-io

## Objective

Build a Go microservice for PDF text extraction that serves as the extraction backend for the monolithic `pdf-extractext` project. The monolith already has a `RemotePdfProcessor` (`app/infrastructure/remote_pdf_processor.py`) that sends PDF files to this microservice via HTTP and expects extracted text in return. This microservice encapsulates the PDF text extraction concern, keeping the monolith's core domain free from PDF-processing dependencies.

The microservice receives a PDF via `multipart/form-data`, extracts the text using a Go PDF library, and returns the extracted text along with metadata. It follows the existing contract defined by the monolith's `RemotePdfProcessor`.

Success criteria: The monolith's `RemotePdfProcessor.extract_text()` works end-to-end against the Go microservice without changes to its logic.

## Tech Stack

- **Language**: Go 1.22
- **Web framework**: Gin (lightweight, idiomatic, minimal abstraction overhead)
- **PDF text extraction**: `github.com/360EntSecGroup-Skylar/pdf` (reads PDF content and extracts text)
- **Error handling**: RFC 9457 (`ProblemDetails`) via custom middleware
- **Configuration**: Environment variables via `os.Getenv` (consistent with monolith's `.env` pattern)
- **Testing**: Go test suite (`go test`), table-driven tests for handler logic
- **Docker**: Official `golang:1.22-slim` image, compiled binary placed in `/app`

Dependencies (go.mod):
```
github.com/gin-gonic/gin v1.10.0
github.com/360EntSecGroup-Skylar/pdf v0.0.0-20231022120000-abc123def456
```

## Commands

| Command | Description |
|---|---|
| `go run main.go` | Start the microservice (development) |
| `go test ./...` | Run all tests |
| `go test -cover ./...` | Run tests with coverage report |
| `go build -o microservicio-io main.go` | Build the binary |
| `docker build -t microservicio-io .` | Build Docker image |
| `docker run -p 8080:8080 microservicio-io` | Run Docker container |

## Project Structure

```
microservicio-io/
├── main.go                # Entry point + router setup
├── go.mod                # Module definition + dependencies
├── go.sum                # Lockfile
├── internal/
│   ├── handler/          # HTTP request handlers (extract, health)
│   ├── model/            # Request/response models
│   ├── service/          # PDF extraction business logic
│   └── error/            # Error types + RFC 9457 conversion
├── external/
│   └── pdf/              # PDF text extraction adapter
├── docker/
│   └── Dockerfile        # Multi-stage build for small binary
├── docker-compose.yml    # Service orchestration (Traefik labels included)
├── .env.example          # Environment variable templates
└── README.md             # This spec + setup instructions
```

## Code Style

Naming conventions:
- **Packages**: lowercase, single words (`handler`, `model`, `service`, `error`, `pdf`)
- **Functions**: `camelCase` (e.g., `extractText`, `computeChecksum`)
- **Types/Structs**: `PascalCase` (e.g., `ExtractRequest`, `ProblemDetail`)
- **Constants**: `UPPER_SNAKE_CASE` (e.g., `MAX_FILE_SIZE`, `DEFAULT_TIMEOUT`)
- **Files**: `snake_case` (e.g., `error_handler.go`, `pdf_service.go`)

Example handler snippet following project conventions:

```go
package handler

import (
    "net/http"

    "github.com/gin-gonic/gin"
    "microservicio-io/internal/model"
    "microservicio-io/internal/error"
)

func Extract(c *gin.Context) {
    req := model.ExtractRequest{}
    if err := c.ShouldBind(&req); err != nil {
        c.Error(error.ValidationError(err)) // RFC 9457 400
        return
    }

    text, err := service.Extract(req.FileBytes, req.Filename)
    if err != nil {
        code := error.CodeFor(err)
        c.AbortWithStatusJSON(code, error.ProblemDetail(code, err.Error()))
        return
    }

    c.JSON(http.StatusOK, model.ExtractResponse{
        Filename: req.Filename,
        Text:     text,
    })
}
```

## Testing Strategy

- **Framework**: Go test (native, no external test framework needed)
- **Test locations**: `_test.go` files alongside implementation
- **Test levels**:
  - **Unit**: Handler logic, error conversion, PDF service extraction with mock bytes
  - **Integration**: Full HTTP round-trip (`httpx` or `net/http` test client)
- **Coverage expectation**: >= 80% on handler and service layers
- **Test patterns**: Table-driven tests for error scenarios (400, 422, 413, 504, 500)
- **Hermeticity**: Tests can run without a running PDF library dependency on actual binary — use byte fixtures

Example test pattern:

```go
func TestExtract_Success(t *testing.T) {
    fixtures := []struct {
        name    string
        bytes   []byte
        wantErr bool
    }{
        {"valid-pdf-fixture", validPDFBytes, false},
        {"non-pdf bytes", []byte("not a pdf"), true},
        {"empty bytes", []byte{}, true},
    }
    for _, fs := range fixtures {
        t.Run(fs.name, func(t *testing.T) {
            _, err := service.Extract(fs.bytes, "test.pdf")
            if fs.wantErr && err == nil {
                t.Fatal("expected error, got nil")
            }
            if !fs.wantErr && err != nil {
                t.Fatalf("unexpected error: %v", err)
            }
        })
    }
}
```

## Boundaries

- **Always do**:
  - Run `go test ./...` before committing
  - Validate that the multipart `file` field is a PDF (magic bytes `%PDF`) before processing
  - Return RFC 9457 `ProblemDetails` for all error responses
  - Use environment variables for configuration (no hardcoded values)
  - Keep handler functions small and focused (one concern per function)

- **Ask first**:
  - Adding new PDF text extraction libraries (evaluate if `pdfcpu` or `qpdf` better fits)
  - Changing the HTTP framework (currently Gin; any change impacts router and middleware)
  - Modifying the response schema (must keep backward compatibility with `RemotePdfProcessor`)

- **Never do**:
  - Commit secrets (API keys, connection strings) to the repository
  - Edit `go.mod` or `go.sum` without `go mod tidy`
  - Return raw error messages to the client — always convert to RFC 9457 format
  - Block the event loop with CPU-bound PDF parsing — use Go's concurrency (goroutines/channels) if needed

## Success Criteria

The microservice is complete when all of the following are true:

1. **Binary builds**: `go build -o microservicio-io main.go` produces a working binary with no errors
2. **Docker image builds**: `docker build -t microservicio-io .` succeeds and the container starts listening on `:8080`
3. **Health endpoint**: `GET /health` returns `200 OK` with `{"status":"ok"}`
4. **Extract endpoint**: `POST /api/v1/extract` with valid PDF multipart returns `200` with `{"filename":"...","extension":".pdf","mime_type":"application/pdf","text":"<extracted>"}`
5. **Error mapping**: All error codes return proper RFC 9457 `application/problem+json`:
   - 400 → `invalid-file`
   - 422 → `malformed-pdf`
   - 413 → `too-large`
   - 504 → `timeout`
   - 500 → `server-error`
6. **Test suite**: `go test ./...` passes with >= 80% coverage on handler and service packages
7. **Monolith compatibility**: The existing `RemotePdfProcessor.extract_text()` works against the microservice without code changes

## Open Questions

1. PDF library choice: The spec uses `github.com/360EntSecGroup-Skylar/pdf`. Should we evaluate `pdfcpu` or `qpdf` for better performance or licensing?
2. Maximum file size: The monolith enforces `PDF_MAX_SIZE_MB = 15`. Should the microservice enforce the same limit, or rely on Traefik/middleware?
3. Timeout value: The existing `EXTRACT_TIMEOUT_SECONDS = 30.0` in the monolith — should this be configurable or fixed?
4. Response filename: The contract returns the original filename. Should we compute a safe filename or use the uploaded one as-is?

These questions will be resolved with the human before implementation begins.