
from django.shortcuts import render, redirect, get_object_or_404
from django.http import JsonResponse, HttpResponse
from django.contrib.auth import (
    login,
    logout,
    authenticate,
    update_session_auth_hash
)
from django.contrib.auth.models import User
from django.contrib.auth.decorators import login_required
from django.views.decorators.http import require_POST
from django.views.decorators.csrf import csrf_exempt

from django.core.mail import send_mail
from django.core.validators import validate_email
from django.core.exceptions import (
    ValidationError,
    ObjectDoesNotExist
)

from django.template.loader import render_to_string
from django.contrib import messages
from django.utils import timezone
from django.conf import settings

from datetime import timedelta

from .models import (
    EmailDigest,
    EmailCode,
    Profile,
    ChatMessage,
    ForumPost,
    ForumComment,
    Topic,
    Question
)

import random
import string
import threading


# =========================
# NudeNet
# =========================
try:
    from nudenet import NudeDetector
    detector = NudeDetector()
except Exception:
    detector = None


TEXT_TTL_DAYS = 14
IMAGE_TTL_DAYS = 14
FILE_TTL_DAYS = 7
NSFW_THRESHOLD = 0.25


# =========================
# ВСПОМОГАТЕЛЬНОЕ
# =========================
def generate_code():

    return ''.join(
        random.choices(
            string.ascii_uppercase + string.digits,
            k=4
        )
    )


def send_email_code_async(email, code):

    send_mail(
        'Black Forum: код подтверждения',
        f'Ваш код подтверждения: {code}',
        settings.EMAIL_HOST_USER,
        [email],
        fail_silently=False,
    )


def cleanup_old_chat_messages():

    now = timezone.now()

    ChatMessage.objects.filter(
        created_at__lt=now - timedelta(days=TEXT_TTL_DAYS),
        image__isnull=True,
        file__isnull=True
    ).delete()

    ChatMessage.objects.filter(
        created_at__lt=now - timedelta(days=IMAGE_TTL_DAYS),
        image__isnull=False
    ).delete()

    ChatMessage.objects.filter(
        created_at__lt=now - timedelta(days=FILE_TTL_DAYS),
        file__isnull=False
    ).delete()


def is_image_nsfw(uploaded_file) -> bool:

    if detector is None:
        return False

    try:

        import tempfile

        uploaded_file.seek(0)

        data = uploaded_file.read()

        uploaded_file.seek(0)

        suffix = (
            ".jpg"
            if not uploaded_file.name.lower().endswith(".png")
            else ".png"
        )

        with tempfile.NamedTemporaryFile(
            delete=False,
            suffix=suffix
        ) as tmp:

            tmp.write(data)

            path = tmp.name

        detections = detector.detect(path)

        BAD_CLASSES = {
            "FEMALE_BREAST_EXPOSED",
            "FEMALE_GENITALIA_EXPOSED",
            "MALE_GENITALIA_EXPOSED",
            "BUTTOCKS_EXPOSED",
            "ANUS_EXPOSED",
        }

        return any(
            d.get("class") in BAD_CLASSES
            and d.get("score", 0) >= NSFW_THRESHOLD
            for d in detections
        )

    except Exception:
        return False


# =========================
# ОСНОВНЫЕ СТРАНИЦЫ
# =========================
def index(request):

    return render(request, "index.html")


def auth(request):

    if request.method == "POST":

        email = request.POST.get("email")

        password = request.POST.get("password")

        user = authenticate(
            request,
            username=email,
            password=password,
        )

        if not user:

            return JsonResponse({
                "status": "error",
                "message": "Неверные данные"
            })

        profile, created = Profile.objects.get_or_create(
            user=user
        )

        if profile.two_factor_enabled:

            code = generate_code()

            EmailCode.objects.create(
                user=user,
                code=code
            )

            threading.Thread(
                target=send_email_code_async,
                args=(user.email, code)
            ).start()

            request.session[
                "pending_login_user_id"
            ] = user.id

            return JsonResponse({
                "status": "confirm_required",
                "redirect": "/confirm-login/"
            })

        login(request, user)

        return JsonResponse({
            "status": "success",
            "redirect": "/"
        })

    return render(request, "auth.html")


def reg(request):

    if request.method == "POST":

        email = request.POST.get("email")

        password = request.POST.get("password")

        confirm = request.POST.get(
            "confirm_password"
        )

        first_name = request.POST.get(
            "first_name",
            ""
        )

        last_name = request.POST.get(
            "last_name",
            ""
        )

        if password != confirm:

            return JsonResponse({
                "status": "error",
                "message": "Пароли не совпадают"
            })

        if User.objects.filter(
            username=email
        ).exists():

            return JsonResponse({
                "status": "error",
                "message": "Пользователь уже существует"
            })

        try:

            validate_email(email)

        except ValidationError:

            return JsonResponse({
                "status": "error",
                "message": "Неверная почта"
            })

        user = User.objects.create_user(
            username=email,
            email=email,
            password=password,
            first_name=first_name,
            last_name=last_name,
            is_active=False
        )

        Profile.objects.get_or_create(
            user=user
        )

        code = generate_code()

        EmailCode.objects.create(
            user=user,
            code=code
        )

        threading.Thread(
            target=send_email_code_async,
            args=(email, code)
        ).start()

        request.session[
            'pending_user_id'
        ] = user.id

        return JsonResponse({
            "status": "confirm_required",
            "redirect": "/confirm/"
        })

    return render(request, "reg.html")


def confirm(request):

    if request.method == 'POST':

        code = request.POST.get(
            'email-code'
        )

        user_id = request.session.get(
            'pending_user_id'
        )

        if not user_id:

            return JsonResponse({
                'status': 'error',
                'message': 'Сессия истекла'
            })

        try:

            user = User.objects.get(
                id=user_id
            )

            email_code = EmailCode.objects.filter(
                user=user
            ).last()

            if not email_code:

                return JsonResponse({
                    'status': 'error',
                    'message': 'Код не найден'
                })

            if email_code.code != code:

                return JsonResponse({
                    'status': 'error',
                    'message': 'Неверный код'
                })

            if email_code.is_expired():

                email_code.delete()

                return JsonResponse({
                    'status': 'error',
                    'message': 'Код истёк'
                })

            user.is_active = True

            user.save()

            email_code.delete()

            login(request, user)

            del request.session[
                'pending_user_id'
            ]

            return JsonResponse({
                'status': 'success',
                'redirect': '/'
            })

        except ObjectDoesNotExist:

            return JsonResponse({
                'status': 'error',
                'message': 'Ошибка подтверждения'
            })

    return render(request, 'confirm.html')


def confirm_login(request):

    if request.method == 'POST':

        code = request.POST.get(
            'email-code'
        )

        user_id = request.session.get(
            'pending_login_user_id'
        )

        if not user_id:

            return JsonResponse({
                'status': 'error',
                'message': 'Сессия истекла'
            })

        try:

            user = User.objects.get(
                id=user_id
            )

            email_code = EmailCode.objects.filter(
                user=user
            ).last()

            if not email_code:

                return JsonResponse({
                    'status': 'error',
                    'message': 'Код не найден'
                })

            if email_code.code != code:

                return JsonResponse({
                    'status': 'error',
                    'message': 'Неверный код'
                })

            if email_code.is_expired():

                email_code.delete()

                return JsonResponse({
                    'status': 'error',
                    'message': 'Код истёк'
                })

            email_code.delete()

            login(request, user)

            del request.session[
                'pending_login_user_id'
            ]

            return JsonResponse({
                'status': 'success',
                'redirect': '/'
            })

        except ObjectDoesNotExist:

            return JsonResponse({
                'status': 'error',
                'message': 'Ошибка подтверждения'
            })

    return render(request, 'confirm.html')


def email(request):

    if request.method == 'POST':

        if request.POST.get('email'):

            try:

                email = request.POST.get('email')

                validate_email(email)

            except ValidationError:

                return JsonResponse({
                    'status': 'error',
                    'message': 'Неправильная почта'
                })

            send_mail(
                "Полезная рассылка",
                "Вы подписались на рассылку.",
                settings.EMAIL_HOST_USER,
                [email],
                fail_silently=False,
            )

            EmailDigest.objects.create(
                email=email
            )

            return JsonResponse({
                'status': 'success',
                'message': 'Отправлено'
            })

    return JsonResponse({
        'status': 'error'
    })


def logout_view(request):

    logout(request)

    return redirect("index")


# =========================
# ЧАТ
# =========================
@login_required
def chat_page(request):

    cleanup_old_chat_messages()

    messages_qs = ChatMessage.objects.order_by(
        "created_at"
    )[:200]

    return render(
        request,
        "chat.html",
        {
            "messages": messages_qs
        }
    )


@login_required
@require_POST
def chat_send(request):

    cleanup_old_chat_messages()

    text = (
        request.POST.get("text") or ""
    ).strip()

    upload = request.FILES.get("upload")

    image = None

    file = None

    if upload:

        if upload.content_type.startswith(
            "image/"
        ):

            if is_image_nsfw(upload):

                return JsonResponse({
                    "status": "error",
                    "message": "18+ запрещено"
                })

            image = upload

        else:

            file = upload

    if not text and not image and not file:

        return JsonResponse({
            "status": "error",
            "message": "Пустое сообщение"
        })

    msg = ChatMessage.objects.create(
        author=request.user,
        text=text,
        image=image,
        file=file,
    )

    message_html = render_to_string(
        "message_partial.html",
        {
            "m": msg,
            "user": request.user,
        }
    )

    return JsonResponse({
        "status": "success",
        "message_html": message_html,
    })


@login_required
@require_POST
def chat_delete(request, msg_id):

    msg = get_object_or_404(
        ChatMessage,
        id=msg_id
    )

    if (
        msg.author != request.user
        and not request.user.is_staff
    ):

        return JsonResponse({
            "status": "error"
        })

    msg.delete()

    return JsonResponse({
        "status": "success"
    })


# =========================
# ФОРУМ
# =========================
@login_required
def forum_home(request):

    selected_topic = request.GET.get(
        'topic'
    )

    selected_topic_id = request.GET.get(
        'topic_id'
    )

    posts = ForumPost.objects.filter(
        is_visible=True
    )

    if selected_topic:

        posts = posts.filter(
            topics__slug=selected_topic
        )

    elif selected_topic_id:

        posts = posts.filter(
            topics__id=selected_topic_id
        )

    posts = posts.order_by(
        "-created_at"
    )

    topics_with_posts = Topic.objects.filter(
        forum_posts__is_visible=True
    ).distinct()

    for topic in topics_with_posts:

        topic.post_count = ForumPost.objects.filter(
            is_visible=True,
            topics=topic
        ).count()

    messages_list = messages.get_messages(
        request
    )

    return render(
        request,
        "forum/home.html",
        {
            "posts": posts,
            "topics": topics_with_posts,
            "selected_topic":
                selected_topic or selected_topic_id,
            "messages": messages_list
        }
    )


@login_required
def forum_create_post(request):

    now = timezone.now()

    last_24h = now - timedelta(hours=24)

    posts_last_24h = ForumPost.objects.filter(
        author=request.user,
        created_at__gte=last_24h
    ).order_by("-created_at")

    limit = 100 if request.user.is_staff else 1

    if posts_last_24h.count() >= limit:

        last_post_time = posts_last_24h.first().created_at

        reset_at = last_post_time + timedelta(
            hours=24
        )

        seconds_left = int(
            (reset_at - now).total_seconds()
        )

        messages.error(
            request,
            f"Лимит постов. Ждите {seconds_left} сек."
        )

        return redirect("forum_home")

    if request.method == "POST":

        title = request.POST.get("title")

        text_content = request.POST.get(
            "text"
        )

        image = request.FILES.get("image")

        topic_ids = request.POST.getlist(
            "topics"
        )

        if not title or not text_content:

            messages.error(
                request,
                "Заполните поля"
            )

            return redirect(
                "forum_create_post"
            )

        post = ForumPost.objects.create(
            author=request.user,
            title=title,
            description=text_content,
            content=text_content,
            image=image,
            is_visible=True,
            is_checked=True,
        )

        if topic_ids:

            post.topics.set(topic_ids)

        messages.success(
            request,
            "Пост создан"
        )

        return redirect("forum_home")

    topics = Topic.objects.all()

    return render(
        request,
        "forum/create_post.html",
        {
            "topics": topics
        }
    )


@login_required
def forum_post_detail(request, post_id):

    post = get_object_or_404(
        ForumPost,
        id=post_id,
        is_visible=True
    )

    comments = post.comments.order_by(
        "created_at"
    )

    if request.method == "POST":

        text = request.POST.get("text")

        if text:

            ForumComment.objects.create(
                post=post,
                author=request.user,
                text=text
            )

        return redirect(
            "forum_post_detail",
            post_id=post.id
        )

    return render(
        request,
        "forum/post_detail.html",
        {
            "post": post,
            "comments": comments
        }
    )


# =========================
# ПРОСТЫЕ СТРАНИЦЫ
# =========================
def question(request):

    return render(
        request,
        "question.html"
    )


def images(request):

    return render(
        request,
        "images.html"
    )


def questions(request):

    return render(
        request,
        "questions.html"
    )


@login_required
def questions_view(request):

    if request.method == 'POST':

        question_text = request.POST.get(
            'question_text'
        )

        if (
            question_text
            and question_text.strip()
        ):

            Question.objects.create(
                author=request.user,
                text=question_text.strip()
            )

            return redirect('questions')

    questions = Question.objects.all()

    return render(
        request,
        'questions.html',
        {
            'questions': questions
        }
    )


@login_required
def account(request):

    profile, created = Profile.objects.get_or_create(
        user=request.user
    )

    if request.method == "POST":

        profile.two_factor_enabled = (
            request.POST.get("two_factor")
            == "on"
        )

        profile.save()

        messages.success(
            request,
            "Настройки сохранены"
        )

        return redirect("account")

    context = {

        'username': request.user.username,
        'first_name': request.user.first_name,
        'last_name': request.user.last_name,
        'email': request.user.email,
        'profile': profile,
    }

    return render(
        request,
        'account.html',
        context
    )


def rules(request):

    return render(
        request,
        "rules.html"
    )

