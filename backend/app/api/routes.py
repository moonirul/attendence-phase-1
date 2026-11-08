
import asyncio

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from app.automation.betopia.session import BetopiaBrowserSession

from app.automation.betopia.dashboard import (
    inspect_dashboard,
    inspect_navigation_targets,
    open_hrms_category,
    open_attendances_app,
    open_home_office_menu,
    open_home_office_attendance,
)

from app.automation.betopia.attendance import (
    read_home_attendance_status,
    execute_home_check_in,
)


router = APIRouter(prefix="/api/erp", tags=["Betopia ERP"])

session = BetopiaBrowserSession()



attendance_run_lock = asyncio.Lock()


# --------------------------------------------------
# REQUEST MODELS
# --------------------------------------------------

class StartSessionRequest(BaseModel):
    headless: bool = False


class HomeCheckInRequest(BaseModel):
    confirm_home_office: bool = False


# --------------------------------------------------
# HELPER: WAIT FOR ATTENDANCE PAGE
# --------------------------------------------------

async def wait_for_home_attendance(timeout_seconds=15):
    page = session.page

    await page.locator(
        ".o_remote_attendance_page"
    ).wait_for(
        state="visible",
        timeout=timeout_seconds * 1000
    )

    await page.wait_for_timeout(1500)


# --------------------------------------------------
# HELPER: WAIT FOR EMPLOYEE VERIFICATION
# --------------------------------------------------

async def wait_for_employee_verification(timeout_seconds=8):
    """
    Read-only polling.
    Does not click any attendance button.
    """

    loop = asyncio.get_running_loop()
    deadline = loop.time() + timeout_seconds

    last_status = None

    while loop.time() < deadline:

        last_status = await read_home_attendance_status(
            session.page
        )

        if (
            last_status.get("page_detected")
            and last_status.get("employee_verified")
        ):
            return last_status

        await asyncio.sleep(0.5)

    return last_status


# --------------------------------------------------
# SESSION
# --------------------------------------------------

@router.post("/session/start")
async def start_session(request: StartSessionRequest):
    global session

    if request.headless != session.headless:

        if session.state.running:
            raise HTTPException(
                409,
                "Stop the current session before changing browser mode."
            )

        session = BetopiaBrowserSession(
            headless=request.headless
        )

    try:
        return await session.start()

    except Exception as exc:
        raise HTTPException(
            500,
            f"Could not start browser session: {type(exc).__name__}"
        )


@router.get("/session/status")
async def session_status():
    return await session.status()


@router.post("/session/stop")
async def stop_session():
    await session.stop()

    return {
        "ok": True,
        "message": "Browser session stopped."
    }


# --------------------------------------------------
# DASHBOARD INSPECTION
# --------------------------------------------------

@router.post("/dashboard/inspect")
async def dashboard_inspect():
    try:
        result = await inspect_dashboard(session)

        return {
            "ok": True,
            "inspection": result
        }

    except Exception as exc:
        raise HTTPException(
            400,
            f"Inspection unavailable: {type(exc).__name__}: {str(exc)[:200]}"
        )


@router.post("/dashboard/navigation/inspect")
async def dashboard_navigation_inspect():
    try:
        return await inspect_navigation_targets(session)

    except Exception as exc:
        raise HTTPException(
            400,
            f"Navigation inspection failed: {type(exc).__name__}: {str(exc)[:200]}"
        )


# --------------------------------------------------
# INDIVIDUAL NAVIGATION ENDPOINTS
# --------------------------------------------------

@router.post("/dashboard/navigation/open-hrms")
async def dashboard_navigation_open_hrms():
    try:
        return await open_hrms_category(session)

    except Exception as exc:
        raise HTTPException(
            400,
            f"Could not open HRMS: {type(exc).__name__}: {str(exc)[:200]}"
        )


@router.post("/dashboard/navigation/open-attendances")
async def dashboard_navigation_open_attendances():
    try:
        return await open_attendances_app(session)

    except Exception as exc:
        raise HTTPException(
            400,
            f"Could not open Attendances: {type(exc).__name__}: {str(exc)[:200]}"
        )


@router.post("/dashboard/navigation/open-home-office-menu")
async def dashboard_navigation_open_home_office_menu():
    try:
        return await open_home_office_menu(session)

    except Exception as exc:
        raise HTTPException(
            400,
            f"Could not open Home Office menu: {type(exc).__name__}: {str(exc)[:200]}"
        )


@router.post("/dashboard/navigation/open-home-office-attendance")
async def dashboard_navigation_open_home_office_attendance():
    try:
        result = await open_home_office_attendance(session)

        if not result.get("ok"):
            return result

        await wait_for_home_attendance()

        return {
            **result,
            "page_ready": True
        }

    except Exception as exc:
        raise HTTPException(
            400,
            f"Could not open Home Office Attendance: {type(exc).__name__}: {str(exc)[:200]}"
        )


# --------------------------------------------------
# HOME OFFICE ATTENDANCE STATUS
# --------------------------------------------------

@router.get("/attendance/home/status")
async def home_attendance_status():
    try:
        result = await read_home_attendance_status(
            session.page
        )

        return {
            "ok": True,
            "attendance": result
        }

    except Exception as exc:
        raise HTTPException(
            400,
            f"Attendance inspection failed: {type(exc).__name__}"
        )


# --------------------------------------------------
# MANUAL HOME OFFICE CHECK-IN
# --------------------------------------------------

@router.post("/attendance/home/check-in")
async def home_attendance_check_in(
    request: HomeCheckInRequest
):

    if not request.confirm_home_office:
        raise HTTPException(
            400,
            "Explicit Home Office confirmation is required."
        )

    if not session.state.running:
        raise HTTPException(
            409,
            "Browser session is not running. Start and login first."
        )

    try:
        result = await execute_home_check_in(
            session.page,
            confirm_home_office=request.confirm_home_office,
        )

        return result

    except Exception as exc:
        raise HTTPException(
            400,
            f"Home Check-In failed: {type(exc).__name__}"
        )


# --------------------------------------------------
# AUTOMATIC HOME OFFICE CHECK-IN
# --------------------------------------------------

@router.post("/attendance/home/auto-check-in")
async def auto_home_attendance_check_in(
    request: HomeCheckInRequest
):
    """
    Complete navigation and perform one verified
    Home Office Check-In.

    - Requires explicit Home Office confirmation.
    - Does not start browser automatically.
    - Does not bypass login or MFA.
    - Does not perform Check-Out.
    - Does not retry Check-In.
    """

    # Step 0: Explicit confirmation

    if not request.confirm_home_office:
        raise HTTPException(
            400,
            "Confirm that you are actually working from home and authorized."
        )

    # Step 1: Browser session check

    if not session.state.running:
        raise HTTPException(
            409,
            "Browser session is not running. Start the session and login first."
        )

    try:
        page = session.page

        current_url = page.url.lower()
        page_title = (await page.title()).lower()

        if "/web/login" in current_url or "login" in page_title:
            raise HTTPException(
                401,
                "ERP login required. Complete manual login/MFA first."
            )

        steps = []

        # Step 2: Apps Groups -> HRMS

        result = await open_hrms_category(session)

        steps.append({
            "step": "open_hrms",
            "result": result
        })

        if not result.get("ok"):
            return {
                "ok": False,
                "action": "not_attempted",
                "reason": "Could not open HRMS.",
                "steps": steps
            }

        # Step 3: HRMS -> Attendances

        result = await open_attendances_app(session)

        steps.append({
            "step": "open_attendances",
            "result": result
        })

        if not result.get("ok"):
            return {
                "ok": False,
                "action": "not_attempted",
                "reason": "Could not open Attendances.",
                "steps": steps
            }

        # Step 4: Open Home Office dropdown

        result = await open_home_office_menu(session)

        steps.append({
            "step": "open_home_office_menu",
            "result": result
        })

        if not result.get("ok"):
            return {
                "ok": False,
                "action": "not_attempted",
                "reason": "Could not open Home Office menu.",
                "steps": steps
            }

        # Step 5: Open Home Office Attendance

        result = await open_home_office_attendance(session)

        steps.append({
            "step": "open_home_office_attendance",
            "result": result
        })

        if not result.get("ok"):
            return {
                "ok": False,
                "action": "not_attempted",
                "reason": "Could not open Home Office Attendance.",
                "steps": steps
            }

        # Step 6: Wait until page is rendered

        await wait_for_home_attendance()

        steps.append({
            "step": "wait_for_page",
            "result": {
                "ok": True,
                "message": "Home Attendance page is visible."
            }
        })

        # Step 7: Wait for employee verification

        attendance = await wait_for_employee_verification(
            timeout_seconds=8
        )

        steps.append({
            "step": "inspect_attendance",
            "result": attendance
        })

        # Verify page

        if not attendance.get("page_detected"):
            return {
                "ok": False,
                "action": "not_attempted",
                "reason": "Home Office Attendance page not verified.",
                "steps": steps
            }

        # Verify employee

        if not attendance.get("employee_verified"):
            return {
                "ok": False,
                "action": "not_attempted",
                "reason": "Employee verification failed after waiting.",
                "attendance": attendance,
                "steps": steps
            }

        # Step 8: Already checked in?

        if attendance.get("status") == "checked_in":
            return {
                "ok": True,
                "action": "already_checked_in",
                "message": "Employee is already checked in.",
                "verified": True,
                "attendance": attendance,
                "steps": steps
            }

        # Step 9: Only proceed from checked_out

        if attendance.get("status") != "checked_out":
            return {
                "ok": False,
                "action": "not_attempted",
                "reason": "Attendance status is unknown. No action taken.",
                "attendance": attendance,
                "steps": steps
            }

        if not attendance.get("check_in_available"):
            return {
                "ok": False,
                "action": "not_attempted",
                "reason": "Check-In button is not available.",
                "attendance": attendance,
                "steps": steps
            }

        # Step 10: Execute exactly one Check-In attempt

        check_in_result = await execute_home_check_in(
            session.page,
            confirm_home_office=request.confirm_home_office,
        )

        steps.append({
            "step": "execute_check_in",
            "result": check_in_result
        })

        # Step 11: Verify ERP response

        if (
            check_in_result.get("ok")
            and check_in_result.get("verified")
            and check_in_result.get("action") == "checked_in"
        ):
            return {
                "ok": True,
                "action": "checked_in",
                "message": "ERP confirms Home Office Check-In.",
                "verified": True,
                "attendance": check_in_result.get("attendance"),
                "steps": steps
            }

        return {
            "ok": False,
            "action": "verification_failed",
            "message": "Check-In was not verified by ERP. Inspect status before retrying.",
            "verified": False,
            "result": check_in_result,
            "steps": steps
        }

    except HTTPException:
        raise

    except Exception as exc:
        raise HTTPException(
            400,
            f"Automatic Check-In failed: {type(exc).__name__}: {str(exc)[:200]}"
        )



@router.post("/attendance/home/run")
async def run_home_attendance_agent(
    request: HomeCheckInRequest
):
    """
    Single endpoint:
    Start browser if needed, wait for ERP dashboard,
    then execute verified Home Office Check-In.
    """

    if not request.confirm_home_office:
        raise HTTPException(
            400,
            "Confirm that you are actually working from home and authorized."
        )

    session_started = False

    try:
        # Step 1: Start browser if needed
        if not session.state.running:

            start_result = await session.start()
            session_started = True

            if not session.state.running:
                return {
                    "ok": False,
                    "action": "session_start_failed",
                    "message": "Could not start browser session.",
                    "session": start_result
                }

        page = session.page

        # Step 2: Check login requirement
        current_url = page.url.lower()
        page_title = (await page.title()).lower()

        if "/web/login" in current_url or "login" in page_title:
            return {
                "ok": False,
                "action": "login_required",
                "message": "Complete ERP login/MFA manually, then call /run again.",
                "session_started": session_started
            }

        # Step 3: Wait for ERP Dashboard App Groups button
        try:
            await page.locator(
                "button.bd_launcher_trigger"
            ).wait_for(
                state="visible",
                timeout=20000
            )

        except Exception:
            return {
                "ok": False,
                "action": "dashboard_not_ready",
                "message": (
                    "ERP Dashboard did not become ready within 20 seconds. "
                    "Check browser and login status before retrying."
                ),
                "page_title": await page.title(),
                "session_started": session_started
            }

        # Step 4: Run existing Auto Check-In workflow
        result = await auto_home_attendance_check_in(request)

        return {
            **result,
            "session_started": session_started
        }

    except HTTPException:
        raise

    except Exception as exc:
        raise HTTPException(
            400,
            f"Attendance agent failed: {type(exc).__name__}: {str(exc)[:200]}"
        )
