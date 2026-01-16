# Use Python 3.11.9 as base image
FROM python:3.11.9-slim

# Set working directory to the project root
WORKDIR /app

# Install system dependencies including Korean fonts and WeasyPrint dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    ca-certificates \
    curl \
    gnupg \
    build-essential \
    fonts-nanum \
    fonts-nanum-coding \
    fonts-nanum-extra \
    fontconfig \
    libpango-1.0-0 \
    libpangoft2-1.0-0 \
    libgdk-pixbuf2.0-0 \
    libffi-dev \
    shared-mime-info \
    && curl -fsSL https://deb.nodesource.com/setup_20.x | bash - \
    && apt-get update \
    && apt-get install -y nodejs \
    && npm install --global gulp-cli \
    && fc-cache -fv \
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/*

# Install Chrome and required dependencies for Lighthouse
RUN apt-get update && apt-get install -y \
    chromium \
    chromium-driver \
    && npm install -g lighthouse@latest

# Install AWS CLI
RUN curl "https://awscli.amazonaws.com/awscli-exe-linux-x86_64.zip" -o "awscliv2.zip" \
    && apt-get update \
    && apt-get install -y unzip \
    && unzip awscliv2.zip \
    && ./aws/install \
    && rm -rf aws awscliv2.zip

# Copy requirements file
COPY requirements.txt .

# Install Python dependencies
RUN pip install --no-cache-dir -r requirements.txt

# Install Playwright browsers (Chromium)
RUN playwright install chromium

# Install Redis and Flask-Session for server-side session management
RUN pip install --no-cache-dir redis Flask-Session

# Copy the rest of the application
COPY . /app

# var 디렉토리 및 하위 디렉토리 생성 및 권한 설정
RUN mkdir -p /app/var/{captures,screenshots,optimization_images,pdf_reports,site_resources,logs} && \
    chmod -R 755 /app/var

# Docker 스크립트에 실행 권한 부여
RUN chmod +x /app/scripts/docker/*.sh

# Compile translation files (.po -> .mo) for production
RUN python -c "import sys; sys.path.append('/app'); from scripts.i18n.compile_translations import compile_all; compile_all()"

# 모델 파일은 프로젝트에 직접 포함되므로 COPY로 자동 복사됨
# 모델 파일이 없는 경우에만 경고 (개발자가 수동으로 다운로드 필요)
RUN if [ ! -f "/app/ecoweb/app/Image_Classification/image_classifier_model_7.h5" ]; then \
        echo "WARNING: Model file not found. Please download it manually:"; \
        echo "  python ecoweb/app/Image_Classification/download_image_model.py"; \
        echo "  or visit: https://drive.google.com/uc?id=1CZPDUofij-NyKmBN21FsntZs2KbgVWeO"; \
    else \
        echo "Model file found, ready to use."; \
    fi

# Expose port
EXPOSE 5000

# Set environment variables
ENV FLASK_APP=/app/ecoweb/run.py
ENV FLASK_ENV=production
ENV REDIS_HOST=redis
ENV REDIS_PORT=6379
ENV SESSION_COOKIE_SECURE=False

# Command to run the application
# 8GB 서버 최적화: 워커 3개, 쓰레드 4개로 설정 (총 12개 동시 HTTP 요청 처리)
# 메모리 효율성과 성능의 균형을 맞춘 설정
CMD ["gunicorn", "--chdir", "ecoweb", "--bind", "0.0.0.0:5000", "--worker-class", "gthread", "--workers", "3", "--threads", "4", "--timeout", "300", "--max-requests", "1000", "--max-requests-jitter", "50", "--log-level", "info", "--access-logfile", "-", "--error-logfile", "-", "run:app"]
