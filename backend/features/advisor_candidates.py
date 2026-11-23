"""Load advisor rows for ranked lists (search results and recommendations).

Both lists use this one query, so they always rank the same fields. Callers
decide who is a candidate by passing SQL conditions; ranking happens afterwards
in plain Python (see features/ranking.py and features/search_ranking.py).
"""

from features.availability import availability_columns, workload_join
from features.reputation import (AS_OF_PARAMETER_COUNT, reputation_columns, reputation_join,
                                 response_count_columns, with_reputation)


def course_key_sql(column):
    """Course code with spaces and hyphens removed and capital letters, for a fixed column name (never user input).

    Matches course_key() in app.py, so "csc 510", "CSC510" and "CSC-510" compare equal.
    """
    return f"regexp_replace(UPPER({column}), '[[:space:]-]+', '', 'g')"


# Leaves out anyone the viewer blocked or who blocked the viewer. Takes the viewer's id twice.
NOT_BLOCKED_SQL = """NOT EXISTS (SELECT 1 FROM student_blocks b
    WHERE (b.blocker_id = %s AND b.blocked_id = s.id) OR (b.blocker_id = s.id AND b.blocked_id = %s))"""


def fetch_advisor_rows(db, conditions, parameters, as_of=None):
    """Return advisor rows meeting every condition, with reputation nested and course lists attached.

    Each row has the public profile summary, availability and reputation, plus the
    internal fields ranking needs: completed course codes and their keys (in the
    same order), and raw response counts.

    Pass as_of (a past time) to get reputation as it stood then, for the ranking
    eval. Profiles, courses and availability are always today's.
    """
    if as_of is not None:
        parameters = [as_of] * AS_OF_PARAMETER_COUNT + list(parameters)
    # Course lists come back in the same order, so each code lines up with its key.
    courses_in_order = "FROM completed_courses c WHERE c.student_id = s.id ORDER BY c.course_code, c.id"
    rows = db.execute(f"""
        SELECT
            s.id,
            s.name,
            s.program,
            s.year,
            s.skills,
            s.advice_topics,
            s.willing_to_advise, {availability_columns()}, {reputation_columns()},
            {response_count_columns()},
            ARRAY(SELECT c.course_code {courses_in_order}) AS courses,
            ARRAY(SELECT {course_key_sql("c.course_code")} {courses_in_order}) AS course_keys
        FROM students s {workload_join()} {reputation_join(as_of=as_of is not None)}
        WHERE {" AND ".join(conditions)}
    """, parameters).fetchall()
    return [with_reputation(row) for row in rows]
