# CI Pipeline

Required checks:
1. install with Python 3.12
2. `ruff check .`
3. `pytest`
4. migration validation
5. dependency/security scan
6. build verification

Protected branches should require passing checks and review.
