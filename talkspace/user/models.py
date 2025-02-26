from django.db import models
from django.contrib.auth.models import AbstractBaseUser, BaseUserManager, PermissionsMixin

class UserManager(BaseUserManager):
    def create_user(self, email=None, phone_number=None, password=None, **extra_fields):
        if not email and not phone_number:
            raise ValueError('Users must have either an email or a phone number.')

        email = self.normalize_email(email) if email else None
        user = self.model(email=email, phone_number=phone_number, **extra_fields)
        if password:
            user.set_password(password)
        user.save(using=self._db)
        return user

    def create_superuser(self, email, password=None, **extra_fields):
        extra_fields.setdefault('is_staff', True)
        extra_fields.setdefault('is_superuser', True)

        if extra_fields.get('is_staff') is not True:
            raise ValueError('Superuser must have is_staff=True.')
        if extra_fields.get('is_superuser') is not True:
            raise ValueError('Superuser must have is_superuser=True.')

        return self.create_user(email=email, password=password, **extra_fields)

class Gender(models.TextChoices):
    MALE = "MALE", 'Male'
    FEMALE = "FEMALE", 'Female'
    OTHER = "OTHER", 'Other'

class User(AbstractBaseUser, PermissionsMixin):
    email = models.EmailField(unique=True, null=True, blank=True)
    phone_number = models.CharField(max_length=15, unique=True, null=True, blank=True)
    username = models.CharField(max_length=150, unique=True, null=True, blank=True)
    first_name = models.CharField(max_length=30)
    last_name = models.CharField(max_length=30)
    gender = models.CharField(max_length=10, choices=Gender.choices)
    is_active = models.BooleanField(default=True)
    is_staff = models.BooleanField(default=False)
    date_joined = models.DateTimeField(auto_now_add=True)

    USERNAME_FIELD = 'email'
    REQUIRED_FIELDS = ['username', 'first_name', 'last_name']

    objects = UserManager()

    groups = models.ManyToManyField(
        'auth.Group',
        related_name='custom_user_set',
        blank=True
    )
    user_permissions = models.ManyToManyField(
        'auth.Permission',
        related_name='custom_user_permissions_set',
        blank=True
    )

    class Meta:
        db_table = 'user'
    
    def get_friends(self):
        """Retrieve friends of the user."""
        sent_friends = FriendRequest.objects.filter(sender=self, status='accepted').values_list('receiver', flat=True)
        received_friends = FriendRequest.objects.filter(receiver=self, status='accepted').values_list('sender', flat=True)
        friend_ids = list(sent_friends) + list(received_friends)
        return User.objects.filter(id__in=friend_ids)

    def __str__(self):
        return self.email if self.email else self.phone_number

class FriendRequest(models.Model):
    sender = models.ForeignKey(User, on_delete=models.CASCADE, related_name='sent_requests')
    receiver = models.ForeignKey(User, on_delete=models.CASCADE, related_name='received_requests')
    status = models.CharField(
        max_length=10,
        choices=[('pending', 'Pending'), ('accepted', 'Accepted'), ('rejected', 'Rejected')],
        default='pending'
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ('sender', 'receiver')

class ChatRoom(models.Model):
    name = models.CharField(max_length=255, unique=True, blank=True)
    users = models.ManyToManyField(User, related_name='chatrooms')
    is_deleted = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    is_group_chat = models.BooleanField(default=False)

    def __str__(self):
        return self.name or "Unnamed Room"

    def save(self, *args, **kwargs):
        is_new = self._state.adding
        super().save(*args, **kwargs)
        if is_new and not self.name:
            user_ids = list(self.users.values_list('id', flat=True))
            if len(user_ids) == 2 and not self.is_group_chat:
                user_ids.sort()
                self.name = f"dm_{user_ids[0]}_{user_ids[1]}"
            else:
                self.name = f"room_{self.id}"
            super().save(*args, **kwargs)

    @classmethod
    def get_or_create_dm(cls, user1, user2):
        user_ids = sorted([user1.id, user2.id])
        room_name = f"dm_{user_ids[0]}_{user_ids[1]}"
        room, created = cls.objects.get_or_create(
            name=room_name,
            defaults={'is_group_chat': False}
        )
        if created:
            room.users.set([user1, user2])
        return room

class ChatMessage(models.Model):
    room = models.ForeignKey(ChatRoom, related_name='messages', on_delete=models.CASCADE)
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    message = models.TextField()
    timestamp = models.DateTimeField(auto_now_add=True)
    is_read = models.BooleanField(default=False)

    def __str__(self):
        return f"Message by {self.user} in {self.room.name}"

    class Meta:
        ordering = ['timestamp']