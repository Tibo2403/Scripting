# Ansible Existing-Server Deployment

Use this path when the target server already exists, for example OVH, Hetzner, or a customer-owned Linux VM.

OpenClaw may select this method, but Ansible remains optional and external to the runtime application.

Suggested day-one flow:

1. Confirm written authorization and target inventory.
2. Run the repository audit scripts.
3. Review `ansible/site.yml`.
4. Execute Ansible from an operator workstation.
5. Run validation scripts and update `1-day-implementation/reports/installation-report.md`.

Keep inventories, credentials, SSH keys, customer IPs, and secrets out of Git.

