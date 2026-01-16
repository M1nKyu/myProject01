import os
from pathlib import Path
from datetime import datetime
from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.common.by import By
import hashlib
import time # time.sleep()을 위해 추가
import asyncio
from functools import wraps

class WebsiteCapture:
    def __init__(self):
        # 캡처 이미지 저장 경로를 var/captures 경로로 설정
        from ecoweb.config import Config
        self.captures_dir = Path(Config.CAPTURE_FOLDER)
        
        # 캡처 저장 디렉토리 생성
        if not os.path.exists(self.captures_dir):
            os.makedirs(self.captures_dir)
            
        # 이벤트 루프별 세마포어를 저장할 딕셔너리 (동일 루프 내 동시성 제어)
        self.semaphores = {}

    def _create_driver(self):
        options = webdriver.ChromeOptions()
        options.add_argument('--headless=new')
        options.add_argument('--no-sandbox')
        options.add_argument('--disable-dev-shm-usage')
        options.add_argument('--disable-gpu')
        # Phase 3 수정: Playwright와 포트 충돌 방지 (9222 → 랜덤 포트)
        options.add_argument('--remote-debugging-port=0')  # 랜덤 포트 사용
        options.add_argument('--window-size=1920,1080')

        # Phase 3 수정: 추가 안정성 옵션
        options.add_argument('--disable-software-rasterizer')
        options.add_argument('--disable-extensions')
        options.add_argument('--disable-setuid-sandbox')
        options.add_argument('--single-process')  # 멀티프로세스 충돌 방지

        chrome_binary = os.environ.get('CHROME_BIN')
        if chrome_binary:
            options.binary_location = chrome_binary

        chromedriver_path = os.environ.get('CHROMEDRIVER_PATH', '/usr/bin/chromedriver')
        service = Service(executable_path=chromedriver_path)

        # Phase 3 수정: 재시도 로직 추가 (빠른 실패)
        max_retries = 2  # 3→2로 감소 (타임아웃 방지)
        for attempt in range(max_retries):
            try:
                driver = webdriver.Chrome(service=service, options=options)
                # 드라이버 생성 성공 시 즉시 반환
                return driver
            except Exception as e:
                error_msg = str(e).lower()
                # 복구 불가능한 오류는 즉시 실패
                if 'session deleted' in error_msg or 'disconnected' in error_msg:
                    print(f"[드라이버 생성 실패] 복구 불가능한 오류: {str(e)[:100]}")
                    raise

                if attempt < max_retries - 1:
                    print(f"[드라이버 생성 재시도 {attempt + 1}/{max_retries}]: {str(e)[:100]}")
                    time.sleep(1)  # 2초→1초로 감소
                else:
                    print(f"[드라이버 생성 최종 실패]: {str(e)[:100]}")
                    raise

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

        # task_id가 있으면 파일명 접두에 짧은 태스크 구분자 추가(가독성)
        if task_id:
            short_tid = hashlib.md5(task_id.encode()).hexdigest()[:6]
            return f"{short_tid}_{base}"
        return base

    async def capture_with_highlight(self, url: str, user_id: str = None, task_id: str = None) -> dict:
        loop = asyncio.get_running_loop()
        if loop not in self.semaphores:
            self.semaphores[loop] = asyncio.Semaphore(1)
        semaphore = self.semaphores[loop]

        # 세마포어를 사용하여 동시 접근 제한
        async with semaphore:
            driver = None
            try:
                # Phase 4 수정: 드라이버 생성 타임아웃 추가
                driver = self._create_driver()

                # Phase 4 수정: 페이지 로드 타임아웃 단축 (10초 → 8초)
                driver.set_page_load_timeout(8)

                # 웹사이트 로드
                driver.get(url)

                # 페이지가 완전히 로드될 때까지 최대 5초 대기 (10초 → 5초)
                WebDriverWait(driver, 5).until(
                    lambda d: d.execute_script('return document.readyState') == 'complete'
                )

                # 이미지에 붉은색 오버레이와 테두리 추가
                driver.execute_script("""
                    document.querySelectorAll('img').forEach(img => {
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
                    });
                """)

                # Phase 4 수정: 스타일 반영 대기 시간 단축 (3초 → 2초)
                time.sleep(2)

                # 파일명 생성 및 저장 (사용자 ID/태스크 ID 포함)
                filename_only = self.generate_filename(url, user_id, task_id)
                # 태스크별 디렉토리 생성
                target_dir = self.captures_dir / (task_id if task_id else '')
                if not os.path.exists(target_dir):
                    os.makedirs(target_dir, exist_ok=True)
                filepath = target_dir / filename_only

                # 스크린샷 저장
                driver.save_screenshot(str(filepath))

                return {
                    "success": True,
                    "filepath": str(filepath),
                    # 템플릿/호출부에서 'captures/<returned>' 형태로 사용할 수 있게 하위 경로 반환
                    "filename": str(Path(task_id) / filename_only) if task_id else filename_only
                }

            except Exception as e:
                error_msg = str(e)
                return {
                    "success": False,
                    "error": error_msg[:200]  # 에러 메시지 길이 제한
                }
            finally:
                # Phase 4 수정: 드라이버 리소스 정리 강화
                if driver:
                    try:
                        driver.quit()
                    except Exception as cleanup_err:
                        print(f"[드라이버 정리 오류] {str(cleanup_err)[:50]}")
                        pass
