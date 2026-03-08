# ORBIT Deployment – Agent Starting Prompt

Copy everything between the dashes and use it as your opening message in Antigravity.
Point it at the `new-app` folder so it can see all files.

---

You are helping me deploy the ORBIT Node project to an AWS EC2 server.

## Your environment

- VS Code opened with `new-app` as the working directory
- WSL (Ubuntu) is the terminal — all commands run there, not PowerShell
- SSH key is already at `~/.ssh/iiith-orbit-key.pem` in WSL with correct permissions (400)
- `rsync`, `ssh`, and `aws` CLI are available in WSL
- AWS CLI has been configured with credentials (region: us-east-2)
- Target server: AWS EC2 named `orbit-dev`, region `us-east-2`, user `ubuntu`
- Current known IP: `16.58.158.189` — but always verify with `aws ec2 describe-instances` first as it may have changed

## Project structure

```
new-app/
├── app/                  ← ORC FastAPI application (do NOT modify)
├── fixtures/             ← bank CSV and wazuh JSON seed data
├── directives/           ← deployment instructions (00 through 07)
├── execution/            ← smoke_test.sh and bootstrap_ec2.sh
├── docker-compose.yml    ← needs ORC service added (Directive 03)
├── Dockerfile            ← complete, do not modify
├── requirements.txt
├── .env.example          ← reference only, never deploy
└── Neo4j/                ← old scripts, do NOT copy to server
```

## Read these files before doing anything

All in `new-app/directives/`:
- `00_OVERVIEW.md` — credentials, architecture, full directive index
- `01_access_and_server_start.md` through `07_runbook.md` — follow in order
- `execution/smoke_test.sh` and `execution/bootstrap_ec2.sh` — referenced by directives

## Instructions

Follow the directives in order starting with Directive 01.

Constraints:
- No GitHub access — use rsync from WSL to copy files to the server (covered in Directive 04)
- Skip Directive 06 (GitHub CI/CD) entirely — do it later when GitHub is available
- Never print, log, or commit the `.env` file
- Do NOT copy the `Neo4j/` folder to the server

How to work:
1. Before each step: tell me what you are about to do and why
2. Run the command in WSL and show me the full output
3. Check the "Done When" checklist before moving to the next directive
4. If something fails: read the error, fix it, tell me what changed, try again
5. After two failed attempts on the same step: stop and ask me

If you are ever unsure whether you are running in WSL or PowerShell, check with:
```bash
uname -a
```
It should say Linux. If it says anything else, switch to the WSL terminal before continuing.

---
