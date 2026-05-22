$(document).ready(function() {
    
    let isSending = false;
    
    // Функция показа ошибки
    function showError(message) {
        $('#error-container')
            .html('<div class="alert alert-danger">' + message + '</div>')
            .removeClass('d-none');
        $('#success-container').addClass('d-none').empty();
    }
    
    // Функция показа успеха
    function showSuccess(message) {
        $('#success-container')
            .html('<div class="alert alert-success">' + message + '</div>')
            .removeClass('d-none');
        $('#error-container').addClass('d-none').empty();
    }
    
    // ==================== ВХОД ПО ПАРОЛЮ ====================
    $('#auth-form').on('submit', function(e) {
        e.preventDefault();
        
        if (isSending) return;
        isSending = true;
        
        $('#auth-button').prop('disabled', true).text('Загрузка...');
        $('#error-container').addClass('d-none').empty();
        $('#success-container').addClass('d-none').empty();
        
        $.ajax({
            url: '/auth/',
            type: 'POST',
            data: $(this).serialize(),
            dataType: 'json',
            success: function(response) {
                isSending = false;
                $('#auth-button').prop('disabled', false).text('Войти');
                
                console.log('Auth response:', response);
                
                if (response.status === 'success') {
                    window.location.href = response.redirect || '/';
                } else if (response.status === 'code_required') {
                    // Перенаправляем на страницу ввода кода
                    window.location.href = '/confirm-login/';
                } else {
                    showError(response.message || 'Ошибка входа');
                }
            },
            error: function(xhr) {
                isSending = false;
                $('#auth-button').prop('disabled', false).text('Войти');
                
                let message = 'Ошибка входа';
                try {
                    const response = JSON.parse(xhr.responseText);
                    if (response.message) message = response.message;
                } catch(e) {}
                
                showError(message);
            }
        });
    });
    
    // ==================== ПЕРЕКЛЮЧЕНИЕ НА ВХОД ПО КОДУ ====================
    $('#code-login-btn').on('click', function(e) {
        e.preventDefault();
        console.log('Switching to code login form');
        $('#password-form').addClass('d-none');
        $('#code-form-container').removeClass('d-none');
        $('#error-container').addClass('d-none').empty();
        $('#success-container').addClass('d-none').empty();
    });
    
    // ==================== ВОЗВРАТ К ВХОДУ ПО ПАРОЛЮ ====================
    $('#back-to-password-btn').on('click', function(e) {
        e.preventDefault();
        console.log('Switching back to password form');
        $('#code-form-container').addClass('d-none');
        $('#password-form').removeClass('d-none');
        $('#error-container').addClass('d-none').empty();
        $('#success-container').addClass('d-none').empty();
    });
    
    // ==================== ОТПРАВКА ЗАПРОСА НА ВХОД ПО КОДУ ====================
    $('#code-login-form').on('submit', function(e) {
        e.preventDefault();
        
        if (isSending) return;
        isSending = true;
        
        $('#code-send-button').prop('disabled', true).text('Отправка...');
        $('#error-container').addClass('d-none').empty();
        $('#success-container').addClass('d-none').empty();
        
        console.log('Sending code login request...');
        
        $.ajax({
            url: '/auth/',
            type: 'POST',
            data: $(this).serialize(),
            dataType: 'json',
            success: function(response) {
                isSending = false;
                $('#code-send-button').prop('disabled', false).text('Отправить код');
                
                console.log('Code login response:', response);
                
                if (response.status === 'code_sent') {
                    // Перенаправляем на страницу ввода кода
                    window.location.href = '/confirm-login/';
                } else {
                    showError(response.message || 'Ошибка отправки кода');
                }
            },
            error: function(xhr) {
                isSending = false;
                $('#code-send-button').prop('disabled', false).text('Отправить код');
                
                let message = 'Ошибка отправки кода';
                try {
                    const response = JSON.parse(xhr.responseText);
                    if (response.message) message = response.message;
                } catch(e) {}
                
                showError(message);
            }
        });
    });
    
});