/**
 * 클라이언트 사이드 국제화(i18n) 지원
 * Flask-Babel의 번역 데이터를 JavaScript에서 사용할 수 있도록 합니다.
 */

class I18n {
    constructor() {
        this.currentLocale = 'ko';
        this.translations = {};
        this.fallbackLocale = 'ko';
        this.init();
    }

    /**
     * 초기화: 현재 언어 설정 로드
     */
    async init() {
        try {
            const response = await fetch('/language/current');
            const data = await response.json();
            this.currentLocale = data.language;
            await this.loadTranslations(this.currentLocale);
        } catch (error) {
            console.error('Failed to load current language:', error);
        }
    }

    /**
     * 번역 데이터 로드
     * @param {string} locale - 언어 코드 (ko, en, ja, zh)
     */
    async loadTranslations(locale) {
        try {
            const response = await fetch(`/static/translations/${locale}.json`);
            if (response.ok) {
                this.translations = await response.json();
            } else {
                console.warn(`Translation file for ${locale} not found`);
            }
        } catch (error) {
            console.error(`Failed to load translations for ${locale}:`, error);
        }
    }

    /**
     * 번역 문자열 가져오기
     * @param {string} key - 번역 키 (예: 'nav.service_intro')
     * @param {object} params - 대체할 파라미터 (선택사항)
     * @returns {string} 번역된 문자열
     */
    t(key, params = {}) {
        let translation = this.translations[key] || key;

        // 파라미터 대체 (예: "Hello {name}" -> "Hello John")
        Object.keys(params).forEach(paramKey => {
            translation = translation.replace(`{${paramKey}}`, params[paramKey]);
        });

        return translation;
    }

    /**
     * 현재 언어 코드 반환
     * @returns {string} 언어 코드
     */
    getLocale() {
        return this.currentLocale;
    }

    /**
     * 언어 변경
     * @param {string} locale - 새 언어 코드
     */
    async changeLanguage(locale) {
        if (locale === this.currentLocale) {
            return;
        }

        try {
            // 서버에 언어 변경 요청
            const response = await fetch(`/language/set/${locale}`);
            if (response.ok) {
                // 번역 데이터 다시 로드
                await this.loadTranslations(locale);
                this.currentLocale = locale;

                // 페이지 리로드 (서버 측 렌더링 업데이트)
                window.location.reload();
            }
        } catch (error) {
            console.error('Failed to change language:', error);
        }
    }

    /**
     * 숫자 포맷팅 (로케일 기반)
     * @param {number} value - 숫자
     * @param {object} options - Intl.NumberFormat 옵션
     * @returns {string} 포맷된 숫자
     */
    formatNumber(value, options = {}) {
        return new Intl.NumberFormat(this.currentLocale, options).format(value);
    }

    /**
     * 날짜 포맷팅 (로케일 기반)
     * @param {Date} date - 날짜 객체
     * @param {object} options - Intl.DateTimeFormat 옵션
     * @returns {string} 포맷된 날짜
     */
    formatDate(date, options = {}) {
        return new Intl.DateTimeFormat(this.currentLocale, options).format(date);
    }
}

// 전역 인스턴스 생성
const i18n = new I18n();

// 전역 함수로 노출
window.t = (key, params) => i18n.t(key, params);
window.i18n = i18n;

// 사용 예제:
// const translated = t('nav.service_intro');
// const formatted = i18n.formatNumber(1234.56);
// const formattedDate = i18n.formatDate(new Date());
