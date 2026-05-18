import re
from datetime import datetime, timezone
from mcp.server.fastmcp import FastMCP
from client import get_client

mcp = FastMCP("gradescope")


def _parse_due(due_str: str | None) -> str:
    """Normalize Gradescope due date strings."""
    if not due_str:
        return "No due date"
    return due_str.strip()


def _is_upcoming(due_str: str) -> bool:
    """Return True if due date is in the future (best-effort parse)."""
    if not due_str or due_str == "No due date":
        return True  # include unknowns
    try:
        # Gradescope uses formats like "Apr 20 2026 11:59 PM"
        dt = datetime.strptime(due_str, "%b %d %Y %I:%M %p")
        dt = dt.replace(tzinfo=timezone.utc)
        return dt >= datetime.now(timezone.utc)
    except ValueError:
        return True


@mcp.tool()
def get_courses() -> str:
    """List all your Gradescope courses (current and past)."""
    client = get_client()
    soup = client.get("/")

    courses = []
    for box in soup.select(".courseList--term"):
        term = box.select_one(".courseList--term-name")
        term_name = term.get_text(strip=True) if term else "Unknown Term"
        for card in box.select(".courseBox"):
            name = card.select_one(".courseBox--shortname")
            full = card.select_one(".courseBox--name")
            href = card.get("href", "")
            course_id = href.strip("/").split("/")[-1] if href else "?"
            courses.append(
                f"[{term_name}] {name.get_text(strip=True) if name else '?'} — "
                f"{full.get_text(strip=True) if full else ''} (ID: {course_id})"
            )

    return "\n".join(courses) if courses else "No courses found."


@mcp.tool()
def get_assignments(course_id: str) -> str:
    """
    Get all assignments for a specific course.
    Use get_courses() first to find course IDs.
    Args:
        course_id: the numeric course ID from Gradescope URL
    """
    client = get_client()
    soup = client.get(f"/courses/{course_id}/assignments")

    rows = soup.select("table.js-assignmentTable tbody tr, .submissionList .submissionList--row")
    if not rows:
        # fallback: try assignment list items
        rows = soup.select("[data-testid='assignment-row'], .js-assignment-row")

    assignments = []
    for row in rows:
        # Name
        name_el = row.select_one(".submissionList--title, .js-title, td:first-child a, .assignment--title")
        name = name_el.get_text(strip=True) if name_el else row.get_text(strip=True)[:60]

        # Due date
        due_el = row.select_one(".submissionList--dueDate, .due-date, td.submissionList--dueDate")
        due = due_el.get_text(strip=True) if due_el else "No due date"

        # Status
        status_el = row.select_one(".submissionList--status, .submission-status")
        status = status_el.get_text(strip=True) if status_el else ""

        if name:
            line = f"- {name} | Due: {due}"
            if status:
                line += f" | {status}"
            assignments.append(line)

    return "\n".join(assignments) if assignments else "No assignments found (or course may be private)."


@mcp.tool()
def get_upcoming_assignments() -> str:
    """
    Get all upcoming/unsubmitted assignments across all your Gradescope courses.
    Scrapes the main dashboard for pending work.
    """
    client = get_client()
    soup = client.get("/")

    assignments = []

    # The dashboard shows upcoming assignments in the activity feed
    for item in soup.select(".js-upcomingAssignments .submissionList--row, .pastDueBox .submissionList--row, .js-courseAssignmentList li"):
        name_el = item.select_one(".submissionList--title, a")
        due_el = item.select_one(".submissionList--dueDate, .due-date")
        course_el = item.select_one(".submissionList--course, .course-name")

        name = name_el.get_text(strip=True) if name_el else ""
        due = due_el.get_text(strip=True) if due_el else "No due date"
        course = course_el.get_text(strip=True) if course_el else ""

        if name:
            assignments.append(f"[{course}] {name} — Due: {due}")

    if assignments:
        return "\n".join(assignments)

    # Fallback: scrape each course individually from dashboard course list
    course_links = []
    for card in soup.select(".courseBox"):
        href = card.get("href", "")
        cid_match = re.search(r"/courses/(\d+)", href)
        name_el = card.select_one(".courseBox--shortname")
        if cid_match and name_el:
            course_links.append((cid_match.group(1), name_el.get_text(strip=True)))

    if not course_links:
        return "No courses or upcoming assignments found on dashboard."

    results = []
    for cid, cname in course_links[:8]:  # cap at 8 courses to avoid rate limiting
        try:
            csoup = client.get(f"/courses/{cid}/assignments")
            for row in csoup.select("tbody tr"):
                cells = row.find_all("td")
                if len(cells) >= 2:
                    name = cells[0].get_text(strip=True)
                    due = cells[1].get_text(strip=True) if len(cells) > 1 else "No due date"
                    submitted_el = row.select_one(".submissionStatus--text, .submission-status")
                    submitted = submitted_el.get_text(strip=True) if submitted_el else ""
                    if name and "No Submission" in submitted or not submitted:
                        results.append(f"[{cname}] {name} — Due: {due}")
        except Exception:
            continue

    return "\n".join(results) if results else "No upcoming assignments found across your courses."


@mcp.tool()
def get_grades() -> str:
    """
    Get your grades/scores for recent submissions across all courses.
    Returns assignment name, score, and max points where available.
    """
    client = get_client()
    soup = client.get("/")

    grades = []
    for item in soup.select(".submissionList--row"):
        name_el = item.select_one(".submissionList--title")
        score_el = item.select_one(".submissionList--score, .score")
        course_el = item.select_one(".submissionList--course")

        name = name_el.get_text(strip=True) if name_el else ""
        score = score_el.get_text(strip=True) if score_el else ""
        course = course_el.get_text(strip=True) if course_el else ""

        if name and score:
            grades.append(f"[{course}] {name} — {score}")

    return "\n".join(grades) if grades else "No graded submissions found on dashboard."


if __name__ == "__main__":
    mcp.run(transport="stdio")
