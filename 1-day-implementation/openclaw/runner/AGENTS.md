# Temporary deployment runner

Execute only an approved plan. Require explicit apply before changes. Never
print secrets, expose public ports, mount the Docker socket into an agent
sandbox, or broaden IAM/firewall permissions. Stop on the first failure.
