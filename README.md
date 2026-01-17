# 🌱 eCarbon - 웹사이트 탄소 배출량 분석 플랫폼

## 📋 프로젝트 소개

AI 기반 웹사이트 디지털 탄소 측정 플랫폼으로, 공공기관 및 기업 웹사이트의 탄소 배출량을 분석하고 최적화 방안을 제안합니다. 웹사이트에서 URL 입력만으로 탄소 배출량, 개선 방향, W3C 웹 지속가능성 가이드라인 준수 여부를 직관적인 UI로 제공합니다.


### ✨ 핵심 특징
- 🔍 **자동화된 분석**: URL 입력만으로 전체 분석 자동 수행
- 📊 **상세한 리포트**: 고품질 PDF 리포트 자동 생성
- 🌍 **다국어 지원**: 한국어, 영어, 일본어, 중국어 4개 언어 지원
- 🚀 **고성능**: Celery 기반 비동기 처리로 동시 20개 작업 처리
- 📱 **반응형 디자인**: 모바일, 태블릿, 데스크톱 완벽 지원



## 🛠 기술 스택

### Backend
- **Python 3.8+**: Flask 웹 프레임워크
- **MongoDB**: NoSQL 데이터베이스
- **Redis**: 세션 관리 및 캐싱
- **Celery**: 비동기 작업 처리
- **Gunicorn**: WSGI HTTP 서버
- **Playwright**: 웹사이트 캡처 및 PDF 생성

### Frontend
- **HTML5/CSS3**: 반응형 웹 디자인
- **JavaScript (ES6+)**: 동적 UI 구현
- **Chart.js**: 데이터 시각화
- **Jinja2**: 템플릿 엔진

### DevOps & Infrastructure
- **Docker & Docker Compose**: 컨테이너화
- **Nginx**: 리버스 프록시 및 정적 파일 서빙
- **GitHub Actions**: CI/CD 파이프라인

### Tools & Services
- **Google Lighthouse**: 웹사이트 성능 분석
- **Google OAuth 2.0**: 사용자 인증
- **Google Analytics**: 사용자 행동 분석
- **GeoIP**: IP 기반 언어 감지


## 📁 프로젝트 구조

```
ecoweb/
├── ecoweb/
│   ├── app/
│   │   ├── blueprints/          # Flask 블루프린트 (라우팅)
│   │   │   ├── main.py          # 메인 페이지 및 분석 페이지
│   │   │   ├── pdf_report.py    # PDF 리포트 생성
│   │   │   ├── seo.py           # SEO 최적화
│   │   │   ├── survey.py        # 설문조사
│   │   │   └── language.py      # 다국어 지원
│   │   ├── services/
│   │   │   ├── analysis/        # 탄소 배출량 분석
│   │   │   ├── capture/         # 웹사이트 캡처
│   │   │   ├── optimization/    # 최적화 서비스
│   │   │   └── report/          # PDF 리포트 생성
│   │   ├── static/
│   │   │   ├── css/             # 스타일시트
│   │   │   ├── js/              # JavaScript
│   │   │   ├── img/             # 이미지 리소스
│   │   │   └── translations/    # 다국어 번역 파일
│   │   ├── templates/           # HTML 템플릿
│   │   ├── utils/               # 유틸리티 함수
│   │   └── translations/        # Flask-Babel 번역 파일
│   ├── config.py                # 설정 파일
│   └── run.py                   # 애플리케이션 진입점
├── docker-compose.dev.yml       # 개발 환경 설정
├── docker-compose.prod.yml      # 프로덕션 환경 설정
├── Dockerfile                   # Docker 이미지 빌드
├── nginx/                       # Nginx 설정
└── requirements.txt             # Python 의존성
```


## 🎯 주요 기여 내용

본 프로젝트에서 **약 70%의 코드를 담당**하며, 다음과 같은 주요 기능을 구현했습니다:

### 1. 플랫폼 웹사이트 UI/UX 개편 (137개 커밋)
- 전체 페이지의 UI/UX 전면 재설계 및 반응형 디자인 적용 (모바일, 태블릿, 데스크톱)
- Figma 디자인을 HTML/CSS로 구현
- 사이드바, 헤더, 메인 페이지 등 모든 컴포넌트 재구현
- Flexbox와 Grid 레이아웃, 미디어 쿼리, clamp() 함수 활용

**관련 코드:**
- [`ecoweb/ecoweb/app/templates/`](ecoweb/ecoweb/app/templates/) - HTML 템플릿
- [`ecoweb/ecoweb/app/static/css/`](ecoweb/ecoweb/app/static/css/) - 스타일시트
- [`ecoweb/ecoweb/app/static/js/`](ecoweb/ecoweb/app/static/js/) - JavaScript
- [`ecoweb/ecoweb/app/blueprints/main.py`](ecoweb/ecoweb/app/blueprints/main.py) - 메인 페이지 라우팅

### 2. 다국어 지원 시스템 (i18n) (17개 커밋)
- 한국어, 영어, 일본어, 중국어 4개 언어 지원
- Flask-Babel 서버 사이드 렌더링 및 Custom i18n.js 클라이언트 사이드 번역
- IP 기반 GeoIP 언어 자동 감지 기능 구현
- Lazy loading 및 번역 파일 캐싱으로 초기 로딩 시간 75% 개선

**관련 코드:**
- [`ecoweb/ecoweb/app/utils/i18n.py`](ecoweb/ecoweb/app/utils/i18n.py) - 다국어 유틸리티
- [`ecoweb/ecoweb/app/blueprints/language.py`](ecoweb/ecoweb/app/blueprints/language.py) - 언어 전환 라우팅
- [`ecoweb/ecoweb/app/translations/`](ecoweb/ecoweb/app/translations/) - Flask-Babel 번역 파일
- [`ecoweb/ecoweb/app/static/translations/`](ecoweb/ecoweb/app/static/translations/) - 클라이언트 사이드 번역 파일

### 3. PDF 리포트 생성 시스템 (33개 커밋)
- Playwright 기반 17페이지 PDF 리포트 생성 (커버, 목차, 13개 콘텐츠 페이지, 요약, 뒷표지)
- Celery 배경 작업으로 비동기 PDF 생성
- Chart.js 통합 및 인라인 SVG 지원으로 데이터 시각화
- 매크로 기반 템플릿 시스템 및 동적 헤더 콘텐츠 구현

**관련 코드:**
- [`ecoweb/ecoweb/app/blueprints/pdf_report.py`](ecoweb/ecoweb/app/blueprints/pdf_report.py) - PDF 리포트 라우팅
- [`ecoweb/ecoweb/app/services/report/`](ecoweb/ecoweb/app/services/report/) - PDF 리포트 생성 서비스
- [`ecoweb/ecoweb/app/services/playwright_pdf_generator.py`](ecoweb/ecoweb/app/services/playwright_pdf_generator.py) - Playwright PDF 생성기
- [`ecoweb/ecoweb/app/services/pdf_report_generator.py`](ecoweb/ecoweb/app/services/pdf_report_generator.py) - PDF 리포트 생성 로직

### 4. SEO 최적화 (4개 커밋)
- SSR 기반 SEO 최적화 시스템 구현
- 동적 Sitemap.xml 및 Robots.txt 생성
- Open Graph 메타 태그 및 Schema.org JSON-LD 구조화 데이터 추가
- Lighthouse SEO 점수 100점 달성

**관련 코드:**
- [`ecoweb/ecoweb/app/blueprints/seo.py`](ecoweb/ecoweb/app/blueprints/seo.py) - SEO 라우팅 (Sitemap, Robots.txt)
- [`ecoweb/ecoweb/app/utils/seo_helpers.py`](ecoweb/ecoweb/app/utils/seo_helpers.py) - SEO 헬퍼 함수
- [`ecoweb/ecoweb/app/utils/structured_data.py`](ecoweb/ecoweb/app/utils/structured_data.py) - 구조화 데이터 생성

### 5. 데이터 아키텍처 개선 (36개 커밋)
- 세션 기반에서 MongoDB 중심 영구 저장 방식으로 전환
- task_id 기반 데이터 조회 시스템 구축
- MongoDB 쿼리 최적화 (중복 쿼리 5회 → 2회 감소)
- 인덱싱 최적화 및 데이터 정규화

**관련 코드:**
- [`ecoweb/ecoweb/app/database.py`](ecoweb/ecoweb/app/database.py) - MongoDB 데이터베이스 연결
- [`ecoweb/ecoweb/app/async_database.py`](ecoweb/ecoweb/app/async_database.py) - 비동기 데이터베이스 작업
- [`ecoweb/ecoweb/app/tasks.py`](ecoweb/ecoweb/app/tasks.py) - Celery 태스크 및 데이터 처리

### 6. 웹사이트 캡처 기능 (14개 커밋)
- Selenium에서 Playwright async로 전환하여 안정성 및 성능 개선
- 전체 페이지 스크린샷 및 호버 미리보기 모달 기능
- 이미지 최적화 대상 영역을 빨간색으로 하이라이트하는 스마트 기능

**관련 코드:**
- [`ecoweb/ecoweb/app/services/capture/`](ecoweb/ecoweb/app/services/capture/) - 웹사이트 캡처 서비스
- [`ecoweb/ecoweb/app/utils/async_website_capture.py`](ecoweb/ecoweb/app/utils/async_website_capture.py) - 비동기 웹사이트 캡처
- [`ecoweb/ecoweb/app/utils/website_capture.py`](ecoweb/ecoweb/app/utils/website_capture.py) - 웹사이트 캡처 유틸리티

### 7. 이미지 최적화 (64개 커밋)
- PNG → WebP 변환 (11.07 MB → 6.74 MB, 39% 절감)
- 이미지 캐싱 시스템 구현으로 중복 다운로드 방지
- 이미지 최적화 페이지 UI 개선 및 Before/After 비교 기능

**관련 코드:**
- [`ecoweb/ecoweb/app/services/optimization/images.py`](ecoweb/ecoweb/app/services/optimization/images.py) - 이미지 최적화 서비스
- [`ecoweb/ecoweb/app/utils/image_cache.py`](ecoweb/ecoweb/app/utils/image_cache.py) - 이미지 캐싱 시스템
- [`ecoweb/ecoweb/app/Image_Classification/`](ecoweb/ecoweb/app/Image_Classification/) - 이미지 분류 모델
- [`ecoweb/scripts/convert_static_images_to_webp.py`](ecoweb/scripts/convert_static_images_to_webp.py) - WebP 변환 스크립트

### 8. 사용자 이벤트 로깅 시스템 (24개 커밋)
- 페이지 뷰 로깅 및 사용자 이벤트 추적 시스템 구현
- 버튼 클릭, 링크 클릭, 폼 제출 등 상세 이벤트 추적
- Google Analytics 통합으로 데이터 기반 의사결정 지원

**관련 코드:**
- [`ecoweb/ecoweb/app/utils/event_logger.py`](ecoweb/ecoweb/app/utils/event_logger.py) - 이벤트 로깅 유틸리티
- [`ecoweb/ecoweb/app/utils/logging_config.py`](ecoweb/ecoweb/app/utils/logging_config.py) - 로깅 설정
- [`ecoweb/ecoweb/app/blueprints/main.py`](ecoweb/ecoweb/app/blueprints/main.py) - 페이지 뷰 로깅 통합

### 9. 배포 및 인프라 설정 (23개 커밋)
- Docker Compose 개발/프로덕션 환경 분리
- Gunicorn 설정 최적화 및 Flask 개발 서버 교체
- Nginx 리버스 프록시 설정 및 SSL 자동 갱신
- Celery 워커 설정 및 컨테이너 메모리 제한 최적화

**관련 코드:**
- [`ecoweb/docker-compose.dev.yml`](ecoweb/docker-compose.dev.yml) - 개발 환경 Docker Compose
- [`ecoweb/docker-compose.prod.yml`](ecoweb/docker-compose.prod.yml) - 프로덕션 환경 Docker Compose
- [`ecoweb/Dockerfile`](ecoweb/Dockerfile) - Docker 이미지 빌드
- [`ecoweb/gunicorn_config.py`](ecoweb/gunicorn_config.py) - Gunicorn 설정
- [`ecoweb/nginx/`](ecoweb/nginx/) - Nginx 설정 파일
- [`ecoweb/celery_worker.py`](ecoweb/celery_worker.py) - Celery 워커 설정

### 10. 코드 리팩토링 (133개 커밋)
- 프로젝트 디렉터리 구조 재구성 및 일관성 확보
- 정적 파일 디렉터리 통합 및 레거시 코드 제거
- 컴포넌트 기반 레이아웃 구조 도입
- 코드 가독성 및 유지보수성 향상

**관련 코드:**
- [`ecoweb/ecoweb/app/`](ecoweb/ecoweb/app/) - 전체 애플리케이션 구조
- [`ecoweb/ecoweb/app/blueprints/`](ecoweb/ecoweb/app/blueprints/) - 블루프린트 구조
- [`ecoweb/ecoweb/app/services/`](ecoweb/ecoweb/app/services/) - 서비스 레이어 구조
- [`ecoweb/ecoweb/app/utils/`](ecoweb/ecoweb/app/utils/) - 유틸리티 함수


## 📊 주요 성과

- ✅ **동시 처리 능력 4배 향상**: 5개 → 20개 작업 동시 처리
- ✅ **이미지 최적화**: PNG → WebP 변환으로 39% 크기 절감 (11.07 MB → 6.74 MB)
- ✅ **MongoDB 쿼리 최적화**: 중복 쿼리 5회 → 2회로 감소
- ✅ **Lighthouse SEO 점수**: 100점 달성
- ✅ **다국어 지원**: 4개 언어 (한국어, 영어, 일본어, 중국어)
- ✅ **반응형 디자인**: 모든 디바이스 완벽 지원

### 프로젝트 통계
- **총 커밋 수**: 654개
- **개발 기간**: 2025년 3월 ~ 2026년 1월 (약 10개월)



## 🚀 시작하기

### 사전 요구사항
- Python 3.8 이상
- Docker & Docker Compose
- MongoDB (또는 MongoDB Atlas)
- Redis

### 설치 방법

1. **저장소 클론**
```bash
git clone https://github.com/your-username/ecoweb-portfolio.git
cd ecoweb-portfolio/ecoweb
```

2. **환경 변수 설정**
```bash
cp .env.example .env
# .env 파일에 필요한 환경 변수 설정
```

3. **Docker Compose로 실행**
```bash
# 개발 환경
docker-compose -f docker-compose.dev.yml up -d

# 프로덕션 환경
docker-compose -f docker-compose.prod.yml up -d
```

4. **애플리케이션 접속**
```
http://localhost:5000 (개발 환경)
```

### 환경 변수

필수 환경 변수:
- `MONGODB_URI`: MongoDB 연결 문자열
- `SECRET_KEY`: Flask 세션 시크릿 키
- `REDIS_HOST`, `REDIS_PORT`: Redis 설정
- `GOOGLE_CLIENT_ID`, `GOOGLE_CLIENT_SECRET`: Google OAuth 인증 정보



## 📸 스크린샷

### 메인 페이지
- 반응형 디자인
- 탄소 배출량 분석 입력 폼
- Eco 웹사이트 소개

### 분석 결과 페이지
- 탄소 배출량 등급 표시
- 상세 분석 차트
- 최적화 제안

### PDF 리포트
- 17페이지 상세 리포트
- 데이터 시각화
- 최적화 방안 제시
