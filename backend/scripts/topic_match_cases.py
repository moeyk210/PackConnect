"""Hand-written test set for topic matching (issue #3).

ADVISOR_TOPICS are realistic advice topic lists. Each case pairs a way a student
might describe what they need with the one advisor topic list that fits it.
Most needs use different words from the right advisor's topics, which is where
shared-word matching struggles; a few use the exact words, to check that
shared words still work. All examples are made up.
"""

ADVISOR_TOPICS = [
    "Projects, interviews",
    "Resume reviews, career fairs, internships",
    "Course workload, time management",
    "Exams, study strategies",
    "Research, grad school applications",
    "Group work, team conflicts",
    "Python, debugging, coding assignments",
    "Balancing a part-time job, finances",
    "Networking, LinkedIn, mentorship",
    "Software testing, CI pipelines",
    "Databases, SQL",
    "Writing reports, presentations",
]

# (what the student asks for, index of the advisor topics that fit it)
CASES = [
    ("interview prep", 0),
    ("mock technical interviews", 0),
    ("job hunting", 1),
    ("getting an internship", 1),
    ("fixing my CV", 1),
    ("too much homework", 2),
    ("staying on top of deadlines", 2),
    ("studying for the final", 3),
    ("midterm prep", 3),
    ("applying to PhD programs", 4),
    ("finding a research lab", 4),
    ("my teammates don't do their share", 5),
    ("dealing with a difficult group member", 5),
    ("my code keeps crashing", 6),
    ("learning Python", 6),
    ("working while in school", 7),
    ("paying for school", 7),
    ("meeting people in industry", 8),
    ("finding a mentor", 8),
    ("writing unit tests", 9),
    ("setting up GitHub Actions", 9),
    ("designing database tables", 10),
    ("writing SQL queries", 10),
    ("giving a class presentation", 11),
    ("writing my final report", 11),
    # Exact words: shared-word matching should already get these right.
    ("time management", 2),
    ("internships", 1),
    ("group work", 5),
    ("research", 4),
    ("debugging", 6),
]
