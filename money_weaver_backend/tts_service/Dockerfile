# MoneyWeaver MOSS-TTS inference service.
# Runs in its OWN venv (tts_service/.venv, python 3.12). NEVER install into main venv.
FROM python:3.12-slim

WORKDIR /app

RUN apt-get update \
    && apt-get install -y --no-install-recommends git libsndfile1 \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# MOSS-TTS-Nano source (small repo) cloned at build; the ONNX weights (~728MB)
# lazy-download at runtime into <repo>/models on the first /tts request.
RUN git clone --depth 1 https://github.com/OpenMOSS/MOSS-TTS-Nano.git \
    && pip install --no-cache-dir --no-deps -e ./MOSS-TTS-Nano

COPY app.py .

EXPOSE 8001
CMD ["uvicorn", "app:app", "--host", "0.0.0.0", "--port", "8001"]
