# Dockerfile voor de Collectiekaart-mediabeheerder.
# Werkt zowel als losstaande container (docker run) als ingebed in een
# Home Assistant add-on (zie config.yaml + run.sh voor het add-on-jasje).
ARG BUILD_FROM=python:3.12-slim
FROM $BUILD_FROM

# tesseract-ocr: nodig voor de lokale (niet-AI) foto-herkenning
RUN apt-get update && apt-get install -y --no-install-recommends \
    tesseract-ocr tesseract-ocr-nld tesseract-ocr-fra tesseract-ocr-eng \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .
RUN mkdir -p /data /app/static/uploads

ENV PORT=8099
EXPOSE 8099

COPY run.sh /run.sh
RUN chmod a+x /run.sh
CMD ["/run.sh"]
