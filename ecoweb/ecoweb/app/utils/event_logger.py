"""
사용자 이벤트 로깅 유틸리티

사용자의 주요 액션을 MongoDB에 기록하는 유틸리티 함수들입니다.
프로덕션 환경에서만 로그가 기록되며, 로컬 환경에서는 비활성화됩니다.
개발 시 임시 활성화: EVENT_LOGGING_FORCE_ENABLE=true 환경 변수 설정
"""

from flask import request, session, current_app
from user_agents import parse
from ecoweb.config import Config
from ecoweb.app.models import UserEventLog
from ecoweb.app import db


def is_logging_enabled():
    """이벤트 로깅이 활성화되어 있는지 확인"""
    return Config.ENABLE_EVENT_LOGGING


def _get_user_info():
    """현재 요청의 사용자 정보 추출"""
    user_id = session.get('user_id')
    user_type = 'registered' if user_id else 'anonymous'
    return str(user_id) if user_id else None, user_type


def _get_device_info():
    """User-Agent에서 디바이스 정보 추출"""
    try:
        user_agent_string = request.user_agent.string
        user_agent = parse(user_agent_string)
        
        device_type = 'Other'
        if user_agent.is_mobile:
            device_type = 'Mobile'
        elif user_agent.is_tablet:
            device_type = 'Tablet'
        elif user_agent.is_pc:
            device_type = 'Desktop'
        
        return {
            'device_type': device_type,
            'browser': user_agent.browser.family,
            'os': user_agent.os.family,
            'user_agent': user_agent_string
        }
    except Exception:
        # User-Agent 파싱 실패 시 기본값
        return {
            'device_type': 'Other',
            'browser': 'Unknown',
            'os': 'Unknown',
            'user_agent': request.user_agent.string if request.user_agent else 'Unknown'
        }


def log_user_event(event_type, event_category, metadata=None, element_id=None):
    """
    일반적인 사용자 이벤트 기록
    
    Args:
        event_type: 이벤트 타입 (예: 'button_click', 'form_submit')
        event_category: 이벤트 카테고리 (예: 'navigation', 'auth')
        metadata: 이벤트별 추가 정보 (dict)
        element_id: 버튼/링크 ID (optional)
    
    Returns:
        bool: 로깅 성공 여부 (비활성화 시 False 반환)
    """
    if not is_logging_enabled():
        return False
    
    try:
        user_id, user_type = _get_user_info()
        device_info = _get_device_info()
        
        event_log = UserEventLog(
            session_id=session.sid if hasattr(session, 'sid') else None,
            user_id=user_id,
            user_type=user_type,
            event_type=event_type,
            event_category=event_category,
            page_url=request.url if request else '',
            ip_address=request.remote_addr if request else '',
            user_agent=device_info['user_agent'],
            device_type=device_info['device_type'],
            browser=device_info['browser'],
            os=device_info['os'],
            element_id=element_id,
            metadata=metadata
        )
        
        db.get_db().user_events.insert_one(event_log.to_dict())
        return True
    except Exception as e:
        # 로깅 실패해도 애플리케이션 동작에 영향 없도록 조용히 처리
        if current_app:
            current_app.logger.debug(f"Failed to log user event: {e}")
        return False


def log_analysis_start(url, user_id=None, is_mobile=False):
    """
    분석 시작 이벤트 기록
    
    Args:
        url: 분석 대상 URL
        user_id: 사용자 ID (optional)
        is_mobile: 모바일 여부
    """
    metadata = {
        'url': url,
        'is_mobile': is_mobile
    }
    return log_user_event(
        event_type='analysis_start',
        event_category='analysis',
        metadata=metadata
    )


def log_analysis_complete(url, task_id, user_id=None, success=True):
    """
    분석 완료 이벤트 기록
    
    Args:
        url: 분석 대상 URL
        task_id: 작업 ID
        user_id: 사용자 ID (optional)
        success: 성공 여부
    """
    metadata = {
        'url': url,
        'task_id': str(task_id) if task_id else None,
        'success': success
    }
    return log_user_event(
        event_type='analysis_complete',
        event_category='analysis',
        metadata=metadata
    )


def log_analysis_cancel(task_id, user_id=None):
    """
    분석 취소 이벤트 기록
    
    Args:
        task_id: 작업 ID
        user_id: 사용자 ID (optional)
    """
    metadata = {
        'task_id': str(task_id) if task_id else None
    }
    return log_user_event(
        event_type='analysis_cancel',
        event_category='analysis',
        metadata=metadata
    )


def log_pdf_generate(task_id, user_id=None):
    """
    PDF 생성 시작 이벤트 기록
    
    Args:
        task_id: 작업 ID
        user_id: 사용자 ID (optional)
    """
    metadata = {
        'task_id': str(task_id) if task_id else None
    }
    return log_user_event(
        event_type='pdf_generate',
        event_category='report',
        metadata=metadata
    )


def log_pdf_download(task_id, user_id=None):
    """
    PDF 다운로드 이벤트 기록
    
    Args:
        task_id: 작업 ID
        user_id: 사용자 ID (optional)
    """
    metadata = {
        'task_id': str(task_id) if task_id else None
    }
    return log_user_event(
        event_type='pdf_download',
        event_category='report',
        metadata=metadata
    )


def log_button_click(element_id, page_url=None, metadata=None):
    """
    버튼 클릭 이벤트 기록
    
    Args:
        element_id: 버튼/링크 ID
        page_url: 페이지 URL (optional, 기본값: 현재 URL)
        metadata: 추가 정보 (optional)
    """
    if page_url is None:
        page_url = request.url if request else ''
    
    return log_user_event(
        event_type='button_click',
        event_category='navigation',
        metadata=metadata,
        element_id=element_id
    )


def log_login(user_id, username=None, login_time=None):
    """
    로그인 이벤트 기록
    
    Args:
        user_id: 사용자 ID
        username: 사용자명 (optional)
        login_time: 로그인 완료 시간 (datetime, optional)
    """
    from datetime import datetime
    metadata = {
        'username': username,
        'login_time': login_time.isoformat() if login_time else datetime.utcnow().isoformat()
    }
    return log_user_event(
        event_type='login',
        event_category='auth',
        metadata=metadata
    )


def log_signup(user_id, username=None):
    """
    회원가입 이벤트 기록
    
    Args:
        user_id: 사용자 ID
        username: 사용자명 (optional)
    """
    metadata = {
        'username': username
    }
    return log_user_event(
        event_type='signup',
        event_category='auth',
        metadata=metadata
    )


def log_page_view(page_type, task_id=None, url=None, metadata=None):
    """
    페이지 조회 이벤트 기록
    
    Args:
        page_type: 페이지 타입 (예: 'home', 'carbon_calculate_emission', 'detailed_analysis', etc.)
        task_id: 작업 ID (optional)
        url: 분석 대상 URL (optional)
        metadata: 추가 정보 (optional)
    """
    page_metadata = {
        'page_type': page_type
    }
    if task_id:
        page_metadata['task_id'] = str(task_id)
    if url:
        page_metadata['url'] = url
    if metadata:
        page_metadata.update(metadata)
    
    return log_user_event(
        event_type='page_view',
        event_category='navigation',
        metadata=page_metadata
    )

