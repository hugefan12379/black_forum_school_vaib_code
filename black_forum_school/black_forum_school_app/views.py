from django.shortcuts import render, redirect, get_object_or_404
from django.http import JsonResponse
from django.contrib.auth import login, logout, authenticate
from django.contrib.auth.models import User
from django.contrib.auth.decorators import login_required
from django.views.decorators.http import require_POST
from django.contrib import messages
from django.utils import timezone
from datetime import timedelta

from .models import ChatMessage, ForumPost, ForumComment
from .utils.nudenet_check import check_image_safe

# =========================
# NudeNet (чат)
# =========================
try:
    from nudenet import NudeDetector
    detector = NudeDetector()
    print("NudeNet: OK")
except Exception as e:
    detector = None
    print("NudeNet: OFF", e)

TEXT_TTL_DAYS = 14
IMAGE_TTL_DAYS = 14
FILE_TTL_DAYS = 7
NSFW_THRESHOLD = 0.25

# =========================
# ВСПОМОГАТЕЛЬНОЕ
# =========================
def cleanup_old_chat_messages():
    now = timezone.now()
    ChatMessage.objects.filter(created_at__lt=now - timedelta(days=TEXT_TTL_DAYS), image__isnull=True, file__isnull=True).delete()
    ChatMessage.objects.filter(created_at__lt=now - timedelta(days=IMAGE_TTL_DAYS), image__isnull=False).delete()
    ChatMessage.objects.filter(created_at__lt=now - timedelta(days=FILE_TTL_DAYS), file__isnull=False).delete()


def is_image_nsfw(uploaded_file) -> bool:
    if detector is None:
        return False

    try:
        uploaded_file.seek(0)
        data = uploaded_file.read()
        uploaded_file.seek(0)

        import tempfile
        suffix = ".jpg" if not uploaded_file.name.lower().endswith(".png") else ".png"

        with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as tmp:
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
            d.get("class") in BAD_CLASSES and d.get("score", 0) >= NSFW_THRESHOLD
            for d in detections
        )
    except:
        return False


# =========================
# ОСНОВНЫЕ СТРАНИЦЫ
# =========================
def index(request):
    return render(request, "index.html")


def auth(request):
    if request.method == "POST":
        user = authenticate(
            request,
            username=request.POST.get("email"),
            password=request.POST.get("password"),
        )
        if user:
            login(request, user)
            return JsonResponse({"status": "success", "redirect": "/"})
        return JsonResponse({"status": "error", "message": "Неверные данные"})
    return render(request, "auth.html")


def reg(request):
    if request.method == "POST":
        email = request.POST.get("email")
        password = request.POST.get("password")
        confirm = request.POST.get("confirm_password")

        if password != confirm:
            return JsonResponse({"status": "error", "message": "Пароли не совпадают"})

        if User.objects.filter(username=email).exists():
            return JsonResponse({"status": "error", "message": "Пользователь существует"})

        User.objects.create_user(username=email, email=email, password=password)
        return JsonResponse({"status": "success", "redirect": "/auth/"})

    return render(request, "reg.html")


def logout_view(request):
    logout(request)
    return redirect("index")


# =========================
# ЧАТ
# =========================
@login_required
def chat_page(request):
    cleanup_old_chat_messages()
    messages_qs = ChatMessage.objects.order_by("-created_at")[:200][::-1]
    return render(request, "chat.html", {"messages": messages_qs})


@login_required
@require_POST
def chat_send(request):
    cleanup_old_chat_messages()

    text = (request.POST.get("text") or "").strip()
    upload = request.FILES.get("upload")

    image = None
    file = None

    if upload:
        if upload.content_type.startswith("image/"):
            if is_image_nsfw(upload):
                return JsonResponse({"status": "error", "message": "18+ запрещено"})
            image = upload
        else:
            file = upload

    if not text and not image and not file:
        return JsonResponse({"status": "error", "message": "Пусто"})

    msg = ChatMessage.objects.create(
        author=request.user,
        text=text,
        image=image,
        file=file,
    )

    return JsonResponse({
        "status": "success",
        "id": msg.id,
        "author": msg.author.username,
        "text": msg.text,
        "created_at": msg.created_at.strftime("%H:%M"),
    })


@login_required
@require_POST
def chat_delete(request, msg_id):
    msg = get_object_or_404(ChatMessage, id=msg_id)
    if msg.author != request.user and not request.user.is_staff:
        return JsonResponse({"status": "error"})
    msg.delete()
    return JsonResponse({"status": "success"})


# =========================
# ФОРУМ (ЕДИНСТВЕННАЯ ВЕРСИЯ)
# =========================
@login_required
def forum_home(request):
    posts = ForumPost.objects.filter(is_visible=True).order_by("-created_at")
    return render(request, "forum/home.html", {"posts": posts})


@login_required
def forum_create_post(request):
    if not ForumPost.can_user_post(request.user):
        messages.error(request, "Можно публиковать 1 пост в 24 часа")
        return redirect("forum_home")

    if request.method == "POST":
        title = request.POST.get("title")
        description = request.POST.get("text")  # 🔥 ВОТ ОНО

        if not title or not description:
            messages.error(request, "Заполните все поля")
            return redirect("forum_create_post")

        post = ForumPost.objects.create(
            author=request.user,
            title=title,
            description=description,
            is_visible=True,
        )

        image = request.FILES.get("image")
        if image:
            if not check_image_safe(image):
                post.delete()
                messages.error(request, "Изображение запрещено")
                return redirect("forum_home")
            post.image = image
            post.save()

        return redirect("forum_home")

    return render(request, "forum/create_post.html")



@login_required
def forum_post_detail(request, post_id):
    post = get_object_or_404(ForumPost, id=post_id, is_visible=True)

    if request.method == "POST":
        ForumComment.objects.create(
            post=post,
            author=request.user,
            text=request.POST.get("text"),
        )
        return redirect("forum_post_detail", post_id=post.id)

    return render(request, "forum/post_detail.html", {"post": post})


# =========================
# ПРОСТЫЕ СТРАНИЦЫ
# =========================
def question(request):
    return render(request, "question.html")


def images(request):
    return render(request, "images.html")






from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.utils import timezone
from .models import ForumPost, ForumComment
from .utils.nudenet_check import check_image_safe
from django.contrib import messages
import os


@login_required
def forum_home(request):
    posts = ForumPost.objects.filter(is_visible=True).order_by("-created_at")
    return render(request, "forum/home.html", {"posts": posts})


@login_required
def forum_create_post(request):
    if not ForumPost.can_user_post(request.user):
        messages.error(request, "Можно публиковать только 1 статью раз в 24 часа.")
        return redirect("forum_home")

    if request.method == "POST":
        title = request.POST.get("title")
        description = request.POST.get("description")
        content = request.POST.get("content")
        image = request.FILES.get("image")

        post = ForumPost.objects.create(
            author=request.user,
            title=title,
            description=description,
            content=content,
            image=image,
            is_visible=False,
            is_checked=False,
        )

        if image:
            img_path = post.image.path
            result = check_image_safe(img_path)

            if result is None:
                post.delete()
                messages.error(request, "Файл не удалось проверить. Загрузка запрещена.")
                return redirect("forum_home")

            if result is False:
                post.delete()
                messages.error(request, "Изображение содержит недопустимый контент.")
                return redirect("forum_home")

        post.is_visible = True
        post.is_checked = True
        post.save()

        return redirect("forum_home")

    return render(request, "forum/create_post.html")









@login_required
def forum_post_detail(request, post_id):
    post = get_object_or_404(ForumPost, id=post_id, is_visible=True)

    if request.method == "POST":
        text = request.POST.get("text")
        ForumComment.objects.create(
            post=post,
            author=request.user,
            text=text
        )
        return redirect("forum_post_detail", post_id=post.id)

    return render(request, "forum/post_detail.html", {"post": post})


@login_required
@require_POST
def forum_delete_post(request, post_id):
    post = get_object_or_404(ForumPost, id=post_id)

    if request.user != post.author and not request.user.is_staff:
        return JsonResponse({"status": "error", "message": "Нет прав"})

    post.delete()
    return JsonResponse({"status": "success"})


@login_required
@require_POST
def forum_like(request, post_id):
    post = get_object_or_404(ForumPost, id=post_id)

    if request.user in post.likes.all():
        post.likes.remove(request.user)
    else:
        post.likes.add(request.user)
        post.dislikes.remove(request.user)

    return JsonResponse({
        "likes": post.likes.count(),
        "dislikes": post.dislikes.count()
    })


@login_required
@require_POST
def forum_dislike(request, post_id):
    post = get_object_or_404(ForumPost, id=post_id)

    if request.user in post.dislikes.all():
        post.dislikes.remove(request.user)
    else:
        post.dislikes.add(request.user)
        post.likes.remove(request.user)

    return JsonResponse({
        "likes": post.likes.count(),
        "dislikes": post.dislikes.count()
    })

@login_required
def forum_post_detail(request, post_id):
    post = get_object_or_404(ForumPost, id=post_id, is_visible=True)
    comments = post.comments.order_by("created_at")

    if request.method == "POST":
        text = request.POST.get("text")
        if text:
            ForumComment.objects.create(
                post=post,
                author=request.user,
                text=text
            )
        return redirect("forum_post_detail", post_id=post.id)

    return render(request, "forum/post_detail.html", {
        "post": post,
        "comments": comments
    })
