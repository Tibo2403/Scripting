# AWS Provisioning Option

Use this path only when the 1 Day Implementation requires automatic creation of new AWS infrastructure.

OpenClaw may coordinate the decision and validation, but AWS infrastructure code must stay optional and reviewed before use.

Recommended future contents:

- Terraform or OpenTofu module for VPC, security groups, VM, storage, and outputs.
- Cloud-init script for Docker, LiteLLM, Ollama or provider gateway setup.
- Cost estimate and teardown command.
- Security controls for SSH, TLS, secrets, logs, and least privilege IAM.

Do not commit AWS credentials, customer identifiers, state files, or generated plans.

