# Werkt zowel als losse container als binnen een Home Assistant add-on.
ARG BUILD_FROM=python:3.12-slim
FROM $BUILD_FROM

# tesseract-ocr is enkel nodig voor de foto-ingave zonder AI.
RUN apt-get update && apt-get install -y --no-install-recommends \
        python3 python3-pip \
        tesseract-ocr tesseract-ocr-nld tesseract-ocr-fra tesseract-ocr-eng \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app
COPY requirements.txt .
RUN pip3 install --no-cache-dir --break-system-packages -r requirements.txt || \
    pip3 install --no-cache-dir -r requirements.txt

COPY . .
RUN chmod a+x /app/run.sh

ENV PORT=8099 \
    PYTHONUNBUFFERED=1
EXPOSE 8099

CMD ["/app/run.sh"]
