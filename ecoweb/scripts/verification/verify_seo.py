#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
SEO 구현 검증 스크립트
각 페이지의 메타 태그와 구조화 데이터를 확인합니다.
"""

import requests
from bs4 import BeautifulSoup
import json
from typing import Dict, List

# 검증할 페이지 목록
PAGES_TO_CHECK = [
    {'url': '/', 'name': '홈페이지'},
    {'url': '/about', 'name': '소개 페이지'},
    {'url': '/guidelines', 'name': '가이드라인'},
    {'url': '/membership/plans', 'name': '회원권'},
    {'url': '/badge', 'name': '뱃지'},
]

BASE_URL = 'http://localhost:5000'

def check_meta_tags(soup: BeautifulSoup) -> Dict:
    """메타 태그 확인"""
    results = {
        'canonical': None,
        'description': None,
        'og_title': None,
        'og_description': None,
        'og_url': None,
        'og_image': None,
        'title': None,
    }

    # Title
    title_tag = soup.find('title')
    if title_tag:
        results['title'] = title_tag.string

    # Canonical
    canonical = soup.find('link', {'rel': 'canonical'})
    if canonical:
        results['canonical'] = canonical.get('href')

    # Description
    description = soup.find('meta', {'name': 'description'})
    if description:
        results['description'] = description.get('content')

    # Open Graph
    og_title = soup.find('meta', {'property': 'og:title'})
    if og_title:
        results['og_title'] = og_title.get('content')

    og_desc = soup.find('meta', {'property': 'og:description'})
    if og_desc:
        results['og_description'] = og_desc.get('content')

    og_url = soup.find('meta', {'property': 'og:url'})
    if og_url:
        results['og_url'] = og_url.get('content')

    og_image = soup.find('meta', {'property': 'og:image'})
    if og_image:
        results['og_image'] = og_image.get('content')

    return results

def check_structured_data(soup: BeautifulSoup) -> List[Dict]:
    """구조화 데이터 (JSON-LD) 확인"""
    scripts = soup.find_all('script', {'type': 'application/ld+json'})
    structured_data = []

    for script in scripts:
        try:
            data = json.loads(script.string)
            structured_data.append(data)
        except json.JSONDecodeError:
            pass

    return structured_data

def verify_page(url: str, name: str):
    """개별 페이지 검증"""
    print(f"\n{'='*60}")
    print(f"📄 {name} ({url})")
    print(f"{'='*60}")

    try:
        response = requests.get(BASE_URL + url, timeout=10)
        response.raise_for_status()

        soup = BeautifulSoup(response.text, 'html.parser')

        # 메타 태그 확인
        print("\n✅ 메타 태그:")
        meta_tags = check_meta_tags(soup)

        for key, value in meta_tags.items():
            if value:
                display_value = value if len(str(value)) < 80 else str(value)[:77] + "..."
                print(f"  ✓ {key}: {display_value}")
            else:
                print(f"  ✗ {key}: 없음")

        # 구조화 데이터 확인
        print("\n✅ 구조화 데이터 (JSON-LD):")
        structured_data = check_structured_data(soup)

        if structured_data:
            for idx, data in enumerate(structured_data, 1):
                schema_type = data.get('@type', '알 수 없음')
                print(f"  ✓ Schema {idx}: {schema_type}")
        else:
            print(f"  ✗ 구조화 데이터 없음")

        # 종합 평가
        print("\n📊 종합 평가:")
        score = 0
        total = 0

        # 필수 항목 체크
        required_items = [
            ('Title', meta_tags['title']),
            ('Canonical URL', meta_tags['canonical']),
            ('Description', meta_tags['description']),
            ('OG Title', meta_tags['og_title']),
            ('구조화 데이터', len(structured_data) > 0),
        ]

        for item_name, item_value in required_items:
            total += 1
            if item_value:
                score += 1
                print(f"  ✓ {item_name}")
            else:
                print(f"  ✗ {item_name} 누락")

        percentage = (score / total) * 100
        print(f"\n  점수: {score}/{total} ({percentage:.0f}%)")

        if percentage == 100:
            print(f"  🎉 완벽합니다!")
        elif percentage >= 80:
            print(f"  ✅ 양호합니다.")
        else:
            print(f"  ⚠️ 개선이 필요합니다.")

        return True

    except requests.exceptions.ConnectionError:
        print(f"  ❌ 서버에 연결할 수 없습니다. localhost:5000이 실행 중인지 확인하세요.")
        return False
    except requests.exceptions.Timeout:
        print(f"  ❌ 요청 시간 초과")
        return False
    except Exception as e:
        print(f"  ❌ 오류 발생: {str(e)}")
        return False

def main():
    """메인 실행"""
    print("=" * 60)
    print("🔍 eCarbon SEO 구현 검증 시작")
    print("=" * 60)
    print(f"\n서버 URL: {BASE_URL}")
    print(f"검증 페이지 수: {len(PAGES_TO_CHECK)}개")

    # 서버 연결 테스트
    print("\n서버 연결 테스트 중...")
    try:
        response = requests.get(BASE_URL, timeout=5)
        print("✅ 서버 연결 성공")
    except:
        print("❌ 서버에 연결할 수 없습니다.")
        print("다음 명령어로 서버를 실행하세요:")
        print("  python run.py")
        print("  또는")
        print("  docker-compose -f docker-compose.dev.yml up")
        return

    # 각 페이지 검증
    success_count = 0
    for page in PAGES_TO_CHECK:
        if verify_page(page['url'], page['name']):
            success_count += 1

    # 최종 요약
    print(f"\n{'='*60}")
    print(f"📊 최종 결과")
    print(f"{'='*60}")
    print(f"검증 완료: {success_count}/{len(PAGES_TO_CHECK)} 페이지")

    if success_count == len(PAGES_TO_CHECK):
        print("🎉 모든 페이지 검증 성공!")
    else:
        print(f"⚠️ {len(PAGES_TO_CHECK) - success_count}개 페이지에서 문제 발견")

    print("\n💡 참고:")
    print("  - 동적 페이지(분석 결과 등)는 실제 분석 후 task_id로 확인하세요")
    print("  - Google Search Console 등록 후 실제 검색 결과를 확인하세요")
    print("  - Lighthouse SEO 점수 측정: Chrome DevTools → Lighthouse → SEO")

if __name__ == '__main__':
    try:
        main()
    except KeyboardInterrupt:
        print("\n\n검증이 중단되었습니다.")
