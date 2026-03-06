#!/bin/bash
# Simplified Wazuh setup - Uses official Wazuh Docker defaults
# Only customizes what's necessary for AWS deployment
set -e

# Region: use env (for local test) or EC2 metadata
export AWS_DEFAULT_REGION=${AWS_DEFAULT_REGION:-$(curl -s --connect-timeout 2 http://169.254.169.254/latest/meta-data/placement/region 2>/dev/null || echo "us-east-1")}
export DATA_MOUNT_PATH=${DATA_MOUNT_PATH:-/data}

# Fetch secrets
INDEXER_CREDS=$(aws secretsmanager get-secret-value --secret-id orbit/node/wazuh-indexer-credentials --query SecretString --output text 2>/dev/null) || true
export INDEXER_USERNAME=$(echo "$INDEXER_CREDS" | jq -r .username 2>/dev/null)
export INDEXER_PASSWORD=$(echo "$INDEXER_CREDS" | jq -r .password 2>/dev/null)
[ -z "$INDEXER_USERNAME" ] && export INDEXER_USERNAME=admin
[ -z "$INDEXER_PASSWORD" ] && export INDEXER_PASSWORD=SecretPassword

# Wazuh API credentials
export API_USERNAME=wazuh-wui
export API_PASSWORD="Wazuh@2024Pass"

WAZUH_DIR=${WAZUH_DIR:-/opt/wazuh-docker}
mkdir -p $WAZUH_DIR/config/wazuh_indexer_ssl_certs
mkdir -p $WAZUH_DIR/config/wazuh_indexer
mkdir -p $WAZUH_DIR/config/wazuh_dashboard
mkdir -p $DATA_MOUNT_PATH/wazuh $DATA_MOUNT_PATH/wazuh-indexer $DATA_MOUNT_PATH/orbit-node
chown -R 1000:1000 $DATA_MOUNT_PATH/wazuh-indexer 2>/dev/null || true

echo "=== Wazuh Simplified Setup ==="

# Create certs.yml
cat > $WAZUH_DIR/config/certs.yml << 'CERTS'
nodes:
  indexer:
    - name: wazuh.indexer
      ip: wazuh.indexer
  server:
    - name: wazuh.manager
      ip: wazuh.manager
  dashboard:
    - name: wazuh.dashboard
      ip: wazuh.dashboard
CERTS

# Generate certs
echo "[1/6] Generating SSL certificates..."
docker run --rm -v $WAZUH_DIR/config/wazuh_indexer_ssl_certs:/certificates \
  -v $WAZUH_DIR/config/certs.yml:/config/certs.yml \
  -e CERT_TOOL_VERSION=4.14 \
  wazuh/wazuh-certs-generator:0.0.3

# Create indexer config
cat > $WAZUH_DIR/config/wazuh_indexer/wazuh.indexer.yml << 'IDX'
network.host: "0.0.0.0"
node.name: "wazuh.indexer"
cluster.name: "wazuh-cluster"
path.data: /var/lib/wazuh-indexer
path.logs: /var/log/wazuh-indexer
discovery.type: single-node
plugins.security.ssl.http.pemcert_filepath: /usr/share/wazuh-indexer/config/certs/wazuh.indexer.pem
plugins.security.ssl.http.pemkey_filepath: /usr/share/wazuh-indexer/config/certs/wazuh.indexer.key
plugins.security.ssl.http.pemtrustedcas_filepath: /usr/share/wazuh-indexer/config/certs/root-ca.pem
plugins.security.ssl.transport.pemcert_filepath: /usr/share/wazuh-indexer/config/certs/wazuh.indexer.pem
plugins.security.ssl.transport.pemkey_filepath: /usr/share/wazuh-indexer/config/certs/wazuh.indexer.key
plugins.security.ssl.transport.pemtrustedcas_filepath: /usr/share/wazuh-indexer/config/certs/root-ca.pem
plugins.security.ssl.http.enabled: true
plugins.security.ssl.transport.enforce_hostname_verification: false
plugins.security.ssl.transport.resolve_hostname: false
plugins.security.authcz.admin_dn: ["CN=admin,OU=Wazuh,O=Wazuh,L=California,C=US"]
plugins.security.nodes_dn: ["CN=wazuh.indexer,OU=Wazuh,O=Wazuh,L=California,C=US"]
plugins.security.allow_default_init_securityindex: true
cluster.routing.allocation.disk.threshold_enabled: false
IDX

# internal_users - admin:SecretPassword
curl -sL "https://raw.githubusercontent.com/wazuh/wazuh-docker/v4.14.2/single-node/config/wazuh_indexer/internal_users.yml" -o $WAZUH_DIR/config/wazuh_indexer/internal_users.yml 2>/dev/null || cat > $WAZUH_DIR/config/wazuh_indexer/internal_users.yml << 'USERS'
_meta:
  type: "internalusers"
  config_version: 2
admin:
  hash: "$2y$12$K/SpwjtB.wOHJ/Nc6GVRDuc1h0rM1DfvziFRNPtk27P.c4yDr9njO"
  reserved: true
  backend_roles: ["admin"]
kibanaserver:
  hash: "$2a$12$4AcgAt3xwOWadA5s5blL6ev39OXDNhmOesEoo33eZtrq2N0YrU3H."
  reserved: true
USERS

# Dashboard config
cat > $WAZUH_DIR/config/wazuh_dashboard/opensearch_dashboards.yml << DASHCFG
server.host: 0.0.0.0
server.port: 5601
opensearch.hosts: https://wazuh.indexer:9200
opensearch.ssl.verificationMode: none
opensearch.ssl.certificateAuthorities: ["/usr/share/wazuh-dashboard/certs/root-ca.pem"]
opensearch.username: "admin"
opensearch.password: "SecretPassword"
opensearch.requestHeadersWhitelist: ["securitytenant","Authorization"]
opensearch_security.multitenancy.enabled: false
server.ssl.enabled: true
server.ssl.key: "/usr/share/wazuh-dashboard/certs/wazuh-dashboard-key.pem"
server.ssl.certificate: "/usr/share/wazuh-dashboard/certs/wazuh-dashboard.pem"
uiSettings.overrides.defaultRoute: /app/wz-home
DASHCFG

cat > $WAZUH_DIR/config/wazuh_dashboard/wazuh.yml << WAZUH_YAML
hosts:
  - default:
      url: "https://wazuh.manager"
      port: 55000
      username: "${API_USERNAME}"
      password: "${API_PASSWORD}"
      run_as: false
WAZUH_YAML

# Docker compose - SIMPLIFIED, uses Wazuh defaults for Filebeat
echo "[2/6] Creating docker-compose.yml..."
cd $WAZUH_DIR
cat > docker-compose.yml << 'COMPOSE'
version: '3.8'
services:
  wazuh.manager:
    image: wazuh/wazuh-manager:4.14.2
    hostname: wazuh.manager
    restart: always
    ports: 
      - "0.0.0.0:1514:1514"
      - "0.0.0.0:1515:1515"
      - "0.0.0.0:514:514/udp"
      - "127.0.0.1:55000:55000"
    environment:
      - INDEXER_URL=https://wazuh.indexer:9200
      - INDEXER_USERNAME=admin
      - INDEXER_PASSWORD=SecretPassword
      - FILEBEAT_SSL_VERIFICATION_MODE=full
      - SSL_CERTIFICATE_AUTHORITIES=/etc/ssl/root-ca.pem
      - SSL_CERTIFICATE=/etc/ssl/filebeat.pem
      - SSL_KEY=/etc/ssl/filebeat.key
      - API_USERNAME
      - API_PASSWORD
    volumes:
      - __DATA_MOUNT_PATH__/wazuh:/var/ossec/data
      - __WAZUH_DIR__/config/wazuh_indexer_ssl_certs/root-ca-manager.pem:/etc/ssl/root-ca.pem
      - __WAZUH_DIR__/config/wazuh_indexer_ssl_certs/wazuh.manager.pem:/etc/ssl/filebeat.pem
      - __WAZUH_DIR__/config/wazuh_indexer_ssl_certs/wazuh.manager-key.pem:/etc/ssl/filebeat.key
  wazuh.indexer:
    image: wazuh/wazuh-indexer:4.14.2
    hostname: wazuh.indexer
    restart: always
    ports: 
      - "127.0.0.1:9200:9200"
    environment:
      - "OPENSEARCH_JAVA_OPTS=-Xms512m -Xmx512m"
    ulimits:
      memlock:
        soft: -1
        hard: -1
      nofile:
        soft: 65536
        hard: 65536
    volumes:
      - __DATA_MOUNT_PATH__/wazuh-indexer:/var/lib/wazuh-indexer
      - __WAZUH_DIR__/config/wazuh_indexer_ssl_certs/root-ca.pem:/usr/share/wazuh-indexer/config/certs/root-ca.pem
      - __WAZUH_DIR__/config/wazuh_indexer_ssl_certs/wazuh.indexer-key.pem:/usr/share/wazuh-indexer/config/certs/wazuh.indexer.key
      - __WAZUH_DIR__/config/wazuh_indexer_ssl_certs/wazuh.indexer.pem:/usr/share/wazuh-indexer/config/certs/wazuh.indexer.pem
      - __WAZUH_DIR__/config/wazuh_indexer_ssl_certs/admin.pem:/usr/share/wazuh-indexer/config/certs/admin.pem
      - __WAZUH_DIR__/config/wazuh_indexer_ssl_certs/admin-key.pem:/usr/share/wazuh-indexer/config/certs/admin-key.pem
      - __WAZUH_DIR__/config/wazuh_indexer/wazuh.indexer.yml:/usr/share/wazuh-indexer/config/opensearch.yml
      - __WAZUH_DIR__/config/wazuh_indexer/internal_users.yml:/usr/share/wazuh-indexer/config/opensearch-security/internal_users.yml
  wazuh.dashboard:
    image: wazuh/wazuh-dashboard:4.14.2
    hostname: wazuh.dashboard
    restart: always
    ports: 
      - "127.0.0.1:5601:5601"
    environment:
      - INDEXER_USERNAME=admin
      - INDEXER_PASSWORD=SecretPassword
      - WAZUH_API_URL=https://wazuh.manager
      - API_USERNAME
      - API_PASSWORD
    volumes:
      - __WAZUH_DIR__/config/wazuh_indexer_ssl_certs/wazuh.dashboard.pem:/usr/share/wazuh-dashboard/certs/wazuh-dashboard.pem
      - __WAZUH_DIR__/config/wazuh_indexer_ssl_certs/wazuh.dashboard-key.pem:/usr/share/wazuh-dashboard/certs/wazuh-dashboard-key.pem
      - __WAZUH_DIR__/config/wazuh_indexer_ssl_certs/root-ca.pem:/usr/share/wazuh-dashboard/certs/root-ca.pem
      - __WAZUH_DIR__/config/wazuh_dashboard/opensearch_dashboards.yml:/usr/share/wazuh-dashboard/config/opensearch_dashboards.yml
      - __WAZUH_DIR__/config/wazuh_dashboard/wazuh.yml:/usr/share/wazuh-dashboard/config/wazuh.yml
    depends_on:
      - wazuh.indexer
    links:
      - wazuh.indexer:wazuh.indexer
      - wazuh.manager:wazuh.manager
COMPOSE

sed -i.bak "s|__DATA_MOUNT_PATH__|$DATA_MOUNT_PATH|g" docker-compose.yml && rm -f docker-compose.yml.bak
sed -i.bak "s|__WAZUH_DIR__|$WAZUH_DIR|g" docker-compose.yml && rm -f docker-compose.yml.bak

# Write .env
API_USERNAME_SAFE=$(printf '%s' "$API_USERNAME" | tr -d '\n\r')
API_PASSWORD_SAFE=$(printf '%s' "$API_PASSWORD" | tr -d '\n\r' | sed 's/"/\\"/g')
printf 'API_USERNAME=%s\nAPI_PASSWORD="%s"\n' "$API_USERNAME_SAFE" "$API_PASSWORD_SAFE" > "$WAZUH_DIR/.env"
chmod 600 "$WAZUH_DIR/.env" 2>/dev/null || true

# Stop old containers
echo "[3/6] Stopping old containers..."
cd /opt/orbit-node 2>/dev/null && docker compose down 2>/dev/null || true
docker ps -q --filter "name=wazuh" | xargs -r docker stop 2>/dev/null || true
docker ps -aq --filter "name=wazuh" | xargs -r docker rm 2>/dev/null || true

# Ensure indexer volume has correct permissions
chown -R 1000:1000 $DATA_MOUNT_PATH/wazuh-indexer 2>/dev/null || true

# Start services
echo "[4/6] Starting Wazuh services..."
cd $WAZUH_DIR
docker compose up -d

# Wait for containers
sleep 30
FAILED=""
for svc in wazuh.manager wazuh.indexer wazuh.dashboard; do
  if ! docker ps --filter "name=$svc" --format '{{.Names}}' | grep -q .; then
    FAILED="$FAILED $svc"
  fi
done
if [ -n "$FAILED" ]; then
  echo "ERROR: Containers did not start:$FAILED" >&2
  docker ps -a --filter "name=wazuh" >&2
  exit 1
fi
echo "✓ All containers running"

# Wait for indexer
echo "[5/6] Waiting for indexer..."
for i in $(seq 1 60); do
  if curl -sk https://127.0.0.1:9200 -u admin:SecretPassword 2>/dev/null | grep -q cluster_name; then
    echo "✓ Indexer ready"
    break
  fi
  sleep 5
done

# Run securityadmin
INDEXER_CONTAINER=$(docker ps -q --filter "name=wazuh.indexer")
if [ -n "$INDEXER_CONTAINER" ]; then
  sleep 10
  docker exec $INDEXER_CONTAINER bash -c 'export JAVA_HOME=/usr/share/wazuh-indexer/jdk && /usr/share/wazuh-indexer/plugins/opensearch-security/tools/securityadmin.sh -cd /usr/share/wazuh-indexer/config/opensearch-security/ -icl -nhnv -cacert /usr/share/wazuh-indexer/config/certs/root-ca.pem -cert /usr/share/wazuh-indexer/config/certs/admin.pem -key /usr/share/wazuh-indexer/config/certs/admin-key.pem -h 127.0.0.1 -p 9200' 2>/dev/null || true
  DASHBOARD_CONTAINER=$(docker ps -q --filter "name=wazuh.dashboard")
  [ -n "$DASHBOARD_CONTAINER" ] && docker restart $DASHBOARD_CONTAINER 2>/dev/null || true
fi

# Nginx config
echo "[6/6] Configuring Nginx..."
if [ -z "${SKIP_NGINX}" ] && command -v nginx >/dev/null 2>&1; then
mkdir -p /etc/nginx/ssl
[ ! -f /etc/nginx/ssl/nginx.crt ] && openssl req -x509 -nodes -days 365 -newkey rsa:2048 -keyout /etc/nginx/ssl/nginx.key -out /etc/nginx/ssl/nginx.crt -subj "/CN=orbit-node"
cat > /etc/nginx/sites-available/orbit-node << 'NGINX'
upstream wazuh_dashboard { server 127.0.0.1:5601; }

server {
  listen 80;
  server_name _;
  return 302 https://$host$request_uri;
}

server {
  listen 443 ssl http2;
  server_name _;
  
  ssl_certificate /etc/nginx/ssl/nginx.crt;
  ssl_certificate_key /etc/nginx/ssl/nginx.key;
  ssl_protocols TLSv1.2 TLSv1.3;
  ssl_ciphers HIGH:!aNULL:!MD5;
  
  proxy_buffer_size 128k;
  proxy_buffers 4 256k;
  proxy_busy_buffers_size 256k;
  
  location / {
    proxy_pass https://wazuh_dashboard;
    proxy_ssl_verify off;
    proxy_set_header Host $host;
    proxy_set_header X-Real-IP $remote_addr;
    proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
    proxy_set_header X-Forwarded-Proto $scheme;
    proxy_http_version 1.1;
    proxy_set_header Upgrade $http_upgrade;
    proxy_set_header Connection "upgrade";
    proxy_connect_timeout 300s;
    proxy_send_timeout 300s;
    proxy_read_timeout 300s;
    proxy_buffering off;
  }
}
NGINX

ln -sf /etc/nginx/sites-available/orbit-node /etc/nginx/sites-enabled/
rm -f /etc/nginx/sites-enabled/default
nginx -t && systemctl restart nginx 2>/dev/null || true
fi

echo ""
echo "=== Setup Complete ==="
echo "Indexer: admin/SecretPassword"
echo "API: ${API_USERNAME}/${API_PASSWORD}"
echo ""
echo "Waiting 30 seconds for Filebeat to start processing alerts..."
sleep 30

# Check if alerts index was created
if curl -sk -u admin:SecretPassword https://127.0.0.1:9200/_cat/indices 2>/dev/null | grep -q "wazuh-alerts"; then
  echo "✓ Alerts index created successfully"
else
  echo "⚠ Alerts index not yet created (may take a few minutes)"
fi

echo ""
echo "Dashboard: https://$(curl -s http://169.254.169.254/latest/meta-data/public-ipv4 2>/dev/null || echo 'YOUR_IP')"
