"""Fail-closed verification primitives for later phases."""


def require_all_checks(checks: dict[str, bool]) -> None:
    failed = [name for name, passed in checks.items() if passed is not True]
    if failed:
        raise PermissionError("Execution blocked; checks not satisfied: " + ", ".join(failed))
