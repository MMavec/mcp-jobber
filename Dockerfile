FROM python:3.12-slim

WORKDIR /app
COPY . /app

RUN pip install --no-cache-dir .

# MCP servers speak JSON-RPC over stdio. CMD (not ENTRYPOINT) so a host like
# Smithery can override it via its own command without argument clashes.
CMD ["mcp-jobber"]
