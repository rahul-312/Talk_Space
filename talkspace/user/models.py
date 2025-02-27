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

        # Fallback for unnamed group chats, but only if no name was provided
        if is_new and not self.name.strip():  # Only trigger if name is actually empty
            if self.users.count() == 2 and not self.is_group_chat:
                users = list(self.users.all())
                other_user = users[1] if users[0].id == self.users.first().id else users[0]
                self.name = f"{other_user.first_name} {other_user.last_name}".strip()
            else:
                self.name = f"Room {self.id}"
            self.save(update_fields=['name'])
    @classmethod
    def get_or_create_dm(cls, user1, user2, name=None):
        """
        Create or get a direct message chat room between two users.
        Default room name is the full name of the *other user* (first + last name).
        """
        # Ensure order doesn't matter for pairing
        user1, user2 = sorted([user1, user2], key=lambda u: u.id)

        if name is None:
            # By default, show user2's full name if user1 is the current user
            other_user = user2 if user1.id == user1.id else user1
            name = f"{other_user.first_name} {other_user.last_name}".strip()
            if not name.strip():
                name = other_user.username  # Fallback to username if no names exist

        room, created = cls.objects.get_or_create(
            name=name,
            defaults={'is_group_chat': False}
        )

        if created:
            room.users.set([user1, user2])
        else:
            # Ensure users are correctly set if room already exists
            if set(room.users.all()) != {user1, user2}:
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