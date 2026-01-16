#!/bin/bash
# Ollama 모델 초기화 스크립트
# 사용 모델: orca-mini (코드에서 사용 중)
# 이 스크립트는 Ollama 컨테이너 내부에서 실행되거나 별도 init 컨테이너로 실행 가능

set -e

OLLAMA_HOST=${OLLAMA_HOST:-ollama}
OLLAMA_PORT=${OLLAMA_PORT:-11434}
OLLAMA_URL="http://${OLLAMA_HOST}:${OLLAMA_PORT}"
MODEL_NAME="orca-mini"

echo "Waiting for Ollama to be ready at ${OLLAMA_URL}..."

# Ollama가 준비될 때까지 대기
max_attempts=30
attempt=0
while [ $attempt -lt $max_attempts ]; do
  if curl -f -s "${OLLAMA_URL}/api/tags" > /dev/null 2>&1; then
    echo "Ollama is ready!"
    break
  fi
  attempt=$((attempt + 1))
  echo "Attempt ${attempt}/${max_attempts}: Ollama is not ready yet. Waiting..."
  sleep 2
done

if [ $attempt -eq $max_attempts ]; then
  echo "ERROR: Ollama did not become ready after ${max_attempts} attempts"
  exit 1
fi

echo "Checking for ${MODEL_NAME} model..."

# 모델 목록 확인
if curl -s "${OLLAMA_URL}/api/tags" | grep -q "\"name\":\"${MODEL_NAME}\""; then
  echo "${MODEL_NAME} model already exists"
else
  echo "Downloading ${MODEL_NAME} model..."
  curl -X POST "${OLLAMA_URL}/api/pull" \
    -H "Content-Type: application/json" \
    -d "{\"name\":\"${MODEL_NAME}\"}"
  
  # 다운로드 완료 확인
  if curl -s "${OLLAMA_URL}/api/tags" | grep -q "\"name\":\"${MODEL_NAME}\""; then
    echo "${MODEL_NAME} model downloaded successfully"
  else
    echo "WARNING: ${MODEL_NAME} model download may have failed"
  fi
fi

echo "Ollama initialization completed"
