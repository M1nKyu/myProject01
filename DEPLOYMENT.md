# 배포 가이드

## 🚀 배포 옵션

### 1. Docker Compose (권장)

#### 개발 환경
```bash
docker-compose -f docker-compose.dev.yml up -d
```

#### 프로덕션 환경
```bash
docker-compose -f docker-compose.prod.yml up -d
```

### 2. 수동 배포

#### 사전 요구사항
- Python 3.8+
- MongoDB
- Redis
- Nginx (선택)

#### 설치
```bash
# 가상 환경 생성
python -m venv venv
source venv/bin/activate  # Windows: venv\Scripts\activate

# 의존성 설치
pip install -r requirements.txt

# 환경 변수 설정
cp .env.example .env
# .env 파일 수정

# 애플리케이션 실행
python ecoweb/run.py
```

## 📝 환경 변수

필수 환경 변수:
- `MONGODB_URI`: MongoDB 연결 문자열
- `SECRET_KEY`: Flask 세션 시크릿 키
- `REDIS_HOST`, `REDIS_PORT`: Redis 설정
- `GOOGLE_CLIENT_ID`, `GOOGLE_CLIENT_SECRET`: Google OAuth 인증 정보

## 🔒 보안 고려사항

- 환경 변수를 통한 민감한 정보 관리
- HTTPS 사용 (프로덕션)
- 세션 쿠키 보안 설정
- API 키 보호

## 📊 모니터링

- Celery 작업 모니터링
- MongoDB 성능 모니터링
- Redis 메모리 사용량 모니터링
- Nginx 액세스 로그
