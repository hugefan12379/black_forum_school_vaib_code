from django.db import models
from django.conf import settings


class MafiaRoom(models.Model):
    blocked_user_id = models.IntegerField(null=True, blank=True)

        # 🏆 победитель (для отображения всем)
    winner_text = models.CharField(max_length=100, default="", blank=True)

    room_number = models.IntegerField(unique=True)

    # лимит игроков (5..20)
    max_players = models.IntegerField(default=20)

    # ведущий
    host = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="mafia_host_rooms"
    )

    # состояние игры
    game_started = models.BooleanField(default=False)

    # lobby / night / day
    phase = models.CharField(max_length=20, default="lobby")

    day_number = models.IntegerField(default=0)
    night_number = models.IntegerField(default=0)

    # этап 5: чей сейчас ход ночью (doctor/sheriff/mafia/boss/maniac)
    turn_role = models.CharField(max_length=20, default="", blank=True)

    # таймер: дедлайн на действие (ночью)
    action_deadline = models.DateTimeField(null=True, blank=True)

    # голосование за смену ведущего
    vote_stage = models.CharField(
        max_length=20,
        default="none",
        choices=[
            ("none", "none"),
            ("change_host_yesno", "change_host_yesno"),
            ("change_host_pick", "change_host_pick"),
        ]
    )
    vote_deadline = models.DateTimeField(null=True, blank=True)
        # 🗳 Этап 6.1: дневное голосование (казнь)
    day_vote_deadline = models.DateTimeField(null=True, blank=True)

    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"Room {self.room_number}"


class MafiaPlayer(models.Model):
    last_seen = models.DateTimeField(auto_now=True)
    room = models.ForeignKey(
        MafiaRoom,
        on_delete=models.CASCADE,
        related_name="players"
    )
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE
    )

    joined_at = models.DateTimeField(auto_now_add=True)

    # жив/мертв
    is_alive = models.BooleanField(default=True)

    # ведущий ли игрок
    is_host = models.BooleanField(default=False)

    # роли:
    # host, civil, doctor, sheriff, mafia, boss, maniac
    role = models.CharField(max_length=20, default="civil")

    # этап 5: ночные действия
    night_target_id = models.IntegerField(null=True, blank=True)
    night_done = models.BooleanField(default=False)

    # игрок может инициировать смену ведущего 1 раз за игру
    used_change_host_vote = models.BooleanField(default=False)

    class Meta:
        unique_together = ("room", "user")

    def __str__(self):
        return f"{self.user.username} in room {self.room.room_number}"


class MafiaChatMessage(models.Model):
    room = models.ForeignKey(MafiaRoom, on_delete=models.CASCADE, related_name="chat_messages")
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    text = models.TextField(max_length=500)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"[Room {self.room.room_number}] {self.user.username}: {self.text[:30]}"


class MafiaNightAction(models.Model):
    room = models.ForeignKey(MafiaRoom, on_delete=models.CASCADE, related_name="night_actions")
    night_number = models.IntegerField(default=1)

    actor = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="mafia_actions_actor")
    target = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="mafia_actions_target",
        null=True,
        blank=True
    )

    action_type = models.CharField(max_length=50)  # kill/heal/check/block
    created_at = models.DateTimeField(auto_now=True)

    class Meta:
        unique_together = ("room", "night_number", "actor", "action_type")

    def __str__(self):
        return f"{self.room.room_number} night {self.night_number}: {self.actor_id}->{self.target_id} ({self.action_type})"


class ChangeHostYesNoVote(models.Model):
    room = models.ForeignKey(MafiaRoom, on_delete=models.CASCADE)
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)

    vote = models.CharField(
        max_length=5,
        choices=[("yes", "yes"), ("no", "no")]
    )

    class Meta:
        unique_together = ("room", "user")


class ChangeHostPickVote(models.Model):
    room = models.ForeignKey(MafiaRoom, on_delete=models.CASCADE)
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)

    target_user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="picked_as_host_votes"
    )

    class Meta:
        unique_together = ("room", "user")



class MafiaDayVote(models.Model):
    room = models.ForeignKey(MafiaRoom, on_delete=models.CASCADE, related_name="day_votes")
    day_number = models.IntegerField(default=1)

    voter = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="mafia_day_votes_voter"
    )

    target = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="mafia_day_votes_target"
    )

    created_at = models.DateTimeField(auto_now=True)

    class Meta:
        unique_together = ("room", "day_number", "voter")

    def __str__(self):
        return f"Room {self.room.room_number} day {self.day_number}: {self.voter_id}->{self.target_id}"







        
from django.db import models
from django.contrib.auth.models import User

class Question(models.Model):
    author = models.ForeignKey(
        User, 
        on_delete=models.CASCADE, 
        verbose_name='Автор',
        related_name='questions'
    )
    text = models.TextField(verbose_name='Текст вопроса')
    created_at = models.DateTimeField(auto_now_add=True, verbose_name='Дата создания')
    is_answered = models.BooleanField(default=False, verbose_name='Отвечен')
    
    class Meta:
        verbose_name = 'Вопрос'
        verbose_name_plural = 'Вопросы'
        ordering = ['-created_at']  # Сначала новые вопросы
    
    def __str__(self):
        return f'Вопрос от {self.author.username} ({self.created_at.strftime("%d.%m.%Y")})'
    
    def author_name(self):
        """Возвращает имя автора или username, если имя не указано"""
        return self.author.first_name or self.author.username
    
    def author_email(self):
        """Возвращает email автора"""
        return self.author.email