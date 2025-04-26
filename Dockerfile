# Dockerfile – horse-bets scraper
FROM python:3.12-slim

# 1. Basic envs
ENV PIP_NO_CACHE_DIR=1 \
    PYTHONUNBUFFERED=1 \
    TZ=Europe/Paris \
    POETRY_VERSION=1.8.2

# 2. System deps for Playwright
RUN apt-get update && apt-get install -y --no-install-recommends \
        ca-certificates curl gnupg libnss3 libatk1.0-0 libatk-bridge2.0-0 \
        libcups2 libdrm2 libxkbcommon0 libxdamage1 libxcomposite1 libxrandr2 \
        libgbm1 libgtk-3-0 libpango-1.0-0 libasound2 libegl1 && \
    rm -rf /var/lib/apt/lists/*

# 3. Install Poetry
RUN pip install "poetry==$POETRY_VERSION"

# 4. Copy project & install deps
WORKDIR /app
COPY pyproject.toml poetry.lock* ./
RUN poetry install --only main --no-interaction --no-ansi

# 5. Copy the code (after deps for better caching)
COPY . .

# 6. Install Playwright browsers (headless Chromium)
RUN poetry run playwright install --with-deps chromium

# 7. Expose nothing (not a web app) and run
CMD ["poetry", "run", "python", "main.py"]
