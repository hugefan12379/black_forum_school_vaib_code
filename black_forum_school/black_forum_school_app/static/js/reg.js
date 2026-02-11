$('#reg-button').click(function (e) {
    e.preventDefault(); // чтобы форма не отправлялась обычным способом

    let email = $('#email').val().trim();
    let password = $('#password').val();
    let confirmPassword = $('#confirm_password').val(); // <-- важно
    let firstName = $('#first-name').val().trim();
    let lastName = $('#last-name').val().trim();
    let csrf = $('[name=csrfmiddlewaretoken]').val();

    if (!email) {
        alert('Введите адрес почты');
        return;
    }

    if (!password) {
        alert('Введите пароль');
        return;
    }

    if (!confirmPassword) {
        alert('Подтвердите пароль');
        return;
    }

    if (password !== confirmPassword) {
        alert('Пароли не совпадают');
        return;
    }

    $.ajax({
        url: '/reg/',
        type: 'POST',
        dataType: 'json',
        data: {
            'email': email,
            'password': password,
            'confirm_password': confirmPassword, // <-- важно
            'first_name': firstName,
            'last_name': lastName,
            'csrfmiddlewaretoken': csrf
        },
        success: function (data) {
            if (data.status === 'success') {
                // после регистрации кидаем на авторизацию
                window.location.href = '/auth/';
            } else {
                alert(data.message || 'Ошибка регистрации');
            }
        },
        error: function () {
            alert('Ошибка сервера. Попробуйте позже');
        }
    });
});
