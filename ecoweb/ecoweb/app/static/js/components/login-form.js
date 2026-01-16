// 로그인 input placeholder 동작 (디자인 유지)
document.addEventListener('DOMContentLoaded', function() {
    const usernameInput = document.getElementById('login-username');
    const usernamePlaceholder = document.getElementById('login-id-placeholder');
    const passwordInput = document.getElementById('login-password');
    const passwordPlaceholder = document.getElementById('login-pw-placeholder');
    const passwordEyeToggle = document.getElementById('login-pw-eye-toggle');
    const passwordEyeIcon = document.getElementById('login-pw-eye-icon');
    const saveCheckBox = document.querySelector('.login-save-check-box');

    function togglePlaceholder(input, placeholder) {
        if (input.value.length > 0) {
            placeholder.style.display = 'none';
        } else {
            placeholder.style.display = '';
        }
    }

    // 플레이스홀더 동작
    if (usernameInput && usernamePlaceholder) {
        usernameInput.addEventListener('input', function() {
            togglePlaceholder(usernameInput, usernamePlaceholder);
        });
        togglePlaceholder(usernameInput, usernamePlaceholder);
    }
    if (passwordInput && passwordPlaceholder) {
        passwordInput.addEventListener('input', function() {
            togglePlaceholder(passwordInput, passwordPlaceholder);
        });
        togglePlaceholder(passwordInput, passwordPlaceholder);
    }

    // 비밀번호 보기/숨기기 토글
    if (passwordEyeToggle && passwordInput && passwordEyeIcon) {
        const eyeOffIconPath = passwordEyeIcon.src.includes('login-eye-off.svg') 
            ? passwordEyeIcon.src 
            : passwordEyeIcon.src.replace('login-eye.svg', 'login-eye-off.svg');
        const eyeIconPath = eyeOffIconPath.replace('login-eye-off.svg', 'login-eye.svg');
        
        passwordEyeToggle.addEventListener('click', function() {
            if (passwordInput.type === 'password') {
                // 비밀번호 표시: eye 아이콘으로 변경 (눈 뜸)
                passwordInput.type = 'text';
                passwordEyeIcon.src = eyeIconPath;
            } else {
                // 비밀번호 숨김: eye-off 아이콘으로 변경 (눈 감음)
                passwordInput.type = 'password';
                passwordEyeIcon.src = eyeOffIconPath;
            }
        });
    }

    // 아이디 저장 체크박스 기능
    let isRememberIdChecked = false;
    
    if (saveCheckBox) {
        // 페이지 로드 시 저장된 아이디 확인
        const savedUsername = localStorage.getItem('rememberedUsername');
        if (savedUsername && usernameInput) {
            usernameInput.value = savedUsername;
            isRememberIdChecked = true;
            saveCheckBox.classList.add('checked');
            togglePlaceholder(usernameInput, usernamePlaceholder);
        }

        // 체크박스 클릭 이벤트
        saveCheckBox.addEventListener('click', function() {
            isRememberIdChecked = !isRememberIdChecked;
            if (isRememberIdChecked) {
                saveCheckBox.classList.add('checked');
            } else {
                saveCheckBox.classList.remove('checked');
                // 체크 해제 시 저장된 아이디 삭제
                localStorage.removeItem('rememberedUsername');
            }
        });
    }

    // 로그인 폼 제출 시 아이디 저장 처리
    const loginForm = document.querySelector('.login-form');
    if (loginForm) {
        loginForm.addEventListener('submit', function(e) {
            // 아이디 저장이 체크되어 있고 아이디가 입력되어 있으면 저장
            if (isRememberIdChecked && usernameInput && usernameInput.value.trim()) {
                localStorage.setItem('rememberedUsername', usernameInput.value.trim());
            } else if (!isRememberIdChecked) {
                // 체크되어 있지 않으면 저장된 아이디 삭제
                localStorage.removeItem('rememberedUsername');
            }
        });
    }
});
