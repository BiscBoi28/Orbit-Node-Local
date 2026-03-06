# Wazuh Ansible Deployment

## Structure

```
04-wazuh-ansible/
├── inventory/
│   ├── local.yml          # For local testing
│   └── ec2.yml            # For EC2 deployment
├── group_vars/
│   └── all.yml            # Configuration variables
├── templates/
│   ├── certs.yml.j2
│   ├── wazuh.indexer.yml.j2
│   ├── opensearch_dashboards.yml.j2
│   ├── wazuh.yml.j2
│   ├── docker-compose.yml.j2
│   └── nginx-wazuh.conf.j2
├── install-wazuh.yml      # Main playbook
└── README.md
```

## Prerequisites

The scripts will automatically install:
- `uv` - Fast Python package manager
- `ansible` - Via uv
- `community.docker` collection

Or install manually:

```bash
# Install uv
curl -LsSf https://astral.sh/uv/install.sh | sh

# Install Ansible via uv
uv tool install ansible

# Install required collections
uv tool run ansible-galaxy collection install community.docker
```

## Configuration

Edit `group_vars/all.yml` to customize:
- Wazuh credentials
- Installation paths
- Versions
- Memory settings

## Usage

### Test Locally (macOS/Linux with Docker)

```bash
# Run against localhost
./run-local.sh
```

### Deploy to EC2

1. Update `inventory/ec2.yml` with your EC2 IP and SSH key
2. Run deployment:

```bash
./run-ec2.sh
```

### Manual Commands

```bash
# Check syntax
uv tool run ansible-playbook install-wazuh.yml --syntax-check

# Dry run
uv tool run ansible-playbook -i inventory/ec2.yml install-wazuh.yml --check

# Run with verbose output
uv tool run ansible-playbook -i inventory/ec2.yml install-wazuh.yml -vvv
```

## Access

After deployment:
- Dashboard: https://YOUR_IP
- Username: admin (default)
- Password: SecretPassword (default)

Change credentials in `group_vars/all.yml` before deployment.
