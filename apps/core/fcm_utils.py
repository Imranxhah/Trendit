import logging
from firebase_admin import messaging
from apps.users.models import UserDevice
from django.conf import settings

logger = logging.getLogger(__name__)

def send_push_notification(user, title, body, data=None):
    """
    Sends a push notification to all active devices of a given user.
    `data` is a dictionary of custom key-value pairs (e.g., {"type": "follow", "target_id": "123"}).
    """
    if data is None:
        data = {}

    # Ensure all data values are strings (FCM requirement)
    stringified_data = {str(k): str(v) for k, v in data.items()}

    # Get all active devices for the user that have an FCM token
    devices = UserDevice.objects.filter(user=user, is_active=True).exclude(fcm_token__isnull=True).exclude(fcm_token="")
    
    if not devices.exists():
        logger.info(f"No active FCM tokens found for user {user.username}")
        return

    tokens = list(devices.values_list('fcm_token', flat=True))
    
    # We can use messaging.MulticastMessage to send to multiple tokens at once
    message = messaging.MulticastMessage(
        notification=messaging.Notification(
            title=title,
            body=body,
        ),
        data=stringified_data,
        tokens=tokens,
    )

    try:
        response = messaging.send_each_for_multicast(message)
        logger.info(f"Successfully sent {response.success_count} messages; {response.failure_count} failed.")
        
        # Optionally, remove invalid tokens if failure_count > 0
        if response.failure_count > 0:
            responses = response.responses
            failed_tokens = []
            for idx, resp in enumerate(responses):
                if not resp.success:
                    # e.g., 'messaging/invalid-registration-token' or 'messaging/registration-token-not-registered'
                    logger.warning(f"Failed to send to token {tokens[idx]}: {resp.exception}")
                    if resp.exception and resp.exception.code in ['messaging/invalid-registration-token', 'messaging/registration-token-not-registered']:
                        failed_tokens.append(tokens[idx])
                        
            if failed_tokens:
                UserDevice.objects.filter(fcm_token__in=failed_tokens).update(is_active=False)
                logger.info(f"Deactivated {len(failed_tokens)} invalid tokens.")
                
    except Exception as e:
        logger.error(f"Error sending FCM notification: {e}")
