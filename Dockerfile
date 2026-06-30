FROM python:3.12-slim

WORKDIR /app

# ffmpeg + шрифты-зависимости для libass. Никакого Chromium не нужно (рендер на ffmpeg).
RUN apt-get update && apt-get install -y --no-install-recommends \
        ffmpeg fonts-dejavu-core \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

CMD ["python", "main.py"]
