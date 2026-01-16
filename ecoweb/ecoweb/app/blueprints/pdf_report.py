"""
PDF 보고서 생성 관련 라우트
"""

import json
import logging
import uuid
from datetime import datetime
from flask import Blueprint, current_app, jsonify, request, session, send_file
from werkzeug.exceptions import BadRequest

# from ecoweb.app.services.pdf_report_generator import CarbonReportGenerator  # WeasyPrint 비활성화로 주석 처리
# from ecoweb.app.services.simple_pdf_generator import SimplePDFGenerator  # Node.js 방식에서 Playwright로 변경
from ecoweb.app.services.report import PlaywrightPDFGenerator
from ecoweb.app.utils.event_logger import log_pdf_generate, log_pdf_download

pdf_bp = Blueprint('pdf_report', __name__)

# 기존 WeasyPrint 기반 PDF 생성 라우트 (비활성화)
# @pdf_bp.route('/generate-pdf-report', methods=['POST'])
def generate_pdf_report_disabled():
    """
    세션 데이터를 기반으로 PDF 보고서 생성
    다중 사용자 환경에서 안전하게 동작하도록 구현
    """
    try:
        # 사용자 식별
        user_id = session.get('user_id', 'anonymous')
        session_id = session.sid if hasattr(session, 'sid') else str(uuid.uuid4())
        
        current_app.logger.info(f"PDF 보고서 생성 요청 - 사용자: {user_id}, 세션: {session_id}")
        
        # 필수 세션 데이터 확인
        required_fields = ['url', 'carbon_emission']
        missing_fields = [field for field in required_fields if field not in session]
        
        if missing_fields:
            current_app.logger.warning(f"필수 세션 데이터 누락: {missing_fields}")
            return jsonify({
                'success': False,
                'error': '분석 데이터가 없습니다. 먼저 웹사이트 분석을 완료해주세요.',
                'missing_fields': missing_fields
            }), 400
        
        # 세션 데이터 수집 및 정리
        session_data = _extract_session_data(session)
        
        # PDF 생성기 초기화 (WeasyPrint 비활성화로 주석 처리)
        # pdf_generator = CarbonReportGenerator()

        # 기존 기능 비활성화로 에러 반환
        return jsonify({
            'success': False,
            'error': '기존 PDF 생성 기능이 비활성화되었습니다. /generate-simple-pdf-report를 사용하세요.'
        }), 503

        # 아래 코드들은 WeasyPrint 비활성화로 주석 처리됨
        # # PDF 생성
        # pdf_buffer = pdf_generator.generate_pdf(session_data)
        #
        # # 파일명 생성 (다중 사용자 환경 고려)
        # url = session_data.get('url', 'unknown')
        # safe_url = _sanitize_filename(url)
        # timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        # filename = f"carbon_report_{safe_url}_{timestamp}.pdf"
        #
        # current_app.logger.info(f"PDF 보고서 생성 완료 - 파일명: {filename}")
        #
        # # PDF 파일 반환
        # return send_file(
        #     pdf_buffer,
        #     as_attachment=True,
        #     download_name=filename,
        #     mimetype='application/pdf'
        # )

    except Exception as e:
        current_app.logger.error(f"기존 PDF 보고서 기능 비활성화됨: {str(e)}", exc_info=True)
        return jsonify({
            'success': False,
            'error': '기존 PDF 생성 기능이 비활성화되었습니다. /generate-simple-pdf-report를 사용하세요.'
        }), 503

@pdf_bp.route('/check-pdf-availability/<task_id>', methods=['GET'])
def check_pdf_availability(task_id):
    """
    PDF 생성 가능 여부 확인 (Phase 3: DB-centered)

    변경 사항:
    - task_id를 URL 파라미터로 받아서 MongoDB에서 데이터 확인
    - 세션 의존성 제거
    """
    try:
        # MongoDB에서 분석 결과 조회
        from ecoweb.app import db
        mongo_db = db.get_db()
        task_results_collection = mongo_db.task_results

        # MongoDB Projection: PDF 가용성 확인에 필요한 필드만 조회
        task_result = task_results_collection.find_one(
            {'_id': task_id},
            {
                'status': 1,
                'result.url': 1,
                'result.calculated.carbon_emission': 1,
                'result.carbon_emission': 1,  # 하위 호환성
                'completed_at': 1
            }
        )

        if not task_result:
            return jsonify({
                'available': False,
                'reason': '분석 결과를 찾을 수 없습니다.'
            }), 404

        # 분석 완료 상태 확인
        task_status = task_result.get('status')
        if task_status not in ['SUCCESS', 'MEASUREMENT_COMPLETE']:
            return jsonify({
                'available': False,
                'reason': f'분석이 완료되지 않았습니다. 상태: {task_status}'
            })

        # 결과 데이터 확인
        result_data = task_result.get('result')
        if not result_data:
            return jsonify({
                'available': False,
                'reason': '분석 결과 데이터가 없습니다.'
            })

        # calculated 섹션에서 carbon_emission 확인
        calculated = result_data.get('calculated', {})
        carbon_emission = calculated.get('carbon_emission')

        # 하위 호환성: calculated 섹션 없으면 최상위에서 조회
        if carbon_emission is None:
            carbon_emission = result_data.get('carbon_emission')

        # 데이터 유효성 검사
        if not isinstance(carbon_emission, (int, float)) or carbon_emission < 0:
            return jsonify({
                'available': False,
                'reason': '유효하지 않은 분석 데이터입니다.'
            })

        return jsonify({
            'available': True,
            'url': result_data.get('url'),
            'analysis_date': task_result.get('completed_at', datetime.now()).isoformat()
        })

    except Exception as e:
        current_app.logger.error(f"PDF 가용성 확인 중 오류: {str(e)}")
        return jsonify({
            'available': False,
            'reason': '시스템 오류가 발생했습니다.'
        }), 500

def _extract_session_data(session_obj):
    """
    세션에서 PDF 생성에 필요한 데이터 추출
    """
    session_data = {}
    
    # 기본 정보
    basic_fields = [
        'url', 'carbon_emission', 'kb_weight', 'emission_percentile',
        'korea_avg_carbon', 'global_avg_carbon', 'korea_diff', 'global_diff',
        'korea_carbon_percentage_diff', 'korea_comparison_status', 'username'
    ]
    
    for field in basic_fields:
        session_data[field] = session_obj.get(field)
    
    # JSON 데이터 파싱
    try:
        view_data_json = session_obj.get('view_data')
        if view_data_json:
            session_data['view_data'] = json.loads(view_data_json)
    except (json.JSONDecodeError, TypeError):
        session_data['view_data'] = {}
    
    try:
        subpages_data_json = session_obj.get('subpages_data')
        if subpages_data_json:
            session_data['subpages'] = json.loads(subpages_data_json)
        else:
            session_data['subpages'] = session_obj.get('subpages', [])
    except (json.JSONDecodeError, TypeError):
        session_data['subpages'] = session_obj.get('subpages', [])
    
    # 콘텐츠 배출량 데이터
    session_data['content_emission_data'] = session_obj.get('content_emission_data', [])
    
    return session_data

def _sanitize_filename(url):
    """
    URL을 파일명으로 사용할 수 있도록 정리
    """
    if not url:
        return 'unknown'
    
    # 프로토콜 제거
    if url.startswith(('http://', 'https://')):
        url = url.split('://', 1)[1]
    
    # 특수문자 제거 및 길이 제한
    import re
    safe_name = re.sub(r'[^\w\-_.]', '_', url)
    safe_name = safe_name[:50]  # 길이 제한
    
    return safe_name

@pdf_bp.route('/generate-simple-pdf-report/<task_id>', methods=['POST'])
def generate_simple_pdf_report(task_id):
    """
    Celery 백그라운드 작업으로 PDF 보고서 생성 요청 (Phase 3: DB-centered)

    변경 사항:
    - task_id를 URL 파라미터로 받아서 MongoDB에서 데이터 조회
    - 세션 의존성 제거 (세션 대신 MongoDB의 enriched_result 사용)
    """
    try:
        # 사용자 식별
        user_id = session.get('user_id', 'anonymous')
        session_id = session.sid if hasattr(session, 'sid') else str(uuid.uuid4())

        # [1] MongoDB에서 분석 결과 데이터 조회
        from ecoweb.app import db
        mongo_db = db.get_db()
        task_results_collection = mongo_db.task_results

        # MongoDB Projection: result 전체를 가져와야 PDF 생성 가능 (모든 필드 필요)
        task_result = task_results_collection.find_one(
            {'_id': task_id},
            {
                'status': 1,
                'result': 1  # PDF 생성에 모든 result 데이터 필요
            }
        )

        if not task_result:
            current_app.logger.error(f'Task ID {task_id}를 찾을 수 없습니다.')
            return jsonify({
                'success': False,
                'error': '분석 결과를 찾을 수 없습니다. 먼저 웹사이트 분석을 완료해주세요.'
            }), 404

        # [2] 분석 완료 상태 확인
        task_status = task_result.get('status')
        if task_status not in ['SUCCESS', 'MEASUREMENT_COMPLETE']:
            return jsonify({
                'success': False,
                'error': f'분석이 완료되지 않았습니다. 상태: {task_status}'
            }), 400

        # [3] enriched_result 추출 (calculated 섹션 포함)
        result_data = task_result.get('result')
        if not result_data:
            current_app.logger.error(f'Task ID {task_id}의 결과 데이터가 없습니다.')
            return jsonify({
                'success': False,
                'error': '분석 결과 데이터가 없습니다.'
            }), 400

        # [4] PDF 생성에 필요한 데이터 준비 (MongoDB 데이터 사용)
        session_data = result_data  # enriched_result를 그대로 사용

        # [5] PDF 생성 작업 관리
        pdf_tasks_collection = mongo_db.pdf_generation_tasks

        # 고유한 PDF 태스크 ID 생성
        pdf_task_id = str(uuid.uuid4())

        # 초기 작업 문서 생성
        task_doc = {
            '_id': pdf_task_id,
            'user_id': user_id,
            'session_id': session_id,
            'analysis_task_id': task_id,  # 분석 작업 ID 저장
            'url': session_data.get('url'),
            'status': 'PENDING',
            'created_at': datetime.utcnow(),
            'progress': {
                'current_step': 'pending',
                'message': 'PDF 생성 대기 중',
                'updated_at': datetime.utcnow().isoformat()
            }
        }
        pdf_tasks_collection.insert_one(task_doc)

        # 이벤트 로깅: PDF 생성 시작
        log_pdf_generate(task_id, user_id=str(user_id) if user_id != 'anonymous' else None)

        # [6] Celery 백그라운드 작업 시작
        from ecoweb.app.tasks import generate_pdf_report_task
        celery_task = generate_pdf_report_task.apply_async(
            args=[session_data, user_id, pdf_task_id],
            task_id=pdf_task_id
        )

        # 태스크 ID 반환
        return jsonify({
            'success': True,
            'task_id': pdf_task_id,
            'message': 'PDF 생성 작업이 시작되었습니다. 작업 상태를 확인하세요.'
        }), 202  # 202 Accepted

    except Exception as e:
        current_app.logger.error(f"PDF 생성 실패: {str(e)}")
        return jsonify({
            'success': False,
            'error': 'PDF 보고서 생성 요청 중 오류가 발생했습니다. 잠시 후 다시 시도해주세요.'
        }), 500

@pdf_bp.route('/pdf-status/<task_id>', methods=['GET'])
def get_pdf_status(task_id):
    """
    PDF 생성 작업의 진행 상태 확인
    """
    try:
        from ecoweb.app import db
        mongo_db = db.get_db()
        pdf_tasks_collection = mongo_db.pdf_generation_tasks

        # MongoDB Projection: PDF 상태 확인에 필요한 필드만 조회
        task_doc = pdf_tasks_collection.find_one(
            {'_id': task_id},
            {
                'status': 1,
                'progress': 1,
                'created_at': 1,
                'completed_at': 1,
                'failed_at': 1,
                'result.pdf_path': 1,
                'result.filename': 1,
                'result.generated_at': 1,
                'error': 1
            }
        )

        if not task_doc:
            return jsonify({
                'success': False,
                'error': '작업을 찾을 수 없습니다.'
            }), 404

        # 상태 정보 반환
        response = {
            'success': True,
            'task_id': task_id,
            'status': task_doc.get('status'),
            'progress': task_doc.get('progress', {}),
            'created_at': task_doc.get('created_at').isoformat() if task_doc.get('created_at') else None
        }

        # 성공한 경우 결과 포함
        if task_doc.get('status') == 'SUCCESS':
            result = task_doc.get('result', {})
            response['result'] = {
                'pdf_path': result.get('pdf_path'),
                'filename': result.get('filename'),
                'generated_at': result.get('generated_at')
            }
            response['completed_at'] = task_doc.get('completed_at').isoformat() if task_doc.get('completed_at') else None

        # 실패한 경우 에러 포함
        elif task_doc.get('status') == 'FAILURE':
            response['error'] = task_doc.get('error')
            response['failed_at'] = task_doc.get('failed_at').isoformat() if task_doc.get('failed_at') else None

        return jsonify(response), 200

    except Exception as e:
        current_app.logger.error(f"PDF 상태 조회 중 오류 발생: {str(e)}", exc_info=True)
        return jsonify({
            'success': False,
            'error': '상태 조회 중 오류가 발생했습니다.'
        }), 500

@pdf_bp.route('/download-pdf/<task_id>', methods=['GET'])
def download_pdf(task_id):
    """
    생성된 PDF 파일 다운로드
    """
    try:
        from ecoweb.app import db
        import os

        mongo_db = db.get_db()
        pdf_tasks_collection = mongo_db.pdf_generation_tasks

        # MongoDB Projection: PDF 다운로드에 필요한 필드만 조회
        task_doc = pdf_tasks_collection.find_one(
            {'_id': task_id},
            {
                'status': 1,
                'result.pdf_path': 1,
                'result.filename': 1
            }
        )

        if not task_doc:
            return jsonify({
                'success': False,
                'error': '작업을 찾을 수 없습니다.'
            }), 404

        # 작업 완료 확인
        if task_doc.get('status') != 'SUCCESS':
            return jsonify({
                'success': False,
                'error': 'PDF 생성이 완료되지 않았습니다.',
                'status': task_doc.get('status')
            }), 400

        # PDF 파일 경로 확인
        result = task_doc.get('result', {})
        relative_path = result.get('pdf_path')
        filename = result.get('filename')

        if not relative_path or not filename:
            return jsonify({
                'success': False,
                'error': 'PDF 파일 정보가 없습니다.'
            }), 404

        # 절대 경로 생성 (var/pdf_reports 사용)
        from ecoweb.config import Config
        # relative_path가 "var/pdf_reports/..." 형식이므로, VAR_DIR 기준으로 절대 경로 생성
        if relative_path.startswith('var/'):
            # var/ 제거 후 VAR_DIR과 결합
            pdf_file_path = os.path.join(Config.VAR_DIR, relative_path.replace('var/', ''))
        else:
            # 기존 방식 (하위 호환성)
            pdf_file_path = os.path.join('/app/ecoweb/static', relative_path)

        # 파일 존재 확인
        if not os.path.exists(pdf_file_path):
            current_app.logger.error(f"PDF 파일이 존재하지 않습니다: {pdf_file_path}")
            return jsonify({
                'success': False,
                'error': 'PDF 파일을 찾을 수 없습니다.'
            }), 404

        # 이벤트 로깅: PDF 다운로드
        user_id = session.get('user_id')
        analysis_task_id = task_doc.get('analysis_task_id')
        if analysis_task_id:
            log_pdf_download(analysis_task_id, user_id=str(user_id) if user_id else None)

        # PDF 파일 반환
        return send_file(
            pdf_file_path,
            as_attachment=True,
            download_name=filename,
            mimetype='application/pdf'
        )

    except Exception as e:
        current_app.logger.error(f"PDF 다운로드 중 오류 발생: {str(e)}", exc_info=True)
        return jsonify({
            'success': False,
            'error': 'PDF 다운로드 중 오류가 발생했습니다.'
        }), 500

@pdf_bp.route('/cancel-pdf/<task_id>', methods=['POST'])
def cancel_pdf_generation(task_id):
    """
    PDF 생성 작업 취소
    """
    try:
        from ecoweb.app import db
        mongo_db = db.get_db()
        pdf_tasks_collection = mongo_db.pdf_generation_tasks

        # MongoDB Projection: 취소 처리에 필요한 필드만 조회
        task_doc = pdf_tasks_collection.find_one(
            {'_id': task_id},
            {'status': 1}
        )

        if not task_doc:
            return jsonify({
                'success': False,
                'error': '작업을 찾을 수 없습니다.'
            }), 404

        # 이미 완료되거나 실패한 작업은 취소 불가
        if task_doc.get('status') in ['SUCCESS', 'FAILURE', 'CANCELLED']:
            return jsonify({
                'success': False,
                'error': f"작업이 이미 {task_doc.get('status')} 상태입니다.",
                'status': task_doc.get('status')
            }), 400

        # 작업 취소 상태로 업데이트
        pdf_tasks_collection.update_one(
            {'_id': task_id},
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


        return jsonify({
            'success': True,
            'message': 'PDF 생성 작업이 취소되었습니다.',
            'task_id': task_id
        }), 200

    except Exception as e:
        current_app.logger.error(f"PDF 취소 실패: {str(e)}")
        return jsonify({
            'success': False,
            'error': '작업 취소 중 오류가 발생했습니다.'
        }), 500
