# Infrastructure Deploy

## Goal

Deploy or tear down the ORBIT Node AWS sandbox (wazuh-dev + orbit-dev EC2 stacks).

## Inputs

- AWS CLI configured with appropriate IAM permissions.
- Key pair `iiith-orbit-key` in `~/.ssh/`.

## Execution — Deploy

### wazuh-dev (deploy first)

```bash
cd cloudFormationScripts-wazuh/01-pre-deployment && bash create-pre-deployment-stack.sh
cd ../02-secrets && bash create-secrets-stack.sh
cd ../03-ec2-deployment && bash deploy-ec2-stack.sh
cd ../04a-wazuh-ansible-customized && bash run-ec2.sh
```

### orbit-dev

```bash
cd cloudFormationScripts-orbit-dev/01-pre-deployment && bash create-pre-deployment-stack.sh
cd ../02-ec2-deployment && bash deploy-ec2-stack.sh
```

## Execution — Teardown

Delete stacks in **reverse** order. See `README.md §Teardown` for exact commands.

> **Warning:** Deleting pre-deployment stacks releases Elastic IPs permanently.

## Outputs

- Running EC2 instances accessible via SSH or SSM.
- Services healthy (check with `sudo bash /data/scripts/health-check.sh`).

## Edge Cases / Learnings

- Neo4j slow on first boot (APOC download) — allow 2-3 min.
- Presidio slow on first boot (spaCy model download) — allow 3-5 min.
- If Docker not ready at boot, manually run `sudo docker compose -f /data/orbit-dev/docker-compose.yml up -d`.
