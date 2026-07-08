# LLM Allowed Use

## Approval

| Field | Value |
| --- | --- |
| Business owner | TBD |
| Technical owner | TBD |
| Security reviewer | TBD |
| Approved date | TBD |
| Review date | TBD |

## Allowed

Use the self-hosted LLM path for:

- code explanation and scripting assistance;
- internal documentation drafts;
- ticket, meeting, or email summaries after removing sensitive content;
- non-sensitive spreadsheet cleanup;
- synthetic test data;
- knowledge base drafts from approved internal notes.

## Review First

Ask the business owner and security reviewer before using:

- customer records;
- HR data;
- legal text;
- regulated records;
- financial data;
- production incident details;
- any content that identifies a customer, employee, patient, or supplier.

## Blocked

Do not send these to any pilot prompt:

- raw passwords;
- private keys;
- API keys;
- seed phrases;
- payment card data;
- unredacted health data;
- production database exports;
- privileged access tokens;
- confidential contract clauses unless approved for the route.

## Route Policy

| Data class | Default route | Cloud fallback allowed? | Notes |
| --- | --- | --- | --- |
| Public or synthetic | Local or cloud | Yes | Use cheapest reliable route. |
| Internal low-risk | Local preferred | Yes, if approved | Remove unnecessary identifiers. |
| Confidential | Local only | No, unless approved | Record approval before testing. |
| Regulated | Blocked by default | No | Requires a compliant environment. |
| Secrets or credentials | Blocked | No | Rotate if exposed. |

## Operator Rule

The LLM may draft text or commands. A human operator must review and approve
changes to users, tenants, mailboxes, files, infrastructure, billing, or access
control.
