# Tomorrow Handoff

This file is the restart point for the next implementation session.

## Current State

- OpenClaw is documented as a temporary coordinator only.
- Codex remains optional.
- `install.ps1` supports `Local`, `DockerCompose`, `Ansible`, `AWS`, and `Azure`.
- `docker-compose.yml` exists as the first portable application-stack option.
- `ansible/` exists for existing OVH, Hetzner, or client Linux servers.
- `infra/aws/` and `infra/azure/` exist only for automatic cloud provisioning.

## First Commands To Run

```powershell
git status --short --branch
.\1-day-implementation\scripts\audit_repo.ps1
.\1-day-implementation\scripts\install.ps1 -Mode DockerCompose -NoCodex
.\1-day-implementation\scripts\run_tests.ps1
.\1-day-implementation\scripts\validate_installation.ps1
```

## Next Work In Order

1. Make the Docker Compose path usable for a real one-day pilot:
   - add `.env.example`;
   - add a minimal LiteLLM config;
   - add health checks;
   - document required secrets and ports.
2. Extend the Ansible path only for existing Linux servers:
   - Docker installation checks;
   - firewall checks;
   - service startup;
   - validation command.
3. Add AWS or Azure provisioning only if the customer wants automatic cloud creation.
4. Run quick validations.
5. Commit and push the final day-one deployment path.

## Do Not Do Yet

- Do not make OpenClaw a runtime dependency.
- Do not commit credentials, customer IPs, state files, or generated cloud plans.
- Do not expose LiteLLM or Open WebUI publicly without authentication, TLS, and firewall rules.
- Do not build AWS and Azure automation unless a provider is chosen.

## Done When

- A new operator can choose one deployment mode in under five minutes.
- The selected mode has one documented command path.
- Validation scripts run cleanly.
- The final report records the method, commands, risks, and rollback notes.
