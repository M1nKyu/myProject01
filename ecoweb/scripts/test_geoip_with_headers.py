"""
X-Forwarded-For 헤더를 사용한 IP 기반 언어 감지 테스트

VPN 없이도 다른 국가 IP를 시뮬레이션하여 테스트할 수 있습니다.

사용법:
    python scripts/test_geoip_with_headers.py
"""

import requests
import json

# 테스트할 국가별 IP 주소 (실제 공인 IP)
TEST_IPS = {
    '한국': '0.0.0.0',  # 실제 한국 IP로 변경 가능
    '일본': '0.0.0.0',  # 실제 일본 IP
    '중국': '0.0.0.0',  # 중국 DNS
    '미국': '0.0.0.0',  # Google DNS
}

BASE_URL = "http://localhost:5000"


def test_with_ip_header(country_name, ip_address):
    """특정 IP 헤더로 요청 보내기"""
    print(f"\n{'='*60}")
    print(f"🌍 {country_name} IP 테스트: {ip_address}")
    print(f"{'='*60}")
    
    try:
        # X-Forwarded-For 헤더로 IP 주소 지정
        headers = {
            'X-Forwarded-For': ip_address,
            'User-Agent': 'Mozilla/5.0 (Test Script)'
        }
        
        response = requests.get(
            BASE_URL,
            headers=headers,
            timeout=5,
            allow_redirects=False
        )
        
        print(f"✅ 응답 코드: {response.status_code}")
        
        # 쿠키에서 언어 확인
        cookies = response.cookies
        if cookies:
            print(f"📋 쿠키:")
            for cookie in cookies:
                print(f"   - {cookie.name}: {cookie.value}")
        
        # Set-Cookie 헤더 확인
        set_cookie = response.headers.get('Set-Cookie', '')
        if 'language' in set_cookie:
            print(f"📋 Set-Cookie 헤더: {set_cookie}")
        
        # 응답 본문에서 언어 관련 정보 확인
        if response.status_code == 200:
            content = response.text
            # 언어 관련 텍스트 찾기
            if 'lang="ko"' in content or 'lang="en"' in content or 'lang="ja"' in content or 'lang="zh"' in content:
                import re
                lang_match = re.search(r'lang="([^"]+)"', content)
                if lang_match:
                    print(f"🌐 HTML lang 속성: {lang_match.group(1)}")
        
    except requests.exceptions.ConnectionError:
        print("❌ Flask 서버가 실행 중이지 않습니다.")
        print("   💡 서버를 실행하려면: python run.py")
    except Exception as e:
        print(f"❌ 오류: {str(e)}")


def main():
    """메인 함수"""
    print("\n" + "="*60)
    print("🧪 X-Forwarded-For 헤더를 사용한 IP 기반 언어 감지 테스트")
    print("="*60)
    print("\n⚠️  주의: Flask 서버가 실행 중이어야 합니다.")
    print("   실행 방법: python run.py")
    
    for country_name, ip_address in TEST_IPS.items():
        test_with_ip_header(country_name, ip_address)
    
    print("\n" + "="*60)
    print("✅ 테스트 완료!")
    print("="*60)
    print("\n💡 추가 정보:")
    print("1. 실제 국가 IP 주소를 사용하면 더 정확한 테스트가 가능합니다")
    print("2. VPN을 사용하면 실제 IP가 변경되어 더 정확한 테스트가 가능합니다")
    print("3. 프로덕션 환경에서는 실제 클라이언트 IP가 자동으로 감지됩니다")


if __name__ == '__main__':
    main()

