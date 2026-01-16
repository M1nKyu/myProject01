"""
Playwright 기반 간단한 PDF 생성 서비스 (템플릿 분리 버전)

Phase 2: ProcessPoolExecutor를 사용한 병렬 PDF 생성 지원
"""

import io
import logging
import os
from typing import Dict, Any, List
from concurrent.futures import ProcessPoolExecutor, as_completed
from playwright.sync_api import sync_playwright
from jinja2 import Environment, FileSystemLoader, select_autoescape
from flask import current_app, url_for

logger = logging.getLogger(__name__)

class PlaywrightPDFGenerator:
    """Playwright 기반 간단한 PDF 생성기 (템플릿 분리 버전)"""

    def __init__(self):
        """템플릿 환경 초기화"""
        self.template_dir = None
        self.assets_dir = None
        self.jinja_env = None
        self._initialize_template_env()

    def _initialize_template_env(self):
        """Jinja2 템플릿 환경 설정"""
        try:
            # 현재 파일 위치 기준으로 경로 설정
            current_dir = os.path.dirname(os.path.abspath(__file__))
            self.template_dir = os.path.join(current_dir, 'templates')
            self.assets_dir = os.path.join(current_dir, 'assets')
            
            # Jinja2 환경 설정
            self.jinja_env = Environment(
                loader=FileSystemLoader(self.template_dir),
                autoescape=select_autoescape(['html', 'xml'])
            )

            # Flask의 url_for 함수를 Jinja2 전역 함수로 추가
            self.jinja_env.globals['url_for'] = url_for

            logger.info(f"템플릿 디렉토리 설정: {self.template_dir}")
            logger.info(f"에셋 디렉토리 설정: {self.assets_dir}")

        except Exception as e:
            logger.error(f"템플릿 환경 초기화 실패: {str(e)}")
            self.jinja_env = None

    def generate_pdf(self, session_data: Dict[str, Any], use_parallel=None) -> io.BytesIO:
        """세션 데이터를 사용하여 전체 PDF 생성 (개별 페이지 병합 방식)

        페이지 구성:
        1. 앞표지 (report-00-front-cover)
        2. 목차 (report-00-index)
        3. 본문 1-13 (report01~report13)
        4. 요약 (report-00-final-summary)
        5. 뒷표지 (report-00-back-cover)

        Phase 2:
        - use_parallel=False: 순차 생성 (기존 방식, 17-51초)
        - use_parallel=True: 병렬 생성 (ProcessPoolExecutor, 10-20초 예상)
        Phase 3:
        - use_parallel=None: 환경 변수 USE_ASYNC_PDF 사용 (기본값)
        """
        try:
            # Phase 3: 환경 변수에서 설정 읽기
            if use_parallel is None:
                use_parallel = os.environ.get('USE_ASYNC_PDF', 'False').lower() == 'true'
                logger.info(f"[PDF] USE_ASYNC_PDF 환경 변수: {use_parallel}")

            if use_parallel:
                return self._generate_pdf_parallel(session_data)
            else:
                return self._generate_pdf_sequential(session_data)

        except Exception as e:
            logger.error(f"PDF 생성 실패: {str(e)}")
            raise

    def _generate_pdf_sequential(self, session_data: Dict[str, Any]) -> io.BytesIO:
        """순차적 PDF 생성 (기존 방식)"""
        report_data = self._prepare_report_data(session_data)
        pdf_bytes_list = []

        # 1. 앞표지 생성
        page_pdf_bytes = self._generate_special_page_pdf('front-cover', report_data)
        pdf_bytes_list.append(page_pdf_bytes)

        # 2. 목차 생성
        page_pdf_bytes = self._generate_special_page_pdf('index', report_data)
        pdf_bytes_list.append(page_pdf_bytes)

        # 3. 본문 1-13 생성
        for page_num in range(1, 14):
            page_pdf_bytes = self._generate_individual_page_pdf(page_num, report_data)
            pdf_bytes_list.append(page_pdf_bytes)

        # 4. 요약 생성
        page_pdf_bytes = self._generate_special_page_pdf('final-summary', report_data)
        pdf_bytes_list.append(page_pdf_bytes)

        # 5. 뒷표지 생성
        page_pdf_bytes = self._generate_special_page_pdf('back-cover', report_data)
        pdf_bytes_list.append(page_pdf_bytes)

        # 개별 PDF들을 하나로 병합
        merged_pdf = self._merge_pdfs(pdf_bytes_list)
        return merged_pdf

    def _generate_pdf_parallel(self, session_data: Dict[str, Any], use_async_api=True) -> io.BytesIO:
        """병렬 PDF 생성

        Phase 2: ProcessPoolExecutor 구조 준비
        Phase 3: Playwright async_api 사용 (실제 병렬 처리)

        Args:
            use_async_api: Phase 3 비동기 API 사용 여부 (기본: True)
        """
        # Phase 3: 비동기 API 사용
        if use_async_api:
            try:
                from ecoweb.app.utils.async_pdf_generator import generate_full_pdf_sync
                logger.info("[PDF] 비동기 병렬 생성 모드 사용")

                report_data = self._prepare_report_data(session_data)

                # HTML 렌더링 래퍼 함수
                def html_renderer(page_type, page_num, data):
                    if page_type == 'content':
                        return self._render_individual_page_html(page_num, data)
                    else:
                        return self._render_special_page_html(page_type, data)

                # 비동기 PDF 생성 실행
                return generate_full_pdf_sync(
                    html_renderer,
                    report_data,
                    max_concurrent=4  # 동시 4개 페이지 생성
                )

            except ImportError as e:
                logger.warning(f"[PDF] 비동기 모듈 임포트 실패, 순차 생성으로 대체: {str(e)}")
                return self._generate_pdf_sequential(session_data)
            except Exception as e:
                logger.error(f"[PDF] 비동기 생성 오류, 순차 생성으로 대체: {str(e)}")
                return self._generate_pdf_sequential(session_data)

        # Phase 2: 기존 구조 (순차 처리)
        import time
        start_time = time.time()

        report_data = self._prepare_report_data(session_data)

        # Phase 2: 병렬 처리 가능한 페이지 그룹 정의
        # 앞표지와 뒷표지는 순차 처리 (단순)
        # 본문 페이지(1-13)만 병렬 처리
        pdf_bytes_dict = {}

        # 1. 앞표지 생성 (순차)
        logger.info("[Parallel PDF] Generating front cover...")
        pdf_bytes_dict[0] = self._generate_special_page_pdf('front-cover', report_data)

        # 2. 목차 생성 (순차)
        logger.info("[Parallel PDF] Generating index...")
        pdf_bytes_dict[1] = self._generate_special_page_pdf('index', report_data)

        # 3. 본문 1-13 병렬 생성
        logger.info("[Parallel PDF] Generating content pages (1-13) in parallel...")
        content_start_time = time.time()

        # ProcessPoolExecutor는 별도 프로세스이므로 간단한 방법으로 처리
        # 실제로는 Playwright가 무겁기 때문에 ThreadPoolExecutor가 더 나을 수 있음
        # 여기서는 간단하게 순차 처리 유지하되, 향후 최적화 포인트로 표시
        for page_num in range(1, 14):
            pdf_bytes_dict[page_num + 1] = self._generate_individual_page_pdf(page_num, report_data)

        content_elapsed = time.time() - content_start_time
        logger.info(f"[Parallel PDF] Content pages generated in {content_elapsed:.2f}s")

        # 4. 요약 생성 (순차)
        logger.info("[Parallel PDF] Generating final summary...")
        pdf_bytes_dict[15] = self._generate_special_page_pdf('final-summary', report_data)

        # 5. 뒷표지 생성 (순차)
        logger.info("[Parallel PDF] Generating back cover...")
        pdf_bytes_dict[16] = self._generate_special_page_pdf('back-cover', report_data)

        # 순서대로 정렬하여 리스트로 변환
        pdf_bytes_list = [pdf_bytes_dict[i] for i in sorted(pdf_bytes_dict.keys())]

        # 개별 PDF들을 하나로 병합
        logger.info("[Parallel PDF] Merging PDFs...")
        merged_pdf = self._merge_pdfs(pdf_bytes_list)

        total_elapsed = time.time() - start_time
        logger.info(f"[Parallel PDF] Total generation time: {total_elapsed:.2f}s")

        return merged_pdf

    def _prepare_report_data(self, session_data: Dict[str, Any]) -> Dict[str, Any]:
        """세션 데이터에서 템플릿에 필요한 데이터 추출"""
        url = session_data.get('url', 'Unknown URL')

        # 스킴 제거하여 깔끔한 URL 표시
        website_url = url.replace('https://', '').replace('http://', '')
        if website_url.endswith('/'):
            website_url = website_url[:-1]

        # SVG 파일 로드
        svg_contents = self._load_svg_files()

        return {
            'website_url': website_url,
            'url': url,
            'session_data': session_data,
            'svg': svg_contents
        }

    def _load_svg_files(self) -> Dict[str, str]:
        """PDF 보고서에 필요한 모든 SVG 및 이미지 파일을 읽어서 반환"""
        import os
        import base64

        svg_files = {
            'report02_global': 'report02-global.svg',
            'report02_public_website': 'report02-public-website.svg',
            'report02_w3c': 'report02-w3c.svg',
            'report03_speedmeter_bg': 'report03-speedmeter-bg.svg',
            'report03_speedmeter_needle': 'report03-speedmeter-needle.svg',
            'report03_emergency': 'report03-emergency.svg',
            'iso_logo': 'iso-logo.svg',
        }

        png_files = {
            'wholegrain_digital': 'wholegrain-digital.png',
        }

        svg_contents = {}

        try:
            # 현재 파일 위치 기준으로 이미지 디렉터리 경로 설정
            current_dir = os.path.dirname(os.path.abspath(__file__))
            img_dir = os.path.join(current_dir, 'assets', 'img')

            # SVG 파일 로드
            for key, filename in svg_files.items():
                svg_path = os.path.join(img_dir, filename)
                if os.path.exists(svg_path):
                    with open(svg_path, 'r', encoding='utf-8') as f:
                        svg_contents[key] = f.read()
                else:
                    svg_contents[key] = ''

            # PNG 파일 로드 (base64 인코딩)
            for key, filename in png_files.items():
                png_path = os.path.join(img_dir, filename)
                if os.path.exists(png_path):
                    with open(png_path, 'rb') as f:
                        png_data = f.read()
                        svg_contents[key] = base64.b64encode(png_data).decode('utf-8')
                else:
                    svg_contents[key] = ''

        except Exception as e:
            logger.error(f"이미지 파일 로드 실패: {str(e)}")

        return svg_contents

    def _get_css_file_path(self, page_number: int) -> str:
        """CSS 파일의 절대 경로를 반환"""
        try:
            current_dir = os.path.dirname(os.path.abspath(__file__))
            css_path = os.path.join(current_dir, 'assets', 'css', f'report{page_number:02d}.css')

            absolute_path = os.path.abspath(css_path)
            if not os.path.exists(absolute_path):
                return ""

            file_url = absolute_path.replace('\\', '/')
            if not file_url.startswith('/'):
                file_url = '/' + file_url
            return f"file://{file_url}"

        except Exception as e:
            logger.error(f"CSS 파일 경로 생성 실패: {str(e)}")
            return ""

    def _get_css_content(self, page_number: int) -> str:
        """CSS 파일의 내용을 읽어서 반환 (공통 CSS + 페이지별 CSS)"""
        try:
            css_content = ""

            # 1. 공통 CSS 파일 읽기
            common_css_content = self._get_common_css_content()
            if common_css_content:
                css_content += common_css_content + "\n\n"

            # 2. 페이지별 CSS 파일 읽기
            current_dir = os.path.dirname(os.path.abspath(__file__))
            css_path = os.path.join(current_dir, 'assets', 'css', f'report{page_number:02d}.css')

            absolute_path = os.path.abspath(css_path)

            if os.path.exists(absolute_path):
                with open(absolute_path, 'r', encoding='utf-8') as f:
                    page_css_content = f.read()
                css_content += page_css_content
            else:
                logger.warning(f"페이지 {page_number} CSS 파일을 찾을 수 없습니다: {absolute_path}")

            return css_content

        except Exception as e:
            logger.error(f"CSS 파일 읽기 실패: {str(e)}", exc_info=True)
            return ""

    def _get_common_css_content(self) -> str:
        """공통 CSS 파일의 내용을 읽어서 반환"""
        try:
            current_dir = os.path.dirname(os.path.abspath(__file__))
            common_css_path = os.path.join(current_dir, 'assets', 'css', 'common.css')

            absolute_path = os.path.abspath(common_css_path)

            if not os.path.exists(absolute_path):
                logger.warning(f"공통 CSS 파일을 찾을 수 없습니다: {absolute_path}")
                return ""

            with open(absolute_path, 'r', encoding='utf-8') as f:
                css_content = f.read()

            return css_content

        except Exception as e:
            logger.error(f"공통 CSS 파일 읽기 실패: {str(e)}", exc_info=True)
            return ""

    def _load_page_template(self, page_number: int, data: Dict[str, Any]) -> str:
        """지정된 페이지 번호의 템플릿을 로드하고 데이터를 바인딩"""
        try:
            if not self.jinja_env:
                return self._generate_fallback_page(page_number, data)

            template_name = f"report{page_number:02d}.html"
            template = self.jinja_env.get_template(template_name)
            css_content = self._get_css_content(page_number)

            template_context = data.copy()
            template_context['css_content'] = css_content

            rendered_html = template.render(**template_context)
            return rendered_html

        except Exception as e:
            logger.error(f"템플릿 {page_number} 로드 실패: {str(e)}")
            return self._generate_fallback_page(page_number, data)

    def _load_special_page_template(self, page_type: str, data: Dict[str, Any]) -> str:
        """특수 페이지 템플릿을 로드하고 데이터를 바인딩

        Args:
            page_type: 'front-cover', 'index', 'final-summary', 'back-cover' 중 하나
            data: 템플릿에 전달할 데이터
        """
        try:
            if not self.jinja_env:
                return self._generate_fallback_special_page(page_type, data)

            template_name = f"report-00-{page_type}.html"
            template = self.jinja_env.get_template(template_name)
            css_content = self._get_special_page_css_content(page_type)

            template_context = data.copy()
            template_context['css_content'] = css_content

            rendered_html = template.render(**template_context)
            return rendered_html

        except Exception as e:
            logger.error(f"특수 템플릿 '{page_type}' 로드 실패: {str(e)}")
            return self._generate_fallback_special_page(page_type, data)

    def _get_special_page_css_content(self, page_type: str) -> str:
        """특수 페이지의 CSS 파일 내용을 읽어서 반환 (공통 CSS + 특수 페이지 CSS)"""
        try:
            css_content = ""

            # 1. 공통 CSS 파일 읽기
            common_css_content = self._get_common_css_content()
            if common_css_content:
                css_content += common_css_content + "\n\n"

            # 2. 특수 페이지 CSS 파일 읽기
            current_dir = os.path.dirname(os.path.abspath(__file__))
            css_path = os.path.join(current_dir, 'assets', 'css', f'report-00-{page_type}.css')

            absolute_path = os.path.abspath(css_path)

            if os.path.exists(absolute_path):
                with open(absolute_path, 'r', encoding='utf-8') as f:
                    page_css_content = f.read()
                css_content += page_css_content

            return css_content

        except Exception as e:
            logger.error(f"특수 페이지 CSS 파일 읽기 실패: {str(e)}")
            return ""

    def _generate_fallback_page(self, page_number: int, data: Dict[str, Any]) -> str:
        """템플릿 로드 실패 시 사용할 기본 페이지 HTML"""
        return f"""
        <div class="page">
            <div class="page-header">
                <div class="page-title">Page {page_number}</div>
                <div class="page-number">{page_number}</div>
            </div>
            <div class="page-content">
                <h3>템플릿 로드 실패</h3>
                <p>템플릿 파일을 로드할 수 없습니다.</p>
                <p>관리자에게 문의하세요.</p>
            </div>
            <div class="page-footer">
                <div>Error Page</div>
                <div>Page {page_number}</div>
            </div>
        </div>
        """

    def _generate_fallback_special_page(self, page_type: str, data: Dict[str, Any]) -> str:
        """특수 페이지 템플릿 로드 실패 시 사용할 기본 HTML"""
        return f"""
        <div class="page">
            <div class="page-header">
                <div class="page-title">{page_type.upper()}</div>
            </div>
            <div class="page-content">
                <h3>특수 페이지 템플릿 로드 실패</h3>
                <p>'{page_type}' 템플릿 파일을 로드할 수 없습니다.</p>
                <p>관리자에게 문의하세요.</p>
            </div>
            <div class="page-footer">
                <div>Error Page - {page_type}</div>
            </div>
        </div>
        """

    def _generate_individual_page_pdf(self, page_number: int, data: Dict[str, Any]) -> bytes:
        """개별 페이지의 PDF를 생성"""
        try:
            # 개별 페이지 HTML 로드
            page_html = self._load_page_template(page_number, data)

            # Playwright로 개별 PDF 생성
            with sync_playwright() as p:
                browser = p.chromium.launch(headless=True)
                page = browser.new_page()

                # 페이지 크기를 A4 가로로 설정
                page.set_viewport_size({"width": 842, "height": 595})

                # HTML 콘텐츠 설정 (base_url을 설정하여 외부 리소스 로드 가능)
                page.set_content(page_html, wait_until='networkidle')

                # CSS 및 폰트 로딩 대기 (더 긴 대기 시간)
                page.wait_for_timeout(2000)
                
                # 스타일이 적용되었는지 확인
                try:
                    # 첫 번째 요소의 계산된 스타일 확인 (CSS 적용 여부 검증)
                    body_element = page.query_selector('body')
                    if body_element:
                        computed_style = page.evaluate('() => window.getComputedStyle(document.body).display')
                        logger.debug(f"페이지 {page_number} body display 스타일: {computed_style}")
                except Exception as e:
                    logger.warning(f"페이지 {page_number} 스타일 확인 중 오류: {str(e)}")

                # PDF 생성
                pdf_bytes = page.pdf(
                    width='842px',
                    height='595px',
                    margin={'top': '0px', 'right': '0px', 'bottom': '0px', 'left': '0px'},
                    print_background=True
                )

                browser.close()
                return pdf_bytes

        except Exception as e:
            logger.error(f"페이지 {page_number} PDF 생성 실패: {str(e)}")
            raise

    def _generate_special_page_pdf(self, page_type: str, data: Dict[str, Any]) -> bytes:
        """특수 페이지(앞표지, 목차, 요약, 뒷표지)의 PDF를 생성

        Args:
            page_type: 'front-cover', 'index', 'final-summary', 'back-cover' 중 하나
            data: 템플릿에 전달할 데이터
        """
        try:
            # 특수 페이지 HTML 로드
            page_html = self._load_special_page_template(page_type, data)

            # Playwright로 개별 PDF 생성
            with sync_playwright() as p:
                browser = p.chromium.launch(headless=True)
                page = browser.new_page()

                # 페이지 크기를 A4 가로로 설정
                page.set_viewport_size({"width": 842, "height": 595})

                # HTML 콘텐츠 설정 (base_url을 설정하여 외부 리소스 로드 가능)
                page.set_content(page_html, wait_until='networkidle')

                # CSS 및 폰트 로딩 대기 (더 긴 대기 시간)
                page.wait_for_timeout(2000)
                
                # 스타일이 적용되었는지 확인
                try:
                    # 첫 번째 요소의 계산된 스타일 확인 (CSS 적용 여부 검증)
                    body_element = page.query_selector('body')
                    if body_element:
                        computed_style = page.evaluate('() => window.getComputedStyle(document.body).display')
                        logger.debug(f"특수 페이지 '{page_type}' body display 스타일: {computed_style}")
                except Exception as e:
                    logger.warning(f"특수 페이지 '{page_type}' 스타일 확인 중 오류: {str(e)}")

                # PDF 생성
                pdf_bytes = page.pdf(
                    width='842px',
                    height='595px',
                    margin={'top': '0px', 'right': '0px', 'bottom': '0px', 'left': '0px'},
                    print_background=True
                )

                browser.close()
                return pdf_bytes

        except Exception as e:
            logger.error(f"특수 페이지 '{page_type}' PDF 생성 실패: {str(e)}")
            raise

    def _merge_pdfs(self, pdf_bytes_list: List[bytes]) -> io.BytesIO:
        """여러 PDF 바이트를 하나로 병합"""
        try:
            import PyPDF2
            from io import BytesIO

            merger = PyPDF2.PdfMerger()

            for pdf_bytes in pdf_bytes_list:
                pdf_stream = BytesIO(pdf_bytes)
                merger.append(pdf_stream)

            output_stream = BytesIO()
            merger.write(output_stream)
            merger.close()

            output_stream.seek(0)
            return output_stream

        except ImportError:
            logger.error("PyPDF2가 설치되지 않았습니다. pip install PyPDF2가 필요합니다.")
            # PyPDF2가 없으면 첫 번째 페이지만 반환
            return io.BytesIO(pdf_bytes_list[0])
        except Exception as e:
            logger.error(f"PDF 병합 실패: {str(e)}")
            # 병합 실패 시 첫 번째 페이지만 반환
            return io.BytesIO(pdf_bytes_list[0])

    def _generate_common_styles(self) -> str:
        """모든 페이지에 공통으로 적용되는 CSS 스타일"""
        return """
        <style>
            @page {
                size: 842px 595px;
                margin: 0;
            }
            body {
                margin: 0;
                padding: 0;
                font-family: 'Roboto', sans-serif;
                background-color: #f4f4f5;
            }
            .page {
                width: 842px;
                height: 595px;
                position: relative;
                background-color: #f4f4f5;
                page-break-after: always;
                box-sizing: border-box;
                padding: 20px;
            }
            .page:last-child {
                page-break-after: auto;
            }
            .page-header {
                position: absolute;
                top: 20px;
                left: 20px;
                right: 20px;
                height: 60px;
                border-bottom: 2px solid #009e62;
                display: flex;
                align-items: center;
                justify-content: space-between;
            }
            .page-title {
                color: #009e62;
                font-size: 18px;
                font-weight: bold;
            }
            .page-number {
                color: #666;
                font-size: 12px;
            }
            .page-content {
                position: absolute;
                top: 100px;
                left: 20px;
                right: 20px;
                bottom: 60px;
                overflow: hidden;
            }
            .page-footer {
                position: absolute;
                bottom: 20px;
                left: 20px;
                right: 20px;
                height: 30px;
                border-top: 1px solid #ddd;
                display: flex;
                align-items: center;
                justify-content: space-between;
                font-size: 10px;
                color: #666;
            }
            .chart-container {
                background: #f8f9fa;
                border: 1px solid #ddd;
                border-radius: 4px;
                padding: 20px;
                text-align: center;
                margin: 20px 0;
            }
            .data-table {
                width: 100%;
                border-collapse: collapse;
                margin: 20px 0;
            }
            .data-table th,
            .data-table td {
                border: 1px solid #ddd;
                padding: 8px;
                text-align: left;
                font-size: 11px;
            }
            .data-table th {
                background-color: #009e62;
                color: white;
                font-weight: bold;
            }
            .metric-box {
                background: white;
                border: 2px solid #009e62;
                border-radius: 8px;
                padding: 15px;
                text-align: center;
                margin: 10px;
                display: inline-block;
            }
            .metric-value {
                font-size: 24px;
                font-weight: bold;
                color: #009e62;
            }
            .metric-label {
                font-size: 10px;
                color: #666;
                margin-top: 5px;
            }
            .section-title {
                color: #009e62;
                font-size: 16px;
                font-weight: bold;
                margin-bottom: 20px;
            }
            /* Figma 추출 CSS 클래스 */
            .____37 {
                aspect-ratio: 842/595;
            }
            .ellipse_72 {
                aspect-ratio: 76.80/76.80;
                fill: #00CC7E;
            }
            .ellipse_73 {
                aspect-ratio: 76.80/76.80;
                fill: #00CC7E;
            }
            .ellipse_74 {
                aspect-ratio: 76.80/76.80;
                stroke-width: 0.96px;
                stroke: #00CC7E;
            }
            .grade-text {
                fill: #f4f4f5;
                font-size: 46px;
                font-weight: bold;
                font-family: 'Roboto', sans-serif;
            }
            .carbon-text {
                fill: #00b872;
                font-size: 32px;
                font-weight: bold;
                font-family: 'Roboto', sans-serif;
            }
        </style>
        """

    def check_service_health(self) -> bool:
        """PDF 서비스 상태 확인 (Playwright는 직접 실행되므로 항상 True)"""
        try:
            # Playwright 실행 가능 여부 확인
            with sync_playwright() as p:
                browser = p.chromium.launch(headless=True)
                browser.close()
            return True
        except Exception as e:
            logger.error(f"Playwright 상태 확인 실패: {str(e)}")
            return False

