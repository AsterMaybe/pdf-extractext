FROM python:3.14-slim

ENV PATH=$PATH:/home/app/.venv/bin

RUN useradd --create-home --home-dir /home/app app
RUN apt-get update
RUN apt-get install -y build-essential
RUN apt-get purge -y --auto-remove -o APT::AutoRemove::RecommendsImportant=false
RUN rm -rf /var/lib/apt/lists/*

WORKDIR /home/app

USER app

ADD https://astral.sh/uv/install.sh ./uv-installer.sh
RUN sh ./uv-installer.sh && rm ./uv-installer.sh

COPY ./app ./app

COPY ./pyproject.toml ./uv.lock ./
RUN uv sync --locked

EXPOSE 8000

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000", "--workers", "4"]
