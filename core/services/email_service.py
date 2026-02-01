from django.core.mail import send_mail
from django.conf import settings
from django.template.loader import render_to_string
from django.utils.html import strip_tags

class EmailService:
    @staticmethod
    def send_otp_email(email, otp_code, purpose='activation'):
        """
        Send OTP code via email using the standard template.
        """
        from django.template import Template, Context
        
        subject_map = {
            'activation': 'Verify your email address',
            'password_reset': 'Reset your password',
            'login': 'Login Verification Code',
        }
        
        subject = subject_map.get(purpose, 'Verification Code')
        
        # HTML Template
        html_template_string = """
<!doctype html>
<html lang="en" xmlns:v="urn:schemas-microsoft-com:vml" xmlns:o="urn:schemas-microsoft-com:office:office">
<head>
    <meta charset="utf-8" />
    <meta name="viewport" content="width=device-width, initial-scale=1.0" />
    <meta name="x-apple-disable-message-reformatting" />
    <title>{{ subject }}</title>
    <!--[if mso]>
      <xml>
        <o:OfficeDocumentSettings>
          <o:PixelsPerInch>96</o:PixelsPerInch>
        </o:OfficeDocumentSettings>
      </xml>
      <style>
        table { border-collapse: collapse; }
        td, th, div, p, a, h1, h2, h3, h4, h5, h6 { font-family: "Georgia", serif; }
      </style>
    <![endif]-->
    <style>
      @import url("https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600&family=Playfair+Display:wght@600;700&display=swap");
      body { margin: 0; padding: 0; word-spacing: normal; background-color: #f4f4f5; }
      header, footer, nav, section, article { display: block; }
      .heading { font-family: "Playfair Display", Georgia, serif; color: #5a1e6e; }
      .body-text { font-family: "Inter", sans-serif; color: #18181b; }
      .btn-primary {
        background-color: #5a1e6e; color: #ffffff !important; border-radius: 8px; text-decoration: none;
        padding: 12px 28px; display: inline-block; font-weight: 600; font-family: "Inter", sans-serif;
        mso-padding-alt: 0; text-underline-color: #5a1e6e;
      }
      .btn-primary:hover { background-color: #461656; }
    </style>
</head>
<body style="background-color: #f4f4f5; -webkit-text-size-adjust: 100%; -ms-text-size-adjust: 100%;">
    <table role="presentation" width="100%" border="0" cellpadding="0" cellspacing="0" style="background-color: #f4f4f5">
      <tr>
        <td align="center" style="padding: 40px 10px">
          <table role="presentation" width="100%" border="0" cellpadding="0" cellspacing="0" style="max-width: 600px; background-color: #ffffff; border-radius: 12px; overflow: hidden; box-shadow: 0 4px 6px -1px rgba(0, 0, 0, 0.1), 0 2px 4px -1px rgba(0, 0, 0, 0.06);">
            <tr>
              <td style="padding: 32px 40px; background-color: #5a1e6e; text-align: center;">
                <h1 style="margin: 0; color: #ffffff; font-family: &quot;Playfair Display&quot;, Georgia, serif; font-size: 24px; font-weight: 700; letter-spacing: 0.5px;">
                  VocalEssence Chorale
                </h1>
              </td>
            </tr>
            <tr>
              <td style="padding: 40px 40px 30px 40px; background-color: #ffffff">
                <h2 class="heading" style="margin-top: 0; margin-bottom: 20px; font-size: 22px; font-weight: 700; color: #18181b;">
                  {{ title }}
                </h2>
                <p class="body-text" style="margin: 0 0 16px 0; font-size: 16px; line-height: 1.6; color: #3f3f46;">
                  Hello Member,
                </p>
                <p class="body-text" style="margin: 0 0 24px 0; font-size: 16px; line-height: 1.6; color: #3f3f46;">
                  {{ message_body }}
                </p>
                
                {% if details %}
                <table role="presentation" width="100%" border="0" cellpadding="0" cellspacing="0" style="background-color: #fafafa; border-radius: 8px; margin-bottom: 24px; border: 1px solid #e4e4e7;">
                  <tr>
                    <td style="padding: 20px; text-align: center;">
                       <h1 style="color: #4CAF50; letter-spacing: 5px; margin: 0; font-family: 'Inter', sans-serif;">{{ details }}</h1>
                    </td>
                  </tr>
                </table>
                {% endif %}
                
              </td>
            </tr>
            <tr>
              <td style="padding: 24px 40px; background-color: #f4f4f5; border-top: 1px solid #e4e4e7; text-align: center;">
                <p style="margin: 0 0 10px 0; font-family: &quot;Inter&quot;, sans-serif; font-size: 12px; line-height: 1.5; color: #71717a;">
                  &copy; 2026 VocalEssence Chorale. All Highs Reserved.
                </p>
              </td>
            </tr>
          </table>
        </td>
      </tr>
    </table>
</body>
</html>
        """
        
        template = Template(html_template_string)
        context = Context({
            'subject': subject,
            'title': subject,
            'message_body': 'Your verification code is below. This code will expire in 10 minutes.',
            'details': otp_code,
        })
        html_message = template.render(context)
        plain_message = strip_tags(html_message)
        
        try:
            send_mail(
                subject,
                plain_message,
                settings.DEFAULT_FROM_EMAIL,
                [email],
                html_message=html_message,
                fail_silently=False,
            )
            return True
        except Exception as e:
            print(f"Failed to send email: {e}")
            return False
