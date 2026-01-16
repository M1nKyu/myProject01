"""
PDF 보고서 생성 서비스
HTML/CSS 템플릿을 사용하여 탄소 배출량 분석 결과를 PDF로 생성합니다.
"""

import io
import os
from datetime import datetime
from typing import Dict, Any, Optional, List
from urllib.parse import urlparse

from flask import render_template, current_app
import weasyprint


class CarbonReportGenerator:
    """HTML/CSS 기반 탄소 배출량 분석 보고서 PDF 생성기"""
    
    def __init__(self):
        pass
    
    def generate_pdf(self, session_data: Dict[str, Any]) -> io.BytesIO:
        """세션 데이터를 기반으로 PDF 보고서 생성"""
        try:
            # 데이터 준비
            report_data = self._prepare_report_data(session_data)

            # CSS 파일 경로 설정 (static 디렉토리에 있음)
            app_root = os.path.dirname(current_app.root_path)
            css_base_path = os.path.join(app_root, 'static', 'pdf-reports', 'css')

            # 모든 페이지 HTML 렌더링
            html_pages = []
            stylesheets = []

            for i in range(1, 14):  # report01.html ~ report13.html
                template_name = f'pdf_reports/report{i:02d}.html'
                css_file = f'report{i:02d}.css'
                css_path = os.path.join(css_base_path, css_file)

                try:
                    # HTML 렌더링
                    page_html = render_template(template_name, **report_data)

                    # CSS 경로 수정 (상대 경로를 절대 경로로 변경)
                    page_html = page_html.replace(f'./report{i:02d}.css', css_path)

                    html_pages.append(page_html)

                    # CSS 파일 경로 수집
                    if os.path.exists(css_path):
                        stylesheets.append(css_path)

                except Exception as e:
                    print(f"페이지 {i} 렌더링 중 오류: {e}")
                    continue

            # 모든 페이지를 하나의 HTML로 결합
            combined_html = ''.join(html_pages)

            # HTML을 PDF로 변환 (CSS 파일들과 함께)
            pdf_buffer = io.BytesIO()
            html_doc = weasyprint.HTML(string=combined_html, base_url=current_app.root_path)

            # CSS 파일들을 별도로 로드
            css_objects = []

            # 가로형 페이지 설정을 위한 기본 CSS 추가
            landscape_css = """
            @page {
                size: A4 landscape;
                margin: 1cm;
            }
            """
            css_objects.append(weasyprint.CSS(string=landscape_css))

            for css_path in stylesheets:
                if os.path.exists(css_path):
                    css_objects.append(weasyprint.CSS(filename=css_path))

            # PDF 페이지 설정 (가로형)
            html_doc.write_pdf(pdf_buffer, stylesheets=css_objects,
                             presentational_hints=True,
                             optimize_images=True)
            pdf_buffer.seek(0)

            return pdf_buffer

        except Exception as e:
            print(f"PDF 생성 중 오류 발생: {e}")
            raise e
    
    def _prepare_report_data(self, session_data: Dict[str, Any]) -> Dict[str, Any]:
        """세션 데이터를 템플릿용 데이터로 변환"""
        # 기본 데이터 추출
        url = session_data.get('url', 'N/A')
        carbon_emission = session_data.get('carbon_emission', 0)
        kb_weight = session_data.get('kb_weight', 0)
        
        # 등급 계산
        grade_info = self._calculate_grade(carbon_emission)
        
        # 콘텐츠 데이터 처리
        content_data = self._process_content_data(session_data.get('content_emission_data', []))
        
        # 서브페이지 데이터 처리
        subpages = self._process_subpage_data(session_data.get('subpages', []))
        
        # 권장사항 생성
        recommendations = self._generate_recommendations(carbon_emission, session_data)
        
        return {
            'url': url,
            'analysis_date': datetime.now().strftime('%Y년 %m월 %d일 %H:%M'),
            'total_size': f"{kb_weight:,.0f}",
            'carbon_emission': f"{carbon_emission:.3f}",
            'grade': grade_info['grade'],
            'grade_class': grade_info['class'],
            'content_data': content_data,
            'subpages': subpages[:5],  # 상위 5개만
            'recommendations': recommendations
        }
    
    def _calculate_grade(self, carbon_emission: float) -> Dict[str, str]:
        """탄소 배출량 기준 등급 계산"""
        if carbon_emission <= 0.3:
            return {'grade': 'A', 'class': 'a'}
        elif carbon_emission <= 0.6:
            return {'grade': 'B', 'class': 'b'}
        elif carbon_emission <= 1.0:
            return {'grade': 'C', 'class': 'c'}
        elif carbon_emission <= 1.5:
            return {'grade': 'D', 'class': 'd'}
        else:
            return {'grade': 'F', 'class': 'f'}
    
    def _process_content_data(self, content_emission_data: List[Dict]) -> List[Dict]:
        """콘텐츠 데이터 처리"""
        processed_data = []
        total_emission = sum(item.get('carbon_emission', 0) for item in content_emission_data)
        
        for item in content_emission_data:
            content_type = item.get('content_type', 'Unknown')
            size = item.get('size_kb', 0)
            emission = item.get('carbon_emission', 0)
            percentage = (emission / total_emission * 100) if total_emission > 0 else 0
            
            processed_data.append({
                'type': content_type,
                'size': f"{size:,.0f}",
                'emission': f"{emission:.3f}",
                'percentage': f"{percentage:.1f}"
            })
        
        return processed_data
    
    def _process_subpage_data(self, subpages_data: List[Dict]) -> List[Dict]:
        """서브페이지 데이터 처리"""
        # 배출량 기준으로 정렬
        sorted_subpages = sorted(
            subpages_data, 
            key=lambda x: x.get('emission_g', 0), 
            reverse=True
        )
        
        processed_data = []
        for subpage in sorted_subpages:
            url = subpage.get('url', 'N/A')
            # URL이 너무 길면 줄임
            if len(url) > 60:
                url = url[:57] + '...'
            
            processed_data.append({
                'url': url,
                'size': f"{subpage.get('total_kb', 0):,.0f}",
                'emission': f"{subpage.get('emission_g', 0):.3f}"
            })
        
        return processed_data
    
    def _generate_recommendations(self, carbon_emission: float, session_data: Dict[str, Any]) -> List[str]:
        """개선 권장사항 생성"""
        recommendations = []
        
        # 기본 권장사항
        if carbon_emission > 1.0:
            recommendations.extend([
                "이미지 최적화: 이미지 파일을 WebP 형식으로 변환하고 적절한 크기로 리사이징하세요.",
                "CSS/JavaScript 압축: 불필요한 공백과 주석을 제거하여 파일 크기를 줄이세요."
            ])
        
        if carbon_emission > 0.6:
            recommendations.extend([
                "CDN 사용: 콘텐츠 전송 네트워크를 활용하여 로딩 속도를 개선하세요.",
                "캐싱 정책 개선: 브라우저 캐싱과 서버 캐싱을 적극 활용하세요."
            ])
        
        # 콘텐츠 유형별 권장사항
        content_data = session_data.get('content_emission_data', [])
        if content_data:
            max_emission_content = max(content_data, key=lambda x: x.get('carbon_emission', 0), default={})
            content_type = max_emission_content.get('content_type', '')
            
            if content_type == 'image':
                recommendations.append("이미지가 가장 많은 탄소를 배출하고 있습니다. 이미지 압축과 최적화를 우선적으로 진행하세요.")
            elif content_type == 'script':
                recommendations.append("JavaScript 파일이 주요 배출원입니다. 코드 분할과 지연 로딩을 고려해보세요.")
        
        # 기본 권장사항이 없으면 일반적인 조언 추가
        if not recommendations:
            recommendations.extend([
                "현재 웹사이트의 탄소 배출량이 양호한 수준입니다.",
                "지속적인 모니터링을 통해 환경 친화적인 웹사이트를 유지하세요."
            ])
        
        return recommendations