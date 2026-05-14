import os
import smtplib
import ssl
import subprocess
import sys
from email.message import EmailMessage


def send_notification(title, message):
    """macOS 系统通知；非 macOS 平台静默跳过。"""
    if sys.platform != "darwin":
        return
    try:
        subprocess.run([
            "osascript", "-e",
            f'display notification "{message}" with title "{title}" sound name "Glass"',
        ], check=True)
        print("  通知已发送")
    except Exception as e:
        print(f"  [WARN] 通知发送失败: {e}")


def send_email(to, subject, html_content):
    """通过 SMTP 发送 HTML 邮件，HTML 直接 inline 进正文。

    必需环境变量：SMTP_HOST、SMTP_USER、SMTP_PASS。
    可选：SMTP_PORT（默认 587）、EMAIL_FROM（默认与 SMTP_USER 相同）。
    """
    host = os.environ.get("SMTP_HOST")
    port = int(os.environ.get("SMTP_PORT", "587"))
    user = os.environ.get("SMTP_USER")
    password = os.environ.get("SMTP_PASS")
    sender = os.environ.get("EMAIL_FROM") or user

    if not (host and user and password):
        print("  [WARN] SMTP 未配置（缺少 SMTP_HOST / SMTP_USER / SMTP_PASS），跳过发邮件")
        return

    msg = EmailMessage()
    msg["Subject"] = subject
    msg["From"] = sender
    msg["To"] = to
    msg.set_content("您的邮件客户端不支持 HTML 显示，请在支持 HTML 的客户端中打开。")
    msg.add_alternative(html_content, subtype="html")

    try:
        ctx = ssl.create_default_context()
        with smtplib.SMTP(host, port, timeout=30) as s:
            s.starttls(context=ctx)
            s.login(user, password)
            s.send_message(msg)
        print(f"  邮件已发送至 {to}")
    except Exception as e:
        print(f"  [WARN] 邮件发送失败: {e}")
