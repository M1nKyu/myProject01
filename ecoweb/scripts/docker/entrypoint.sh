#!/bin/bash
# Docker 컨테이너 진입점 스크립트
# var 디렉토리 권한 설정 및 초기화

set -e

# var 디렉토리 및 하위 디렉토리 생성 및 권한 설정
mkdir -p /app/var/{captures,optimization_images,pdf_reports,site_resources,logs}
chmod -R 755 /app/var

# 로그 디렉토리 권한 설정
chmod -R 755 /app/var/logs

echo "Directory permissions set successfully"

# 원래 명령어 실행
exec "$@"

