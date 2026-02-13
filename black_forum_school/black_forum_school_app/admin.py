from django.contrib import admin
from .models import Topic, ChatMessage, ForumPost, ForumComment, Article

@admin.register(Topic)
class TopicAdmin(admin.ModelAdmin):
    list_display = ['name', 'slug', 'color', 'icon', 'created_at']
    list_filter = ['created_at', 'color']
    search_fields = ['name', 'description']
    prepopulated_fields = {'slug': ('name',)}
    list_editable = ['color', 'icon']  # Можно редактировать прямо в списке

@admin.register(ForumPost)
class ForumPostAdmin(admin.ModelAdmin):
    list_display = ['title', 'author', 'created_at', 'is_visible', 'topic_list']
    list_filter = ['is_visible', 'created_at', 'topics']
    search_fields = ['title', 'content', 'author__username']
    filter_horizontal = ['topics']  # Удобный виджет для выбора тем
    actions = ['make_visible', 'make_invisible']
    
    def topic_list(self, obj):
        return ", ".join([t.name for t in obj.topics.all()])
    topic_list.short_description = "Темы"
    
    def make_visible(self, request, queryset):
        queryset.update(is_visible=True)
    make_visible.short_description = "Сделать видимыми"
    
    def make_invisible(self, request, queryset):
        queryset.update(is_visible=False)
    make_invisible.short_description = "Скрыть"

@admin.register(Article)
class ArticleAdmin(admin.ModelAdmin):
    list_display = ['title', 'author', 'created_at', 'topic_list']
    list_filter = ['created_at', 'topics']
    search_fields = ['title', 'description', 'author__username']
    filter_horizontal = ['topics']  # Удобный виджет для выбора тем
    
    def topic_list(self, obj):
        return ", ".join([t.name for t in obj.topics.all()])
    topic_list.short_description = "Темы"

@admin.register(ForumComment)
class ForumCommentAdmin(admin.ModelAdmin):
    list_display = ['author', 'post', 'created_at', 'text_preview']
    list_filter = ['created_at']
    search_fields = ['text', 'author__username']
    
    def text_preview(self, obj):
        return obj.text[:50] + "..." if len(obj.text) > 50 else obj.text
    text_preview.short_description = "Текст"

@admin.register(ChatMessage)
class ChatMessageAdmin(admin.ModelAdmin):
    list_display = ['author', 'created_at', 'text_preview', 'has_image', 'has_file']
    list_filter = ['created_at']
    search_fields = ['text', 'author__username']
    
    def text_preview(self, obj):
        return obj.text[:50] + "..." if len(obj.text) > 50 else obj.text
    text_preview.short_description = "Текст"
    
    def has_image(self, obj):
        return bool(obj.image)
    has_image.boolean = True
    has_image.short_description = "Изображение"
    
    def has_file(self, obj):
        return bool(obj.file)
    has_file.boolean = True
    has_file.short_description = "Файл"