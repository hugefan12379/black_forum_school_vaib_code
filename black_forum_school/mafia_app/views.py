import random

from django.shortcuts import render, get_object_or_404
from django.http import JsonResponse
from django.contrib.auth.decorators import login_required
from django.views.decorators.http import require_POST
from django.utils import timezone

from .models import MafiaChatMessage, MafiaNightAction

from .models import MafiaRoom, MafiaPlayer
from django.utils import timezone
from datetime import timedelta
from django.utils import timezone
from datetime import timedelta
import random
from django.views.decorators.http import require_POST
from django.http import JsonResponse
from django.shortcuts import get_object_or_404
from django.db import models
from .models import MafiaDayVote

def _get_or_create_rooms():
    for i in [1, 2, 3]:
        MafiaRoom.objects.get_or_create(room_number=i)


def _build_roles_for_room(room_number: int, total_players: int):
    """
    Всегда должно быть:
    - 1 ведущий (host)  (назначается отдельно)
    - 1 доктор
    - 1 шериф
    - 1 мафия
    - минимум 2 мирных

    Добавки:
    от 8: +1 мафия, +красотка(босс) (только в комнате 3)
    от 10: +маньяк (только в комнате 3)
    от 15: +1 мафия
    от 19: +1 мафия +1 шериф
    """

    roles = []

    # базовый набор (кроме ведущего)
    roles += ["doctor", "sheriff", "mafia"]
    roles += ["civil", "civil"]  # минимум 2 мирных

    if total_players >= 8:
        roles += ["mafia"]
        if room_number == 3:
            roles += ["boss"]  # красотка (босс мафии)

    if total_players >= 10:
        if room_number == 3:
            roles += ["maniac"]

    if total_players >= 15:
        roles += ["mafia"]

    if total_players >= 19:
        roles += ["mafia", "sheriff"]

    # добиваем мирными до total_players-1 (ведущий отдельно)
    while len(roles) < (total_players - 1):
        roles.append("civil")

    roles = roles[: (total_players - 1)]
    random.shuffle(roles)
    return roles


# =========================
# PAGES
# =========================

@login_required
def mafia_rooms(request):
    _get_or_create_rooms()
    rooms = MafiaRoom.objects.order_by("room_number")
    return render(request, "mafia/rooms.html", {"rooms": rooms})


@login_required
def mafia_room(request, room_number: int):
    _get_or_create_rooms()

    room = get_object_or_404(MafiaRoom, room_number=room_number)
    players = MafiaPlayer.objects.filter(room=room).select_related("user").order_by("joined_at")
    me = MafiaPlayer.objects.filter(room=room, user=request.user).first()

    return render(request, "mafia/room.html", {
        "room": room,
        "players": players,
        "me": me,
    })


# =========================
# ACTIONS
# =========================

@login_required
@require_POST
def room_join(request, room_number: int):
    room = get_object_or_404(MafiaRoom, room_number=room_number)

    if room.game_started:
        return JsonResponse({"status": "error", "message": "Игра уже началась. Жди следующую."})

    if MafiaPlayer.objects.filter(room=room).count() >= 20:
        return JsonResponse({"status": "error", "message": "Комната заполнена (20/20)"})

    MafiaPlayer.objects.get_or_create(room=room, user=request.user)
    return JsonResponse({"status": "success"})


@login_required
@require_POST
def room_leave(request, room_number: int):
    room = get_object_or_404(MafiaRoom, room_number=room_number)

    if room.game_started:
        return JsonResponse({"status": "error", "message": "Нельзя выйти после старта игры"})

    me = MafiaPlayer.objects.filter(room=room, user=request.user).first()
    if not me:
        return JsonResponse({"status": "success"})

    # если уходил ведущий — снимаем ведущего
    if room.host_id == request.user.id:
        room.host = None
        room.save(update_fields=["host"])

    me.delete()
    return JsonResponse({"status": "success"})


@login_required
@require_POST
def room_become_host(request, room_number: int):
    room = get_object_or_404(MafiaRoom, room_number=room_number)

    if room.game_started:
        return JsonResponse({"status": "error", "message": "Игра уже началась"})

    me = MafiaPlayer.objects.filter(room=room, user=request.user).first()
    if not me:
        return JsonResponse({"status": "error", "message": "Сначала войди в комнату"})

    if room.host_id and room.host_id != request.user.id:
        return JsonResponse({"status": "error", "message": "Ведущий уже выбран"})

    room.host = request.user
    room.save(update_fields=["host"])

    # всем сбросить роли
    MafiaPlayer.objects.filter(room=room).update(is_host=False, role="civil")

    me.is_host = True
    me.role = "host"
    me.save(update_fields=["is_host", "role"])

    return JsonResponse({"status": "success"})


@login_required
@require_POST
def room_start_game(request, room_number: int):
    room = get_object_or_404(MafiaRoom, room_number=room_number)

    if room.host_id != request.user.id:
        return JsonResponse({"status": "error", "message": "Только ведущий может начать игру"})

    if room.game_started:
        return JsonResponse({"status": "error", "message": "Игра уже началась"})

    players = list(MafiaPlayer.objects.filter(room=room).select_related("user").order_by("joined_at"))

    if len(players) < 5:
        return JsonResponse({"status": "error", "message": "Нужно минимум 5 игроков"})

    host_player = next((p for p in players if p.user_id == room.host_id), None)
    if not host_player:
        return JsonResponse({"status": "error", "message": "Ведущий не в комнате"})

    others = [p for p in players if p.user_id != room.host_id]
    roles = _build_roles_for_room(room.room_number, total_players=len(players))

    for p, role in zip(others, roles):
        p.role = role
        p.is_alive = True
        p.is_host = False
        p.save(update_fields=["role", "is_alive", "is_host"])

    host_player.role = "host"
    host_player.is_host = True
    host_player.is_alive = True
    host_player.save(update_fields=["role", "is_host", "is_alive"])

    room.game_started = True
    room.phase = "night"
    room.night_number = 1
    room.day_number = 0
    room.save(update_fields=["game_started", "phase", "night_number", "day_number"])

    return JsonResponse({"status": "success"})


@login_required
@require_POST
def room_reset_game(request, room_number: int):
    room = get_object_or_404(MafiaRoom, room_number=room_number)

    if room.host_id != request.user.id:
        return JsonResponse({"status": "error", "message": "Только ведущий может сбросить игру"})

    room.game_started = False
    room.phase = "lobby"
    room.day_number = 0
    room.night_number = 0
    room.save(update_fields=["game_started", "phase", "day_number", "night_number"])

    MafiaPlayer.objects.filter(room=room).update(role="civil", is_alive=True, is_host=False)

    # ведущего вернуть
    host_player = MafiaPlayer.objects.filter(room=room, user_id=room.host_id).first()
    if host_player:
        host_player.role = "host"
        host_player.is_host = True
        host_player.save(update_fields=["role", "is_host"])

    return JsonResponse({"status": "success"})


from django.utils import timezone

from django.http import JsonResponse
from django.shortcuts import get_object_or_404
from django.contrib.auth.decorators import login_required
from django.db.models import Count

@login_required
def room_state(request, room_number: int):
    room = get_object_or_404(MafiaRoom, room_number=room_number)

    _kick_inactive_players(room)

    # 1) авто-действие ночи (таймер 30 сек)
    _auto_action_if_needed(room)

    # 2) голосования смены ведущего (таймер 15 сек)
    _process_votes_if_needed(room)

    # 3) дневное голосование
    _process_day_vote_if_needed(room)

    # 4) победа
    _check_win_condition(room)

    room.refresh_from_db()

    players = MafiaPlayer.objects.filter(room=room).select_related("user").order_by("joined_at")

    data_players = []
    for p in players:
        first = (p.user.first_name or "").strip()
        last = (p.user.last_name or "").strip()

        display_name = first if first else p.user.username
        full_name = (first + " " + last).strip() if (first or last) else p.user.username

        role_for_user = None

        # игрок видит свою роль
        if request.user.id == p.user_id:
            role_for_user = p.role

        # ведущий видит все роли
        if room.host_id == request.user.id:
            role_for_user = p.role

        data_players.append({
            "id": p.user.id,
            "name": display_name,
            "full_name": full_name,
            "is_host": (room.host_id == p.user.id),
            "is_alive": p.is_alive,
            "role": role_for_user,
        })

    # ---------------------------
    # ДНЕВНЫЕ ГОЛОСА (подсчёт)
    # ---------------------------
    day_votes = {}
    my_day_vote_target_id = None

    if room.day_vote_deadline:
        votes_qs = MafiaDayVote.objects.filter(room=room, day_number=room.day_number)

        # подсчёт голосов по target_id
        counts = votes_qs.values("target_id").annotate(c=Count("id"))
        for x in counts:
            if x["target_id"] is not None:
                day_votes[str(x["target_id"])] = x["c"]

        # за кого проголосовал я
        my_vote = votes_qs.filter(voter=request.user).first()
        if my_vote:
            my_day_vote_target_id = my_vote.target_id

    return JsonResponse({
        "status": "success",
        "room": room.room_number,
        "phase": room.phase,
        "game_started": room.game_started,
        "day_number": room.day_number,
        "night_number": room.night_number,
        "host_id": room.host_id,
        "players": data_players,
        "count": len(data_players),

        "vote_stage": room.vote_stage,
        "vote_deadline": room.vote_deadline.isoformat() if room.vote_deadline else None,

        "turn_role": room.turn_role,
        "action_deadline": room.action_deadline.isoformat() if room.action_deadline else None,

        "day_vote_deadline": room.day_vote_deadline.isoformat() if room.day_vote_deadline else None,

        "winner_text": room.winner_text,

        "day_votes": day_votes,
        "my_day_vote_target_id": my_day_vote_target_id,
    })



    

@login_required
@require_POST
def room_leave(request, room_number: int):
    room = get_object_or_404(MafiaRoom, room_number=room_number)

    me = MafiaPlayer.objects.filter(room=room, user=request.user).first()
    if not me:
        return JsonResponse({"status": "success"})

    # если игра стартовала — нельзя выходить (иначе ломается)
    if room.game_started:
        return JsonResponse({"status": "error", "message": "Нельзя выйти после старта игры"})

    # если уходил ведущий — снимаем ведущего
    if room.host_id == request.user.id:
        room.host = None
        room.save(update_fields=["host"])

    me.delete()
    return JsonResponse({"status": "success"})
@login_required
def room_chat_list(request, room_number: int):
    room = get_object_or_404(MafiaRoom, room_number=room_number)

    # чат доступен только днём (как у тебя было задумано)
    if room.phase != "day":
        return JsonResponse({
            "status": "success",
            "messages": [],
            "count": 0,
        })

    messages = MafiaChatMessage.objects.filter(room=room).select_related("user").order_by("created_at")[:200]

    data = []
    for m in messages:
        first = (m.user.first_name or "").strip()
        last = (m.user.last_name or "").strip()

        display_name = first if first else m.user.username
        full_name = (first + " " + last).strip() if (first or last) else m.user.username

        data.append({
            "id": m.id,
            "user_id": m.user_id,
            "user": display_name,
            "full_name": full_name,   # <-- добавили
            "text": m.text,
            "time": m.created_at.strftime("%H:%M"),
        })

    return JsonResponse({
        "status": "success",
        "messages": data,
        "count": len(data),
    })



@login_required
@require_POST
def room_chat_send(request, room_number: int):
    room = get_object_or_404(MafiaRoom, room_number=room_number)

    me = MafiaPlayer.objects.filter(room=room, user=request.user).first()
    if not me:
        return JsonResponse({"status": "error", "message": "Сначала войди в комнату"})

    if not me.is_alive:
        return JsonResponse({"status": "error", "message": "Ты мёртв и не можешь писать"})

    if not room.game_started or room.phase != "day":
        return JsonResponse({"status": "error", "message": "Чат доступен только днём"})

    text = (request.POST.get("text") or "").strip()
    if not text:
        return JsonResponse({"status": "error", "message": "Пустое сообщение"})

    if len(text) > 500:
        return JsonResponse({"status": "error", "message": "Слишком длинно (макс 500)"})

    MafiaChatMessage.objects.create(room=room, user=request.user, text=text)
    return JsonResponse({"status": "success"})


@login_required
@require_POST
def room_set_phase(request, room_number: int):
    room = get_object_or_404(MafiaRoom, room_number=room_number)

    # только ведущий
    if room.host_id != request.user.id:
        return JsonResponse({"status": "error", "message": "Только ведущий может менять фазу"})

    if not room.game_started:
        return JsonResponse({"status": "error", "message": "Игра не началась"})

    phase = request.POST.get("phase")
    if phase not in ["day", "night"]:
        return JsonResponse({"status": "error", "message": "Неверная фаза"})

    room.phase = phase

    if phase == "day":
        room.day_number += 1
    else:
        room.night_number += 1
        # на новую ночь — чистим действия прошлой ночи (чтобы не путалось)
        MafiaNightAction.objects.filter(room=room, night_number=room.night_number).delete()

    room.save(update_fields=["phase", "day_number", "night_number"])
    return JsonResponse({"status": "success"})


@login_required
@require_POST
def room_choose_action(request, room_number: int):
    room = get_object_or_404(MafiaRoom, room_number=room_number)

    me = MafiaPlayer.objects.filter(room=room, user=request.user).first()
    if not me:
        return JsonResponse({"status": "error", "message": "Сначала войди в комнату"})

    if not me.is_alive:
        return JsonResponse({"status": "error", "message": "Ты мёртв"})

    if not room.game_started or room.phase != "night":
        return JsonResponse({"status": "error", "message": "Действия доступны только ночью"})

    target_id = request.POST.get("target_id")
    if not target_id:
        return JsonResponse({"status": "error", "message": "Не выбран игрок"})

    try:
        target_id = int(target_id)
    except:
        return JsonResponse({"status": "error", "message": "Неверный target_id"})

    target_player = MafiaPlayer.objects.filter(room=room, user_id=target_id, is_alive=True).first()
    if not target_player:
        return JsonResponse({"status": "error", "message": "Цель не найдена или мертва"})

    # определяем тип действия по роли
    action_type = None

    if me.role == "doctor":
        action_type = "heal"
    elif me.role == "sheriff":
        action_type = "check"
    elif me.role == "mafia":
        action_type = "kill"
    elif me.role == "boss":
        action_type = "block"
    elif me.role == "maniac":
        action_type = "kill"
    else:
        return JsonResponse({"status": "error", "message": "У твоей роли нет ночного действия"})

    MafiaNightAction.objects.update_or_create(
        room=room,
        night_number=room.night_number,
        actor=request.user,
        action_type=action_type,
        defaults={"target": target_player.user},
    )

    return JsonResponse({"status": "success"})


def _majority(count_alive: int):
    # большинство = больше половины
    return (count_alive // 2) + 1


def _process_votes_if_needed(room: MafiaRoom):
    """
    Проверяет таймер голосования и завершает его автоматически.
    """
    if room.vote_stage == "none":
        return

    if not room.vote_deadline:
        return

    if timezone.now() < room.vote_deadline:
        return

    players_alive = MafiaPlayer.objects.filter(room=room, is_alive=True)
    alive_count = players_alive.count()

    # 🟦 Голосование 1: "Меняем ведущего?"
    if room.vote_stage == "change_host_yesno":
        yes_votes = ChangeHostYesNoVote.objects.filter(room=room, vote="yes").count()

        if yes_votes >= _majority(alive_count):
            # запускаем этап 2
            room.vote_stage = "change_host_pick"
            room.vote_deadline = timezone.now() + timedelta(seconds=15)
            room.save(update_fields=["vote_stage", "vote_deadline"])
        else:
            # голосование не прошло
            room.vote_stage = "none"
            room.vote_deadline = None
            room.save(update_fields=["vote_stage", "vote_deadline"])

        return

    # 🟩 Голосование 2: выбор нового ведущего
    if room.vote_stage == "change_host_pick":
        # кто набрал больше голосов
        votes = ChangeHostPickVote.objects.filter(room=room).values("target_user_id").annotate(c=models.Count("id")).order_by("-c")

        if votes:
            winner_id = votes[0]["target_user_id"]
            room.host_id = winner_id
            room.save(update_fields=["host"])

            # обновим is_host/role
            MafiaPlayer.objects.filter(room=room).update(is_host=False)
            MafiaPlayer.objects.filter(room=room, user_id=winner_id).update(is_host=True, role="host")

        # заканчиваем голосование
        room.vote_stage = "none"
        room.vote_deadline = None
        room.save(update_fields=["vote_stage", "vote_deadline"])

        return
@login_required
@require_POST
def vote_change_host_start(request, room_number: int):
    room = get_object_or_404(MafiaRoom, room_number=room_number)

    me = MafiaPlayer.objects.filter(room=room, user=request.user).first()
    if not me:
        return JsonResponse({"status": "error", "message": "Ты не в комнате"})

    if not room.game_started:
        return JsonResponse({"status": "error", "message": "Игра ещё не началась"})

    if room.vote_stage != "none":
        return JsonResponse({"status": "error", "message": "Голосование уже идёт"})

    if me.used_change_host_vote:
        return JsonResponse({"status": "error", "message": "Ты уже запускал голосование в этой игре"})

    # запускаем этап 1
    room.vote_stage = "change_host_yesno"
    room.vote_deadline = timezone.now() + timedelta(seconds=15)
    room.save(update_fields=["vote_stage", "vote_deadline"])

    # отметим что игрок уже использовал право
    me.used_change_host_vote = True
    me.save(update_fields=["used_change_host_vote"])

    # очищаем старые голоса (на всякий)
    ChangeHostYesNoVote.objects.filter(room=room).delete()
    ChangeHostPickVote.objects.filter(room=room).delete()

    return JsonResponse({"status": "success"})
@login_required
@require_POST
def vote_change_host_yesno(request, room_number: int):
    room = get_object_or_404(MafiaRoom, room_number=room_number)

    if room.vote_stage != "change_host_yesno":
        return JsonResponse({"status": "error", "message": "Сейчас нет голосования этапа 1"})

    vote = request.POST.get("vote")
    if vote not in ["yes", "no"]:
        return JsonResponse({"status": "error", "message": "vote должен быть yes или no"})

    # голосуем
    ChangeHostYesNoVote.objects.update_or_create(
        room=room,
        user=request.user,
        defaults={"vote": vote}
    )

    return JsonResponse({"status": "success"})
@login_required
@require_POST
def vote_change_host_pick(request, room_number: int):
    room = get_object_or_404(MafiaRoom, room_number=room_number)

    if room.vote_stage != "change_host_pick":
        return JsonResponse({"status": "error", "message": "Сейчас нет голосования этапа 2"})

    target_id = request.POST.get("target_id")
    if not target_id:
        return JsonResponse({"status": "error", "message": "target_id обязателен"})

    # можно голосовать только за игроков комнаты
    if not MafiaPlayer.objects.filter(room=room, user_id=target_id).exists():
        return JsonResponse({"status": "error", "message": "Этот игрок не в комнате"})

    ChangeHostPickVote.objects.update_or_create(
        room=room,
        user=request.user,
        defaults={"target_user_id": target_id}
    )

    return JsonResponse({"status": "success"})


ACTION_SECONDS = 30

NIGHT_ORDER = ["boss", "doctor", "sheriff", "mafia", "maniac"]
# boss = красотка (нейтрализует)


def _start_turn(room: MafiaRoom, role: str):
    room.turn_role = role
    room.action_deadline = timezone.now() + timedelta(seconds=ACTION_SECONDS)
    room.save(update_fields=["turn_role", "action_deadline"])
    MafiaPlayer.objects.filter(room=room).update(night_done=False, night_target_id=None)
    if role == NIGHT_ORDER[0]:
        room.blocked_user_id = None
        room.save(update_fields=["blocked_user_id"])


def _auto_action_if_needed(room: MafiaRoom):
    if not room.game_started or room.phase != "night":
        return

    # если ночь началась и нет хода — стартуем с первой роли
    if not room.turn_role:
        _start_turn(room, NIGHT_ORDER[0])
        return

    # если роли НЕТ вообще (все умерли или не было) — скипаем сразу
    role = room.turn_role
    actors = MafiaPlayer.objects.filter(room=room, is_alive=True, role=role)

    if not actors.exists():
        _next_turn(room)
        return

    # если у роли все уже сделали выбор — скипаем раньше таймера
    if actors.filter(night_done=False).count() == 0:
        _next_turn(room)
        return

    # если дедлайна нет — ставим
    if not room.action_deadline:
        room.action_deadline = timezone.now() + timedelta(seconds=ACTION_SECONDS)
        room.save(update_fields=["action_deadline"])
        return

    # если время ещё не вышло — ждём
    if timezone.now() < room.action_deadline:
        return

    # время вышло → автодействие (для тех кто не выбрал)
    alive_players = list(MafiaPlayer.objects.filter(room=room, is_alive=True))
    if len(alive_players) < 2:
        return

    # берём первого кто не сделал действие
    actor = actors.filter(night_done=False).first()
    if not actor:
        _next_turn(room)
        return

    # выбираем рандомную цель (не себя если возможно)
    possible_targets = [p for p in alive_players if p.user_id != actor.user_id]
    if not possible_targets:
        possible_targets = alive_players

    target = random.choice(possible_targets)

    actor.night_target_id = target.user_id
    actor.night_done = True
    actor.save(update_fields=["night_target_id", "night_done"])

    # переключаем ход дальше
    _next_turn(room)





def _next_turn(room: MafiaRoom):
    if room.turn_role not in NIGHT_ORDER:
        _start_turn(room, NIGHT_ORDER[0])
        return

    idx = NIGHT_ORDER.index(room.turn_role)
    next_idx = idx + 1

    # дошли до конца ночи → завершаем ночь и начинаем день
    if next_idx >= len(NIGHT_ORDER):
        # применяем ночь
        _apply_night_results(room)

        # проверяем победу
        _check_win_condition(room)

        # если игра закончилась — не переводим в день
        room.refresh_from_db()
        if not room.game_started:
            return

        # начинаем день
        room.phase = "day"
        room.day_number += 1
        room.turn_role = ""
        room.action_deadline = None
        room.save(update_fields=["phase", "day_number", "turn_role", "action_deadline"])
        return


    # следующий ход
    _start_turn(room, NIGHT_ORDER[next_idx])




@login_required
@require_POST
def room_action(request, room_number: int):
    room = get_object_or_404(MafiaRoom, room_number=room_number)

    if not room.game_started or room.phase != "night":
        return JsonResponse({"status": "error", "message": "Сейчас не ночь"})

    me = MafiaPlayer.objects.filter(room=room, user=request.user).first()
    if not me or not me.is_alive:
        return JsonResponse({"status": "error", "message": "Ты не в игре или мёртв"})

    # проверка: сейчас ход твоей роли?
    if room.turn_role != me.role:
        return JsonResponse({"status": "error", "message": "Сейчас не твой ход"})

    if me.night_done:
        return JsonResponse({"status": "error", "message": "Ты уже сделал действие"})

    target_id = request.POST.get("target_id")
    if not target_id:
        return JsonResponse({"status": "error", "message": "Не выбран игрок"})

    try:
        target_id = int(target_id)
    except:
        return JsonResponse({"status": "error", "message": "Некорректный target_id"})

    target = MafiaPlayer.objects.filter(room=room, user_id=target_id, is_alive=True).first()
    if not target:
        return JsonResponse({"status": "error", "message": "Цель не найдена или мертва"})

    me.night_target_id = target.user_id
    me.night_done = True
    me.save(update_fields=["night_target_id", "night_done"])

    # НЕ переключаем ход сразу!
    # ход переключится автоматически, когда истечёт таймер (или когда все этой роли сделали выбор)
    return JsonResponse({"status": "success"})


from django.http import JsonResponse
from django.contrib.auth.decorators import login_required
from django.shortcuts import get_object_or_404

from .models import MafiaRoom, MafiaPlayer, MafiaChatMessage


@login_required
def room_reset_game(request, room_number: int):
    room = get_object_or_404(MafiaRoom, room_number=room_number)

    # только ведущий может сбрасывать
    if room.host_id != request.user.id:
        return JsonResponse({"status": "error", "message": "Только ведущий может сбросить игру"}, status=403)

    # сбрасываем состояние комнаты
    room.game_started = False
    room.phase = "lobby"
    room.day_number = 0
    room.night_number = 0
    room.turn_role = ""
    room.action_deadline = None
    room.vote_stage = "none"
    room.vote_deadline = None
    room.save()

    # сбрасываем игроков
    MafiaPlayer.objects.filter(room=room).update(
        role="civil",
        is_alive=True,
        night_target_id=None,
        night_done=False,
        is_host=False,
    )

    # ведущий остаётся ведущим (или можно убрать если хочешь)
    # отмечаем ведущего в player-таблице (если он в комнате)
    MafiaPlayer.objects.filter(room=room, user_id=room.host_id).update(is_host=True)

    # 🔥 очищаем чат
    MafiaChatMessage.objects.filter(room=room).delete()

    return JsonResponse({"status": "success"})
from django.http import JsonResponse
from django.contrib.auth.decorators import login_required
from django.shortcuts import get_object_or_404
from django.utils import timezone

from .models import MafiaRoom, MafiaPlayer, MafiaChatMessage


@login_required
def room_chat_send(request, room_number: int):
    if request.method != "POST":
        return JsonResponse({"status": "error", "message": "POST only"}, status=405)

    room = get_object_or_404(MafiaRoom, room_number=room_number)

    # должен быть в комнате
    if not MafiaPlayer.objects.filter(room=room, user=request.user).exists():
        return JsonResponse({"status": "error", "message": "Вы не в комнате"}, status=403)

    text = (request.POST.get("text") or "").strip()
    if not text:
        return JsonResponse({"status": "error", "message": "Пустое сообщение"}, status=400)

    if len(text) > 500:
        text = text[:500]

    msg = MafiaChatMessage.objects.create(
        room=room,
        user=request.user,
        text=text,
    )

    return JsonResponse({
        "status": "success",
        "id": msg.id,
        "text": msg.text,
        "created_at": msg.created_at.isoformat(),
    })



DAY_VOTE_SECONDS = 30


def _process_day_vote_if_needed(room: MafiaRoom):
    """
    Если идёт день и таймер дневного голосования вышел — считаем голоса и казним.
    """
    if not room.game_started:
        return

    if room.phase != "day":
        return

    if not room.day_vote_deadline:
        return

    if timezone.now() < room.day_vote_deadline:
        return

    # Таймер вышел — считаем голоса
    alive_players = list(MafiaPlayer.objects.filter(room=room, is_alive=True).select_related("user"))
    if len(alive_players) <= 1:
        room.day_vote_deadline = None
        room.save(update_fields=["day_vote_deadline"])
        return

    alive_ids = [p.user_id for p in alive_players]

    votes_qs = MafiaDayVote.objects.filter(room=room, day_number=room.day_number)
    votes_qs = votes_qs.filter(voter_id__in=alive_ids, target_id__in=alive_ids)

    counts = votes_qs.values("target_id").annotate(c=models.Count("id")).order_by("-c")

    if not counts:
        # никто не голосовал → казним случайного живого
        victim_id = random.choice(alive_ids)
    else:
        max_votes = counts[0]["c"]
        top = [x["target_id"] for x in counts if x["c"] == max_votes]
        victim_id = random.choice(top)

    # казним
    MafiaPlayer.objects.filter(room=room, user_id=victim_id).update(is_alive=False)


    _check_win_condition(room)
    # очищаем голоса этого дня (чтобы не мешали)
    MafiaDayVote.objects.filter(room=room, day_number=room.day_number).delete()

    # сбрасываем таймер
    room.day_vote_deadline = None
    room.save(update_fields=["day_vote_deadline"])










@login_required
@require_POST
def day_vote_start(request, room_number: int):
    room = get_object_or_404(MafiaRoom, room_number=room_number)

    if room.host_id != request.user.id:
        return JsonResponse({"status": "error", "message": "Только ведущий может запускать голосование"})

    if not room.game_started:
        return JsonResponse({"status": "error", "message": "Игра не началась"})

    if room.phase != "day":
        return JsonResponse({"status": "error", "message": "Голосование доступно только днём"})

    if room.day_vote_deadline:
        return JsonResponse({"status": "error", "message": "Голосование уже идёт"})

    # старт таймера
    room.day_vote_deadline = timezone.now() + timedelta(seconds=DAY_VOTE_SECONDS)
    room.save(update_fields=["day_vote_deadline"])

    # очищаем голоса на всякий случай
    MafiaDayVote.objects.filter(room=room, day_number=room.day_number).delete()

    return JsonResponse({"status": "success", "seconds": DAY_VOTE_SECONDS})








@login_required
@require_POST
def day_vote_cast(request, room_number: int):
    room = get_object_or_404(MafiaRoom, room_number=room_number)

    if not room.game_started:
        return JsonResponse({"status": "error", "message": "Игра не началась"})

    if room.phase != "day":
        return JsonResponse({"status": "error", "message": "Голосование только днём"})

    if not room.day_vote_deadline:
        return JsonResponse({"status": "error", "message": "Голосование ещё не запущено ведущим"})

    me = MafiaPlayer.objects.filter(room=room, user=request.user).first()
    if not me:
        return JsonResponse({"status": "error", "message": "Ты не в комнате"})

    if not me.is_alive:
        return JsonResponse({"status": "error", "message": "Ты мёртв и не можешь голосовать"})

    if room.blocked_user_id == request.user.id:
        return JsonResponse({"status": "error", "message": "Ты заблокирован красоткой и не можешь голосовать"})

    target_id = request.POST.get("target_id")
    if not target_id:
        return JsonResponse({"status": "error", "message": "Не выбран игрок"})

    try:
        target_id = int(target_id)
    except:
        return JsonResponse({"status": "error", "message": "Некорректный target_id"})

    target = MafiaPlayer.objects.filter(room=room, user_id=target_id, is_alive=True).first()
    if not target:
        return JsonResponse({"status": "error", "message": "Цель не найдена или мертва"})

    if target.user_id == request.user.id:
        return JsonResponse({"status": "error", "message": "Нельзя голосовать за себя"})

    MafiaDayVote.objects.update_or_create(
        room=room,
        day_number=room.day_number,
        voter=request.user,
        defaults={"target_id": target.user_id}
    )

    return JsonResponse({"status": "success"})







def _count_alive_by_roles(room: MafiaRoom):
    alive = MafiaPlayer.objects.filter(room=room, is_alive=True)

    mafia_count = alive.filter(role__in=["mafia", "boss"]).count()
    maniac_count = alive.filter(role="maniac").count()
    civil_count = alive.exclude(role__in=["mafia", "boss", "maniac", "host"]).count()

    # ведущий не участвует в победе
    total_alive_no_host = alive.exclude(role="host").count()

    return mafia_count, maniac_count, civil_count, total_alive_no_host


def _finish_game(room: MafiaRoom, winner_text: str):
    """
    Завершает игру, сбрасывает комнату и чистит чат.
    """
    room.game_started = False
    room.phase = "lobby"
    room.turn_role = ""
    room.action_deadline = None

    room.vote_stage = "none"
    room.vote_deadline = None

    room.day_vote_deadline = None

    room.winner_text = winner_text
    room.save()

    # сброс игроков
    MafiaPlayer.objects.filter(room=room).update(
        is_alive=True,
        night_target_id=None,
        night_done=False,
        role="civil",
        is_host=False,
        used_change_host_vote=False,
    )

    # вернуть ведущего если он есть
    if room.host_id:
        MafiaPlayer.objects.filter(room=room, user_id=room.host_id).update(
            role="host",
            is_host=True,
            is_alive=True
        )

    # чистим чат
    MafiaChatMessage.objects.filter(room=room).delete()

    # чистим голосования
    ChangeHostYesNoVote.objects.filter(room=room).delete()
    ChangeHostPickVote.objects.filter(room=room).delete()
    MafiaDayVote.objects.filter(room=room).delete()











def _check_win_condition(room: MafiaRoom):
    """
    Проверяет победу после любых смертей.
    """
    if not room.game_started:
        return

    mafia_count, maniac_count, civil_count, total_alive_no_host = _count_alive_by_roles(room)

    # если остался 1 игрок (или 0) — заканчиваем
    if total_alive_no_host <= 1:
        if mafia_count > 0:
            _finish_game(room, "🏆 Победа мафии!")
        elif maniac_count > 0:
            _finish_game(room, "🏆 Победа маньяка!")
        else:
            _finish_game(room, "🏆 Победа мирных!")
        return

    # победа мирных: мафии нет
    if mafia_count == 0 and room.game_started:
        # если есть маньяк и он жив — он ещё может победить, но по твоей логике можно дать победу мирным
        # я сделаю так: если мафии нет, но маньяк жив — игра продолжается (чтобы маньяк мог выиграть)
        if maniac_count > 0:
            return
        _finish_game(room, "🏆 Победа мирных!")
        return

    # победа мафии: мафии >= мирных (без маньяка)
    if mafia_count >= civil_count and room.game_started:
        _finish_game(room, "🏆 Победа мафии!")
        return

    # победа маньяка: он один (без ведущего)
    if maniac_count == 1 and total_alive_no_host == 1 and room.game_started:
        _finish_game(room, "🏆 Победа маньяка!")
        return









def _apply_night_results(room: MafiaRoom):
    """
    Ночь:
    - boss: блокирует выбранного игрока (он не действует ночью и не голосует днём)
    - doctor: лечит цель (если доктор заблокирован — лечения нет)
    - sheriff: проверяет цель (если шериф заблокирован — проверки нет)
      если шерифов 2 — проверяет каждый отдельно
    - mafia: голосуют за убийство (если мафия заблокирована — её голос не считается)
      если равенство голосов — убиваем случайного среди лидеров
    - maniac: убивает (если маньяк заблокирован — не убивает)
    """

    if room.phase != "night":
        return

    alive_players = list(MafiaPlayer.objects.filter(room=room, is_alive=True))

    def alive_by_role(role):
        return [p for p in alive_players if p.role == role]

    # --- boss block ---
    blocked_id = None
    bosses = alive_by_role("boss")
    if bosses:
        boss = bosses[0]
        if boss.night_done and boss.night_target_id:
            blocked_id = boss.night_target_id


    room.blocked_user_id = blocked_id
    room.save(update_fields=["blocked_user_id"])

    # --- doctor heal ---
    healed_id = None
    doctors = alive_by_role("doctor")
    if doctors:
        doctor = doctors[0]
        if doctor.user_id != blocked_id and doctor.night_done and doctor.night_target_id:
            healed_id = doctor.night_target_id

    # --- sheriff checks (если их 2) ---
    sheriffs = alive_by_role("sheriff")
    for sh in sheriffs:
        if sh.user_id == blocked_id:
            continue
        if not sh.night_done or not sh.night_target_id:
            continue

        target = MafiaPlayer.objects.filter(room=room, user_id=sh.night_target_id).first()
        if not target:
            continue

        # логика "злой/добрый"
        is_evil = target.role in ["mafia", "boss"]

        # маньяк становится "злым" для шерифа только когда мафия мертва
        mafia_alive = MafiaPlayer.objects.filter(room=room, is_alive=True, role__in=["mafia", "boss"]).exists()
        if (not mafia_alive) and target.role == "maniac":
            is_evil = True

        # пишем ведущему в чат (видно днём)
        MafiaChatMessage.objects.create(
            room=room,
            user=sh.user,
            text=f"🕵️ Проверка: {target.user.first_name or target.user.username} → {'ЗЛОЙ' if is_evil else 'ДОБРЫЙ'}"
        )

    # --- mafia voting kill ---
    mafia_members = [p for p in alive_players if p.role in ["mafia", "boss"]]
    mafia_votes = {}

    for m in mafia_members:
        # если мафия заблокирована — её голос не учитываем
        if m.user_id == blocked_id:
            continue
        if not m.night_done or not m.night_target_id:
            continue

        mafia_votes[m.night_target_id] = mafia_votes.get(m.night_target_id, 0) + 1

        # двойной голос босса
        if m.role == "boss":
            mafia_votes[m.night_target_id] += 1

    mafia_kill_target_id = None
    if mafia_votes:
        max_votes = max(mafia_votes.values())
        leaders = [uid for uid, c in mafia_votes.items() if c == max_votes]
        mafia_kill_target_id = random.choice(leaders)

    # --- maniac kill ---
    maniac_target_id = None
    maniacs = alive_by_role("maniac")
    if maniacs:
        maniac = maniacs[0]
        if maniac.user_id != blocked_id and maniac.night_done and maniac.night_target_id:
            maniac_target_id = maniac.night_target_id

    # --- apply kills ---
    kills = []
    if mafia_kill_target_id:
        kills.append(("mafia", mafia_kill_target_id))
    if maniac_target_id:
        kills.append(("maniac", maniac_target_id))

    for killer, victim_id in kills:
        # если лечили — спасён
        if healed_id and victim_id == healed_id:
            continue

        MafiaPlayer.objects.filter(room=room, user_id=victim_id).update(is_alive=False)

        victim = MafiaPlayer.objects.filter(room=room, user_id=victim_id).select_related("user").first()
        if victim:
            MafiaChatMessage.objects.create(
                room=room,
                user=victim.user,
                text=f"💀 Убит игрок: {victim.user.first_name or victim.user.username} (роль: {victim.role})"
            )



@login_required
@require_POST
def room_ping(request, room_number: int):
    room = get_object_or_404(MafiaRoom, room_number=room_number)

    me = MafiaPlayer.objects.filter(room=room, user=request.user).first()
    if not me:
        return JsonResponse({"status": "error", "message": "Ты не в комнате"})

    me.last_seen = timezone.now()
    me.save(update_fields=["last_seen"])

    return JsonResponse({"status": "success"})








def _kick_inactive_players(room: MafiaRoom):
    if room.game_started:
        return  # во время игры не кикаем

    limit = timezone.now() - timedelta(seconds=30)

    inactive = MafiaPlayer.objects.filter(room=room, last_seen__lt=limit)

    # если ведущий неактивен — снимаем ведущего
    if room.host_id and inactive.filter(user_id=room.host_id).exists():
        room.host = None
        room.save(update_fields=["host"])

    inactive.delete()





