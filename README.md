# MCP Email Sender — Email Validation & SMTP for AI Agents

> An MCP (Model Context Protocol) server that gives AI agents the ability to validate email addresses, check MX records, detect disposable/role-based emails, and send emails via SMTP — all with zero external dependencies.

## Features

- **8 MCP Tools**: `validate_email`, `validate_email_batch`, `check_mx_records`, `is_disposable`, `is_role_based`, `send_email`, `send_email_batch`, `test_smtp_connection`
- **Zero dependencies** — pure Python stdlib (smtplib, email, re, socket)
- **Email validation** — format check, disposable detection, role-based detection, MX record lookup
- **Batch operations** — validate or send multiple emails in one call
- **SMTP support** — TLS, SSL, plain, with CC/BCC/Reply-To
- **STDIO JSON-RPC mode** — drop-in for Claude Desktop, Hermes, or any MCP client
- **Environment-based config** — SMTP credentials from env vars or tool args

## Quick Start

```bash
# STDIO mode (for MCP clients)
python -m src.server --stdio

# Print manifest
python -m src.server --manifest
```

### Use as a library

```python
from src.server import MCPEmailServer
import json

server = MCPEmailServer()

# Validate email
result = server.handle_tool_call("validate_email", {"email": "user@gmail.com"})
print(json.loads(result))  # {"valid_format": true, "overall_valid": true, ...}

# Batch validate
result = server.handle_tool_call("validate_email_batch", {
    "emails": ["user@gmail.com", "test@mailinator.com", "bad-email"]
})

# Send email
result = server.handle_tool_call("send_email", {
    "to": "recipient@example.com",
    "subject": "Hello from AI",
    "body": "This email was sent by an AI agent via MCP.",
    "smtp_host": "smtp.gmail.com",
    "smtp_port": 587,
    "smtp_username": "your@gmail.com",
    "smtp_password": "app-password",
    "use_tls": True
})
```

## MCP Tool Reference

| Tool | Description | Required Params |
|------|-------------|-----------------|
| `validate_email` | Full validation (format, disposable, role, MX) | `email` |
| `validate_email_batch` | Batch validate multiple emails | `emails` |
| `check_mx_records` | MX records for a domain | `domain` |
| `is_disposable` | Check if disposable email service | `email` |
| `is_role_based` | Check if role-based (admin@, info@) | `email` |
| `send_email` | Send via SMTP | `to`, `subject`, `body` |
| `send_email_batch` | Send multiple emails | `emails` |
| `test_smtp_connection` | Test SMTP server connection | — |

## SMTP Configuration

Set via environment variables or pass in tool args:

```bash
export SMTP_HOST=smtp.gmail.com
export SMTP_PORT=587
export SMTP_USERNAME=your@gmail.com
export SMTP_PASSWORD=your-app-password
export SMTP_TLS=true
```

## Integration with Claude Desktop

```json
{
  "mcpServers": {
    "email-sender": {
      "command": "python",
      "args": ["-m", "src.server", "--stdio"],
      "cwd": "/path/to/mcp-email-sender",
      "env": {
        "SMTP_HOST": "smtp.gmail.com",
        "SMTP_PORT": "587",
        "SMTP_USERNAME": "your@gmail.com",
        "SMTP_PASSWORD": "your-app-password",
        "SMTP_TLS": "true"
      }
    }
  }
}
```

## Tests

```bash
python -m pytest tests/ -v  # 37 tests, all passing
```

## License

MIT

## Author

AMEOBIUS — [github.com/AMEOBIUS](https://github.com/AMEOBIUS)
