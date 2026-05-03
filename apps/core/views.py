from rest_framework import generics, permissions, status
from rest_framework.response import Response
from .models import Notification, Report
from .serializers import NotificationSerializer, ReportSerializer

class NotificationListView(generics.ListAPIView):
    serializer_class = NotificationSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        return Notification.objects.filter(recipient=self.request.user)

class NotificationReadView(generics.UpdateAPIView):
    serializer_class = NotificationSerializer
    permission_classes = [permissions.IsAuthenticated]
    queryset = Notification.objects.all()

    def update(self, request, *args, **kwargs):
        instance = self.get_object()
        if instance.recipient != request.user:
            return Response(status=status.HTTP_403_FORBIDDEN)
        instance.read_status = True
        instance.save()
        return Response({"status": "notification marked as read"})

class ReportCreateView(generics.CreateAPIView):
    serializer_class = ReportSerializer
    permission_classes = [permissions.IsAuthenticated]

    def perform_create(self, serializer):
        serializer.save(reporter=self.request.user)
