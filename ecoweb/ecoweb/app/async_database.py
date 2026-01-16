"""
비동기 MongoDB 연결 래퍼 (Phase 4)

Motor를 사용한 완전 비동기 MongoDB 연결
Flask ASGI 전환 시 사용
"""
import os
from motor.motor_asyncio import AsyncIOMotorClient
from typing import Optional
import logging

logger = logging.getLogger(__name__)


class AsyncMongoDB:
    """
    비동기 MongoDB 클라이언트 래퍼 (Phase 4)

    Flask ASGI 전환 후 사용:
    - Motor (비동기 MongoDB 드라이버)
    - AsyncIOMotorClient 사용
    - async/await 패턴
    """

    def __init__(self):
        self.client: Optional[AsyncIOMotorClient] = None
        self.db = None
        self._initialized = False

    async def init_app(self, app=None):
        """
        비동기 초기화

        Usage:
            async_db = AsyncMongoDB()
            await async_db.init_app(app)
        """
        if self._initialized:
            return

        try:
            mongo_uri = os.environ.get('MONGO_URI', 'mongodb+srv://USERNAME:PASSWORD@HOST/?retryWrites=true&w=majority')
            db_name = os.environ.get('MONGO_DB_NAME', 'ecoweb')

            # Motor 클라이언트 생성
            self.client = AsyncIOMotorClient(
                mongo_uri,
                maxPoolSize=50,  # 연결 풀 크기
                minPoolSize=10,
                maxIdleTimeMS=30000,
                serverSelectionTimeoutMS=5000
            )

            # 연결 테스트
            await self.client.admin.command('ping')

            self.db = self.client[db_name]
            self._initialized = True

            logger.info("[ASYNC MONGODB] 비동기 MongoDB 연결 성공")

        except Exception as e:
            logger.error(f"[ASYNC MONGODB] 연결 실패: {str(e)}")
            raise

    async def close(self):
        """
        연결 종료

        Usage:
            await async_db.close()
        """
        if self.client:
            self.client.close()
            self._initialized = False
            logger.info("[ASYNC MONGODB] 연결 종료")

    async def get_db(self):
        """
        데이터베이스 인스턴스 반환

        Returns:
            AsyncIOMotorDatabase
        """
        if not self._initialized:
            raise RuntimeError("AsyncMongoDB가 초기화되지 않았습니다. await init_app()을 먼저 호출하세요.")
        return self.db

    async def create_indexes(self):
        """
        비동기 인덱스 생성 (Phase 1 인덱스 포함)
        """
        if not self._initialized:
            raise RuntimeError("AsyncMongoDB가 초기화되지 않았습니다.")

        try:
            # measured_urls 컬렉션
            await self.db.measured_urls.create_index([("url", 1)], unique=True)
            await self.db.measured_urls.create_index([("measured_at", -1)])
            await self.db.measured_urls.create_index([("user_id", 1)])
            await self.db.measured_urls.create_index([("measured_type", 1)])
            await self.db.measured_urls.create_index([("measured_source", 1)])

            # lighthouse_traffic_02 컬렉션
            await self.db.lighthouse_traffic_02.create_index([("url", 1)], unique=True)
            await self.db.lighthouse_traffic_02.create_index([("measured_at", -1)])
            await self.db.lighthouse_traffic_02.create_index([("user_id", 1)])
            await self.db.lighthouse_traffic_02.create_index([("url", 1), ("timestamp", -1)])

            # lighthouse_resources_02 컬렉션
            await self.db.lighthouse_resources_02.create_index([("url", 1)], unique=True)
            await self.db.lighthouse_resources_02.create_index([("measured_at", -1)])
            await self.db.lighthouse_resources_02.create_index([("user_id", 1)])
            await self.db.lighthouse_resources_02.create_index([("url", 1), ("timestamp", -1)])

            # task_results 컬렉션
            await self.db.task_results.create_index([("status", 1), ("created_at", -1)])
            await self.db.task_results.create_index([("user_id", 1), ("status", 1)])
            await self.db.task_results.create_index([("status", 1), ("created_at", 1)])
            await self.db.task_results.create_index([("celery_task_id", 1)])

            # lighthouse_subpage 컬렉션
            await self.db.lighthouse_subpage.create_index([("domain_url", 1), ("timestamp", -1)])

            logger.info("[ASYNC MONGODB] 인덱스 생성 완료")

        except Exception as e:
            logger.error(f"[ASYNC MONGODB] 인덱스 생성 실패: {str(e)}")
            raise


# 전역 인스턴스 (Flask ASGI 전환 후 사용)
async_db = AsyncMongoDB()


# 동기 호환 래퍼 (점진적 마이그레이션용)
def get_async_db_sync():
    """
    동기 코드에서 비동기 DB 접근 시 사용 (권장하지 않음)

    실제 사용 시:
        import asyncio
        db = asyncio.run(async_db.get_db())
    """
    import asyncio
    return asyncio.run(async_db.get_db())
