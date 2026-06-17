import logging
import firebase_admin
from firebase_admin import messaging
from apps.users.models import UserDevice
from django.conf import settings

logger = logging.getLogger(__name__)

def send_push_notification(user, title, body, data=None, trigger_user=None):
    """
    Sends a silent data-only push notification to all active devices of a given user.
    `data` is a dictionary of custom key-value pairs (e.g., {"type": "follow", "target_id": "123"}).
    """
    # Guard: check if Firebase Admin SDK was initialized
    if not firebase_admin._apps:
        logger.error("Firebase Admin SDK is NOT initialized. Cannot send push notifications. "
                      "Check FIREBASE_CREDENTIALS in .env and ensure the file exists.")
        return

    if data is None:
        data = {}

    # Pack title and body into data so Flutter can construct the notification locally
    data['title'] = title
    data['body'] = body
    data['click_action'] = 'FLUTTER_NOTIFICATION_CLICK'
    
    if trigger_user:
        data['trigger_user_name'] = trigger_user.username
        if trigger_user.profile_picture:
            data['trigger_user_image'] = getattr(trigger_user.profile_picture, 'url', None)

    # Ensure all data values are strings (FCM requirement)
    stringified_data = {str(k): str(v) for k, v in data.items() if v is not None}

    # Get all active devices for the user that have an FCM token
    devices = UserDevice.objects.filter(user=user, is_active=True).exclude(fcm_token__isnull=True).exclude(fcm_token="")
    
    if not devices.exists():
        logger.info(f"No active FCM tokens found for user {user.username}")
        return

    tokens = list(devices.values_list('fcm_token', flat=True))
    logger.info(f"Sending FCM to {len(tokens)} device(s) for user {user.username}")
    
    # Build Android-specific config to ensure high priority delivery
    android_config = messaging.AndroidConfig(
        priority='high',
    )
    
    # We can use messaging.MulticastMessage to send to multiple tokens at once
    # Omit the `notification` argument entirely for a silent data payload.
    message = messaging.MulticastMessage(
        data=stringified_data,
        android=android_config,
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
