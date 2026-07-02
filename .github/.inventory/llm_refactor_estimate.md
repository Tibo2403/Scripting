# LLM Refactor Inventory (quick)

> Hidden inventory file for rapid planning.

## Repository
- Name: `Tibo2403/Scripting`
- Main languages: Python (44.1%), PowerShell (39.2%), Shell (16.7%)
- Goal: estimate effort to rework scripts with LLM-assisted refactoring

## Time box (requested)
- Total budget: 5 minutes
- Allocation: **2.5 min** for this repository

## Quick inventory targets
1. Python scripts
   - Normalize CLI entrypoints
   - Add lightweight typing on key functions
   - Group helpers by domain
2. PowerShell scripts
   - Standardize parameter blocks and verbose/error behavior
   - Extract repeated logic into reusable functions
3. Shell scripts
   - Add `set -euo pipefail` where safe
   - Improve quoting and path handling consistency

## LLM technology options (for retravail)
- GPT-4.1 / GPT-4o style assistants: broad refactor + doc generation
- Claude-class assistants: long-context restructuring and explanations
- Open-source (Llama/Mistral) local runs: batch transforms on sensitive scripts

## Estimation model (very small)
- Scan + classify files: 20%
- Refactor proposals by language: 50%
- Validation/checklist output: 30%

## Practical refactor checklist
- [ ] Detect duplicate script patterns
- [ ] Define shared conventions (naming, logging, errors)
- [ ] Propose per-file minimal diffs first
- [ ] Run syntax/lint checks per language
- [ ] Produce migration notes for changed commands/flags

## Output expected after first pass
- A prioritized list of scripts to refactor first (high reuse/high risk)
- Suggested LLM per task type (generation, migration, review)
- Minimal safe patch plan (small commits)
