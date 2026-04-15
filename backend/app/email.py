"""Email verification via Resend."""

import logging
import os
import secrets

import resend

logger = logging.getLogger(__name__)

resend.api_key = os.getenv("RESEND_API_KEY", "")

FROM_EMAIL = "noreply@mail.dragonbox.top"


def generate_verification_code() -> str:
    """Generate a 6-digit numeric verification code."""
    return "".join(str(secrets.randbelow(10)) for _ in range(6))


def send_verification_email(to_email: str, code: str) -> bool:
    """Send a verification code email. Returns True on success."""
    html_content = f"""
    <div style="font-family: 'Segoe UI', Arial, sans-serif; max-width: 480px; margin: 0 auto; padding: 32px; background: #f9f6f0; border-radius: 12px;">
      <h2 style="color: #5a4a3a; text-align: center; margin-bottom: 8px;">
        邮箱验证 / Email Verification
      </h2>
      <p style="color: #6b5b4b; text-align: center; font-size: 14px; margin-bottom: 24px;">
        MTG AI Search
      </p>
      <div style="background: #fff; border: 1px solid #e0d5c5; border-radius: 8px; padding: 24px; text-align: center;">
        <p style="color: #5a4a3a; margin-bottom: 4px;">你的验证码是 / Your verification code is:</p>
        <p style="font-size: 36px; font-weight: bold; letter-spacing: 8px; color: #c9a959; margin: 16px 0;">
          {code}
        </p>
        <p style="color: #8a7a6a; font-size: 13px;">
          验证码将在 10 分钟后失效<br/>
          This code expires in 10 minutes.
        </p>
      </div>
      <p style="color: #a09080; font-size: 12px; text-align: center; margin-top: 20px;">
        如果你没有请求此验证码，请忽略本邮件。<br/>
        If you did not request this code, please ignore this email.
      </p>
    </div>
    """
    try:
        resend.Emails.send(
            {
                "from": f"MTG AI Search <{FROM_EMAIL}>",
                "to": [to_email],
                "subject": "验证码 / Verification Code — MTG AI Search",
                "html": html_content,
            }
        )
        logger.info("Verification email sent to %s", to_email)
        return True
    except Exception:
        logger.exception("Failed to send verification email to %s", to_email)
        return False
