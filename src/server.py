"""MCP Server for email validation and SMTP sending.

Wraps EmailValidator + EmailSender in a Model Context Protocol server.
Agents can validate emails, check MX records, and send emails via SMTP.
"""
import json
import sys
import os
import argparse
from typing import Any, Dict, List, Optional

from .email_engine import EmailValidator, EmailSender


TOOL_DEFS = [
    {
        "name": "validate_email",
        "description": "Validate an email address — checks format, disposable domains, role-based addresses. Optionally checks MX records.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "email": {"type": "string", "description": "Email address to validate"},
                "check_mx": {"type": "boolean", "default": False, "description": "Check MX records (slower, network call)"}
            },
            "required": ["email"]
        }
    },
    {
        "name": "validate_email_batch",
        "description": "Validate multiple email addresses at once. Returns summary + per-email results.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "emails": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "List of email addresses to validate"
                },
                "check_mx": {"type": "boolean", "default": False, "description": "Check MX records for each"}
            },
            "required": ["emails"]
        }
    },
    {
        "name": "check_mx_records",
        "description": "Check MX (Mail Exchange) records for a domain. Returns list of MX servers with priorities.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "domain": {"type": "string", "description": "Domain to check (e.g. gmail.com)"}
            },
            "required": ["domain"]
        }
    },
    {
        "name": "is_disposable",
        "description": "Check if an email address uses a disposable email service (mailinator, guerrillamail, etc.).",
        "inputSchema": {
            "type": "object",
            "properties": {
                "email": {"type": "string", "description": "Email address to check"}
            },
            "required": ["email"]
        }
    },
    {
        "name": "is_role_based",
        "description": "Check if an email is a role-based address (admin@, info@, support@, etc.).",
        "inputSchema": {
            "type": "object",
            "properties": {
                "email": {"type": "string", "description": "Email address to check"}
            },
            "required": ["email"]
        }
    },
    {
        "name": "send_email",
        "description": "Send an email via SMTP. Requires SMTP server config in environment or args.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "to": {"type": "string", "description": "Recipient email address"},
                "subject": {"type": "string", "description": "Email subject"},
                "body": {"type": "string", "description": "Email body (plain text or HTML)"},
                "from": {"type": "string", "description": "Sender email (defaults to SMTP username)"},
                "html": {"type": "boolean", "default": False, "description": "Send as HTML"},
                "cc": {"type": "array", "items": {"type": "string"}, "description": "CC recipients"},
                "bcc": {"type": "array", "items": {"type": "string"}, "description": "BCC recipients"},
                "reply_to": {"type": "string", "description": "Reply-To address"},
                "smtp_host": {"type": "string", "description": "SMTP server host (or env SMTP_HOST)"},
                "smtp_port": {"type": "integer", "default": 25, "description": "SMTP server port"},
                "smtp_username": {"type": "string", "description": "SMTP username (or env SMTP_USERNAME)"},
                "smtp_password": {"type": "string", "description": "SMTP password (or env SMTP_PASSWORD)"},
                "use_tls": {"type": "boolean", "default": False, "description": "Use STARTTLS"},
                "use_ssl": {"type": "boolean", "default": False, "description": "Use SSL (port 465)"}
            },
            "required": ["to", "subject", "body"]
        }
    },
    {
        "name": "send_email_batch",
        "description": "Send multiple emails via SMTP in one call. Each email needs to, subject, body.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "emails": {
                    "type": "array",
                    "items": {
                        "type": "object",
                        "properties": {
                            "to": {"type": "string"},
                            "subject": {"type": "string"},
                            "body": {"type": "string"},
                            "from": {"type": "string"},
                            "html": {"type": "boolean"},
                            "cc": {"type": "array", "items": {"type": "string"}},
                            "bcc": {"type": "array", "items": {"type": "string"}},
                            "reply_to": {"type": "string"}
                        }
                    },
                    "description": "List of email objects to send"
                },
                "smtp_host": {"type": "string"},
                "smtp_port": {"type": "integer", "default": 25},
                "smtp_username": {"type": "string"},
                "smtp_password": {"type": "string"},
                "use_tls": {"type": "boolean", "default": False},
                "use_ssl": {"type": "boolean", "default": False}
            },
            "required": ["emails"]
        }
    },
    {
        "name": "test_smtp_connection",
        "description": "Test SMTP server connection without sending an email. Returns connection status.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "smtp_host": {"type": "string", "description": "SMTP server host (or env SMTP_HOST)"},
                "smtp_port": {"type": "integer", "default": 25},
                "smtp_username": {"type": "string"},
                "smtp_password": {"type": "string"},
                "use_tls": {"type": "boolean", "default": False},
                "use_ssl": {"type": "boolean", "default": False}
            }
        }
    },
]


class MCPEmailServer:
    """MCP server for email validation and sending."""

    def __init__(self, name: str = "mcp-email-sender", version: str = "1.0.0"):
        self.name = name
        self.version = version

    def _get_sender(self, args: Dict[str, Any]) -> EmailSender:
        """Create EmailSender from args or environment."""
        host = args.get("smtp_host") or os.environ.get("SMTP_HOST", "localhost")
        port = args.get("smtp_port", int(os.environ.get("SMTP_PORT", "25")))
        username = args.get("smtp_username") or os.environ.get("SMTP_USERNAME")
        password = args.get("smtp_password") or os.environ.get("SMTP_PASSWORD")
        use_tls = args.get("use_tls", os.environ.get("SMTP_TLS", "").lower() in ("true", "1", "yes"))
        use_ssl = args.get("use_ssl", os.environ.get("SMTP_SSL", "").lower() in ("true", "1", "yes"))
        return EmailSender(host=host, port=port, username=username, password=password,
                          use_tls=use_tls, use_ssl=use_ssl)

    def list_tools(self) -> List[Dict]:
        return TOOL_DEFS

    def manifest(self) -> Dict:
        return {
            "server": {"name": self.name, "version": self.version},
            "capabilities": {"tools": {"listChanged": False}, "resources": {}, "prompts": {}},
            "tools": self.list_tools(),
        }

    def handle_tool_call(self, name: str, args: Dict[str, Any]) -> str:
        try:
            if name == "validate_email":
                email = args["email"]
                check_mx = args.get("check_mx", False)
                result = EmailValidator.validate(email, check_mx=check_mx)
                return json.dumps(result)

            elif name == "validate_email_batch":
                emails = args["emails"]
                check_mx = args.get("check_mx", False)
                result = EmailValidator.validate_batch(emails, check_mx=check_mx)
                return json.dumps(result)

            elif name == "check_mx_records":
                domain = args["domain"]
                result = EmailValidator.check_mx_records(domain)
                return json.dumps(result)

            elif name == "is_disposable":
                email = args["email"]
                result = {"email": email, "is_disposable": EmailValidator.is_disposable(email)}
                return json.dumps(result)

            elif name == "is_role_based":
                email = args["email"]
                result = {"email": email, "is_role_based": EmailValidator.is_role_based(email)}
                return json.dumps(result)

            elif name == "send_email":
                sender = self._get_sender(args)
                result = sender.send_email(
                    to=args["to"],
                    subject=args["subject"],
                    body=args["body"],
                    from_addr=args.get("from") or args.get("from_addr"),
                    html=args.get("html", False),
                    cc=args.get("cc"),
                    bcc=args.get("bcc"),
                    reply_to=args.get("reply_to"),
                )
                return json.dumps(result)

            elif name == "send_email_batch":
                sender = self._get_sender(args)
                result = sender.send_batch(args["emails"])
                return json.dumps(result)

            elif name == "test_smtp_connection":
                sender = self._get_sender(args)
                result = sender.test_connection()
                return json.dumps(result)

            else:
                return json.dumps({"error": f"Unknown tool: {name}"})

        except KeyError as e:
            return json.dumps({"error": f"Missing required parameter: {e}", "tool": name})
        except Exception as e:
            return json.dumps({"error": str(e), "tool": name})


def _run_stdio():
    """Run the MCP server over stdin/stdout JSON-RPC."""
    server = MCPEmailServer()
    for line in sys.stdin:
        line = line.strip()
        if not line:
            continue
        try:
            request = json.loads(line)
        except json.JSONDecodeError:
            print(json.dumps({"jsonrpc": "2.0", "error": {"code": -32700, "message": "Parse error"}}), flush=True)
            continue

        method = request.get("method", "")
        req_id = request.get("id")
        params = request.get("params", {})

        if method == "initialize":
            response = {"jsonrpc": "2.0", "id": req_id, "result": {"server": server.name, "version": server.version}}
        elif method == "tools/list":
            response = {"jsonrpc": "2.0", "id": req_id, "result": {"tools": server.list_tools()}}
        elif method == "tools/call":
            tool_name = params.get("name", "")
            tool_args = params.get("arguments", {})
            result = server.handle_tool_call(tool_name, tool_args)
            response = {"jsonrpc": "2.0", "id": req_id, "result": {"content": [{"type": "text", "text": result}]}}
        elif method == "shutdown":
            response = {"jsonrpc": "2.0", "id": req_id, "result": {}}
            print(json.dumps(response), flush=True)
            break
        else:
            response = {"jsonrpc": "2.0", "id": req_id, "error": {"code": -32601, "message": f"Method not found: {method}"}}

        print(json.dumps(response), flush=True)


def main():
    parser = argparse.ArgumentParser(description="MCP Email Server")
    parser.add_argument("--stdio", action="store_true", help="Run in STDIO JSON-RPC mode")
    parser.add_argument("--manifest", action="store_true", help="Print server manifest and exit")
    args = parser.parse_args()

    if args.manifest:
        print(json.dumps(MCPEmailServer().manifest(), indent=2))
    elif args.stdio:
        _run_stdio()
    else:
        parser.print_help()


if __name__ == "__main__":
    main()
