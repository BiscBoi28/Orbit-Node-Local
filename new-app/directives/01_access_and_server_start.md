# Directive 01 – Access orbit-dev and Start the Server if Offline

## What You Have

| Thing | Value |
|-------|-------|
| Instance name | `orbit-dev` |
| Public IP | `16.58.158.189` |
| Region | `us-east-2` |
| SSH key file | `iiith-orbit-key.pem` |
| SSH user | `ubuntu` |
| AWS Console login | username + password (for starting the instance if stopped) |

---

## Part A – Start the EC2 Instance if it is Offline

You only need this section if the server is stopped. If it's already running, skip to Part B.

### How to tell if the instance is stopped

```bash
aws ec2 describe-instances \
  --region us-east-2 \
  --filters "Name=ip-address,Values=16.58.158.189" \
  --query "Reservations[0].Instances[0].{State:State.Name,ID:InstanceId}" \
  --output table
```

If `State` shows `stopped` or `terminated`, continue below.
If it shows `running`, skip to Part B.

### Get the instance ID (needed to start it)

```bash
INSTANCE_ID=$(aws ec2 describe-instances \
  --region us-east-2 \
  --filters "Name=ip-address,Values=16.58.158.189" \
  --query "Reservations[0].Instances[0].InstanceId" \
  --output text)

echo "Instance ID: $INSTANCE_ID"
```

If the IP filter doesn't find it (the IP may change when stopped/started), search by name instead:

```bash
INSTANCE_ID=$(aws ec2 describe-instances \
  --region us-east-2 \
  --filters "Name=tag:Name,Values=orbit-dev" \
  --query "Reservations[0].Instances[0].InstanceId" \
  --output text)

echo "Instance ID: $INSTANCE_ID"
```

### Start the instance

```bash
aws ec2 start-instances \
  --region us-east-2 \
  --instance-ids $INSTANCE_ID
```

### Wait for it to be running

```bash
aws ec2 wait instance-running \
  --region us-east-2 \
  --instance-ids $INSTANCE_ID

echo "Instance is running"
```

This command blocks and returns only when the instance is fully running (usually 60–90 seconds).

### Get the new public IP (it may have changed after a stop/start)

```bash
aws ec2 describe-instances \
  --region us-east-2 \
  --instance-ids $INSTANCE_ID \
  --query "Reservations[0].Instances[0].PublicIpAddress" \
  --output text
```

> ⚠️ **Important:** AWS assigns a new public IP every time an instance starts unless it has an Elastic IP. 
> If the IP has changed, use the new IP for all subsequent SSH commands in this session.
> Update the `new-app/.env` file on the server if the Neo4j URI references this IP.

---

## Part B – One-Time WSL Key Setup

Your `.pem` key is currently on your Windows filesystem. You need to copy it into WSL
before SSH will work. **Do this once — you never need to do it again.**

### Find where the key is on your Windows filesystem

Inside WSL, your Windows drives are mounted under `/mnt/`. For example:
- `C:\Users\YourName\Downloads\iiith-orbit-key.pem` → `/mnt/c/Users/YourName/Downloads/iiith-orbit-key.pem`
- `C:\Users\YourName\Desktop\iiith-orbit-key.pem` → `/mnt/c/Users/YourName/Desktop/iiith-orbit-key.pem`

If you're not sure where it is, search from WSL:
```bash
find /mnt/c/Users -name "iiith-orbit-key.pem" 2>/dev/null
```

### Copy it into WSL and set correct permissions

```bash
# Create the .ssh directory if it doesn't exist
mkdir -p ~/.ssh

# Copy the key — replace the path with what you found above
cp /mnt/c/Users/YOUR_USERNAME/path/to/iiith-orbit-key.pem ~/.ssh/iiith-orbit-key.pem

# Set permissions — SSH refuses to use a key that anyone else can read
chmod 400 ~/.ssh/iiith-orbit-key.pem
```

### Verify it's in place

```bash
ls -la ~/.ssh/iiith-orbit-key.pem
# Should show: -r-------- ... iiith-orbit-key.pem
```

---

## Part C – Connect via SSH

### Connect

```bash
ssh -i ~/.ssh/iiith-orbit-key.pem ubuntu@16.58.158.189
```

Replace `16.58.158.189` with the new IP if it changed after a restart (from Part A above).

You should see an Ubuntu welcome message and a prompt like:
```
ubuntu@ip-172-xx-xx-xx:~$
```

Type `exit` to disconnect.

### Useful SSH shortcut (optional, saves typing)

Add this to `~/.ssh/config` on your local machine:
```
Host orbit-dev
    HostName 16.58.158.189
    User ubuntu
    IdentityFile ~/.ssh/iiith-orbit-key.pem
```

Then you can just type: `ssh orbit-dev`

> If the IP changes after a restart, update the `HostName` line.

---

## Part C – Check What's Currently Running on the Server

Once connected via SSH:

```bash
# See all running Docker containers
docker ps

# See all containers including stopped ones
docker ps -a

# Check disk space
df -h /

# Check memory
free -h
```

Make a note of what containers are running. This tells you what's already deployed
and what still needs to be set up (covered in Directive 04).

---

## Verification

- [ ] Can run `aws ec2 describe-instances` and see `orbit-dev` in the output
- [ ] Instance state is `running`
- [ ] `ssh -i ~/.ssh/iiith-orbit-key.pem ubuntu@<IP>` opens a shell prompt
- [ ] `docker ps` runs without errors inside the server

---

## Troubleshooting

**`Permission denied (publickey)` when SSH-ing:**
- The key file permissions are wrong. Run: `chmod 400 ~/.ssh/iiith-orbit-key.pem`
- Make sure you're using `ubuntu` as the username, not `ec2-user` or `root`

**`Connection timed out` or `Connection refused`:**
- The instance is stopped → follow Part A to start it
- Or the IP has changed → get the new IP from Part A

**AWS CLI says `Unable to locate credentials`:**
- Run `aws configure` and enter your AWS access key ID and secret (from your team's AWS account)
- Set the default region to `us-east-2`

**`aws ec2 start-instances` returns `UnauthorizedOperation`:**
- Your AWS CLI user doesn't have EC2 start permissions
- Use the AWS Console (browser) to start it instead: log in with your username/password at https://console.aws.amazon.com, go to EC2 → Instances, select `orbit-dev`, click Instance State → Start
