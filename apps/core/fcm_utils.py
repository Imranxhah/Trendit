import logging
from datetime import timedelta

import firebase_admin
from firebase_admin import messaging

from apps.users.models import UserDevice

logger = logging.getLogger(__name__)


_FCM_DATA_KEY_ALIASES = {
    # `message_type` is reserved by FCM and causes the entire message to fail.
    "message_type": "chat_message_type",
}


def _prepare_fcm_data(data):
    prepared = {}
    for key, value in (data or {}).items():
        if value is None:
            continue
        key = str(key)
        prepared[_FCM_DATA_KEY_ALIASES.get(key, key)] = str(value)
    return prepared


def send_push_notification(
    user,
    title,
    body,
    data=None,
    trigger_user=None,
    display_notification=False,
):
    """
    Sends a push notification to all active devices of a given user.
    Chat messages use an OS-visible notification payload for reliable background delivery;
    other notification types can keep using the app-rendered data-only flow.
    `data` is a dictionary of custom key-value pairs (e.g., {"type": "follow", "target_id": "123"}).
    """
    # Guard: check if Firebase Admin SDK was initialized
    if not firebase_admin._apps:
        logger.error("Firebase Admin SDK is NOT initialized. Cannot send push notifications. "
                      "Check FIREBASE_CREDENTIALS in .env and ensure the file exists.")
        return {"success_count": 0, "failure_count": 0, "device_count": 0}

    data = dict(data or {})

    # Pack title and body into data so Flutter can construct the notification locally
    data['title'] = title
    data['body'] = body
    data['click_action'] = 'FLUTTER_NOTIFICATION_CLICK'
    
    if trigger_user:
        data['trigger_user_name'] = trigger_user.username
        if trigger_user.profile_picture:
            data['trigger_user_image'] = getattr(trigger_user.profile_picture, 'url', None)

    # Ensure values are strings and reserved FCM keys are never transmitted.
    stringified_data = _prepare_fcm_data(data)

    # Get all active devices for the user that have an FCM token
    devices = UserDevice.objects.filter(user=user, is_active=True).exclude(fcm_token__isnull=True).exclude(fcm_token="")
    
    if not devices.exists():
        logger.info(f"No active FCM tokens found for user {user.username}")
        return {"success_count": 0, "failure_count": 0, "device_count": 0}

    tokens = list(devices.values_list('fcm_token', flat=True))
    logger.info(f"Sending FCM to {len(tokens)} device(s) for user {user.username}")
    
    is_chat = stringified_data.get("type") == "chat_message"
    channel_id = "trendit_messages" if is_chat else "high_importance_channel"
    notification_count = None
    if is_chat:
        try:
            notification_count = max(1, int(stringified_data.get("unread_count", "1")))
        except (TypeError, ValueError):
            notification_count = 1

    android_notification = None
    notification = None
    if display_notification:
        image_url = stringified_data.get("trigger_user_image")
        if not image_url or not image_url.startswith(("https://", "http://")):
            image_url = None

        notification = messaging.Notification(title=title, body=body)
        android_notification = messaging.AndroidNotification(
            icon="ic_notification",
            color="#FF6A1A",
            sound="default",
            tag=stringified_data.get("notification_tag"),
            click_action="FLUTTER_NOTIFICATION_CLICK",
            channel_id=channel_id,
            image=image_url,
            notification_count=notification_count,
            default_vibrate_timings=True,
            visibility="private",
        )

    # High priority plus a visible notification payload lets Android wake a
    # sleeping device and render the message while the app is backgrounded.
    android_config = messaging.AndroidConfig(
        priority='high',
        ttl=timedelta(days=1),
        notification=android_notification,
    )

    message = messaging.MulticastMessage(
        data=stringified_data,
        notification=notification,
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
                    token_hint = f"{tokens[idx][:8]}...{tokens[idx][-6:]}"
                    logger.warning(
                        "Failed to send to token %s: %s",
                        token_hint,
                        resp.exception,
                    )
                    error_code = str(getattr(resp.exception, "code", "")).lower()
                    error_text = str(resp.exception).lower()
                    invalid_token = (
                        "invalid-registration-token" in error_code
                        or "registration-token-not-registered" in error_code
                        or "not registered" in error_text
                    )
                    if invalid_token:
                        failed_tokens.append(tokens[idx])
                        
            if failed_tokens:
                UserDevice.objects.filter(fcm_token__in=failed_tokens).update(is_active=False)
                logger.info(f"Deactivated {len(failed_tokens)} invalid tokens.")
        return {
            "success_count": response.success_count,
            "failure_count": response.failure_count,
            "device_count": len(tokens),
        }
    except Exception as e:
        logger.exception("Error sending FCM notification: %s", e)
        return {
            "success_count": 0,
            "failure_count": len(tokens),
            "device_count": len(tokens),
        }
