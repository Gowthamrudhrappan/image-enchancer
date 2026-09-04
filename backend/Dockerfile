FROM python:3.10-slim

# System libs OpenCV/torch need at runtime
RUN apt-get update && apt-get install -y --no-install-recommends \
    git \
    libgl1 \
    libglib2.0-0 \
    ffmpeg \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY app.py .

# Model weights get downloaded here on first request and cached for
# every request after — mount this as a volume in production so a
# redeploy doesn't re-download ~400MB of weights every time.
RUN mkdir -p /app/weights
ENV CLARITY_WEIGHTS_DIR=/app/weights

EXPOSE 8000

CMD ["uvicorn", "app:app", "--host", "0.0.0.0", "--port", "8000"]
