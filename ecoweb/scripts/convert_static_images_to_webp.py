"""
정적 이미지 디렉터리의 모든 PNG 이미지를 WebP로 변환하는 스크립트

사용법:
    python scripts/convert_static_images_to_webp.py

환경변수:
    IMG_WEBP_QUALITY: WebP 변환 품질 (0-100, 기본값: 85)
"""
import os
import sys
from pathlib import Path
from PIL import Image

# 프로젝트 루트를 Python 경로에 추가
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

def convert_png_to_webp(input_file: Path, output_file: Path, quality: int = 85, filter_larger: bool = True) -> tuple[bool, int, int]:
    """
    단일 PNG 파일을 WebP로 변환
    
    Args:
        input_file: 입력 PNG 파일 경로
        output_file: 출력 WebP 파일 경로
        quality: WebP 변환 품질 (0-100)
        filter_larger: True면 변환 후 크기가 원본보다 큰 이미지를 제외
    
    Returns:
        (성공 여부, 원본 크기, 변환된 크기)
    """
    try:
        if os.path.getsize(input_file) == 0:
            print(f"  [실패] {input_file.name}: 0바이트 파일")
            return False, 0, 0

        # 출력 디렉터리 생성
        output_file.parent.mkdir(parents=True, exist_ok=True)

        with Image.open(input_file) as img:
            # RGBA 또는 LA 모드는 lossless로 저장
            if img.mode in ('RGBA', 'LA'):
                img.save(output_file, 'WEBP', quality=quality, lossless=True)
            else:
                img.save(output_file, 'WEBP', quality=quality, lossless=False)
            
            original_size = os.path.getsize(input_file)
            new_size = os.path.getsize(output_file)
            
            # 필터링 옵션: 변환 후 크기가 더 큰 이미지 제외
            if filter_larger and new_size >= original_size:
                try:
                    output_file.unlink()  # WebP 파일 삭제
                except Exception:
                    pass
                print(f"  [필터링] {input_file.name}: 원본 {original_size:,} bytes → WebP {new_size:,} bytes (제외됨)")
                return False, original_size, new_size
            
            reduction = original_size - new_size
            reduction_percent = (reduction / original_size) * 100
            print(f"  [성공] {input_file.name}: {original_size:,} bytes → {new_size:,} bytes ({reduction_percent:.1f}% 절감)")
            return True, original_size, new_size
            
    except (Image.UnidentifiedImageError, FileNotFoundError) as e:
        print(f"  [실패] {input_file.name}: 파일 오류 - {e}")
        return False, 0, 0
    except (OSError, ValueError) as e:
        print(f"  [실패] {input_file.name}: 저장 오류 - {e}")
        return False, 0, 0
    except Exception as e:
        print(f"  [실패] {input_file.name}: 예기치 않은 오류 - {e}")
        return False, 0, 0


def convert_static_images_to_webp(base_dir: Path, output_base_dir: Path, quality: int = 85, filter_larger: bool = True):
    """
    정적 이미지 디렉터리의 모든 PNG를 WebP로 변환
    
    Args:
        base_dir: 입력 디렉터리 (예: ecoweb/ecoweb/app/static/img/)
        output_base_dir: 출력 디렉터리 (예: ecoweb/ecoweb/app/static/img/webp/)
        quality: WebP 변환 품질 (0-100)
        filter_larger: True면 변환 후 크기가 원본보다 큰 이미지를 제외
    """
    if not base_dir.exists():
        print(f"오류: 입력 디렉터리가 존재하지 않습니다: {base_dir}")
        return
    
    # 환경변수 품질 우선 적용
    try:
        quality_env = os.getenv('IMG_WEBP_QUALITY')
        if quality_env is not None:
            quality = int(quality_env)
    except Exception:
        pass
    
    # 모든 PNG 파일 찾기 (재귀적)
    png_files = list(base_dir.rglob('*.png'))
    
    if not png_files:
        print("변환할 PNG 파일이 없습니다.")
        return
    
    print(f"\n총 {len(png_files)}개의 PNG 파일을 찾았습니다.\n")
    print("=" * 80)
    
    success_count = 0
    failed_count = 0
    filtered_count = 0
    total_original_size = 0
    total_webp_size = 0
    
    for png_file in png_files:
        # 원본 디렉터리 구조 유지
        relative_path = png_file.relative_to(base_dir)
        webp_file = output_base_dir / relative_path.with_suffix('.webp')
        
        print(f"\n[{success_count + failed_count + filtered_count + 1}/{len(png_files)}] {relative_path}")
        
        success, original_size, webp_size = convert_png_to_webp(
            png_file, 
            webp_file, 
            quality=quality, 
            filter_larger=filter_larger
        )
        
        if success:
            success_count += 1
            total_original_size += original_size
            total_webp_size += webp_size
        elif filter_larger and webp_size >= original_size:
            filtered_count += 1
        else:
            failed_count += 1
    
    print("\n" + "=" * 80)
    print("\n변환 결과:")
    print(f"  성공: {success_count}개")
    print(f"  필터링됨 (크기 증가): {filtered_count}개")
    print(f"  실패: {failed_count}개")
    
    if success_count > 0:
        total_reduction = total_original_size - total_webp_size
        total_reduction_percent = (total_reduction / total_original_size) * 100
        print(f"\n크기 절감:")
        print(f"  원본 총 크기: {total_original_size:,} bytes ({total_original_size / 1024 / 1024:.2f} MB)")
        print(f"  WebP 총 크기: {total_webp_size:,} bytes ({total_webp_size / 1024 / 1024:.2f} MB)")
        print(f"  절감량: {total_reduction:,} bytes ({total_reduction / 1024 / 1024:.2f} MB, {total_reduction_percent:.1f}%)")
    
    print("\n변환 완료!")


def main():
    """메인 함수"""
    # 프로젝트 루트 기준으로 경로 설정
    # scripts/convert_static_images_to_webp.py -> ecoweb/ -> ecoweb/ecoweb/app/static/img
    script_path = Path(__file__).resolve()
    # scripts 디렉터리의 부모가 ecoweb
    ecoweb_root = script_path.parent.parent
    base_dir = ecoweb_root / 'ecoweb' / 'app' / 'static' / 'img'
    output_base_dir = ecoweb_root / 'ecoweb' / 'app' / 'static' / 'img' / 'webp'
    
    print("정적 이미지 PNG → WebP 변환 스크립트")
    print("=" * 80)
    print(f"입력 디렉터리: {base_dir}")
    print(f"출력 디렉터리: {output_base_dir}")
    print(f"품질: {os.getenv('IMG_WEBP_QUALITY', '85')} (환경변수 IMG_WEBP_QUALITY로 조절 가능)")
    print("=" * 80)
    
    convert_static_images_to_webp(
        base_dir=base_dir,
        output_base_dir=output_base_dir,
        quality=85,
        filter_larger=True
    )


if __name__ == "__main__":
    main()

