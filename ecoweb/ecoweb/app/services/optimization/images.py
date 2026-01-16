import os
from PIL import Image
from pathlib import Path
from flask import session

def convert_to_webp(input_dir, output_dir, quality=75, selected_files=None):
    """
        quality (int): WebP 변환 품질 (0-100)
        selected_files (List[str] | None): 변환할 특정 파일 경로 리스트. 지정되면 해당 파일만 변환합니다.
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
                if fp.exists():
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
                if os.path.getsize(img_file) == 0:
                    print(f"WebP 변환 실패 (0바이트 파일): {img_file.name}")
                    failed_count += 1
                    continue

                output_file = output_path / f"{img_file.stem}.webp"
                with Image.open(img_file) as img:
                    try:
                        if img.mode in ('RGBA', 'LA'):
                            img.save(output_file, 'WEBP', quality=quality, lossless=True)
                        else:
                            img.save(output_file, 'WEBP', quality=quality, lossless=False)
                        
                        original_size = os.path.getsize(img_file)
                        new_size = os.path.getsize(output_file)
                        webp_total_size += new_size
                        image_files.append({'name': output_file.name, 'size': new_size, 'original_size': original_size})
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
    
    # Construct the Path object for the base image directory with absolute path
    base_image_path = Path(f'/app/ecoweb/static/images/{url_s}')
    webp_image_path = Path(f'/app/ecoweb/static/images/{url_s}/results')
    
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