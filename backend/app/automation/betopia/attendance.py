
import asyncio
import os
import re
from datetime import datetime, timezone
from typing import Any

from playwright.async_api import Page


# Prevent two API requests from clicking Check-In simultaneously.
_check_in_lock = asyncio.Lock()


def normalize(value: str) -> str:
    """Normalize text for reliable comparison."""
    return re.sub(r"\s+", " ", value).strip().casefold()


async def read_home_attendance_status(page: Page) -> dict[str, Any]:
    """
    Read-only Home Office attendance inspection.
    This function never clicks any attendance button.
    """

    if page.is_closed():
        raise RuntimeError("ERP browser page is closed.")

    title = await page.title()
    container = page.locator(".o_remote_attendance_page")

    if await container.count() != 1:
        return {
            "inspected_at": datetime.now(timezone.utc).isoformat(),
            "page_detected": False,
            "status": "unknown",
            "eligible_for_action": False,
            "reason": (
                "Home Attendance container not uniquely identified."
            ),
        }

    page_text = await container.inner_text()

    # Read attendance status only inside the Home Attendance container.
    status_element = container.locator(".o_remote_page_status")

    status_text = ""
    status_class = ""

    if await status_element.count() == 1:
        status_text = await status_element.inner_text()
        status_class = await status_element.get_attribute("class") or ""

    # Inspect attendance buttons only inside this container.
    controls = await container.locator(
        "button.o_remote_page_btn"
    ).evaluate_all("""
        elements => elements.map(el => ({
            text: (el.innerText || "").trim(),
            class_name: el.className,
            disabled: !!el.disabled,
            visible: !!(
                el.offsetWidth ||
                el.offsetHeight ||
                el.getClientRects().length
            )
        }))
    """)

    # Determine attendance status.
    combined_status = normalize(status_text)

    if "not checked in" in combined_status:
        attendance_status = "checked_out"

    elif "checked in" in combined_status:
        attendance_status = "checked_in"

    elif "checked-out" in status_class:
        attendance_status = "checked_out"

    elif "checked-in" in status_class:
        attendance_status = "checked_in"

    else:
        attendance_status = "unknown"

    # Check-In button availability.
    check_in_available = any(
        "check in" in normalize(item["text"])
        and item["visible"]
        and not item["disabled"]
        for item in controls
    )

    # Read-only Check-Out availability.
    check_out_available = any(
        "check out" in normalize(item["text"])
        and item["visible"]
        and not item["disabled"]
        for item in controls
    )

    # Employee name verification diagnostics.
    expected_employee = os.getenv(
        "BETOPIA_EXPECTED_EMPLOYEE", ""
    ).strip()

    expected_normalized = normalize(expected_employee)

    # Check whether expected employee name exists inside
    # the Home Attendance container.
    employee_name_in_container = (
        bool(expected_normalized)
        and expected_normalized in normalize(page_text)
    )

    # Check whether expected employee name exists anywhere
    # on the page. This is diagnostic only.
    body_text = await page.locator("body").inner_text()

    employee_name_in_page = (
        bool(expected_normalized)
        and expected_normalized in normalize(body_text)
    )

    # IMPORTANT:
    # Page-wide text matching is not sufficient for identity verification.
    employee_verified = employee_name_in_container

    page_detected = (
        title.strip() == "Home Attendance"
        and await container.count() == 1
    )

    return {
        "inspected_at": datetime.now(timezone.utc).isoformat(),

        "page_title": title,
        "page_detected": page_detected,

        "attendance_type": "home_office",
        "status": attendance_status,
        "status_text": status_text,
        "status_class": status_class,

        "employee_verified": employee_verified,
        "employee_verification_configured": bool(expected_employee),

        "employee_name_in_attendance_container":
            employee_name_in_container,

        "employee_name_in_page":
            employee_name_in_page,

        "home_office_approval": "unknown",

        "check_in_available": check_in_available,
        "check_out_available": check_out_available,

        "check_in_time": None,
        "check_out_time": None,

        "eligible_for_action": False,

        "controls": controls,

        "reason": (
            "Read-only inspection. Employee name matching is not "
            "a substitute for a stable ERP employee ID."
        ),
    }


async def execute_home_check_in(
    page: Page,
    confirm_home_office: bool = False,
) -> dict[str, Any]:
    """
    Attempt one Home Office Check-In and verify the resulting ERP status.

    Safety rules:
    - Explicit Home Office confirmation is required.
    - Employee name must match the configured expected name.
    - Attendance status must be checked_out.
    - Check-In button must be uniquely identified.
    - Only one click is allowed.
    - No automatic retry.
    """

    if not confirm_home_office:
        return {
            "ok": False,
            "action": "not_attempted",
            "reason": (
                "Explicit confirmation is required. "
                "Confirm that you are actually working from home "
                "and authorized to record Home Office attendance."
            ),
        }

    async with _check_in_lock:

        # Step 1: Inspect current ERP state.
        before = await read_home_attendance_status(page)

        if not before.get("page_detected"):
            return {
                "ok": False,
                "action": "not_attempted",
                "reason": "Home Attendance page was not detected.",
                "before": before,
            }

        # Step 2: Verify employee name.
        if not before.get("employee_verified"):
            return {
                "ok": False,
                "action": "not_attempted",
                "reason": "Expected employee name could not be verified.",
                "before": before,
            }

        # Step 3: Prevent duplicate Check-In.
        if before.get("status") == "checked_in":
            return {
                "ok": True,
                "action": "already_checked_in",
                "message": (
                    "Employee is already checked in. "
                    "No click performed."
                ),
                "attendance": before,
            }

        # Step 4: Require a known checked-out state.
        if before.get("status") != "checked_out":
            return {
                "ok": False,
                "action": "not_attempted",
                "reason": (
                    "Attendance status is unknown. "
                    "No click performed."
                ),
                "before": before,
            }

        # Step 5: Require an available Check-In button.
        if not before.get("check_in_available"):
            return {
                "ok": False,
                "action": "not_attempted",
                "reason": (
                    "Check-In button is unavailable or disabled."
                ),
                "before": before,
            }

        # Step 6: Locate the Check-In button.
        container = page.locator(".o_remote_attendance_page")

        button = container.locator(
            "button.o_remote_page_btn.check-in"
        )

        # Validate button count.
        if await button.count() != 1:
            return {
                "ok": False,
                "action": "not_attempted",
                "reason": (
                    "Check-In button was not uniquely identified."
                ),
                "before": before,
            }

        # Validate visibility.
        if not await button.is_visible():
            return {
                "ok": False,
                "action": "not_attempted",
                "reason": "Check-In button is not visible.",
                "before": before,
            }

        # Validate enabled state.
        if not await button.is_enabled():
            return {
                "ok": False,
                "action": "not_attempted",
                "reason": "Check-In button is disabled.",
                "before": before,
            }

        # Step 7: Exactly one click.
        # Never automatically retry this action.
        try:
            await button.click(timeout=5000)

        except Exception as exc:
            return {
                "ok": False,
                "action": "outcome_unknown",
                "reason": (
                    "Click did not complete normally. "
                    "Inspect the current ERP attendance status "
                    "before considering any further action."
                ),
                "error_type": type(exc).__name__,
            }

        # Step 8: Verify updated ERP attendance status.
        deadline = (
            asyncio.get_running_loop().time() + 15
        )

        while asyncio.get_running_loop().time() < deadline:

            await asyncio.sleep(0.5)

            try:
                after = await read_home_attendance_status(page)

            except Exception:
                continue

            if after.get("status") == "checked_in":
                return {
                    "ok": True,
                    "action": "checked_in",
                    "message": (
                        "ERP confirms Home Office Check-In."
                    ),
                    "verified": True,
                    "attendance": after,
                }

        # Step 9: Final inspection.
        # Never retry automatically.
        try:
            final_status = await read_home_attendance_status(page)

        except Exception:
            final_status = {
                "status": "unknown"
            }

        return {
            "ok": False,
            "action": "verification_failed",
            "message": (
                "Check-In was attempted once, but ERP did not confirm "
                "the checked-in state within 15 seconds. "
                "Do not retry until the current attendance status "
                "is inspected."
            ),
            "verified": False,
            "attendance": final_status,
        }
