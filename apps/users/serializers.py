from rest_framework import serializers
from django.contrib.auth import get_user_model
from .models import OTPVerification

User = get_user_model()

from rest_framework_simplejwt.serializers import TokenObtainPairSerializer
from rest_framework import exceptions

from django.utils import timezone
from datetime import timedelta
from .models import OTPVerification
import random

class CustomTokenObtainPairSerializer(TokenObtainPairSerializer):
    username_field = 'email'
    email = serializers.CharField()

    def validate(self, attrs):
        try:
            data = super().validate(attrs)
        except exceptions.AuthenticationFailed as e:
            print(f"!!! Authentication Failed during super().validate: {e} !!!")
            raise e
        
        # After super().validate, self.user should be set if authentication was successful
        if self.user:
            print(f"--- User authenticated: {self.user.email}. is_verified: {self.user.is_verified}, is_banned: {self.user.is_banned} ---")

        if not self.user.is_verified:
            # Generate new OTP for the user since they tried to log in
            OTPVerification.objects.filter(user=self.user).delete()
            otp_code = str(random.randint(100000, 999999))
            expires_at = timezone.now() + timedelta(minutes=10)
            OTPVerification.objects.create(
                user=self.user,
                otp_code=otp_code,
                expires_at=expires_at
            )
            print(f"!!! Login failed: User is unverified. New OTP for {self.user.email} is {otp_code} !!!")
            
            # The custom exception handler looks for 'detail' string by default to assign to 'message'
            # To allow frontend detection, we return a specific phrase.
            raise exceptions.AuthenticationFailed(
                'ACCOUNT_NOT_VERIFIED',
                code='not_verified'
            )

        if self.user.is_banned:
            reason = self.user.ban_reason or 'No reason provided.'
            print(f"!!! Login failed: User {self.user.email} is banned. Reason: {reason} !!!")
            raise exceptions.AuthenticationFailed(
                f'Your account has been banned. Reason: {reason}',
                code='account_banned'
            )
        
        print(f"--- Login successful for user: {self.user.email} ---")
        return data

class UserRegistrationSerializer(serializers.ModelSerializer):
    password = serializers.CharField(write_only=True)

    class Meta:
        model = User
        fields = ['email', 'password', 'phone_number']

class UserRegistrationSerializer(serializers.ModelSerializer):
    password = serializers.CharField(write_only=True)
    email = serializers.EmailField()
    phone_number = serializers.CharField(required=False, allow_blank=True, allow_null=True)

    class Meta:
        model = User
        fields = ['email', 'password', 'phone_number']

    def validate_email(self, value):
        user = User.objects.filter(email=value).first()
        if user and user.is_verified:
            raise serializers.ValidationError("user with this email address already exists.")
        return value

    def validate_phone_number(self, value):
        if value:
            user = User.objects.filter(phone_number=value).first()
            if user and user.is_verified:
                raise serializers.ValidationError("user with this phone number already exists.")
        return value

    def create(self, validated_data):
        email = validated_data['email']
        phone_number = validated_data.get('phone_number')
        
        # If an unverified user exists with this email or phone, delete them so they can restart registration cleanly
        existing_user = User.objects.filter(email=email, is_verified=False).first()
        if not existing_user and phone_number:
            existing_user = User.objects.filter(phone_number=phone_number, is_verified=False).first()
            
        if existing_user:
            existing_user.delete()
            
        base_username = email.split('@')[0]
        username = base_username
        
        # Ensure username is unique
        counter = 1
        while User.objects.filter(username=username).exists():
            username = f"{base_username}{counter}"
            counter += 1
            
        user = User.objects.create_user(
            username=username,
            email=email,
            password=validated_data['password'],
            phone_number=phone_number,
            is_verified=False  # Block login until verified
        )
        return user

class OTPVerifySerializer(serializers.Serializer):
    email = serializers.CharField() # accept email, username, or phone
    otp_code = serializers.CharField(max_length=6)

class UserProfileSerializer(serializers.ModelSerializer):
    class Meta:
        model = User
        fields = ['username', 'phone_number', 'email']
        read_only_fields = ['email'] # Usually email shouldn't be changed through simple profile update without verification

class ForgotPasswordRequestSerializer(serializers.Serializer):
    email = serializers.EmailField()

    def validate_email(self, value):
        if not User.objects.filter(email=value).exists():
            raise serializers.ValidationError("Account with this email does not exist.")
        return value

class ForgotPasswordResetSerializer(serializers.Serializer):
    email = serializers.EmailField()
    otp_code = serializers.CharField(max_length=6)
    new_password = serializers.CharField(write_only=True, min_length=6)
