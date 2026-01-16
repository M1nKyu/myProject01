"""
Structured Data (Schema.org JSON-LD) 생성 헬퍼 모듈

이 모듈은 검색 엔진 최적화를 위한 Schema.org 구조화 데이터를 생성합니다.
"""

from typing import Dict, List, Optional
from datetime import datetime


class StructuredDataGenerator:
    """Schema.org JSON-LD 생성 헬퍼 클래스"""

    @staticmethod
    def generate_organization_schema() -> Dict:
        """Organization Schema (사이트 전역)

        Returns:
            Organization 타입의 Schema.org JSON-LD
        """
        return {
            "@context": "https://schema.org",
            "@type": "Organization",
            "name": "eCarbon",
            "url": "https://example.com",
            "logo": {
                "@type": "ImageObject",
                "url": "https://example.com/static/img/logo.png"
            },
            "description": "디지털 지속가능성을 위한 AI 기반 디지털 탄소 측정 플랫폼",
            "foundingDate": "2024",
            "contactPoint": {
                "@type": "ContactPoint",
                "contactType": "Customer Service",
                "availableLanguage": ["Korean", "English"]
            }
        }

    @staticmethod
    def generate_website_schema() -> Dict:
        """WebSite Schema (검색 기능 포함)

        Returns:
            WebSite 타입의 Schema.org JSON-LD (SearchAction 포함)
        """
        return {
            "@context": "https://schema.org",
            "@type": "WebSite",
            "name": "eCarbon",
            "url": "https://example.com",
            "description": "웹사이트 탄소배출량 측정 및 최적화 플랫폼",
            "potentialAction": {
                "@type": "SearchAction",
                "target": {
                    "@type": "EntryPoint",
                    "urlTemplate": "https://example.com/?url={search_term_string}"
                },
                "query-input": "required name=search_term_string"
            }
        }

    @staticmethod
    def generate_analysis_article_schema(
        task_result: Dict,
        task_id: str
    ) -> Dict:
        """분석 결과 Article Schema

        Args:
            task_result: MongoDB task_results 문서
            task_id: Task ID

        Returns:
            Article 타입의 Schema.org JSON-LD
        """
        view_data = task_result.get('result', {})
        calculated = view_data.get('calculated', {})

        # 데이터 추출
        url = view_data.get('url', 'Unknown')
        carbon_emission = calculated.get('carbon_emission', 0)
        emission_grade = calculated.get('emission_grade', 'N/A')
        created_at = task_result.get('created_at', datetime.utcnow())

        # URL에서 도메인 추출
        try:
            from urllib.parse import urlparse
            parsed_url = urlparse(url)
            domain = parsed_url.netloc or parsed_url.path
        except:
            domain = url

        # 날짜 형식 처리
        if hasattr(created_at, 'isoformat'):
            date_str = created_at.isoformat()
        else:
            date_str = str(created_at)

        return {
            "@context": "https://schema.org",
            "@type": "Article",
            "headline": f"{domain} 탄소배출량 분석 결과",
            "description": f"{domain}의 웹사이트 탄소배출량 분석 리포트. 배출량: {carbon_emission}g CO2, 등급: {emission_grade}",
            "image": "https://example.com/static/img/og/ecarbon-og-image.png",
            "datePublished": date_str,
            "dateModified": date_str,
            "author": {
                "@type": "Organization",
                "name": "eCarbon"
            },
            "publisher": {
                "@type": "Organization",
                "name": "eCarbon",
                "logo": {
                    "@type": "ImageObject",
                    "url": "https://example.com/static/img/logo.png"
                }
            },
            "mainEntityOfPage": {
                "@type": "WebPage",
                "@id": f"https://example.com/carbon_calculate_emission/{task_id}"
            },
            "about": {
                "@type": "Thing",
                "name": "웹사이트 탄소배출량",
                "description": f"{carbon_emission}g CO2 per page view"
            }
        }

    @staticmethod
    def generate_breadcrumb_schema(items: List[Dict[str, str]]) -> Dict:
        """Breadcrumb Schema

        Args:
            items: Breadcrumb 항목 리스트
                   예: [{'name': '홈', 'url': '/'}, {'name': '분석 결과', 'url': '/result'}]

        Returns:
            BreadcrumbList 타입의 Schema.org JSON-LD
        """
        return {
            "@context": "https://schema.org",
            "@type": "BreadcrumbList",
            "itemListElement": [
                {
                    "@type": "ListItem",
                    "position": idx + 1,
                    "name": item['name'],
                    "item": f"https://example.com{item['url']}" if not item['url'].startswith('http') else item['url']
                }
                for idx, item in enumerate(items)
            ]
        }

    @staticmethod
    def generate_faq_schema(faqs: List[Dict[str, str]]) -> Dict:
        """FAQ Schema

        Args:
            faqs: FAQ 항목 리스트
                  예: [{'question': 'Q1', 'answer': 'A1'}, ...]

        Returns:
            FAQPage 타입의 Schema.org JSON-LD
        """
        return {
            "@context": "https://schema.org",
            "@type": "FAQPage",
            "mainEntity": [
                {
                    "@type": "Question",
                    "name": faq['question'],
                    "acceptedAnswer": {
                        "@type": "Answer",
                        "text": faq['answer']
                    }
                }
                for faq in faqs
            ]
        }

    @staticmethod
    def generate_web_application_schema() -> Dict:
        """WebApplication Schema (서비스 설명)

        Returns:
            WebApplication 타입의 Schema.org JSON-LD
        """
        return {
            "@context": "https://schema.org",
            "@type": "WebApplication",
            "name": "eCarbon",
            "description": "웹사이트 탄소배출량 측정 및 최적화 도구",
            "url": "https://example.com",
            "applicationCategory": "EnvironmentalApplication",
            "operatingSystem": "Any",
            "offers": {
                "@type": "Offer",
                "price": "0",
                "priceCurrency": "KRW"
            },
            "featureList": [
                "웹사이트 탄소배출량 측정",
                "AI 기반 최적화 제안",
                "W3C 지속가능성 가이드라인 준수 평가",
                "상세 분석 리포트 생성"
            ]
        }

    @staticmethod
    def generate_how_to_schema(
        name: str,
        description: str,
        steps: List[Dict[str, str]]
    ) -> Dict:
        """HowTo Schema (사용 방법 안내)

        Args:
            name: How-to 제목
            description: How-to 설명
            steps: 단계별 내용
                   예: [{'name': '1단계', 'text': '설명'}, ...]

        Returns:
            HowTo 타입의 Schema.org JSON-LD
        """
        return {
            "@context": "https://schema.org",
            "@type": "HowTo",
            "name": name,
            "description": description,
            "step": [
                {
                    "@type": "HowToStep",
                    "position": idx + 1,
                    "name": step['name'],
                    "text": step['text']
                }
                for idx, step in enumerate(steps)
            ]
        }

    @staticmethod
    def generate_itemlist_schema(
        name: str,
        items: List[Dict[str, str]]
    ) -> Dict:
        """ItemList Schema (목록형 콘텐츠)

        Args:
            name: 리스트 제목
            items: 항목 리스트
                   예: [{'name': '항목1', 'url': '/item1'}, ...]

        Returns:
            ItemList 타입의 Schema.org JSON-LD
        """
        return {
            "@context": "https://schema.org",
            "@type": "ItemList",
            "name": name,
            "itemListElement": [
                {
                    "@type": "ListItem",
                    "position": idx + 1,
                    "name": item['name'],
                    "url": f"https://example.com{item['url']}" if not item['url'].startswith('http') else item['url']
                }
                for idx, item in enumerate(items)
            ]
        }
