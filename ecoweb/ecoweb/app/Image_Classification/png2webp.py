import os
from PIL import Image
from pathlib import Path
from flask import session
from ecoweb.config import Config

def convert_to_webp(input_dir, output_dir, quality=75, selected_files=None, filter_larger=True):
    """
        quality (int): WebP 변환 품질 (0-100)
        selected_files (List[str] | None): 변환할 특정 파일 경로 리스트. 지정되면 해당 파일만 변환합니다.
        filter_larger (bool): True면 변환 후 크기가 원본보다 큰 이미지를 제외합니다. 기본값 True.
    """
    input_path = Path(input_dir)
    output_path = Path(output_dir)
    success_count, failed_count, webp_total_size = 0, 0, 0
    image_files = []

    if not input_path.exists():
        return [], 0, 0, 1 # input_dir 없음 실패

    output_path.mkdir(parents=True, exist_ok=True)

    if not os.access(output_path, os.W_OK):
        return [], 0, 0, 1 # output_dir 쓰기 권한 없음 실패

    # 환경변수 품질 우선 적용
    try:
        quality_env = os.getenv('IMG_WEBP_QUALITY')
        if quality_env is not None:
            quality = int(quality_env)
    except Exception:
        pass

    # 변환 대상 목록 구성
    candidate_files = []
    if selected_files:
        # 절대/상대 경로 모두 허용, 실제 존재하는 파일만 처리
        for p in selected_files:
            try:
                fp = Path(p)
                # 파일 존재 확인 및 WebP 파일 제외
                if fp.exists() and fp.is_file():
                    # 이미 WebP 파일인 경우 제외
                    if fp.suffix.lower() == '.webp':
                        continue
                    # 이미지 파일만 포함 (PNG, JPG, JPEG)
                    if fp.suffix.lower() in ['.png', '.jpg', '.jpeg']:
                        candidate_files.append(fp)
            except Exception:
                continue
    else:
        extensions = ['*.png', '*.jpg', '*.jpeg']
        for ext in extensions:
            for img in input_path.glob(ext):
                candidate_files.append(img)

    for img_file in candidate_files:
            try:
                # 파일 존재 및 크기 확인
                if not img_file.exists() or not img_file.is_file():
                    print(f"WebP 변환 실패 (파일 없음): {img_file}")
                    failed_count += 1
                    continue
                
                if os.path.getsize(img_file) == 0:
                    print(f"WebP 변환 실패 (0바이트 파일): {img_file.name}")
                    failed_count += 1
                    continue
                
                # 이미 WebP 파일인 경우 제외
                if img_file.suffix.lower() == '.webp':
                    print(f"WebP 변환 건너뜀 (이미 WebP 파일): {img_file.name}")
                    continue

                # 서브디렉토리 구조 제거: webp/ 디렉토리에 직접 저장
                output_file = output_path / f"{img_file.stem}.webp"
                webp_relative_path = Path(f"{img_file.stem}.webp")
                
                # 출력 디렉토리 생성
                output_file.parent.mkdir(parents=True, exist_ok=True)
                
                with Image.open(img_file) as img:
                    try:
                        if img.mode in ('RGBA', 'LA'):
                            img.save(output_file, 'WEBP', quality=quality, lossless=True)
                        else:
                            img.save(output_file, 'WEBP', quality=quality, lossless=False)
                        
                        original_size = os.path.getsize(img_file)
                        new_size = os.path.getsize(output_file)
                        
                        # 필터링 옵션: 변환 후 크기가 더 큰 이미지 제외
                        if filter_larger and new_size >= original_size:
                            # 변환 후 크기가 더 크거나 같은 경우: WebP 파일 삭제 및 제외
                            try:
                                output_file.unlink()  # WebP 파일 삭제
                            except Exception:
                                pass
                            failed_count += 1
                            continue
                        
                        # 실제로 절감되는 이미지만 포함
                        webp_total_size += new_size
                        # webp_name에 단순 파일명만 저장
                        image_files.append({
                            'name': output_file.name,  # 파일명 (예: image.webp)
                            'webp_name': output_file.name,  # 단순 파일명 (템플릿에서 사용)
                            'size': new_size, 
                            'original_size': original_size
                        })
                        success_count += 1
                    except (OSError, ValueError) as save_error:
                        print(f"WebP 변환 저장 실패: {img_file.name} - {save_error}")
                        failed_count += 1
            except (Image.UnidentifiedImageError, FileNotFoundError) as e:
                print(f"WebP 변환 실패 (파일오류): {img_file.name} - {e}")
                failed_count += 1
            except Exception as e:
                print(f"WebP 변환 중 예기치 않은 오류: {img_file.name} - {e}")
                failed_count += 1

    return image_files, webp_total_size, success_count, failed_count

def main():
    url_s = session.get('url')
    if url_s: 
        url_s = url_s.replace("https://", "").replace("http://", "")
    else:
        print("Error: URL not found in session for png2webp.main")
        return [] 

    print("cleaned url_s : ", url_s)
    
    # Construct the Path object for the base image directory with absolute path (var/optimization_images 사용)
    base_image_path = Path(os.path.join(Config.OPTIMIZATION_IMAGES_FOLDER, url_s))
    webp_image_path = Path(os.path.join(Config.OPTIMIZATION_IMAGES_FOLDER, url_s, 'webp'))
    
    # Ensure the base directory for original images exists.
    # os.mkdir would fail if parent directories (e.g., from a url_s like 'domain.com/path') don't exist.
    # os.makedirs will create all necessary parent directories.
    if not os.path.exists(base_image_path):
        os.makedirs(base_image_path)
    if not os.path.exists(webp_image_path):
        os.makedirs(webp_image_path)

    
    # The convert_to_webp function handles the creation of its output_dir (img_to_webp subdir).
    # We just need to ensure its input_dir (base_image_path) exists.
    result, webp_total_size = convert_to_webp(str(base_image_path), str(webp_image_path), 85)
    return result, webp_total_size

if __name__ == "__main__":
    main()