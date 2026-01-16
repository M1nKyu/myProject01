"""
Sitemap.xml 및 Robots.txt 검증 스크립트

이 스크립트는 /sitemap.xml과 /robots.txt 엔드포인트가
정상적으로 작동하는지 확인합니다.

사용법:
    python verify_sitemap_robots.py

요구사항:
    - Flask 서버가 localhost:5000에서 실행 중이어야 합니다
    - requests 라이브러리 필요

작성일: 2025-10-22
"""

import requests
from urllib.parse import urlparse
import sys


def test_sitemap():
    """Sitemap.xml 테스트"""
    print("\n" + "="*60)
    print("🗺️  Sitemap.xml 검증")
    print("="*60)

    url = "http://localhost:5000/sitemap.xml"

    try:
        response = requests.get(url, timeout=10)

        print(f"\n✅ 응답 코드: {response.status_code}")

        if response.status_code == 200:
            print(f"✅ Content-Type: {response.headers.get('Content-Type')}")

            # XML 형식 확인
            if 'xml' in response.headers.get('Content-Type', ''):
                print("✅ Content-Type이 XML입니다")
            else:
                print(f"⚠️  Content-Type이 XML이 아닙니다: {response.headers.get('Content-Type')}")

            # 내용 검증
            content = response.text

            # XML 선언 확인
            if '<?xml version=' in content:
                print("✅ XML 선언이 있습니다")

            # urlset 확인
            if '<urlset' in content and 'sitemaps.org' in content:
                print("✅ Sitemap 형식이 올바릅니다")

            # URL 개수 확인
            url_count = content.count('<loc>')
            print(f"✅ 포함된 URL 개수: {url_count}개")

            # 필수 페이지 확인
            required_pages = [
                ('/', '홈페이지'),
                ('/about', '소개'),
                ('/guidelines', '가이드라인'),
                ('/membership/plans', '회원권'),
                ('/badge', '뱃지')
            ]

            print("\n📋 포함된 페이지:")
            for path, name in required_pages:
                if path in content:
                    print(f"  ✅ {name} ({path})")
                else:
                    print(f"  ❌ {name} ({path}) - 누락!")

            # changefreq 확인
            if '<changefreq>' in content:
                print("\n✅ changefreq 태그가 있습니다")

            # priority 확인
            if '<priority>' in content:
                print("✅ priority 태그가 있습니다")

            print("\n✅ Sitemap.xml 검증 완료!")
            return True

        else:
            print(f"❌ 실패: HTTP {response.status_code}")
            print(f"응답 내용: {response.text[:500]}")
            return False

    except requests.exceptions.ConnectionError:
        print("❌ 연결 실패: 서버가 실행 중인지 확인하세요")
        print("   docker ps 또는 python run.py 확인")
        return False
    except Exception as e:
        print(f"❌ 오류 발생: {e}")
        return False


def test_robots():
    """Robots.txt 테스트"""
    print("\n" + "="*60)
    print("🤖 Robots.txt 검증")
    print("="*60)

    url = "http://localhost:5000/robots.txt"

    try:
        response = requests.get(url, timeout=10)

        print(f"\n✅ 응답 코드: {response.status_code}")

        if response.status_code == 200:
            print(f"✅ Content-Type: {response.headers.get('Content-Type')}")

            # text/plain 확인
            if 'text/plain' in response.headers.get('Content-Type', ''):
                print("✅ Content-Type이 text/plain입니다")

            content = response.text

            # User-agent 확인
            if 'User-agent:' in content:
                print("✅ User-agent 지시문이 있습니다")

            # Allow 확인
            if 'Allow:' in content:
                print("✅ Allow 지시문이 있습니다")

            # Disallow 확인
            if 'Disallow:' in content:
                print("✅ Disallow 지시문이 있습니다")

            # Sitemap 참조 확인
            if 'Sitemap:' in content:
                print("✅ Sitemap 위치가 지정되어 있습니다")
                # Sitemap URL 추출
                for line in content.split('\n'):
                    if line.startswith('Sitemap:'):
                        sitemap_url = line.split(':', 1)[1].strip()
                        print(f"   📍 Sitemap URL: {sitemap_url}")

            # 주요 Disallow 규칙 확인
            print("\n📋 주요 Disallow 규칙:")
            disallow_rules = [
                ('/carbon_calculate_emission/', '분석 결과 (동적)'),
                ('/code_analysis/', '코드 분석 (동적)'),
                ('/img_optimization/', '이미지 최적화 (동적)'),
                ('/dev/', '개발 도구'),
                ('/api/', 'API'),
                ('/auth/', '인증')
            ]

            for path, name in disallow_rules:
                if f'Disallow: {path}' in content:
                    print(f"  ✅ {name} ({path})")
                else:
                    print(f"  ⚠️  {name} ({path}) - 누락")

            # Crawl-delay 확인
            if 'Crawl-delay:' in content:
                print("\n✅ Crawl-delay가 설정되어 있습니다")

            print("\n✅ Robots.txt 검증 완료!")
            return True

        else:
            print(f"❌ 실패: HTTP {response.status_code}")
            print(f"응답 내용: {response.text[:500]}")
            return False

    except requests.exceptions.ConnectionError:
        print("❌ 연결 실패: 서버가 실행 중인지 확인하세요")
        print("   docker ps 또는 python run.py 확인")
        return False
    except Exception as e:
        print(f"❌ 오류 발생: {e}")
        return False


def main():
    """메인 함수"""
    print("\n" + "="*60)
    print("🔍 ECO-WEB Sitemap & Robots 검증 스크립트")
    print("="*60)

    sitemap_ok = test_sitemap()
    robots_ok = test_robots()

    print("\n" + "="*60)
    print("📊 최종 결과")
    print("="*60)

    if sitemap_ok and robots_ok:
        print("\n✅ 모든 테스트 통과!")
        print("\n다음 단계:")
        print("1. Google Search Console에 Sitemap 제출")
        print("   → https://search.google.com/search-console")
        print("2. Robots.txt 문법 검증")
        print("   → https://www.google.com/webmasters/tools/robots-testing-tool")
        print("3. 실제 크롤러 테스트")
        print("   → curl -A 'Googlebot' http://localhost:5000/sitemap.xml")
        return 0
    else:
        print("\n❌ 일부 테스트 실패")
        print("\n해결 방법:")
        print("1. Flask 서버 재시작: docker-compose restart web")
        print("2. 로그 확인: docker logs ecoweb-web-1")
        print("3. Blueprint 등록 확인: logs에 'SEO blueprint registered' 메시지")
        return 1


if __name__ == '__main__':
    sys.exit(main())
