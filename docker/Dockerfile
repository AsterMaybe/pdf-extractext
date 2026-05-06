FROM python:3.14

WORKDIR /app

COPY  pyproject.toml .

RUN pip install .

COPY .. .

EXPOSE 8000

CMD ["python", "app/main.py"]