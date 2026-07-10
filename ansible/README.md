# Existing-server deployment

This playbook deploys the repository's Docker Compose LLM stack. It does not install OpenClaw itself.

```powershell
Copy-Item ansible/inventory.example.ini ansible/inventory.ini
ansible-playbook -i ansible/inventory.ini ansible/site.yml --syntax-check
ansible-playbook -i ansible/inventory.ini ansible/site.yml
$env:LITELLM_MASTER_KEY = '<at-least-32-random-characters>'
ansible-playbook -i ansible/inventory.ini ansible/site.yml -e deployment_apply=true
```

The normal run is a non-mutating Docker preflight. Apply mode copies the stack,
writes the secret with mode `0600`, validates Compose, and waits for health.
Ports remain on localhost; use authenticated TLS or a VPN for remote access.
