"""Settings shared by every step of the pipeline. Edit these, not the scripts."""
import os
from pathlib import Path
from dotenv import load_dotenv

load_dotenv()

DATA_DIR = Path(os.environ.get("COMPANY_FINDER_DATA", Path(__file__).parent / "data"))
DATA_DIR.mkdir(exist_ok=True)




# Google Places
# Query -> which resume lane it suggests
PLACES_QUERIES = {
    "software development company": "full-stack",
    "web development agency":       "full-stack",
    "digital agency":               "full-stack",
    "software company":             "either",
    "IT consulting":                "either",
    "data analytics company":       "data",
    "engineering consulting firm":  "data",
}

# Names containing these are almost never what you want
EXCLUDE_NAME_KEYWORDS = [
    "repair", "phone", "cell", "computer store", "pc store", "best buy",
    "geek squad", "printer", "copier", "staffing",
]


# Orgs whose name/description contains these are usually not employers
GITHUB_EXCLUDE_KEYWORDS = [
    "hackathon", "hacks", "club", "student", "university", "college", "school",
    "class", "course", "cosc", "homework", "workshop", "meetup", "bootcamp",
    "robotics", "frc", "ftc", "vex", "girls who code", "church", "ministr",
    "isd", "high school", "chapter",
]


# Scoring
# Personal Stats that i like using, will change later
MY_LANGUAGES = {"Python", "JavaScript", "TypeScript", "Java", "C++",
                "Jupyter Notebook", "PLpgSQL", "TSQL"}
FULLSTACK_LANGUAGES = {"JavaScript", "TypeScript", "HTML", "CSS", "Vue", "Svelte"}
DATA_LANGUAGES = {"Python", "Jupyter Notebook", "R"}

# Hosts that don't identify a company (can't be used to match records)
GENERIC_HOSTS = {
    "facebook.com", "linkedin.com", "instagram.com", "twitter.com", "x.com",
    "github.com", "github.io", "sites.google.com", "google.com", "wixsite.com",
    "business.site", "linktr.ee", "medium.com", "youtube.com",
}
