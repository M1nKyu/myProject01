#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
배포 전 체크리스트 검증 스크립트
국제화(i18n) 설정 및 번역 파일 상태를 확인합니다.

Usage:
    python pre_deploy_check.py
"""
import os
import sys
import json
from pathlib import Path

# Windows 콘솔 유니코드 출력 지원
if sys.platform == 'win32':
    import codecs
    sys.stdout = codecs.getwriter('utf-8')(sys.stdout.buffer, 'strict')
    sys.stderr = codecs.getwriter('utf-8')(sys.stderr.buffer, 'strict')

# 프로젝트 루트 디렉토리
BASE_DIR = Path(__file__).resolve().parent
TRANSLATIONS_DIR = BASE_DIR / 'ecoweb' / 'app' / 'translations'
STATIC_TRANSLATIONS_DIR = BASE_DIR / 'ecoweb' / 'app' / 'static' / 'translations'

# 지원 언어 목록
SUPPORTED_LANGUAGES = ['ko', 'en', 'ja', 'zh']

# 색상 출력 (ANSI 코드)
GREEN = '\033[92m'
YELLOW = '\033[93m'
RED = '\033[91m'
RESET = '\033[0m'
BOLD = '\033[1m'


def print_section(title):
    """섹션 제목 출력"""
    print(f"\n{BOLD}{'=' * 60}{RESET}")
    print(f"{BOLD}{title}{RESET}")
    print(f"{BOLD}{'=' * 60}{RESET}\n")


def print_check(passed, message):
    """체크 결과 출력"""
    if passed:
        print(f"{GREEN}✓{RESET} {message}")
    else:
        print(f"{RED}✗{RESET} {message}")
    return passed


def check_babel_installed():
    """Flask-Babel 설치 확인"""
    try:
        import flask_babel
        try:
            version = flask_babel.__version__
        except AttributeError:
            # Some versions don't have __version__, try pkg_resources
            try:
                import pkg_resources
                version = pkg_resources.get_distribution('flask-babel').version
            except:
                version = "installed"
        return print_check(True, f"Flask-Babel installed (v{version})")
    except ImportError:
        return print_check(False, "Flask-Babel NOT installed")


def check_po_files():
    """서버 측 번역 파일(.po) 확인"""
    all_exist = True

    for lang in SUPPORTED_LANGUAGES:
        po_file = TRANSLATIONS_DIR / lang / 'LC_MESSAGES' / 'messages.po'
        exists = po_file.exists()
        all_exist = all_exist and exists

        if exists:
            size = po_file.stat().st_size
            print_check(True, f"{lang}/messages.po exists ({size:,} bytes)")
        else:
            print_check(False, f"{lang}/messages.po NOT FOUND")

    return all_exist


def check_mo_files():
    """컴파일된 번역 파일(.mo) 확인"""
    all_exist = True
    warning_count = 0

    for lang in SUPPORTED_LANGUAGES:
        mo_file = TRANSLATIONS_DIR / lang / 'LC_MESSAGES' / 'messages.mo'
        po_file = TRANSLATIONS_DIR / lang / 'LC_MESSAGES' / 'messages.po'

        exists = mo_file.exists()

        if exists:
            mo_size = mo_file.stat().st_size
            mo_mtime = mo_file.stat().st_mtime

            # .po 파일이 .mo 파일보다 최신인지 확인
            if po_file.exists():
                po_mtime = po_file.stat().st_mtime
                if po_mtime > mo_mtime:
                    print_check(False, f"{lang}/messages.mo is OUTDATED (need recompile)")
                    warning_count += 1
                    all_exist = False
                else:
                    print_check(True, f"{lang}/messages.mo is up-to-date ({mo_size:,} bytes)")
            else:
                print_check(True, f"{lang}/messages.mo exists ({mo_size:,} bytes)")
        else:
            print_check(False, f"{lang}/messages.mo NOT FOUND (run: python compile_translations.py)")
            all_exist = False

    if warning_count > 0:
        print(f"\n{YELLOW}⚠ Warning: {warning_count} .mo file(s) need recompilation{RESET}")

    return all_exist


def check_json_files():
    """클라이언트 측 번역 파일(JSON) 확인"""
    all_exist = True

    for lang in SUPPORTED_LANGUAGES:
        json_file = STATIC_TRANSLATIONS_DIR / f"{lang}.json"
        exists = json_file.exists()
        all_exist = all_exist and exists

        if exists:
            size = json_file.stat().st_size

            # JSON 파일 유효성 검사
            try:
                with open(json_file, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    key_count = len(data)
                print_check(True, f"{lang}.json is valid ({key_count} keys, {size:,} bytes)")
            except json.JSONDecodeError as e:
                print_check(False, f"{lang}.json is INVALID JSON: {e}")
                all_exist = False
        else:
            print_check(False, f"{lang}.json NOT FOUND")

    return all_exist


def check_translation_consistency():
    """언어 간 번역 키 일관성 확인"""
    print("\nChecking translation key consistency...")

    # JSON 파일 간 키 일관성 확인
    all_keys = {}
    for lang in SUPPORTED_LANGUAGES:
        json_file = STATIC_TRANSLATIONS_DIR / f"{lang}.json"
        if json_file.exists():
            with open(json_file, 'r', encoding='utf-8') as f:
                all_keys[lang] = set(json.load(f).keys())

    if len(all_keys) == len(SUPPORTED_LANGUAGES):
        # 모든 언어의 키 집합 비교
        base_keys = all_keys['ko']  # 한국어를 기준으로

        consistent = True
        for lang in ['en', 'ja', 'zh']:
            if lang in all_keys:
                missing = base_keys - all_keys[lang]
                extra = all_keys[lang] - base_keys

                if missing:
                    print_check(False, f"{lang}.json missing keys: {', '.join(list(missing)[:5])}...")
                    consistent = False

                if extra:
                    print_check(False, f"{lang}.json has extra keys: {', '.join(list(extra)[:5])}...")
                    consistent = False

        if consistent:
            print_check(True, f"All languages have consistent keys ({len(base_keys)} keys)")
            return True
        else:
            return False
    else:
        print_check(False, "Cannot check consistency - some JSON files are missing")
        return False


def check_config_files():
    """설정 파일 확인"""
    babel_cfg = BASE_DIR / 'babel.cfg'

    if babel_cfg.exists():
        print_check(True, "babel.cfg exists")
        return True
    else:
        print_check(False, "babel.cfg NOT FOUND")
        return False


def check_i18n_integration():
    """Flask 앱 통합 확인"""
    init_file = BASE_DIR / 'ecoweb' / 'app' / '__init__.py'

    if init_file.exists():
        with open(init_file, 'r', encoding='utf-8') as f:
            content = f.read()

            has_import = 'from ecoweb.app.utils.i18n import init_babel' in content
            has_call = 'init_babel(app)' in content

            if has_import and has_call:
                print_check(True, "Babel initialized in __init__.py")
                return True
            else:
                if not has_import:
                    print_check(False, "Missing import: from ecoweb.app.utils.i18n import init_babel")
                if not has_call:
                    print_check(False, "Missing call: init_babel(app)")
                return False
    else:
        print_check(False, "__init__.py NOT FOUND")
        return False


def main():
    """메인 체크리스트 실행"""
    print(f"{BOLD}ECO-WEB i18n Pre-Deployment Checklist{RESET}")
    print(f"Checking internationalization setup...\n")

    checks = []

    # 1. 의존성 확인
    print_section("1. Dependencies")
    checks.append(check_babel_installed())

    # 2. 설정 파일 확인
    print_section("2. Configuration Files")
    checks.append(check_config_files())

    # 3. 서버 측 번역 파일 확인
    print_section("3. Server-side Translation Files (.po)")
    checks.append(check_po_files())

    # 4. 컴파일된 번역 파일 확인
    print_section("4. Compiled Translation Files (.mo)")
    checks.append(check_mo_files())

    # 5. 클라이언트 측 번역 파일 확인
    print_section("5. Client-side Translation Files (JSON)")
    checks.append(check_json_files())

    # 6. 번역 키 일관성 확인
    print_section("6. Translation Key Consistency")
    checks.append(check_translation_consistency())

    # 7. Flask 통합 확인
    print_section("7. Flask Integration")
    checks.append(check_i18n_integration())

    # 최종 결과
    print_section("Summary")

    passed = sum(checks)
    total = len(checks)

    if passed == total:
        print(f"{GREEN}{BOLD}✓ All checks passed! ({passed}/{total}){RESET}")
        print(f"{GREEN}Ready to deploy!{RESET}\n")
        return 0
    else:
        failed = total - passed
        print(f"{RED}{BOLD}✗ {failed} check(s) failed ({passed}/{total}){RESET}")
        print(f"{YELLOW}Please fix the issues before deploying.{RESET}\n")

        if not all(checks[3:4]):  # .mo 파일 체크 실패
            print(f"{YELLOW}Tip: Run 'python compile_translations.py' to compile translations{RESET}\n")

        return 1


if __name__ == '__main__':
    try:
        sys.exit(main())
    except KeyboardInterrupt:
        print("\n\nInterrupted by user")
        sys.exit(130)
    except Exception as e:
        print(f"\n{RED}✗ Unexpected error: {e}{RESET}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
