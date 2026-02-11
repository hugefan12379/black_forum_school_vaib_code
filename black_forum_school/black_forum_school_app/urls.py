from django.urls import path, include
from . import views

urlpatterns = [
    path('', views.index, name='index'),
    path('auth/', views.auth, name='auth'),
    path('reg/', views.reg, name='reg'),
    path('question/', views.question, name='question'),
    path('images/', views.images, name='images'),
    path('logout/', views.logout_view, name='logout'),

    path('chat/', views.chat_page, name='chat'),
    path('chat/send/', views.chat_send, name='chat_send'),
    path("chat/delete/<int:msg_id>/", views.chat_delete, name="chat_delete"),

    path("mafia/", include("mafia_app.urls")),

    # 👇 ФОРУМ
    path("forum/", views.forum_home, name="forum_list"),  # ← ВАЖНО
    path("forum/create/", views.forum_create_post, name="forum_create_post"),
    path("forum/post/<int:post_id>/", views.forum_post_detail, name="forum_post_detail"),
    path("forum/", views.forum_home, name="forum_home"),
    path("forum/post/<int:post_id>/delete/", views.forum_delete_post, name="forum_delete_post"),
    path("forum/post/<int:post_id>/like/", views.forum_like, name="forum_like"),
path("forum/post/<int:post_id>/dislike/", views.forum_dislike, name="forum_dislike"),

]
