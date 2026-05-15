import logging
import os
import smtplib
import ssl
import subprocess
import sys
from email.message import EmailMessage

logger = logging.getLogger(__name__)


def _esc_as(s):
    """AppleScript 字符串转义：反斜杠、双引号、换行符。"""
    return str(s).replace("\\", "\\\\").replace('"', '\\"').replace("\n", " ").replace("\r", " ")


def _esc_ps(s):
    """PowerShell 双引号字符串转义：双引号 → 连续两个双引号。"""
    return str(s).replace('"', '""')


def send_notification(title, message):
    """跨平台系统通知。失败/不支持的平台静默 skip（不影响主流程）。

    - macOS：osascript display notification
    - Linux：notify-send（需要 libnotify-bin / notify-osd 已安装）
    - Windows：PowerShell BurntToast-free toast（Win10+）
    - 其它：静默 no-op
    """
    p = sys.platform
    try:
        if p == "darwin":
            t_safe = _esc_as(title)
            m_safe = _esc_as(message)
            subprocess.run(
                ["osascript", "-e",
                 f'display notification "{m_safe}" with title "{t_safe}" sound name "Glass"'],
                check=True,
            )
        elif p.startswith("linux"):
            subprocess.run(["notify-send", title, message], check=True)
        elif p == "win32":
            t_safe = _esc_ps(title)
            m_safe = _esc_ps(message)
            ps = (
                "$ErrorActionPreference='SilentlyContinue';"
                "[Windows.UI.Notifications.ToastNotificationManager,"
                "Windows.UI.Notifications,ContentType=WindowsRuntime]>$null;"
                "$x=[Windows.UI.Notifications.ToastNotificationManager]"
                "::GetTemplateContent([Windows.UI.Notifications.ToastTemplateType]::ToastText02);"
                f'$x.GetElementsByTagName(\'text\')[0].AppendChild($x.CreateTextNode("{t_safe}"))>$null;'
                f'$x.GetElementsByTagName(\'text\')[1].AppendChild($x.CreateTextNode("{m_safe}"))>$null;'
                "$t=[Windows.UI.Notifications.ToastNotification]::new($x);"
                "[Windows.UI.Notifications.ToastNotificationManager]"
                "::CreateToastNotifier('DailyInvestmentReport').Show($t);"
            )
            subprocess.run(["powershell", "-NoProfile", "-Command", ps], check=True)
        else:
            return  # 未支持的平台，silent no-op
        logger.info("通知已发送")
    except Exception as e:
        logger.warning("通知发送失败（%s）: %s", p, e)


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
        logger.warning("SMTP 未配置（缺少 SMTP_HOST / SMTP_USER / SMTP_PASS），跳过发邮件")
        return

    msg = EmailMessage()
    msg["Subject"] = subject
    msg["From"] = sender
    msg["To"] = to
    msg.set_content("Your email client does not support HTML. Open in an HTML-capable client.")
    msg.add_alternative(html_content, subtype="html")

    try:
        ctx = ssl.create_default_context()
        with smtplib.SMTP(host, port, timeout=30) as s:
            s.starttls(context=ctx)
            s.login(user, password)
            s.send_message(msg)
        logger.info("邮件已发送至 %s", to)
    except Exception as e:
        logger.warning("邮件发送失败: %s", e)
