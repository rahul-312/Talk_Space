import re
from rest_framework import serializers
from django.core.exceptions import ValidationError
from .models import User, FriendRequest, ChatMessage, ChatRoom
from rest_framework_simplejwt.tokens import RefreshToken

class UserRegistrationSerializer(serializers.ModelSerializer):
    password = serializers.CharField(write_only=True)

    class Meta:
        model = User
        fields = ['email', 'phone_number', 'username', 'first_name', 'last_name', 'gender', 'password']

    def validate_phone_number(self, value):
        if value and not re.match(r'^\+\d{1,4}\d{10}$', value):
            raise ValidationError("Phone number must start with a country code followed by 10 digits.")
        return value

    def validate_email(self, value):
        if value and not value.endswith('@gmail.com'):
            raise ValidationError("Email must be a Gmail address.")
        return value

    def validate_username(self, value):
        if value:
            if User.objects.filter(username=value).exists():
                raise ValidationError("Username is already taken.")
        return value

    def validate_password(self, value):
        if not re.match(r'^(?=.*[A-Za-z])(?=.*\d)(?=.*[!@#$%^&*()_+={}\[\]:;"\'<>,.?/\\|`~]).{8,}$', value):
            raise ValidationError(
                "Password must be at least 8 characters long, contain at least one letter, one number, and one special character."
            )
        return value

    def create(self, validated_data):
        user = User.objects.create_user(
            email=validated_data.get('email'),
            phone_number=validated_data.get('phone_number'),
            username=validated_data.get('username'),
            first_name=validated_data['first_name'],
            last_name=validated_data['last_name'],
            gender=validated_data['gender'],
            password=validated_data['password']
        )
        return user

class UserLoginSerializer(serializers.Serializer):
    email = serializers.EmailField(required=False)
    phone_number = serializers.CharField(max_length=15, required=False)
    username = serializers.CharField(max_length=150, required=False)
    password = serializers.CharField(write_only=True)

    def validate(self, data):
        if not data.get('email') and not data.get('phone_number') and not data.get('username'):
            raise serializers.ValidationError("Email, phone number, or username is required.")

        user = None
        if data.get('email'):
            user = User.objects.filter(email=data['email']).first()
        elif data.get('phone_number'):
            user = User.objects.filter(phone_number=data['phone_number']).first()
        elif data.get('username'):
            user = User.objects.filter(username=data['username']).first()

        if user is None or not user.check_password(data['password']):
            raise serializers.ValidationError("Invalid credentials.")

        return user

    def get_tokens_for_user(self, user):
        refresh = RefreshToken.for_user(user)
        return {
            'access': str(refresh.access_token),
            'refresh': str(refresh)
        }
    
class UserListSerializer(serializers.ModelSerializer):
    class Meta:
        model = User
        fields = ['email', 'phone_number', 'username', 'first_name', 'last_name', 'gender']
    
class FriendRequestSerializer(serializers.ModelSerializer):

    receiver = serializers.CharField()
    class Meta:
        model = FriendRequest
        fields = ['id', 'receiver', 'status', 'created_at']
        read_only_fields = ['id', 'status', 'created_at']
    
    def validate_receiver(self, value):

        
        try:
            receiver = User.objects.get(username=value)
        except User.DoesNotExist:
            raise serializers.ValidationError("User with the given username does not exist.")
        return receiver

    def create(self, validated_data):
        sender = self.context['request'].user
        receiver = validated_data['receiver']

        if sender == receiver:
            raise serializers.ValidationError("You cannot send a friend request to yourself.")

        if FriendRequest.objects.filter(sender=sender, receiver=receiver).exists():
            raise serializers.ValidationError("Friend request already sent.")

        if FriendRequest.objects.filter(sender=receiver, receiver=sender, status='accepted').exists():
            raise serializers.ValidationError("You are already friends.")

        return FriendRequest.objects.create(sender=sender, receiver=receiver)
    
class ChatRoomSerializer(serializers.ModelSerializer):
    class Meta:
        model = ChatRoom
        fields = ['id', 'name', 'users', 'created_at']
        read_only_fields = ['created_at']


class ChatMessageSerializer(serializers.ModelSerializer):
    class Meta:
        model = ChatMessage
        fields = ['id', 'room', 'user', 'message', 'timestamp']
        read_only_fields = ['id', 'room', 'user', 'timestamp']