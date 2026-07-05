"""Email validation and SMTP sending engine — zero dependencies.

Uses only Python stdlib (smtplib, email, urllib, json, dns.resolver fallback).
Validates email format, checks MX records, sends via SMTP.
"""
import json
import smtplib
import socket
import re
import urllib.request
import urllib.parse
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from typing import Any, Dict, List, Optional, Tuple


# Email regex (RFC 5322 simplified)
EMAIL_REGEX = re.compile(
    r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
)

# Common disposable email domains
DISPOSABLE_DOMAINS = {
    "mailinator.com", "guerrillamail.com", "tempmail.com", "10minutemail.com",
    "throwaway.email", "temp-mail.org", "fakeinbox.com", "sharklasers.com",
    "yopmail.com", "getnada.com", "maildrop.cc", "dispostable.com",
    "mailnesia.com", "trashmail.com", "tempinbox.com", "spam4.me",
}


class EmailValidator:
    """Email validation without external dependencies."""

    @staticmethod
    def validate_format(email: str) -> bool:
        """Check if email format is valid (RFC 5322 simplified)."""
        return bool(EMAIL_REGEX.match(email))

    @staticmethod
    def extract_domain(email: str) -> Optional[str]:
        """Extract domain from email address."""
        if "@" not in email:
            return None
        return email.split("@")[1].lower()

    @staticmethod
    def is_disposable(email: str) -> bool:
        """Check if email uses a disposable email service."""
        domain = EmailValidator.extract_domain(email)
        if not domain:
            return False
        return domain in DISPOSABLE_DOMAINS

    @staticmethod
    def is_role_based(email: str) -> bool:
        """Check if email is a role-based address (admin@, info@, etc.)."""
        role_prefixes = {
            "admin", "info", "support", "sales", "contact", "help",
            "webmaster", "postmaster", "abuse", "security", "noreply",
            "no-reply", "donotreply", "marketing", "team", "office",
            "hello", "mail", "root", "sysadmin", "billing",
        }
        if "@" not in email:
            return False
        local = email.split("@")[0].lower()
        return local in role_prefixes

    @staticmethod
    def check_mx_records(domain: str, timeout: int = 5) -> Dict:
        """Check MX records for a domain using DNS lookup.

        Ties to use socket.getaddrinfo as fallback if no DNS resolver available.
        """
        try:
            # Try using dnspython if available (optional, not required)
            import dns.resolver
            answers = dns.resolver.resolve(domain, "MX", lifetime=timeout)
            mx_records = []
            for r in answers:
                mx_records.append({
                    "priority": r.preference,
                    "exchange": str(r.exchange).rstrip("."),
                })
            mx_records.sort(key=lambda x: x["priority"])
            return {
                "domain": domain,
                "has_mx": len(mx_records) > 0,
                "mx_records": mx_records,
                "source": "dnspython",
            }
        except ImportError:
            # Fallback: try SMTP connection to domain
            try:
                socket.setdefaulttimeout(timeout)
                smtp = smtplib.SMTP(timeout=timeout)
                code, msg = smtp.connect(f"mx.{domain}")
                smtp.quit()
                return {
                    "domain": domain,
                    "has_mx": True,
                    "mx_records": [{"priority": 0, "exchange": f"mx.{domain}"}],
                    "source": "smtp_fallback",
                }
            except Exception:
                # Last resort: check if domain resolves at all
                try:
                    socket.getaddrinfo(domain, 25, socket.AF_INET, socket.SOCK_STREAM)
                    return {
                        "domain": domain,
                        "has_mx": True,
                        "mx_records": [],
                        "source": "dns_a_record",
                    }
                except socket.gaierror:
                    return {
                        "domain": domain,
                        "has_mx": False,
                        "mx_records": [],
                        "source": "dns_lookup_failed",
                    }
        except Exception as e:
            return {
                "domain": domain,
                "has_mx": False,
                "mx_records": [],
                "source": "error",
                "error": str(e),
            }

    @staticmethod
    def validate(email: str, check_mx: bool = False) -> Dict:
        """Full email validation. Returns detailed results."""
        result = {
            "email": email,
            "valid_format": False,
            "domain": None,
            "is_disposable": False,
            "is_role_based": False,
            "mx_check": None,
            "overall_valid": False,
        }

        result["valid_format"] = EmailValidator.validate_format(email)
        if not result["valid_format"]:
            return result

        result["domain"] = EmailValidator.extract_domain(email)
        result["is_disposable"] = EmailValidator.is_disposable(email)
        result["is_role_based"] = EmailValidator.is_role_based(email)

        if check_mx:
            result["mx_check"] = EmailValidator.check_mx_records(result["domain"])

        result["overall_valid"] = (
            result["valid_format"]
            and not result["is_disposable"]
            and (result["mx_check"] is None or result["mx_check"]["has_mx"])
        )

        return result

    @staticmethod
    def validate_batch(emails: List[str], check_mx: bool = False) -> Dict:
        """Validate multiple emails at once."""
        results = []
        for email in emails:
            results.append(EmailValidator.validate(email, check_mx=check_mx))
        valid_count = sum(1 for r in results if r["overall_valid"])
        return {
            "total": len(emails),
            "valid": valid_count,
            "invalid": len(emails) - valid_count,
            "results": results,
        }


class EmailSender:
    """SMTP email sender with zero dependencies."""

    def __init__(self, host: str = "localhost", port: int = 25,
                 username: str = None, password: str = None,
                 use_tls: bool = False, use_ssl: bool = False):
        self.host = host
        self.port = port
        self.username = username
        self.password = password
        self.use_tls = use_tls
        self.use_ssl = use_ssl

    def send_email(self, to: str, subject: str, body: str,
                   from_addr: str = None, html: bool = False,
                   cc: List[str] = None, bcc: List[str] = None,
                   reply_to: str = None) -> Dict:
        """Send an email via SMTP."""
        from_addr = from_addr or self.username or "noreply@localhost"

        if html:
            msg = MIMEMultipart("alternative")
            msg.attach(MIMEText(body, "html", "utf-8"))
        else:
            msg = MIMEText(body, "plain", "utf-8")

        msg["Subject"] = subject
        msg["From"] = from_addr
        msg["To"] = to

        if cc:
            msg["Cc"] = ", ".join(cc)
        if reply_to:
            msg["Reply-To"] = reply_to

        all_recipients = [to]
        if cc:
            all_recipients.extend(cc)
        if bcc:
            all_recipients.extend(bcc)

        try:
            if self.use_ssl:
                server = smtplib.SMTP_SSL(self.host, self.port, timeout=30)
            else:
                server = smtplib.SMTP(self.host, self.port, timeout=30)

            if self.use_tls and not self.use_ssl:
                server.starttls()

            if self.username and self.password:
                server.login(self.username, self.password)

            server.sendmail(from_addr, all_recipients, msg.as_string())
            server.quit()

            return {
                "success": True,
                "to": to,
                "subject": subject,
                "recipients_count": len(all_recipients),
            }
        except smtplib.SMTPAuthenticationError as e:
            return {"success": False, "error": f"Authentication failed: {e}", "to": to}
        except smtplib.SMTPRecipientsRefused as e:
            return {"success": False, "error": f"Recipients refused: {e}", "to": to}
        except smtplib.SMTPException as e:
            return {"success": False, "error": f"SMTP error: {e}", "to": to}
        except Exception as e:
            return {"success": False, "error": str(e), "to": to}

    def send_batch(self, emails: List[Dict]) -> Dict:
        """Send multiple emails. Each dict must have to, subject, body.

        Optional keys: from_addr, html (bool), cc, bcc, reply_to.
        """
        results = []
        sent = 0
        failed = 0
        for email_data in emails:
            result = self.send_email(
                to=email_data["to"],
                subject=email_data["subject"],
                body=email_data["body"],
                from_addr=email_data.get("from_addr"),
                html=email_data.get("html", False),
                cc=email_data.get("cc"),
                bcc=email_data.get("bcc"),
                reply_to=email_data.get("reply_to"),
            )
            results.append(result)
            if result["success"]:
                sent += 1
            else:
                failed += 1

        return {
            "total": len(emails),
            "sent": sent,
            "failed": failed,
            "results": results,
        }

    def test_connection(self) -> Dict:
        """Test SMTP server connection without sending."""
        try:
            if self.use_ssl:
                server = smtplib.SMTP_SSL(self.host, self.port, timeout=10)
            else:
                server = smtplib.SMTP(self.host, self.port, timeout=10)

            if self.use_tls and not self.use_ssl:
                server.starttls()

            if self.username and self.password:
                server.login(self.username, self.password)

            server.quit()
            return {
                "success": True,
                "host": self.host,
                "port": self.port,
                "tls": self.use_tls,
                "ssl": self.use_ssl,
            }
        except Exception as e:
            return {
                "success": False,
                "host": self.host,
                "port": self.port,
                "error": str(e),
            }
