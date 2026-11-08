"""Safe defaults. Real company policy must be configured and verified."""


POLICY = {
    "inspection_only_by_default": True,
    "dry_run_by_default": True,
    "scheduled_submission_enabled": False,
    "require_explicit_user_approval": True,
    "require_verified_employee_identity": True,
    "require_verified_presence_and_work_mode": True,
    "block_when_uncertain": True,
    "never_retry_uncertain_submission": True,
}
