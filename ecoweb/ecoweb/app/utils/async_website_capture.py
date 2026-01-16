"""
비동기 웹사이트 캡처 (Phase 4)

Playwright async_api를 사용한 완전 비동기 스크린샷 생성
Selenium 대체로 성능 및 안정성 향상
"""
import os
from pathlib import Path
from datetime import datetime
import hashlib
import asyncio
from playwright.async_api import async_playwright
import logging

logger = logging.getLogger(__name__)


class AsyncWebsiteCapture:
    """
    비동기 웹사이트 캡처 (Phase 4)

    Playwright async_api 사용:
    - 완전 비동기 (Worker 블로킹 없음)
    - Selenium보다 빠르고 안정적
    - PDF 생성과 동일한 기술 스택
    """

    def __init__(self):
        # 캡처 이미지 저장 경로
        from ecoweb.config import Config
        self.captures_dir = Path(Config.CAPTURE_FOLDER)

        # 캡처 저장 디렉토리 생성
        if not os.path.exists(self.captures_dir):
            os.makedirs(self.captures_dir)

    def generate_filename(self, url: str, user_id: str = None, task_id: str = None) -> str:
        """URL과 사용자 ID를 기반으로 고유한 파일명 생성"""
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        url_hash = hashlib.md5(url.encode()).hexdigest()[:8]

        # 사용자 ID가 제공된 경우 파일명에 포함
        if user_id:
            user_hash = hashlib.md5(user_id.encode()).hexdigest()[:6]
            base = f"capture_{url_hash}_{user_hash}_{timestamp}.png"
        else:
            random_str = os.urandom(4).hex()
            base = f"capture_{url_hash}_{timestamp}_{random_str}.png"

        # task_id가 있으면 파일명 접두에 짧은 태스크 구분자 추가
        if task_id:
            short_tid = hashlib.md5(task_id.encode()).hexdigest()[:6]
            return f"{short_tid}_{base}"
        return base

    async def capture_with_highlight(
        self,
        url: str,
        user_id: str = None,
        task_id: str = None,
        timeout: int = 10000
    ) -> dict:
        """
        비동기로 웹사이트를 캡처합니다 (이미지 하이라이트 포함)

        Args:
            url: 캡처할 URL
            user_id: 사용자 ID (선택)
            task_id: 태스크 ID (선택)
            timeout: 페이지 로드 타임아웃 (ms, 기본 10초)

        Returns:
            dict: {"success": bool, "filepath": str, "filename": str} or {"success": False, "error": str}
        """
        logger.info(f"[비동기 캡처 시작] {url}")

        try:
            async with async_playwright() as p:
                # Phase 4: Playwright async_api 사용 (성능 최적화)
                browser = await p.chromium.launch(
                    headless=True,
                    args=[
                        '--no-sandbox',
                        '--disable-setuid-sandbox',
                        '--disable-dev-shm-usage',
                        '--disable-gpu',
                        '--disable-software-rasterizer',
                        '--disable-extensions',
                        '--disable-background-networking',
                        '--disable-default-apps',
                        '--disable-sync',
                        '--metrics-recording-only',
                        '--mute-audio',
                        '--no-first-run',
                        '--single-process',
                        '--remote-debugging-port=0'  # 랜덤 포트 (충돌 방지)
                    ]
                )

                try:
                    page = await browser.new_page()

                    # 뷰포트 설정
                    await page.set_viewport_size({"width": 1920, "height": 1080})

                    # 페이지 로드 (Phase 4 최적화: domcontentloaded로 빠른 시작)
                    await page.goto(url, timeout=timeout, wait_until='domcontentloaded')

                    # Lazy loading 이미지 강제 로드 (viewport 내만)
                    await page.evaluate("""
                        () => {
                            const viewportHeight = window.innerHeight;

                            // viewport 내 이미지만 처리 (성능 최적화)
                            document.querySelectorAll('img').forEach(img => {
                                const rect = img.getBoundingClientRect();
                                const isVisible = rect.top < viewportHeight && rect.bottom > 0;

                                if (isVisible) {
                                    // 모든 lazy loading 패턴 처리
                                    if (img.dataset.src) img.src = img.dataset.src;
                                    if (img.dataset.lazySrc) img.src = img.dataset.lazySrc;
                                    if (img.dataset.original) img.src = img.dataset.original;
                                    if (img.dataset.lazy) img.src = img.dataset.lazy;

                                    // loading 속성 강제 변경
                                    img.loading = 'eager';

                                    // lazy loading 클래스 제거
                                    img.classList.remove('lazyload', 'lazy');
                                }
                            });
                        }
                    """)

                    # networkidle 시도 (최대 5초, 실패해도 진행)
                    try:
                        await page.wait_for_load_state('networkidle', timeout=5000)
                    except Exception as e:
                        pass

                    # 최적화 가능한 이미지에만 붉은색 표시 (WebP/AVIF 변환 대상)
                    await page.evaluate("""
                        () => {
                            // 최적화 가능한 확장자 (WebP/AVIF로 변환 가능)
                            const optimizableExtensions = ['.jpg', '.jpeg', '.png', '.gif', '.bmp', '.tiff', '.tif'];

                            // 모든 이미지 리소스 수집 함수
                            const getImageUrl = (img) => {
                                // <img> 태그의 src 또는 data-src
                                return img.src || img.dataset.src || img.dataset.original || img.dataset.lazy || '';
                            };

                            const isOptimizable = (url) => {
                                if (!url) return false;

                                // 이미 최적화된 포맷은 제외
                                const lowerUrl = url.toLowerCase();
                                if (lowerUrl.includes('.webp') || lowerUrl.includes('.avif')) {
                                    return false;
                                }

                                // SVG는 제외 (벡터 포맷)
                                if (lowerUrl.includes('.svg')) {
                                    return false;
                                }

                                // 최적화 가능한 확장자 확인
                                return optimizableExtensions.some(ext => lowerUrl.includes(ext));
                            };

                            // <img> 태그 처리
                            document.querySelectorAll('img').forEach(img => {
                                const imageUrl = getImageUrl(img);

                                if (isOptimizable(imageUrl)) {
                                    const container = document.createElement('div');
                                    container.style.position = 'relative';
                                    container.style.display = 'inline-block';
                                    container.style.border = '3px solid red';
                                    container.style.boxSizing = 'border-box';

                                    img.parentNode.insertBefore(container, img);
                                    container.appendChild(img);

                                    const overlay = document.createElement('div');
                                    overlay.style.position = 'absolute';
                                    overlay.style.top = '0';
                                    overlay.style.left = '0';
                                    overlay.style.width = '100%';
                                    overlay.style.height = '100%';
                                    overlay.style.backgroundColor = 'red';
                                    overlay.style.opacity = '0.3';
                                    overlay.style.pointerEvents = 'none';

                                    container.appendChild(overlay);
                                }
                            });

                            // CSS background-image도 처리 (선택적)
                            document.querySelectorAll('*').forEach(element => {
                                const style = window.getComputedStyle(element);
                                const bgImage = style.backgroundImage;

                                if (bgImage && bgImage !== 'none') {
                                    // url(...) 추출
                                    const urlMatch = bgImage.match(/url\(['"]?([^'"]+)['"]?\)/);
                                    if (urlMatch && urlMatch[1]) {
                                        const bgUrl = urlMatch[1];

                                        if (isOptimizable(bgUrl)) {
                                            // background-image 요소에 테두리 추가
                                            element.style.outline = '3px solid red';
                                            element.style.position = element.style.position || 'relative';

                                            // 오버레이 추가
                                            const overlay = document.createElement('div');
                                            overlay.style.position = 'absolute';
                                            overlay.style.top = '0';
                                            overlay.style.left = '0';
                                            overlay.style.width = '100%';
                                            overlay.style.height = '100%';
                                            overlay.style.backgroundColor = 'red';
                                            overlay.style.opacity = '0.3';
                                            overlay.style.pointerEvents = 'none';
                                            overlay.style.zIndex = '999';

                                            element.appendChild(overlay);
                                        }
                                    }
                                }
                            });

                            console.log('[ECO-WEB] 최적화 가능한 이미지 하이라이트 완료');
                        }
                    """)

                    # 스타일 반영 대기 (비동기)
                    await page.wait_for_timeout(2000)  # 2초

                    # 파일명 생성 및 저장
                    filename_only = self.generate_filename(url, user_id, task_id)
                    target_dir = self.captures_dir / (task_id if task_id else '')
                    if not os.path.exists(target_dir):
                        os.makedirs(target_dir, exist_ok=True)
                    filepath = target_dir / filename_only

                    # 스크린샷 저장 (비동기)
                    # Phase 5 개선: full_page로 전체 화면 캡처 (UI에서 크롭하여 표시)
                    await page.screenshot(
                        path=str(filepath),
                        full_page=True,  # 전체 페이지 캡처 (UI에서 일부만 표시)
                        timeout=15000  # 스크린샷 자체 타임아웃 15초
                    )

                    # Phase 4 수정: 웹 경로는 항상 / 사용 (Windows \ 방지)
                    if task_id:
                        web_filename = f"{task_id}/{filename_only}"
                    else:
                        web_filename = filename_only

                    return {
                        "success": True,
                        "filepath": str(filepath),
                        "filename": web_filename
                    }

                finally:
                    # 브라우저 종료
                    await browser.close()

        except asyncio.TimeoutError:
            error_msg = f"페이지 로드 타임아웃 ({timeout}ms)"
            logger.warning(f"[비동기 캡처 타임아웃] {url}: {error_msg}")
            return {
                "success": False,
                "error": error_msg
            }

        except Exception as e:
            error_msg = str(e)[:200]
            logger.error(f"캡처 실패: {url} - {error_msg}")
            return {
                "success": False,
                "error": error_msg
            }


# 전역 인스턴스
async_website_capture = AsyncWebsiteCapture()
