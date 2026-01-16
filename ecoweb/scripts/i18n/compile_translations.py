#!/usr/bin/env python
"""
번역 파일 컴파일 스크립트
.po 파일을 .mo 바이너리 파일로 컴파일하여 프로덕션 배포 준비

Usage:
    python compile_translations.py
"""
import os
import sys
import subprocess
from pathlib import Path

# 프로젝트 루트 디렉토리
BASE_DIR = Path(__file__).resolve().parent.parent.parent
TRANSLATIONS_DIR = BASE_DIR / 'ecoweb' / 'app' / 'translations'

# 지원 언어 목록
SUPPORTED_LANGUAGES = ['ko', 'en', 'ja', 'zh']


def check_pybabel_installed():
    """pybabel이 설치되어 있는지 확인"""
    try:
        result = subprocess.run(
            ['pybabel', '--version'],
            capture_output=True,
            text=True,
            check=True
        )
        print(f"✓ pybabel found: {result.stdout.strip()}")
        return True
    except (subprocess.CalledProcessError, FileNotFoundError):
        print("✗ pybabel not found. Please install Babel:")
        print("  pip install Babel")
        return False


def compile_language(lang):
    """특정 언어의 번역 파일 컴파일"""
    po_file = TRANSLATIONS_DIR / lang / 'LC_MESSAGES' / 'messages.po'

    if not po_file.exists():
        print(f"⚠ Warning: {po_file} not found, skipping...")
        return False

    print(f"Compiling {lang}... ", end='', flush=True)

    try:
        result = subprocess.run(
            [
                'pybabel', 'compile',
                '-d', str(TRANSLATIONS_DIR),
                '-l', lang,
                '--statistics'
            ],
            capture_output=True,
            text=True,
            check=True
        )
        print("✓")

        # 통계 정보 출력
        if result.stderr:
            stats = result.stderr.strip()
            if stats:
                print(f"  {stats}")

        return True
    except subprocess.CalledProcessError as e:
        print("✗")
        print(f"  Error: {e.stderr}")
        return False


def verify_compiled_files():
    """컴파일된 .mo 파일 존재 확인"""
    print("\n=== Verification ===")
    all_exist = True

    for lang in SUPPORTED_LANGUAGES:
        mo_file = TRANSLATIONS_DIR / lang / 'LC_MESSAGES' / 'messages.mo'
        if mo_file.exists():
            size = mo_file.stat().st_size
            print(f"✓ {lang}: {mo_file} ({size:,} bytes)")
        else:
            print(f"✗ {lang}: {mo_file} NOT FOUND")
            all_exist = False

    return all_exist


def compile_all():
    """모든 언어의 번역 파일 컴파일"""
    print("=== ECO-WEB Translation Compiler ===\n")

    if not check_pybabel_installed():
        return False

    if not TRANSLATIONS_DIR.exists():
        print(f"✗ Error: Translations directory not found: {TRANSLATIONS_DIR}")
        return False

    print(f"\nTranslations directory: {TRANSLATIONS_DIR}")
    print(f"Languages to compile: {', '.join(SUPPORTED_LANGUAGES)}\n")

    print("=== Compiling ===")
    success_count = 0

    for lang in SUPPORTED_LANGUAGES:
        if compile_language(lang):
            success_count += 1

    print(f"\n{success_count}/{len(SUPPORTED_LANGUAGES)} languages compiled successfully")

    # 검증
    verification_passed = verify_compiled_files()

    if verification_passed and success_count == len(SUPPORTED_LANGUAGES):
        print("\n✓ All translations compiled successfully!")
        return True
    else:
        print("\n⚠ Some translations failed to compile")
        return False


if __name__ == '__main__':
    try:
        success = compile_all()
        sys.exit(0 if success else 1)
    except KeyboardInterrupt:
        print("\n\nInterrupted by user")
        sys.exit(130)
    except Exception as e:
        print(f"\n✗ Unexpected error: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
