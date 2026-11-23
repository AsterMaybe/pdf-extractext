# Build stage - Python 3.15.2 on Alpine 3.24 with uv
FROM python:3.15.2-alpine3.24@sha256:0f9552bb28711333da16915ec146f5e6bb44a7fdac9ced15dc17c2e0206346dd AS builder

RUN apk add --no-cache gcc musl-dev libffi-dev openssl-dev cargo
WORKDIR /home/app

COPY pyproject.toml uv.lock ./
RUN pip install --no-cache-dir uv && uv sync --no-cache --no-dev

COPY ./app ./app

# Runtime stage - Python 3.15.2 on Alpine 3.24
FROM python:3.15.2-alpine3.24@sha256:0f9552bb28711333da16915ec146f5e6bb44a7fdac9ced15dc17c2e0206346dd

RUN apk upgrade --no-cache && apk add --no-cache ca-certificates

# Usuario no-root con UID/GID fijos (D1).
RUN addgroup -S -g 10001 app \
    && adduser -S -u 10001 -G app -h /home/app app

WORKDIR /home/app

COPY --from=builder /home/app/.venv ./.venv
COPY --from=builder /home/app/app ./app

USER 10001:10001

EXPOSE 8000

ENV PATH="/home/app/.venv/bin:$PATH" \
    PYTHONUNBUFFERED=1 \
    UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy

ENTRYPOINT [".venv/bin/uvicorn", "app.main:app", "--host", "0.0.0.0"]