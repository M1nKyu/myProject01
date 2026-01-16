#!/usr/bin/env python3
"""
Static 파일 통합 스크립트
new-ui-css와 css를 통합하고, new-ui-js와 js를 통합합니다.
"""
import os
import shutil
from pathlib import Path

# 프로젝트 루트
BASE_DIR = Path(__file__).parent
STATIC_DIR = BASE_DIR / "ecoweb" / "ecoweb" / "app" / "static"

def copy_file_safe(src, dst):
    """파일을 안전하게 복사 (디렉터리 생성 포함)"""
    dst.parent.mkdir(parents=True, exist_ok=True)
    if src.exists():
        shutil.copy2(src, dst)
        print(f"✓ 복사: {src.relative_to(STATIC_DIR)} -> {dst.relative_to(STATIC_DIR)}")
    else:
        print(f"✗ 파일 없음: {src}")

def merge_new_ui_css():
    """new-ui-css를 css로 통합"""
    print("\n=== CSS 파일 통합 시작 ===")
    
    new_ui_css = STATIC_DIR / "new-ui-css"
    css_dir = STATIC_DIR / "css"
    
    if not new_ui_css.exists():
        print("new-ui-css 디렉터리가 없습니다.")
        return
    
    # header 디렉터리를 components/header로 복사
    header_src = new_ui_css / "header"
    header_dst = css_dir / "components" / "header"
    if header_src.exists():
        if header_dst.exists():
            shutil.rmtree(header_dst)
        shutil.copytree(header_src, header_dst)
        print(f"✓ 헤더 복사: {header_src.relative_to(STATIC_DIR)} -> {header_dst.relative_to(STATIC_DIR)}")
    
    # common 파일들 복사 (기존 파일 덮어쓰기)
    common_src = new_ui_css / "common"
    common_dst = css_dir / "common"
    if common_src.exists():
        for file in common_src.glob("*.css"):
            copy_file_safe(file, common_dst / file.name)
    
    # pages 디렉터리 통합
    pages_src = new_ui_css
    pages_dst = css_dir / "pages"
    
    # 각 페이지 디렉터리 복사
    for page_dir in ["main", "auth", "about", "membership", 
                      "carbon_calculate_emission", "detailed_analysis", 
                      "code_analysis", "img_optimization", 
                      "sustainability_analysis", "fragments"]:
        src_dir = pages_src / page_dir
        dst_dir = pages_dst / page_dir
        if src_dir.exists():
            dst_dir.mkdir(parents=True, exist_ok=True)
            for file in src_dir.glob("*.css"):
                copy_file_safe(file, dst_dir / file.name)
    
    print("\n=== CSS 파일 통합 완료 ===\n")

def merge_new_ui_js():
    """new-ui-js를 js로 통합"""
    print("\n=== JavaScript 파일 통합 시작 ===")
    
    new_ui_js = STATIC_DIR / "new-ui-js"
    js_dir = STATIC_DIR / "js"
    
    if not new_ui_js.exists():
        print("new-ui-js 디렉터리가 없습니다.")
        return
    
    # common 파일들 복사
    common_src = new_ui_js / "common"
    common_dst = js_dir / "common"
    if common_src.exists():
        common_dst.mkdir(parents=True, exist_ok=True)
        for file in common_src.glob("*.js"):
            copy_file_safe(file, common_dst / file.name)
    
    # components 디렉터리 생성 및 파일 복사
    components_dst = js_dir / "components"
    components_dst.mkdir(parents=True, exist_ok=True)
    
    # 루트의 JS 파일들을 components로 복사
    for file in new_ui_js.glob("*.js"):
        copy_file_safe(file, components_dst / file.name)
    
    print("\n=== JavaScript 파일 통합 완료 ===\n")

if __name__ == "__main__":
    print("Static 파일 통합 스크립트 시작")
    print(f"작업 디렉터리: {STATIC_DIR}")
    
    if not STATIC_DIR.exists():
        print(f"오류: {STATIC_DIR} 디렉터리가 없습니다.")
        exit(1)
    
    merge_new_ui_css()
    merge_new_ui_js()
    
    print("\n=== 모든 작업 완료 ===")
    print("\n다음 단계:")
    print("1. 브라우저에서 페이지가 정상적으로 로드되는지 확인")
    print("2. 모든 경로가 올바르게 작동하는지 확인")
    print("3. 확인 후 new-ui-css와 new-ui-js 디렉터리 삭제 가능")

