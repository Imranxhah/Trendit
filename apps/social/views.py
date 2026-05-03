from rest_framework import generics, permissions, status
from rest_framework.response import Response
from rest_framework.views import APIView
from django.db.models import Q
from .models import CloseBuddy, PostApproval, Vote, BuddyRequest
from .serializers import (
    BuddyRequestSerializer, BuddyRespondSerializer, 
    CloseBuddySerializer, PostApprovalSerializer, VoteSerializer,
    UserMinimalSerializer
)
from django.contrib.auth import get_user_model

User = get_user_model()

class SendBuddyRequestView(generics.CreateAPIView):
    serializer_class = BuddyRequestSerializer
    permission_classes = [permissions.IsAuthenticated]

    def perform_create(self, serializer):
        serializer.save(sender=self.request.user)

class RespondBuddyRequestView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def post(self, request):
        serializer = BuddyRespondSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        
        request_id = serializer.validated_data['request_id']
        action = serializer.validated_data['action']
        
        try:
            buddy_req = BuddyRequest.objects.get(id=request_id, receiver=request.user, status='pending')
            buddy_req.status = action
            buddy_req.save()
            return Response({"message": f"Request {action}."}, status=status.HTTP_200_OK)
        except BuddyRequest.DoesNotExist:
            return Response({"error": "Request not found or already processed."}, status=status.HTTP_404_NOT_FOUND)

class IncomingRequestsView(generics.ListAPIView):
    serializer_class = BuddyRequestSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        return BuddyRequest.objects.filter(receiver=self.request.user, status='pending')

class BuddyListView(generics.ListAPIView):
    serializer_class = UserMinimalSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        user = self.request.user
        # Mutual buddies are those where a request was accepted (either sent or received by user)
        accepted_requests = BuddyRequest.objects.filter(
            (Q(sender=user) | Q(receiver=user)),
            status='accepted'
        )
        buddy_ids = []
        for req in accepted_requests:
            if req.sender == user:
                buddy_ids.append(req.receiver.id)
            else:
                buddy_ids.append(req.sender.id)
        return User.objects.filter(id__in=buddy_ids)

class CloseBuddyListCreateView(generics.ListCreateAPIView):
    serializer_class = CloseBuddySerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        return CloseBuddy.objects.filter(user=self.request.user)

    def perform_create(self, serializer):
        buddy = serializer.validated_data['buddy']
        user = self.request.user
        
        # Logic: Auto-create Buddy connection if adding to Close Buddy
        # We ensure a 'BuddyRequest' exists and is 'accepted'
        BuddyRequest.objects.update_or_create(
            sender=user, receiver=buddy,
            defaults={'status': 'accepted'}
        )
        # Also ensure the reverse if we want mutual (though the above covers the connection)
        
        serializer.save(user=user)

class PostApprovalCreateView(generics.CreateAPIView):
    serializer_class = PostApprovalSerializer
    permission_classes = [permissions.IsAuthenticated]

    def perform_create(self, serializer):
        # Validation: Only Close Buddies can approve (logic handled in clean or here)
        post = serializer.validated_data['post']
        if not CloseBuddy.objects.filter(user=post.author, buddy=self.request.user).exists():
            from rest_framework.exceptions import ValidationError
            raise ValidationError("Only close buddies of the author can approve this post.")
        serializer.save(buddy=self.request.user)

class VoteCreateView(generics.CreateAPIView):
    serializer_class = VoteSerializer
    permission_classes = [permissions.IsAuthenticated]

    def perform_create(self, serializer):
        serializer.save(user=self.request.user)
