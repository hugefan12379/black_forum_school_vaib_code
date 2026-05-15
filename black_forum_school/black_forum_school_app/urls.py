from django.urls import path, include
from . import views

urlpatterns = [
    path('', views.index, name='index'),
    path('auth/', views.auth, name='auth'),
    path('reg/', views.reg, name='reg'),
    path('question/', views.question, name='question'),
    path('images/', views.images, name='images'),
    path('logout/', views.logout_view, name='logout'),

    # ЧАТ
    path('chat/', views.chat_page, name='chat'),
    path('chat/send/', views.chat_send, name='chat_send'),
    path("chat/delete/<int:msg_id>/", views.chat_delete, name="chat_delete"),

    path("mafia/", include("mafia_app.urls")),

    # ФОРУМ
    path("forum/", views.forum_home, name="forum_home"),
    path("forum/", views.forum_home, name="forum_list"),     # ← добавили для navbar
    path("forum/create/", views.forum_create_post, name="forum_create_post"),
    path("forum/post/<int:post_id>/", views.forum_post_detail, name="forum_post_detail"),

    path("questions/", views.questions_view, name="questions"),
    path('account/', views.account, name='account'),
    path('rules/', views.rules, name='rules'),
    path('comfirm/', views.confirm, name='confirm'),
path(
    "confirm/",
    views.confirm,
    name="confirm"
),

path(
    "confirm-login/",
    views.confirm_login,
    name="confirm_login"
),


]

