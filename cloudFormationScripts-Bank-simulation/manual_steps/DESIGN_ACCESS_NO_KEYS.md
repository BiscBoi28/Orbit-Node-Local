# Design: Accessing EC2 When No SSH Keys or Access Keys Exist

## Scenario

- EC2 instances are created by CloudFormation (inventory comes from stack outputs).
- No key pairs or SSH access keys were configured for these machines.
- We still need to run configuration (Ansible: install software, register Wazuh).

## Options

| Approach | When to use | Requirements |
|----------|-------------|--------------|
| **SSH with key** | You have (or will create) a key pair and can set `SSH_PRIVATE_KEY_FILE` in config. | Key pair on instance, private key on control machine, security group allows SSH (22) from your IP. |
| **AWS Systems Manager (SSM)** | No key pairs; instances are already registered with SSM. | Instance profile with `AmazonSSMManagedInstanceCore`, SSM agent on instance, control machine has AWS credentials and session-manager plugin. |

This project supports **both**. Use SSM when you have no keys.

---

## How It Works

### 1. Pre-requirements (already in place)

- EC2 instance profile includes **AmazonSSMManagedInstanceCore**, so instances can be managed via SSM without SSH.
- Security groups allow SSH from AdminCIDR for the “key” path; SSM does not need inbound SSH.

### 2. Inventory: two modes

- **SSH mode** (default when `USE_SSM` is not set or is `false`):
  - Inventory uses **public IP** and `ansible_user` (e.g. `ec2-user`, `ubuntu`).
  - Ansible connects over SSH. Requires `SSH_PRIVATE_KEY_FILE` set to a valid `.pem` (or key-based auth).

- **SSM mode** (when `USE_SSM=true` in `config/deployment.env`):
  - Inventory uses **instance ID** as the target and `ansible_connection=community.aws.aws_ssm`.
  - Ansible runs commands through SSM (no SSH, no keys on the instance).
  - Control machine must have AWS CLI credentials and the **Session Manager plugin** installed.

### 3. Configuration step (e.g. `configure_machine_1.sh`)

- Regenerates inventory (so it picks up `USE_SSM` and current stack outputs).
- Runs Ansible; connection is either SSH or SSM depending on inventory.

---

## What You Need for SSM (no keys)

1. **Instance profile**  
   Already set: pre-requirements stack attaches a role with `AmazonSSMManagedInstanceCore` to EC2.

2. **SSM agent on instances**  
   Amazon Linux 2/2023 and Windows Server have it by default.

3. **Control machine (where you run Ansible)**  
   - AWS credentials (e.g. `AWS_PROFILE` / env) with permission to `ssm:StartSession` and related SSM APIs.  
   - [Session Manager plugin](https://docs.aws.amazon.com/systems-manager/latest/userguide/session-manager-working-with-install-plugin.html) installed.  
   - Ansible collection: `ansible-galaxy collection install community.aws` (or `amazon.aws` if using the redirected plugin).

4. **Config**  
   In `config/deployment.env`:
   - `USE_SSM=true`  
   - Leave `SSH_PRIVATE_KEY_FILE` empty (or omit).

5. **Ansible collection**  
   Install the AWS collection that provides the SSM connection plugin:
   ```bash
   ansible-galaxy collection install community.aws
   ```
   (On newer Ansible the plugin may live in `amazon.aws`; install `amazon.aws` if `community.aws.aws_ssm` is not found.)

6. **Session Manager plugin (control machine)**  
   Required for SSM sessions. Install per [AWS docs](https://docs.aws.amazon.com/systems-manager/latest/userguide/session-manager-working-with-install-plugin.html), e.g. on macOS:
   ```bash
   curl "https://s3.amazonaws.com/session-manager-downloads/plugin/latest/mac_arm64/sessionmanager-bundle.zip" -o "sessionmanager-bundle.zip"
   unzip sessionmanager-bundle.zip && sudo ./sessionmanager-bundle/install -i /usr/local/sessionmanagerplugin -b /usr/local/bin/session-manager-plugin
   ```

---

## Summary

| You have | Set in config | Result |
|----------|----------------|--------|
| No keys, SSM OK | `USE_SSM=true` | Inventory uses instance IDs and `aws_ssm`; Ansible runs over SSM. |
| A .pem for the instances | `SSH_PRIVATE_KEY_FILE=/path/to/key.pem` | Inventory uses IPs; Ansible runs over SSH with that key. |

Inventory is always generated from the same source (CloudFormation stacks); only the **connection method** (SSH vs SSM) and **target** (IP vs instance ID) change so you can run the 4th step with or without keys.
