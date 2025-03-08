import re
from rest_framework import serializers
from django.core.exceptions import ValidationError
from .models import User, FriendRequest, ChatMessage, ChatRoom
from rest_framework_simplejwt.tokens import RefreshToken
from django.db.models import Q
from django.core.validators import validate_email
from django.core.validators import FileExtensionValidator

PASSWORD_REGEX = r'^(?=.*[A-Za-z])(?=.*\d)(?=.*[!@#$%^&*()_+={}\[\]:;"\'<>,.?/\\|`~]).{8,}$'
class UserRegistrationSerializer(serializers.ModelSerializer):
    password = serializers.CharField(write_only=True)
    confirm_password = serializers.CharField(write_only=True)
    profile_picture = serializers.ImageField(required=False, allow_null=True)

    class Meta:
        model = User
        fields = [
            'email',
            'phone_number',
            'username',
            'first_name',
            'last_name',
            'gender',
            'profile_picture',
            'password',
            'confirm_password'
        ]

    def validate_phone_number(self, value):
        """Validate phone number format and uniqueness."""
        if value:
            if not re.match(r'^\+\d{1,4}\d{7,15}$', value):
                raise ValidationError("Phone number must start with a country code followed by 7-15 digits.")
            if User.objects.filter(phone_number=value).exists():
                raise ValidationError("Phone number is already registered.")
        return value

    def validate_email(self, value):
        """Ensure email is valid and unique."""
        if value:
            try:
                validate_email(value)
            except ValidationError:
                raise ValidationError("Enter a valid email address.")
            if User.objects.filter(email=value).exists():
                raise ValidationError("Email is already registered.")
        return value

    def validate_username(self, value):
        """Ensure username is unique if provided."""
        if value:
            if User.objects.filter(username=value).exists():
                raise ValidationError("Username is already taken.")
            if len(value) < 3:
                raise ValidationError("Username must be at least 3 characters long.")
        return value

    def validate_password(self, value):
        """Ensure password meets security requirements."""
        if not re.match(PASSWORD_REGEX, value):
            raise ValidationError(
                "Password must be at least 8 characters long, contain at least one letter, one number, and one special character."
            )
        return value

    def validate(self, data):
        """Check if password matches and at least one contact method is provided."""
        if data.get('password') != data.get('confirm_password'):
            raise ValidationError({"confirm_password": "Passwords do not match."})
        
        # Ensure at least email or phone_number is provided (consistent with UserManager)
        if not data.get('email') and not data.get('phone_number'):
            raise ValidationError("Either an email or phone number must be provided.")
        
        return data

    def create(self, validated_data):
        """Create and return a new user."""
        validated_data.pop('confirm_password', None)
        user = User.objects.create_user(
            email=validated_data.get('email'),
            phone_number=validated_data.get('phone_number'),
            username=validated_data.get('username'),
            first_name=validated_data['first_name'],
            last_name=validated_data['last_name'],
            gender=validated_data['gender'],
            password=validated_data['password'],
            profile_picture=validated_data.get('profile_picture')
        )
        return user


class UserLoginSerializer(serializers.Serializer):
    email = serializers.EmailField(required=False)
    phone_number = serializers.CharField(max_length=15, required=False)
    username = serializers.CharField(max_length=150, required=False)
    password = serializers.CharField(write_only=True)

    def validate(self, data):
        # Ensure at least one identifier is provided.
        if not data.get('email') and not data.get('phone_number') and not data.get('username'):
            raise serializers.ValidationError("Email, phone number, or username is required.")

        # Identify the user
        user = None
        if data.get('email'):
            user = User.objects.filter(email=data['email']).first()
        elif data.get('phone_number'):
            user = User.objects.filter(phone_number=data['phone_number']).first()
        elif data.get('username'):
            user = User.objects.filter(username=data['username']).first()

        if user is None:
            raise serializers.ValidationError("No user found with the provided credentials.")

        # Check if password is correct
        if not user.check_password(data['password']):
            raise serializers.ValidationError("Invalid password.")

        # Return user object if authentication is successful
        return user

    def get_tokens_for_user(self, user):
        """
        Generates refresh and access tokens for the authenticated user.
        """
        refresh = RefreshToken.for_user(user)
        return {
            'access': str(refresh.access_token),
            'refresh': str(refresh)
        }

class UserSerializer(serializers.ModelSerializer):
    profile_picture = serializers.ImageField(
        required=False, 
        allow_null=True, 
        validators=[FileExtensionValidator(allowed_extensions=['jpg', 'jpeg', 'png'])]
    )

    class Meta:
        model = User
        fields = [
            "email",
            "phone_number",
            "username",
            "first_name",
            "last_name",
            "gender",
            "profile_picture",
        ]
        read_only_fields = ["email", "gender"]

class UserListSerializer(serializers.ModelSerializer):
    class Meta:
        model = User
        fields = ['email', 'phone_number', 'username', 'first_name', 'last_name', 'gender',"profile_picture"]
    
class FriendRequestSerializer(serializers.ModelSerializer):
    receiver = serializers.CharField()

    class Meta:
        model = FriendRequest
        fields = ['id', 'receiver', 'status', 'created_at']
        read_only_fields = ['id', 'status', 'created_at']

    def validate_receiver(self, value):
        try:
            return User.objects.get(username=value)
        except User.DoesNotExist:
            raise serializers.ValidationError("User with this username does not exist.")

    def validate(self, data):
        sender = self.context['request'].user
        receiver = data['receiver']

        if sender == receiver:
            raise serializers.ValidationError("You cannot send a friend request to yourself.")

        # Check if a pending friend request already exists
        if FriendRequest.objects.filter(sender=sender, receiver=receiver, status='pending').exists():
            raise serializers.ValidationError("Friend request already sent and is pending.")

        # Check if you are already friends (i.e., an accepted friend request exists)
        if FriendRequest.objects.filter(
            Q(sender=sender, receiver=receiver, status='accepted') |
            Q(sender=receiver, receiver=sender, status='accepted')
        ).exists():
            raise serializers.ValidationError("You are already friends with this user.")

        return data

    def create(self, validated_data):
        return FriendRequest.objects.create(
            sender=self.context['request'].user,
            receiver=validated_data['receiver']
        )
    
class ChatRoomSerializer(serializers.ModelSerializer):
    users = UserListSerializer(many=True)
    class Meta:
        model = ChatRoom
        fields = ['id', 'name', 'users', 'is_group_chat', 'created_at']

class ChatMessageSerializer(serializers.ModelSerializer):
    first_name = serializers.SerializerMethodField()
    last_name = serializers.SerializerMethodField()
    profile_picture = serializers.SerializerMethodField()

    class Meta:
        model = ChatMessage
        fields = [
            'id', 'room', 'user', 'message', 'timestamp', 'is_read',
            'first_name', 'last_name', 'profile_picture'
        ]

    def get_first_name(self, obj):
        return obj.user.first_name

    def get_last_name(self, obj):
        return obj.user.last_name

    def get_profile_picture(self, obj):
        if obj.user.profile_picture:
            return obj.user.profile_picture.url
        return None

    
class FriendSerializer(serializers.ModelSerializer):
    class Meta:
        model = User
        fields = ['id', 'username', 'first_name', 'last_name', 'email',"profile_picture"]