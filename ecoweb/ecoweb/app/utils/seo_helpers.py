"""
SEO 메타 데이터 생성 헬퍼 모듈

이 모듈은 Flask Jinja2 템플릿에 전달할 SEO 메타 데이터를 생성합니다.
"""

from flask import request, url_for
from typing import Dict, Optional, List


class MetaDataGenerator:
    """SEO 메타 데이터 생성 헬퍼 클래스"""

    @staticmethod
    def generate_page_meta(
        title: str,
        description: str,
        canonical_path: str,
        og_image: Optional[str] = None,
        og_type: str = 'website',
        keywords: Optional[List[str]] = None,
        hreflang: Optional[Dict[str, str]] = None
    ) -> Dict:
        """페이지 메타 데이터 생성

        Args:
            title: 페이지 제목 (최대 60자 권장)
            description: 페이지 설명 (최대 160자 권장)
            canonical_path: 정규 URL 경로 (예: '/carbon_calculate_emission/task123')
            og_image: OG 이미지 URL (None이면 기본 이미지)
            og_type: OG 타입 (website, article 등)
            keywords: SEO 키워드 리스트
            hreflang: 다국어 URL 딕셔너리 (예: {'ko': 'url1', 'en': 'url2'})

        Returns:
            템플릿에 전달할 메타 데이터 딕셔너리
        """
        # 기본 URL 구성
        base_url = request.url_root.rstrip('/')
        canonical_url = f"{base_url}{canonical_path}"

        # 기본 OG 이미지 설정
        if not og_image:
            og_image = url_for(
                'static',
                filename='img/og/ecarbon-og-image.png',
                _external=True
            )

        # 기본 키워드
        default_keywords = ['탄소배출량', '웹사이트 분석', '친환경', '최적화', 'eCarbon', '지속가능성']

        # 메타 데이터 딕셔너리 구성
        meta = {
            'title': title[:60],  # 60자 제한 (Google 권장)
            'description': description[:160],  # 160자 제한 (Google 권장)
            'canonical': canonical_url,
            'og_title': title[:60],
            'og_description': description[:160],
            'og_image': og_image,
            'og_url': canonical_url,
            'og_type': og_type,
            'og_site_name': 'eCarbon',
            'og_locale': 'ko_KR',
            'twitter_card': 'summary_large_image',
            'twitter_site': '@eCarbon',
            'keywords': keywords or default_keywords,
            'hreflang': hreflang,
            'robots': 'index, follow'  # 기본: 인덱싱 허용
        }

        return meta

    @staticmethod
    def generate_home_meta() -> Dict:
        """홈페이지 메타 데이터 생성"""
        return MetaDataGenerator.generate_page_meta(
            title="eCarbon - 웹사이트 탄소배출량 분석 서비스",
            description="디지털 지속가능성을 위한 AI 기반 디지털 탄소 측정 플랫폼. 웹사이트의 탄소배출량을 측정하고 최적화 방안을 제시합니다.",
            canonical_path="/",
            og_type='website',
            keywords=['탄소배출량 측정', '웹사이트 최적화', '디지털 탄소', 'AI 분석', '지속가능성']
        )

    @staticmethod
    def generate_analysis_meta(task_result: Dict, task_id: str) -> Dict:
        """분석 결과 페이지 메타 데이터 생성

        Args:
            task_result: MongoDB task_results 문서
            task_id: Task ID

        Returns:
            분석 결과 페이지용 메타 데이터
        """
        view_data = task_result.get('result', {})
        calculated = view_data.get('calculated', {})

        # URL 및 탄소배출량 정보 추출
        url = view_data.get('url', 'Unknown')
        # URL에서 도메인만 추출 (표시용)
        try:
            from urllib.parse import urlparse
            parsed_url = urlparse(url)
            domain = parsed_url.netloc or parsed_url.path
        except:
            domain = url

        carbon_emission = calculated.get('carbon_emission', 0)
        emission_grade = calculated.get('emission_grade', 'N/A')
        emission_percentile = calculated.get('emission_percentile', 50)

        # 타이틀 및 설명 생성
        title = f"{domain} 탄소배출량 분석 - eCarbon"
        description = (
            f"{domain}의 탄소배출량은 {carbon_emission}g CO2/페이지뷰로, "
            f"상위 {emission_percentile}%에 속합니다. "
            f"등급: {emission_grade}. 웹사이트의 환경 영향을 확인하세요."
        )

        # 동적 OG 이미지 (향후 구현 예정)
        og_image = url_for(
            'static',
            filename='img/og/ecarbon-og-image.png',
            _external=True
        )

        return MetaDataGenerator.generate_page_meta(
            title=title,
            description=description,
            canonical_path=f"/carbon_calculate_emission/{task_id}",
            og_image=og_image,
            og_type='article',
            keywords=[
                '탄소배출량',
                domain,
                '웹사이트 분석',
                f'{emission_grade} 등급',
                '환경 영향'
            ]
        )

    @staticmethod
    def generate_detailed_analysis_meta(url: str) -> Dict:
        """정밀 분석 페이지 메타 데이터 생성

        Args:
            url: 분석 대상 URL

        Returns:
            정밀 분석 페이지용 메타 데이터
        """
        # URL에서 도메인만 추출
        try:
            from urllib.parse import urlparse
            parsed_url = urlparse(url)
            domain = parsed_url.netloc or parsed_url.path
        except:
            domain = url or 'N/A'

        title = f"{domain} 상세 분석 - eCarbon"
        description = f"{domain}의 서브페이지별 탄소배출량, 네트워크 구간별 배출량, 콘텐츠 유형별 분석 결과를 확인하세요."

        return MetaDataGenerator.generate_page_meta(
            title=title,
            description=description,
            canonical_path="/detailed-analysis",
            og_type='article',
            keywords=['상세 분석', '서브페이지', '네트워크 분석', domain]
        )

    @staticmethod
    def generate_guidelines_meta() -> Dict:
        """지속가능성 가이드라인 페이지 메타 데이터 생성"""
        return MetaDataGenerator.generate_page_meta(
            title="W3C 웹 지속가능성 가이드라인 - eCarbon",
            description="W3C의 웹 지속가능성 가이드라인을 기반으로 웹사이트의 환경 영향을 평가하고 개선 방안을 제시합니다.",
            canonical_path="/guidelines",
            og_type='website',
            keywords=['W3C', '지속가능성 가이드라인', '웹 최적화', '환경 친화적']
        )

    @staticmethod
    def generate_about_meta() -> Dict:
        """소개 페이지 메타 데이터 생성"""
        return MetaDataGenerator.generate_page_meta(
            title="eCarbon 소개 - 디지털 탄소 측정 플랫폼",
            description="eCarbon은 AI 기반 디지털 탄소 측정 플랫폼으로, 웹사이트의 환경 영향을 분석하고 지속가능한 웹 개발을 지원합니다.",
            canonical_path="/about",
            og_type='website',
            keywords=['eCarbon 소개', '디지털 탄소', '지속가능한 웹', 'AI 분석']
        )
