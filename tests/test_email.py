"""Tests for MCP Email Sender — validation, MX checks, SMTP sending (mocked)."""
import json
import pytest
import os
import sys
from unittest.mock import MagicMock, patch, mock_open
import smtplib

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from src.server import MCPEmailServer, TOOL_DEFS
from src.email_engine import EmailValidator, EmailSender


# ─── Tool Definition Tests ────────────────────────────────────────────────

class TestToolDefinitions:
    def test_all_tools_have_names(self):
        for tool in TOOL_DEFS:
            assert "name" in tool and len(tool["name"]) > 0

    def test_all_tools_have_descriptions(self):
        for tool in TOOL_DEFS:
            assert "description" in tool and len(tool["description"]) > 10

    def test_all_tools_have_input_schema(self):
        for tool in TOOL_DEFS:
            assert "inputSchema" in tool
            assert tool["inputSchema"]["type"] == "object"

    def test_expected_tool_count(self):
        assert len(TOOL_DEFS) == 8

    def test_required_tools_present(self):
        names = {t["name"] for t in TOOL_DEFS}
        expected = {
            "validate_email", "validate_email_batch", "check_mx_records",
            "is_disposable", "is_role_based", "send_email",
            "send_email_batch", "test_smtp_connection"
        }
        assert names == expected

    def test_validate_email_requires_email(self):
        tool = next(t for t in TOOL_DEFS if t["name"] == "validate_email")
        assert "email" in tool["inputSchema"].get("required", [])

    def test_send_email_requires_fields(self):
        tool = next(t for t in TOOL_DEFS if t["name"] == "send_email")
        required = tool["inputSchema"].get("required", [])
        assert "to" in required
        assert "subject" in required
        assert "body" in required


# ─── Manifest Tests ───────────────────────────────────────────────────────

class TestManifest:
    def test_manifest_structure(self):
        server = MCPEmailServer()
        manifest = server.manifest()
        assert manifest["server"]["name"] == "mcp-email-sender"
        assert len(manifest["tools"]) == 8

    def test_manifest_tools_match_defs(self):
        server = MCPEmailServer()
        manifest = server.manifest()
        manifest_names = {t["name"] for t in manifest["tools"]}
        def_names = {t["name"] for t in TOOL_DEFS}
        assert manifest_names == def_names


# ─── EmailValidator Tests ─────────────────────────────────────────────────

class TestEmailValidator:
    def test_valid_format(self):
        assert EmailValidator.validate_format("user@example.com") is True
        assert EmailValidator.validate_format("test.user+tag@sub.example.co.uk") is True

    def test_invalid_format(self):
        assert EmailValidator.validate_format("not-an-email") is False
        assert EmailValidator.validate_format("@example.com") is False
        assert EmailValidator.validate_format("user@") is False
        assert EmailValidator.validate_format("user@.com") is False
        assert EmailValidator.validate_format("") is False

    def test_extract_domain(self):
        assert EmailValidator.extract_domain("user@example.com") == "example.com"
        assert EmailValidator.extract_domain("test@MAIL.CO.UK") == "mail.co.uk"

    def test_extract_domain_no_at(self):
        assert EmailValidator.extract_domain("notanemail") is None

    def test_is_disposable(self):
        assert EmailValidator.is_disposable("user@mailinator.com") is True
        assert EmailValidator.is_disposable("test@guerrillamail.com") is True
        assert EmailValidator.is_disposable("user@gmail.com") is False
        assert EmailValidator.is_disposable("user@company.com") is False

    def test_is_role_based(self):
        assert EmailValidator.is_role_based("admin@company.com") is True
        assert EmailValidator.is_role_based("support@company.com") is True
        assert EmailValidator.is_role_based("info@company.com") is True
        assert EmailValidator.is_role_based("john@company.com") is False
        assert EmailValidator.is_role_based("user.name@gmail.com") is False

    def test_validate_full_valid(self):
        result = EmailValidator.validate("user@gmail.com")
        assert result["valid_format"] is True
        assert result["is_disposable"] is False
        assert result["is_role_based"] is False
        assert result["overall_valid"] is True
        assert result["domain"] == "gmail.com"

    def test_validate_disposable(self):
        result = EmailValidator.validate("user@mailinator.com")
        assert result["valid_format"] is True
        assert result["is_disposable"] is True
        assert result["overall_valid"] is False

    def test_validate_role_based(self):
        result = EmailValidator.validate("admin@company.com")
        assert result["is_role_based"] is True
        assert result["overall_valid"] is True  # role-based is still valid

    def test_validate_invalid_format(self):
        result = EmailValidator.validate("not-an-email")
        assert result["valid_format"] is False
        assert result["overall_valid"] is False

    def test_validate_batch(self):
        emails = ["user@gmail.com", "bad-email", "test@mailinator.com"]
        result = EmailValidator.validate_batch(emails)
        assert result["total"] == 3
        assert result["valid"] == 1  # only gmail.com
        assert result["invalid"] == 2
        assert len(result["results"]) == 3


# ─── EmailSender Tests (mocked SMTP) ──────────────────────────────────────

class TestEmailSender:
    def test_send_email_success(self):
        sender = EmailSender(host="smtp.test.com", port=587, username="user@test.com", password="pass")
        with patch("smtplib.SMTP") as mock_smtp:
            mock_server = MagicMock()
            mock_smtp.return_value = mock_server
            result = sender.send_email(
                to="recipient@example.com",
                subject="Test Subject",
                body="Hello World",
            )
            assert result["success"] is True
            assert result["to"] == "recipient@example.com"
            assert result["subject"] == "Test Subject"
            mock_server.login.assert_called_once_with("user@test.com", "pass")
            mock_server.sendmail.assert_called_once()
            mock_server.quit.assert_called_once()

    def test_send_email_html(self):
        sender = EmailSender(host="smtp.test.com", port=587)
        with patch("smtplib.SMTP") as mock_smtp:
            mock_server = MagicMock()
            mock_smtp.return_value = mock_server
            result = sender.send_email(
                to="recipient@example.com",
                subject="HTML Test",
                body="<h1>Hello</h1>",
                html=True,
            )
            assert result["success"] is True

    def test_send_email_with_cc_bcc(self):
        sender = EmailSender(host="smtp.test.com", port=587)
        with patch("smtplib.SMTP") as mock_smtp:
            mock_server = MagicMock()
            mock_smtp.return_value = mock_server
            result = sender.send_email(
                to="recipient@example.com",
                subject="Test",
                body="Hello",
                cc=["cc1@example.com", "cc2@example.com"],
                bcc=["bcc@example.com"],
            )
            assert result["success"] is True
            assert result["recipients_count"] == 4  # to + 2 cc + 1 bcc

    def test_send_email_auth_error(self):
        sender = EmailSender(host="smtp.test.com", port=587, username="user", password="wrong")
        with patch("smtplib.SMTP") as mock_smtp:
            mock_server = MagicMock()
            mock_server.login.side_effect = smtplib.SMTPAuthenticationError(535, b"Auth failed")
            mock_smtp.return_value = mock_server
            result = sender.send_email("to@example.com", "Test", "Body")
            assert result["success"] is False
            assert "Authentication" in result["error"]

    def test_send_email_connection_error(self):
        sender = EmailSender(host="bad.server.com", port=25)
        with patch("smtplib.SMTP", side_effect=ConnectionRefusedError("Connection refused")):
            result = sender.send_email("to@example.com", "Test", "Body")
            assert result["success"] is False
            assert "Connection refused" in result["error"]

    def test_send_batch(self):
        sender = EmailSender(host="smtp.test.com", port=587)
        with patch("smtplib.SMTP") as mock_smtp:
            mock_server = MagicMock()
            mock_smtp.return_value = mock_server
            emails = [
                {"to": "user1@example.com", "subject": "Test 1", "body": "Body 1"},
                {"to": "user2@example.com", "subject": "Test 2", "body": "Body 2"},
                {"to": "user3@example.com", "subject": "Test 3", "body": "Body 3"},
            ]
            result = sender.send_batch(emails)
            assert result["total"] == 3
            assert result["sent"] == 3
            assert result["failed"] == 0

    def test_test_connection_success(self):
        sender = EmailSender(host="smtp.test.com", port=587, username="user", password="pass")
        with patch("smtplib.SMTP") as mock_smtp:
            mock_server = MagicMock()
            mock_smtp.return_value = mock_server
            result = sender.test_connection()
            assert result["success"] is True
            assert result["host"] == "smtp.test.com"

    def test_test_connection_failure(self):
        sender = EmailSender(host="bad.server.com", port=25)
        with patch("smtplib.SMTP", side_effect=ConnectionRefusedError("No connection")):
            result = sender.test_connection()
            assert result["success"] is False
            assert "No connection" in result["error"]


# ─── Server Tool Dispatch Tests ───────────────────────────────────────────

class TestServerToolDispatch:
    def test_unknown_tool_returns_error(self):
        server = MCPEmailServer()
        result = json.loads(server.handle_tool_call("nonexistent", {}))
        assert "error" in result

    def test_missing_required_param(self):
        server = MCPEmailServer()
        result = json.loads(server.handle_tool_call("validate_email", {}))
        assert "error" in result

    def test_validate_email_dispatch(self):
        server = MCPEmailServer()
        result = json.loads(server.handle_tool_call("validate_email", {"email": "user@gmail.com"}))
        assert result["valid_format"] is True
        assert result["overall_valid"] is True

    def test_is_disposable_dispatch(self):
        server = MCPEmailServer()
        result = json.loads(server.handle_tool_call("is_disposable", {"email": "user@mailinator.com"}))
        assert result["is_disposable"] is True

    def test_is_role_based_dispatch(self):
        server = MCPEmailServer()
        result = json.loads(server.handle_tool_call("is_role_based", {"email": "admin@company.com"}))
        assert result["is_role_based"] is True

    def test_validate_batch_dispatch(self):
        server = MCPEmailServer()
        result = json.loads(server.handle_tool_call("validate_email_batch", {
            "emails": ["user@gmail.com", "bad-email"]
        }))
        assert result["total"] == 2
        assert result["valid"] == 1

    def test_send_email_dispatch(self):
        server = MCPEmailServer()
        with patch("smtplib.SMTP") as mock_smtp:
            mock_server = MagicMock()
            mock_smtp.return_value = mock_server
            result = json.loads(server.handle_tool_call("send_email", {
                "to": "recipient@example.com",
                "subject": "Test",
                "body": "Hello",
                "smtp_host": "smtp.test.com",
                "smtp_port": 587,
            }))
            assert result["success"] is True

    def test_test_smtp_connection_dispatch(self):
        server = MCPEmailServer()
        with patch("smtplib.SMTP") as mock_smtp:
            mock_server = MagicMock()
            mock_smtp.return_value = mock_server
            result = json.loads(server.handle_tool_call("test_smtp_connection", {
                "smtp_host": "smtp.test.com",
                "smtp_port": 587,
            }))
            assert result["success"] is True


# ─── STDIO Mode Tests ─────────────────────────────────────────────────────

class TestSTDIOMode:
    def test_manifest_flag_prints_json(self, capsys):
        from src.server import main
        with patch("sys.argv", ["server", "--manifest"]):
            main()
        captured = capsys.readouterr()
        output = captured.out.strip()
        parsed = json.loads(output)
        assert parsed["server"]["name"] == "mcp-email-sender"
