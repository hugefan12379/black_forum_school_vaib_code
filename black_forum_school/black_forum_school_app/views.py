from django.shortcuts import render, redirect, get_object_or_404
from django.http import JsonResponse
from django.contrib.auth import login, logout, authenticate
from django.contrib.auth.models import User
from django.contrib.auth.decorators import login_required
from django.views.decorators.http import require_POST
from django.contrib import messages
from django.utils import timezone
from datetime import timedelta
from django.contrib import messages

from .models import ChatMessage, ForumPost, ForumComment, Topic  # Добавлен импорт Topic
from .utils.nudenet_check import check_image_safe


# =========================
# NudeNet (чат)
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
    except Exception:
        return False
#регистрация:
def index(request):
    return render(request, "index.html")

def auth(request):
    if request.method == 'POST':
        email = request.POST.get('email')
        password = request.POST.get('password')

        user = authenticate(request, username=email, password=password)
        print(user)

        if user is not None:
            login(request, user)

            # Если пользователь есть
            return JsonResponse({ 'status' : 'success'})
        else:
            # Если пользователя нету
            return JsonResponse({ 'status' : 'error' })      
    else:
        return render(request, 'auth.html')

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
    return redirect('index') # перенаправление

'''
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
'''

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
# ФОРУМ
# =========================
@login_required
def forum_home(request):
    # Получаем выбранную тему из GET параметров
    selected_topic = request.GET.get('topic')
    selected_topic_id = request.GET.get('topic_id')
    
    # Базовый запрос
    posts = ForumPost.objects.filter(is_visible=True)
    
    # Применяем фильтр по теме
    if selected_topic:
        posts = posts.filter(topics__slug=selected_topic)
    elif selected_topic_id:
        posts = posts.filter(topics__id=selected_topic_id)
    
    # Сортируем
    posts = posts.order_by("-created_at")
    
    # Получаем все темы для фильтров (только те, у которых есть посты)
    topics_with_posts = Topic.objects.filter(forum_posts__is_visible=True).distinct()
    
    # Считаем количество постов в каждой теме
    for topic in topics_with_posts:
        topic.post_count = ForumPost.objects.filter(
            is_visible=True, 
            topics=topic
        ).count()
    
    # Добавляем сообщения в контекст
    messages_list = messages.get_messages(request)
    
    return render(request, "forum/home.html", {
        "posts": posts,
        "topics": topics_with_posts,
        "selected_topic": selected_topic or selected_topic_id,
        "messages": messages_list
    })


@login_required
def forum_create_post(request):
    now = timezone.now()
    last_24h = now - timedelta(hours=24)

    posts_last_24h = ForumPost.objects.filter(
        author=request.user,
        created_at__gte=last_24h
    ).order_by("-created_at")

    if request.user.is_staff:
        limit = 100
    else:
        limit = 1

    if posts_last_24h.count() >= limit:
        last_post_time = posts_last_24h.first().created_at
        reset_at = last_post_time + timedelta(hours=24)
        seconds_left = int((reset_at - now).total_seconds())

        messages.error(
            request,
            f"Вы опубликовали максимум постов за 24 часа. "
            f"Таймер сбросится через {seconds_left} сек."
        )
        return redirect("forum_home")

    if request.method == "POST":
        title = request.POST.get("title")
        text_content = request.POST.get("text")
        image = request.FILES.get("image")
        
        # Получаем выбранные темы
        topic_ids = request.POST.getlist("topics")

        if not title or not text_content:
            messages.error(request, "Заполните все поля")
            return redirect("forum_create_post")

        # Создаем пост
        post = ForumPost.objects.create(
            author=request.user,
            title=title,
            description=text_content,
            content=text_content,
            image=image,
            is_visible=True,
            is_checked=True,
        )
        
        # Добавляем темы
        if topic_ids:
            post.topics.set(topic_ids)

        messages.success(request, "Пост успешно создан!")
        return redirect("forum_home")

    # Получаем все темы для формы создания
    topics = Topic.objects.all()
    return render(request, "forum/create_post.html", {"topics": topics})


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


# =========================
# ПРОСТЫЕ СТРАНИЦЫ
# =========================
def question(request):
    return render(request, "question.html")


def images(request):
    return render(request, "images.html")


def questions(request):
    if request.method == "POST" and request.user.is_authenticated:
        question_text = request.POST.get("question_text")
        if question_text:
            # Если создали модель Question
            # Question.objects.create(
            #     author=request.user,
            #     text=question_text,
            #     is_visible=False  # На модерации
            # )
            messages.success(request, "Ваш вопрос отправлен на модерацию!")
            return redirect("questions")
    
    # Получаем вопросы (если есть модель)
    # questions_list = Question.objects.filter(is_visible=True)
    
    return render(request, "questions.html", {
        # 'questions': questions_list
    })






from django.shortcuts import render, redirect
from django.contrib.auth.decorators import login_required
from .models import Question

@login_required
def questions_view(request):
    if request.method == 'POST':
        question_text = request.POST.get('question_text')
        if question_text and question_text.strip():
            # Создаем вопрос с привязкой к текущему пользователю
            Question.objects.create(
                author=request.user,
                text=question_text.strip()
            )
            return redirect('questions')  # Перенаправляем на ту же страницу
    
    # Получаем все вопросы для отображения
    questions = Question.objects.all()
    
    return render(request, 'questions.html', {
        'questions': questions
    })