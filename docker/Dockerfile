FROM python:3.14-slim

RUN useradd --create-home --home-dir /home/app app

WORKDIR /home/app

RUN pip install --no-cache-dir uv

COPY ./pyproject.toml ./uv.lock ./

RUN uv sync --locked

COPY ./app ./app

RUN chown -R app:app /home/app

USER app

EXPOSE 8000

CMD ["uv", "run", "uvicorn", "app.main:app", "--host", "0.0.0.0"]
