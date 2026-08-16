"""Send interview invitation emails with frontend deep links."""
from __future__ import annotations

import html
import logging
import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

from backend.app.core.config import settings
from backend.app.services.interview_assignment import build_interview_url

logger = logging.getLogger(__name__)

COMPANY_NAME = "HireMate"


def build_interview_link(user_id: int, interview_id: int, access_token: str | None = None) -> str:
    return build_interview_url(user_id, interview_id, access_token)


def _build_email_content(
    *,
    to_email: str,
    user_name: str | None,
    user_id: int,
    interview_id: int,
    title: str,
    difficulty: str,
    summary: str,
    access_token: str | None = None,
) -> tuple[str, str, str]:
    link = build_interview_link(user_id, interview_id, access_token)
    greeting_name = user_name.strip() if user_name and user_name.strip() else "there"
    safe_title = html.escape(title)
    safe_difficulty = html.escape(difficulty.capitalize())
    safe_summary = html.escape(summary.strip())
    safe_email = html.escape(to_email)
    safe_link = html.escape(link, quote=True)
    safe_greeting = html.escape(greeting_name)

    subject = f"{COMPANY_NAME} — Complete your interview: {title}"

    text_body = f"""Hello {greeting_name},

{COMPANY_NAME} has invited you to complete an online interview.

Interview details
-----------------
Title: {title}
Difficulty: {difficulty.capitalize()}
About: {summary.strip()}

Complete your interview here:
{link}

This link is personal to your account (user id: {user_id}, interview id: {interview_id}).
Please sign in with {to_email} before you start.

What to expect
--------------
- AI will read each question aloud
- Answer by speaking or typing
- All answers are evaluated together at the end

If you did not expect this email, you can ignore it.

Best regards,
The {COMPANY_NAME} Team
"""

    html_body = f"""
<!DOCTYPE html>
<html>
  <body style="margin:0;padding:0;background:#f4f6fb;font-family:Arial,Helvetica,sans-serif;color:#1f2937;">
    <table role="presentation" width="100%" cellspacing="0" cellpadding="0" style="background:#f4f6fb;padding:24px 0;">
      <tr>
        <td align="center">
          <table role="presentation" width="600" cellspacing="0" cellpadding="0" style="background:#ffffff;border-radius:12px;overflow:hidden;box-shadow:0 8px 24px rgba(15,23,42,0.08);">
            <tr>
              <td style="background:#2563eb;padding:24px 32px;color:#ffffff;">
                <div style="font-size:14px;letter-spacing:0.04em;text-transform:uppercase;opacity:0.9;">{COMPANY_NAME}</div>
                <h1 style="margin:8px 0 0;font-size:24px;line-height:1.3;">Complete your interview</h1>
              </td>
            </tr>
            <tr>
              <td style="padding:32px;">
                <p style="margin:0 0 16px;font-size:16px;line-height:1.6;">Hello {safe_greeting},</p>
                <p style="margin:0 0 20px;font-size:16px;line-height:1.6;">
                  <strong>{COMPANY_NAME}</strong> has invited you to complete an online interview.
                  Use the button below to open your personal interview page and get started.
                </p>

                <table role="presentation" width="100%" cellspacing="0" cellpadding="0" style="background:#f8fafc;border:1px solid #e5e7eb;border-radius:10px;margin-bottom:24px;">
                  <tr>
                    <td style="padding:20px;">
                      <p style="margin:0 0 8px;font-size:14px;color:#6b7280;">Interview</p>
                      <p style="margin:0 0 12px;font-size:18px;font-weight:700;color:#111827;">{safe_title}</p>
                      <p style="margin:0 0 8px;font-size:14px;"><strong>Difficulty:</strong> {safe_difficulty}</p>
                      <p style="margin:0;font-size:14px;line-height:1.6;"><strong>About:</strong> {safe_summary}</p>
                    </td>
                  </tr>
                </table>

                <p style="margin:0 0 20px;text-align:center;">
                  <a href="{safe_link}"
                     style="display:inline-block;background:#2563eb;color:#ffffff;text-decoration:none;padding:14px 28px;border-radius:8px;font-size:16px;font-weight:700;">
                    Complete Interview Here
                  </a>
                </p>

                <p style="margin:0 0 12px;font-size:14px;line-height:1.6;color:#4b5563;">
                  Or copy this link into your browser:<br/>
                  <a href="{safe_link}" style="color:#2563eb;word-break:break-all;">{safe_link}</a>
                </p>

                <p style="margin:0 0 12px;font-size:14px;line-height:1.6;color:#4b5563;">
                  Please sign in with <strong>{safe_email}</strong> before starting.
                  This link is assigned to user id <strong>{user_id}</strong> and interview id <strong>{interview_id}</strong>.
                </p>

                <ul style="margin:0;padding-left:20px;font-size:14px;line-height:1.7;color:#4b5563;">
                  <li>AI will read each question aloud</li>
                  <li>Answer by speaking or typing</li>
                  <li>All answers are evaluated together at the end</li>
                </ul>
              </td>
            </tr>
            <tr>
              <td style="padding:20px 32px;background:#f8fafc;border-top:1px solid #e5e7eb;font-size:12px;color:#6b7280;">
                If you did not expect this invitation, you can safely ignore this email.<br/>
                &copy; {COMPANY_NAME}
              </td>
            </tr>
          </table>
        </td>
      </tr>
    </table>
  </body>
</html>
"""

    return subject, text_body, html_body


def send_interview_invitation_email(
    *,
    to_email: str,
    user_id: int,
    interview_id: int,
    title: str,
    difficulty: str,
    summary: str,
    user_name: str | None = None,
    access_token: str | None = None,
    description: str | None = None,
) -> bool:
    """Send interview link email. Returns True if sent (or skipped in dev), False on failure."""
    display_summary = (summary or description or title).strip()
    subject, text_body, html_body = _build_email_content(
        to_email=to_email,
        user_name=user_name,
        user_id=user_id,
        interview_id=interview_id,
        title=title,
        difficulty=difficulty,
        summary=display_summary,
        access_token=access_token,
    )
    link = build_interview_link(user_id, interview_id, access_token)

    if not settings.smtp_host:
        logger.info(
            "SMTP not configured — interview invitation for %s (%s): %s",
            to_email,
            user_name or "user",
            link,
        )
        return True

    message = MIMEMultipart("alternative")
    message["Subject"] = subject
    message["From"] = settings.smtp_from_email or settings.smtp_user
    message["To"] = to_email
    message.attach(MIMEText(text_body, "plain"))
    message.attach(MIMEText(html_body, "html"))

    try:
        with smtplib.SMTP(settings.smtp_host, settings.smtp_port, timeout=30) as server:
            if settings.smtp_use_tls:
                server.starttls()
            if settings.smtp_user and settings.smtp_password:
                server.login(settings.smtp_user, settings.smtp_password.replace(" ", ""))
            server.sendmail(message["From"], [to_email], message.as_string())
        logger.info("Interview invitation email sent to %s", to_email)
        return True
    except Exception as exc:
        logger.error("Failed to send interview email to %s: %s", to_email, exc)
        return False


def _send_simple_email(*, to_email: str, subject: str, text_body: str, html_body: str) -> bool:
    if not settings.smtp_host:
        logger.info("SMTP not configured — would email %s: %s", to_email, subject)
        return True

    message = MIMEMultipart("alternative")
    message["Subject"] = subject
    message["From"] = settings.smtp_from_email or settings.smtp_user
    message["To"] = to_email
    message.attach(MIMEText(text_body, "plain"))
    message.attach(MIMEText(html_body, "html"))

    try:
        with smtplib.SMTP(settings.smtp_host, settings.smtp_port, timeout=30) as server:
            if settings.smtp_use_tls:
                server.starttls()
            if settings.smtp_user and settings.smtp_password:
                server.login(settings.smtp_user, settings.smtp_password.replace(" ", ""))
            server.sendmail(message["From"], [to_email], message.as_string())
        logger.info("Email sent to %s: %s", to_email, subject)
        return True
    except Exception as exc:
        logger.error("Failed to send email to %s: %s", to_email, exc)
        return False


def send_new_interview_request_admin_email(
    *,
    user_email: str,
    user_name: str,
    domain: str,
    description: str,
    request_id: int,
) -> bool:
    admin_email = settings.admin_email
    if not admin_email:
        logger.info("ADMIN_EMAIL not set — skip new request notification for request %s", request_id)
        return True

    subject = f"{COMPANY_NAME} — New interview request #{request_id}"
    text_body = (
        f"A user submitted a new interview request.\n\n"
        f"Request ID: {request_id}\n"
        f"User: {user_name} ({user_email})\n"
        f"Domain: {domain}\n"
        f"Description:\n{description}\n\n"
        f"Review it in the admin panel under Requested Interviews."
    )
    html_body = f"""
    <p>A user submitted a new interview request.</p>
    <p><strong>Request ID:</strong> {request_id}<br/>
    <strong>User:</strong> {html.escape(user_name)} ({html.escape(user_email)})<br/>
    <strong>Domain:</strong> {html.escape(domain)}</p>
    <p><strong>Description:</strong><br/>{html.escape(description)}</p>
    <p>Review it in the admin panel under <strong>Requested Interviews</strong>.</p>
    """
    return _send_simple_email(
        to_email=admin_email,
        subject=subject,
        text_body=text_body,
        html_body=html_body,
    )


def send_interview_completion_emails(
    *,
    user_email: str,
    user_name: str | None,
    interview_title: str,
    score: int,
    domain: str,
) -> None:
    greeting = user_name or "there"
    user_subject = f"{COMPANY_NAME} — Interview completed: {interview_title}"
    user_text = (
        f"Hello {greeting},\n\n"
        f"Your interview for {domain} has been completed.\n"
        f"Overall score: {score}/100\n\n"
        f"Open Interview Practice in {COMPANY_NAME} to view your detailed results."
    )
    user_html = f"""
    <p>Hello {html.escape(greeting)},</p>
    <p>Your interview for <strong>{html.escape(domain)}</strong> has been completed.</p>
    <p><strong>Overall score:</strong> {score}/100</p>
    <p>Open Interview Practice in {COMPANY_NAME} to view your detailed results.</p>
    """
    _send_simple_email(
        to_email=user_email,
        subject=user_subject,
        text_body=user_text,
        html_body=user_html,
    )

    admin_email = settings.admin_email
    if not admin_email:
        return

    admin_subject = f"{COMPANY_NAME} — User completed interview ({score}/100)"
    admin_text = (
        f"User {greeting} ({user_email}) completed interview '{interview_title}'.\n"
        f"Domain: {domain}\n"
        f"Score: {score}/100"
    )
    admin_html = f"""
    <p>User <strong>{html.escape(greeting)}</strong> ({html.escape(user_email)}) completed an interview.</p>
    <p><strong>Interview:</strong> {html.escape(interview_title)}<br/>
    <strong>Domain:</strong> {html.escape(domain)}<br/>
    <strong>Score:</strong> {score}/100</p>
    """
    _send_simple_email(
        to_email=admin_email,
        subject=admin_subject,
        text_body=admin_text,
        html_body=admin_html,
    )
