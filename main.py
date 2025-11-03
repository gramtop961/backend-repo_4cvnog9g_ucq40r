import os
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, EmailStr
from typing import Any, Dict

from database import db, create_document
from schemas import ContactMessage

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.get("/")
def read_root():
    return {"message": "Bean and Cofe API running"}

@app.get("/api/hello")
def hello():
    return {"message": "Hello from the backend API!"}

@app.get("/test")
def test_database():
    """Test endpoint to check if database is available and accessible"""
    response: Dict[str, Any] = {
        "backend": "✅ Running",
        "database": "❌ Not Available",
        "database_url": None,
        "database_name": None,
        "connection_status": "Not Connected",
        "collections": []
    }
    
    try:
        if db is not None:
            response["database"] = "✅ Available"
            try:
                collections = db.list_collection_names()
                response["collections"] = collections[:10]
                response["database"] = "✅ Connected & Working"
                response["connection_status"] = "Connected"
            except Exception as e:
                response["database"] = f"⚠️  Connected but Error: {str(e)[:50]}"
        else:
            response["database"] = "⚠️  Available but not initialized"
            
    except Exception as e:
        response["database"] = f"❌ Error: {str(e)[:50]}"
    
    # Check environment variables
    response["database_url"] = "✅ Set" if os.getenv("DATABASE_URL") else "❌ Not Set"
    response["database_name"] = "✅ Set" if os.getenv("DATABASE_NAME") else "❌ Not Set"
    
    return response

class ContactRequest(BaseModel):
    name: str
    email: EmailStr
    message: str

@app.post("/contact")
def submit_contact(payload: ContactRequest):
    """Store contact inquiry in DB and send email via SMTP using environment variables.
    Required env vars:
      SMTP_HOST, SMTP_PORT, SMTP_USER, SMTP_PASS, SMTP_FROM, SMTP_TO
    """
    # Save to database (if configured)
    try:
        contact_doc = ContactMessage(name=payload.name, email=payload.email, message=payload.message)
        _id = create_document("contactmessage", contact_doc)
    except Exception:
        # Database not configured; continue without failing email
        _id = None

    # Prepare email
    smtp_host = os.getenv("SMTP_HOST")
    smtp_port = int(os.getenv("SMTP_PORT", "587"))
    smtp_user = os.getenv("SMTP_USER")
    smtp_pass = os.getenv("SMTP_PASS")
    smtp_from = os.getenv("SMTP_FROM") or os.getenv("SMTP_USER")
    smtp_to = os.getenv("SMTP_TO") or os.getenv("CONTACT_RECIPIENT")

    if not (smtp_host and smtp_port and smtp_user and smtp_pass and smtp_from and smtp_to):
        # If SMTP not configured, inform client gracefully
        return {
            "ok": True,
            "stored": bool(_id),
            "email_sent": False,
            "message": "Contact saved. Email service not configured on server. Please set SMTP environment variables to enable email sending.",
        }

    subject = f"New Inquiry from Bean and Cofe: {payload.name}"
    html_body = f"""
        <h2>New Contact Inquiry</h2>
        <p><strong>Name:</strong> {payload.name}</p>
        <p><strong>Email:</strong> {payload.email}</p>
        <p><strong>Message:</strong><br/>{payload.message.replace('\n', '<br/>')}</p>
    """

    msg = MIMEMultipart("alternative")
    msg["Subject"] = subject
    msg["From"] = smtp_from
    msg["To"] = smtp_to
    msg.attach(MIMEText(html_body, "html"))

    try:
        with smtplib.SMTP(smtp_host, smtp_port, timeout=15) as server:
            server.starttls()
            server.login(smtp_user, smtp_pass)
            server.sendmail(smtp_from, [smtp_to], msg.as_string())
        email_sent = True
    except Exception as e:
        email_sent = False

    return {
        "ok": True,
        "stored": bool(_id),
        "email_sent": email_sent,
        "message": "Thanks! Your message has been received. We'll get back to you shortly."
    }


if __name__ == "__main__":
    import uvicorn
    port = int(os.getenv("PORT", 8000))
    uvicorn.run(app, host="0.0.0.0", port=port)
