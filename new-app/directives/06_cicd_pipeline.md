# Directive 06 – GitHub Actions CI/CD Pipeline

## Goal

After this directive, every time anyone on your team pushes code to the `main` branch,
GitHub automatically deploys it to orbit-dev and confirms it's healthy.

Your team sees a ✅ or ❌ in the GitHub Actions tab — no manual steps needed.

**Do this directive last.** The system should already be fully working before you set this up.

---

## Prerequisites

- [ ] Directives 01–05 complete — full system running, smoke tests passing
- [ ] `new-app` code is in a GitHub repository
- [ ] You have admin access to that repository (to add Secrets)
- [ ] GitHub is available again

---

## Before You Start: Push new-app to GitHub

If your `new-app` code hasn't been pushed to GitHub yet, do that first.

### If you have an empty GitHub repo already

```bash
# On your laptop, inside the new-app folder
cd /path/to/your/new-app

git init                        # only needed if not already a git repo
git add .
git commit -m "initial commit"
git branch -M main
git remote add origin https://github.com/YOUR_TEAM/YOUR_REPO.git
git push -u origin main
```

### If you're not sure whether it's already there

Go to your GitHub repository in a browser and check if `app/`, `fixtures/`,
`docker-compose.yml`, and `Dockerfile` are visible. If yes, it's already there.

---

## How the Pipeline Works

```
Someone pushes code to main on GitHub
              │
              ▼
GitHub Actions starts a runner (a temporary Linux machine)
              │
              ▼
Runner SSHes into orbit-dev
              │
              ▼
orbit-dev: git pull → docker compose build orc → docker compose up
              │
              ▼
Health check: curl /health
              │
              ▼
GitHub shows ✅ (pass) or ❌ (fail) in the Actions tab
```

---

## Step 1 – Store the SSH Key as a GitHub Secret

GitHub Actions needs the `.pem` key to SSH into orbit-dev.
It's stored as an encrypted secret — never visible after you save it.

1. On your laptop, print the contents of the key file:
   ```bash
   cat ~/.ssh/iiith-orbit-key.pem
   ```
2. Copy the entire output — including the `-----BEGIN RSA PRIVATE KEY-----`
   and `-----END RSA PRIVATE KEY-----` lines.
3. Go to your GitHub repository in a browser.
4. Click **Settings** → **Secrets and variables** → **Actions**.
5. Click **New repository secret** and add each of these:

| Secret Name       | Value |
|-------------------|-------|
| `SSH_PRIVATE_KEY` | The full contents of `iiith-orbit-key.pem` (copied in step 2) |
| `SSH_HOST`        | `16.58.158.189` |
| `SSH_USER`        | `ubuntu` |

---

## Step 2 – Create the GitHub Actions Workflow File

Create this file on your laptop at exactly this path inside your repo:
`.github/workflows/deploy.yml`

(You'll need to create the `.github/workflows/` folders if they don't exist.)

```yaml
# .github/workflows/deploy.yml
# Automatically deploys ORBIT to orbit-dev on every push to main

name: Deploy to orbit-dev

on:
  push:
    branches:
      - main

jobs:
  deploy:
    name: Deploy via SSH
    runs-on: ubuntu-latest

    steps:
      - name: Checkout code
        uses: actions/checkout@v4

      - name: Set up SSH key
        run: |
          mkdir -p ~/.ssh
          echo "${{ secrets.SSH_PRIVATE_KEY }}" > ~/.ssh/deploy_key
          chmod 400 ~/.ssh/deploy_key
          ssh-keyscan -H ${{ secrets.SSH_HOST }} >> ~/.ssh/known_hosts

      - name: Deploy to orbit-dev
        run: |
          ssh -i ~/.ssh/deploy_key ${{ secrets.SSH_USER }}@${{ secrets.SSH_HOST }} '
            set -e
            cd ~/orbit
            git pull origin main
            docker compose build orc
            docker compose up -d --no-deps orc
            echo "Deploy complete"
          '

      - name: Verify health check
        run: |
          # Give ORC 30 seconds to restart
          sleep 30

          ssh -i ~/.ssh/deploy_key ${{ secrets.SSH_USER }}@${{ secrets.SSH_HOST }} '
            HTTP_CODE=$(curl -s -o /dev/null -w "%{http_code}" http://localhost:8000/health)
            echo "HTTP status: $HTTP_CODE"
            if [ "$HTTP_CODE" = "200" ]; then
              echo "HEALTH CHECK PASSED"
            else
              echo "HEALTH CHECK FAILED"
              exit 1
            fi
          '
```

**What `--no-deps orc` means:** Only ORC is rebuilt and restarted. Neo4j and Presidio
are left running — their data is untouched. This makes deployments fast and safe.

---

## Step 3 – Handle the IP Change Problem

The `SSH_HOST` secret contains the server's current IP (`16.58.158.189`).
If the server is ever stopped and restarted, AWS will give it a new IP.

**Recommended fix: request an Elastic IP from whoever manages your AWS account.**
An Elastic IP is a fixed IP address that stays the same even after restarts — it's free
as long as it's attached to a running instance. Ask your team's AWS admin to attach one
to orbit-dev.

**In the meantime:** if the IP changes, update the `SSH_HOST` secret in GitHub
(Settings → Secrets → Actions → SSH_HOST → Update) and you're good.

---

## Step 4 – Commit and Push

```bash
git add .github/workflows/deploy.yml
git commit -m "feat: add GitHub Actions auto-deploy"
git push
```

This push itself will trigger the first deployment. Watch it in the Actions tab.

---

## Step 5 – Watch the First Deployment

1. Go to your GitHub repository
2. Click the **Actions** tab at the top
3. You'll see a workflow run called "Deploy to orbit-dev" — click it
4. You can see live logs from each step

✅ Green = deployed and health check passed
❌ Red = something failed — click the failed step to see the exact error

---

## Verification

### Confirm the server has the latest code after a push

SSH into the server and check:
```bash
ssh -i ~/.ssh/iiith-orbit-key.pem ubuntu@16.58.158.189
cd ~/orbit
git log --oneline -3
```

The top commit should match the latest commit shown on your GitHub `main` branch.

---

## Done When

- [ ] `new-app` code is in a GitHub repository
- [ ] Three GitHub Secrets added: `SSH_PRIVATE_KEY`, `SSH_HOST`, `SSH_USER`
- [ ] `.github/workflows/deploy.yml` committed and pushed
- [ ] First automated deploy shows ✅ in the GitHub Actions tab
- [ ] Health check passes after automated deploy
- [ ] Team can see deploy status by visiting the Actions tab

---

## Troubleshooting

**`Permission denied (publickey)` in the Actions log:**
- The `SSH_PRIVATE_KEY` secret wasn't copied correctly.
- Make sure you copied the entire key file including the header and footer lines.
- Re-save the secret: Settings → Secrets → SSH_PRIVATE_KEY → Update.

**`Connection refused` or `Connection timed out`:**
- The server IP has changed after a restart. Update the `SSH_HOST` secret with the new IP.
- Get the new IP: `aws ec2 describe-instances --region us-east-2 --filters "Name=tag:Name,Values=orbit-dev" --query "Reservations[0].Instances[0].PublicIpAddress" --output text`

**`git pull` fails with `not a git repository`:**
- The code on the server was copied via rsync (not cloned from GitHub).
- Fix: SSH in, then initialise git and link it to the repo:
  ```bash
  cd ~/orbit
  git init
  git remote add origin https://github.com/YOUR_TEAM/YOUR_REPO.git
  git fetch
  git checkout main
  ```
  Then re-run the deploy from GitHub Actions.

**Deploy succeeds but health check fails:**
- ORC crashed after restart. Check logs:
  ```bash
  ssh -i ~/.ssh/iiith-orbit-key.pem ubuntu@16.58.158.189
  cd ~/orbit
  docker compose logs --tail=50 orc
  ```
