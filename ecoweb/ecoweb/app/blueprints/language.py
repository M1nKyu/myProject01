"""
언어 전환 블루프린트
사용자의 언어 설정을 변경하는 라우트
"""
from flask import Blueprint, session, redirect, request, url_for, jsonify
from ecoweb.app.utils.i18n import SUPPORTED_LANGUAGES, DEFAULT_LANGUAGE

language_bp = Blueprint('language', __name__, url_prefix='/language')


@language_bp.route('/set/<lang_code>')
def set_language(lang_code):
    """
    사용자의 언어 설정을 변경합니다.

    Args:
        lang_code: 언어 코드 (ko, en, ja, zh)

    Returns:
        이전 페이지로 리다이렉트 또는 홈페이지로 이동
    """
    # 유효한 언어 코드인지 확인
    if lang_code not in SUPPORTED_LANGUAGES:
        lang_code = DEFAULT_LANGUAGE

    # 세션에 언어 저장
    session['language'] = lang_code
    session.permanent = True  # 세션 영구 보존

    # 이전 페이지 또는 홈페이지로 리다이렉트
    referrer = request.referrer
    if referrer:
        return redirect(referrer)
    else:
        return redirect(url_for('main.home'))


@language_bp.route('/current')
def get_current_language():
    """
    현재 설정된 언어를 JSON으로 반환합니다.

    Returns:
        JSON: {'language': 'ko', 'name': '한국어'}
    """
    current_lang = session.get('language', DEFAULT_LANGUAGE)
    lang_info = SUPPORTED_LANGUAGES.get(current_lang, SUPPORTED_LANGUAGES[DEFAULT_LANGUAGE])

    return jsonify({
        'language': current_lang,
        'name': lang_info['name'],
        'flag_code': lang_info['flag_code'],
        'english_name': lang_info['english_name']
    })
