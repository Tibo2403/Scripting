# Test à blanc (sans actions destructives)
.\Invoke-PRA.ps1 -ConfigPath .\backup-config.json -WhatIfMode

# Exécution réelle
.\Invoke-PRA.ps1 -ConfigPath .\backup-config.json
