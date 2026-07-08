# Deployment Method Router

OpenClaw acts as the temporary decision layer for the 1 Day Implementation workflow.

It must choose the smallest deployment method that fits the customer context:

| Method | Use when | Repository entry point |
| --- | --- | --- |
| Local | Fast manual setup on a known machine | `1-day-implementation/scripts/install.ps1 -Mode Local` |
| Docker Compose | Single VPS, OVH, Hetzner, lab, or portable demo stack | `docker-compose.yml` |
| Ansible | Existing Linux server owned by OVH, Hetzner, or a client | `ansible/site.yml` |
| AWS | New AWS infrastructure must be provisioned automatically | `infra/aws/` |
| Azure | New Azure infrastructure must be provisioned automatically | `infra/azure/` |

OpenClaw coordinates the method choice, task split, validation scripts, test checks, and final report only. The deployed project must remain usable without OpenClaw.

