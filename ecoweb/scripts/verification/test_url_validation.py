#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
URL 검증 및 정규화 테스트 스크립트

이 스크립트는 ecoweb.app.utils.validators 모듈의 URL 검증 기능을 테스트합니다.
"""

import sys
import os
import re
import ipaddress
from urllib.parse import urlparse
from typing import Tuple

# validators.py 함수들을 직접 정의 (독립 실행을 위해)
def _is_valid_ip(hostname: str) -> bool:
    """IP 주소 형식이 유효한지 검사합니다 (IPv4/IPv6)."""
    hostname = hostname.strip('[]')
    try:
        ipaddress.ip_address(hostname)
        return True
    except ValueError:
        return False


def validate_and_normalize_url(url: str) -> Tuple[bool, str, str]:
    """URL 유효성 검사 및 정규화를 수행합니다."""
    if url is None:
        return False, "", "URL이 비어있습니다"

    if not isinstance(url, str):
        try:
            url = str(url)
        except Exception:
            return False, "", "URL을 문자열로 변환할 수 없습니다"

    url = url.strip()

    if not url:
        return False, "", "URL이 비어있습니다"

    if len(url) > 2000:
        return False, "", "URL이 너무 깁니다 (최대 2000자)"

    forbidden_chars = ['\n', '\r', '\t', '\x00', '\x0b', '\x0c']
    if any(char in url for char in forbidden_chars):
        return False, "", "URL에 허용되지 않는 제어 문자가 포함되어 있습니다"

    if not url.startswith(('http://', 'https://')):
        if '://' in url:
            detected_scheme = url.split('://')[0].lower()
            if detected_scheme not in ['http', 'https']:
                return False, "", f"http 또는 https 프로토콜만 지원됩니다 (입력된 프로토콜: {detected_scheme})"
        url = 'https://' + url

    try:
        parsed = urlparse(url)

        if parsed.scheme not in ['http', 'https']:
            return False, "", f"http 또는 https 프로토콜만 지원됩니다 (현재: {parsed.scheme})"

        if not parsed.netloc:
            return False, "", "유효한 도메인이 필요합니다"

        hostname = parsed.netloc.split(':')[0]

        if not hostname:
            return False, "", "호스트명이 비어있습니다"

        if '..' in hostname:
            return False, "", "도메인에 연속된 점(..)이 포함되어 있습니다"

        if parsed.port is not None:
            if parsed.port < 1 or parsed.port > 65535:
                return False, "", f"유효하지 않은 포트 번호입니다 (1-65535): {parsed.port}"

        if hostname.lower() == 'localhost':
            pass
        elif _is_valid_ip(hostname):
            pass
        else:
            domain_pattern = r'^([a-zA-Z0-9가-힣]([a-zA-Z0-9\-가-힣]{0,61}[a-zA-Z0-9가-힣])?\.)+[a-zA-Z가-힣]{2,}$'
            if not re.match(domain_pattern, hostname):
                return False, "", "유효하지 않은 도메인 형식입니다"

        if parsed.path and ' ' in parsed.path:
            return False, "", "URL 경로에 인코딩되지 않은 공백이 포함되어 있습니다"

        if parsed.query and ' ' in parsed.query:
            return False, "", "URL 쿼리에 인코딩되지 않은 공백이 포함되어 있습니다"

        return True, url, ""

    except ValueError as e:
        return False, "", f"URL 파싱 오류: {str(e)}"
    except Exception as e:
        return False, "", f"URL 검증 중 예상치 못한 오류: {str(e)}"


def sanitize_url_for_command(url: str) -> str:
    """명령어 실행에 사용할 URL을 안전하게 이스케이프합니다."""
    is_valid, normalized_url, error_msg = validate_and_normalize_url(url)

    if not is_valid:
        raise ValueError(f"Invalid URL: {error_msg}")

    dangerous_chars = [';', '&', '|', '`', '$', '(', ')', '<', '>', '\n']
    if any(char in normalized_url for char in dangerous_chars):
        raise ValueError("URL contains potentially dangerous characters for shell execution")

    return normalized_url


def test_url_validation():
    """다양한 URL 형식을 테스트합니다."""

    test_cases = [
        # (입력 URL, 예상 결과, 설명)
        ("example.com", True, "프로토콜 없는 도메인"),
        ("https://example.com", True, "정상적인 HTTPS URL"),
        ("http://example.com", True, "정상적인 HTTP URL"),
        ("https://example.com:8080", True, "포트 포함 URL"),
        ("https://example.com/path/to/page", True, "경로 포함 URL"),
        ("https://example.com?query=value", True, "쿼리 포함 URL"),

        # 잘못된 형식
        ("", False, "빈 문자열"),
        ("   ", False, "공백만 있는 문자열"),
        ("ftp://example.com", False, "FTP 프로토콜"),
        ("javascript:alert(1)", False, "JavaScript 프로토콜"),
        ("https://", False, "도메인 없음"),
        ("https://..", False, "잘못된 도메인"),
        ("https://example..com", False, "연속된 점"),
        ("https://example.com:99999", False, "잘못된 포트"),
        ("https://example.com\x00", False, "Null 바이트 포함"),
        ("https://example.com\nmalicious", False, "중간에 개행 문자 포함"),
        ("https://example .com", False, "공백 포함 도메인"),
        ("https://example.com/path with spaces", False, "인코딩되지 않은 공백"),

        # 특수 케이스
        ("localhost", True, "localhost"),
        ("http://localhost:3000", True, "localhost with port"),
        ("https://0.0.0.0", True, "IPv4 주소"),
        ("https://테스트.com", True, "한글 도메인 (IDN)"),
        ("https://sub.example.com", True, "서브도메인"),
        ("https://example.com/", True, "후행 슬래시"),

        # 긴 URL (정확한 계산)
        ("https://example.com/" + "a" * 1970, True, "긴 URL (2000자 이하)"),
        ("https://example.com/" + "a" * 1981, False, "너무 긴 URL (2000자 초과)"),
    ]

    print("=" * 80)
    print("URL 검증 테스트 시작")
    print("=" * 80)
    print()

    passed = 0
    failed = 0

    for url, expected_valid, description in test_cases:
        is_valid, normalized_url, error_msg = validate_and_normalize_url(url)

        # 결과 확인
        if is_valid == expected_valid:
            status = "[PASS]"
            passed += 1
        else:
            status = "[FAIL]"
            failed += 1

        # 결과 출력
        print(f"{status} | {description}")
        print(f"  입력: {repr(url[:50])}{'...' if len(url) > 50 else ''}")
        print(f"  예상: {'유효함' if expected_valid else '무효함'}")
        print(f"  결과: {'유효함' if is_valid else '무효함'}")

        if is_valid:
            print(f"  정규화된 URL: {normalized_url[:70]}{'...' if len(normalized_url) > 70 else ''}")
        else:
            print(f"  오류 메시지: {error_msg}")

        print()

    print("=" * 80)
    print(f"테스트 완료: 총 {len(test_cases)}건 | 성공 {passed}건 | 실패 {failed}건")
    print("=" * 80)

    return failed == 0


def test_sanitize_url():
    """sanitize_url_for_command 함수를 테스트합니다."""

    print("\n" + "=" * 80)
    print("URL Sanitization 테스트 시작")
    print("=" * 80)
    print()

    test_cases = [
        ("https://example.com", True, "정상 URL"),
        ("example.com", True, "프로토콜 없는 URL"),
        ("https://example.com; rm -rf /", False, "명령어 인젝션 시도 (세미콜론)"),
        ("https://example.com|whoami", False, "명령어 인젝션 시도 (파이프)"),
        ("https://example.com`whoami`", False, "명령어 인젝션 시도 (백틱)"),
    ]

    passed = 0
    failed = 0

    for url, should_succeed, description in test_cases:
        try:
            sanitized = sanitize_url_for_command(url)
            if should_succeed:
                status = "[PASS]"
                passed += 1
                print(f"{status} | {description}")
                print(f"  Input: {url}")
                print(f"  Sanitized URL: {sanitized}")
            else:
                status = "[FAIL]"
                failed += 1
                print(f"{status} | {description}")
                print(f"  Input: {url}")
                print(f"  Error: Should have raised exception but succeeded")
        except ValueError as e:
            if not should_succeed:
                status = "[PASS]"
                passed += 1
                print(f"{status} | {description}")
                print(f"  Input: {url}")
                print(f"  Exception: {str(e)}")
            else:
                status = "[FAIL]"
                failed += 1
                print(f"{status} | {description}")
                print(f"  Input: {url}")
                print(f"  Error: {str(e)}")

        print()

    print("=" * 80)
    print(f"Sanitization 테스트 완료: 총 {len(test_cases)}건 | 성공 {passed}건 | 실패 {failed}건")
    print("=" * 80)

    return failed == 0


if __name__ == "__main__":
    print("\n[URL Validation Module Test]\n")

    validation_passed = test_url_validation()
    sanitization_passed = test_sanitize_url()

    print("\n" + "=" * 80)
    if validation_passed and sanitization_passed:
        print("[SUCCESS] All tests passed!")
        sys.exit(0)
    else:
        print("[FAILURE] Some tests failed")
        sys.exit(1)
