FROM python:3.12-slim

WORKDIR /app

RUN groupadd --gid 1000 lashbot \
    && useradd --uid 1000 --gid lashbot --create-home lashbot

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY app/ ./app/

USER lashbot

CMD ["python", "-m", "app.main"]
