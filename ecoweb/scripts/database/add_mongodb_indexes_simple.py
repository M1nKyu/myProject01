#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
MongoDB 인덱스 추가 스크립트 (Flask 앱 컨텍스트 사용)

실행 방법:
    flask shell < add_mongodb_indexes_simple.py
또는
    python run_add_indexes.py
"""

# Flask 앱 생성 및 MongoDB 연결
from ecoweb.app import create_app
from ecoweb.app import db

app = create_app()

with app.app_context():
    mongo_db = db.get_db()
    collection = mongo_db.task_results

    print("=" * 80)
    print("MongoDB 인덱스 추가 시작")
    print("=" * 80)

    # [1] user_id + created_at 인덱스
    print("\n[1] user_id + created_at 인덱스 추가 중...")
    try:
        result1 = collection.create_index([
            ('user_id', 1),
            ('created_at', -1)
        ], name='idx_user_created')
        print(f"    ✓ 인덱스 생성 완료: {result1}")
    except Exception as e:
        print(f"    ⚠ 인덱스 이미 존재하거나 생성 실패: {e}")

    # [2] status + created_at 인덱스
    print("\n[2] status + created_at 인덱스 추가 중...")
    try:
        result2 = collection.create_index([
            ('status', 1),
            ('created_at', -1)
        ], name='idx_status_created')
        print(f"    ✓ 인덱스 생성 완료: {result2}")
    except Exception as e:
        print(f"    ⚠ 인덱스 이미 존재하거나 생성 실패: {e}")

    # [3] created_at 인덱스
    print("\n[3] created_at 인덱스 추가 중...")
    try:
        result3 = collection.create_index([
            ('created_at', -1)
        ], name='idx_created')
        print(f"    ✓ 인덱스 생성 완료: {result3}")
    except Exception as e:
        print(f"    ⚠ 인덱스 이미 존재하거나 생성 실패: {e}")

    # [4] completed_at 인덱스
    print("\n[4] completed_at 인덱스 추가 중...")
    try:
        result4 = collection.create_index([
            ('completed_at', -1)
        ], name='idx_completed')
        print(f"    ✓ 인덱스 생성 완료: {result4}")
    except Exception as e:
        print(f"    ⚠ 인덱스 이미 존재하거나 생성 실패: {e}")

    print("\n" + "=" * 80)
    print("✓ 인덱스 추가 작업 완료")
    print("=" * 80)

    # 인덱스 목록 확인
    print("\n현재 인덱스 목록:")
    for idx in collection.list_indexes():
        print(f"  - {idx['name']}: {idx.get('key', {})}")
