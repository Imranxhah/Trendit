from rest_framework import status, generics, permissions
from rest_framework.response import Response
from rest_framework.views import APIView
from django.utils import timezone
from datetime import timedelta
from django.shortcuts import get_object_or_404
import random
from .models import User, OTPVerification, UserViolation

from .serializers import (
    UserRegistrationSerializer, 
    OTPVerifySerializer, 
    UserProfileSerializer,
    ForgotPasswordRequestSerializer,
    ForgotPasswordResetSerializer,
    UserProfileDetailSerializer,
    GoogleLoginSerializer
)
from .utils import send_otp_email


class UserProfileView(generics.RetrieveUpdateAPIView):
    serializer_class = UserProfileSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_object(self):
        return self.request.user


class UserProfileDetailView(generics.RetrieveAPIView):
    queryset = User.objects.filter(is_active=True)
    serializer_class = UserProfileDetailSerializer
    permission_classes = [permissions.IsAuthenticated]
    lookup_field = 'id'
    lookup_url_kwarg = 'user_id'


class RegisterView(generics.CreateAPIView):
    serializer_class = UserRegistrationSerializer

    def create(self, request, *args, **kwargs):
        print("DEBUG RegisterView: create() called")
        try:
            print("DEBUG RegisterView: request.data =", request.data)
        except Exception as e:
            print("DEBUG RegisterView: Error parsing request data:", e)
        serializer = self.get_serializer(data=request.data)
        if not serializer.is_valid():
            print("Registration validation errors:", serializer.errors)
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
        user = serializer.save()
        
        # Generate 6-digit OTP
        otp_code = str(random.randint(100000, 999999))
        expires_at = timezone.now() + timedelta(minutes=10)
        
        OTPVerification.objects.create(
            user=user,
            otp_code=otp_code,
            expires_at=expires_at
        )
        
        # Print OTP to console (as requested)
        print(f"DEBUG: OTP for {user.email} is {otp_code}")
        
        # Send OTP via Email
        send_otp_email(
            email=user.email,
            username=user.username,
            otp_code=otp_code,
            purpose="register"
        )
        
        return Response({
            "message": "User registered successfully. Please verify your email with the OTP sent.",
            "email": user.email
        }, status=status.HTTP_201_CREATED)


from django.db.models import Q

class VerifyOTPView(APIView):
    def post(self, request):
        serializer = OTPVerifySerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        
        email_or_identifier = serializer.validated_data['email'] # Using the field name from serializer, but it might contain phone/username
        otp_code = serializer.validated_data['otp_code']
        
        try:
            user = User.objects.get(
                Q(email=email_or_identifier) | 
                Q(username=email_or_identifier) | 
                Q(phone_number=email_or_identifier)
            )
            otp_obj = OTPVerification.objects.filter(
                user=user, 
                otp_code=otp_code,
                expires_at__gt=timezone.now()
            ).latest('created_at')
            
            user.is_verified = True
            user.save()
            
            # Delete the OTP after successful verification
            otp_obj.delete()
            
            return Response({"message": "Account verified successfully. You can now login."}, status=status.HTTP_200_OK)
            
        except (User.DoesNotExist, OTPVerification.DoesNotExist, User.MultipleObjectsReturned):
            return Response({"error": "Invalid or expired OTP, or account not found."}, status=status.HTTP_400_BAD_REQUEST)


class ForgotPasswordRequestView(APIView):
    def post(self, request):
        serializer = ForgotPasswordRequestSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
            
        email = serializer.validated_data['email']
        user = User.objects.get(email=email)
        
        # Invalidate old OTPs for this user
        OTPVerification.objects.filter(user=user).delete()
        
        # Generate 6-digit OTP
        otp_code = str(random.randint(100000, 999999))
        expires_at = timezone.now() + timedelta(minutes=10)
        
        OTPVerification.objects.create(
            user=user,
            otp_code=otp_code,
            expires_at=expires_at
        )
        
        # Print OTP to console for debugging
        print(f"DEBUG: Password Reset OTP for {user.email} is {otp_code}")
        
        # Send OTP via Email
        send_otp_email(
            email=user.email,
            username=user.username,
            otp_code=otp_code,
            purpose="password_reset"
        )
        
        return Response({
            "message": "Password reset OTP sent to email.",
            "email": user.email
        }, status=status.HTTP_200_OK)


class ForgotPasswordResetView(APIView):
    def post(self, request):
        serializer = ForgotPasswordResetSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
            
        email = serializer.validated_data['email']
        otp_code = serializer.validated_data['otp_code']
        new_password = serializer.validated_data['new_password']
        
        try:
            user = User.objects.get(email=email)
            otp_obj = OTPVerification.objects.filter(
                user=user, 
                otp_code=otp_code,
                expires_at__gt=timezone.now()
            ).latest('created_at')
            
            # Reset the password
            user.set_password(new_password)
            user.save()
            
            # Delete the OTP after successful verification
            otp_obj.delete()
            
            return Response({"message": "Password has been reset successfully. You can now login."}, status=status.HTTP_200_OK)
            
        except (User.DoesNotExist, OTPVerification.DoesNotExist):
            return Response({"error": "Invalid or expired OTP."}, status=status.HTTP_400_BAD_REQUEST)


# ─── Admin-only Ban / Unban Views ────────────────────────────────────────────

class BanUserView(APIView):
    """
    POST /users/ban/<user_id>/
    Admin-only. Bans a user and optionally records a reason.
    Body: { "ban_reason": "optional reason text" }
    """
    permission_classes = [permissions.IsAdminUser]

    def post(self, request, user_id):
        user = get_object_or_404(User, pk=user_id)

        if user.is_superuser:
            return Response(
                {"error": "Superusers cannot be banned."},
                status=status.HTTP_403_FORBIDDEN
            )

        if user.is_banned:
            return Response(
                {"message": f"User '{user.username}' is already banned."},
                status=status.HTTP_200_OK
            )

        user.is_banned = True
        user.ban_reason = request.data.get('ban_reason', '')
        user.save(update_fields=['is_banned', 'ban_reason'])

        return Response({
            "message": f"User '{user.username}' has been banned.",
            "ban_reason": user.ban_reason or "No reason provided."
        }, status=status.HTTP_200_OK)


class UnbanUserView(APIView):
    """
    POST /users/unban/<user_id>/
    Admin-only. Removes the ban from a user.
    """
    permission_classes = [permissions.IsAdminUser]

    def post(self, request, user_id):
        user = get_object_or_404(User, pk=user_id)

        if not user.is_banned:
            return Response(
                {"message": f"User '{user.username}' is not banned."},
                status=status.HTTP_200_OK
            )

        user.is_banned = False
        user.ban_reason = None
        user.save(update_fields=['is_banned', 'ban_reason'])

        return Response({
            "message": f"User '{user.username}' has been unbanned."
        }, status=status.HTTP_200_OK)


class RecordViolationView(APIView):
    """
    POST /users/violations/
    Records a user violation/strike sent from the client application.
    Auto-bans the user if they reach 3 or more violations.
    """
    permission_classes = [permissions.IsAuthenticated]

    def post(self, request):
        user = request.user
        
        rule_broken = request.data.get('rule_broken', 'Client Rule Broken')
        description = request.data.get('description', 'A rule was broken on the client application.')

        # Record the violation
        UserViolation.objects.create(
            user=user,
            rule_broken=rule_broken,
            description=description
        )

        total_violations = user.violations.count()
        limit = 3
        remaining_violations = max(0, limit - total_violations)

        if total_violations >= limit:
            if not user.is_banned:
                user.is_banned = True
                user.ban_reason = f"Banned automatically: Exceeded violation limit ({total_violations}/{limit}). Last violation: {rule_broken}."
                user.save(update_fields=['is_banned', 'ban_reason'])
            message = f"Your account has been banned due to exceeding the maximum violation limit of {limit}."
        else:
            message = f"Violation recorded. Warning shown. You have {remaining_violations} remaining violation(s) before your account is banned."

        return Response({
            "message": message,
            "total_violations": total_violations,
            "remaining_violations": remaining_violations,
            "is_banned": user.is_banned
        }, status=status.HTTP_201_CREATED)

class GoogleLoginView(APIView):
    permission_classes = [permissions.AllowAny]

    def post(self, request):
        serializer = GoogleLoginSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        
        # The validated data from serializer will contain the tokens
        return Response(serializer.validated_data, status=status.HTTP_200_OK)


class SyncContactsView(APIView):
    """
    POST /users/sync-contacts/
    Body: { "contacts": ["+923001234567", "03001234567", ...] }
    Finds registered users matching the provided phone numbers.
    """
    permission_classes = [permissions.IsAuthenticated]

    def post(self, request):
        contacts = request.data.get('contacts', [])
        if not isinstance(contacts, list):
            return Response({"error": "contacts must be a list"}, status=status.HTTP_400_BAD_REQUEST)
            
        if not contacts:
            return Response({
                "status": "success", 
                "data": {"registered_users": []}
            }, status=status.HTTP_200_OK)

        matching_users = User.objects.filter(phone_number__in=contacts, is_active=True).exclude(id=request.user.id)
        
        data = []
        for u in matching_users:
            is_following = False
            try:
                from apps.social.models import Follow
                is_following = Follow.objects.filter(follower=request.user, following=u).exists()
            except Exception:
                pass
                
            data.append({
                "id": u.id,
                "username": u.username,
                "first_name": u.first_name,
                "last_name": u.last_name,
                "profile_picture": request.build_absolute_uri(u.profile_picture.url) if u.profile_picture else None,
                "is_following": is_following
            })
            
        return Response({
            "status": "success",
            "data": {
                "registered_users": data
            }
        }, status=status.HTTP_200_OK)


class UpdateDeviceTokenView(APIView):
    """
    POST /users/device-token/
    Body: { "device_id": "unique-device-id", "fcm_token": "token-string" }
    Updates or creates a UserDevice entry with the given FCM token.
    """
    permission_classes = [permissions.IsAuthenticated]

    def post(self, request):
        device_id = request.data.get('device_id')
        fcm_token = request.data.get('fcm_token')

        if not device_id:
            return Response({"error": "device_id is required."}, status=status.HTTP_400_BAD_REQUEST)
        if not fcm_token:
            return Response({"error": "fcm_token is required."}, status=status.HTTP_400_BAD_REQUEST)

        # Update or create the device record
        # Lookup by device_id alone (it's globally unique).
        # If a different user logs in on the same device, reassign it.
        from apps.users.models import UserDevice
        device, created = UserDevice.objects.update_or_create(
            device_id=device_id,
            defaults={'user': request.user, 'fcm_token': fcm_token, 'is_active': True}
        )

        return Response({"message": "Device token updated successfully."}, status=status.HTTP_200_OK)


class TestNotificationView(APIView):
    """
    POST /users/test-notification/
    Sends a test FCM notification to the requesting user's own device.
    Body can optionally contain { "title": "...", "body": "...", "type": "..." }
    """
    permission_classes = [permissions.IsAuthenticated]

    def post(self, request):
        from apps.core.fcm_utils import send_push_notification

        title = request.data.get('title', 'Test Notification')
        body = request.data.get('body', 'This is a test notification from the backend!')
        notif_type = request.data.get('type', 'system')

        # Send push notification to the logged-in user
        data = {
            "type": notif_type,
            "target_id": "0",
            "message": "Test successful."
        }

        try:
            send_push_notification(
                user=request.user,
                title=title,
                body=body,
                data=data,
                trigger_user=request.user
            )
            return Response({"message": "Test notification triggered successfully."}, status=status.HTTP_200_OK)
        except Exception as e:
            return Response({"error": str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

