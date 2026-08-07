FROM python:3.12-slim

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1

WORKDIR /app

COPY requirements/ /tmp/requirements/
RUN pip install --no-cache-dir -r /tmp/requirements/prod.txt

COPY . /app/

EXPOSE 8000
