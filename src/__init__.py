"""mcp-email-sender package — MCP server for email validation and SMTP sending."""
from .email_engine import EmailValidator, EmailSender
from .server import MCPEmailServer, TOOL_DEFS

__all__ = ["EmailValidator", "EmailSender", "MCPEmailServer", "TOOL_DEFS"]
__version__ = "1.0.0"
