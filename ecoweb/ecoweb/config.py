# debug mode
import base64
import os
from redis import Redis

# log 정도 설정

BASE_DIR = os.path.dirname(__file__)
APP_DIR = os.path.join(BASE_DIR, 'app')
VAR_DIR = os.path.join(os.path.dirname(BASE_DIR), 'var')

class Config:
    # 런타임 데이터 디렉터리 경로
    VAR_DIR = VAR_DIR
    CAPTURE_FOLDER = os.path.join(VAR_DIR, 'captures')
    OPTIMIZATION_IMAGES_FOLDER = os.path.join(VAR_DIR, 'optimization_images')
    PDF_REPORT_FOLDER = os.path.join(VAR_DIR, 'pdf_reports')
    SITE_RESOURCES_FOLDER = os.path.join(VAR_DIR, 'site_resources')
    
    # 디렉터리 생성
    for folder in [CAPTURE_FOLDER, OPTIMIZATION_IMAGES_FOLDER, PDF_REPORT_FOLDER, SITE_RESOURCES_FOLDER]:
        os.makedirs(folder, exist_ok=True)
    # mongodb config
    MONGO_URI = os.getenv('MONGODB_URI', 'mongodb://USERNAME:PASSWORD@HOST:PORT/'
        CELERY_RESULT_BACKEND = f'redis://:{REDIS_PASSWORD}@{REDIS_HOST}:{REDIS_PORT}/2'
    else:
        CELERY_BROKER_URL = f'redis://{REDIS_HOST}:{REDIS_PORT}/1'
        CELERY_RESULT_BACKEND = f'redis://{REDIS_HOST}:{REDIS_PORT}/2'
    # Phase 1: 동시 실행 임계값 증가 (5 -> 20)
    # Worker 2개 × 동시성 10 = 최대 20개 작업 동시 처리 가능
    CELERY_QUEUE_THRESHOLD = 20  # 동시 실행 가능한 최대 작업 수

    # Google OAuth 2.0 설정
    GOOGLE_CLIENT_ID = os.getenv('GOOGLE_CLIENT_ID')
    GOOGLE_CLIENT_SECRET = os.getenv('GOOGLE_CLIENT_SECRET')
    GOOGLE_DISCOVERY_URL = "https://accounts.google.com/.well-known/openid_connect_configuration"
    
    # OAuth 리디렉션 설정 (프로덕션/개발 환경 자동 감지)
    FLASK_ENV = os.getenv('FLASK_ENV', 'development')
    if FLASK_ENV == 'production':
        # 프로덕션 환경: HTTPS 사용
        OAUTH_REDIRECT_PROTOCOL = 'https'
        SERVER_NAME = os.getenv('SERVER_NAME', 'example.com')  # 도메인 이름 사용 (IP 대신)
    else:
        # 개발 환경: HTTP 사용
        OAUTH_REDIRECT_PROTOCOL = 'http'
        SERVER_NAME = os.getenv('SERVER_NAME', 'localhost:5000')
    
    # 이미지 캐시 설정
    IMG_CACHE_TTL_DAYS = int(os.getenv('IMG_CACHE_TTL_DAYS', '7'))  # 기본 7일
    IMG_CACHE_ENABLED = os.getenv('IMG_CACHE_ENABLED', 'true').lower() == 'true'
    
    # 리소스 다운로드 설정 (디렉토리 구조 생성용)
    ENABLE_RESOURCE_DOWNLOAD = os.getenv('ENABLE_RESOURCE_DOWNLOAD', 'false').lower() == 'true'
    
    # 이벤트 로깅 설정
    # 프로덕션 환경에서는 기본적으로 활성화, 로컬/개발 환경에서는 비활성화
    # 개발 시 임시 활성화: EVENT_LOGGING_FORCE_ENABLE=true 환경 변수 설정
    EVENT_LOGGING_FORCE_ENABLE = os.getenv('EVENT_LOGGING_FORCE_ENABLE', 'False').lower() == 'true'
    ENABLE_EVENT_LOGGING = (
        FLASK_ENV == 'production' or 
        EVENT_LOGGING_FORCE_ENABLE
    )