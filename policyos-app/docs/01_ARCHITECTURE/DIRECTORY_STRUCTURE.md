# Directory Structure

Recommended structure:

```text
app/
├── api/
│   ├── deps.py
│   └── routes/
├── core/
│   ├── config.py
│   ├── security.py
│   └── logging.py
├── db/
│   ├── base.py
│   └── session.py
├── models/
├── schemas/
├── services/
├── repositories/
├── agents/
├── knowledge/
└── audit/

tests/
├── unit/
├── integration/
└── api/

docs/
specs/
prompts/
```

## Placement rules
- Pydantic request/response models belong in `schemas`.
- SQLAlchemy entities belong in `models`.
- Business operations belong in `services`.
- Reusable database queries belong in `repositories`.
- Cross-cutting security code belongs in `core/security.py`.
