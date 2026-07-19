# Indexing Strategy

Index candidates:
- foreign keys used in joins
- normalized email or login identifiers
- organization and status combinations
- created-at ordering for audit and activity feeds
- lookup keys used in authentication and authorization

Rules:
- Add indexes based on query patterns.
- Avoid redundant indexes.
- Measure before and after for high-volume queries.
- Document partial or expression indexes.
