import os
import logging
import multiprocessing

# Gunicorn 서버 설정
bind = "0.0.0.0"
workers = multiprocessing.cpu_count() * 2 + 1
worker_class = "gevent"
timeout = 300
keepalive = 5

# 로깅 설정
loglevel = "warning"  # 경고 이상의 로그만 표시
accesslog = "-"  # 표준 출력으로 액세스 로그 전송
errorlog = "-"   # 표준 에러로 에러 로그 전송
access_log_format = '%(h)s [%(u)s] "%(r)s" %(s)s "%(f)s" "%(a)s" - %(L)s'

# 액세스 로그 형식 사용자 정의
# %(h)s: 원격 주소
# %(u)s: 사용자 이름 (있는 경우)
# %(r)s: 요청 라인
# %(s)s: 상태 코드
# %(f)s: 리퍼러
# %(a)s: 사용자 에이전트
# %(L)s: 요청 처리 시간 (ms)

def post_worker_init(worker):
    """워커 초기화 후 호출되는 함수"""
    # 불필요한 로그 비활성화
    logging.getLogger("gunicorn.error").setLevel(logging.WARNING)
    logging.getLogger("gunicorn.access").setLevel(logging.WARNING)

def worker_exit(server, worker):
    """워커 종료 시 호출되는 함수"""
    pass
