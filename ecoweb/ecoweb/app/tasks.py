from ecoweb.app.extensions import celery
from flask import current_app, session
from datetime import datetime
import threading
import os
import re
import json
import time
import asyncio
import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry
import urllib3
from pathlib import Path
from . import db
from .services.lighthouse import run_lighthouse, process_report
from .services.subpage_crawling import subpage_crawling
from .services.analysis.analysis_service import perform_detailed_analysis
from .services.resource_size_scanner import total_bytes_for_pages
from .services.analysis.emissions import estimate_emission_per_page, estimate_emission_from_kb
from ecoweb.app.Image_Classification import png2webp
from .services.capture.website import WebsiteCapture
# from .services.capture.async_website import async_website_capture
from .utils.task_cancellation import check_task_cancelled_legacy
from .utils.emission_calculator import EmissionCalculator
from .utils.grade import grade_point, grade_point_by_emission

# SSL 경고 메시지 비활성화 (이미지 다운로드 시 verify=False 사용으로 인한 경고 억제)
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

# ==========================================================================
# 📊 데이터 강화 헬퍼 함수 (Phase 1: Session-to-DB Refactoring)
# ==========================================================================

def _predict_percentile(emission: float) -> int:
    """
    백분위 예측 함수 - EmissionCalculator.predict_percentile()의 래퍼

    선형 보간 방식으로 배출량에 따른 백분위를 예측합니다.

    Args:
        emission: 탄소 배출량 (gCO2e)

    Returns:
        int: 백분위 (1~99)
    """
    return EmissionCalculator.predict_percentile(emission)


def _enrich_view_data(view_data: dict, url: str, mongo_db, resource_doc=None, traffic_doc=None) -> dict:
    """
    모든 파생 데이터를 한 번에 계산하여 view_data를 강화합니다.

    이 함수는 tasks.py의 analyze_url_task()에서 호출되어,
    Lighthouse 분석이 완료된 후 모든 계산을 수행하고 결과를 MongoDB에 저장합니다.

    계산되는 데이터:
    - 탄소 배출량 (carbon_emission)
    - 배출량 등급 (emission_grade, emission_grade_num)
    - 백분위 (emission_percentile)
    - 평균 대비 차이 (korea_diff, global_diff 등)
    - 콘텐츠 유형별 배출량 (content_emission_data)
    - 배출량 분해 데이터 (emissions_breakdown)

    Args:
        view_data: Lighthouse 분석 결과
        url: 분석 대상 URL
        mongo_db: MongoDB 데이터베이스 핸들
        resource_doc: lighthouse_resources_02 문서 (선택적, 없으면 조회)
        traffic_doc: lighthouse_traffic_02 문서 (선택적, 없으면 조회)

    Returns:
        enriched_result: calculated 섹션이 추가된 view_data
    """
    # view_data 복사본 생성 (원본 보존)
    enriched = dict(view_data)

    # [1] 기본 데이터 추출
    total_byte_weight = view_data.get('total_byte_weight', 0)
    kb_weight = total_byte_weight / 1024

    # [2] 탄소 배출량 계산 (KB 기준)
    carbon_emission = round(estimate_emission_from_kb(kb_weight), 2)

    # [3] 등급 계산 (wholegraindigital.com 기준)
    emission_grade = EmissionCalculator.get_emission_grade(carbon_emission)
    emission_grade_num = EmissionCalculator.get_emission_grade_number(carbon_emission)

    # [4] 백분위 계산
    emission_percentile = _predict_percentile(carbon_emission)

    # [5] 평균 배출량 계산
    korea_avg_carbon = round(estimate_emission_per_page(0.00456), 2)  # 한국 평균: 4.56MB
    global_avg_carbon = round(estimate_emission_per_page(0.002344), 2)  # 세계 평균: 2.34MB

    # [6] 평균 대비 차이 계산
    korea_diff = round(korea_avg_carbon - carbon_emission, 2)
    global_diff = round(global_avg_carbon - carbon_emission, 2)
    korea_diff_abs = round(abs(korea_diff), 2)
    global_diff_abs = round(abs(global_diff), 2)

    # [7] 평균 대비 백분율 차이
    if korea_avg_carbon > 0:
        korea_carbon_percentage_diff = round(abs((carbon_emission - korea_avg_carbon) / korea_avg_carbon) * 100)
    else:
        korea_carbon_percentage_diff = 0

    # [8] 비교 상태 (i18n 지원)
    korea_comparison_status = "낮습니다" if korea_diff > 0 else "높습니다"  # DEPRECATED: 한글 하드코딩
    korea_emission_status = "below_avg" if korea_diff > 0 else "above_avg"  # 권장: i18n 키로 사용

    # [9] 콘텐츠 유형별 배출량 데이터 처리
    content_emission_data = []
    try:
        # 전달받은 traffic_doc 사용, 없으면 조회
        if not traffic_doc:
            traffic_doc = mongo_db.lighthouse_traffic_02.find_one({'url': url})
        
        if traffic_doc:
            resource_summary = traffic_doc.get('resourceSummary')
            if resource_summary:
                from .services.analysis.analysis_service import process_content_emission_data
                content_emission_data = process_content_emission_data(resource_summary)
    except Exception as e:
        current_app.logger.warning(f"콘텐츠 배출량 데이터 처리 실패: {e}")
        content_emission_data = []

    # [10] 배출량 분해 데이터 (서버/네트워크/디바이스별)
    emissions_breakdown = {}
    try:
        from .services.analysis.emissions import emissions_breakdown_from_bytes
        emissions_breakdown = emissions_breakdown_from_bytes(total_byte_weight, region='korea')
    except Exception as e:
        current_app.logger.warning(f"배출량 분해 데이터 계산 실패: {e}")

    # [10-1] 콘텐츠 타입별 카운트 데이터 처리 (파이차트용)
    content_count_data = []
    try:
        from urllib.parse import urlparse
        from collections import Counter
        import os
        
        # 전달받은 resource_doc 사용, 없으면 조회
        doc = resource_doc
        if not doc:
            collection_resource = mongo_db.lighthouse_resources_02
            query_candidates = []
            if url:
                query_candidates.append({'url': url})
                stripped = url.replace('https://', '').replace('http://', '')
                query_candidates.append({'url': stripped})
            
            for q in query_candidates:
                try:
                    doc = collection_resource.find_one(
                        q,
                        {'_id': 0, 'networkRequests': 1, 'network_requests': 1, 'timestamp': 1},
                        sort=[('timestamp', -1)]  # 최신 timestamp 우선
                    )
                    if doc:
                        break
                except Exception:
                    continue
        
        if doc:
            requests_list = doc.get('networkRequests') or doc.get('network_requests') or []
            ext_counter = Counter()
            
            # 확장자 매핑 (resourceType 기반)
            resource_type_to_ext = {
                'document': 'html',
                'script': 'js',
                'stylesheet': 'css',
                'image': None,  # URL에서 추출 시도
                'font': None,   # URL에서 추출 시도
                'media': None,  # URL에서 추출 시도
            }
            
            # 일반적인 파일 확장자 목록
            valid_extensions = {
                'png', 'jpg', 'jpeg', 'gif', 'webp', 'svg', 'ico',
                'js', 'css', 'html', 'htm',
                'woff', 'woff2', 'ttf', 'otf', 'eot',
                'pdf', 'json', 'xml', 'txt',
                'mp4', 'mp3', 'webm', 'avi', 'mov',
                'zip', 'rar', 'gz'
            }
            
            for req in requests_list:
                url_val = req.get('url', '')
                if not url_val:
                    continue
                
                try:
                    parsed = urlparse(url_val)
                    path = parsed.path
                    
                    # 확장자 추출
                    ext = None
                    if '.' in path:
                        _, ext_with_dot = os.path.splitext(path)
                        if ext_with_dot:
                            ext = ext_with_dot.lower().lstrip('.')
                    
                    # 확장자가 없으면 resourceType 기반 매핑 시도
                    if not ext:
                        resource_type = (req.get('resourceType') or req.get('resource_type') or '').lower()
                        ext = resource_type_to_ext.get(resource_type)
                    
                    # 유효한 확장자만 카운트
                    if ext and ext in valid_extensions:
                        ext_counter[ext] += 1
                except Exception:
                    continue
            
            # 확장자 라벨 매핑 (표시용)
            ext_label_map = {
                'png': 'PNG', 'jpg': 'JPG', 'jpeg': 'JPG', 'gif': 'GIF', 'webp': 'WEBP',
                'svg': 'SVG', 'ico': 'ICO',
                'js': 'JS', 'css': 'CSS', 'html': 'HTML', 'htm': 'HTML',
                'woff': 'WOFF', 'woff2': 'WOFF2', 'ttf': 'TTF', 'otf': 'OTF', 'eot': 'EOT',
                'pdf': 'PDF', 'json': 'JSON', 'xml': 'XML', 'txt': 'TXT',
                'mp4': 'MP4', 'mp3': 'MP3', 'webm': 'WEBM', 'avi': 'AVI', 'mov': 'MOV',
                'zip': 'ZIP', 'rar': 'RAR', 'gz': 'GZ'
            }
            
            # 카운트가 많은 순으로 정렬하여 상위 항목만 선택
            sorted_exts = sorted(ext_counter.items(), key=lambda x: x[1], reverse=True)
            content_count_data = [
                {'ext': ext, 'label': ext_label_map.get(ext, ext.upper()), 'count': count}
                for ext, count in sorted_exts[:11]  # 최대 11개
            ]
    except Exception as e:
        current_app.logger.warning(f"콘텐츠 카운트 데이터 처리 실패: {e}")
        content_count_data = []

    # [11] calculated 섹션 구성
    # 모든 계산된 데이터를 하나의 섹션에 정리하여 저장
    enriched['calculated'] = {
        # === 기본 측정값 ===
        'carbon_emission': carbon_emission,
        'kb_weight': kb_weight,
        'total_byte_weight': total_byte_weight,

        # === 등급 ===
        'emission_grade': emission_grade,
        'emission_grade_num': emission_grade_num,

        # === 백분위 ===
        'emission_percentile': emission_percentile,

        # === 평균 기준 ===
        'korea_avg_carbon': korea_avg_carbon,
        'global_avg_carbon': global_avg_carbon,

        # === 평균 대비 차이 ===
        'korea_diff': korea_diff,
        'global_diff': global_diff,
        'korea_diff_abs': korea_diff_abs,
        'global_diff_abs': global_diff_abs,

        # === 평균 대비 비율 ===
        'korea_carbon_percentage_diff': korea_carbon_percentage_diff,
        'korea_comparison_status': korea_comparison_status,  # DEPRECATED: 하위 호환성용
        'korea_emission_status': korea_emission_status,  # 권장: i18n 지원

        # === 콘텐츠 유형별 배출량 ===
        'content_emission_data': content_emission_data,

        # === 콘텐츠 타입별 카운트 데이터 (파이차트용) ===
        'content_count_data': content_count_data,

        # === 배출량 분해 데이터 ===
        'emissions_breakdown': emissions_breakdown,

        # === 하위 호환성 (DEPRECATED) ===
        'korea_carbon_emission_grade': emission_grade,  # [Deprecated] use emission_grade
        'world_carbon_emission_grade': emission_grade,  # [Deprecated] use emission_grade
    }

    return enriched

@celery.task(bind=True, ignore_result=True)
def analyze_url_task(self, url, user_id, is_mobile, original_task_id, perform_subpage_crawling=False, existing_view_data=None):
    """
    Celery task to run lighthouse analysis in the background.
    """
    def check_task_cancelled():
        """작업이 취소되었는지 확인하고, 취소된 경우 예외를 발생시킵니다."""
        check_task_cancelled_legacy(original_task_id, current_app.logger)

    try:
        # [2] MongoDB 컬렉션 핸들 준비 및 연결 상태 확인
        try:
            mongo_db = db.get_db()
            # MongoDB 연결 테스트
            mongo_db.list_collection_names()
        except Exception as mongo_error:
            current_app.logger.error(f"분석 실패: MongoDB 연결 실패 - {str(mongo_error)}")
            raise Exception(f"MongoDB 연결 실패: {str(mongo_error)}")
        
        collection_traffic = mongo_db.lighthouse_traffic_02
        collection_resource = mongo_db.lighthouse_resources_02
        collection_measured_urls = mongo_db.measured_urls
        collection_subpage = mongo_db.lighthouse_subpage
        task_results_collection = mongo_db.task_results
        
        # 컬렉션 접근 테스트
        try:
            collection_traffic.find_one({}, limit=1)
            collection_resource.find_one({}, limit=1)
        except Exception as coll_error:
            current_app.logger.error(f"분석 실패: MongoDB 컬렉션 접근 실패 - {str(coll_error)}")
            raise Exception(f"MongoDB 컬렉션 접근 실패: {str(coll_error)}")

        # 초기 취소 확인
        check_task_cancelled()

        # [2-1] MongoDB 데이터 일괄 조회 (최적화: 중복 조회 방지)
        # 같은 URL에 대한 조회를 한 번에 수행하여 재사용
        resource_doc = None
        traffic_doc = None
        lighthouse_timestamp = None
        
        try:
            # URL 정규화 (query_candidates 패턴)
            query_candidates = []
            if url:
                query_candidates.append({'url': url})
                stripped = url.replace('https://', '').replace('http://', '')
                query_candidates.append({'url': stripped})
            
            # lighthouse_resources_02 조회 (network_requests, timestamp)
            for q in query_candidates:
                try:
                    resource_doc = collection_resource.find_one(
                        q,
                        {
                            '_id': 0,
                            'networkRequests': 1,
                            'network_requests': 1,
                            'timestamp': 1
                        },
                        sort=[('timestamp', -1)]  # 최신 timestamp 우선
                    )
                    if resource_doc:
                        # Lighthouse timestamp 추출
                        ts = resource_doc.get('timestamp')
                        if ts:
                            if isinstance(ts, datetime):
                                lighthouse_timestamp = ts.isoformat()
                            elif isinstance(ts, str):
                                lighthouse_timestamp = ts
                        break
                except Exception:
                    continue
            
            # lighthouse_traffic_02 조회 (resourceSummary, audits)
            for q in query_candidates:
                try:
                    traffic_doc = collection_traffic.find_one(
                        q,
                        {
                            '_id': 0,
                            'resourceSummary': 1,
                            'audits': 1
                        },
                        sort=[('timestamp', -1)]  # 최신 timestamp 우선
                    )
                    if traffic_doc:
                        break
                except Exception:
                    continue
        except Exception as e:
            current_app.logger.warning(f"MongoDB 일괄 조회 중 오류 (계속 진행): {e}")
            # 조회 실패해도 작업은 계속 진행 (나중에 개별 조회 시도)

        # [3] Lighthouse 분석 수행 여부 결정
        if existing_view_data:
            # 기존 Lighthouse 데이터 사용
            print(f'[기존 데이터 활용] Lighthouse 측정 생략, 기존 데이터 사용')
            view_data = existing_view_data.copy()
            view_data['url'] = url

            # 진행상황 초기화: 입력 페이지 완료, 하위 페이지 대기중
            try:
                task_results_collection.update_one(
                    {'_id': original_task_id},
                    {'$set': {
                        'progress': {
                            'current_step': 'subpages',
                            'steps': {
                                'input': {'status': 'done', 'message': '기존 Lighthouse 데이터 사용'},
                                'subpages': {'status': 'waiting', 'message': '하위 페이지 분석 대기'}
                            },
                            'updated_at': datetime.utcnow().isoformat()
                        }
                    }}
                )
            except Exception:
                pass
        else:
            # 새로운 Lighthouse 분석 수행
            self.update_state(state='PROGRESS', meta={'status': 'Lighthouse 분석을 시작합니다...'})
            # 진행상황 초기화: 입력 페이지 분석 진행중, 하위 페이지 대기중
            try:
                task_results_collection.update_one(
                    {'_id': original_task_id},
                    {'$set': {
                        'progress': {
                            'current_step': 'input',
                            'steps': {
                                'input': {'status': 'in_progress', 'message': '입력 페이지 분석 시작'},
                                'subpages': {'status': 'waiting', 'message': '하위 페이지 분석 대기'}
                            },
                            'updated_at': datetime.utcnow().isoformat()
                        }
                    }}
                )
            except Exception:
                pass
            timeout = 240 if is_mobile else 120 # 타임아웃 시간을 2배로 늘림
            # Lighthouse 대기 중 하트비트(진행 중 신호) 쓰레드 시작
            _hb_stop = threading.Event()
            def _heartbeat():
                start_ts = time.time()
                while not _hb_stop.is_set():
                    try:
                        # 하트비트 중에도 취소 확인
                        task_doc = task_results_collection.find_one({'_id': original_task_id})
                        if task_doc and task_doc.get('status') == 'CANCELLED':
                            current_app.logger.info(f'Task {original_task_id} cancelled during heartbeat, stopping')
                            _hb_stop.set()
                            break

                        elapsed = int(time.time() - start_ts)
                        task_results_collection.update_one(
                            {'_id': original_task_id},
                            {'$set': {
                                'progress.steps.input': {'status': 'in_progress', 'message': f'Lighthouse 실행 중... ({elapsed}s)'},
                                'progress.current_step': 'input',
                                'progress.updated_at': datetime.utcnow().isoformat()
                            }}
                        )
                    except Exception:
                        pass
                    # 로그도 주기적으로 남김 (stdout)
                    # (간소화) 표준 출력 제거
                    try:
                        _ = elapsed  # no-op
                    except Exception:
                        pass
                    _hb_stop.wait(5.0)
            _hb_thread = threading.Thread(target=_heartbeat, daemon=True)
            _hb_thread.start()
            try:
                # Lighthouse 실행 전 취소 확인
                check_task_cancelled()
                # Lighthouse 재시도 로직 (크래시 방지)
                max_retries = 2
                exit_code = None
                last_error = None
                
                for attempt in range(max_retries):
                    try:
                        exit_code = run_lighthouse(url, timeout)
                        
                        # exit_code가 딕셔너리인 경우 (비동기 모드에서 오류 발생 시)
                        if isinstance(exit_code, dict):
                            if exit_code.get("success", False):
                                exit_code = 0
                                break
                            else:
                                last_error = exit_code.get("error", "Unknown error")
                                if "crashed" not in last_error.lower() and "timeout" not in last_error.lower():
                                    # 크래시나 타임아웃이 아닌 경우 재시도 불필요
                                    raise Exception(f"Lighthouse 분석 실패: {last_error}")
                                if attempt < max_retries - 1:
                                    time.sleep(2)  # 재시도 전 대기
                                    continue
                                else:
                                    raise Exception(f"Lighthouse 분석 실패: {last_error}")
                        elif exit_code == 0:
                            break
                        else:
                            if attempt < max_retries - 1:
                                time.sleep(2)
                                continue
                    except Exception as e:
                        last_error = str(e)
                        if attempt < max_retries - 1:
                            time.sleep(2)
                            continue
                        else:
                            raise
                
                if exit_code is None:
                    raise Exception(f"Lighthouse 분석 실패: {last_error or 'Unknown error'}")
            finally:
                _hb_stop.set()
                try:
                    _hb_thread.join(timeout=2)
                except Exception:
                    pass
            
            # exit_code 최종 검증 (재시도 로직에서 이미 처리되었지만 안전장치)
            if isinstance(exit_code, dict):
                if not exit_code.get("success", False):
                    error_msg = exit_code.get("error", "Unknown error")
                    raise Exception(f"Lighthouse 분석 실패: {error_msg}")
                else:
                    exit_code = 0  # 성공한 경우 0으로 설정
            
            if exit_code != 0:
                raise Exception(f"Lighthouse 분석 실패: 종료 코드 {exit_code}")

            # Lighthouse 완료 후 취소 확인
            check_task_cancelled()
            
            # report.json 파일 생성 여부 확인
            # os는 이미 파일 상단에서 import됨
            report_paths = [
                os.path.join(os.getcwd(), 'report.json'),
                os.path.join('/app', 'report.json'),
                os.path.join('/app/ecoweb', 'report.json'),
                os.path.join('/app/ecoweb/app', 'report.json'),
            ]
            
            report_found = False
            for report_path in report_paths:
                if os.path.exists(report_path):
                    report_found = True
                    break
                
                if not report_found:
                    current_app.logger.error(f"분석 실패: Lighthouse report.json 파일이 생성되지 않았습니다")
                    raise FileNotFoundError("Lighthouse 실행 후 report.json 파일이 생성되지 않았습니다.")

            # [4] Lighthouse 보고서 처리 단계로 상태 업데이트
            self.update_state(state='PROGRESS', meta={'status': 'Lighthouse 보고서를 처리 중입니다...'})
            try:
                task_results_collection.update_one(
                    {'_id': original_task_id},
                    {'$set': {
                        'progress.steps.input': {'status': 'in_progress', 'message': 'Lighthouse 보고서 처리 중'},
                        'progress.current_step': 'input',
                        'progress.updated_at': datetime.utcnow().isoformat()
                    }}
                )
            except Exception:
                pass

            # [5] 보고서 처리 및 view_data 생성
            view_data = process_report(
                url,
                collection_resource,
                collection_traffic,
                collection_measured_urls,
                measured_type="manual",
                measured_cycle="None",
                measured_source="user",
                user_id=user_id,
                is_mobile=is_mobile
            )
            # (간소화) 표준 출력 제거

            # [6] 기본 필드 보정: URL을 view_data에 먼저 할당
            view_data['url'] = url

            # [7] 분석 데이터 유효성 검사
            if not view_data or view_data.get('total_byte_weight', 0) == 0:
                raise ValueError("Lighthouse 분석 결과 데이터가 생성되지 않았습니다.")

        # [8] 옵션: 하위 페이지 크롤링 및 분석 수행
        # 하위 페이지 크롤링 전 취소 확인
        check_task_cancelled()
        self.update_state(state='PROGRESS', meta={'status': '하위 페이지를 크롤링하고 분석합니다...'})
        try:
            # 입력 페이지 단계 완료, 하위 페이지 단계 시작
            task_results_collection.update_one(
                {'_id': original_task_id},
                {'$set': {
                    'progress.steps.input': {'status': 'done', 'message': '입력 페이지 분석 완료'},
                    'progress.steps.subpages': {'status': 'in_progress', 'message': '하위 페이지 분석 중'},
                    'progress.current_step': 'subpages',
                    'progress.updated_at': datetime.utcnow().isoformat()
                }}
            )
        except Exception:
            pass

        # 하위 페이지 크롤링 시간 제한 (60초)
        import signal
        def timeout_handler(signum, frame):
            raise TimeoutError("하위 페이지 크롤링 시간 초과")

        subpages = []
        try:
            # Windows에서는 signal.alarm이 지원되지 않으므로 다른 방법 사용
            if os.name != 'nt':  # Unix/Linux
                signal.signal(signal.SIGALRM, timeout_handler)
                signal.alarm(90)  # 90초 제한

            print(f'[하위페이지 크롤링] 시작: {url} (최대 10페이지)')
            subpages = subpage_crawling(url, collection_subpage, max_pages=10)
            print(f'[하위페이지 크롤링] 완료: {len(subpages) if subpages else 0}개 페이지 발견')

            if os.name != 'nt':
                signal.alarm(0)  # 타이머 해제
        except TimeoutError:
            current_app.logger.warning(f"하위 페이지 크롤링 시간 초과: {url}")
            subpages = []
        except Exception as e:
            current_app.logger.warning(f"하위 페이지 크롤링 실패: {e}")
            subpages = []
        finally:
            if os.name != 'nt':
                signal.alarm(0)  # 타이머 해제

        # 하위 페이지 데이터 처리 및 상태 업데이트 (성공/실패 여부와 관계없이)
        if subpages:
            # 리소스 사이즈 계산 및 병합
            try:
                per_page_sizes = total_bytes_for_pages([s.get('url') for s in subpages if s.get('url')])
                by_url = {p.get('url'): int(p.get('total_bytes') or 0) for p in per_page_sizes.get('per_page', [])}
                for s in subpages:
                    u = s.get('url')
                    if u in by_url:
                        s['total_bytes'] = by_url[u]
                        s['total_kb'] = round(by_url[u] / 1024.0, 2)
            except Exception as e:
                current_app.logger.warning(f"하위 페이지 리소스 크기 계산 실패: {e}")
            view_data['subpages'] = subpages
            current_app.logger.info(f"하위 페이지 수집 완료: URL={url}, 수집 수={len(subpages)}")
        else:
            view_data['subpages'] = []
            current_app.logger.info(f"하위 페이지 수집 실패/시간초과: URL={url}, 수집 수=0")

        # 하위 페이지 단계 완료 상태 업데이트 (항상 실행)
        try:
            status_message = '하위 페이지 분석 완료' if subpages else '하위 페이지 분석 완료 (시간초과 또는 실패)'
            task_results_collection.update_one(
                {'_id': original_task_id},
                {'$set': {
                    'progress.steps.subpages': {'status': 'done', 'message': status_message},
                    'progress.current_step': 'subpages',
                    'progress.updated_at': datetime.utcnow().isoformat()
                }}
            )
        except Exception as e:
            current_app.logger.warning(f"하위 페이지 진행 상태 업데이트 실패: {e}")
        # session['subpages'] = subpages  # Celery 작업 내에서 직접 session에 접근하는 것은 권장되지 않음
            # perform_detailed_analysis(url)

        # [9] 이미지 최적화 및 캡처 작업 실행 (기존 img_optimization 로직 이동)
        # 이미지 최적화 전 취소 확인
        check_task_cancelled()
        try:
            # 진행 상태: 이미지 최적화 시작
            try:
                task_results_collection.update_one(
                    {'_id': original_task_id},
                    {'$set': {
                        'progress.steps.image_opt': {'status': 'in_progress', 'message': '이미지 최적화 중'},
                        'progress.current_step': 'image_opt',
                        'progress.updated_at': datetime.utcnow().isoformat()
                    }}
                )
            except Exception:
                pass
            original_url = url  # 세션 URL 대체
            # 파일 저장용: 스킴 제거 버전
            url_s_stripped = (original_url or '').replace('https://', '').replace('http://', '')
            print(f"[IMAGE_OPT] URL: {original_url}, url_s_stripped: {url_s_stripped}")
            current_app.logger.info(f"[IMAGE_OPT] URL: {original_url}, url_s_stripped: {url_s_stripped}")

            # 1) 이미지 URL 수집: 이미 조회된 resource_doc 재사용 (최적화)
            Image_paths = []
            doc = resource_doc  # 일괄 조회한 데이터 재사용
            lighthouse_timestamp = None
            
            try:
                # resource_doc이 없으면 조회 (fallback)
                if not doc:
                    collection_resource = mongo_db.lighthouse_resources_02
                    query_candidates = []
                    if original_url:
                        query_candidates.append({'url': original_url})
                        stripped = original_url.replace('https://', '').replace('http://', '')
                        query_candidates.append({'url': stripped})
                    
                    # 가장 최신 timestamp의 데이터 조회
                    for q in query_candidates:
                        try:
                            doc = collection_resource.find_one(
                                q, 
                                {'_id': 0, 'networkRequests': 1, 'network_requests': 1, 'timestamp': 1},
                                sort=[('timestamp', -1)]  # 최신 timestamp 우선
                            )
                            if doc:
                                break
                        except Exception as query_error:
                            current_app.logger.error(f"분석 실패: 이미지 URL 조회 오류 - {str(query_error)}")
                
                # Lighthouse timestamp 추출 (이미 조회된 경우 또는 새로 조회한 경우)
                if doc:
                    ts = doc.get('timestamp')
                    if ts:
                        if isinstance(ts, datetime):
                            lighthouse_timestamp = ts.isoformat()
                        elif isinstance(ts, str):
                            lighthouse_timestamp = ts
                
                image_exts = ('.jpg', '.jpeg', '.png', '.webp', '.gif')
                if doc:
                    requests_list = doc.get('networkRequests') or doc.get('network_requests') or []
                    
                    from urllib.parse import urlparse, urljoin
                    target_parsed = urlparse(original_url)
                    target_domain = target_parsed.netloc
                    
                    for item in requests_list:
                        url_val = item.get('url', '')
                        if not url_val:
                            continue
                        
                        # data: URL 스킵 (base64 인코딩된 이미지는 다운로드 불가)
                        if url_val.startswith('data:'):
                            continue
                        
                        # 상대 경로를 절대 URL로 변환
                        if not url_val.startswith(('http://', 'https://')):
                            url_val = urljoin(original_url, url_val)
                        
                        rtype = (item.get('resourceType') or item.get('resource_type') or '').lower()
                        # resourceType이 'image'인 경우만 수집 (확장자 체크는 보조적으로만 사용)
                        is_image = rtype == 'image'
                        
                        # resourceType이 없거나 'image'가 아닌 경우, URL 확장자로 확인
                        if not is_image:
                            is_image = url_val.lower().endswith(image_exts)
                        
                        if is_image:
                            Image_paths.append(url_val)
            except Exception as e:
                current_app.logger.error(f"분석 실패: 이미지 URL 조회 오류 - {str(e)}")

            # 처리 이미지 수 제한
            try:
                max_images = int(os.getenv('IMG_OPT_MAX', '100'))
            except Exception:
                max_images = 100
            if isinstance(Image_paths, list) and len(Image_paths) > max_images:
                Image_paths = Image_paths[:max_images]

            # 저장 경로 준비 (var/optimization_images 사용)
            from ecoweb.config import Config
            image_dir_path = os.path.join(Config.OPTIMIZATION_IMAGES_FOLDER, url_s_stripped)
            if not os.path.exists(image_dir_path):
                os.makedirs(image_dir_path, exist_ok=True)

            # 이미지 캐시 유틸리티 임포트
            from ecoweb.app.utils.image_cache import (
                get_cached_image_info,
                is_cache_valid,
                check_image_changed,
                update_image_cache,
                calculate_file_hash,
                load_cache_metadata
            )
            
            # 캐시 설정 확인
            cache_enabled = Config.IMG_CACHE_ENABLED
            cache_ttl_days = Config.IMG_CACHE_TTL_DAYS

            # 고성능 다운로드: 세션 + 풀 + 병렬 (다운로드 전용)
            downloaded = []
            from concurrent.futures import ThreadPoolExecutor, as_completed
            import ssl as _ssl

            class TLSAdapter(HTTPAdapter):
                def init_poolmanager(self, *args, **kwargs):
                    context = _ssl.SSLContext(_ssl.PROTOCOL_TLS_CLIENT)
                    try:
                        context.set_ciphers('DEFAULT@SECLEVEL=1')
                    except Exception:
                        pass
                    try:
                        context.options |= 0x4  # OP_LEGACY_SERVER_CONNECT
                    except Exception:
                        pass
                    context.check_hostname = False
                    context.verify_mode = _ssl.CERT_NONE
                    kwargs['ssl_context'] = context
                    return super().init_poolmanager(*args, **kwargs)

            retry = Retry(total=3, connect=2, read=1, backoff_factor=0.3, status_forcelist=[429, 500, 502, 503, 504], allowed_methods=["GET"]) 
            dl_session = requests.Session()
            dl_session.headers.update({'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'})
            adapter = TLSAdapter(max_retries=retry, pool_connections=16, pool_maxsize=16)
            dl_session.mount('https://', adapter)
            dl_session.mount('http://', adapter)
            # 컨테이너 환경 변수(프록시 등) 신뢰
            dl_session.trust_env = True

            def download_one(imageurl: str):
                # ThreadPoolExecutor 내부에서는 Flask 애플리케이션 컨텍스트가 없으므로 일반 logging 사용
                import logging
                logger = logging.getLogger(__name__)
                
                # data: URL 스킵 (base64 인코딩된 이미지는 HTTP 요청으로 다운로드 불가)
                if imageurl.startswith('data:'):
                    logger.debug(f"[TASKS] Skipping data: URL: {imageurl[:50]}...")
                    return None
                
                try:
                    # URL에서 파일명 추출 (더 정확한 방법)
                    from urllib.parse import urlparse, unquote
                    parsed = urlparse(imageurl)
                    path = unquote(parsed.path)  # URL 디코딩
                    
                    # 경로에서 파일명 추출
                    if '/' in path:
                        filename = os.path.basename(path)
                    else:
                        filename = path
                    
                    # 파일명이 없거나 확장자가 없는 경우 URL에서 추출 시도
                    if not filename or '.' not in filename:
                        # URL의 마지막 부분 사용
                        path_parts = [p for p in path.split('/') if p]
                        if path_parts:
                            filename = path_parts[-1]
                        else:
                            # URL 전체를 해시하여 파일명 생성
                            import hashlib
                            url_hash = hashlib.md5(imageurl.encode()).hexdigest()[:8]
                            # Content-Type에서 확장자 추출 시도
                            filename = f"image_{url_hash}.jpg"  # 기본값
                    
                    # 파일명 정리 (특수문자 제거)
                    filename = re.sub(r'[<>:"|?*]', '_', filename)
                    if not filename:
                        import hashlib
                        url_hash = hashlib.md5(imageurl.encode()).hexdigest()[:8]
                        filename = f"image_{url_hash}.jpg"
                    
                    destination = os.path.join(image_dir_path, filename)
                    
                    # 캐시 확인 (캐시 활성화 및 Lighthouse timestamp 존재 시)
                    if cache_enabled and lighthouse_timestamp:
                        cached_info = get_cached_image_info(imageurl, url_s_stripped, Config)
                        
                        if cached_info:
                            # 메타데이터에서 Lighthouse timestamp 조회
                            metadata = load_cache_metadata(url_s_stripped, Config)
                            cached_lighthouse_ts = metadata.get('lighthouse_timestamp')
                            
                            if cached_lighthouse_ts:
                                # timestamp 일치 및 TTL 검증
                                timestamp_match, ttl_valid = is_cache_valid(
                                    lighthouse_timestamp,
                                    cached_lighthouse_ts,
                                    cache_ttl_days
                                )
                                
                                # TTL이 유효한 경우 캐시 사용 (timestamp 일치 여부와 무관)
                                # timestamp는 같은 분석 세션인지 확인용이며, TTL 내에서는 캐시 재사용 가능
                                if ttl_valid:
                                    # 이미지 변경 감지 (HEAD 요청)
                                    changed = check_image_changed(
                                        imageurl,
                                        cached_info,
                                        dl_session,
                                        destination if os.path.exists(destination) else None
                                    )
                                    
                                    if not changed:
                                        # 캐시 재사용
                                        if os.path.exists(destination):
                                            file_size = os.path.getsize(destination)
                                            return {
                                                'name': filename,
                                                'path': destination,
                                                'size': file_size,
                                                'url': imageurl,
                                                'cached': True,  # 캐시 재사용 플래그
                                            }
                    
                    # 이미 존재하는 파일인 경우 URL 해시를 추가하여 중복 방지
                    if os.path.exists(destination):
                        import hashlib
                        url_hash = hashlib.md5(imageurl.encode()).hexdigest()[:8]
                        name, ext = os.path.splitext(filename)
                        filename = f"{name}_{url_hash}{ext}"
                        destination = os.path.join(image_dir_path, filename)
                    
                    logger.debug(f"[TASKS] Downloading image: {imageurl} -> {filename}")
                    
                    resp = dl_session.get(imageurl, verify=False, timeout=(3, 8))
                    if resp.status_code != 200:
                        logger.warning(f"[TASKS] Failed to download image: {imageurl} (status: {resp.status_code})")
                        return None
                    
                    # Content-Type 확인
                    content_type = resp.headers.get('Content-Type', '').lower()
                    if 'image' not in content_type:
                        logger.warning(f"[TASKS] Not an image: {imageurl} (Content-Type: {content_type})")
                        return None
                    
                    # ETag 및 Last-Modified 추출
                    etag = resp.headers.get('ETag', '').strip('"')
                    last_modified = resp.headers.get('Last-Modified')
                    
                    with open(destination, 'wb') as f:
                        f.write(resp.content)
                    if not os.path.exists(destination):
                        return None
                    file_size = os.path.getsize(destination)
                    
                    logger.debug(f"[TASKS] Downloaded: {filename} ({file_size} bytes) from {imageurl}")
                    
                    # 캐시 메타데이터 업데이트 (다운로드 완료 후)
                    if cache_enabled and lighthouse_timestamp:
                        update_image_cache(
                            imageurl,
                            url_s_stripped,
                            filename,
                            destination,
                            file_size,
                            lighthouse_timestamp,
                            Config,
                            etag=etag if etag else None,
                            last_modified=last_modified if last_modified else None
                        )
                    
                    return {
                        'name': filename,
                        'path': destination,
                        'size': file_size,
                        'url': imageurl,  # 원본 URL 저장 (디버깅용)
                        'cached': False,  # 새로 다운로드됨
                    }
                except requests.exceptions.RequestException as req_err:
                    logger.warning(f"[TASKS] Request error downloading {imageurl}: {req_err}")
                    return None
                except Exception as e:
                    logger.error(f"[TASKS] Error downloading {imageurl}: {e}")
                    import traceback
                    logger.error(f"[TASKS] Traceback: {traceback.format_exc()}")
                    return None

            max_workers = min(3, len(Image_paths)) if len(Image_paths) > 0 else 0
            cached_count = 0
            download_count = 0
            failed_count = 0
            if max_workers > 0:
                with ThreadPoolExecutor(max_workers=max_workers) as executor:
                    future_map = {executor.submit(download_one, u): u for u in Image_paths}
                    for fut in as_completed(future_map):
                        res = fut.result()
                        if isinstance(res, dict):
                            downloaded.append(res)
                            if res.get('cached'):
                                cached_count += 1
                            else:
                                download_count += 1
                        else:
                            failed_count += 1
            

            # 이미지 파일 정보 수집 (모델 분류 제거: 모든 이미지를 WebP 변환 대상으로 설정)
            files = []
            try:
                sizes = {it['name']: it['size'] for it in downloaded}
                for it in downloaded:
                    # section05에서 표시할 원본 이미지 경로 설정
                    # 원본 이미지는 <url>/<name> 형태로 저장됨
                    # 템플릿에서 var/optimization_images/를 제거하므로 그대로 사용
                    rel_url = f"var/optimization_images/{url_s_stripped}/{it['name']}"
                    
                    files.append({
                        'name': it['name'],
                        'url': rel_url,  # 원본 이미지 경로 (section05 표시용)
                        'size': sizes.get(it['name'], it['size'])
                    })
            except Exception as e:
                current_app.logger.error(f"분석 실패: 이미지 파일 정보 처리 오류 - {str(e)}")
                # 예외 발생 시에도 기본 파일 정보는 유지
                for it in downloaded:
                    files.append({
                        'name': it['name'],
                        'url': f"var/optimization_images/{url_s_stripped}/{it['name']}",
                        'size': it['size']
                    })

            category = {'iconfile': [], 'logofile': [], 'others': []}
            webpfiles = []
            total_downloaded_image_bytes = 0
            eligible_original_image_bytes = 0
            # 모든 이미지를 WebP 변환 대상으로 설정 (모델 분류 제거)
            for fi in files:
                total_downloaded_image_bytes += fi['size']
                webpfiles.append(fi)
                eligible_original_image_bytes += fi['size']
                # 카테고리 분류는 파일명 기반으로만 수행
                if 'ico' in fi['name']:
                    category['iconfile'].append(fi)
                elif 'logo' in fi['name']:
                    category['logofile'].append(fi)
                else:
                    category['others'].append(fi)

            time.sleep(0.5)
            # webp/ 디렉토리로 변경
            webp_output_dir = os.path.join(image_dir_path, 'webp')
            os.makedirs(webp_output_dir, exist_ok=True)
            selected_paths = []
            for f in webpfiles:
                # 원본 이미지 경로 직접 사용 (copied_path 제거)
                original_path = None
                for it in downloaded:
                    if it['name'] == f['name']:
                        original_path = it.get('path')
                        break
                
                if original_path and os.path.exists(original_path):
                    # 이미 WebP 파일인 경우 제외
                    orig_path = Path(original_path)
                    if orig_path.suffix.lower() == '.webp':
                        continue
                    # 이미지 파일만 포함 (PNG, JPG, JPEG)
                    if orig_path.suffix.lower() in ['.png', '.jpg', '.jpeg']:
                        selected_paths.append(original_path)
            # WebP 변환 (변환 과정에서 자동으로 크기가 더 큰 이미지 필터링됨)
            convertedfiles, webp_total_size, success_count, failed_count = png2webp.convert_to_webp(
                image_dir_path, 
                webp_output_dir, 
                selected_files=selected_paths,
                filter_larger=True  # 변환 후 크기가 더 큰 이미지 자동 제외
            )
            
            # webp_name 필드 설정 및 캐시 메타데이터 업데이트 (필터링은 convert_to_webp 내부에서 이미 처리됨)
            for _item in convertedfiles:
                if isinstance(_item, dict):
                    # webp_name이 없으면 name을 사용 (하위 호환성)
                    if 'webp_name' not in _item and 'name' in _item:
                        _item['webp_name'] = _item['name']
                    
                    # WebP 파일의 실제 경로 계산 (단순 파일명 사용)
                    webp_name = _item.get('webp_name', _item.get('name', ''))
                    webp_file_path = os.path.join(webp_output_dir, webp_name)
                    
                    # WebP 정보를 캐시 메타데이터에 업데이트
                    if cache_enabled and lighthouse_timestamp:
                        # 원본 파일명으로 이미지 URL 찾기
                        original_filename = _item.get('original_name') or _item.get('name').replace('.webp', '')
                        for it in downloaded:
                            if it['name'] == original_filename or it['name'].startswith(original_filename):
                                if os.path.exists(webp_file_path):
                                    webp_size = os.path.getsize(webp_file_path)
                                    update_image_cache(
                                        it['url'],
                                        url_s_stripped,
                                        it['name'],
                                        it['path'],
                                        it['size'],
                                        lighthouse_timestamp,
                                        Config,
                                        webp_path=webp_file_path,
                                        webp_size=webp_size
                                    )
                                break
            
            # 필터링된 이미지들의 원본 크기 계산 (convert_to_webp에서 이미 필터링됨)
            filtered_eligible_original_image_bytes = sum(
                item.get('original_size', 0) 
                for item in convertedfiles 
                if isinstance(item, dict)
            )
            eligible_original_image_bytes = filtered_eligible_original_image_bytes
            
            convertedfiles.sort(key=lambda x: x['name'], reverse=False)
            webpfiles.sort(key=lambda x: x['name'], reverse=False)
            time.sleep(0.5)

            # 캡처 수행 (Phase 4: Playwright async로 전환, Worker 블로킹 없음)
            captured_image_path = None
            try:
                # WebsiteCapture 클래스 사용 (Playwright 기반)
                from ecoweb.app.services.capture.website import WebsiteCapture
                website_capture = WebsiteCapture()
                
                # 비동기 함수를 동기적으로 실행
                import asyncio
                async def _capture_task():
                    return await website_capture.capture_with_highlight(
                        f"https://{url_s_stripped}",
                        user_id=str(user_id) if user_id is not None else None,
                        task_id=str(original_task_id) if original_task_id is not None else None
                    )
                capture_result = asyncio.run(_capture_task())
                if capture_result and capture_result.get('success'):
                    captured_image_filename = capture_result.get('filename')
                    # filename may already include task_id subdirectory
                    captured_image_path = f"var/captures/{captured_image_filename}"
            except Exception as e:
                pass  # 캡처 실패는 조용히 처리

            # CO2 절감량 계산
            saved_bytes = int(eligible_original_image_bytes) - int(webp_total_size)
            co2_saved = 0
            if saved_bytes > 0:
                saved_gb = saved_bytes / (1024**3)
                co2_saved = estimate_emission_per_page(saved_gb)

            # 신규 지표 계산 (DB 기반)
            converted_stems = set()
            try:
                from pathlib import Path as _Path
                for _cf in convertedfiles:
                    if isinstance(_cf, dict) and 'name' in _cf:
                        converted_stems.add(_Path(_cf['name']).stem)
            except Exception:
                pass

            db_images = []
            try:
                requests_list = (doc.get('networkRequests') or doc.get('network_requests')) if doc else None
                if requests_list:
                    import urllib.parse as _urlparse
                    for item in requests_list:
                        rtype = (item.get('resourceType') or item.get('resource_type') or '').lower()
                        if rtype != 'image':
                            url_val = item.get('url', '')
                            if not url_val.lower().endswith(('.jpg', '.jpeg', '.png', '.gif', '.webp')):
                                continue
                        url_val = item.get('url', '')
                        try:
                            parsed = _urlparse.urlparse(url_val)
                            basename = os.path.basename(parsed.path)
                        except Exception:
                            parts = re.split(r':|\/|\.', url_val)
                            basename = parts[-2] + '.' + parts[-1] if len(parts) >= 2 else url_val
                        size = (
                            item.get('resourceSize')
                            or item.get('resource_size')
                            or item.get('transferSize')
                            or item.get('transfer_size')
                            or 0
                        )
                        try:
                            size = int(size)
                        except Exception:
                            size = 0
                        db_images.append({'basename': basename, 'stem': os.path.splitext(basename)[0], 'size': size})
            except Exception as _e:
                pass

            optimized_image_total_bytes = 0
            optimization_saved_bytes = 0
            converted_image_count = len(convertedfiles)
            
            # optimization_saved_bytes 계산: 실제 다운로드된 이미지 기준으로 계산
            # eligible_original_image_bytes는 WebP 변환 대상 이미지들의 원본 크기
            # webp_total_size는 변환된 WebP 이미지들의 총 크기
            optimization_saved_bytes = max(int(eligible_original_image_bytes) - int(webp_total_size), 0)
            
            # optimized_image_total_bytes 계산: 최적화 후 전체 이미지 크기
            # = WebP 변환된 이미지 크기 + 변환되지 않은 이미지 크기
            # 변환되지 않은 이미지 = 전체 다운로드 이미지 - 변환 대상 이미지
            unconverted_image_bytes = max(int(total_downloaded_image_bytes) - int(eligible_original_image_bytes), 0)
            optimized_image_total_bytes = int(webp_total_size) + int(unconverted_image_bytes)
            
            # converted_image_count는 이미 계산됨 (위에서 len(convertedfiles))

            # 최적화 효과 판단: 변환 대상 이미지의 원본 크기와 WebP 변환 후 크기를 비교
            # webp_total_size는 이미 필터링되어 원본보다 작은 이미지만 포함하므로,
            # webp_total_size >= eligible_original_image_bytes인 경우는 변환 효과가 없는 경우
            is_already_optimized = False
            if eligible_original_image_bytes > 0:
                # 변환 대상 이미지가 있고, WebP 변환 후 크기가 원본보다 크거나 같으면 "이미 최적화됨"
                if webp_total_size >= eligible_original_image_bytes:
                    is_already_optimized = True
            elif total_downloaded_image_bytes > 0:
                # 변환 대상 이미지가 없고, 전체 다운로드 이미지가 있으면 최적화할 이미지가 없는 경우
                # 하지만 이 경우는 일반적으로 최적화가 필요 없는 경우이므로 False로 유지
                is_already_optimized = False

            # 결과 패키징 및 view_data에 저장 (향후 라우트에서 재사용)
            image_opt_result = {
                'captured_image_path': captured_image_path,
                'category': category,
                'files': files,  # 모든 분류된 이미지 포함 (webpfiles가 아닌 files)
                'filecount': len(files),  # 전체 파일 수
                'totalsize': total_downloaded_image_bytes,
                'total_downloaded_image_bytes': total_downloaded_image_bytes,
                'eligible_original_image_bytes': eligible_original_image_bytes,
                'optimized_image_total_bytes': optimized_image_total_bytes,
                'optimization_saved_bytes': optimization_saved_bytes,
                'converted_image_count': converted_image_count,
                'convertedfiles': convertedfiles,
                'url_s': url_s_stripped,
                'webp_total_size': webp_total_size,
                'co2_saved': co2_saved,
                'is_already_optimized': is_already_optimized,  # 새 필드 추가
            }

            # view_data 강화 및 DB에 별도 필드로 저장
            try:
                view_data['image_optimization'] = image_opt_result
            except Exception:
                pass

            # [9-1] 중간 저장 (진행 상태만 업데이트, result는 최종 저장 시에만)
            task_results_collection.update_one(
                {'_id': original_task_id},
                {'$set': {
                    'progress.steps.image_opt': {'status': 'done', 'message': '이미지 최적화 완료'},
                    'progress.updated_at': datetime.utcnow().isoformat()
                }},
                upsert=True
            )
            
            # 이미지 최적화 완료 로깅
            total_images = len(downloaded)
            if cache_enabled and cached_count > 0:
                current_app.logger.info(f"이미지 최적화 완료: 총 {total_images}개 (캐시 재사용: {cached_count}개, 새로 다운로드: {download_count}개, 실패: {failed_count}개)")
            else:
                if download_count > 0 or failed_count > 0:
                    current_app.logger.info(f"이미지 최적화 완료: 총 {total_images}개 (다운로드: {download_count}개, 실패: {failed_count}개)")
                else:
                    current_app.logger.info(f"이미지 최적화 완료: 총 {total_images}개")
        except Exception as e:
            current_app.logger.error(f"분석 실패: 이미지 최적화 오류 - {str(e)}")
            try:
                task_results_collection.update_one(
                    {'_id': original_task_id},
                    {'$set': {
                        'progress.steps.image_opt': {'status': 'failed', 'message': str(e)},
                        'progress.updated_at': datetime.utcnow().isoformat()
                    }}
                )
            except Exception:
                pass

        # [9-2] 코드 분석 데이터 사전 처리 (directory_maker + CO2 계산)
        # 환경 변수로 코드 분석 기능 제어 (기본값: 활성화)
        enable_code_analysis = os.getenv('ENABLE_CODE_ANALYSIS', 'true').lower() == 'true'

        if enable_code_analysis:
            # 코드 분석 전 취소 확인
            check_task_cancelled()
            try:
                # 진행 상태: 코드 분석 시작
                try:
                    task_results_collection.update_one(
                        {'_id': original_task_id},
                        {'$set': {
                            'progress.steps.code_analysis': {'status': 'in_progress', 'message': '코드 분석 데이터 생성 중'},
                            'progress.current_step': 'code_analysis',
                            'progress.updated_at': datetime.utcnow().isoformat()
                        }}
                    )
                except Exception:
                    pass

                # DirectoryMaker 및 CO2 계산
                from ecoweb.app.ProjectMaker.DirectoryMaker import (
                    directory_maker, 
                    directory_to_json,
                    build_directory_structure_from_urls,
                    get_network_requests
                )

                # directory_maker: 리소스 다운로드 및 로컬 디렉터리 구조 생성
                directory_structure = {}
                try:
                    # 리소스 다운로드 옵션 확인
                    download_resources = Config.ENABLE_RESOURCE_DOWNLOAD
                    
                    if download_resources:
                        # 기존 방식: 실제 파일 다운로드
                        root_path = directory_maker(
                            url=url,
                            collection_traffic=collection_traffic,
                            collection_resource=collection_resource,
                            download_resources=True
                        )
                        # 디렉터리 구조를 JSON으로 변환
                        directory_structure = directory_to_json(root_path=root_path)
                    else:
                        # 최적화 방식: URL만으로 구조 생성 (다운로드 없음)
                        # 이미 조회된 resource_doc 재사용 (최적화)
                        urls = []
                        if resource_doc:
                            # resource_doc에서 network_requests 추출
                            requests_list = resource_doc.get('networkRequests') or resource_doc.get('network_requests') or []
                            urls = [
                                req.get('url', '') for req in requests_list
                                if req.get('url')
                            ]
                        else:
                            # fallback: get_network_requests 호출
                            documents = get_network_requests(collection_resource=collection_resource, url=url)
                            urls = [
                                doc["url"] for doc in documents
                                if doc.get("url")
                            ]
                        
                        if urls:
                            structure_dict = build_directory_structure_from_urls(urls)
                            directory_structure = directory_to_json(structure_dict=structure_dict)
                except Exception as e:
                    pass
                    try:
                        from ecoweb.app.ProjectMaker.DirectoryMaker import generate_sample_directory_structure
                        directory_structure = generate_sample_directory_structure()
                    except Exception:
                        directory_structure = {"project": {"__files__": ["index.html", "main.js", "styles.css"]}}

                # CO2 배출량 계산
                co2_emissions = {}
                total_js_bytes = view_data.get('total_resource_bytes_script', 0)
                unused_js_bytes = view_data.get('total_unused_bytes_script', 0)
                view_data['used_js_script_size'] = max(total_js_bytes - unused_js_bytes, 0)

                metrics_to_calculate_co2 = [
                    'total_byte_weight',
                    'third_party_summary_wasted_bytes',
                    'total_resource_bytes_script',
                    'total_unused_bytes_script',
                    'used_js_script_size',
                    'can_optimize_css_bytes',
                    'modern_image_formats_bytes',
                    'efficient_animated_content_bytes',
                    'duplicated_javascript_bytes'
                ]

                for key in metrics_to_calculate_co2:
                    byte_value = view_data.get(key, 0)
                    try:
                        byte_value = int(byte_value) if byte_value else 0
                    except (ValueError, TypeError):
                        byte_value = 0

                    if byte_value > 0:
                        gb_value = byte_value / (1024 * 1024 * 1024)
                        co2_emissions[key] = estimate_emission_per_page(data_gb=gb_value)
                    else:
                        co2_emissions[key] = 0.0

                # 폰트 최적화 데이터 계산
                font_total_bytes = view_data.get('font_total_bytes', 0)
                detailed_font_info = view_data.get('detailed_font_info', [])

                current_font_co2_emission = 0.0
                if font_total_bytes > 0:
                    font_data_gb = font_total_bytes / (1024 * 1024 * 1024)
                    current_font_co2_emission = estimate_emission_per_page(data_gb=font_data_gb)

                # 폰트 최적화 방법 설정 (optimization.py에서 복사)
                FONT_OPTIMIZATION_METHODS_CONFIG = [
                    {'name': 'WOFF로 변경', 'description': '웹 최적화 압축 형식. 대부분의 모던 브라우저에서 지원됩니다.', 'size_multiplier': 0.55},
                    {'name': 'WOFF2로 변경', 'description': 'WOFF보다 향상된 압축률을 제공하는 차세대 웹 폰트 형식입니다.', 'size_multiplier': 0.50},
                    {'name': '서브셋 폰트 적용', 'description': '웹사이트에 실제 사용되는 글자들만 포함하여 폰트 파일 크기를 줄입니다.', 'size_multiplier': 0.25},
                    {'name': '가변 폰트로 변경', 'description': '하나의 폰트 파일로 다양한 스타일을 지원하여 여러 정적 폰트 파일 요청을 줄입니다.', 'size_multiplier': 0.30},
                    {'name': '시스템 폰트로 변경', 'description': '웹 폰트를 다운로드하는 대신 사용자 운영체제의 기본 폰트를 사용합니다.', 'size_multiplier': 0.00}
                ]

                font_optimization_data = []
                if font_total_bytes > 0:
                    for method in FONT_OPTIMIZATION_METHODS_CONFIG:
                        original_size_bytes = font_total_bytes
                        reduced_size_bytes = original_size_bytes * method['size_multiplier']
                        saved_bytes = original_size_bytes - reduced_size_bytes

                        emissions_gCO2eq = 0.0
                        if reduced_size_bytes > 0:
                            reduced_size_gb = reduced_size_bytes / (1024 * 1024 * 1024)
                            emissions_gCO2eq = estimate_emission_per_page(data_gb=reduced_size_gb)

                        font_optimization_data.append({
                            'name': method['name'],
                            'description': method['description'],
                            'saved_bytes': saved_bytes,
                            'emissions_gCO2eq': emissions_gCO2eq
                        })

                # 코드 최적화 데이터 추출 (final_report 기반)
                # 이미 조회된 traffic_doc 재사용 (최적화)
                code_optimization_data = {'total_wasted_bytes': 0, 'co2_saving': 0.0, 'unused_css_count': 0, 'unused_js_count': 0, 'unused_css_rules': [], 'unused_javascript': []}
                try:
                    # 일괄 조회한 traffic_doc 재사용, 없으면 조회 (fallback)
                    code_traffic_doc = traffic_doc
                    if not code_traffic_doc:
                        code_traffic_doc = collection_traffic.find_one({'url': url}, {'_id': 0, 'audits': 1})
                    
                    if code_traffic_doc and 'audits' in code_traffic_doc:
                        audits = code_traffic_doc.get('audits', {})
                        unused_css_rules = audits.get('unused-css-rules', {}).get('details', {}).get('items', [])
                        unused_javascript = audits.get('unused-javascript', {}).get('details', {}).get('items', [])

                        total_css_wasted_bytes = sum(item.get('wastedBytes', 0) for item in unused_css_rules)
                        total_js_wasted_bytes = sum(item.get('wastedBytes', 0) for item in unused_javascript)
                        total_wasted_bytes = total_css_wasted_bytes + total_js_wasted_bytes

                        co2_saving = estimate_emission_per_page((total_wasted_bytes or 0) / (1024 * 1024 * 1024))

                        code_optimization_data = {
                            'total_wasted_bytes': total_wasted_bytes,
                            'co2_saving': co2_saving,
                            'unused_css_count': len(unused_css_rules),
                            'unused_js_count': len(unused_javascript),
                            'unused_css_rules': unused_css_rules,
                            'unused_javascript': unused_javascript
                        }
                except Exception as e:
                    pass

                # 결과 패키징
                code_analysis_result = {
                    'directory_structure': directory_structure,
                    'co2_emissions': co2_emissions,
                    'font_total_bytes': font_total_bytes,
                    'current_font_co2_emission': current_font_co2_emission,
                    'detailed_font_info': detailed_font_info,
                    'font_optimization_data': font_optimization_data,
                    'code_optimization_data': code_optimization_data
                }

                # view_data 강화
                try:
                    view_data['code_analysis'] = code_analysis_result
                except Exception:
                    pass

                # 중간 저장 (진행 상태만 업데이트, result는 최종 저장 시에만)
                task_results_collection.update_one(
                    {'_id': original_task_id},
                    {'$set': {
                        'progress.steps.code_analysis': {'status': 'done', 'message': '코드 분석 완료'},
                        'progress.updated_at': datetime.utcnow().isoformat()
                    }},
                    upsert=True
                )
            except Exception as e:
                current_app.logger.error(f"분석 실패: 코드 분석 오류 - {str(e)}")
                try:
                    task_results_collection.update_one(
                        {'_id': original_task_id},
                        {'$set': {
                            'progress.steps.code_analysis': {'status': 'failed', 'message': str(e)},
                            'progress.updated_at': datetime.utcnow().isoformat()
                        }}
                    )
                except Exception:
                    pass

        # [10] 데이터 강화: 모든 파생 데이터 계산 (Phase 1: Session-to-DB Refactoring)
        current_app.logger.info("[ENRICH] view_data 강화 시작: 모든 파생 데이터 계산")
        try:
            # 일괄 조회한 데이터를 전달하여 중복 조회 방지
            enriched_result = _enrich_view_data(view_data, url, mongo_db, resource_doc=resource_doc, traffic_doc=traffic_doc)
            current_app.logger.info("[ENRICH] view_data 강화 완료: calculated 섹션 추가됨")
        except Exception as e:
            current_app.logger.error(f"[ENRICH] view_data 강화 실패: {e}, 원본 데이터 사용", exc_info=True)
            enriched_result = view_data  # 강화 실패 시 원본 사용

        # [11] 측정 완료 결과를 task_results 컬렉션에 저장 (최종 상태 MEASUREMENT_COMPLETE)
        update_result = task_results_collection.update_one(
            {'_id': original_task_id},
            {'$set': {
                'status': 'MEASUREMENT_COMPLETE',
                'result': enriched_result,  # ← enriched_result 사용 (calculated 섹션 포함)
                'completed_at': datetime.utcnow()
            }},
            upsert=True
        )
        current_app.logger.info(f"MongoDB 저장 결과: 일치={update_result.matched_count}, 수정={update_result.modified_count}, 삽입ID={update_result.upserted_id}")

        current_app.logger.info(f'Celery 작업 성공적으로 완료: URL={url}')
        return {'status': 'MEASUREMENT_COMPLETE'}

    except Exception as e:
        # [11] 예외 처리: 실패 상태 및 오류 메시지 저장
        # 취소된 작업인 경우 다르게 처리
        if 'cancelled by user' in str(e).lower() or 'task cancelled' in str(e).lower():
            current_app.logger.info(f'Celery 작업 취소됨: URL={url}, 사유={e}')
            return {'status': 'CANCELLED', 'reason': str(e)}

        current_app.logger.error(f'Celery 작업 실패: URL={url}, 오류={e}', exc_info=True)

        # 실패한 단계에 따라 적절한 상태 업데이트
        update_data = {
            'status': 'FAILURE',
            'error': str(e),
            'progress.updated_at': datetime.utcnow().isoformat()
        }

        # 현재 진행 상태를 확인하여 적절한 단계를 실패로 표시
        try:
            current_task = task_results_collection.find_one({'_id': original_task_id})
            current_step = current_task.get('progress', {}).get('current_step', 'input') if current_task else 'input'

            if current_step == 'input':
                update_data['progress.steps.input'] = {'status': 'failed', 'message': str(e)}
            elif current_step == 'subpages':
                update_data['progress.steps.subpages'] = {'status': 'failed', 'message': f'하위 페이지 분석 실패: {str(e)}'}
            elif current_step == 'image_opt':
                update_data['progress.steps.image_opt'] = {'status': 'failed', 'message': f'이미지 최적화 실패: {str(e)}'}
            else:
                update_data['progress.steps.input'] = {'status': 'failed', 'message': str(e)}
        except Exception:
            # 현재 단계 확인 실패 시 기본적으로 input 단계를 실패로 설정
            update_data['progress.steps.input'] = {'status': 'failed', 'message': str(e)}

        task_results_collection.update_one(
            {'_id': original_task_id},
            {'$set': update_data},
            upsert=True
        )
        return {'status': 'FAILURE', 'error': str(e)}
    finally:
        # [12] 후처리: 큐에 남아있는 다음 작업 처리 시도
        # 취소된 작업은 후속 처리를 건너뜀
        try:
            mongo_db = db.get_db()
            task_doc = mongo_db.task_results.find_one({'_id': original_task_id})
            if task_doc and task_doc.get('status') == 'CANCELLED':
                current_app.logger.info(f'Task {original_task_id} was cancelled, skipping queue processing')
                return
        except Exception:
            pass

        current_app.logger.info("작업 종료: 큐의 다음 작업을 처리합니다.")
        try:
            # 순환 참조를 피하기 위해 함수 내에서 import 합니다.
            from ecoweb.app.blueprints.main import process_queued_tasks
            process_queued_tasks()
        except ImportError as ie:
            current_app.logger.error(f"process_queued_tasks 임포트 실패: {ie}")
        except Exception as final_e:
            current_app.logger.error(f"process_queued_tasks 호출 중 오류: {final_e}", exc_info=True)

@celery.task(bind=True, ignore_result=False)
def generate_pdf_report_task(self, session_data: dict, user_id, original_task_id):
    """
    Celery task to generate PDF report in the background.

    Args:
        session_data: Session data containing URL and analysis results
        user_id: User ID for organizing PDF files
        original_task_id: MongoDB task document ID for progress tracking

    Returns:
        dict: Task result with status and file information
    """
    import io
    from ecoweb.app.utils.task_cancellation import check_task_cancelled_legacy

    def check_task_cancelled():
        """작업이 취소되었는지 확인하고, 취소된 경우 예외를 발생시킵니다."""
        check_task_cancelled_legacy(original_task_id, current_app.logger)

    try:
        # MongoDB 컬렉션 핸들
        mongo_db = db.get_db()
        pdf_tasks_collection = mongo_db.pdf_generation_tasks

        # 초기 취소 확인
        check_task_cancelled()

        # [2] 진행 상태 업데이트: 초기화 단계
        pdf_tasks_collection.update_one(
            {'_id': original_task_id},
            {'$set': {
                'status': 'PROCESSING',
                'progress': {
                    'current_step': 'initialization',
                    'message': 'PDF 생성기 초기화 중',
                    'updated_at': datetime.utcnow().isoformat()
                }
            }}
        )

        # PDF 생성기 초기화
        from ecoweb.app.services.report import PlaywrightPDFGenerator
        pdf_generator = PlaywrightPDFGenerator()

        # [3] 진행 상태 업데이트: PDF 생성 단계
        pdf_tasks_collection.update_one(
            {'_id': original_task_id},
            {'$set': {
                'progress': {
                    'current_step': 'generating',
                    'message': 'PDF 페이지 생성 중 (1/13)',
                    'updated_at': datetime.utcnow().isoformat()
                }
            }}
        )

        # 하트비트 쓰레드: PDF 생성 중 진행 상태 주기적 업데이트
        _hb_stop = threading.Event()
        _hb_page_counter = {'current': 1}

        def _heartbeat():
            """PDF 생성 중 진행 상태를 주기적으로 업데이트하는 하트비트 쓰레드"""
            start_ts = time.time()
            while not _hb_stop.is_set():
                try:
                    # 취소 확인
                    task_doc = pdf_tasks_collection.find_one({'_id': original_task_id})
                    if task_doc and task_doc.get('status') == 'CANCELLED':
                        _hb_stop.set()
                        break

                    elapsed = int(time.time() - start_ts)
                    current_page = _hb_page_counter.get('current', 1)

                    pdf_tasks_collection.update_one(
                        {'_id': original_task_id},
                        {'$set': {
                            'progress': {
                                'current_step': 'generating',
                                'message': f'PDF 페이지 생성 중 ({current_page}/13) - {elapsed}s',
                                'updated_at': datetime.utcnow().isoformat()
                            }
                        }}
                    )
                except Exception:
                    pass
                _hb_stop.wait(3.0)  # 3초마다 업데이트

        _hb_thread = threading.Thread(target=_heartbeat, daemon=True)
        _hb_thread.start()

        try:
            # PDF 생성 전 취소 확인
            check_task_cancelled()

            pdf_buffer = pdf_generator.generate_pdf(session_data)
        finally:
            _hb_stop.set()
            try:
                _hb_thread.join(timeout=2)
            except Exception:
                pass

        # PDF 생성 후 취소 확인
        check_task_cancelled()

        # [4] 진행 상태 업데이트: 파일 저장 단계
        pdf_tasks_collection.update_one(
            {'_id': original_task_id},
            {'$set': {
                'progress': {
                    'current_step': 'saving',
                    'message': 'PDF 파일 저장 중',
                    'updated_at': datetime.utcnow().isoformat()
                }
            }}
        )

        # [5] 파일 시스템에 PDF 저장 (var/pdf_reports 사용)
        from ecoweb.config import Config
        user_pdf_dir = os.path.join(Config.PDF_REPORT_FOLDER, str(user_id))
        os.makedirs(user_pdf_dir, exist_ok=True)

        # 파일명 생성
        url = session_data.get('url', 'unknown')

        # URL을 파일명으로 사용할 수 있도록 정리
        def _sanitize_filename(url):
            if not url:
                return 'unknown'
            # 프로토콜 제거
            if url.startswith(('http://', 'https://')):
                url = url.split('://', 1)[1]
            # 특수문자 제거 및 길이 제한
            safe_name = re.sub(r'[^\w\-_.]', '_', url)
            safe_name = safe_name[:50]  # 길이 제한
            return safe_name

        safe_url = _sanitize_filename(url)
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        filename = f"carbon_report_{safe_url}_{timestamp}.pdf"

        # 절대 경로로 파일 저장
        pdf_path = os.path.join(user_pdf_dir, filename)

        with open(pdf_path, 'wb') as f:
            f.write(pdf_buffer.getvalue())

        file_size = os.path.getsize(pdf_path)

        # [6] 진행 상태 업데이트: 완료 단계
        relative_path = f"var/pdf_reports/{user_id}/{filename}"

        pdf_tasks_collection.update_one(
            {'_id': original_task_id},
            {'$set': {
                'status': 'SUCCESS',
                'completed_at': datetime.utcnow(),
                'result': {
                    'pdf_path': relative_path,
                    'filename': filename,
                    'file_size': file_size,
                    'generated_at': datetime.utcnow().isoformat()
                },
                'progress': {
                    'current_step': 'completed',
                    'message': 'PDF 생성 완료',
                    'updated_at': datetime.utcnow().isoformat()
                }
            }}
        )

        return {
            'status': 'SUCCESS',
            'pdf_path': relative_path,
            'filename': filename,
            'file_size': file_size
        }

    except Exception as e:
        # 취소된 작업인 경우
        if 'cancelled by user' in str(e).lower() or 'task cancelled' in str(e).lower():
            pdf_tasks_collection.update_one(
                {'_id': original_task_id},
                {'$set': {
                    'status': 'CANCELLED',
                    'cancelled_at': datetime.utcnow(),
                    'progress': {
                        'current_step': 'cancelled',
                        'message': '사용자에 의해 취소됨',
                        'updated_at': datetime.utcnow().isoformat()
                    }
                }}
            )
            return {'status': 'CANCELLED', 'reason': str(e)}

        # 일반 오류
        current_app.logger.error(f'PDF 생성 실패: {str(e)}')

        pdf_tasks_collection.update_one(
            {'_id': original_task_id},
            {'$set': {
                'status': 'FAILURE',
                'failed_at': datetime.utcnow(),
                'error': str(e),
                'progress': {
                    'current_step': 'failed',
                    'message': f'PDF 생성 실패: {str(e)}',
                    'updated_at': datetime.utcnow().isoformat()
                }
            }}
        )

        return {'status': 'FAILURE', 'error': str(e)}
