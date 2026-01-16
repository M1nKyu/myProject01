/**
 * PDF 보고서 생성 관련 JavaScript 함수들
 * 다중 사용자 환경에서 안전하게 동작하도록 구현
 */

class PDFReportManager {
    constructor() {
        this.isGenerating = false;
        this.init();
    }

    init() {
        // PDF 저장 버튼 이벤트 리스너 등록
        document.addEventListener('DOMContentLoaded', () => {
            this.attachEventListeners();
            this.checkPDFAvailability();
        });
    }

    getTaskId() {
        // 1. body의 data-task-id 속성에서 가져오기
        const taskIdFromBody = document.body.dataset.taskId;
        if (taskIdFromBody) return taskIdFromBody;

        // 2. hidden input에서 가져오기
        const taskIdInput = document.getElementById('task-id') || document.querySelector('input[name="task_id"]');
        if (taskIdInput) return taskIdInput.value;

        // 3. 전역 변수에서 가져오기 (템플릿에서 설정된 경우)
        if (typeof window.taskId !== 'undefined') return window.taskId;

        // 4. URL path에서 추출 (예: /carbon_calculate_emission/task-id-123)
        const pathMatch = window.location.pathname.match(/\/carbon_calculate_emission\/([^\/]+)/);
        if (pathMatch && pathMatch[1]) return pathMatch[1];

        console.error('task_id를 찾을 수 없습니다.');
        return null;
    }

    attachEventListeners() {
        // PDF 저장 버튼 찾기 (새 클래스명)
        const pdfButton = document.querySelector('.userbar-pdf');
        if (pdfButton) {
            pdfButton.addEventListener('click', (e) => {
                e.preventDefault();
                this.handlePDFGeneration();
            });

            // 호버 효과 추가
            pdfButton.addEventListener('mouseenter', () => {
                if (!this.isGenerating) {
                    pdfButton.style.cursor = 'pointer';
                    pdfButton.style.opacity = '0.8';
                }
            });

            pdfButton.addEventListener('mouseleave', () => {
                pdfButton.style.opacity = '1';
            });
        }
    }

    async checkPDFAvailability() {
        try {
            // task_id를 페이지의 dataset 또는 hidden input에서 가져오기
            const taskId = this.getTaskId();
            if (!taskId) {
                this.disablePDFButton('분석 작업 ID를 찾을 수 없습니다.');
                return;
            }

            const response = await fetch(`/check-pdf-availability/${taskId}`, {
                method: 'GET',
                headers: {
                    'Content-Type': 'application/json',
                },
                credentials: 'same-origin'
            });

            const result = await response.json();

            if (!result.available) {
                this.disablePDFButton(result.reason || '분석 데이터가 없습니다.');
            } else {
                this.enablePDFButton();
            }
        } catch (error) {
            console.error('PDF 가용성 확인 중 오류:', error);
            this.disablePDFButton('시스템 오류가 발생했습니다.');
        }
    }

    async handlePDFGeneration() {
        if (this.isGenerating) {
            return;
        }

        try {
            this.setGeneratingState(true);

            // 사용자에게 진행 상황 알림
            this.showNotification('PDF 보고서 생성을 시작합니다...', 'info');

            // task_id 가져오기
            const taskId = this.getTaskId();
            if (!taskId) {
                throw new Error('분석 작업 ID를 찾을 수 없습니다.');
            }

            // 1단계: PDF 생성 작업 요청
            const response = await fetch(`/generate-simple-pdf-report/${taskId}`, {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                },
                credentials: 'same-origin'
            });

            if (!response.ok) {
                const errorData = await response.json();
                throw new Error(errorData.error || 'PDF 생성 요청에 실패했습니다.');
            }

            const data = await response.json();

            if (!data.success || !data.task_id) {
                throw new Error('PDF 생성 작업을 시작할 수 없습니다.');
            }

            const pdfTaskId = data.task_id;
            console.log('PDF 생성 작업 시작:', pdfTaskId);

            // 2단계: 작업 상태 폴링
            const result = await this.pollTaskStatus(pdfTaskId);

            if (result.status === 'SUCCESS') {
                // 3단계: PDF 다운로드
                await this.downloadPDF(pdfTaskId, result.filename);

                this.showNotification('PDF 보고서가 성공적으로 다운로드되었습니다.', 'success');

                // 다운로드 완료 후 버튼 상태 복원
                setTimeout(() => {
                    this.setGeneratingState(false);
                }, 1000);

            } else if (result.status === 'FAILURE') {
                throw new Error(result.error || 'PDF 생성에 실패했습니다.');
            } else if (result.status === 'CANCELLED') {
                throw new Error('PDF 생성 작업이 취소되었습니다.');
            } else {
                throw new Error('PDF 생성 작업이 알 수 없는 상태입니다: ' + result.status);
            }

        } catch (error) {
            console.error('PDF 생성 중 오류:', error);
            this.showNotification(
                error.message || 'PDF 보고서 생성 중 오류가 발생했습니다. 잠시 후 다시 시도해주세요.',
                'error'
            );
            this.setGeneratingState(false);
        }
    }

    async pollTaskStatus(taskId, maxAttempts = 60, interval = 2000) {
        /**
         * 작업 상태를 주기적으로 확인
         * @param {string} taskId - 작업 ID
         * @param {number} maxAttempts - 최대 시도 횟수 (기본 60회 = 2분)
         * @param {number} interval - 폴링 간격 (밀리초, 기본 2000ms)
         */
        let attempts = 0;

        while (attempts < maxAttempts) {
            try {
                const response = await fetch(`/pdf-status/${taskId}`, {
                    method: 'GET',
                    headers: {
                        'Content-Type': 'application/json',
                    },
                    credentials: 'same-origin'
                });

                if (!response.ok) {
                    throw new Error('작업 상태 조회에 실패했습니다.');
                }

                const result = await response.json();

                if (!result.success) {
                    throw new Error(result.error || '작업 정보를 가져올 수 없습니다.');
                }

                console.log('작업 상태:', result.status, result.progress);

                // 진행 상황 업데이트
                if (result.progress && result.progress.message) {
                    this.updateProgressMessage(result.progress.message);
                }

                // 완료 상태 확인
                if (result.status === 'SUCCESS' || result.status === 'FAILURE' || result.status === 'CANCELLED') {
                    return {
                        status: result.status,
                        error: result.error,
                        filename: result.result ? result.result.filename : null
                    };
                }

                // 다음 폴링까지 대기
                await new Promise(resolve => setTimeout(resolve, interval));
                attempts++;

            } catch (error) {
                console.error('상태 폴링 중 오류:', error);
                throw error;
            }
        }

        // 타임아웃
        throw new Error('PDF 생성 시간이 초과되었습니다. 잠시 후 다시 시도해주세요.');
    }

    async downloadPDF(taskId, filename) {
        /**
         * 생성된 PDF 파일 다운로드
         * @param {string} taskId - 작업 ID
         * @param {string} filename - 파일명
         */
        try {
            const response = await fetch(`/download-pdf/${taskId}`, {
                method: 'GET',
                credentials: 'same-origin'
            });

            if (!response.ok) {
                throw new Error('PDF 다운로드에 실패했습니다.');
            }

            // Blob으로 변환
            const blob = await response.blob();
            const url = window.URL.createObjectURL(blob);

            // 다운로드 링크 생성 및 클릭
            const downloadLink = document.createElement('a');
            downloadLink.href = url;
            downloadLink.download = filename || 'carbon_report.pdf';
            document.body.appendChild(downloadLink);
            downloadLink.click();
            document.body.removeChild(downloadLink);

            // 메모리 정리
            window.URL.revokeObjectURL(url);

        } catch (error) {
            console.error('PDF 다운로드 중 오류:', error);
            throw error;
        }
    }

    updateProgressMessage(message) {
        /**
         * 진행 상황 메시지 업데이트
         * @param {string} message - 진행 상황 메시지
         */
        const pdfText = document.querySelector('.userbar-pdf .userbar-actions-text');
        if (pdfText) {
            // 메시지에서 시간 정보만 추출 (예: "PDF 페이지 생성 중 (5/13) - 25s" -> "PDF 생성 중... 25s")
            let displayMessage = 'PDF 생성 중...';

            // 시간 정보 추출 (예: "45s")
            const timeMatch = message.match(/(\d+)s/);
            if (timeMatch) {
                displayMessage = `PDF 생성 중... ${timeMatch[0]}`;
            }

            pdfText.textContent = displayMessage;
        }
    }

    setGeneratingState(isGenerating) {
        this.isGenerating = isGenerating;
        const pdfButton = document.querySelector('.userbar-pdf');
        const pdfText = document.querySelector('.userbar-pdf .userbar-actions-text');

        if (pdfButton && pdfText) {
            if (isGenerating) {
                pdfButton.style.opacity = '0.6';
                pdfButton.style.cursor = 'not-allowed';
                pdfText.innerHTML = '<span class="text-full">PDF 생성 중...</span><span class="text-short">생성중...</span>';

                // 로딩 애니메이션 추가
                pdfButton.classList.add('generating');
            } else {
                pdfButton.style.opacity = '1';
                pdfButton.style.cursor = 'pointer';
                pdfText.innerHTML = '<span class="text-full">PDF로 저장하기</span><span class="text-short">PDF저장</span>';

                // 로딩 애니메이션 제거
                pdfButton.classList.remove('generating');
            }
        }
    }

    enablePDFButton() {
        const pdfButton = document.querySelector('.userbar-pdf');
        if (pdfButton) {
            pdfButton.style.opacity = '1';
            pdfButton.style.cursor = 'pointer';
            pdfButton.removeAttribute('disabled');
            pdfButton.title = 'PDF 보고서 다운로드';
        }
    }

    disablePDFButton(reason) {
        const pdfButton = document.querySelector('.userbar-pdf');
        if (pdfButton) {
            pdfButton.style.opacity = '0.5';
            pdfButton.style.cursor = 'not-allowed';
            pdfButton.setAttribute('disabled', 'true');
            pdfButton.title = reason;
        }
    }

    showNotification(message, type = 'info') {
        // 기존 알림 제거
        const existingNotification = document.querySelector('.pdf-notification');
        if (existingNotification) {
            existingNotification.remove();
        }

        // 새 알림 생성
        const notification = document.createElement('div');
        notification.className = `pdf-notification pdf-notification-${type}`;
        notification.innerHTML = `
            <div class="pdf-notification-content">
                <span class="pdf-notification-icon">${this.getNotificationIcon(type)}</span>
                <span class="pdf-notification-message">${message}</span>
                <button class="pdf-notification-close" onclick="this.parentElement.parentElement.remove()">×</button>
            </div>
        `;

        // 스타일 적용
        notification.style.cssText = `
            position: fixed;
            top: 100px;
            right: 20px;
            z-index: 100001;
            max-width: 400px;
            padding: 15px;
            border-radius: 8px;
            box-shadow: 0 4px 12px rgba(0, 0, 0, 0.15);
            font-family: 'Malgun Gothic', sans-serif;
            font-size: 14px;
            line-height: 1.4;
            animation: slideInRight 0.3s ease-out;
            ${this.getNotificationStyles(type)}
        `;

        document.body.appendChild(notification);

        // 자동 제거 (성공/정보 메시지만)
        if (type !== 'error') {
            setTimeout(() => {
                if (notification.parentNode) {
                    notification.style.animation = 'slideOutRight 0.3s ease-in';
                    setTimeout(() => {
                        if (notification.parentNode) {
                            notification.remove();
                        }
                    }, 300);
                }
            }, 5000);
        }
    }

    getNotificationIcon(type) {
        const icons = {
            'success': '✅',
            'error': '❌',
            'info': 'ℹ️',
            'warning': '⚠️'
        };
        return icons[type] || icons['info'];
    }

    getNotificationStyles(type) {
        const styles = {
            'success': 'background-color: #d4edda; border-left: 4px solid #28a745; color: #155724;',
            'error': 'background-color: #f8d7da; border-left: 4px solid #dc3545; color: #721c24;',
            'info': 'background-color: #d1ecf1; border-left: 4px solid #17a2b8; color: #0c5460;',
            'warning': 'background-color: #fff3cd; border-left: 4px solid #ffc107; color: #856404;'
        };
        return styles[type] || styles['info'];
    }
}

// CSS 애니메이션 추가
const style = document.createElement('style');
style.textContent = `
    @keyframes slideInRight {
        from {
            transform: translateX(100%);
            opacity: 0;
        }
        to {
            transform: translateX(0);
            opacity: 1;
        }
    }

    @keyframes slideOutRight {
        from {
            transform: translateX(0);
            opacity: 1;
        }
        to {
            transform: translateX(100%);
            opacity: 0;
        }
    }

    .pdf-notification-content {
        display: flex;
        align-items: center;
        gap: 10px;
    }

    .pdf-notification-close {
        background: none;
        border: none;
        font-size: 18px;
        cursor: pointer;
        margin-left: auto;
        padding: 0;
        width: 20px;
        height: 20px;
        display: flex;
        align-items: center;
        justify-content: center;
        border-radius: 50%;
        transition: background-color 0.2s;
    }

    .pdf-notification-close:hover {
        background-color: rgba(0, 0, 0, 0.1);
    }

    .userbar-pdf.generating {
        animation: pulse 1.5s ease-in-out infinite;
    }

    @keyframes pulse {
        0% {
            opacity: 0.6;
        }
        50% {
            opacity: 0.8;
        }
        100% {
            opacity: 0.6;
        }
    }
`;
document.head.appendChild(style);

// PDF 보고서 매니저 인스턴스 생성
const pdfReportManager = new PDFReportManager();
