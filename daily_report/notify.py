import os
import smtplib
import ssl
import subprocess
import sys
from email.message import EmailMessage


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
            subprocess.run(
                ["osascript", "-e",
                 f'display notification "{message}" with title "{title}" sound name "Glass"'],
                check=True,
            )
        elif p.startswith("linux"):
            subprocess.run(["notify-send", title, message], check=True)
        elif p == "win32":
            ps = (
                "$ErrorActionPreference='SilentlyContinue';"
                "[Windows.UI.Notifications.ToastNotificationManager,"
                "Windows.UI.Notifications,ContentType=WindowsRuntime]>$null;"
                "$x=[Windows.UI.Notifications.ToastNotificationManager]"
                "::GetTemplateContent([Windows.UI.Notifications.ToastTemplateType]::ToastText02);"
                f"$x.GetElementsByTagName('text')[0].AppendChild($x.CreateTextNode(\"{title}\"))>$null;"
                f"$x.GetElementsByTagName('text')[1].AppendChild($x.CreateTextNode(\"{message}\"))>$null;"
                "$t=[Windows.UI.Notifications.ToastNotification]::new($x);"
                "[Windows.UI.Notifications.ToastNotificationManager]"
                "::CreateToastNotifier('DailyInvestmentReport').Show($t);"
            )
            subprocess.run(["powershell", "-NoProfile", "-Command", ps], check=True)
        else:
            return  # 未支持的平台，silent no-op
        print("  通知已发送")
    except Exception as e:
        print(f"  [WARN] 通知发送失败（{p}）: {e}")


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
    msg.set_content("Your email client does not support HTML. Open in an HTML-capable client.")
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
