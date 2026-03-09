FROM python:3.11-slim

WORKDIR /srv

ENV PYTHONUNBUFFERED=1

RUN apt-get update && apt-get install -y curl && rm -rf /var/lib/apt/lists/*

COPY wazuh_mcp/requirements_mcp.txt ./wazuh_mcp/requirements_mcp.txt
RUN pip install --no-cache-dir -r ./wazuh_mcp/requirements_mcp.txt

COPY app/ ./app/
COPY Neo4j/ ./Neo4j/
COPY wazuh_mcp/ ./wazuh_mcp/
COPY wazuh/fixtures/ ./wazuh/fixtures/

EXPOSE 8001

CMD ["python", "-m", "wazuh_mcp.server"]
