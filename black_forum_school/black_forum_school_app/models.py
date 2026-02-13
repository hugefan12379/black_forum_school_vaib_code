from django.db import models
from django.contrib.auth.models import User  # Этот импорт уже должен быть в начале файла
from django.utils import timezone
from datetime import timedelta


# =========================
# ТЕМЫ (Topics)
# =========================
class Topic(models.Model):
    name = models.CharField(max_length=200, verbose_name="Название")
    slug = models.SlugField(unique=True, verbose_name="URL")
    description = models.TextField(blank=True, verbose_name="Описание")
    color = models.CharField(
        max_length=20, 
        default="primary", 
        verbose_name="Цвет",
        help_text="Bootstrap цвет: primary, success, danger, warning, info"
    )
    icon = models.CharField(
        max_length=50, 
        blank=True, 
        verbose_name="Иконка",
        help_text="Класс иконки (например, bi-game, bi-book)"
    )
    created_at = models.DateTimeField(auto_now_add=True, verbose_name="Дата создания")
    
    class Meta:
        verbose_name = "Тема"
        verbose_name_plural = "Темы"
        ordering = ['name']
    
    def __str__(self):
        return self.name


# =========================
# ЧАТ
# =========================
class ChatMessage(models.Model):
    author = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name="chat_messages"
    )
    text = models.TextField(blank=True)
    image = models.ImageField(
        upload_to="chat_images/",
        blank=True,
        null=True
    )
    file = models.FileField(
        upload_to="chat_files/",
        blank=True,
        null=True
    )
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.author.username}: {self.text[:30]}"


# =========================
# ФОРУМ — ПОСТ
# =========================
class ForumPost(models.Model):
    author = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name="forum_posts"
    )

    title = models.CharField(max_length=200)
    description = models.TextField(max_length=500)
    content = models.TextField()

    # ManyToMany поле для множественного выбора тем
    topics = models.ManyToManyField(
        Topic,
        blank=True,
        related_name="forum_posts",
        verbose_name="Темы"
    )

    image = models.ImageField(
        upload_to="forum_images/",
        null=True,
        blank=True
    )

    created_at = models.DateTimeField(auto_now_add=True)

    is_visible = models.BooleanField(default=True)
    is_checked = models.BooleanField(default=False)

    @staticmethod
    def can_user_post(user):
        last_post = ForumPost.objects.filter(
            author=user
        ).order_by("-created_at").first()

        if not last_post:
            return True

        return timezone.now() - last_post.created_at >= timedelta(hours=24)

    def __str__(self):
        return self.title
    
    def get_topics_list(self):
        """Возвращает список тем для шаблона"""
        return self.topics.all()


# =========================
# ФОРУМ — КОММЕНТАРИЙ
# =========================
class ForumComment(models.Model):
    post = models.ForeignKey(
        ForumPost,
        on_delete=models.CASCADE,
        related_name="comments"
    )
    author = models.ForeignKey(
        User,
        on_delete=models.CASCADE
    )
    text = models.TextField()
    created_at = models.DateTimeField(auto_now_add=True)
    
    def __str__(self):
        return f"Комментарий от {self.author}"


# =========================
# СТАТЬИ
# =========================
class Article(models.Model):
    author = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name="articles"
    )
    title = models.CharField(max_length=24)
    description = models.TextField(max_length=3500)
    image = models.ImageField(
        upload_to="articles/",
        blank=True,
        null=True
    )
    
    # ManyToMany поле для множественного выбора тем
    topics = models.ManyToManyField(
        Topic,
        blank=True,
        related_name="articles",
        verbose_name="Темы"
    )
    
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        verbose_name = "Статья"
        verbose_name_plural = "Статьи"
        ordering = ['-created_at']
    
    def __str__(self):
        return self.title
    
    def get_topics_list(self):
        """Возвращает список тем для шаблона"""
        return self.topics.all()


# =========================
# ВОПРОСЫ (ДОБАВЛЕНО)
# =========================
class Question(models.Model):
    author = models.ForeignKey(
        User, 
        on_delete=models.CASCADE, 
        related_name='questions',
        verbose_name="Автор"
    )
    text = models.TextField(verbose_name="Текст вопроса")
    is_answered = models.BooleanField(
        default=False, 
        verbose_name="Есть ответ"
    )
    is_visible = models.BooleanField(
        default=False, 
        verbose_name="Виден на сайте",
        help_text="Только после модерации"
    )
    created_at = models.DateTimeField(
        auto_now_add=True,
        verbose_name="Дата создания"
    )

    class Meta:
        verbose_name = "Вопрос"
        verbose_name_plural = "Вопросы"
        ordering = ['-created_at']  # Сначала новые вопросы

    def __str__(self):
        return f"Вопрос от {self.author.username}: {self.text[:50]}"