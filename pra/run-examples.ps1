# Test à blanc (sans actions destructives)
.\Invoke-PRA.ps1 -ConfigPath .\backup-config.json -WhatIfMode

# Tests sans réseau ni restauration réelle
.\tests\Test-PraRecovery.ps1

# La restauration réelle exige -RestoreAction : voir PRA_V2_Operationnel.md.
