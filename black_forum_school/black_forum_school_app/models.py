from django.db import models
from django.contrib.auth.models import User
from django.utils import timezone
from datetime import timedelta


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
    content = models.TextField()  # тут сохраняются абзацы

    image = models.ImageField(
        upload_to="forum_images/",
        null=True,
        blank=True
    )

    created_at = models.DateTimeField(auto_now_add=True)

    is_visible = models.BooleanField(default=True)
    is_checked = models.BooleanField(default=False)  # NudeNet проверил

    def can_user_post(user):
        last_post = ForumPost.objects.filter(
            author=user
        ).order_by("-created_at").first()

        if not last_post:
            return True

        return timezone.now() - last_post.created_at >= timedelta(hours=24)

    def __str__(self):
        return self.title


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
# СТАТЬИ (Article)
# =========================
class Article(models.Model):
    author = models.ForeignKey(
        User,
        on_delete=models.CASCADE
    )
    title = models.CharField(max_length=200)
    description = models.TextField()
    image = models.ImageField(
        upload_to="articles/",
        blank=True,
        null=True
    )
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return self.title
