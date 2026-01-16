"""
이미지 최적화 캐시 관리 유틸리티

Lighthouse timestamp 기반 캐시 만료 검사 및 이미지 변경 감지 기능 제공
"""
import os
import json
import hashlib
import tempfile
import shutil
from datetime import datetime, timezone, timedelta
from pathlib import Path
from typing import Optional, Dict, Any
import requests
import logging

# 파일 잠금 지원 (플랫폼별)
try:
    import fcntl  # Linux/Unix
    HAS_FCNTL = True
except ImportError:
    HAS_FCNTL = False
    try:
        import msvcrt  # Windows
        HAS_MSVCRT = True
    except ImportError:
        HAS_MSVCRT = False

logger = logging.getLogger(__name__)


def get_image_url_hash(image_url: str) -> str:
    """
    이미지 URL을 해시하여 고유 식별자 생성
    
    Args:
        image_url: 이미지 URL
        
    Returns:
        str: MD5 해시값 (16자리)
    """
    return hashlib.md5(image_url.encode()).hexdigest()[:16]


def get_cache_metadata_path(url_s: str, config) -> str:
    """
    캐시 메타데이터 파일 경로 반환
    
    Args:
        url_s: URL (스킴 제거)
        config: Config 객체
        
    Returns:
        str: 메타데이터 파일 경로
    """
    image_dir = os.path.join(config.OPTIMIZATION_IMAGES_FOLDER, url_s)
    return os.path.join(image_dir, '.cache_metadata.json')


def _lock_file(file_obj, exclusive=False):
    """
    파일 잠금 (플랫폼별)
    
    Args:
        file_obj: 파일 객체
        exclusive: True면 배타적 잠금, False면 공유 잠금
    """
    if HAS_FCNTL:
        # Linux/Unix
        lock_type = fcntl.LOCK_EX if exclusive else fcntl.LOCK_SH
        fcntl.flock(file_obj.fileno(), lock_type | fcntl.LOCK_NB)
    elif HAS_MSVCRT:
        # Windows
        if exclusive:
            msvcrt.locking(file_obj.fileno(), msvcrt.LK_NBLCK, 1)
    # 잠금을 지원하지 않는 플랫폼에서는 무시


def _unlock_file(file_obj):
    """파일 잠금 해제"""
    if HAS_FCNTL:
        fcntl.flock(file_obj.fileno(), fcntl.LOCK_UN)
    elif HAS_MSVCRT:
        msvcrt.locking(file_obj.fileno(), msvcrt.LK_UNLCK, 1)


def load_cache_metadata(url_s: str, config) -> Dict[str, Any]:
    """
    캐시 메타데이터 로드 (파일 잠금 사용)
    
    Args:
        url_s: URL (스킴 제거)
        config: Config 객체
        
    Returns:
        dict: 캐시 메타데이터 (없으면 빈 dict)
    """
    metadata_path = get_cache_metadata_path(url_s, config)
    
    if not os.path.exists(metadata_path):
        return {}
    
    max_retries = 3
    retry_delay = 0.1
    
    for attempt in range(max_retries):
        try:
            with open(metadata_path, 'r', encoding='utf-8') as f:
                # 공유 잠금 (읽기)
                try:
                    _lock_file(f, exclusive=False)
                except (IOError, OSError):
                    # 잠금 실패 시 재시도
                    if attempt < max_retries - 1:
                        import time
                        time.sleep(retry_delay)
                        retry_delay *= 2
                        continue
                
                try:
                    content = f.read()
                    # 빈 파일 체크
                    if not content.strip():
                        return {}
                    metadata = json.loads(content)
                    return metadata
                finally:
                    try:
                        _unlock_file(f)
                    except Exception:
                        pass
        except (json.JSONDecodeError, IOError, OSError) as e:
            if attempt < max_retries - 1:
                import time
                time.sleep(retry_delay)
                retry_delay *= 2
                continue
            
            logger.warning(f"캐시 메타데이터 로드 실패: {e}, 빈 메타데이터로 시작")
            # 손상된 파일 백업
            try:
                backup_path = f"{metadata_path}.backup.{datetime.now().strftime('%Y%m%d_%H%M%S')}"
                shutil.move(metadata_path, backup_path)
            except Exception:
                pass
            return {}
    
    return {}


def save_cache_metadata(url_s: str, metadata: Dict[str, Any], config):
    """
    캐시 메타데이터 저장 (원자적 쓰기 + 파일 잠금)
    
    Args:
        url_s: URL (스킴 제거)
        metadata: 저장할 메타데이터
        config: Config 객체
    """
    metadata_path = get_cache_metadata_path(url_s, config)
    image_dir = os.path.dirname(metadata_path)
    
    # 디렉터리 생성
    os.makedirs(image_dir, exist_ok=True)
    
    # 타임스탬프 업데이트
    now = datetime.now(timezone.utc).isoformat()
    if 'cache_created_at' not in metadata:
        metadata['cache_created_at'] = now
    metadata['cache_updated_at'] = now
    
    max_retries = 3
    retry_delay = 0.1
    
    for attempt in range(max_retries):
        try:
            # 원자적 쓰기: 임시 파일에 쓰고 rename
            temp_fd, temp_path = tempfile.mkstemp(
                dir=image_dir,
                prefix='.cache_metadata.tmp.',
                suffix='.json'
            )
            
            try:
                with os.fdopen(temp_fd, 'w', encoding='utf-8') as f:
                    # 배타적 잠금 (쓰기)
                    try:
                        _lock_file(f, exclusive=True)
                    except (IOError, OSError):
                        # 잠금 실패 시 재시도
                        if attempt < max_retries - 1:
                            import time
                            time.sleep(retry_delay)
                            retry_delay *= 2
                            os.close(temp_fd)
                            os.unlink(temp_path)
                            continue
                        raise
                    
                    try:
                        json.dump(metadata, f, indent=2, ensure_ascii=False)
                        f.flush()
                        os.fsync(f.fileno())  # 디스크에 강제 쓰기
                    finally:
                        try:
                            _unlock_file(f)
                        except Exception:
                            pass
                
                # 원자적 이동 (rename은 원자적 연산)
                shutil.move(temp_path, metadata_path)
                return
                
            except Exception as e:
                # 임시 파일 정리
                try:
                    if os.path.exists(temp_path):
                        os.unlink(temp_path)
                except Exception:
                    pass
                raise
                
        except (IOError, OSError) as e:
            if attempt < max_retries - 1:
                import time
                time.sleep(retry_delay)
                retry_delay *= 2
                continue
            logger.error(f"캐시 메타데이터 저장 실패: {e}")
            raise


def calculate_file_hash(file_path: str) -> Optional[str]:
    """
    파일의 SHA256 해시 계산
    
    Args:
        file_path: 파일 경로
        
    Returns:
        str: SHA256 해시값 (없으면 None)
    """
    if not os.path.exists(file_path):
        return None
    
    try:
        sha256 = hashlib.sha256()
        with open(file_path, 'rb') as f:
            for chunk in iter(lambda: f.read(4096), b''):
                sha256.update(chunk)
        return sha256.hexdigest()
    except Exception as e:
        logger.warning(f"파일 해시 계산 실패: {file_path}, {e}")
        return None


def check_image_changed(
    image_url: str,
    cached_meta: Dict[str, Any],
    session: requests.Session,
    file_path: Optional[str] = None
) -> bool:
    """
    이미지가 변경되었는지 확인 (HTTP 헤더 기반)
    
    Args:
        image_url: 이미지 URL
        cached_meta: 캐시된 메타데이터 (이미지별)
        session: requests.Session 객체
        file_path: 로컬 파일 경로 (HEAD 실패 시 해시 비교용)
        
    Returns:
        bool: True면 변경됨, False면 변경 안됨
    """
    try:
        # HEAD 요청으로 변경 감지
        resp = session.head(image_url, verify=False, timeout=(2, 5), allow_redirects=True)
        
        if resp.status_code == 200:
            # ETag 비교 (우선)
            etag = resp.headers.get('ETag', '').strip('"')
            cached_etag = cached_meta.get('etag', '').strip('"')
            
            if etag and cached_etag:
                if etag == cached_etag:
                    return False  # 변경 안됨
                else:
                    return True  # 변경됨
            
            # Last-Modified 비교 (ETag가 없는 경우)
            last_modified = resp.headers.get('Last-Modified')
            cached_last_modified = cached_meta.get('last_modified')
            
            if last_modified and cached_last_modified:
                try:
                    from email.utils import parsedate_to_datetime
                    server_time = parsedate_to_datetime(last_modified)
                    cached_time = datetime.fromisoformat(cached_last_modified.replace('Z', '+00:00'))
                    
                    if server_time and cached_time:
                        if server_time <= cached_time:
                            return False  # 변경 안됨
                        else:
                            return True  # 변경됨
                except Exception:
                    pass
        
        # HEAD 실패 시 파일 해시로 폴백
        if file_path and os.path.exists(file_path):
            current_hash = calculate_file_hash(file_path)
            cached_hash = cached_meta.get('file_hash')
            
            if current_hash and cached_hash:
                return current_hash != cached_hash
        
        # 모든 검증 실패 시 변경된 것으로 간주
        return True
        
    except Exception as e:
        logger.debug(f"이미지 변경 감지 실패: {image_url}, {e}")
        # 예외 발생 시 파일 해시로 폴백
        if file_path and os.path.exists(file_path):
            current_hash = calculate_file_hash(file_path)
            cached_hash = cached_meta.get('file_hash')
            
            if current_hash and cached_hash:
                return current_hash != cached_hash
        
        return True  # 검증 실패 시 재다운로드


def is_cache_valid(
    lighthouse_timestamp: str,
    cached_lighthouse_timestamp: Optional[str],
    ttl_days: int = 7
) -> tuple[bool, bool]:
    """
    캐시 유효성 검증 (Lighthouse timestamp 기반)
    
    Args:
        lighthouse_timestamp: 현재 Lighthouse 분석의 timestamp (ISO 형식)
        cached_lighthouse_timestamp: 캐시된 Lighthouse timestamp (ISO 형식)
        ttl_days: TTL 일수
        
    Returns:
        tuple[bool, bool]: (timestamp 일치 여부, TTL 만료 여부)
    """
    # 1. Lighthouse timestamp 일치 확인 (참고용, 필수 조건 아님)
    timestamp_match = False
    if cached_lighthouse_timestamp:
        # 타임스탬프 문자열 정규화 (밀리초, 타임존 처리)
        try:
            cached_ts = cached_lighthouse_timestamp.replace('Z', '+00:00')
            current_ts = lighthouse_timestamp.replace('Z', '+00:00')
            
            # ISO 형식 파싱
            cached_dt = datetime.fromisoformat(cached_ts)
            current_dt = datetime.fromisoformat(current_ts)
            
            # 타임스탬프 일치 확인 (초 단위까지)
            timestamp_match = (cached_dt.replace(microsecond=0) == current_dt.replace(microsecond=0))
        except Exception as e:
            logger.debug(f"[CACHE] 타임스탬프 파싱 실패: {e}")
    
    # 2. TTL 만료 확인 (캐시된 timestamp 기준으로 계산)
    ttl_valid = False
    if cached_lighthouse_timestamp:
        try:
            cached_ts = cached_lighthouse_timestamp.replace('Z', '+00:00')
            cached_dt = datetime.fromisoformat(cached_ts)
            expiry_dt = cached_dt + timedelta(days=ttl_days)
            now = datetime.now(timezone.utc)
            
            ttl_valid = (now < expiry_dt)
            if not ttl_valid:
                logger.debug(f"[CACHE] TTL 만료: 캐시 시점 {cached_dt}, 만료 시점 {expiry_dt}, 현재 {now}")
        except Exception as e:
            logger.debug(f"[CACHE] TTL 계산 실패: {e}")
            ttl_valid = False
    else:
        # 캐시된 timestamp가 없으면 TTL 검증 불가
        ttl_valid = False
    
    return timestamp_match, ttl_valid


def get_cached_image_info(
    image_url: str,
    url_s: str,
    config
) -> Optional[Dict[str, Any]]:
    """
    캐시된 이미지 정보 조회
    
    Args:
        image_url: 이미지 URL
        url_s: URL (스킴 제거)
        config: Config 객체
        
    Returns:
        dict: 캐시된 이미지 정보 (없으면 None)
    """
    metadata = load_cache_metadata(url_s, config)
    if not metadata:
        return None
    
    url_hash = get_image_url_hash(image_url)
    images = metadata.get('images', {})
    
    cached_info = images.get(url_hash)
    return cached_info


def update_image_cache(
    image_url: str,
    url_s: str,
    filename: str,
    file_path: str,
    file_size: int,
    lighthouse_timestamp: str,
    config,
    webp_path: Optional[str] = None,
    webp_size: Optional[int] = None,
    etag: Optional[str] = None,
    last_modified: Optional[str] = None
):
    """
    이미지 캐시 메타데이터 업데이트 (원자적 업데이트)
    
    Args:
        image_url: 이미지 URL
        url_s: URL (스킴 제거)
        filename: 저장된 파일명
        file_path: 파일 경로
        file_size: 파일 크기
        lighthouse_timestamp: Lighthouse 분석 timestamp
        config: Config 객체
        webp_path: WebP 변환 파일 경로
        webp_size: WebP 파일 크기
        etag: ETag 값
        last_modified: Last-Modified 값
    """
    metadata_path = get_cache_metadata_path(url_s, config)
    max_retries = 5
    retry_delay = 0.1
    
    for attempt in range(max_retries):
        try:
            # 원자적 읽기-수정-쓰기
            metadata = load_cache_metadata(url_s, config)
            
            # Lighthouse timestamp 업데이트
            metadata['lighthouse_timestamp'] = lighthouse_timestamp
            
            # images 딕셔너리 초기화
            if 'images' not in metadata:
                metadata['images'] = {}
            
            # 파일 해시 계산
            file_hash = calculate_file_hash(file_path)
            
            # 이미지 정보 업데이트
            url_hash = get_image_url_hash(image_url)
            if url_hash not in metadata['images']:
                metadata['images'][url_hash] = {}
            
            # 기존 정보 유지하면서 업데이트
            metadata['images'][url_hash].update({
                'url': image_url,
                'filename': filename,
                'file_size': file_size,
                'file_hash': file_hash,
            })
            
            # ETag/Last-Modified 업데이트 (값이 있는 경우만)
            if etag is not None:
                metadata['images'][url_hash]['etag'] = etag
            if last_modified is not None:
                metadata['images'][url_hash]['last_modified'] = last_modified
            
            # WebP 정보 추가/업데이트
            if webp_path:
                metadata['images'][url_hash]['webp_path'] = webp_path
                if webp_size:
                    metadata['images'][url_hash]['webp_size'] = webp_size
            
            # 메타데이터 저장 (원자적 쓰기)
            save_cache_metadata(url_s, metadata, config)
            return
            
        except (IOError, OSError) as e:
            if attempt < max_retries - 1:
                import time
                time.sleep(retry_delay)
                retry_delay *= 2
                continue
            logger.error(f"캐시 메타데이터 업데이트 실패: {e}")
            # 최종 실패 시에도 예외를 발생시키지 않고 로그만 남김
            return
        except Exception as e:
            logger.error(f"캐시 메타데이터 업데이트 중 예외 발생: {e}")
            return

