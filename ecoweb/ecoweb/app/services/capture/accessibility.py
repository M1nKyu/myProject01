import requests
import logging
import asyncio
import time
from typing import Dict, Any, Optional

logger = logging.getLogger(__name__)

def check_site_accessibility_sync(url: str, timeout: int = 5) -> bool:
    """
    URL이 접근 가능한지 동기적으로 확인합니다. (비동기 코드에서 호출 가능)
    
    Args:
        url (str): 확인할 URL
        timeout (int): 타임아웃 시간 (초)
    
    Returns:
        bool: 접근 가능하면 True, 불가능하면 False
    """
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
    }
    
    # 1. HEAD 요청 시도
    try:
        response = requests.head(url, headers=headers, timeout=timeout, allow_redirects=True, verify=False)
        if 200 <= response.status_code < 400:
            return True
        logger.info(f"HEAD 요청 실패 (상태코드: {response.status_code}), GET 요청으로 재시도: {url}")
    except Exception as head_error:
        logger.info(f"HEAD 요청 예외 발생, GET 요청으로 재시도: {url}, 오류: {head_error}")
    
    # 2. GET 요청으로 재시도
    try:
        response = requests.get(
            url, 
            headers=headers, 
            timeout=timeout, 
            allow_redirects=True,
            verify=False, 
            stream=True
        )
        
        # 응답이 시작되면 즉시 연결 종료 (전체 다운로드하지 않음)
        response.close()
        
        if 200 <= response.status_code < 400:
            return True
        else:
            logger.warning(f"사이트 접근 실패 - 상태코드: {response.status_code}, URL: {url}")
            return False
            
    except requests.exceptions.Timeout:
        logger.warning(f"사이트 접근 실패 - 타임아웃({timeout}초), URL: {url}")
        return False
    except requests.exceptions.ConnectionError as e:
        logger.warning(f"사이트 접근 실패 - 연결 오류: {e}, URL: {url}")
        return False
    except requests.exceptions.SSLError as e:
        logger.warning(f"사이트 접근 실패 - SSL 오류: {e}, URL: {url}")
        return False
    except Exception as e:
        logger.warning(f"사이트 접근 실패 - 예외: {e}, URL: {url}")
        return False

async def check_site_accessibility(url: str, timeout: int = 5) -> bool:
    """
    URL이 접근 가능한지 비동기적으로 확인합니다.
    
    Args:
        url (str): 확인할 URL
        timeout (int): 타임아웃 시간 (초)
    
    Returns:
        bool: 접근 가능하면 True, 불가능하면 False
    """
    # 비동기 컨텍스트에서 동기 함수 실행
    loop = asyncio.get_event_loop()
    return await loop.run_in_executor(None, check_site_accessibility_sync, url, timeout)

async def check_multiple_sites_accessibility(urls: list, timeout: int = 5) -> Dict[str, bool]:
    """
    여러 URL의 접근성을 병렬로 확인합니다.
    
    Args:
        urls (list): 확인할 URL 목록
        timeout (int): 각 URL에 대한 타임아웃 시간 (초)
    
    Returns:
        Dict[str, bool]: URL을 키로, 접근 가능 여부를 값으로 하는 딕셔너리
    """
    tasks = []
    for url in urls:
        tasks.append(check_site_accessibility(url, timeout))
    
    results = await asyncio.gather(*tasks)
    return dict(zip(urls, results))

async def check_site_with_retry(url: str, max_retries: int = 3, timeout: int = 5) -> Dict[str, Any]:
    """
    URL 접근성을 여러 번 재시도하며 확인하고 상세 정보를 반환합니다.
    
    Args:
        url (str): 확인할 URL
        max_retries (int): 최대 재시도 횟수
        timeout (int): 각 시도의 타임아웃 시간 (초)
    
    Returns:
        Dict[str, Any]: 접근성 검사 결과 정보
    """
    start_time = time.time()
    
    for attempt in range(max_retries):
        try:
            is_accessible = await check_site_accessibility(url, timeout)
            
            if is_accessible:
                elapsed = time.time() - start_time
                return {
                    'url': url,
                    'accessible': True,
                    'attempts': attempt + 1,
                    'elapsed_seconds': round(elapsed, 2),
                    'error': None
                }
            
            # 실패 시 짧게 대기 후 재시도
            if attempt < max_retries - 1:
                await asyncio.sleep(0.5)
                
        except Exception as e:
            if attempt < max_retries - 1:
                await asyncio.sleep(0.5)
            else:
                elapsed = time.time() - start_time
                return {
                    'url': url,
                    'accessible': False,
                    'attempts': attempt + 1,
                    'elapsed_seconds': round(elapsed, 2),
                    'error': str(e)
                }
    
    elapsed = time.time() - start_time
    return {
        'url': url,
        'accessible': False,
        'attempts': max_retries,
        'elapsed_seconds': round(elapsed, 2),
        'error': 'Maximum retries reached'
    }

async def check_site_health(url: str, timeout: int = 5) -> Dict[str, Any]:
    """
    URL의 건강 상태를 확인하고 상세 정보를 반환합니다.
    
    Args:
        url (str): 확인할 URL
        timeout (int): 타임아웃 시간 (초)
    
    Returns:
        Dict[str, Any]: 사이트 건강 상태 정보
    """
    start_time = time.time()
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
    }
    
    try:
        # 비동기 컨텍스트에서 동기 함수 실행
        loop = asyncio.get_event_loop()
        
        # HEAD 요청 시도
        head_result = None
        try:
            head_response = await loop.run_in_executor(
                None,
                lambda: requests.head(url, headers=headers, timeout=timeout, allow_redirects=True, verify=False)
            )
            head_result = {
                'status_code': head_response.status_code,
                'success': 200 <= head_response.status_code < 400
            }
        except Exception as head_error:
            head_result = {
                'status_code': None,
                'success': False,
                'error': str(head_error)
            }
        
        # GET 요청 시도 (HEAD가 실패했거나 상태 코드가 4xx/5xx인 경우)
        get_result = None
        if not head_result['success']:
            try:
                get_response = await loop.run_in_executor(
                    None,
                    lambda: requests.get(url, headers=headers, timeout=timeout, allow_redirects=True, verify=False, stream=True)
                )
                # 응답 시작되면 연결 종료
                get_response.close()
                
                get_result = {
                    'status_code': get_response.status_code,
                    'success': 200 <= get_response.status_code < 400
                }
            except Exception as get_error:
                get_result = {
                    'status_code': None,
                    'success': False,
                    'error': str(get_error)
                }
        
        elapsed = time.time() - start_time
        
        return {
            'url': url,
            'accessible': head_result['success'] or (get_result and get_result['success']),
            'head_request': head_result,
            'get_request': get_result,
            'elapsed_seconds': round(elapsed, 2)
        }
        
    except Exception as e:
        elapsed = time.time() - start_time
        return {
            'url': url,
            'accessible': False,
            'error': str(e),
            'elapsed_seconds': round(elapsed, 2)
        }



