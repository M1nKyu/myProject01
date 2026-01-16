#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
MongoDB 인덱스 추가 스크립트 (Phase 1: Session-to-DB Refactoring)

이 스크립트는 task_results 컬렉션에 성능 최적화를 위한 인덱스를 추가합니다.

실행 방법:
    python add_mongodb_indexes.py
"""

import os
import sys
from pymongo import MongoClient, ASCENDING, DESCENDING

# MongoDB 연결 설정
def get_mongo_connection():
    """MongoDB 연결을 생성하고 반환합니다."""
    mongo_uri = os.getenv('MONGODB_URI', 'mongodb://localhost:27017/')
    client = MongoClient(mongo_uri)
    return client

def add_indexes():
    """task_results 컬렉션에 인덱스를 추가합니다."""
    try:
        client = get_mongo_connection()
        db = client.get_database()  # .env에서 지정된 DB 사용
        collection = db.task_results

        print("=" * 80)
        print("MongoDB 인덱스 추가 시작")
        print("=" * 80)

        # [1] user_id + created_at 인덱스 (사용자별 최근 작업 조회 최적화)
        print("\n[1] user_id + created_at 인덱스 추가 중...")
        result1 = collection.create_index([
            ('user_id', ASCENDING),
            ('created_at', DESCENDING)
        ], name='idx_user_created')
        print(f"    ✓ 인덱스 생성 완료: {result1}")

        # [2] status + created_at 인덱스 (상태별 작업 조회 최적화)
        print("\n[2] status + created_at 인덱스 추가 중...")
        result2 = collection.create_index([
            ('status', ASCENDING),
            ('created_at', DESCENDING)
        ], name='idx_status_created')
        print(f"    ✓ 인덱스 생성 완료: {result2}")

        # [3] created_at 인덱스 (시간순 정렬 최적화)
        print("\n[3] created_at 인덱스 추가 중...")
        result3 = collection.create_index([
            ('created_at', DESCENDING)
        ], name='idx_created')
        print(f"    ✓ 인덱스 생성 완료: {result3}")

        # [4] completed_at 인덱스 (완료 시간순 정렬 최적화)
        print("\n[4] completed_at 인덱스 추가 중...")
        result4 = collection.create_index([
            ('completed_at', DESCENDING)
        ], name='idx_completed')
        print(f"    ✓ 인덱스 생성 완료: {result4}")

        print("\n" + "=" * 80)
        print("✓ 모든 인덱스 추가 완료")
        print("=" * 80)

        # 인덱스 목록 확인
        print("\n현재 인덱스 목록:")
        for idx in collection.list_indexes():
            print(f"  - {idx['name']}: {idx.get('key', {})}")

        return True

    except Exception as e:
        print(f"\n✗ 오류 발생: {e}", file=sys.stderr)
        return False
    finally:
        if 'client' in locals():
            client.close()

if __name__ == '__main__':
    # .env 파일 로드 (python-dotenv 사용)
    try:
        from dotenv import load_dotenv
        load_dotenv()
        print("✓ .env 파일 로드 완료")
    except ImportError:
        print("⚠ python-dotenv가 설치되지 않았습니다. 환경 변수를 직접 설정해주세요.")

    success = add_indexes()
    sys.exit(0 if success else 1)
