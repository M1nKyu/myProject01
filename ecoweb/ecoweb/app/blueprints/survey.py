from flask import Blueprint, request, jsonify, current_app, render_template, session
from datetime import datetime, timezone
from bson import ObjectId
from .. import db
from ..models import SurveyResponse

survey_bp = Blueprint('survey', __name__)

@survey_bp.route('/check_survey_status', methods=['GET'])
def check_survey_status():
    """사용자의 설문조사 완료 상태 확인"""
    try:
        mongo_db = db.get_db()
        user_id = session.get('user_id')
        session_id = session.get('session_id', request.cookies.get('session'))
        ip_address = request.remote_addr
        
        # 사용자 식별: 로그인한 사용자 > 세션 ID > IP 주소
        query = {}
        if user_id:
            query['user_id'] = user_id
        elif session_id:
            query['session_id'] = session_id
        else:
            query['ip_address'] = ip_address
            
        existing_survey = mongo_db.survey_responses.find_one(query)
        
        # ObjectId를 문자열로 변환하여 JSON 직렬화 가능하게 만들기
        survey_data = None
        if existing_survey:
            survey_data = dict(existing_survey)
            if '_id' in survey_data:
                survey_data['_id'] = str(survey_data['_id'])
        
        return jsonify({
            'has_completed_survey': existing_survey is not None and (
                existing_survey.get('is_completed', False) or 
                existing_survey.get('is_skipped', False)
            ),
            'survey_data': survey_data
        })
        
    except Exception as e:
        current_app.logger.error(f"설문조사 상태 확인 실패: {e}", exc_info=True)
        return jsonify({'error': '설문조사 상태 확인 중 오류가 발생했습니다.'}), 500

@survey_bp.route('/submit_survey', methods=['POST'])
def submit_survey():
    """설문조사 데이터 저장"""
    try:
        data = request.get_json()
        user_id = session.get('user_id')
        session_id = session.get('session_id', request.cookies.get('session'))
        ip_address = request.remote_addr
        
        # SurveyResponse 객체 생성
        survey = SurveyResponse(
            user_id=user_id,
            session_id=session_id,
            ip_address=ip_address
        )
        
        # 설문 응답 데이터 설정 (간소화된 구조)
        survey.step1_source = data.get('step1_source')
        survey.step2_role = data.get('step2_role')
        survey.step2_owner = data.get('step2_owner')
        survey.step3_visitors = data.get('step3_visitors')
        survey.step3_type = data.get('step3_type')
        survey.step4_email = data.get('step4_email')
        survey.step7_updates_optin = data.get('step7_updates_optin', False)
        
        # 완료 상태 설정
        survey.is_completed = data.get('is_completed', True)
        survey.is_skipped = data.get('is_skipped', False)
        survey.completed_at = datetime.now()
        
        # MongoDB에 저장
        mongo_db = db.get_db()
        
        # 사용자 식별을 위한 쿼리
        query = {}
        if user_id:
            query['user_id'] = user_id
        elif session_id:
            query['session_id'] = session_id
        else:
            query['ip_address'] = ip_address
            
        # 기존 응답이 있으면 업데이트, 없으면 새로 생성
        result = mongo_db.survey_responses.update_one(
            query,
            {'$set': survey.to_dict()},
            upsert=True
        )
        
        # 로그인한 사용자의 경우 users 컬렉션에 뉴스레터 구독 정보 업데이트
        if user_id and survey.step7_updates_optin:
            try:
                mongo_db.users.update_one(
                    {'_id': ObjectId(user_id)},
                    {'$set': {'newsletter_subscription': True}},
                    upsert=False
                )
                current_app.logger.info(f"사용자 뉴스레터 구독 업데이트: user_id={user_id}")
            except Exception as e:
                current_app.logger.error(f"사용자 뉴스레터 구독 업데이트 실패: {e}")
        
        current_app.logger.info(f"설문조사 저장 완료: user_id={user_id}, session_id={session_id}")
        
        return jsonify({
            'success': True,
            'message': '설문조사 응답이 저장되었습니다.'
        })
        
    except Exception as e:
        current_app.logger.error(f"설문조사 저장 실패: {e}", exc_info=True)
        return jsonify({'error': '설문조사 저장 중 오류가 발생했습니다.'}), 500

@survey_bp.route('/skip_survey', methods=['POST'])
def skip_survey():
    """설문조사 건너뛰기"""
    try:
        user_id = session.get('user_id')
        session_id = session.get('session_id', request.cookies.get('session'))
        ip_address = request.remote_addr
        
        # SurveyResponse 객체 생성 (건너뛰기용)
        survey = SurveyResponse(
            user_id=user_id,
            session_id=session_id,
            ip_address=ip_address
        )
        survey.is_skipped = True
        survey.completed_at = datetime.now()
        
        # MongoDB에 저장
        mongo_db = db.get_db()
        
        # 사용자 식별을 위한 쿼리
        query = {}
        if user_id:
            query['user_id'] = user_id
        elif session_id:
            query['session_id'] = session_id
        else:
            query['ip_address'] = ip_address
            
        result = mongo_db.survey_responses.update_one(
            query,
            {'$set': survey.to_dict()},
            upsert=True
        )
        
        current_app.logger.info(f"설문조사 건너뛰기 저장: user_id={user_id}, session_id={session_id}")
        
        return jsonify({
            'success': True,
            'message': '설문조사를 건너뛰었습니다.'
        })
        
    except Exception as e:
        current_app.logger.error(f"설문조사 건너뛰기 저장 실패: {e}", exc_info=True)
        return jsonify({'error': '설문조사 건너뛰기 저장 중 오류가 발생했습니다.'}), 500

@survey_bp.route('/survey_fragment')
def survey_fragment():
    """설문조사 HTML fragment 반환"""
    return render_template('includes/survey.html')
