# BAYLab AI development contract

Build in small, tested stages. UI language: Indonesian. Code and comments: English.
Chemistry decisions come only from deterministic, expert-reviewed rules, never an LLM.
Every scientific claim needs a genuine source identifier; otherwise show "belum ada sumber".
Rules have draft or validated status. Only the designated chemist (Pak Pugoh) may validate.
Aroma is a spray indicator. Never claim antimicrobial efficacy from software results.
Label simulated data "Data contoh ilustratif" and exclude it from real training data.
Keep secrets outside code. Do not put private data in browser storage or public assets.
Add typed interfaces and meaningful tests for each implemented module.
Do not invent the missing R-01 through R-12 spreadsheet or chemist-curated gold standard.
Do not force chemical outcomes just to satisfy a contradictory example in a prompt.

## Delivery stages
0. Scaffold and health endpoint. No domain features yet.
1. SQLAlchemy models, Alembic, and sourced material seed.
2. PubChem and RDKit matching against reviewed rules.
3. Formulation rule engine and chemist gold standard evaluation.
4. Licensed literature ingestion, retrieval, and citation evaluation.
5. Deterministic MCDA and aroma reconstruction.
6. Experiment tracking and evaluation-only ML until sufficient real data.
7. Migrate the original UI from index.html and references into typed Next.js pages.
8. Authentication, authorization, audit, encrypted backups, deployment hardening.

The root index.html is an earlier illustrative prototype, not the production application.
Stage 0 does not authorize real formulation data or public production deployment.
