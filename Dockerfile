FROM python:3.12-slim

WORKDIR /app

COPY src/ /app/src/
COPY tests/ /app/tests/
COPY README.md /app/README.md

CMD ["python", "-m", "src.server", "--stdio"]
