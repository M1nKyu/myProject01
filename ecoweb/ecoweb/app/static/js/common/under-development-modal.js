// 'data-dev-link' 속성을 가진 모든 요소를 찾습니다.
const devLinks = document.querySelectorAll('[data-dev-link]');

// 각 링크에 클릭 이벤트 리스너를 추가합니다.
devLinks.forEach(link => {
    link.addEventListener('click', function(event) {
        // 링크의 기본 동작(페이지 이동 등)을 막습니다.
        event.preventDefault();
        // 간단한 팝업(alert)을 띄웁니다.
        alert('해당 서비스는 현재 준비 중입니다.');
    });
});
