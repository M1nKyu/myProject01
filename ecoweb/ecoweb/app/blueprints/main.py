# 표준 라이브러리
import json
import logging
import os
import random
import threading
import time
import uuid
from datetime import datetime, timedelta, timezone
from urllib.parse import urlsplit, urlunsplit

# 서드파티 라이브러리
import requests
import urllib3
from bson import Int64, ObjectId

# SSL 경고 메시지 비활성화 (사이트 접근성 체크 시 verify=False 사용)
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
from celery.result import AsyncResult
from flask import (
    Blueprint, current_app, flash, jsonify, make_response, redirect,
    render_template, request, send_from_directory, session, url_for
)
from werkzeug.utils import secure_filename

# 로컬 애플리케이션
from ecoweb.app import celery, db
from ecoweb.app.services.analysis.analysis_service import perform_detailed_analysis, process_content_emission_data
from ecoweb.app.services.analysis.emissions import estimate_emission_per_page, estimate_emission_from_kb
# from ecoweb.app.services.report.pdf import CarbonReportGenerator  # WeasyPrint 비활성화로 주석 처리
from ecoweb.app.tasks import analyze_url_task
from ecoweb.app.utils.grade import grade_point, grade_point_by_emission
from ecoweb.app.utils.emission_calculator import EmissionCalculator
from ecoweb.app.utils.seo_helpers import MetaDataGenerator
from ecoweb.app.utils.structured_data import StructuredDataGenerator
from ecoweb.app.utils.validators import validate_and_normalize_url
from ecoweb.app.services.capture.accessibility import check_site_accessibility_sync  # Phase 2: 비동기 접근성 체크
from ecoweb.app.utils.event_logger import log_analysis_start, log_analysis_cancel, log_user_event, is_logging_enabled, log_page_view

from ..database import get_db
from .utils import get_active_celery_tasks
from ecoweb.app.utils.task_cancellation import log_task_cancellation, is_task_cancelled

main_bp = Blueprint('main', __name__)

# ===================================================================
# 🔍 사이트 접근성 체크 함수
# ===================================================================
def check_site_accessibility(url, timeout=5):
    """
    URL이 접근 가능한지 확인합니다.

    Args:
        url (str): 확인할 URL
        timeout (int): 타임아웃 시간 (초). Phase 1: 10초 → 5초로 단축

    Returns:
        bool: 접근 가능하면 True, 불가능하면 False
    """
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
    }

    try:
        # 먼저 HEAD 요청 시도
        response = requests.head(url, headers=headers, timeout=timeout, allow_redirects=True, verify=False)
        if 200 <= response.status_code < 400:
            return True

        # HEAD 요청이 실패하면 GET 요청 시도 (일부 사이트는 HEAD를 지원하지 않음)
        current_app.logger.info(f"HEAD 요청 실패 (상태코드: {response.status_code}), GET 요청으로 재시도: {url}")

    except Exception as head_error:
        current_app.logger.info(f"HEAD 요청 예외 발생, GET 요청으로 재시도: {url}, 오류: {head_error}")

    try:
        # GET 요청으로 재시도 (첫 몇 바이트만 받음)
        response = requests.get(url, headers=headers, timeout=timeout, allow_redirects=True,
                              verify=False, stream=True)

        # 응답이 시작되면 즉시 연결 종료 (전체 다운로드하지 않음)
        response.close()

        if 200 <= response.status_code < 400:
            return True
        else:
            current_app.logger.warning(f"사이트 접근 실패 - 상태코드: {response.status_code}, URL: {url}")
            return False

    except requests.exceptions.Timeout:
        current_app.logger.warning(f"사이트 접근 실패 - 타임아웃({timeout}초), URL: {url}")
        return False
    except requests.exceptions.ConnectionError as e:
        current_app.logger.warning(f"사이트 접근 실패 - 연결 오류: {e}, URL: {url}")
        return False
    except requests.exceptions.SSLError as e:
        current_app.logger.warning(f"사이트 접근 실패 - SSL 오류: {e}, URL: {url}")
        return False
    except Exception as e:
        current_app.logger.warning(f"사이트 접근 실패 - 예외: {e}, URL: {url}")
        return False

# ===================================================================
# 🏠 메인 페이지 라우트
# ===================================================================
@main_bp.route('/', methods=['GET', 'POST'])
def home():
    # [1] 최근 입력한 URL 목록을 쿠키에서 불러오기 (최대 5개 관리)
    recent_urls = json.loads(request.cookies.get('recent_urls', '[]'))
    
    # 메인 페이지 접속 로깅 (GET 요청만)
    if request.method == 'GET':
        log_page_view('home')

    # [2] 폼 제출(POST) 시 분석 작업을 생성하고 로딩 페이지로 이동
    if request.method == 'POST':
        # [3] 사용자 에이전트를 통해 모바일 여부 판별 (UI/분석 구분용)
        user_agent = request.headers.get('User-Agent', '').lower()
        is_mobile = 'iphone' in user_agent or 'android' in user_agent or 'mobile' in user_agent
        
        # [4] 폼에서 URL 입력값을 가져와 공백 제거
        url = request.form.get('wgd-cc-url', '').strip()

        # [5] URL이 비어있으면 에러 메시지 후 메인으로 리다이렉트
        if not url:
            flash('유효한 URL을 입력해주세요.', 'error')
            return redirect(url_for('main.home'))

        # [6] URL 검증 및 정규화 (개선된 보안 검증)
        is_valid, normalized_url, error_msg = validate_and_normalize_url(url)
        if not is_valid:
            current_app.logger.warning(f'URL 검증 실패: {url} - {error_msg}')
            flash(f'URL 형식 오류: {error_msg}', 'error')
            return redirect(url_for('main.home'))

        # 검증된 URL 사용
        url = normalized_url
        current_app.logger.info(f'URL 검증 성공: {url}')
        
        # 이벤트 로깅: 분석 시작
        user_id = session.get('user_id')
        log_analysis_start(url, user_id=str(user_id) if user_id else None, is_mobile=is_mobile)

        # [6-1] 사이트 접근성 사전 체크 (Phase 2: 비동기 체크 사용)
        if not check_site_accessibility_sync(url, timeout=5):
            current_app.logger.error(f'사이트 접근 실패: {url}')

            # MongoDB 핸들 획득
            db = get_db()
            task_id = str(uuid.uuid4())

            # 사용자 친화적 에러 정보 생성
            error_info = {
                'title': '사이트에 접근할 수 없습니다',
                'message': '입력하신 웹사이트에 연결할 수 없습니다.',
                'suggestion': 'URL을 다시 확인하거나 해당 사이트가 정상 작동하는지 확인해 주세요.'
            }

            # 접근성 실패한 task 결과를 DB에 저장 (로딩 페이지 표시용)
            db.task_results.insert_one({
                '_id': task_id,
                'status': 'FAILURE',
                'failure_type': 'ACCESSIBILITY_CHECK',
                'url': url,
                'user_id': session.get('user_id', 'anonymous'),
                'is_mobile': is_mobile,
                'error': '사이트에 접근할 수 없습니다.',
                'error_info': error_info,
                'created_at': datetime.now(timezone.utc)
            })

            # 세션에 task_id만 저장 (Phase 4: DB-centered architecture)
            session['task_id'] = task_id

            # 최근 URL 목록 갱신
            if url in recent_urls:
                recent_urls.remove(url)
            recent_urls.insert(0, url)
            recent_urls = recent_urls[:5]

            # 로딩 페이지로 리다이렉트 (오류 메시지가 표시될 것임)
            response = make_response(redirect(url_for('main.loading', task_id=task_id, url=url)))
            response.set_cookie('recent_urls', json.dumps(recent_urls), max_age=30*24*60*60)
            return response

        # [7] 사용자 식별자 획득 및 요청 로깅
        user_id = session.get('user_id', 'anonymous')
        # current_app.logger.info(f'URL 분석 요청 - 사용자: {user_id}, URL: {url}')

        # [8] MongoDB 핸들 획득
        db = get_db()

        # [9] 최근 데이터 존재 여부 확인 (일주일 이내)
        recent_threshold = datetime.now(timezone.utc) - timedelta(days=7)

        # lighthouse_traffic_02와 lighthouse_resources_02 컬렉션에서 최근 데이터 확인
        # MongoDB Projection: 모든 필드 필요 (process_existing_data에서 사용)
        traffic_data = db.lighthouse_traffic_02.find_one({
            'url': url,
            'timestamp': {'$gte': recent_threshold}
        }, sort=[('timestamp', -1)])

        resource_data = db.lighthouse_resources_02.find_one({
            'url': url,
            'timestamp': {'$gte': recent_threshold}
        }, sort=[('timestamp', -1)])

        # [10] 두 컬렉션 모두에 최근 데이터가 있으면 기존 Lighthouse 데이터 재사용하여 Celery 작업 실행
        if traffic_data and resource_data:
            print(f'[DB 조회 성공] 최근 Lighthouse 데이터 발견: {url}')
            print(f'[DB 조회 성공] Traffic 데이터: {traffic_data.get("timestamp")}')
            print(f'[DB 조회 성공] Resource 데이터: {resource_data.get("timestamp")}')
            current_app.logger.info(f'최근 Lighthouse 데이터 발견: {url} - 하위페이지 분석 및 이미지 최적화만 실행')

            # 기존 Lighthouse 데이터로부터 view_data 생성
            try:
                from ecoweb.app.services.lighthouse import process_existing_data
                view_data = process_existing_data(traffic_data, resource_data, url, is_mobile)
                print(f'[DB 조회 성공] view_data 생성 완료: total_byte_weight={view_data.get("total_byte_weight", 0)} bytes')

                # 동시 실행 제한(쓰로틀링) 확인
                CELERY_QUEUE_THRESHOLD = 5
                active_tasks = get_active_celery_tasks()

                original_task_id = str(uuid.uuid4())
                print(f'[DB 조회 성공] 하위페이지+이미지최적화 task_id 생성: {original_task_id}')

                if active_tasks >= CELERY_QUEUE_THRESHOLD:
                    # 큐에 대기
                    db.task_results.insert_one({
                        '_id': original_task_id,
                        'status': 'QUEUED',
                        'url': url,
                        'user_id': user_id,
                        'is_mobile': is_mobile,
                        'created_at': datetime.now(timezone.utc)
                    })
                    current_app.logger.info(f'Task {original_task_id} (기존 데이터 활용) queued. Active tasks: {active_tasks}')
                else:
                    # 즉시 실행: 하위페이지 + 이미지 최적화만 수행하는 Celery 작업
                    task = analyze_url_task.delay(url, user_id, is_mobile, original_task_id,
                                                perform_subpage_crawling=True, existing_view_data=view_data)
                    celery_task_id = task.id

                    db.task_results.insert_one({
                        '_id': original_task_id,
                        'celery_task_id': celery_task_id,
                        'status': 'PENDING',
                        'url': url,
                        'user_id': user_id,
                        'is_mobile': is_mobile,
                        'created_at': datetime.now(timezone.utc)
                    })
                    current_app.logger.info(f'Task {original_task_id} (기존 데이터 활용) started with Celery ID {celery_task_id}')

                session['task_id'] = original_task_id

                # 최근 URL 목록 갱신
                if url in recent_urls:
                    recent_urls.remove(url)
                recent_urls.insert(0, url)
                recent_urls = recent_urls[:5]

                # 로딩 페이지로 리다이렉트 (하위페이지 분석 + 이미지 최적화 진행)
                print(f'[DB 조회 성공] 로딩 페이지로 리다이렉트: task_id={original_task_id}')
                response = make_response(redirect(url_for('main.loading', task_id=original_task_id, url=url)))
                response.set_cookie('recent_urls', json.dumps(recent_urls), max_age=30*24*60*60)
                return response

            except Exception as e:
                current_app.logger.warning(f'기존 데이터 처리 실패: {e}. 새로운 측정을 진행합니다.')
                # 기존 데이터 처리 실패 시 새로운 측정 진행

        # [11] 동시 실행 제한(쓰로틀링) 및 현재 실행 중인 작업 수 조회
        CELERY_QUEUE_THRESHOLD = 5  # 동시에 실행할 최대 작업 수
        active_tasks = get_active_celery_tasks()
        
        # [12] 즉시 실행 불가: 큐 상태로 task_results에 초기 문서 삽입
        if active_tasks >= CELERY_QUEUE_THRESHOLD:
            task_id = str(uuid.uuid4())
            db.task_results.insert_one({
                '_id': task_id,
                'status': 'QUEUED',
                'url': url,
                'user_id': user_id,
                'is_mobile': is_mobile,
                'result': None,
                'created_at': datetime.now(timezone.utc)
            })
            current_app.logger.info(f'Task {task_id} for {url} is queued. Active tasks: {active_tasks}')

        # [13] 즉시 실행 가능: Celery 작업 생성 후 task_results에 PENDING으로 기록
        else:
            original_task_id = str(uuid.uuid4())
            task = analyze_url_task.delay(url, user_id, is_mobile, original_task_id, perform_subpage_crawling=False)
            celery_task_id = task.id

            db.task_results.insert_one({
                '_id': original_task_id,
                'celery_task_id': celery_task_id,
                'status': 'PENDING',
                'url': url,
                'user_id': user_id,
                'is_mobile': is_mobile,
                'created_at': datetime.now(timezone.utc)
            })
            task_id = original_task_id
            current_app.logger.info(f'Task {task_id} for {url} started immediately with Celery ID {celery_task_id}. Active tasks: {active_tasks}')
        
        # [14] 세션에 현재 작업 식별자만 저장 (Phase 4: DB-centered architecture)
        session['task_id'] = task_id

        # [15] 최근 URL 목록 갱신(중복 제거 후 맨 앞에 추가, 최대 5개 유지)
        if url in recent_urls:
            recent_urls.remove(url)
        recent_urls.insert(0, url)
        recent_urls = recent_urls[:5]

        # [16] 로딩 페이지로 리다이렉트 + 최근 URL 쿠키 저장(30일)
        response = make_response(redirect(url_for('main.loading', task_id=task_id, url=url)))
        response.set_cookie('recent_urls', json.dumps(recent_urls), max_age=30*24*60*60)
        return response
    
    # [17] GET 요청: 메인 페이지 렌더링
    # SEO: 메타 데이터 및 Structured Data 생성
    meta = MetaDataGenerator.generate_home_meta()
    structured_data = [
        StructuredDataGenerator.generate_organization_schema(),
        StructuredDataGenerator.generate_website_schema(),
        StructuredDataGenerator.generate_web_application_schema()
    ]

    return render_template(
        'pages/main/main.html',
        recent_urls=recent_urls,
        meta=meta,
        structured_data=structured_data
    )

# ==========================================================================
# 📑 통합 분석 페이지 라우트 (사이드바에서 접근)
# ==========================================================================
@main_bp.route('/carbon_calculate_emission')
def carbon_calculate_emission_router():
    """통합 분석 페이지 - 최근 분석 결과가 있으면 결과 표시, 없으면 새 분석 시작"""
    # 세션에서 최근 task_id 확인
    last_task_id = session.get('last_completed_task_id')

    if last_task_id:
        # task_id가 있으면 해당 결과가 유효한지 확인
        try:
            mongo_db = db.get_db()
            task_results_collection = mongo_db.task_results
            # MongoDB Projection: 상태 확인에 필요한 필드만 조회
            task_result = task_results_collection.find_one(
                {'_id': last_task_id},
                {'status': 1, '_id': 0}
            )

            if task_result and task_result.get('status') in ['SUCCESS', 'MEASUREMENT_COMPLETE']:
                # 유효한 결과가 있으면 결과 페이지로 리다이렉트
                current_app.logger.info(f'마지막 완료된 분석 결과로 리다이렉트: {last_task_id}')
                return redirect(url_for('main.carbon_calculate_emission', task_id=last_task_id))
        except Exception as e:
            current_app.logger.warning(f'마지막 task_id 확인 중 오류: {e}')

    # task_id가 없거나 유효하지 않으면 새 분석 시작 페이지 표시
    recent_urls = json.loads(request.cookies.get('recent_urls', '[]'))
    return render_template('pages/main/main.html', recent_urls=recent_urls)

# ==========================================================================
# 📑 URL 분석 결과 페이지 라우트
# ==========================================================================
@main_bp.route('/carbon_calculate_emission/<task_id>')
def carbon_calculate_emission(task_id):
    """
    URL 분석 결과 페이지 (Phase 2: Session-to-DB Refactoring)

    변경 사항:
    - MongoDB의 calculated 섹션에서 이미 계산된 데이터 직접 사용
    - 모든 계산 로직 제거 (tasks.py의 _enrich_view_data()에서 이미 계산됨)
    - 세션 저장 최소화 (task_id와 하위 호환성을 위한 기본 정보만)
    """
    current_app.logger.info(f'결과 페이지 요청 시작: Task ID = {task_id}')
    
    # 페이지 조회 로깅
    log_page_view('carbon_calculate_emission', task_id=task_id)
    
    try:
        mongo_db = db.get_db()
        task_results_collection = mongo_db.task_results

        # [1] MongoDB에서 enriched_result 읽기 (Phase 1+2: 재시도 최적화)
        max_retries = 5  # 10 → 5로 감소
        retry_delay = 0.8  # Phase 2 수정: 0.5초 → 0.8초 (DB 쓰기 완료 대기)
        task_result = None
        for attempt in range(max_retries):
            task_result = task_results_collection.find_one({'_id': task_id})
            if task_result:
                task_status = task_result.get('status')
                # Phase 2: SUCCESS 상태도 완료로 처리 (Celery 완료 상태)
                # 성공 상태인 경우에만 루프 종료
                if task_status in ['SUCCESS', 'MEASUREMENT_COMPLETE']:
                    break
                # 작업이 아직 진행 중인 경우 재시도
                elif task_status in ['PENDING', 'PROCESSING', 'STARTED', 'PROGRESS']:
                    current_app.logger.debug(f'작업 진행 중 (재시도 {attempt+1}/{max_retries}): Task ID {task_id}, 상태={task_status}')
                    time.sleep(retry_delay)
                    continue
                # 실패/취소 상태인 경우 즉시 종료
                else:
                    break
            else:
                current_app.logger.debug(f'작업 결과 없음 (재시도 {attempt+1}/{max_retries}): Task ID {task_id}')
                time.sleep(retry_delay)

        if not task_result:
            current_app.logger.error(f'결과를 찾을 수 없음: Task ID {task_id}가 데이터베이스에 없습니다.')
            flash('분석 결과를 찾는 데 실패했습니다. 다시 시도해 주세요.', 'error')
            return redirect(url_for('main.home'))

        task_status = task_result.get('status')
        if task_status not in ['SUCCESS', 'MEASUREMENT_COMPLETE']:
            error_info = task_result.get('error', '알 수 없는 오류')
            current_app.logger.error(f'작업 실패: Task ID {task_id}의 상태가 {task_status}. 오류: {error_info}')

            # PENDING 상태인 경우 더 친절한 메시지 제공
            if task_status in ['PENDING', 'PROCESSING', 'STARTED', 'PROGRESS']:
                flash('분석이 아직 진행 중입니다. 잠시 후 다시 시도해 주세요.', 'warning')
                return redirect(url_for('main.loading', task_id=task_id, url=task_result.get('url', '')))
            else:
                flash(f'URL 분석 중 오류가 발생했습니다: {error_info}', 'error')
                return redirect(url_for('main.home'))

        view_data = task_result.get('result')
        if not view_data or not isinstance(view_data, dict):
            current_app.logger.error(f'데이터 형식 오류: Task ID {task_id}의 결과 데이터가 비어 있거나 형식이 잘못되었습니다.')
            flash('분석 데이터가 비어있거나 형식이 올바르지 않습니다. 다른 URL로 시도해 주세요.', 'error')
            return redirect(url_for('main.home'))

        # [2] calculated 섹션 추출 (모든 계산된 데이터)
        calculated = view_data.get('calculated', {})

        # [3] 하위 호환성: calculated 섹션이 없는 경우 (기존 데이터) - 즉석 계산
        if not calculated:
            current_app.logger.warning(f'Task ID {task_id}: calculated 섹션 없음. 즉석 계산 수행 (하위 호환성)')
            total_byte_weight = view_data.get('total_byte_weight', 0)
            kb_weight = total_byte_weight / 1024
            carbon_emission = round(estimate_emission_from_kb(kb_weight), 2)
            korea_avg_carbon = round(estimate_emission_per_page(0.00456), 2)
            global_avg_carbon = round(estimate_emission_per_page(0.002344), 2)
            korea_diff = round(korea_avg_carbon - carbon_emission, 2)
            global_diff = round(global_avg_carbon - carbon_emission, 2)
            emission_percentile = EmissionCalculator.predict_percentile(carbon_emission)
            emission_grade = EmissionCalculator.get_emission_grade(carbon_emission)
            korea_carbon_percentage_diff = round(abs((carbon_emission - korea_avg_carbon) / korea_avg_carbon) * 100) if korea_avg_carbon > 0 else 0
            korea_comparison_status = "낮습니다" if korea_diff > 0 else "높습니다"  # DEPRECATED
            korea_emission_status = "below_avg" if korea_diff > 0 else "above_avg"  # for i18n

            calculated = {
                'carbon_emission': carbon_emission,
                'kb_weight': kb_weight,
                'emission_grade': emission_grade,
                'emission_percentile': emission_percentile,
                'korea_avg_carbon': korea_avg_carbon,
                'global_avg_carbon': global_avg_carbon,
                'korea_diff': korea_diff,
                'global_diff': global_diff,
                'korea_diff_abs': round(abs(korea_diff), 2),
                'global_diff_abs': round(abs(global_diff), 2),
                'korea_carbon_percentage_diff': korea_carbon_percentage_diff,
                'korea_comparison_status': korea_comparison_status,  # DEPRECATED
                'korea_emission_status': korea_emission_status  # for i18n
            }

        # [4] URL 추출
        url = view_data.get('url')
        if not url:
            current_app.logger.error(f'URL 없음: Task ID {task_id}의 결과 데이터에 URL이 없습니다.')
            flash('분석 데이터에서 URL을 찾을 수 없습니다.', 'error')
            return redirect(url_for('main.home'))

        # [5] 세션 저장 최소화 (Phase 4: DB-centered architecture)
        # task_id 추적용으로만 세션 사용 (대용량 데이터는 MongoDB에서 직접 읽기)
        session['current_task_id'] = task_id
        session['last_completed_task_id'] = task_id

        # [6] 템플릿 렌더링용 변수 준비 (calculated 섹션에서 직접 추출)
        subpages_data = view_data.get('subpages', [])
        emission_trend_data = []  # 향후 구현 가능

        current_app.logger.info(f'Task ID {task_id}의 결과 페이지를 성공적으로 렌더링합니다.')

        # [7] SEO: 메타 데이터 및 Structured Data 생성
        meta = MetaDataGenerator.generate_analysis_meta(task_result, task_id)
        structured_data = [
            StructuredDataGenerator.generate_organization_schema(),
            StructuredDataGenerator.generate_analysis_article_schema(task_result, task_id),
            StructuredDataGenerator.generate_breadcrumb_schema([
                {'name': '홈', 'url': '/'},
                {'name': '분석 결과', 'url': f'/carbon_calculate_emission/{task_id}'}
            ])
        ]

        return render_template(
            'pages/analysis/carbon_calculate_emission.html',
            task_id=task_id,
            view_data=view_data,
            url=url,
            kb_weight=f"{calculated.get('kb_weight', 0):,.0f}",
            grade=None,  # 기존 grade_point 사용 안 함
            carbon_emission=calculated.get('carbon_emission'),
            global_avg_carbon=calculated.get('global_avg_carbon'),
            korea_avg_carbon=calculated.get('korea_avg_carbon'),
            korea_diff=calculated.get('korea_diff'),
            global_diff=calculated.get('global_diff'),
            korea_diff_abs=calculated.get('korea_diff_abs'),
            global_diff_abs=calculated.get('global_diff_abs'),
            institution_type=session.get('institution_type'),
            analysis_date=datetime.now(),
            emission_percentile=calculated.get('emission_percentile'),
            korea_carbon_emission_grade=calculated.get('emission_grade'),
            world_carbon_emission_grade=calculated.get('emission_grade'),
            subpages_data=subpages_data,
            emission_trend_data=json.dumps(emission_trend_data),
            korea_carbon_percentage_diff=calculated.get('korea_carbon_percentage_diff'),
            korea_comparison_status=calculated.get('korea_comparison_status'),  # DEPRECATED
            korea_emission_status=calculated.get('korea_emission_status', 'below_avg'),  # for i18n
            meta=meta,  # SEO meta data
            structured_data=structured_data  # Schema.org JSON-LD
        )

    except Exception as e:
        current_app.logger.error(f"결과 페이지 로딩 중 오류 발생: {e}", exc_info=True)
        flash('결과를 표시하는 중 오류가 발생했습니다.', 'error')
        return redirect(url_for('main.home'))

# ==========================================================================
# 🧪 정밀 분석 페이지 라우트 
# ==========================================================================
@main_bp.route('/detailed-analysis', methods=['GET', 'POST'])
def detailed_analysis():
    """정밀 분석 페이지 라우트 - 웹사이트의 상세 분석을 제공합니다."""
    # 페이지 조회 로깅
    task_id_for_logging = session.get('last_completed_task_id')
    log_page_view('detailed_analysis', task_id=task_id_for_logging)
    
    # 로컬 임포트로 순환 참조 방지
    from ecoweb.app.services.analysis.emissions import emissions_breakdown_from_bytes

    def normalize_url(u: str) -> str:
        """스킴/쿼리/프래그먼트 무시, www 제거, 말미 슬래시 제거, 소문자화.
        비교는 scheme을 제외하고 netloc+path 기준으로 수행한다."""
        if not u:
            return ''
        try:
            u = u.strip()
            parts = urlsplit(u)
            netloc = parts.netloc.lower()
            if netloc.startswith('www.'):
                netloc = netloc[4:]
            path = parts.path.rstrip('/')
            # scheme, query, fragment 제거하고 netloc+path만 반환
            return f"{netloc}{path}"
        except Exception:
            return (u or '').lower().rstrip('/').replace('http://', '').replace('https://', '').lstrip('www.')

    # Phase 4: DB-centered architecture - 세션에서 task_id 가져와서 DB 조회
    task_id = session.get('last_completed_task_id')
    url = None
    subpages = []
    total_byte_weight = None
    emissions_breakdown = None  # 초기화
    content_emission_data = []  # 초기화
    korea_carbon_percentage_diff = None  # 초기화
    korea_comparison_status = None  # 초기화 (DEPRECATED)
    korea_emission_status = 'below_avg'  # 초기화 (for i18n)

    if task_id:
        # DB에서 task_id로 최신 분석 결과 조회
        mongo_db = db.get_db()
        task_results_collection = mongo_db.task_results
        # MongoDB Projection: detailed_analysis에 필요한 필드 조회
        result_doc = task_results_collection.find_one(
            {'_id': task_id},
            {
                'status': 1,
                'result': 1  # 전체 result 객체 조회 (partial object 문제 방지)
            }
        )

        if result_doc and result_doc.get('status') in ['SUCCESS', 'MEASUREMENT_COMPLETE']:
            result = result_doc.get('result', {})
            url = result.get('url')
            subpages = result.get('subpages', [])
            total_byte_weight = result.get('total_byte_weight')

            # calculated 섹션에서 사전 계산된 데이터 가져오기 (Phase 3: DB-centered)
            calculated = result.get('calculated', {})
            emissions_breakdown = calculated.get('emissions_breakdown')
            content_emission_data = calculated.get('content_emission_data', [])
            content_count_data = calculated.get('content_count_data', [])  # tasks.py에서 계산된 데이터 사용
            korea_carbon_percentage_diff = calculated.get('korea_carbon_percentage_diff')
            korea_comparison_status = calculated.get('korea_comparison_status')  # DEPRECATED
            korea_emission_status = calculated.get('korea_emission_status', 'below_avg')

    # 하위 호환성: task_id가 없거나 DB 조회 실패 시 세션에서 읽기 (기존 동작)
    if not url:
        url = session.get('url')
        subpages = session.get('subpages', [])
        view_data_json = session.get('view_data')
        if view_data_json:
            try:
                vd = json.loads(view_data_json)
                total_byte_weight = vd.get('total_byte_weight')
            except Exception:
                pass

    # 3) 배출량 상세 breakdown: DB에서 가져온 값이 없으면 계산 (하위 호환성)
    if not emissions_breakdown:
        try:
            emissions_breakdown = emissions_breakdown_from_bytes(total_byte_weight or 0, region='korea', round_digits=4)
        except Exception:
            emissions_breakdown = {}

    # 3-1) 네트워크 상세값(해저/외부/홈) 파생 생성
    # 요구사항: 네트워크 총량은 해저 케이블로 두고, 디바이스와 네트워크 사이 구간에
    # 두 개의 중간값을 생성해 각각 외부 네트워크, 홈 네트워크로 할당
    try:
        device_g = float(((emissions_breakdown or {}).get('device') or {}).get('total_g') or 0)
        network_g = float(((emissions_breakdown or {}).get('network') or {}).get('total_g') or 0)
        # sea = network
        sea_g = network_g
        # 외부/홈은 net~device 구간에서 등분값 (예: 1/3, 2/3)
        diff = device_g - network_g
        external_g = network_g + diff * (1.0/3.0)
        home_g = network_g + diff * (2.0/3.0)
        # 소수 정리(템플릿에서 %.2f 포맷 사용하므로 원값은 float 유지)
        emissions_breakdown['network_detail'] = {
            'sea_g': sea_g,
            'external_g': external_g,
            'home_g': home_g,
        }
    except Exception:
        if isinstance(emissions_breakdown, dict):
            emissions_breakdown.setdefault('network_detail', {
                'sea_g': 0.0,
                'external_g': 0.0,
                'home_g': 0.0,
            })

    # 4) 서브페이지별 탄소배출량(g) 계산 및 템플릿용 데이터 구성
    enriched_subpages = []
    total_emission_g = 0.0
    # 현재 요청 URL 정규화
    current_url_norm = normalize_url(url or '')
    try:
        for sp in (subpages or []):
            # sp는 dict 또는 문자열일 수 있음
            # 먼저 URL 동일성 검사(요청 URL과 같은 항목 제외)
            try:
                sp_url_raw = ''
                if isinstance(sp, dict):
                    sp_url_raw = str(sp.get('url') or '')
                else:
                    sp_url_raw = str(sp)
                sp_url_norm = normalize_url(sp_url_raw)
                if current_url_norm and sp_url_norm and (sp_url_norm == current_url_norm):
                    continue  # 동일 URL은 제외
            except Exception:
                pass

            if isinstance(sp, dict):
                kb = None
                if 'total_kb' in sp:
                    kb = sp.get('total_kb')
                elif 'total_bytes' in sp:
                    try:
                        kb = (float(sp.get('total_bytes') or 0) / 1024.0)
                    except Exception:
                        kb = 0.0
                emission_g = 0.0
                if kb is not None:
                    try:
                        emission_g = float(estimate_emission_from_kb(kb))
                    except Exception:
                        emission_g = 0.0
                sp_en = dict(sp)
                sp_en['emission_g'] = round(emission_g, 2)
                enriched_subpages.append(sp_en)
                total_emission_g += emission_g
            else:
                # 문자열 URL만 있는 경우
                enriched_subpages.append({'url': str(sp), 'emission_g': 0.0})
    except Exception:
        # 실패하더라도 기존 subpages로 폴백
        enriched_subpages = subpages or []
        total_emission_g = 0.0

    avg_emission_g = 0.0
    if enriched_subpages:
        try:
            cnt = max(1, len(enriched_subpages))
            avg_emission_g = round(total_emission_g / cnt, 2)
        except Exception:
            avg_emission_g = 0.0
    total_emission_g = round(total_emission_g, 2)

    # 상대 막대 길이 계산을 위한 최대값
    max_emission_g = 0.0
    try:
        max_emission_g = max((sp.get('emission_g') or 0.0) for sp in enriched_subpages) if enriched_subpages else 0.0
    except Exception:
        max_emission_g = 0.0

    if max_emission_g > 0:
        for sp in enriched_subpages:
            try:
                pct = (float(sp.get('emission_g') or 0.0) / max_emission_g) * 100.0
            except Exception:
                pct = 0.0
            # 최소 가시성 확보를 위해 4% 하한 적용 (0은 0 유지)
            if pct > 0 and pct < 4:
                pct = 4.0
            sp['emission_pct'] = round(pct, 2)
    else:
        for sp in enriched_subpages:
            sp['emission_pct'] = 0.0

    # user-bar 데이터는 위에서 이미 calculated 섹션에서 가져왔음 (중복 조회 제거)

    # SEO: 메타 데이터 및 Structured Data 생성
    meta = MetaDataGenerator.generate_detailed_analysis_meta(url or 'N/A')
    structured_data = [
        StructuredDataGenerator.generate_organization_schema(),
        StructuredDataGenerator.generate_breadcrumb_schema([
            {'name': '홈', 'url': '/'},
            {'name': '분석 결과', 'url': f'/carbon_calculate_emission/{task_id}' if task_id else '/'},
            {'name': '상세 분석', 'url': '/detailed-analysis'}
        ])
    ]

    # 콘텐츠 카운트 데이터가 없으면 빈 리스트로 초기화
    if 'content_count_data' not in locals():
        content_count_data = []
    
    return render_template(
        'pages/analysis/detailed_analysis.html',
        task_id=task_id,  # task_id 추가
        url=url or 'N/A',
        subpages=enriched_subpages,
        emissions_breakdown=emissions_breakdown,
        content_emission_data=content_emission_data,  # 콘텐츠 유형별 배출량 데이터
        content_count_data=content_count_data,  # 콘텐츠 타입별 카운트 데이터 (파이차트용)
        avg_emission_g=avg_emission_g,
        total_emission_g=total_emission_g,
        # user-bar 데이터
        korea_carbon_percentage_diff=korea_carbon_percentage_diff,
        korea_comparison_status=korea_comparison_status,  # DEPRECATED
        korea_emission_status=korea_emission_status,  # for i18n
        meta=meta,  # SEO meta data
        structured_data=structured_data  # Schema.org JSON-LD
    )

# ==========================================================================
# 🌱 지속 가능성 가이드라인 페이지 라우트
# ==========================================================================
@main_bp.route('/guidelines')
def guidelines_page():
    # 페이지 조회 로깅
    task_id_for_logging = session.get('last_completed_task_id')
    log_page_view('sustainability_analysis', task_id=task_id_for_logging)
    
    # Use module-level DATA_FILE_PATH (points to data/urls/wsg_guideline.json)
    json_paths_to_try = [
        DATA_FILE_PATH,
        os.path.join(current_app.root_path, 'data', 'urls', 'wsg_guideline.json'),
        os.path.join(current_app.root_path, '..', 'data', 'guidelines.json'),
    ]

    full_json_data = {}
    last_error = None
    for path in json_paths_to_try:
        try:
            with open(path, 'r', encoding='utf-8') as f:
                full_json_data = json.load(f)
                current_app.logger.info(f"Loaded guidelines JSON from: {path}")
                break
        except FileNotFoundError as e:
            last_error = e
            continue
        except json.JSONDecodeError as e:
            last_error = e
            break

    if not full_json_data:
        current_app.logger.error(f"Failed to load guidelines JSON. Last error: {last_error}")
        flash('지속 가능성 가이드라인 파일을 찾을 수 없거나 형식 오류입니다.', 'error')

    processed_guidelines = []
    if isinstance(full_json_data, dict):
        categories = full_json_data.get('category', [])
        if isinstance(categories, list):
            for category_item in categories:
                if isinstance(category_item, dict):
                    guidelines_in_category = category_item.get('guidelines', [])
                    # Use shortName for prefix (e.g., 'UX'), default to 'CAT' if not found
                    category_prefix = category_item.get('shortName', category_item.get('name', 'CAT'))
                    # Simplify prefix if it's like 'UX Design' to just 'UX'
                    if isinstance(category_prefix, str) and ' ' in category_prefix:
                        category_prefix = category_prefix.split(' ')[0]

                    if isinstance(guidelines_in_category, list):
                        for guideline_data in guidelines_in_category:
                            if isinstance(guideline_data, dict):
                                display_id = f"{category_prefix}-{guideline_data.get('id', 'N/A')}"
                                title = guideline_data.get('guideline', 'No title provided')

                                # Extract description from the first item in criteria list
                                criteria_list = guideline_data.get('criteria', [])
                                description_text = 'N/A'
                                if criteria_list and isinstance(criteria_list, list) and len(criteria_list) > 0 and isinstance(criteria_list[0], dict):
                                    description_text = criteria_list[0].get('description', 'N/A')

                                # Explicit benefits processing to ensure a dictionary is passed to the template
                                current_benefits_value_for_template = {} # Default to an empty dict
                                raw_benefits_from_json = guideline_data.get('benefits')

                                if isinstance(raw_benefits_from_json, list):
                                    if len(raw_benefits_from_json) > 0:
                                        first_item_in_benefits_list = raw_benefits_from_json[0]
                                        if isinstance(first_item_in_benefits_list, dict):
                                            current_benefits_value_for_template = first_item_in_benefits_list

                                effort_str = guideline_data.get('effort')
                                impact_str = guideline_data.get('impact')
                                effort_display_val = get_level_display(effort_str)
                                impact_display_val = get_level_display(impact_str)

                                # Mock compliance status
                                compliance_status = random.choice([True, False])

                                processed_guidelines.append({
                                    'id': display_id,
                                    'title': title,
                                    'area': category_item.get('name', 'N/A'),
                                    'effort': guideline_data.get('effort'), # Value from JSON
                                    'impact': guideline_data.get('impact'), # Value from JSON
                                    'effort_display': effort_display_val,
                                    'impact_display': impact_display_val,
                                    'description': description_text,
                                    'intent': guideline_data.get('intent', 'N/A'),
                                    'benefits': current_benefits_value_for_template, # Guaranteed to be a dict
                                    'compliance_status': compliance_status  # Added compliance status
                                })
    
    # Prepare top_urgent_items
    non_compliant_guidelines = [g for g in processed_guidelines if not g['compliance_status']]

    level_to_numeric = {
        "High": 3, "높음": 3,
        "Medium": 2, "중간": 2,
        "Low": 1, "낮음": 1
    }

    def calculate_priority_score(guideline):
        impact_str = guideline.get('impact')
        effort_str = guideline.get('effort')
        
        numeric_impact = level_to_numeric.get(impact_str, 0) # Default to 0 if unknown
        numeric_effort = level_to_numeric.get(effort_str, 1) # Default to 1 if unknown to avoid division by zero
        
        if numeric_effort == 0: # Should not happen with default 1
            return 0 
        return numeric_impact / numeric_effort

    # Sort non-compliant guidelines by the calculated priority score, descending
    non_compliant_guidelines.sort(key=calculate_priority_score, reverse=True)
    
    top_urgent_items_for_stats = []
    for g in non_compliant_guidelines[:3]: # Take top 3
        top_urgent_items_for_stats.append({
            'id': g['id'],
            'title': g['title'],
            'effort_display': g['effort_display'],
            'impact_display': g['impact_display'],
            # Add original effort/impact if needed by other parts of template, though not for display here
            'effort': g['effort'], 
            'impact': g['impact'] 
        })

    stats_data = {
        'overall_score': '56/92', # Placeholder
        'categories': [
            {'name': 'UX', 'score': '12/29', 'priority': 10},
            {'name': 'Hosting', 'score': '10/12', 'priority': 7},
            {'name': 'Web Design', 'score': '15/22', 'priority': 8},
            {'name': 'BM', 'score': '19/29', 'priority': 6}
        ],
        'radar_chart_labels': ['UX', 'Hosting', 'Web Design', 'BM'], # Updated labels
        'radar_chart_data': [12, 10, 15, 19], # Example data for radar chart
        'score_trend_labels': ['Jan', 'Feb', 'Mar', 'Apr'], # Example labels for line chart
        'score_trend_data': [50, 55, 52, 60], # Example data for line chart
        'top_urgent_items': top_urgent_items_for_stats
    }

    # Calculate category scores and priorities for '카테고리별 상세'
    # Phase 4: 세션에서 task_id와 url 가져오기 (sidebar 표시용)
    task_id = session.get('last_completed_task_id')
    url = None
    korea_carbon_percentage_diff = None
    korea_comparison_status = None  # DEPRECATED
    korea_emission_status = 'below_avg'  # for i18n

    if task_id:
        try:
            mongo_db = db.get_db()
            task_doc = mongo_db.task_results.find_one(
                {'_id': task_id},
                {'result.url': 1, 'result.calculated': 1}
            )
            if task_doc and 'result' in task_doc:
                result = task_doc['result']
                url = result.get('url')
                # user-bar 데이터
                calculated = result.get('calculated', {})
                korea_carbon_percentage_diff = calculated.get('korea_carbon_percentage_diff')
                korea_comparison_status = calculated.get('korea_comparison_status')  # DEPRECATED
                korea_emission_status = calculated.get('korea_emission_status', 'below_avg')
        except Exception as e:
            current_app.logger.warning(f'guidelines_page에서 URL 조회 실패: {e}')

    # SEO: 메타 데이터 및 Structured Data 생성
    meta = MetaDataGenerator.generate_guidelines_meta()
    structured_data = [
        StructuredDataGenerator.generate_organization_schema(),
        StructuredDataGenerator.generate_breadcrumb_schema([
            {'name': '홈', 'url': '/'},
            {'name': '지속가능성 가이드라인', 'url': '/guidelines'}
        ])
    ]

    return render_template('pages/analysis/sustainability_analysis.html',
                           task_id=task_id,
                           url=url,
                           guidelines=processed_guidelines,
                           stats=stats_data,
                           # user-bar 데이터
                           korea_carbon_percentage_diff=korea_carbon_percentage_diff,
                           korea_comparison_status=korea_comparison_status,  # DEPRECATED
                           korea_emission_status=korea_emission_status,  # for i18n
                           meta=meta,  # SEO meta data
                           structured_data=structured_data)  # Schema.org JSON-LD
# ==========================================================================
# ✅ 프로세스 관리 함수
# ==========================================================================
def process_queued_tasks():
    db = get_db()
    active_tasks = get_active_celery_tasks()
    CELERY_QUEUE_THRESHOLD = 5

    if active_tasks < CELERY_QUEUE_THRESHOLD:
        # Find the oldest queued task and update its status to prevent race conditions
        queued_task_doc = db.task_results.find_one_and_update(
            {'status': 'QUEUED'},
            {'$set': {'status': 'PROCESSING'}},
            sort=[('created_at', 1)]
        )

        if queued_task_doc:
            url = queued_task_doc['url']
            user_id = queued_task_doc.get('user_id', 'anonymous')
            is_mobile = queued_task_doc.get('is_mobile', False)
            original_task_id = queued_task_doc['_id'] # This is the original, unique ID from the queue
            existing_lighthouse_data = queued_task_doc.get('existing_lighthouse_data')

            # Submit the task to Celery, 기존 데이터가 있으면 함께 전달
            if existing_lighthouse_data:
                task = analyze_url_task.delay(url, user_id, is_mobile, original_task_id,
                                            perform_subpage_crawling=True, existing_view_data=existing_lighthouse_data)
                print(f'[큐 처리] 기존 Lighthouse 데이터 활용하여 작업 시작: {original_task_id}')
            else:
                task = analyze_url_task.delay(url, user_id, is_mobile, original_task_id)
            new_celery_id = task.id

            # Update the document with the new Celery task ID and a proper initial state
            db.task_results.update_one(
                {'_id': original_task_id}, # Find by the original, unique ID
                {'$set': {'celery_task_id': new_celery_id, 'status': 'PENDING'}}
            )

            current_app.logger.info(f"Queued task {original_task_id} for {url} started with new Celery ID {new_celery_id}.")
        else:
            current_app.logger.debug("No queued tasks to process.")
    else:
        current_app.logger.debug(f"Queue processing skipped. Active tasks: {active_tasks}")


# ==========================================================================
# 📁 new-ui 파일 제공 라우트 
# ==========================================================================
@main_bp.route('/pages/main/<path:filename>')
def serve_ui_files(filename):
    return send_from_directory(os.path.join(current_app.root_path, 'templates', 'pages', 'main'), filename)

# ==========================================================================
# 📸 캡처 이미지 서빙 라우트
# ==========================================================================
@main_bp.route('/var/captures/<path:filename>')
def serve_capture_image(filename):
    """var/captures 디렉토리의 캡처 이미지 파일을 서빙"""
    from ecoweb.config import Config
    import os
    
    # var/captures 디렉토리 경로
    captures_dir = Config.CAPTURE_FOLDER
    file_path = os.path.join(captures_dir, filename)
    
    # 보안 체크: captures_dir 밖으로 나가는 경로 차단
    captures_dir_abs = os.path.abspath(captures_dir)
    file_path_abs = os.path.abspath(file_path)
    
    if not file_path_abs.startswith(captures_dir_abs):
        current_app.logger.warning(f"보안 위협: 캡처 디렉토리 밖으로 접근 시도: {file_path}")
        return jsonify({'error': 'Invalid path'}), 403
    
    # 파일 존재 확인
    if not os.path.exists(file_path):
        current_app.logger.warning(f"캡처 이미지 파일을 찾을 수 없습니다: {file_path}")
        return jsonify({'error': 'File not found'}), 404
    
    # 이미지 파일 서빙
    return send_from_directory(captures_dir, filename, mimetype='image/png')

# ==========================================================================
# 🖼️ 이미지 파일 서빙 라우트 (var/optimization_images 디렉토리)
# ==========================================================================
@main_bp.route('/var/optimization_images/<path:filename>')
def serve_image_file(filename):
    """var/optimization_images 디렉토리의 이미지 파일을 서빙"""
    from ecoweb.config import Config
    import os
    from mimetypes import guess_type
    
    # var/optimization_images 디렉토리 경로
    images_dir = Config.OPTIMIZATION_IMAGES_FOLDER
    file_path = os.path.join(images_dir, filename)
    
    # 보안 체크: images_dir 밖으로 나가는 경로 차단
    images_dir_abs = os.path.abspath(images_dir)
    file_path_abs = os.path.abspath(file_path)
    
    if not file_path_abs.startswith(images_dir_abs):
        current_app.logger.warning(f"보안 위협: 이미지 디렉토리 밖으로 접근 시도: {file_path}")
        return jsonify({'error': 'Invalid path'}), 403
    
    # 파일 존재 확인
    if not os.path.exists(file_path):
        current_app.logger.warning(f"이미지 파일을 찾을 수 없습니다: {file_path}")
        return jsonify({'error': 'File not found'}), 404
    
    # MIME 타입 자동 감지
    mime_type, _ = guess_type(file_path)
    if not mime_type:
        # 파일 확장자 기반 MIME 타입 설정
        if filename.lower().endswith('.webp'):
            mime_type = 'image/webp'
        elif filename.lower().endswith(('.png', '.jpg', '.jpeg', '.gif', '.svg')):
            mime_type = 'image/png' if filename.lower().endswith('.png') else \
                       'image/jpeg' if filename.lower().endswith(('.jpg', '.jpeg')) else \
                       'image/gif' if filename.lower().endswith('.gif') else 'image/svg+xml'
        else:
            mime_type = 'application/octet-stream'
    
    # 이미지 파일 서빙
    return send_from_directory(images_dir, filename, mimetype=mime_type)

# Path for sustainability guidelines JSON
DATA_FILE_PATH = os.path.join(os.path.dirname(__file__), '..', 'static', 'data', 'urls', 'wsg_guideline.json')

def get_level_display(level_str):
    """Converts '낮음', '중간', '높음' to a star rating string."""
    if level_str == "낮음" or level_str == "Low":
        return "★☆☆"
    elif level_str == "중간" or level_str == "Medium":
        return "★★☆"
    elif level_str == "높음" or level_str == "High":
        return "★★★"
    return "--- " # Default for unknown, added a space to ensure it's not empty visually

# ==========================================================================
# ⏳ URL 분석 로딩 페이지 
# ==========================================================================
@main_bp.route('/loading/<task_id>')
def loading(task_id):
    # [1] Phase 4: URL은 DB에서 조회 (세션 사용 안 함)
    # MongoDB Projection: URL 필드만 조회하여 성능 최적화
    url = ''
    try:
        mongo_db = db.get_db()
        task_doc = mongo_db.task_results.find_one(
            {'_id': task_id},
            {'url': 1, '_id': 0}  # Projection: URL만 가져오기
        )
        if task_doc:
            # URL은 task_results 문서에 직접 저장되어 있음
            url = task_doc.get('url', '')
    except Exception as e:
        current_app.logger.warning(f'로딩 페이지에서 URL 조회 실패: {e}')

    return render_template('pages/common/loading.html', task_id=task_id, url=url)

# ==========================================================================
# ✔️ URL 분석 상태 확인 엔드포인트 
# ==========================================================================
@main_bp.route('/check_status/<task_id>')
def check_status(task_id):
    try:
        db = get_db()
    except Exception as e:
        # MongoDB 연결 실패 시 적절한 에러 응답 반환
        current_app.logger.error(f"MongoDB 연결 실패 (check_status): {str(e)}")
        return jsonify({
            'status': 'ERROR',
            'error': '데이터베이스 연결에 실패했습니다. 잠시 후 다시 시도해주세요.',
            'error_type': 'DATABASE_CONNECTION_ERROR'
        }), 503  # Service Unavailable
    
    try:
        # The task_id from the URL is our original_task_id (UUID)
        # MongoDB Projection: 상태 확인에 필요한 필드만 조회
        task_doc = db.task_results.find_one(
            {'_id': task_id},
            {
                'status': 1,
                'progress': 1,
                'celery_task_id': 1,
                'created_at': 1,
                'cancellation_reason': 1,
                'cancelled_at': 1
            }
        )

        if not task_doc:
            return jsonify({'status': 'NOT_FOUND'}), 404

        # If the task status is final in our DB, we can trust it.
        if task_doc.get('status') in ['SUCCESS', 'FAILURE', 'MEASUREMENT_COMPLETE', 'CANCELLED']:
            # Phase 4: 더 이상 세션에 subpages를 저장하지 않음 (DB에서 직접 읽기)
            response_data = {
                'status': task_doc['status'],
                'progress': task_doc.get('progress')
            }

            # 취소된 작업의 경우 추가 정보 포함
            if task_doc.get('status') == 'CANCELLED':
                response_data['cancellation_reason'] = task_doc.get('cancellation_reason', 'unknown')
                response_data['cancelled_at'] = task_doc.get('cancelled_at')

            return jsonify(response_data)

        # If the task is queued, calculate its position.
        if task_doc.get('status') == 'QUEUED':
            queued_tasks_before = db.task_results.count_documents({
                'status': 'QUEUED',
                'created_at': {'$lt': task_doc.get('created_at', datetime.now(timezone.utc))}
            })
            queue_position = queued_tasks_before + 1
            return jsonify({'status': 'QUEUED', 'queue_position': queue_position, 'progress': task_doc.get('progress')})

        # If the task is PENDING, PROCESSING, or STARTED, check Celery for a more current state.
        celery_task_id = task_doc.get('celery_task_id')
        if not celery_task_id:
            # This can happen if the task is queued but not yet processed by process_queued_tasks
            return jsonify({'status': 'QUEUED', 'queue_position': 'N/A', 'progress': task_doc.get('progress')})

        task_result = AsyncResult(celery_task_id, app=celery)

        # Phase 2 수정: Celery 상태가 SUCCESS이고 DB가 아직 업데이트 안 된 경우 처리
        celery_state = task_result.state

        # Celery가 SUCCESS이면 DB 상태 한 번 더 확인 (재조회)
        if celery_state == 'SUCCESS':
            # DB에서 최신 상태 재조회
            task_doc_refresh = db.task_results.find_one(
                {'_id': task_doc['_id']},
                {'status': 1, 'progress': 1}
            )
            if task_doc_refresh:
                db_status = task_doc_refresh.get('status')
                # DB에 MEASUREMENT_COMPLETE 또는 SUCCESS가 쓰였으면 그것 반환
                if db_status in ['SUCCESS', 'MEASUREMENT_COMPLETE']:
                    return jsonify({
                        'status': db_status,
                        'progress': task_doc_refresh.get('progress')
                    })

            # DB에 아직 안 쓰였으면 Celery SUCCESS를 그대로 반환
            # (프론트엔드에서 SUCCESS도 완료 상태로 처리)
            return jsonify({
                'status': 'SUCCESS',
                'progress': task_doc.get('progress')
            })

        # Return the current state from Celery. The final state will be written to DB by the task itself.
        meta = None
        try:
            meta = task_result.info if hasattr(task_result, 'info') else None
        except Exception:
            meta = None
        return jsonify({'status': celery_state, 'progress': task_doc.get('progress'), 'meta': meta})
    
    except Exception as e:
        # MongoDB 쿼리 중 발생한 예외 처리
        current_app.logger.error(f"MongoDB 쿼리 오류 (check_status): {str(e)}")
        return jsonify({
            'status': 'ERROR',
            'error': '작업 상태를 확인하는 중 오류가 발생했습니다. 잠시 후 다시 시도해주세요.',
            'error_type': 'DATABASE_QUERY_ERROR'
        }), 500

# ==========================================================================
# 🚫 작업 취소 라우트
# ==========================================================================
@main_bp.route('/cancel_task/<task_id>', methods=['POST'])
def cancel_task(task_id):
    """
    모든 유형의 작업을 취소합니다.

    지원하는 작업 유형:
    - analyze_url_task (Lighthouse 분석)
    - 향후 추가될 다른 Celery 작업들
    """
    current_app.logger.info(f"[CANCEL_ENDPOINT] Received cancellation request for task: {task_id}")
    current_app.logger.info(f"[CANCEL_ENDPOINT] Request method: {request.method}, Content-Type: {request.content_type}")
    current_app.logger.info(f"[CANCEL_ENDPOINT] Request data: {request.get_data()}")

    try:
        db_handle = get_db()
        # MongoDB Projection: 취소 처리에 필요한 필드만 조회
        task_doc = db_handle.task_results.find_one(
            {'_id': task_id},
            {
                'status': 1,
                'celery_task_id': 1,
                'progress': 1
            }
        )

        if not task_doc:
            return jsonify({'status': 'error', 'message': 'Task not found'}), 404

        # 이미 취소된 작업은 중복 처리하지 않음
        if task_doc.get('status') == 'CANCELLED':
            log_task_cancellation(task_id, "already_cancelled", current_app.logger)
            return jsonify({'status': 'already_cancelled', 'message': 'Task already cancelled'})

        # 요청에서 취소 사유 추출
        cancellation_reason = 'user_cancelled'
        if request.json:
            cancellation_reason = request.json.get('reason', 'user_cancelled')
        
        # 이벤트 로깅: 분석 취소
        user_id = session.get('user_id')
        log_analysis_cancel(task_id, user_id=str(user_id) if user_id else None)

        # 완료된 작업이라도 Celery 워커가 아직 실행 중일 수 있으므로 정리
        completed_statuses = ['SUCCESS', 'FAILURE', 'MEASUREMENT_COMPLETE']
        if task_doc.get('status') in completed_statuses:
            current_app.logger.info(f"Task {task_id} is {task_doc.get('status')}, but cleaning up any remaining processes")

            cleanup_success = _cleanup_celery_task(task_doc.get('celery_task_id'), task_id)
            log_task_cancellation(task_id, f"cleanup_after_completion:{cancellation_reason}", current_app.logger)

            return jsonify({
                'status': 'cleaned_up',
                'message': 'Task completed but background processes cleaned up',
                'cleanup_success': cleanup_success
            })

        # 진행 중인 작업 취소
        revoke_success = _cleanup_celery_task(task_doc.get('celery_task_id'), task_id)

        # MongoDB에서 작업 상태를 취소됨으로 업데이트
        update_data = {
            'status': 'CANCELLED',
            'cancelled_at': datetime.utcnow(),
            'cancellation_reason': cancellation_reason,
            'progress.updated_at': datetime.utcnow().isoformat(),
            'celery_revoke_success': revoke_success
        }

        # 진행 단계별 취소 상태 업데이트 (일반화)
        _update_progress_steps_cancelled(task_doc, update_data)

        result = db_handle.task_results.update_one(
            {'_id': task_id},
            {'$set': update_data}
        )

        if result.modified_count > 0:
            log_task_cancellation(task_id, cancellation_reason, current_app.logger)
            current_app.logger.info(f"Task {task_id} successfully cancelled by user. Reason: {cancellation_reason}")
            return jsonify({
                'status': 'success',
                'message': 'Task cancelled successfully',
                'cancellation_reason': cancellation_reason,
                'celery_revoke_success': revoke_success
            })
        else:
            current_app.logger.warning(f"Failed to update task {task_id} status to cancelled")
            return jsonify({'status': 'error', 'message': 'Failed to cancel task'}), 500

    except Exception as e:
        current_app.logger.error(f"Error cancelling task {task_id}: {e}", exc_info=True)
        return jsonify({'status': 'error', 'message': 'Internal server error'}), 500


def _cleanup_celery_task(celery_task_id, task_id):
    """
    Celery 작업을 정리합니다.

    Returns:
        bool: 정리 성공 여부
    """
    if not celery_task_id:
        return True  # Celery ID가 없으면 정리할 것도 없음

    try:
        task_result = AsyncResult(celery_task_id, app=celery)

        # 실행 중인 작업만 revoke
        if task_result.state in ['PENDING', 'STARTED', 'PROGRESS']:
            task_result.revoke(terminate=True)
            current_app.logger.info(f"Celery task {celery_task_id} revoked for task_id {task_id}")
            return True
        else:
            current_app.logger.info(f"Celery task {celery_task_id} was in state {task_result.state}, no revoke needed")
            return True

    except Exception as e:
        current_app.logger.warning(f"Failed to revoke Celery task {celery_task_id}: {e}")
        return False


def _update_progress_steps_cancelled(task_doc, update_data):
    """
    작업의 진행 단계를 취소 상태로 업데이트합니다.

    다양한 작업 유형의 단계 구조를 자동으로 감지하여 처리합니다.
    """
    try:
        progress = task_doc.get('progress', {})
        current_step = progress.get('current_step')
        steps = progress.get('steps', {})

        # 현재 단계가 있으면 해당 단계를 취소로 마크
        if current_step and current_step in steps:
            update_data[f'progress.steps.{current_step}'] = {
                'status': 'cancelled',
                'message': '사용자에 의해 취소됨'
            }

        # 알려진 단계들도 처리 (하위 호환성)
        known_steps = ['input', 'subpages', 'image_opt', 'processing', 'analysis', 'output']
        for step in known_steps:
            if step in steps and steps[step].get('status') == 'in_progress':
                update_data[f'progress.steps.{step}'] = {
                    'status': 'cancelled',
                    'message': '사용자에 의해 취소됨'
                }

    except Exception as e:
        current_app.logger.warning(f"Failed to update progress steps for cancelled task: {e}")

# ==========================================================================
# 🖱️ 클릭 이벤트 로깅 라우트 (기존 - 하위 호환성 유지)
# ==========================================================================
@main_bp.route('/log-click', methods=['POST'])
def log_click_event():
    data = request.get_json()
    if not data or 'element_id' not in data or 'page_url' not in data:
        return jsonify({'status': 'error', 'message': 'Missing data'}), 400

    session_id = session.sid
    element_id = data['element_id']
    page_url = data['page_url']

    # 데이터베이스에 클릭 이벤트 기록 (중복 방지)
    try:
        mongo_db = db.get_db()
        click_events = mongo_db.click_events
        
        # session_id와 element_id를 기준으로 고유한 클릭을 보장
        click_events.update_one(
            {'session_id': session_id, 'element_id': element_id},
            {
                '$setOnInsert': {
                    'session_id': session_id,
                    'element_id': element_id,
                    'page_url': page_url,
                    'timestamp': datetime.utcnow()
                }
            },
            upsert=True
        )
        return jsonify({'status': 'success', 'message': 'Click logged'})
    except Exception as e:
        current_app.logger.error(f"Error logging click event: {e}")
        return jsonify({'status': 'error', 'message': 'Internal server error'}), 500


# ==========================================================================
# 📊 사용자 이벤트 로깅 API (선택적 - 수동 호출용)
# ==========================================================================
# 참고: 현재는 서버 사이드 로깅만 사용하며, 클라이언트 사이드 자동 추적은 사용하지 않습니다.
# 이 엔드포인트는 필요 시 수동으로 이벤트를 기록하기 위해 유지됩니다.
@main_bp.route('/api/log-event', methods=['POST'])
def log_event():
    """
    수동으로 사용자 이벤트를 기록합니다.
    (현재는 서버 사이드 로깅만 사용하므로 일반적으로 사용되지 않음)
    
    Request Body:
    {
        "event_type": "button_click",
        "event_category": "navigation",
        "element_id": "measureBtn",
        "metadata": {...}
    }
    """
    if not is_logging_enabled():
        return jsonify({'status': 'disabled', 'message': 'Event logging is disabled'}), 200
    
    try:
        data = request.get_json()
        if not data:
            return jsonify({'status': 'error', 'message': 'Missing JSON data'}), 400
        
        event_type = data.get('event_type')
        event_category = data.get('event_category', 'navigation')
        element_id = data.get('element_id')
        metadata = data.get('metadata')
        
        if not event_type:
            return jsonify({'status': 'error', 'message': 'event_type is required'}), 400
        
        # 이벤트 기록
        log_user_event(
            event_type=event_type,
            event_category=event_category,
            metadata=metadata,
            element_id=element_id
        )
        
        return jsonify({'status': 'success', 'message': 'Event logged'})
    except Exception as e:
        current_app.logger.error(f"Error logging event: {e}")
        return jsonify({'status': 'error', 'message': 'Internal server error'}), 500


@main_bp.route('/api/logging-status', methods=['GET'])
def logging_status():
    """
    이벤트 로깅 활성화 상태를 반환합니다.
    (현재는 서버 사이드 로깅만 사용하므로 일반적으로 사용되지 않음)
    """
    return jsonify({
        'enabled': is_logging_enabled()
    })



# ==========================================================================
# ✨ 소개 페이지
# ==========================================================================
@main_bp.route('/about')
def about():
    # SEO: 메타 데이터 및 Structured Data 생성
    meta = MetaDataGenerator.generate_about_meta()
    structured_data = [
        StructuredDataGenerator.generate_organization_schema(),
        StructuredDataGenerator.generate_breadcrumb_schema([
            {'name': '홈', 'url': '/'},
            {'name': 'eCarbon 소개', 'url': '/about'}
        ])
    ]

    return render_template(
        'pages/main/about.html',
        meta=meta,
        structured_data=structured_data
    )

# ==========================================================================
# 🎟️ 회원권 페이지
# ==========================================================================
@main_bp.route('/membership/plans')
def membership_plans():
    # SEO: 메타 데이터 및 Structured Data 생성
    meta = MetaDataGenerator.generate_page_meta(
        title="eCarbon 회원권 - 프리미엄 플랜",
        description="eCarbon 프리미엄 회원권으로 무제한 웹사이트 분석, 우선 지원, 고급 리포트 기능을 이용하세요.",
        canonical_path="/membership/plans",
        og_type='website',
        keywords=['회원권', '프리미엄', '무제한 분석', 'eCarbon 플랜']
    )
    structured_data = [
        StructuredDataGenerator.generate_organization_schema(),
        StructuredDataGenerator.generate_breadcrumb_schema([
            {'name': '홈', 'url': '/'},
            {'name': '회원권', 'url': '/membership/plans'}
        ])
    ]

    return render_template(
        'pages/membership/membership-plans.html',
        meta=meta,
        structured_data=structured_data
    )

# ==========================================================================
# 🎖️ 뱃지 페이지
# ==========================================================================
@main_bp.route('/badge')
def badge():
    # SEO: 메타 데이터 및 Structured Data 생성
    meta = MetaDataGenerator.generate_page_meta(
        title="eCarbon 뱃지 - 친환경 웹사이트 인증",
        description="eCarbon 뱃지로 친환경 웹사이트를 인증받고, 방문자에게 환경 보호 노력을 알리세요.",
        canonical_path="/badge",
        og_type='website',
        keywords=['eCarbon 뱃지', '친환경 인증', '웹사이트 인증', '탄소중립']
    )
    structured_data = [
        StructuredDataGenerator.generate_organization_schema(),
        StructuredDataGenerator.generate_breadcrumb_schema([
            {'name': '홈', 'url': '/'},
            {'name': '뱃지', 'url': '/badge'}
        ])
    ]

    return render_template(
        'badge.html',  # 실제 템플릿 경로
        meta=meta,
        structured_data=structured_data
    )

# ==========================================================================
# 🚫 에러 페이지 
# ==========================================================================
@main_bp.route('/error')
def error():
    return render_template('pages/error/error.html')

# ==================================================================================================
# @main_bp.route('/gov-analysis')
# def gov_analysis():
#     global_avg_carbon = session.get('global_avg_carbon')    
#     korea_avg_carbon = session.get('korea_avg_carbon')
#     carbon_emission = session.get('carbon_emission')
#     global_diff = session.get('global_diff')
#     korea_diff = session.get('korea_diff')
#     global_diff_abs = session.get('global_diff_abs')
#     korea_diff_abs = session.get('korea_diff_abs')
    
#     # MongoDB에서 monthly_stats 콜렉션 데이터 가져오기
#     from datetime import datetime, timedelta
#     import random
    
#     # 현재 날짜에서 이전 달 첫날 구하기
#     today = datetime.now()
#     last_month_start = datetime(today.year, today.month, 1) - timedelta(days=1)
#     last_month_start = datetime(last_month_start.year, last_month_start.month, 1)
    
#     # 12개월 전 날짜 계산
#     twelve_months_ago = last_month_start - timedelta(days=365)
    
#     # 이전 12개월 각 월의 날짜 및 월문자열 준비
#     month_dates = []
#     month_strings = []
    
#     for i in range(12):
#         # 현재로부터 i개월 이전
#         month_date = datetime(today.year, today.month, 1) - timedelta(days=30 * (i+1))
#         month_dates.append(month_date)
#         month_strings.append(month_date.strftime('%Y-%m'))
    
#     # DB에서 데이터 조회 시도
#     monthly_emissions_data = []
#     db_data_months = set()  # DB에서 가져온 데이터의 월 기록
    
#     try:
#         # MongoDB 연결
#         mongo_db = db.get_db()
        
#         # 월별 통계 콜렉션 존재 확인
#         collections = mongo_db.list_collection_names()
#         print(f"MongoDB 콜렉션 목록: {collections}")
        
#         if 'monthly_stats' in collections:
#             # 조회 조건 출력
#             print(f"twelve_months_ago: {twelve_months_ago}, last_month_start: {last_month_start}")
            
#             # monthly_stats 콜렉션에서 최근 12개월 데이터 조회
#             query = {'month': {'$gte': twelve_months_ago, '$lte': last_month_start}}
#             print(f"MongoDB 쿼리: {query}")
            
#             try:
#                 monthly_stats_data = list(mongo_db.monthly_stats.find(query).sort('month', 1))
#                 print(f"monthly_stats 콜렉션 조회 결과: {len(monthly_stats_data)}개 데이터")
                
#                 # DB에서 가져온 데이터 처리
#                 if len(monthly_stats_data) > 0:
#                     for stat in monthly_stats_data:
#                         if 'month' in stat and 'avgEmission' in stat:
#                             month_str = stat['month'].strftime('%Y-%m')
#                             db_data_months.add(month_str)  # 이미 처리한 월 기록
                            
#                             monthly_emissions_data.append({
#                                 'month': month_str,
#                                 'avgEmission': round(stat['avgEmission'], 2)
#                             })
#                         else:
#                             print(f"monthly_stats 데이터 형식 오류: {stat.keys()}")
#             except Exception as inner_e:
#                 print(f"monthly_stats 콜렉션 조회 중 오류: {str(inner_e)}")
#     except Exception as e:
#         print(f"MongoDB 연결 오류: {str(e)}")
    
#     # DB에서 가져온 데이터가 12개월 보다 적으면 나머지 월은 테스트 데이터로 채우기
#     if len(monthly_emissions_data) < 12:
#         print(f"DB 데이터가 부족하여 테스트 데이터 추가: {len(monthly_emissions_data)}/12")
        
#         # 부족한 월에 대해 테스트 데이터 생성
#         for month_str in month_strings:
#             if month_str not in db_data_months:
#                 # 1.5~2.0 사이의 랜덤값 생성 (테스트용)
#                 random_emission = 1.5 + (random.random() * 0.5)
                
#                 monthly_emissions_data.append({
#                     'month': month_str,
#                     'avgEmission': round(random_emission, 2)
#                 })
    
#     # 월 순서대로 정렬
#     monthly_emissions_data.sort(key=lambda x: x['month'])
    
#     print(f"월별 데이터 최종 개수: {len(monthly_emissions_data)}개 데이터")
    
#     return render_template('gov_analysis.html', 
#                         global_avg_carbon=global_avg_carbon,
#                         korea_avg_carbon=korea_avg_carbon,
#                         carbon_emission=carbon_emission,
#                         global_diff=global_diff,
#                         korea_diff=korea_diff,
#                         global_diff_abs=global_diff_abs,
#                         korea_diff_abs=korea_diff_abs,
#                         monthly_emissions_data=json.dumps(monthly_emissions_data))

# URL 분석 라우트 =========================================================================================
# @main_bp.route('/carbon_analysis', methods=['POST'])
# def carbon_analysis():

#     url = request.form.get('url', '').strip()
#     if url and not url.startswith('http://') and not url.startswith('https://'):
#         url = 'https://' + url

#     is_mobile = request.form.get('is_mobile') == 'true'

#     if not url:
#         return jsonify({'error': 'URL is required'}), 400

#     CELERY_QUEUE_THRESHOLD = 5  # 동시에 실행할 최대 작업 수
#     active_tasks = get_active_celery_tasks()
#     db = get_db()

#     if active_tasks >= CELERY_QUEUE_THRESHOLD:
#         task_id = str(uuid.uuid4())
#         db.task_results.insert_one({
#             '_id': task_id,
#             'status': 'QUEUED',
#             'url': url,
#             'user_id': 'anonymous',
#             'is_mobile': is_mobile,
#             'result': None,
#             'created_at': datetime.now(timezone.utc)
#         })
#         current_app.logger.info(f'Task {task_id} for {url} is queued. Active tasks: {active_tasks}')
#         return jsonify({'task_id': task_id})
#     else:
#         original_task_id = str(uuid.uuid4())
#         task = analyze_url_task.delay(url, 'anonymous', is_mobile, original_task_id, perform_subpage_crawling=False)
#         celery_task_id = task.id

#         # Store initial task info using the original_task_id
#         db.task_results.insert_one({
#             '_id': original_task_id, # Use our generated UUID as the primary key
#             'celery_task_id': celery_task_id,
#             'status': 'PENDING',
#             'url': url,
#             'user_id': 'anonymous',
#             'is_mobile': is_mobile,
#             'created_at': datetime.now(timezone.utc)
#         })

#         current_app.logger.info(f"Task for {url} started immediately. Original Task ID: {original_task_id}, Celery ID: {celery_task_id}")
#         return jsonify({'task_id': original_task_id})
#         return jsonify({'task_id': task.id})


# ==========================================================================
# 🛠️ 개발용 PDF 보고서 프리뷰 (CSS 테스트용)
# ==========================================================================
@main_bp.route('/dev/pdf-preview')
@main_bp.route('/dev/pdf-preview/<int:page_num>')
def dev_pdf_preview(page_num=1):
    """개발용 PDF 보고서 프리뷰 - 브라우저에서 CSS 확인

    페이지 번호:
    0: 앞표지
    1-13: 본문
    14: 요약
    15: 뒷표지
    16: 목차
    """

    from ecoweb.app.services.report import PlaywrightPDFGenerator

    # 특수 페이지 매핑
    special_pages = {
        0: 'front-cover',
        14: 'final-summary',
        15: 'back-cover',
        16: 'index'
    }

    # 특정 페이지 렌더링
    if page_num in special_pages or (1 <= page_num <= 13):
        try:
            pdf_generator = PlaywrightPDFGenerator()
            svg_contents = pdf_generator._load_svg_files()

            # 테스트 데이터 준비
            test_data = {
                'website_url': 'preview.example.com',
                'url': 'https://preview.example.com',
                'session_data': {},
                'svg': svg_contents
            }

            # 특수 페이지
            if page_num in special_pages:
                page_type = special_pages[page_num]
                page_html = pdf_generator._load_special_page_template(page_type, test_data)
            # 일반 페이지 (1-13)
            else:
                page_html = pdf_generator._load_page_template(page_num, test_data)

            # HTML을 직접 반환
            response = make_response(page_html)
            response.headers['Content-Type'] = 'text/html; charset=utf-8'

        except Exception as e:
            current_app.logger.error(f"템플릿 로딩 실패: {str(e)}")
            response = make_response(render_template('pages/error/error.html', error_message='템플릿 로딩 실패'))
    else:
        # 전체 페이지 미리보기
        html_pages = []
        pdf_generator = PlaywrightPDFGenerator()
        svg_contents = pdf_generator._load_svg_files()

        for i in range(1, 14):
            try:
                test_data = {
                    'website_url': 'preview.example.com',
                    'url': 'https://preview.example.com',
                    'session_data': {},
                    'svg': svg_contents
                }
                page_html = pdf_generator._load_page_template(i, test_data)

                # 페이지 구분을 위한 스타일 추가
                page_html = f'<div style="page-break-after: always; border: 2px solid #ccc; margin: 20px; padding: 20px;"><h3>Page {i}</h3>{page_html}</div>'
                html_pages.append(page_html)
            except Exception as e:
                html_pages.append(f'<div style="color: red;">페이지 {i} 렌더링 오류: {e}</div>')

        combined_html = f'''
        <!DOCTYPE html>
        <html>
        <head>
            <meta charset="utf-8">
            <title>PDF 보고서 전체 미리보기</title>
            <style>
                body {{ font-family: Arial, sans-serif; margin: 20px; }}
                .navigation {{ position: fixed; top: 10px; right: 10px; background: white; padding: 10px; border: 1px solid #ccc; max-height: 80vh; overflow-y: auto; }}
                .navigation a {{ display: block; margin: 5px 0; text-decoration: none; color: blue; }}
                .navigation strong {{ display: block; margin-bottom: 10px; }}
            </style>
        </head>
        <body>
            <div class="navigation">
                <strong>페이지별 보기:</strong>
                <a href="/dev/pdf-preview/0">앞표지</a>
                <a href="/dev/pdf-preview/16">목차</a>
                {''.join([f'<a href="/dev/pdf-preview/{i}">페이지 {i}</a>' for i in range(1, 14)])}
                <a href="/dev/pdf-preview/14">요약</a>
                <a href="/dev/pdf-preview/15">뒷표지</a>
                <hr>
                <a href="/dev/pdf-preview">전체 보기</a>
            </div>
            <h1>PDF 보고서 전체 미리보기</h1>
            {''.join(html_pages)}
        </body>
        </html>
        '''
        response = make_response(combined_html)
        response.headers['Cache-Control'] = 'no-cache, no-store, must-revalidate'
        response.headers['Pragma'] = 'no-cache'
        response.headers['Expires'] = '0'
    
    # 공통 헤더 설정 (if 블록 밖에서)
    if 'response' not in locals():
        response = make_response(render_template('pages/error/error.html', error_message='처리할 수 없는 요청'))
        response.headers['Cache-Control'] = 'no-cache, no-store, must-revalidate'
        response.headers['Pragma'] = 'no-cache'
        response.headers['Expires'] = '0'

    return response


# 홈페이지 라우트 ===========================================================================================
# @main_bp.route('/homepage' , methods=['GET', 'POST'])
# def homepage():
#     return render_template('homepage.html')