FROM python:3.14-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy
    
COPY --from=ghcr.io/astral-sh/uv:0.11.17 /uv /bin/

RUN useradd --create-home --home-dir /home/app app

WORKDIR /home/app

COPY --chown=app:app ./pyproject.toml ./uv.lock ./

RUN uv sync --locked --no-cache --no-dev

COPY --chown=app:app ./app ./app

USER app

EXPOSE 8000

CMD [".venv/bin/uvicorn", "app.main:app", "--host", "0.0.0.0"]