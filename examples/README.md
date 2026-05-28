# Examples

These files are safe placeholders for local labs and documentation.

- `targets.lab.txt` - example target list for an isolated lab.
- `stealth_post.conf.example` - example local-only FTPS configuration.
- `users.import.csv` - sample CSV shape for `UserManagement.ps1` lab imports using encrypted password strings.

Generate an `EncryptedPassword` value on the target machine:

```powershell
Read-Host -AsSecureString | ConvertFrom-SecureString
```

Do not commit real targets, credentials, tenant names, scan output, packet captures, or customer data.
