"""
Email service for sending verification emails
Supports Resend API (recommended) or Gmail SMTP
"""
import httpx
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from typing import Optional
import secrets
from datetime import datetime, timedelta

from app.config import settings


def generate_verification_token() -> str:
    """Generate a random verification token"""
    return secrets.token_urlsafe(32)


def get_token_expiry() -> datetime:
    """Get token expiry time (24 hours from now)"""
    return datetime.utcnow() + timedelta(hours=24)


def _build_verification_html(full_name: str, verify_url: str) -> str:
    """Build verification email HTML"""
    return f"""
    <!DOCTYPE html>
    <html>
    <head>
        <meta charset="UTF-8">
        <style>
            body {{ font-family: Arial, sans-serif; line-height: 1.6; color: #333; }}
            .container {{ max-width: 600px; margin: 0 auto; padding: 20px; }}
            .header {{ background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); color: white; padding: 30px; text-align: center; border-radius: 10px 10px 0 0; }}
            .content {{ background: #f9f9f9; padding: 30px; border-radius: 0 0 10px 10px; }}
            .button {{ display: inline-block; background: #667eea; color: white; padding: 15px 30px; text-decoration: none; border-radius: 5px; margin: 20px 0; }}
            .footer {{ text-align: center; margin-top: 20px; color: #666; font-size: 12px; }}
        </style>
    </head>
    <body>
        <div class="container">
            <div class="header">
                <h1>🏢 B2B Marketplace</h1>
            </div>
            <div class="content">
                <h2>Xin chào {full_name}!</h2>
                <p>Cảm ơn bạn đã đăng ký tài khoản tại B2B Marketplace.</p>
                <p>Vui lòng click vào nút bên dưới để xác thực email của bạn:</p>
                
                <center>
                    <a href="{verify_url}" class="button" style="color: white;">✅ Xác thực Email</a>
                </center>
                
                <p>Hoặc copy link sau vào trình duyệt:</p>
                <p style="word-break: break-all; background: #eee; padding: 10px; border-radius: 5px;">
                    {verify_url}
                </p>
                
                <p><strong>Lưu ý:</strong> Link này sẽ hết hạn sau 24 giờ.</p>
                
                <hr style="margin: 30px 0; border: none; border-top: 1px solid #ddd;">
                
                <p><strong>Bước tiếp theo:</strong></p>
                <p>Sau khi xác thực email, tài khoản của bạn sẽ được gửi đến Admin để duyệt. 
                Bạn sẽ nhận được email thông báo khi tài khoản được phê duyệt.</p>
            </div>
            <div class="footer">
                <p>Email này được gửi tự động, vui lòng không trả lời.</p>
                <p>© 2024 B2B Marketplace. All rights reserved.</p>
            </div>
        </div>
    </body>
    </html>
    """


def _build_approval_html(full_name: str, approved: bool, login_url: str, rejected_reason: Optional[str] = None) -> str:
    """Build approval notification email HTML"""
    if approved:
        return f"""
        <!DOCTYPE html>
        <html>
        <head>
            <meta charset="UTF-8">
            <style>
                body {{ font-family: Arial, sans-serif; line-height: 1.6; color: #333; }}
                .container {{ max-width: 600px; margin: 0 auto; padding: 20px; }}
                .header {{ background: linear-gradient(135deg, #11998e 0%, #38ef7d 100%); color: white; padding: 30px; text-align: center; border-radius: 10px 10px 0 0; }}
                .content {{ background: #f9f9f9; padding: 30px; border-radius: 0 0 10px 10px; }}
                .button {{ display: inline-block; background: #11998e; color: white; padding: 15px 30px; text-decoration: none; border-radius: 5px; margin: 20px 0; }}
            </style>
        </head>
        <body>
            <div class="container">
                <div class="header">
                    <h1>🎉 Chúc mừng!</h1>
                </div>
                <div class="content">
                    <h2>Xin chào {full_name}!</h2>
                    <p>Tài khoản của bạn đã được <strong style="color: green;">PHÊ DUYỆT</strong>!</p>
                    <p>Bạn có thể đăng nhập và bắt đầu sử dụng B2B Marketplace ngay bây giờ.</p>
                    
                    <center>
                        <a href="{login_url}" class="button" style="color: white;">🚀 Đăng nhập ngay</a>
                    </center>
                </div>
            </div>
        </body>
        </html>
        """
    else:
        reason_text = f"<p><strong>Lý do:</strong> {rejected_reason}</p>" if rejected_reason else ""
        return f"""
        <!DOCTYPE html>
        <html>
        <head>
            <meta charset="UTF-8">
            <style>
                body {{ font-family: Arial, sans-serif; line-height: 1.6; color: #333; }}
                .container {{ max-width: 600px; margin: 0 auto; padding: 20px; }}
                .header {{ background: linear-gradient(135deg, #eb3349 0%, #f45c43 100%); color: white; padding: 30px; text-align: center; border-radius: 10px 10px 0 0; }}
                .content {{ background: #f9f9f9; padding: 30px; border-radius: 0 0 10px 10px; }}
            </style>
        </head>
        <body>
            <div class="container">
                <div class="header">
                    <h1>📋 Thông báo</h1>
                </div>
                <div class="content">
                    <h2>Xin chào {full_name},</h2>
                    <p>Rất tiếc, tài khoản của bạn <strong style="color: red;">chưa được phê duyệt</strong>.</p>
                    {reason_text}
                    <p>Nếu bạn có thắc mắc, vui lòng liên hệ với chúng tôi.</p>
                </div>
            </div>
        </body>
        </html>
        """


async def send_email_resend(to_email: str, subject: str, html_content: str) -> bool:
    """Send email using Resend API"""
    if not settings.RESEND_API_KEY:
        return False
    
    try:
        # Use verified domain from settings, fallback to bmdtlab.site
        from_email = settings.EMAIL_FROM or "B2B Marketplace <noreply@bmdtlab.site>"
        
        async with httpx.AsyncClient() as client:
            response = await client.post(
                "https://api.resend.com/emails",
                headers={
                    "Authorization": f"Bearer {settings.RESEND_API_KEY}",
                    "Content-Type": "application/json"
                },
                json={
                    "from": from_email,
                    "to": [to_email],
                    "subject": subject,
                    "html": html_content
                }
            )
            
            if response.status_code == 200:
                print(f"✅ Email sent to {to_email} via Resend")
                return True
            else:
                print(f"❌ Resend error: {response.status_code} - {response.text}")
                return False
    except Exception as e:
        print(f"❌ Resend exception: {e}")
        return False


def send_email_smtp(to_email: str, subject: str, html_content: str) -> bool:
    """Send email using SMTP (Gmail)"""
    if not settings.SMTP_HOST or not settings.SMTP_USER:
        return False
    
    try:
        msg = MIMEMultipart("alternative")
        msg["Subject"] = subject
        msg["From"] = f"B2B Marketplace <{settings.SMTP_USER}>"
        msg["To"] = to_email
        
        msg.attach(MIMEText(html_content, "html"))
        
        with smtplib.SMTP(settings.SMTP_HOST, settings.SMTP_PORT, timeout=10) as server:
            server.starttls()
            server.login(settings.SMTP_USER, settings.SMTP_PASSWORD)
            server.sendmail(settings.SMTP_USER, to_email, msg.as_string())
        
        print(f"✅ Email sent to {to_email} via SMTP")
        return True
        
    except Exception as e:
        print(f"❌ SMTP error: {e}")
        return False


async def send_verification_email(
    to_email: str, 
    full_name: str, 
    verification_token: str,
    frontend_url: Optional[str] = None
) -> bool:
    """Send verification email to user"""
    base_url = frontend_url or settings.FRONTEND_URL or "http://localhost:5173"
    verify_url = f"{base_url}/verify-email?token={verification_token}"
    
    subject = "Xác thực email - B2B Marketplace"
    html_content = _build_verification_html(full_name, verify_url)
    
    # Try Resend first, then SMTP
    if settings.RESEND_API_KEY:
        result = await send_email_resend(to_email, subject, html_content)
        if result:
            return True
    
    # Try SMTP
    if settings.SMTP_HOST and settings.SMTP_USER:
        result = send_email_smtp(to_email, subject, html_content)
        if result:
            return True
    
    # Dev mode: print token with clear formatting
    print(f"")
    print(f"{'='*60}")
    print(f"⚠️  EMAIL NOT CONFIGURED - DEV MODE")
    print(f"{'='*60}")
    print(f"📧 To: {to_email}")
    print(f"🔗 Verification Link:")
    print(f"   {verify_url}")
    print(f"{'='*60}")
    print(f"")
    return True  # Return True to allow registration in dev mode


async def send_approval_notification(
    to_email: str,
    full_name: str,
    approved: bool,
    rejected_reason: Optional[str] = None,
    frontend_url: Optional[str] = None
) -> bool:
    """Send approval/rejection notification to user"""
    base_url = frontend_url or settings.FRONTEND_URL or "http://localhost:5173"
    login_url = f"{base_url}/login"
    
    subject = "🎉 Tài khoản đã được phê duyệt - B2B Marketplace" if approved else "Thông báo về tài khoản - B2B Marketplace"
    html_content = _build_approval_html(full_name, approved, login_url, rejected_reason)
    
    # Try Resend first, then SMTP
    if settings.RESEND_API_KEY:
        result = await send_email_resend(to_email, subject, html_content)
        if result:
            return True
    
    # Try SMTP
    if settings.SMTP_HOST and settings.SMTP_USER:
        result = send_email_smtp(to_email, subject, html_content)
        if result:
            return True
    
    # Dev mode
    print(f"⚠️ Email not configured. Approval notification for {to_email}: {'Approved' if approved else 'Rejected'}")
    return True