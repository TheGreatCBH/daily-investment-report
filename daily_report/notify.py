import subprocess


def send_notification(title, message):
    """macOS 系统通知"""
    try:
        subprocess.run([
            "osascript", "-e",
            f'display notification "{message}" with title "{title}" sound name "Glass"',
        ], check=True)
        print("  通知已发送")
    except Exception as e:
        print(f"  [WARN] 通知发送失败: {e}")


def send_email(to, subject, html_content, email_config, report_path):
    """通过 Mail.app 发送报告（HTML 作为附件）"""
    subject_escaped = subject.replace('"', '\\"')
    report_escaped = str(report_path.absolute()).replace('"', '\\"')

    applescript = f'''
    tell application "Mail"
        set newMessage to make new outgoing message with properties {{subject:"{subject_escaped}", visible:false}}
        tell newMessage
            make new to recipient at end of to recipients with properties {{address:"{to}"}}
            set content to "今日投资简报已生成，请下载附件后用浏览器打开查看完整报告（含走势图）。"
            make new attachment with properties {{file name:POSIX file "{report_escaped}"}} at after last paragraph
            send
        end tell
    end tell
    '''
    try:
        subprocess.run(["osascript", "-e", applescript], check=True, timeout=30)
        print(f"  邮件已发送至 {to}")
    except Exception as e:
        print(f"  [WARN] 邮件发送失败: {e}")
