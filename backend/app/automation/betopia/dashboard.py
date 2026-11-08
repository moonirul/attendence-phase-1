
from typing import Any

from .session import BetopiaBrowserSession


async def inspect_dashboard(
    session: BetopiaBrowserSession,
) -> dict[str, Any]:
    """Return observed DOM evidence without clicking anything."""
    return await session.inspect()


async def inspect_navigation_targets(
    session: BetopiaBrowserSession,
) -> dict[str, Any]:
    """Inspect visible navigation links and menu items."""

    page = session.page

    items = await page.evaluate("""() => {
        const visible = (el) => {
            const s = getComputedStyle(el);
            const r = el.getBoundingClientRect();

            return s.display !== 'none'
                && s.visibility !== 'hidden'
                && r.width > 0
                && r.height > 0;
        };

        const elements = [
            ...document.querySelectorAll(
                'a, button, [role="menuitem"], [role="tab"], [class*="bdl"]'
            )
        ];

        return elements
            .filter(visible)
            .map(el => ({
                tag: el.tagName.toLowerCase(),
                text: (
                    el.innerText ||
                    el.getAttribute('aria-label') ||
                    el.title ||
                    ''
                ).trim().slice(0, 150),
                href: el.getAttribute('href'),
                role: el.getAttribute('role'),
                class_name: typeof el.className === 'string'
                    ? el.className
                    : null
            }))
            .filter(x => x.text || x.href);
    }""")

    return {
        "ok": True,
        "page_title": await page.title(),
        "navigation_targets": items,
        "action_taken": False,
    }


async def open_app_groups(
    session: BetopiaBrowserSession,
) -> dict[str, Any]:
    """Open App Groups if it is not already open."""

    page = session.page

    hrms_button = page.locator(
        "button.bdl__nav-item"
    ).filter(has_text="HRMS")

    # If HRMS is already visible, App Groups is already open.
    if await hrms_button.count() == 1:
        if await hrms_button.is_visible():
            return {
                "ok": True,
                "message": "App Groups is already open.",
                "action_taken": False,
            }

    button = page.locator(
        "button.bd_launcher_trigger"
    )

    count = await button.count()

    if count != 1:
        return {
            "ok": False,
            "reason": (
                f"App Groups button not uniquely identified. Found: {count}"
            ),
        }

    if not await button.is_visible():
        return {
            "ok": False,
            "reason": "App Groups button is not visible.",
        }

    await button.click(timeout=5000)

    try:
        await hrms_button.wait_for(
            state="visible",
            timeout=5000,
        )
    except Exception:
        return {
            "ok": False,
            "reason": "App Groups opened, but HRMS was not found.",
        }

    return {
        "ok": True,
        "message": "App Groups opened successfully.",
        "action_taken": True,
    }







async def open_hrms_category(
    session: BetopiaBrowserSession,
) -> dict[str, Any]:
    """Open HRMS only when it is not already active."""

    page = session.page

    app_result = await open_app_groups(session)

    if not app_result["ok"]:
        return app_result

    hrms_button = page.locator(
        "button.bdl__nav-item"
    ).filter(has_text="HRMS")

    if await hrms_button.count() != 1:
        return {
            "ok": False,
            "reason": "HRMS button is not uniquely identified.",
        }

    if not await hrms_button.is_visible():
        return {
            "ok": False,
            "reason": "HRMS button is not visible.",
        }

    active_hrms = page.locator(
        "button.bdl__nav-item--active"
    ).filter(has_text="HRMS")

    # Already active: do not click again.
    if await active_hrms.count() == 1:
        return {
            "ok": True,
            "message": "HRMS is already active.",
            "action_taken": False,
        }

    await hrms_button.click(timeout=5000)

    try:
        await active_hrms.wait_for(
            state="visible",
            timeout=5000,
        )
    except Exception:
        return {
            "ok": False,
            "reason": "HRMS could not be activated.",
        }

    return {
        "ok": True,
        "message": "HRMS activated successfully.",
        "action_taken": True,
    }








async def open_attendances_app(
    session: BetopiaBrowserSession,
) -> dict[str, Any]:
    """Open Attendances app from HRMS category."""

    page = session.page

    # Confirm HRMS category is active.
    hrms = page.locator(
        "button.bdl__nav-item--active"
    ).filter(has_text="HRMS")

    if await hrms.count() != 1:
        return {
            "ok": False,
            "reason": "HRMS category is not active.",
        }

    # Find Attendances app card.
    card = page.locator(
        "div.bdl__card"
    ).filter(
        has=page.locator(
            "span.bdl__card-name",
            has_text="Attendances",
        )
    )

    count = await card.count()

    if count != 1:
        return {
            "ok": False,
            "reason": (
                f"Attendances card not uniquely identified. Found: {count}"
            ),
        }

    if not await card.is_visible():
        return {
            "ok": False,
            "reason": "Attendances card is not visible.",
        }

    await card.click(timeout=5000)

    try:
        await page.wait_for_function(
            """() => document.title.includes('Attendance')
                || document.body.innerText.includes('My Attendance Details')""",
            timeout=10000,
        )
    except Exception:
        return {
            "ok": False,
            "reason": "Attendances page could not be verified.",
        }

    return {
        "ok": True,
        "message": "Attendances app opened.",
        "page_title": await page.title(),
        "current_url": page.url,
    }



async def open_home_office_menu(
    session: BetopiaBrowserSession,
) -> dict[str, Any]:
    """Open Home Office dropdown only when needed."""

    page = session.page

    button = page.get_by_role(
        "button",
        name="Home Office",
        exact=True,
    )

    menu_item = page.get_by_role(
        "menuitem",
        name="Home Office Attendance",
        exact=True,
    )

    if await button.count() != 1:
        return {
            "ok": False,
            "reason": "Home Office button is not unique.",
        }

    if not await button.is_visible():
        return {
            "ok": False,
            "reason": "Home Office button is not visible.",
        }

    # Dropdown already open.
    if (
        await menu_item.count() == 1
        and await menu_item.is_visible()
    ):
        return {
            "ok": True,
            "message": "Home Office dropdown is already open.",
            "action_taken": False,
        }

    await button.click(timeout=5000)

    try:
        await menu_item.wait_for(
            state="visible",
            timeout=5000,
        )
    except Exception:
        return {
            "ok": False,
            "reason": "Home Office dropdown could not be opened.",
        }

    return {
        "ok": True,
        "message": "Home Office dropdown opened.",
        "action_taken": True,
    }


async def open_home_office_attendance(
    session: BetopiaBrowserSession,
) -> dict[str, Any]:
    """Open Home Office Attendance page."""

    page = session.page

    menu_item = page.get_by_role(
        "menuitem",
        name="Home Office Attendance",
        exact=True,
    )

    count = await menu_item.count()

    if count != 1:
        return {
            "ok": False,
            "reason": (
                "Home Office Attendance menu not uniquely identified. "
                f"Found: {count}"
            ),
        }

    if not await menu_item.is_visible():
        return {
            "ok": False,
            "reason": "Home Office Attendance menu is not visible.",
        }

    await menu_item.click(timeout=5000)

    try:
        await page.wait_for_function(
            """() => document.title === 'Home Attendance'
                && document.querySelectorAll(
                    '.o_remote_attendance_page'
                ).length === 1""",
            timeout=10000,
        )
    except Exception:
        return {
            "ok": False,
            "reason": "Home Office Attendance page could not be verified.",
            "page_title": await page.title(),
        }

    return {
        "ok": True,
        "message": "Home Office Attendance page opened.",
        "page_title": await page.title(),
        "action_taken": True,
    }
