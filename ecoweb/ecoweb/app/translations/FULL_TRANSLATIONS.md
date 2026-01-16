# 전체 페이지 번역 키 설계

## 번역 전략

각 페이지의 핵심 UI 텍스트만 번역하고, 설명문이나 가이드는 언어별로 다르게 작성합니다.

## 페이지별 번역 키

### 1. 로딩 페이지 (loading.html)

```
loading.page_title = "분석 중... - eCarbon"
loading.please_wait = "잠시만 기다려주세요..."
loading.analyzing_url_suffix = "을 분석하고 있어요!"
loading.analyzing_main_page = "입력 페이지 분석 중"
loading.analyzing_subpages = "하위 페이지 분석 중"
loading.optimizing_images = "이미지 최적화 진행 중"
loading.analysis_complete = "분석 완료!"
loading.view_results = "결과 보기"
loading.go_home = "홈으로 돌아가기"
loading.queued_message = "서버 요청이 많아 대기 중입니다. (대기열: {position}번째)"
loading.in_progress = "분석을 진행하고 있어요..."
loading.cancelled_title = "분석이 취소되었습니다"
loading.cancelled_message = "사용자에 의해 분석이 중단되었습니다."
loading.failed_title = "분석에 실패했습니다"
loading.failed_message = "웹사이트 분석 중 문제가 발생했습니다."
loading.new_analysis = "새로운 분석 시작하기"
loading.check_site = "사이트 직접 확인"
loading.try_different_url = "다른 URL 입력하기"
```

### 2. 탄소 배출량 결과 페이지 (carbon_calculate_emission.html)

```
result.page_title = "탄소 배출량 분석 결과"
result.carbon_footprint = "탄소발자국"
result.page_weight = "페이지 무게"
result.grade = "등급"
result.percentile = "상위 {percent}%"
result.cleaner_than = "전체 웹사이트보다 깨끗합니다"
result.comparison_korea = "한국 평균과 비교"
result.comparison_global = "세계 평균과 비교"
result.higher = "높습니다"
result.lower = "낮습니다"
result.equivalent_to = "이는 다음과 같습니다"
result.tree_months = "나무 {count}그루를 {months}개월 키운 효과"
result.smartphone_charges = "스마트폰 {count}회 충전"
result.subpages_title = "하위 페이지 분석"
result.optimization_title = "최적화 제안"
result.download_pdf = "PDF 다운로드"
result.share_results = "결과 공유하기"
```

### 3. 상세 분석 페이지 (detailed_analysis.html)

```
detailed.page_title = "상세 분석 리포트"
detailed.emissions_by_type = "콘텐츠 유형별 배출량"
detailed.total_emission = "총 배출량"
detailed.average_emission = "평균 배출량"
detailed.breakdown_chart = "배출량 분해 차트"
detailed.recommendations = "개선 권장사항"
```

### 4. 코드 최적화 페이지 (code_analysis.html)

```
code.page_title = "코드 최적화"
code.optimization_opportunities = "최적화 기회"
code.file_size_reduction = "파일 크기 감소"
code.minification = "압축 및 최소화"
code.code_splitting = "코드 분할"
code.download_optimized = "최적화된 코드 다운로드"
```

### 5. 이미지 최적화 페이지 (img_optimization.html)

```
image.page_title = "이미지 최적화"
image.total_images = "총 이미지 개수"
image.optimizable_images = "최적화 가능 이미지"
image.size_reduction = "용량 감소"
image.webp_conversion = "WebP 변환"
image.download_optimized = "최적화된 이미지 다운로드"
```

### 6. 지속가능성 분석 페이지 (sustainability_analysis.html)

```
sustainability.page_title = "지속가능성 분석"
sustainability.w3c_guidelines = "W3C 지속가능한 웹 가이드라인"
sustainability.compliance_score = "준수율"
sustainability.recommendations = "권장사항"
sustainability.best_practices = "모범 사례"
```

## 공통 번역 키 (이미 정의됨)

```
common.submit = "제출"
common.cancel = "취소"
common.confirm = "확인"
common.close = "닫기"
common.save = "저장"
common.delete = "삭제"
common.edit = "수정"
common.view_more = "더보기"
error.invalid_url = "유효하지 않은 URL입니다"
error.analysis_failed = "분석에 실패했습니다"
error.network_error = "네트워크 오류가 발생했습니다"
error.server_error = "서버 오류가 발생했습니다"
```

## 구현 우선순위

1. 로딩 페이지 (가장 자주 보는 페이지)
2. 탄소 배출량 결과 페이지 (핵심 기능)
3. 나머지 페이지 (순차 적용)
