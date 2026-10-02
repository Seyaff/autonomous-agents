import logging
import base64
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from typing import Optional, Dict, Any
from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError

from core.settings import settings

logger = logging.getLogger(__name__)


class GmailService:
    """Send emails using Google Gmail API."""
    
    def __init__(self):
        self._service = None
        self._sender_email = getattr(settings, "GMAIL_SENDER_EMAIL", "noreply@siyaf.com")
    
    def _get_credentials(self) -> Credentials:
        """Build credentials from environment variables."""
        client_id = getattr(settings, "GOOGLE_CLIENT_ID", "")
        client_secret = getattr(settings, "GOOGLE_CLIENT_SECRET", "")
        refresh_token = getattr(settings, "GMAIL_REFRESH_TOKEN", "")
        
        if not all([client_id, client_secret, refresh_token]):
            raise ValueError("Gmail API credentials not configured. Need GOOGLE_CLIENT_ID, GOOGLE_CLIENT_SECRET, GMAIL_REFRESH_TOKEN")
        
        return Credentials(
            token=None,
            refresh_token=refresh_token,
            client_id=client_id,
            client_secret=client_secret,
            token_uri="https://oauth2.googleapis.com/token",
        )
    
    def _get_service(self):
        """Get or create Gmail API service."""
        if self._service is None:
            credentials = self._get_credentials()
            self._service = build("gmail", "v1", credentials=credentials)
        return self._service
    
    def send_email(
        self,
        to: str,
        subject: str,
        html_body: str,
        text_body: Optional[str] = None,
        from_name: str = "Siyaf",
    ) -> bool:
        """Send an email via Gmail API."""
        try:
            service = self._get_service()
            
            # Create message
            message = MIMEMultipart("alternative")
            message["To"] = to
            message["Subject"] = subject
            message["From"] = f"{from_name} <{self._sender_email}>"
            
            # Add text part
            if text_body:
                message.attach(MIMEText(text_body, "plain"))
            
            # Add HTML part
            message.attach(MIMEText(html_body, "html"))
            
            # Encode message
            raw_message = base64.urlsafe_b64encode(message.as_bytes()).decode()
            
            # Send
            result = service.users().messages().send(
                userId="me",
                body={"raw": raw_message}
            ).execute()
            
            logger.info(f"Email sent to {to}: {result.get('id')}")
            return True
            
        except HttpError as e:
            logger.error(f"Gmail API error sending to {to}: {e}")
            return False
        except Exception as e:
            logger.exception(f"Failed to send email to {to}: {e}")
            return False
    
    def send_new_message_notification(
        self,
        to_email: str,
        customer_name: str,
        preview: str,
        conversation_id: str,
    ) -> bool:
        """Send new message notification email."""
        subject = f"New WhatsApp message from {customer_name}"
        
        html_body = f"""
        <!DOCTYPE html>
        <html>
        <body style="font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; line-height: 1.6; color: #333; max-width: 600px; margin: 0 auto; padding: 20px;">
            <div style="background: linear-gradient(135deg, #25D366 0%, #128C7E 100%); padding: 30px; border-radius: 12px 12px 0 0;">
                <h1 style="color: white; margin: 0; font-size: 24px;">💬 New WhatsApp Message</h1>
            </div>
            <div style="background: #f8f9fa; padding: 30px; border-radius: 0 0 12px 12px; border: 1px solid #e9ecef; border-top: none;">
                <p style="font-size: 16px; margin-top: 0;">You have a new message from <strong>{customer_name}</strong>:</p>
                
                <div style="background: white; border-left: 4px solid #25D366; padding: 20px; margin: 20px 0; border-radius: 0 8px 8px 0; box-shadow: 0 2px 4px rgba(0,0,0,0.05);">
                    <p style="margin: 0; font-size: 15px; color: #444;">{preview}</p>
                </div>
                
                <div style="text-align: center; margin-top: 30px;">
                    <a href="https://siyaf.vercel.app/inbox/c/{conversation_id}" 
                       style="display: inline-block; background: #25D366; color: white; padding: 14px 28px; border-radius: 8px; text-decoration: none; font-weight: 600; font-size: 16px;">
                        View in Inbox →
                    </a>
                </div>
                
                <hr style="border: none; border-top: 1px solid #e9ecef; margin: 30px 0;">
                <p style="font-size: 13px; color: #888; text-align: center; margin: 0;">
                    You're receiving this because you have notifications enabled.<br>
                    <a href="https://siyaf.vercel.app/settings" style="color: #25D366;">Manage preferences</a>
                </p>
            </div>
        </body>
        </html>
        """
        
        text_body = f"""New WhatsApp message from {customer_name}

{preview}

View in Inbox: https://siyaf.vercel.app/inbox/c/{conversation_id}

---
Manage preferences: https://siyaf.vercel.app/settings"""
        
        return self.send_email(
            to=to_email,
            subject=subject,
            html_body=html_body,
            text_body=text_body,
        )
    
    def send_order_notification(
        self,
        to_email: str,
        customer_name: str,
        order_id: str,
        total_amount: str,
        conversation_id: str,
    ) -> bool:
        """Send new order notification email."""
        subject = f"New Order #{order_id} from {customer_name}"
        
        html_body = f"""
        <!DOCTYPE html>
        <html>
        <body style="font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; line-height: 1.6; color: #333; max-width: 600px; margin: 0 auto; padding: 20px;">
            <div style="background: linear-gradient(135deg, #25D366 0%, #128C7E 100%); padding: 30px; border-radius: 12px 12px 0 0;">
                <h1 style="color: white; margin: 0; font-size: 24px;">🛒 New Order Received</h1>
            </div>
            <div style="background: #f8f9fa; padding: 30px; border-radius: 0 0 12px 12px; border: 1px solid #e9ecef; border-top: none;">
                <p style="font-size: 16px; margin-top: 0;"><strong>{customer_name}</strong> placed a new order:</p>
                
                <div style="background: white; border-left: 4px solid #25D366; padding: 20px; margin: 20px 0; border-radius: 0 8px 8px 0; box-shadow: 0 2px 4px rgba(0,0,0,0.05);">
                    <p style="margin: 0 0 10px;"><strong>Order ID:</strong> {order_id}</p>
                    <p style="margin: 0 0 10px;"><strong>Customer:</strong> {customer_name}</p>
                    <p style="margin: 0;"><strong>Total:</strong> {total_amount}</p>
                </div>
                
                <div style="text-align: center; margin-top: 30px;">
                    <a href="https://siyaf.vercel.app/inbox/c/{conversation_id}" 
                       style="display: inline-block; background: #25D366; color: white; padding: 14px 28px; border-radius: 8px; text-decoration: none; font-weight: 600; font-size: 16px;">
                        View Order Details →
                    </a>
                </div>
            </div>
        </body>
        </html>
        """
        
        return self.send_email(
            to=to_email,
            subject=subject,
            html_body=html_body,
        )


# Global instance
gmail_service = GmailService()