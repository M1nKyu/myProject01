import tensorflow as tf
import numpy as np
from tensorflow.keras.preprocessing import image
import cv2
import os
import time

# Verbose logging toggle (set to True for detailed per-image logs)
VERBOSE = False

result = []
current_dir = os.path.dirname(os.path.abspath(__file__))
model_path = os.path.join(current_dir, 'image_classifier_model_7.h5')
# Docker 환경에서 모델 파일이 없을 경우 대체 경로 확인
if not os.path.exists(model_path):
    # Dockerfile에서 COPY . /app을 하면 ecoweb/ 디렉터리가 /app/ecoweb/로 복사됨
    docker_model_paths = [
        '/app/ecoweb/app/Image_Classification/image_classifier_model_7.h5',  # 올바른 경로
        '/app/ecoweb/ecoweb/app/Image_Classification/image_classifier_model_7.h5',  # 이전 경로 (하위 호환)
    ]
    for docker_path in docker_model_paths:
        if os.path.exists(docker_path):
            model_path = docker_path
            print(f"[MODEL] Found model at Docker path: {docker_path}")
            break

# Lazy-load model to avoid Celery prefork TF issues
_model = None

def get_model():
    global _model
    if _model is None:
        import logging
        logger = logging.getLogger(__name__)
        
        logger.info(f"[MODEL] Loading image classifier model from: {model_path}")
        logger.info(f"[MODEL] Model file exists: {os.path.exists(model_path)}")
        
        if not os.path.exists(model_path):
            error_msg = f"모델 파일을 찾을 수 없습니다: {model_path}"
            logger.error(f"[MODEL] {error_msg}")
            raise FileNotFoundError(error_msg)
        
        try:
            # optional: constrain TF threads to avoid oversubscription
            try:
                tf.config.threading.set_intra_op_parallelism_threads(2)
                tf.config.threading.set_inter_op_parallelism_threads(2)
            except Exception:
                pass
            # ensure GPU is disabled in CPU-only containers
            try:
                tf.config.set_visible_devices([], 'GPU')
            except Exception:
                pass

            logger.info(f"[MODEL] Starting model load...")
            _model = tf.keras.models.load_model(model_path)
            logger.info(f"[MODEL] Model loaded successfully")
            
            # warm-up after load to avoid first-call latency
            try:
                dummy = np.zeros((1, 224, 224, 3), dtype=np.float32)
                _ = _model.predict(dummy, verbose=0)
                logger.info("[MODEL] Warm-up inference completed")
                print("[PRINT][MODEL] Warm-up inference completed")
            except Exception as _e:
                # Keep warm-up failure visible once
                logger.warning(f"[MODEL] Warm-up skipped: {_e}")
                print(f"[PRINT][MODEL] Warm-up skipped: {_e}")
        except Exception as e:
            error_msg = f"Error loading model: {e}"
            logger.error(f"[MODEL] {error_msg}")
            print(error_msg)
            raise
    else:
        import logging
        logger = logging.getLogger(__name__)
        logger.debug("[MODEL] Using cached model instance")
    
    return _model

# 이미지 업스케일 함수 (고급 보간법 사용)
def preprocess_image(img_path, target_size=(224, 224)):

    # OpenCV로 이미지 불러오기
    t0 = time.perf_counter()
    img = cv2.imread(img_path)
    if img is None:
        if VERBOSE:
            print(f"[PRINT][MODEL] Preprocess skip (unreadable): {os.path.basename(img_path)}")
        return None

    # 고급 보간법으로 이미지 확대
    img = cv2.resize(img, target_size, interpolation=cv2.INTER_CUBIC)

    # BGR을 RGB로 변환
    img = cv2.cvtColor(img, cv2.COLOR_BGR2RGB)

    # 정규화 (모델 학습 시 사용한 것과 동일하게)
    img = img / 255.0
    img = np.expand_dims(img, axis=0)

    t1 = time.perf_counter()
    prep_ms = int((t1 - t0) * 1000)
    if VERBOSE:
        print(f"[PRINT][MODEL] Preprocess done: {os.path.basename(img_path)} | {prep_ms} ms")
    return img

# 이미지 예측 함수
def predict_image(img_path, filename, output_path):

    if not os.path.exists(output_path):
        os.makedirs(output_path)
    # 클래스 이름 정의
    class_names = ['jpg_human', 'jpg_logo', 'jpg_nature', 'jpg_svg']  # train_data.class_indices에서 가져온 순서대로 입력
    
    # 분류 디렉토리 생성 제거: 분류 정보는 메타데이터로만 관리

    # 이미지 전처리
    img_array = preprocess_image(img_path)

    # 예측 수행
    p0 = time.perf_counter()
    m = get_model()
    predictions = m.predict(img_array, verbose=0)
    p1 = time.perf_counter()
    pred_ms = int((p1 - p0) * 1000)

    predicted_class_index = np.argmax(predictions, axis=1)[0]
    confidence = predictions[0][predicted_class_index]
    predicted_class_name = class_names[predicted_class_index]

    if VERBOSE:
        print(f"[PRINT][MODEL] Predict done: {filename} | {pred_ms} ms")
    # 분류 디렉토리 생성 및 파일 복사 제거: 분류 정보는 메타데이터로만 관리

    # 파일 크기 가져오기
    try:
        size = os.path.getsize(img_path)
    except OSError:
        size = 0

    # 예측 결과 반환
    return {
        'name': filename,
        'size': size,
        'class_name': predicted_class_name,
        'confidence': float(confidence)  # JSON 직렬화를 위해 float으로 변환
    }

# 배치 예측 함수: 여러 이미지를 한 번에 예측하여 속도 향상
def predict_images_batch(img_paths, filenames, output_path):
    import logging
    logger = logging.getLogger(__name__)
    
    logger.info(f"[MODEL] predict_images_batch called with {len(img_paths)} images")
    # output_path는 더 이상 사용되지 않지만 함수 시그니처 호환성을 위해 유지
    # 분류 디렉토리 생성 제거: 분류 정보는 메타데이터로만 관리
    
    class_names = ['jpg_human', 'jpg_logo', 'jpg_nature', 'jpg_svg']

    # 전처리 배치 구성
    arrays = []
    sizes = []
    kept_filenames = []
    kept_paths = []
    for p, fn in zip(img_paths, filenames):
        arr = preprocess_image(p)
        if arr is None:
            continue
        arrays.append(arr)
        kept_filenames.append(fn)
        kept_paths.append(p)
        try:
            sizes.append(os.path.getsize(p))
        except OSError:
            sizes.append(0)

    if len(arrays) == 0:
        logger.warning("[MODEL] No valid images to process")
        return []

    logger.info(f"[MODEL] Processing {len(arrays)} images with model")
    batch = np.vstack(arrays)
    b0 = time.perf_counter()
    m = get_model()
    logger.info(f"[MODEL] Model instance obtained, starting batch prediction...")
    preds = m.predict(batch, verbose=0)
    b1 = time.perf_counter()
    elapsed_ms = int((b1-b0)*1000)
    logger.info(f"[MODEL] Batch predict completed: {len(arrays)} items in {elapsed_ms} ms")
    print(f"[PRINT][MODEL] Batch predict done: {len(arrays)} items | {elapsed_ms} ms")

    results = []
    for i, probs in enumerate(preds):
        idx = int(np.argmax(probs))
        conf = float(probs[idx])
        cname = class_names[idx]
        # 파일 복사 제거: 분류 정보는 메타데이터로만 관리
        # copied_path 필드 제거

        results.append({
            'name': kept_filenames[i],
            'size': sizes[i],
            'class_name': cname,
            'confidence': conf,
            'original_path': kept_paths[i]
        })

    return results
    
def main():
    if __name__ == "__main__":
        not_confi = 0
        confi = 0
        # 테스트할 이미지 경로
        test_image_path = 'images'  # 실제 테스트 이미지 경로로 변경
        for filename in os.listdir(test_image_path):
            test_path = os.path.join(test_image_path, filename)
            try:
                predict_image(test_path,filename, output_path)
            except Exception as e:
                print(f" path : {test_path} error : {e}")

        print(f"not confi : {not_confi}")
        print(f"confi : {confi}")