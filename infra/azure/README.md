# Azure Provisioning Option

Use this path only when the 1 Day Implementation requires automatic creation of new Azure infrastructure.

OpenClaw may coordinate the decision and validation, but Azure infrastructure code must stay optional and reviewed before use.

Recommended future contents:

- Terraform or Bicep module for resource group, network, VM, storage, and outputs.
- Cloud-init script for Docker, LiteLLM, Ollama or provider gateway setup.
- Cost estimate and teardown command.
- Security controls for SSH, TLS, Key Vault, logs, and least privilege RBAC.

Do not commit Azure credentials, customer identifiers, state files, or generated plans.

