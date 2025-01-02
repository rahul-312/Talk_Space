import re
from rest_framework import serializers
from django.core.exceptions import ValidationError
from .models import User
from rest_framework_simplejwt.tokens import RefreshToken

class UserRegistrationSerializer(serializers.ModelSerializer):
    password = serializers.CharField(write_only=True)

    class Meta:
        model = User
        fields = ['email', 'phone_number', 'first_name', 'last_name', 'gender', 'password']

    def validate_phone_number(self, value):
        if not re.match(r'^\+91\d{10}$', value):
            raise ValidationError("Phone number must start with +91 followed by 10 digits.")
        return value

    def validate_email(self, value):
        if not value.endswith('@gmail.com'):
            raise ValidationError("Email must be a Gmail address.")
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
            first_name=validated_data['first_name'],
            last_name=validated_data['last_name'],
            gender=validated_data['gender'],
            password=validated_data['password']
        )
        return user


class UserLoginSerializer(serializers.Serializer):
    email = serializers.EmailField(required=False)
    phone_number = serializers.CharField(max_length=15, required=False)
    password = serializers.CharField(write_only=True)

    def validate(self, data):
        if not data.get('email') and not data.get('phone_number'):
            raise serializers.ValidationError("Email or phone number is required.")

        user = None
        if data.get('email'):
            user = User.objects.filter(email=data['email']).first()
        elif data.get('phone_number'):
            user = User.objects.filter(phone_number=data['phone_number']).first()

        if user is None or not user.check_password(data['password']):
            raise serializers.ValidationError("Invalid credentials.")

        return user

    def get_tokens_for_user(self, user):
        refresh = RefreshToken.for_user(user)
        return {
            'access': str(refresh.access_token),
            'refresh': str(refresh)
        }