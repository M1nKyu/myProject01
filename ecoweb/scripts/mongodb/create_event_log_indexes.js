/**
 * user_events 컬렉션 인덱스 생성 스크립트
 * 
 * 사용법:
 *   mongo ecoweb create_event_log_indexes.js
 * 또는 MongoDB Compass에서 직접 실행
 */

// 데이터베이스 선택
db = db.getSiblingDB('ecoweb');

// user_events 컬렉션 인덱스 생성
print('Creating indexes for user_events collection...');

// 1. timestamp 인덱스 (내림차순 - 최신 데이터 조회 최적화)
db.user_events.createIndex(
    { timestamp: -1 },
    { name: 'idx_timestamp_desc' }
);
print('✓ Created index: timestamp (descending)');

// 2. event_type + timestamp 복합 인덱스 (이벤트 타입별 시간대별 조회)
db.user_events.createIndex(
    { event_type: 1, timestamp: -1 },
    { name: 'idx_event_type_timestamp' }
);
print('✓ Created index: event_type + timestamp');

// 3. user_id + timestamp 복합 인덱스 (사용자별 이벤트 조회)
db.user_events.createIndex(
    { user_id: 1, timestamp: -1 },
    { name: 'idx_user_id_timestamp' }
);
print('✓ Created index: user_id + timestamp');

// 4. session_id + timestamp 복합 인덱스 (세션별 이벤트 조회)
db.user_events.createIndex(
    { session_id: 1, timestamp: -1 },
    { name: 'idx_session_id_timestamp' }
);
print('✓ Created index: session_id + timestamp');

// 5. event_category + timestamp 복합 인덱스 (카테고리별 이벤트 조회)
db.user_events.createIndex(
    { event_category: 1, timestamp: -1 },
    { name: 'idx_event_category_timestamp' }
);
print('✓ Created index: event_category + timestamp');

// 인덱스 목록 확인
print('\nIndexes created:');
db.user_events.getIndexes().forEach(function(index) {
    print('  - ' + index.name + ': ' + JSON.stringify(index.key));
});

print('\n✓ All indexes created successfully!');

