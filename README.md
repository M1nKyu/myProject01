<div align="center">
  <img src="github-assets/image/ecarbon-logo-01.png" alt="eCarbon Logo" width="400">
</div>


> **📌 레포지토리 안내**  
> [원본 프로젝트](https://github.com/CarbonAra-CBA/ecoweb)는 private 팀 프로젝트로, 제3자가 접근할 수 없어 확인이 불가능합니다. 따라서 본인이 구현한 부분만 선별하여 복사하여 정리한 레포지토리입니다.  
> 본 레포지토리에는 본인이 담당한 코드와 작업 내역만 포함되어 있으며, 총 871개 커밋 중 654개(약 75%)를 담당했습니다.

# eCarbon - 웹사이트 탄소 배출량 분석 플랫폼

## 📋 프로젝트 소개

AI 기반 웹사이트 디지털 탄소 측정 플랫폼으로, 공공기관 및 기업 웹사이트의 탄소 배출량을 분석하고 최적화 방안을 제안합니다. 웹사이트에서 URL 입력만으로 탄소 배출량, 개선 방향, W3C 웹 지속가능성 가이드라인 준수 여부를 직관적인 UI로 제공합니다. ([소개 영상](https://blog-minkyu.netlify.app/assets/ecarbon-new/%EC%86%8C%EA%B0%9C.mp4) / [시연 영상](https://blog-minkyu.netlify.app/assets/ecarbon-new/%EC%8B%9C%EC%97%B01.mp4))

- **기간**: 2025년 2월 ~ 2025년 12월 (11개월)
- **인원**: 5인 (컴공 3, 미디어커뮤니케이션 1, 산업디자인 1)
- **역할**: 풀스택 개발 및 DevOps
  - 프론트엔드, 백엔드 개발
  - Figma UI/UX 디자인의 웹 구현 (HTML/CSS)
  - 서버 인프라 구축 및 배포 (KT Cloud 사용)
  - 서비스 런칭 후 지속적인 운영·유지보수 및 기능 개선

## 📁 프로젝트 아키텍처 및 디렉토리 구조

![프로젝트 아키텍처](github-assets/image/project-architecture.jpg)

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


## 🎯 구현 내용

### 1. 플랫폼 웹사이트 UI/UX 개편
Figma를 사용하여 산업디자인학과 팀원의 디자인을 HTML+CSS 코드로 구현하여 각 페이지의 UI/UX를 재설계하고, 반응형 디자인을 적용하여 다양한 화면에서 최적화된 사용자 경험을 제공하도록 개선

**관련 코드:**
- [`ecoweb/ecoweb/app/templates/`](ecoweb/ecoweb/app/templates/) - HTML 템플릿
- [`ecoweb/ecoweb/app/static/css/`](ecoweb/ecoweb/app/static/css/) - 스타일시트
- [`ecoweb/ecoweb/app/static/js/`](ecoweb/ecoweb/app/static/js/) - JavaScript
- [`ecoweb/ecoweb/app/blueprints/main.py`](ecoweb/ecoweb/app/blueprints/main.py) - 메인 페이지 라우팅

### 2. 다국어 지원 시스템
한국어, 영어, 일본어, 중국어 4개 언어를 지원하는 다국어 시스템을 구축하고, IP 기반 GeoIP 언어 자동 감지 기능을 통해 사용자의 IP 주소를 기반으로 국가를 판별하여 해당 국가에 맞는 언어를 자동 설정

**관련 코드:**
- [`ecoweb/ecoweb/app/utils/i18n.py`](ecoweb/ecoweb/app/utils/i18n.py) - 다국어 유틸리티
- [`ecoweb/ecoweb/app/blueprints/language.py`](ecoweb/ecoweb/app/blueprints/language.py) - 언어 전환 라우팅
- [`ecoweb/ecoweb/app/translations/`](ecoweb/ecoweb/app/translations/) - Flask-Babel 번역 파일
- [`ecoweb/ecoweb/app/static/translations/`](ecoweb/ecoweb/app/static/translations/) - 클라이언트 사이드 번역 파일

### 3. 웹사이트 캡처 기능
사용자가 입력한 URL의 웹사이트를 캡처하고, WebP 또는 SVG로 변환해야 할 대상 이미지 영역을 빨간색으로 하이라이트하여 표시함. 사용자는 이미지가 최적화 대상인지 한눈에 파악할 수 있음

**관련 코드:**
- [`ecoweb/ecoweb/app/services/capture/`](ecoweb/ecoweb/app/services/capture/) - 웹사이트 캡처 서비스
- [`ecoweb/ecoweb/app/utils/async_website_capture.py`](ecoweb/ecoweb/app/utils/async_website_capture.py) - 비동기 웹사이트 캡처
- [`ecoweb/ecoweb/app/utils/website_capture.py`](ecoweb/ecoweb/app/utils/website_capture.py) - 웹사이트 캡처 유틸리티

### 4. PDF 리포트 생성 시스템
Playwright 기반 HTML/CSS 렌더링 방식으로 고품질 PDF 레포트를 생성하는 시스템을 구축하고, Celery 백그라운드 작업으로 비동기 PDF 생성을 구현하여 사용자가 리포트 생성 중에도 다른 서비스를 이용할 수 있도록 구현

**관련 코드:**
- [`ecoweb/ecoweb/app/blueprints/pdf_report.py`](ecoweb/ecoweb/app/blueprints/pdf_report.py) - PDF 리포트 라우팅
- [`ecoweb/ecoweb/app/services/report/`](ecoweb/ecoweb/app/services/report/) - PDF 리포트 생성 서비스
- [`ecoweb/ecoweb/app/services/playwright_pdf_generator.py`](ecoweb/ecoweb/app/services/playwright_pdf_generator.py) - Playwright PDF 생성기
- [`ecoweb/ecoweb/app/services/pdf_report_generator.py`](ecoweb/ecoweb/app/services/pdf_report_generator.py) - PDF 리포트 생성 로직

### 5. Google OAuth2.0 인증 시스템
Google OAuth 2.0 로그인을 구현해 Google 계정으로 간편하게 회원가입 및 로그인할 수 있도록 하고, 비밀번호 표시/숨김·아이디 기억 기능을 포함한 로그인 UI를 개선했으며, Redis 기반 세션 관리로 다중 서버 환경에서도 안정적으로 동작하는 인증 구조를 구축

**관련 코드:**
- [`ecoweb/ecoweb/app/blueprints/main.py`](ecoweb/ecoweb/app/blueprints/main.py) - 인증 라우팅
- [`ecoweb/ecoweb/app/templates/pages/auth/`](ecoweb/ecoweb/app/templates/pages/auth/) - 로그인/회원가입 템플릿

### 6. 설문조사 시스템
사용자 피드백 수집을 위해 설문조사 시스템을 구축하여 사용자의 의견을 수집하며, 뉴스레터 구독 기능을 추가하여 최신 소식을 전달할 수 있는 채널을 확보하고, 수집된 데이터를 서비스 개선, 사용자 니즈 파악, 마케팅 전략 수립 등 다양한 목적으로 활용할 수 있도록 함

**관련 코드:**
- [`ecoweb/ecoweb/app/blueprints/survey.py`](ecoweb/ecoweb/app/blueprints/survey.py) - 설문조사 라우팅
- [`ecoweb/ecoweb/app/templates/includes/survey.html`](ecoweb/ecoweb/app/templates/includes/survey.html) - 설문조사 템플릿

### 7. 배포 및 인프라 설정
docker-compose를 개발, 배포 두 버전으로 분리하여 개발 유연성과 프로덕션 환경의 안정성을 확보하고, Nginx와 Gunicorn을 적용해 도메인·SSL·보안 설정을 포함한 안정적인 프로덕션 배포 환경을 구축

**관련 코드:**
- [`ecoweb/docker-compose.dev.yml`](ecoweb/docker-compose.dev.yml) - 개발 환경 Docker Compose
- [`ecoweb/docker-compose.prod.yml`](ecoweb/docker-compose.prod.yml) - 프로덕션 환경 Docker Compose
- [`ecoweb/Dockerfile`](ecoweb/Dockerfile) - Docker 이미지 빌드
- [`ecoweb/gunicorn_config.py`](ecoweb/gunicorn_config.py) - Gunicorn 설정
- [`ecoweb/nginx/`](ecoweb/nginx/) - Nginx 설정 파일
- [`ecoweb/celery_worker.py`](ecoweb/celery_worker.py) - Celery 워커 설정


### 8. 데이터 아키텍처 개선
세션 기반에서 MongoDB 중심 영구 저장 방식으로 전환하여 데이터 지속성을 확보하고, task_id 기반 데이터 조회 시스템을 구축하여 분석 결과를 효율적으로 관리하며, MongoDB 쿼리 최적화를 통해 중복 쿼리를 5회에서 2회로 감소시키고 인덱싱 최적화 및 데이터 정규화를 수행

**관련 코드:**
- [`ecoweb/ecoweb/app/database.py`](ecoweb/ecoweb/app/database.py) - MongoDB 데이터베이스 연결
- [`ecoweb/ecoweb/app/async_database.py`](ecoweb/ecoweb/app/async_database.py) - 비동기 데이터베이스 작업
- [`ecoweb/ecoweb/app/tasks.py`](ecoweb/ecoweb/app/tasks.py) - Celery 태스크 및 데이터 처리

### 9. 이미지 최적화
PNG 이미지를 WebP 형식으로 변환하여 11.07 MB에서 6.74 MB로 39% 크기 절감을 달성하고, 이미지 캐싱 시스템을 구현하여 중복 다운로드를 방지하며, 이미지 최적화 페이지 UI를 개선하여 Before/After 비교 기능을 제공

**관련 코드:**
- [`ecoweb/ecoweb/app/services/optimization/images.py`](ecoweb/ecoweb/app/services/optimization/images.py) - 이미지 최적화 서비스
- [`ecoweb/ecoweb/app/utils/image_cache.py`](ecoweb/ecoweb/app/utils/image_cache.py) - 이미지 캐싱 시스템
- [`ecoweb/ecoweb/app/Image_Classification/`](ecoweb/ecoweb/app/Image_Classification/) - 이미지 분류 모델
- [`ecoweb/scripts/convert_static_images_to_webp.py`](ecoweb/scripts/convert_static_images_to_webp.py) - WebP 변환 스크립트

### 10. 사용자 이벤트 로깅 시스템
페이지 뷰 로깅 및 사용자 이벤트 추적 시스템을 구현하여 사용자 행동을 분석하고, 버튼 클릭, 링크 클릭, 폼 제출 등 상세 이벤트를 추적하며, Google Analytics 통합을 통해 데이터 기반 의사결정을 지원

**관련 코드:**
- [`ecoweb/ecoweb/app/utils/event_logger.py`](ecoweb/ecoweb/app/utils/event_logger.py) - 이벤트 로깅 유틸리티
- [`ecoweb/ecoweb/app/utils/logging_config.py`](ecoweb/ecoweb/app/utils/logging_config.py) - 로깅 설정
- [`ecoweb/ecoweb/app/blueprints/main.py`](ecoweb/ecoweb/app/blueprints/main.py) - 페이지 뷰 로깅 통합

## 🔧 문제 해결

### 1. Celery 비동기 처리 도입
초기 시스템은 Flask 라우트에서 직접 웹사이트 분석을 실행하는 동기 처리 방식을 사용했습니다. 분석 작업이 서버를 완전히 블로킹하여 다른 사용자 요청도 처리할 수 없었고, 동시 접속 사용자가 많을 때 대기 시간이 심각하게 증가했습니다. 이를 해결하기 위해 Celery 기반 비동기 작업 처리 아키텍처를 도입하고, Redis를 메시지 브로커로 사용하여 작업 큐를 구성했습니다. 작업 상태를 실시간으로 조회하는 폴링 시스템을 구현하고, 로딩 페이지에서 진행 상황을 시각적으로 표시하도록 했습니다. 결과적으로 동시 처리 능력이 크게 향상되었고, 평균 응답 시간이 개선되었습니다.

**관련 코드:**
- [`ecoweb/ecoweb/app/tasks.py`](ecoweb/ecoweb/app/tasks.py) - Celery 태스크 정의
- [`ecoweb/celery_worker.py`](ecoweb/celery_worker.py) - Celery 워커 설정
- [`ecoweb/ecoweb/app/blueprints/main.py`](ecoweb/ecoweb/app/blueprints/main.py) - 비동기 작업 처리 로직

### 2. 프로젝트 디렉토리 구조 최적화
프로젝트 초기에는 심각한 구조적 비일관성 문제가 있었습니다. 템플릿 파일이 여러 디렉터리에 분산되어 있었고, 중복 파일이 존재했으며, 런타임 데이터와 정적 파일이 혼재되어 있어 파일을 찾기 어려웠고 유지보수가 어려웠습니다. 이를 해결하기 위해 디렉터리 구조 재정비, 레거시·중복 코드 제거, 정적 리소스 및 UI 구조 통합, 컴포넌트 기반 설계 도입을 통해 가독성과 재사용성, 유지보수성을 전반적으로 개선했습니다.

**관련 코드:**
- [`ecoweb/ecoweb/app/`](ecoweb/ecoweb/app/) - 전체 애플리케이션 구조
- [`ecoweb/ecoweb/app/blueprints/`](ecoweb/ecoweb/app/blueprints/) - 블루프린트 구조
- [`ecoweb/ecoweb/app/services/`](ecoweb/ecoweb/app/services/) - 서비스 레이어 구조
- [`ecoweb/ecoweb/app/utils/`](ecoweb/ecoweb/app/utils/) - 유틸리티 함수

### 3. 캡처 기능: Selenium → Playwright 전환
Selenium 기반 캡처 로직은 async로 선언되어 있었지만 내부가 동기 블로킹 API로 구성되어 실제로는 동기 방식으로 동작하는 문제가 있었습니다. 이를 해결하기 위해 Playwright async API로 전환해 완전 비동기·논블로킹 구조를 구현함으로써 Worker 블로킹을 제거하고 동시 처리량을 크게 향상시켰습니다.

**관련 코드:**
- [`ecoweb/ecoweb/app/utils/async_website_capture.py`](ecoweb/ecoweb/app/utils/async_website_capture.py) - 비동기 웹사이트 캡처
- [`ecoweb/ecoweb/app/services/capture/`](ecoweb/ecoweb/app/services/capture/) - 웹사이트 캡처 서비스


### 4. SEO 최적화 구현
기존 웹사이트는 검색 엔진 노출을 고려한 구조가 충분히 구현되지 않아, 웹사이트의 정보가 검색 엔진에 제대로 전달되지 않았고 그 결과 검색 결과에서 불리한 위치에 머무르는 문제가 있었습니다. 이를 해결하기 위해 검색 엔진이 웹페이지를 바로 이해할 수 있도록 구조를 개선하고, 페이지별로 고유한 정보를 제공하도록 최적화했습니다. 그 결과 Lighthouse SEO 평가에서 100점을 달성하여 웹사이트의 검색 노출도와 접근성을 크게 향상시켰습니다.

**관련 코드:**
- [`ecoweb/ecoweb/app/blueprints/seo.py`](ecoweb/ecoweb/app/blueprints/seo.py) - SEO 라우팅 (Sitemap, Robots.txt)
- [`ecoweb/ecoweb/app/utils/seo_helpers.py`](ecoweb/ecoweb/app/utils/seo_helpers.py) - SEO 헬퍼 함수
- [`ecoweb/ecoweb/app/utils/structured_data.py`](ecoweb/ecoweb/app/utils/structured_data.py) - 구조화 데이터 생성


## 📊 주요 성과

- ✅ **동시 처리 능력 4배 향상**: 5개 → 20개 작업 동시 처리
- ✅ **이미지 최적화**: PNG → WebP 변환으로 39% 크기 절감 (11.07 MB → 6.74 MB)
- ✅ **MongoDB 쿼리 최적화**: 중복 쿼리 5회 → 2회로 감소
- ✅ **Lighthouse SEO 점수**: 100점 달성
- ✅ **다국어 지원**: 4개 언어 (한국어, 영어, 일본어, 중국어)
- ✅ **반응형 디자인**: 모든 디바이스 완벽 지원

## 📸 스크린샷

### 메인 페이지
![메인 페이지 상단](github-assets/image/Main-top.jpg)
![메인 페이지 하단](github-assets/image/Main-footer.png)
![메인 페이지 모바일](github-assets/image/Main-responsive-phone.png)
![메인 페이지 태블릿](github-assets/image/Main-responsive-tablet.png)

### 통합 분석 페이지
![탄소 배출량 계산 상단](github-assets/image/carbon-top.jpg)
![탄소 배출량 계산 하단](github-assets/image/carbon-bottom.png)

### 코드 분석 페이지
![코드 분석 상단](github-assets/image/code-top.jpg)
![코드 분석 중간](github-assets/image/code-middle.png)
![코드 분석 하단](github-assets/image/code-bottom.jpg)

### 이미지 최적화 페이지
![이미지 최적화 상단](github-assets/image/Image-top.png)
![이미지 캡처](github-assets/image/Image-Capture.png)
![이미지 최적화 하단](github-assets/image/Image-bottom.png)

### 지속가능성 가이드라인 페이지
![지속가능성 분석 상단](github-assets/image/sustain-top.jpg)
![지속가능성 모달](github-assets/image/sustain-modal.jpg)
![지속가능성 분석 하단](github-assets/image/sustain-bottom.png)

### 정밀 분석 페이지
![상세 분석 상단](github-assets/image/detail-top.jpg)
![상세 분석 하단](github-assets/image/detail-bottom.jpg)

### 로딩 페이지
![로딩 중](github-assets/image/loading-01.jpg)
![로딩 완료](github-assets/image/loading-complete.jpg)

### 로그인 페이지
![로그인 페이지](github-assets/image/Login.png)

### 설문조사
![설문조사](github-assets/image/survey.png)

### PDF 리포트
![PDF 리포트 전체](github-assets/image/report-all.jpg)
![PDF 리포트 생성 플로우](github-assets/image/report-flow.jpg)

### 다국어 지원 시스템
![다국어 지원](github-assets/image/i18n.jpg)
![다국어 지원 플로우](github-assets/image/i18n-flow.jpg)

### Celery 비동기 처리
![Celery 도입 전](github-assets/image/celery-before.jpg)
![Celery 도입 후](github-assets/image/celery-after.jpg)

### 크롤링 아키텍처
![크롤링 아키텍처](github-assets/image/crawling-architecture.jpg)

### Figma 디자인
![Figma 디자인](github-assets/image/figma.png)

### 구버전 UI (Before)
![구버전 상세 분석](github-assets/image/old-detail.png)
![구버전 탄소 배출량](github-assets/image/old-emission.png)
![구버전 가이드](github-assets/image/old-guide.png)
![구버전 이미지 최적화](github-assets/image/old-image.png)
