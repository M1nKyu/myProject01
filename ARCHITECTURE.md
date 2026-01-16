# 시스템 아키텍처

## 전체 아키텍처

```
┌─────────────┐
│   Client    │
│  (Browser)  │
└──────┬──────┘
       │
       │ HTTP/HTTPS
       │
┌──────▼─────────────────────────────────────┐
│              Nginx                          │
│         (Reverse Proxy)                     │
└──────┬──────────────────────────────────────┘
       │
       ├──────────────┬──────────────┐
       │              │              │
┌──────▼──────┐  ┌───▼──────┐  ┌───▼──────┐
│   Flask     │  │  Celery   │  │  Redis   │
│   (Gunicorn)│  │  Worker   │  │  Cache   │
└──────┬──────┘  └───────────┘  └──────────┘
       │
       │
┌──────▼──────┐
│   MongoDB   │
│  Database   │
└─────────────┘
```

## 주요 컴포넌트

### 1. Frontend
- **HTML/CSS/JavaScript**: 사용자 인터페이스
- **Chart.js**: 데이터 시각화
- **i18n.js**: 클라이언트 사이드 다국어 지원

### 2. Backend
- **Flask**: 웹 프레임워크
- **Gunicorn**: WSGI HTTP 서버
- **Celery**: 비동기 작업 처리
- **Redis**: 세션 관리 및 캐싱

### 3. Database
- **MongoDB**: 메인 데이터베이스
  - 사용자 데이터
  - 분석 결과
  - 이벤트 로그

### 4. External Services
- **Google Lighthouse**: 웹사이트 성능 분석
- **Playwright**: 웹사이트 캡처 및 PDF 생성
- **Google OAuth 2.0**: 사용자 인증
- **Google Analytics**: 사용자 행동 분석

## 데이터 흐름

### 분석 요청 처리
```
1. 사용자 URL 입력
   ↓
2. Flask 라우터 (main.py)
   ↓
3. Celery 작업 큐에 추가
   ↓
4. Celery Worker가 Lighthouse 분석 실행
   ↓
5. MongoDB에 결과 저장
   ↓
6. 사용자에게 결과 반환
```

### PDF 리포트 생성
```
1. 사용자 PDF 요청
   ↓
2. Celery 작업 큐에 추가
   ↓
3. Playwright로 HTML 렌더링
   ↓
4. PDF 생성
   ↓
5. 파일 시스템에 저장
   ↓
6. 사용자에게 다운로드 링크 제공
```

## 보안 고려사항

- 환경 변수를 통한 민감한 정보 관리
- Redis 세션 관리
- Google OAuth 2.0 인증
- HTTPS 통신 (프로덕션)

## 성능 최적화

- **이미지 캐싱**: 7일 TTL
- **MongoDB 인덱싱**: 복합 인덱스 활용
- **Celery 비동기 처리**: 동시 20개 작업 처리
- **Nginx 정적 파일 서빙**: 정적 파일 직접 서빙
