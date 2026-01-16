import os
from flask import g
from pymongo import MongoClient
from pymongo.errors import ConnectionFailure, AutoReconnect, ServerSelectionTimeoutError

# --- 환경 변수 설정 (기존 로직 유지) ---
def set_default_env_vars():
    if 'MONGO_URI' not in os.environ:
        os.environ['MONGO_URI'] = 'mongodb+srv://USERNAME:PASSWORD@HOST/?retryWrites=true&w=majority'
    if 'MONGO_DB_NAME' not in os.environ:
        os.environ['MONGO_DB_NAME'] = 'ecoweb'

    default_env_vars = {
        'PINECONE_API_KEY': 'PINECONE_API_KEY_REMOVED',
        'INDEX_NAME': 'sustainable-webdesign-guidline',
        'LANGCHAIN_TRACING_V2': 'true',
        'LANGCHAIN_ENDPOINT': 'https://api.smith.langchain.com',
        'LANGCHAIN_API_KEY': 'LANGCHAIN_API_KEY_REMOVED',
        'LANGCHAIN_PROJECT': 'project-name'
    }
    for key, value in default_env_vars.items():
        os.environ.setdefault(key, value)

set_default_env_vars()

# --- 데이터베이스 연결 관리 ---

def get_db():
    """
    요청 컨텍스트(g)에 DB 연결을 가져오거나 생성합니다.
    MongoClient는 한 번만 생성되어 애플리케이션 전체에서 재사용됩니다.
    """
    if 'db_client' not in g:
        try:
            # MongoClient는 한 번만 생성되어야 하므로, g에 저장하지 않고
            # 모듈 수준이나 클래스 수준에서 관리해야 하지만, Flask의 g를 활용하여
            # 요청마다 연결을 확인하는 현재 구조를 유지하며 문제를 해결합니다.
            # 가장 좋은 방법은 Flask 앱 팩토리에서 client를 초기화하는 것입니다.
            # 여기서는 현재 구조를 최소한으로 변경합니다.
            if 'mongo_client' not in g:
                g.mongo_client = MongoClient(os.environ['MONGO_URI'])
                # 연결 테스트
                g.mongo_client.admin.command('ping')
        
            
            g.db = g.mongo_client[os.environ['MONGO_DB_NAME']]

        except (ConnectionFailure, AutoReconnect, ServerSelectionTimeoutError) as e:
            print(f"MongoDB 연결 실패: {e}")
            # g에서 실패한 클라이언트 제거 (다음 요청 시 재시도)
            g.pop('mongo_client', None)
            raise
        except Exception as e:
            print(f"DB 연결 중 오류 발생: {e}")
            # g에서 실패한 클라이언트 제거 (다음 요청 시 재시도)
            g.pop('mongo_client', None)
            raise
    return g.db

def close_db(e=None):
    """
    요청 컨텍스트가 종료될 때 호출되어 g에서 DB 관련 객체를 제거합니다.
    MongoClient는 닫지 않습니다.
    """
    g.pop('db', None)
    # mongo_client는 요청 간에 유지될 수 있도록 g에서 제거하지 않거나,
    # 앱이 종료될 때 닫도록 별도 관리해야 합니다. 여기서는 g에서 제거합니다.
    client = g.pop('mongo_client', None)
    # if client: client.close() # 앱 종료 시에만 호출되어야 함


class MongoDB:
    """
    기존의 MongoDB 클래스 인터페이스를 유지하면서 새로운 연결 로직을 사용합니다.
    """
    def __init__(self, app=None):
        if app is not None:
            self.init_app(app)

    def init_app(self, app):
        app.teardown_appcontext(close_db)

    def get_db(self):
        return get_db()

    def close(self):
        # 이 메서드는 더 이상 클라이언트를 닫지 않습니다.
        pass

    def create_indexes(self):
        db_instance = self.get_db()
        try:
            # measured_urls 컬렉션
            db_instance.measured_urls.create_index([("url", 1)], unique=True)
            db_instance.measured_urls.create_index([("measured_at", -1)])
            db_instance.measured_urls.create_index([("user_id", 1)])
            db_instance.measured_urls.create_index([("measured_type", 1)])
            db_instance.measured_urls.create_index([("measured_source", 1)])

            # lighthouse_traffic_02 컬렉션 (복합 인덱스 추가)
            db_instance.lighthouse_traffic_02.create_index([("url", 1)], unique=True)
            db_instance.lighthouse_traffic_02.create_index([("measured_at", -1)])
            db_instance.lighthouse_traffic_02.create_index([("user_id", 1)])
            # Phase 1: 복합 인덱스 - URL과 timestamp 동시 조회 최적화
            db_instance.lighthouse_traffic_02.create_index([("url", 1), ("timestamp", -1)])

            # lighthouse_resources_02 컬렉션 (복합 인덱스 추가)
            db_instance.lighthouse_resources_02.create_index([("url", 1)], unique=True)
            db_instance.lighthouse_resources_02.create_index([("measured_at", -1)])
            db_instance.lighthouse_resources_02.create_index([("user_id", 1)])
            # Phase 1: 복합 인덱스 - URL과 timestamp 동시 조회 최적화
            db_instance.lighthouse_resources_02.create_index([("url", 1), ("timestamp", -1)])

            # Phase 1: task_results 컬렉션 인덱스 강화
            # 상태별 작업 조회 최적화
            db_instance.task_results.create_index([("status", 1), ("created_at", -1)])
            # 사용자별 작업 조회 최적화
            db_instance.task_results.create_index([("user_id", 1), ("status", 1)])
            # 큐 처리 순서 최적화 (QUEUED 상태의 작업을 생성 시간순으로 조회)
            db_instance.task_results.create_index([("status", 1), ("created_at", 1)])
            # Celery task ID로 빠른 조회
            db_instance.task_results.create_index([("celery_task_id", 1)])

            # Phase 1: lighthouse_subpage 컬렉션 인덱스
            db_instance.lighthouse_subpage.create_index([("domain_url", 1), ("timestamp", -1)])

            print("MongoDB 인덱스가 성공적으로 생성/확인되었습니다.")
        except Exception as e:
            print(f"인덱스 생성 중 오류 발생: {e}")

# 전역 인스턴스
db = MongoDB()