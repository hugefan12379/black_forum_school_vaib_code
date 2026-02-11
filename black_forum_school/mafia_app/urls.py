from django.urls import path
from . import views

urlpatterns = [
    path("", views.mafia_rooms, name="mafia_rooms"),
    path("room/<int:room_number>/", views.mafia_room, name="mafia_room"),

    path("room/<int:room_number>/join/", views.room_join, name="room_join"),
    path("room/<int:room_number>/leave/", views.room_leave, name="room_leave"),
    path("room/<int:room_number>/become-host/", views.room_become_host, name="room_become_host"),

    path("room/<int:room_number>/start/", views.room_start_game, name="room_start_game"),
    path("room/<int:room_number>/reset/", views.room_reset_game, name="room_reset_game"),

    path("room/<int:room_number>/state/", views.room_state, name="room_state"),
    path("room/<int:room_number>/chat/list/", views.room_chat_list, name="room_chat_list"),
    path("room/<int:room_number>/chat/send/", views.room_chat_send, name="room_chat_send"),

    path("room/<int:room_number>/phase/set/", views.room_set_phase, name="room_set_phase"),

    path("room/<int:room_number>/action/choose/", views.room_choose_action, name="room_choose_action"),

    path("room/<int:room_number>/vote-change-host/start/", views.vote_change_host_start, name="vote_change_host_start"),
    path("room/<int:room_number>/vote-change-host/yesno/", views.vote_change_host_yesno, name="vote_change_host_yesno"),
    path("room/<int:room_number>/vote-change-host/pick/", views.vote_change_host_pick, name="vote_change_host_pick"),
    path("room/<int:room_number>/action/", views.room_action, name="room_action"),
    
    
    path("room/<int:room_number>/day-vote/start/", views.day_vote_start, name="day_vote_start"),
    path("room/<int:room_number>/day-vote/cast/", views.day_vote_cast, name="day_vote_cast"),
    
    path("room/<int:room_number>/ping/", views.room_ping, name="room_ping"),
    path("", views.mafia_rooms, name="mafia_rooms"),
    path("room/<int:room_number>/", views.mafia_room, name="mafia_room"),
]
