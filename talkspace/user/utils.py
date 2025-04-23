from django.core.mail import EmailMultiAlternatives
from django.conf import settings
from django.template.loader import render_to_string

def send_password_reset_email(user, reset_link):
    subject = "Reset Your Password"
    from_email = settings.EMAIL_HOST_USER
    to_email = user.email

    context = {
        'first_name': user.first_name or 'there',
        'reset_link': reset_link,
    }

    text_content = f"""
Hi {context['first_name']},

Click the link below to reset your password:
{context['reset_link']}

If you didn't request a password reset, you can safely ignore this email.
"""

    html_content = render_to_string('emails/reset_password_email.html', context)

    msg = EmailMultiAlternatives(subject, text_content, from_email, [to_email])
    msg.attach_alternative(html_content, "text/html")
    msg.send()
