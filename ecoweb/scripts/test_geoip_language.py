"""
IP 기반 GeoIP 언어 자동 감지 테스트 스크립트

이 스크립트는 IP 주소를 기반으로 언어를 자동 감지하는 기능을 테스트합니다.

사용법:
    python scripts/test_geoip_language.py

요구사항:
    - Flask 서버가 실행 중이어야 합니다 (선택사항)
    - requests 라이브러리 필요
"""

import sys
import os

# 프로젝트 루트를 Python 경로에 추가
project_root = os.path.join(os.path.dirname(__file__), '..')
sys.path.insert(0, project_root)

# 직접 함수 구현 (의존성 최소화)
import requests
import logging

logging.basicConfig(level=logging.WARNING)

# 국가 코드 → 언어 코드 매핑
COUNTRY_TO_LANGUAGE = {
    'KR': 'ko',  # 한국
    'JP': 'ja',  # 일본
    'CN': 'zh',  # 중국
    # 기타 국가는 영어로 매핑
}

# IP GeoIP 캐시
_ip_country_cache = {}


def get_country_from_ip(ip_address: str):
    """IP 주소로부터 국가 코드를 가져옵니다."""
    # 로컬 IP 주소 처리
    if ip_address in ('0.0.0.0', 'localhost', '::1') or ip_address.startswith('192.168.') or ip_address.startswith('10.'):
        return None
    
    # 캐시 확인
    if ip_address in _ip_country_cache:
        return _ip_country_cache[ip_address]
    
    try:
        response = requests.get(
            f'http://ip-api.com/json/{ip_address}',
            params={'fields': 'countryCode'},
            timeout=2
        )
        
        if response.status_code == 200:
            data = response.json()
            country_code = data.get('countryCode')
            
            if len(_ip_country_cache) < 100:
                _ip_country_cache[ip_address] = country_code
            
            return country_code
        else:
            return None
    except Exception:
        return None


def get_locale_from_country(country_code: str):
    """국가 코드를 언어 코드로 변환합니다."""
    if not country_code:
        return None
    
    language = COUNTRY_TO_LANGUAGE.get(country_code.upper())
    
    if language is None:
        return 'en'
    
    return language


def test_get_country_from_ip():
    """IP 주소로부터 국가 코드 가져오기 테스트"""
    print("\n" + "="*60)
    print("🌍 IP → 국가 코드 테스트")
    print("="*60)
    
    # 테스트할 IP 주소들 (실제 공인 IP 주소)
    test_ips = {
        '0.0.0.0': 'US',  # Google DNS (미국)
        '0.0.0.0': 'AU',  # Cloudflare DNS (호주)
        '0.0.0.0': 'CN',  # 중국 DNS
    }
    
    print("\n테스트 IP 주소들:")
    for ip, expected_country in test_ips.items():
        print(f"  - {ip} (예상: {expected_country})")
    
    print("\n실제 결과:")
    for ip, expected_country in test_ips.items():
        try:
            country = get_country_from_ip(ip)
            status = "✅" if country == expected_country else "⚠️"
            print(f"  {status} {ip} → {country} (예상: {expected_country})")
        except Exception as e:
            print(f"  ❌ {ip} → 오류: {str(e)}")


def test_get_locale_from_country():
    """국가 코드 → 언어 코드 변환 테스트"""
    print("\n" + "="*60)
    print("🗣️  국가 코드 → 언어 코드 테스트")
    print("="*60)
    
    test_cases = {
        'KR': 'ko',  # 한국 → 한국어
        'JP': 'ja',  # 일본 → 일본어
        'CN': 'zh',  # 중국 → 중국어
        'US': 'en',  # 미국 → 영어
        'GB': 'en',  # 영국 → 영어
        'FR': 'en',  # 프랑스 → 영어 (매핑 없음)
        'DE': 'en',  # 독일 → 영어 (매핑 없음)
    }
    
    print("\n테스트 케이스:")
    for country, expected_lang in test_cases.items():
        result = get_locale_from_country(country)
        status = "✅" if result == expected_lang else "❌"
        print(f"  {status} {country} → {result} (예상: {expected_lang})")


def test_local_ip():
    """로컬 IP 주소 필터링 테스트"""
    print("\n" + "="*60)
    print("🏠 로컬 IP 주소 필터링 테스트")
    print("="*60)
    
    local_ips = [
        '0.0.0.0',
        'localhost',
        '::1',
        '0.0.0.0',
        '0.0.0.0',
    ]
    
    print("\n로컬 IP 주소들:")
    for ip in local_ips:
        country = get_country_from_ip(ip)
        status = "✅" if country is None else "❌"
        print(f"  {status} {ip} → {country} (예상: None)")


def test_with_flask_server():
    """Flask 서버를 통한 실제 테스트"""
    print("\n" + "="*60)
    print("🌐 Flask 서버 통합 테스트")
    print("="*60)
    
    base_url = "http://localhost:5000"
    
    try:
        # 세션 없이 접속 (IP 기반 감지가 작동해야 함)
        print("\n1. 세션 없이 메인 페이지 접속 (IP 기반 언어 감지)")
        response = requests.get(base_url, timeout=5)
        
        if response.status_code == 200:
            print(f"   ✅ 응답 코드: {response.status_code}")
            # 쿠키에서 언어 확인
            cookies = response.cookies
            print(f"   📋 쿠키: {dict(cookies)}")
        else:
            print(f"   ⚠️  응답 코드: {response.status_code}")
            
    except requests.exceptions.ConnectionError:
        print("   ⚠️  Flask 서버가 실행 중이지 않습니다.")
        print("   💡 서버를 실행하려면: python run.py")
    except Exception as e:
        print(f"   ❌ 오류: {str(e)}")


def test_api_directly():
    """IP GeoIP API 직접 테스트"""
    print("\n" + "="*60)
    print("🔌 IP GeoIP API 직접 테스트")
    print("="*60)
    
    test_ip = "0.0.0.0"  # Google DNS
    
    try:
        response = requests.get(
            f'http://ip-api.com/json/{test_ip}',
            params={'fields': 'countryCode'},
            timeout=2
        )
        
        if response.status_code == 200:
            data = response.json()
            print(f"   ✅ API 응답 성공")
            print(f"   📋 응답 데이터: {data}")
            print(f"   🌍 국가 코드: {data.get('countryCode')}")
        else:
            print(f"   ⚠️  API 응답 코드: {response.status_code}")
            
    except Exception as e:
        print(f"   ❌ API 호출 실패: {str(e)}")


def main():
    """메인 함수"""
    print("\n" + "="*60)
    print("🧪 IP 기반 GeoIP 언어 자동 감지 테스트")
    print("="*60)
    
    # 1. 국가 코드 → 언어 코드 변환 테스트
    test_get_locale_from_country()
    
    # 2. 로컬 IP 필터링 테스트
    test_local_ip()
    
    # 3. IP GeoIP API 직접 테스트
    test_api_directly()
    
    # 4. 실제 IP 주소 테스트 (시간이 걸릴 수 있음)
    print("\n" + "="*60)
    print("⏳ 실제 IP 주소 테스트 (API 호출 중...)")
    print("="*60)
    test_get_country_from_ip()
    
    # 5. Flask 서버 통합 테스트 (선택사항)
    test_with_flask_server()
    
    print("\n" + "="*60)
    print("✅ 테스트 완료!")
    print("="*60)
    print("\n💡 추가 테스트 방법:")
    print("1. 브라우저에서 세션 쿠키 삭제 후 접속")
    print("2. VPN을 사용하여 다른 국가 IP로 접속")
    print("3. 개발자 도구에서 쿠키 확인")
    print("4. 서버 로그에서 언어 감지 메시지 확인")


if __name__ == '__main__':
    main()

