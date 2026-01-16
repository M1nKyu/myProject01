#!/usr/bin/env python
"""
템플릿에서 번역이 필요한 한국어 텍스트를 추출하는 스크립트
"""
import re
from pathlib import Path
from collections import defaultdict

BASE_DIR = Path(__file__).resolve().parent
TEMPLATES_DIR = BASE_DIR / 'ecoweb' / 'app' / 'templates' / 'new-ui'

# 번역 키 매핑
TRANSLATION_KEYS = {
    # 로딩 페이지
    'loading': {
        '잠시만 기다려주세요...': 'loading.please_wait',
        '을 분석하고 있어요!': 'loading.analyzing_url',
        '입력 페이지 분석 중': 'loading.analyzing_main_page',
        '하위 페이지 분석 중': 'loading.analyzing_subpages',
        '이미지 최적화 진행 중': 'loading.optimizing_images',
        '분석 완료!': 'loading.analysis_complete',
        '결과 보기': 'loading.view_results',
        '홈으로 돌아가기': 'loading.go_home',
        '분석 중... - eCarbon': 'loading.page_title',
        '서버 요청이 많아 대기 중입니다': 'loading.queued_message',
        '분석을 진행하고 있어요...': 'loading.in_progress',
        '분석이 취소되었습니다': 'loading.cancelled',
        '분석에 실패했습니다': 'loading.failed',
    },
    # 홈 페이지
    'home': {
        '보이지 않는 탄소,\\n지금 확인해보세요': 'home.main_title',
        'URL을 입력하여 웹사이트의 탄소 배출량을 분석하고\\n친환경 개선 가이드를 받아보세요': 'home.main_subtitle',
        '웹사이트 주소를 입력해주세요': 'home.url_placeholder',
        '분석 시작': 'home.analyze_button',
        '최근 검색한 URL': 'home.recent_searches',
    },
}

def main():
    print("번역 키 설계를 위한 참고용 스크립트입니다.")
    print("실제 번역 파일은 수동으로 작성해야 합니다.")
    print("\n다음 파일들에서 번역이 필요한 텍스트:")

    for page_type, translations in TRANSLATION_KEYS.items():
        print(f"\n[{page_type}]")
        for korean, key in translations.items():
            print(f"  {key}: {korean}")

if __name__ == '__main__':
    main()
