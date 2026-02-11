$('#auth-button').click(function (e) {
    e.preventDefault(); // ❗ чтобы форма не отправлялась обычным способом

    let email = $('#email').val();
    let password = $('#password').val();
    let csrf = $('[name=csrfmiddlewaretoken]').val();

    // берём next из URL (например /auth/?next=/chat/)
    let nextUrl = new URLSearchParams(window.location.search).get("next");

    if (!email) {
        alert('Введите адрес почты');
        return;
    }

    if (!password) {
        alert('Введите пароль');
        return;
    }

    $.ajax({
        url: '/auth/',
        type: 'POST',
        dataType: 'json',
        data: {
            'email': email,
            'password': password,
            'next': nextUrl, // ✅ отправляем next на сервер
            'csrfmiddlewaretoken': csrf
        },
        success: function (data) {
            if (data.status === 'success') {
                // ✅ если сервер вернул next — идём туда
                if (data.next) {
                    window.location.href = data.next;
                } else if (nextUrl) {
                    window.location.href = nextUrl;
                } else {
                    window.location.href = '/';
                }
            } else {
                alert(data.message || 'Ошибка входа');
            }
        },
        error: function () {
            alert('Ошибка входа. Проверь логин/пароль или регистрацию.');
        }
    });
});
