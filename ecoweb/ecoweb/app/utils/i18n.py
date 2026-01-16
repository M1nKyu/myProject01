"""
국제화(i18n) 유틸리티
Flask-Babel을 사용한 다국어 지원 시스템
"""
from flask import session, request
from flask_babel import Babel
from typing import Optional
import requests
import logging

# 지원 언어 목록
SUPPORTED_LANGUAGES = {
    'ko': {'name': '한국어', 'flag_code': 'kr', 'english_name': 'Korean'},
    'en': {'name': 'English', 'flag_code': 'us', 'english_name': 'English'},
    'ja': {'name': '日本語', 'flag_code': 'jp', 'english_name': 'Japanese'},
    'zh': {'name': '中文', 'flag_code': 'cn', 'english_name': 'Chinese'}
}

DEFAULT_LANGUAGE = 'ko'

babel = Babel()

# 국가 코드 → 언어 코드 매핑
COUNTRY_TO_LANGUAGE = {
    'KR': 'ko',  # 한국
    'JP': 'ja',  # 일본
    'CN': 'zh',  # 중국
    # 기타 국가는 영어로 매핑
}

logger = logging.getLogger(__name__)

# IP GeoIP 캐시 (메모리 기반, 최대 100개)
_ip_country_cache = {}


def get_country_from_ip(ip_address: str) -> Optional[str]:
    """
    IP 주소로부터 국가 코드를 가져옵니다.
    
    Args:
        ip_address: IP 주소 문자열
        
    Returns:
        Optional[str]: 국가 코드 (예: 'KR', 'JP', 'CN') 또는 None
    """
    # 로컬 IP 주소 처리
    if ip_address in ('0.0.0.0', 'localhost', '::1') or ip_address.startswith('192.168.') or ip_address.startswith('10.'):
        return None
    
    # 캐시 확인
    if ip_address in _ip_country_cache:
        return _ip_country_cache[ip_address]
    
    try:
        # ip-api.com 무료 API 사용 (분당 45회 제한)
        # JSON 형식으로 응답 받기
        response = requests.get(
            f'http://ip-api.com/json/{ip_address}',
            params={'fields': 'countryCode'},
            timeout=2  # 2초 타임아웃
        )
        
        if response.status_code == 200:
            data = response.json()
            country_code = data.get('countryCode')
            
            # 캐시에 저장 (최대 100개까지만)
            if len(_ip_country_cache) < 100:
                _ip_country_cache[ip_address] = country_code
            
            return country_code
        else:
            logger.warning(f"IP GeoIP API returned status {response.status_code}")
            return None
            
    except requests.exceptions.Timeout:
        logger.warning(f"IP GeoIP API timeout for IP: {ip_address}")
        return None
    except requests.exceptions.RequestException as e:
        logger.warning(f"IP GeoIP API error for IP {ip_address}: {str(e)}")
        return None
    except Exception as e:
        logger.error(f"Unexpected error in get_country_from_ip: {str(e)}")
        return None


def get_locale_from_country(country_code: str) -> Optional[str]:
    """
    국가 코드를 언어 코드로 변환합니다.
    
    Args:
        country_code: 국가 코드 (예: 'KR', 'JP', 'CN')
        
    Returns:
        Optional[str]: 언어 코드 (ko, ja, zh, en) 또는 None
    """
    if not country_code:
        return None
    
    # 매핑된 언어 코드 반환
    language = COUNTRY_TO_LANGUAGE.get(country_code.upper())
    
    # 매핑되지 않은 국가는 영어로 설정
    if language is None:
        return 'en'
    
    return language


def get_locale() -> str:
    """
    현재 사용자의 언어 설정을 반환합니다.

    우선순위:
    1. URL 파라미터 (?lang=en)
    2. 세션에 저장된 언어
    3. 브라우저 Accept-Language 헤더
    4. IP 기반 국가 감지
    5. 기본 언어 (한국어)

    Returns:
        str: 언어 코드 (ko, en, ja, zh)
    """
    # 1. URL 파라미터 확인
    url_lang = request.args.get('lang')
    if url_lang and url_lang in SUPPORTED_LANGUAGES:
        session['language'] = url_lang
        return url_lang

    # 2. 세션에 저장된 언어
    session_lang = session.get('language')
    if session_lang and session_lang in SUPPORTED_LANGUAGES:
        return session_lang

    # 3. 브라우저 언어 설정 (Accept-Language 헤더)
    browser_lang = request.accept_languages.best_match(SUPPORTED_LANGUAGES.keys())
    if browser_lang:
        session['language'] = browser_lang
        return browser_lang

    # 4. IP 기반 국가 감지
    try:
        # 클라이언트 IP 주소 가져오기 (프록시 고려)
        client_ip = request.environ.get('HTTP_X_FORWARDED_FOR', request.environ.get('REMOTE_ADDR', ''))
        if client_ip:
            # X-Forwarded-For는 여러 IP를 포함할 수 있음 (첫 번째 IP 사용)
            client_ip = client_ip.split(',')[0].strip()
            
            country_code = get_country_from_ip(client_ip)
            if country_code:
                locale_from_country = get_locale_from_country(country_code)
                if locale_from_country and locale_from_country in SUPPORTED_LANGUAGES:
                    session['language'] = locale_from_country
                    return locale_from_country
    except Exception as e:
        logger.warning(f"Error in IP-based language detection: {str(e)}")
        # IP 기반 감지 실패 시 다음 단계로 진행

    # 5. 기본 언어
    session['language'] = DEFAULT_LANGUAGE
    return DEFAULT_LANGUAGE


def get_current_language_info() -> dict:
    """
    현재 언어의 상세 정보를 반환합니다.

    Returns:
        dict: 언어 정보 {'code': 'ko', 'name': '한국어', 'flag': '🇰🇷', 'english_name': 'Korean'}
    """
    current_lang = get_locale()
    return {
        'code': current_lang,
        **SUPPORTED_LANGUAGES[current_lang]
    }


def init_babel(app):
    """
    Flask 앱에 Babel을 초기화합니다.

    Args:
        app: Flask 애플리케이션 인스턴스
    """
    babel.init_app(app, locale_selector=get_locale)

    # Babel 설정
    app.config['BABEL_TRANSLATION_DIRECTORIES'] = 'translations'
    app.config['BABEL_DEFAULT_LOCALE'] = DEFAULT_LANGUAGE
    app.config['BABEL_DEFAULT_TIMEZONE'] = 'Asia/Seoul'

    # 번역 파일 누락 시 기본 언어(한국어)로 폴백
    # 프로덕션 환경에서 .mo 파일이 없을 경우를 대비
    app.config['BABEL_FALLBACK_LOCALE'] = DEFAULT_LANGUAGE

    # 템플릿 컨텍스트에 언어 정보 추가
    @app.context_processor
    def inject_language_info():
        return {
            'current_language': get_current_language_info(),
            'supported_languages': SUPPORTED_LANGUAGES,
            'get_locale': get_locale
        }

    # 프로덕션 환경에서 번역 파일 로딩 확인
    if app.config.get('FLASK_ENV') == 'production':
        import logging
        logger = logging.getLogger(__name__)

        try:
            from flask_babel import get_translations
            translations = get_translations()
            if translations:
                logger.info(f"✓ Translations loaded successfully for locale: {get_locale()}")
            else:
                logger.warning(f"⚠ No translations found, using fallback locale: {DEFAULT_LANGUAGE}")
        except Exception as e:
            logger.error(f"✗ Error loading translations: {e}")
            logger.warning(f"Using fallback locale: {DEFAULT_LANGUAGE}")
