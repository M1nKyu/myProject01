import gdown
import os
import sys

file_id = '1CZPDUofij-NyKmBN21FsntZs2KbgVWeO'
output = "ecoweb/ecoweb/app/Image_Classification/image_classifier_model_7.h5"
url = f"https://drive.google.com/uc?id={file_id}"

# 이미 모델 파일이 존재하면 다운로드 스킵
if os.path.exists(output):
    print(f"Model file already exists at {output}, skipping download.")
    sys.exit(0)

try:
    print(f"Downloading image classification model from Google Drive...")
    gdown.download(url, output, quiet=False)
    print("Image Classifier Model Download complete!")
except Exception as e:
    print(f"Warning: Failed to download image classification model: {e}")
    print("The application will run without image classification functionality.")
    print("You can manually download the model later if needed.")
    # Docker 빌드가 실패하지 않도록 경고만 출력하고 성공으로 종료
    sys.exit(0)
