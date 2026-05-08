import threading
from django.core.mail import EmailMultiAlternatives
from django.template.loader import render_to_string
from django.utils.html import strip_tags
from django.conf import settings

class EmailThread(threading.Thread):
    def __init__(self, email_msg):
        self.email_msg = email_msg
        threading.Thread.__init__(self)

    def run(self):
        try:
            self.email_msg.send()
        except Exception as e:
            # You can log the error here if needed
            print(f"Failed to send email: {e}")

def send_otp_email(email, username, otp_code, purpose="register"):
    """
    Sends an OTP email asynchronously to the user.
    `purpose` can be 'register' or 'password_reset'
    """
    if purpose == "password_reset":
        subject = "Trendit - Password Reset Verification Code"
        title = "Reset Your Password"
        message = "Please use the following verification code to reset your password. Do not share this code with anyone."
    else:
        subject = "Trendit - Welcome! Verify your email"
        title = "Verify Your Account"
        message = "Thank you for registering with Trendit! Please use the following verification code to complete your registration."

    context = {
        'username': username,
        'otp_code': otp_code,
        'title': title,
        'message': message
    }

    html_content = render_to_string('users/otp_email.html', context)
    text_content = strip_tags(html_content)

    email_msg = EmailMultiAlternatives(
        subject=subject,
        body=text_content,
        from_email=settings.DEFAULT_FROM_EMAIL,
        to=[email]
    )
    email_msg.attach_alternative(html_content, "text/html")

    # Send asynchronously
    EmailThread(email_msg).start()
