"""
모델 파일 경로 확인 스크립트
로컬 및 Docker 환경에서 모델 파일 경로를 확인합니다.
"""
import os
import sys

def check_model_paths():
    """모델 파일 경로를 확인하고 출력합니다."""
    print("=" * 80)
    print("모델 파일 경로 확인")
    print("=" * 80)
    
    # 현재 스크립트 위치 기준으로 경로 계산
    script_dir = os.path.dirname(os.path.abspath(__file__))
    project_root = os.path.dirname(script_dir)
    
    print(f"\n프로젝트 루트: {project_root}")
    
    # 로컬 경로들
    local_paths = [
        os.path.join(project_root, 'ecoweb', 'ecoweb', 'app', 'Image_Classification', 'image_classifier_model_7.h5'),
        os.path.join(project_root, 'ecoweb', 'app', 'Image_Classification', 'image_classifier_model_7.h5'),
    ]
    
    print("\n[로컬 경로 확인]")
    for path in local_paths:
        exists = os.path.exists(path)
        status = "[OK] 존재" if exists else "[X] 없음"
        print(f"  {status}: {path}")
        if exists:
            size = os.path.getsize(path)
            print(f"    크기: {size / (1024*1024):.2f} MB")
    
    # Docker 경로들
    docker_paths = [
        '/app/ecoweb/app/Image_Classification/image_classifier_model_7.h5',
        '/app/ecoweb/ecoweb/app/Image_Classification/image_classifier_model_7.h5',
    ]
    
    print("\n[Docker 경로 (참고용)]")
    for path in docker_paths:
        print(f"  {path}")
    
    # model_test.py가 사용할 경로 시뮬레이션
    print("\n[model_test.py 경로 계산 시뮬레이션]")
    model_test_path = os.path.join(project_root, 'ecoweb', 'ecoweb', 'app', 'Image_Classification', 'model_test.py')
    if os.path.exists(model_test_path):
        current_dir = os.path.dirname(os.path.abspath(model_test_path))
        calculated_path = os.path.join(current_dir, 'image_classifier_model_7.h5')
        print(f"  model_test.py 위치: {current_dir}")
        print(f"  계산된 모델 경로: {calculated_path}")
        print(f"  파일 존재: {os.path.exists(calculated_path)}")
    
    print("\n" + "=" * 80)

if __name__ == "__main__":
    check_model_paths()

