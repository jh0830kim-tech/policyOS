# Design Principles

1. **Modularity** — each domain has explicit responsibilities.
2. **Dependency direction** — outer layers depend on inner abstractions, not the reverse.
3. **Async-first** — request-path I/O uses async APIs.
4. **Least privilege** — users and agents receive only required access.
5. **Idempotency where needed** — retries must not duplicate consequential actions.
6. **Observability** — important operations expose logs, metrics, and traces.
7. **Source integrity** — AI outputs preserve source identifiers.
8. **Human review** — consequential documents and external actions require approval.
9. **Backward compatibility** — API changes are versioned or migrated.
10. **Small change sets** — implementation proceeds through focused increments.
