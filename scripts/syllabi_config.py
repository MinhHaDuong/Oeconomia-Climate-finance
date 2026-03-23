"""Data constants for the syllabi collection pipeline.

Extracted from collect_syllabi.py to keep the main script under the
800-line module-length wall. These are pure configuration data — search
queries and seed URLs — with no logic.
"""

# --- Search queries ---
# (topic, suffix, language_hint)
SEARCH_QUERIES = [
    # English
    ("climate finance", "syllabus", "en"),
    ("climate finance", "reading list", "en"),
    ("climate finance", "course outline", "en"),
    ("climate finance", "course bibliography", "en"),
    ("green finance", "syllabus", "en"),
    ("green finance", "reading list", "en"),
    ("carbon finance", "syllabus", "en"),
    ("carbon finance", "reading list", "en"),
    ("sustainable finance", "syllabus", "en"),
    ("sustainable finance", "reading list", "en"),
    ("climate economics", "syllabus", "en"),
    ("climate economics", "reading list", "en"),
    ("environmental finance", "syllabus", "en"),
    # French
    ("finance climatique", "syllabus", "fr"),
    ("finance climatique", "bibliographie", "fr"),
    ("finance climatique", "plan de cours", "fr"),
    ("financement climatique", "syllabus", "fr"),
    ("finance verte", "syllabus", "fr"),
    ("finance durable", "syllabus", "fr"),
    # German
    ("Klimafinanzierung", "Syllabus", "de"),
    ("Klimafinanzierung", "Literaturliste", "de"),
    ("nachhaltige Finanzwirtschaft", "Syllabus", "de"),
    ("nachhaltige Finanzwirtschaft", "Seminarplan", "de"),
    ("Sustainable Finance", "Syllabus Universität", "de"),
    # Spanish
    ("finanzas climáticas", "syllabus", "es"),
    ("finanzas climáticas", "bibliografía", "es"),
    ("financiamiento climático", "programa curso", "es"),
    ("finanzas sostenibles", "syllabus", "es"),
    # Portuguese
    ("finanças climáticas", "programa", "pt"),
    ("finanças climáticas", "bibliografia", "pt"),
    ("finanças sustentáveis", "syllabus", "pt"),
    # Chinese
    ("气候金融 课程 教学大纲", "", "zh"),
    ("气候融资 课程 参考书目", "", "zh"),
    ("绿色金融 课程 教学大纲", "", "zh"),
    # Japanese
    ("気候ファイナンス シラバス", "", "ja"),
    ("グリーンファイナンス シラバス 参考文献", "", "ja"),
    # Korean
    ("기후금융 강의계획서", "", "ko"),
    ("녹색금융 강의계획서", "", "ko"),
    # Italian
    ("finanza climatica", "syllabus", "it"),
    ("finanza sostenibile", "syllabus bibliografia", "it"),
    # Dutch
    ("klimaatfinanciering", "syllabus", "nl"),
    ("duurzame financiering", "syllabus literatuurlijst", "nl"),
]

# --- Seed URLs (Tier 1 & 3) ---
SEED_URLS = [
    # Brown Syllabus Bank
    {"url": "https://climate.watson.brown.edu/syllabus-bank",
     "title": "Brown Climate Solutions Lab - Syllabus Bank",
     "source_tier": "curated", "language": "en"},
    # Harvard FECS 2025
    {"url": "https://salatainstitute.harvard.edu/wp-content/uploads/2024/12/FECS-2025-reading-list-15Dec24-1.pdf",
     "title": "Harvard FECS 2025 Reading List",
     "source_tier": "curated", "language": "en"},
    # Harvard FECS 2026
    {"url": "https://salatainstitute.harvard.edu/wp-content/uploads/2026/01/FECS-2026-Reading-List_05Jan26-2.pdf",
     "title": "Harvard FECS 2026 Reading List",
     "source_tier": "curated", "language": "en"},
    # Columbia Business School B8363
    {"url": "https://courses.business.columbia.edu/B8363",
     "title": "Columbia Business School - Climate Finance",
     "source_tier": "known_program", "language": "en"},
    # NYU Stern Climate Finance
    {"url": "https://www.stern.nyu.edu/experience-stern/about/departments-centers-initiatives/climate-finance/teaching/climate-finance-course",
     "title": "NYU Stern - Climate Finance Course",
     "source_tier": "known_program", "language": "en"},
    # UBC MBA Climate Finance
    {"url": "https://blogs.ubc.ca/ftmba2025/files/2024/10/BAFI-580C-Climate-Finance-MBA-Syllabus-2024W1.pdf",
     "title": "UBC MBA Climate Finance Syllabus",
     "source_tier": "known_program", "language": "en"},
    # SOAS Summer School
    {"url": "https://www.soas.ac.uk/sites/default/files/summerschool/subjects/course-handbooks/file144926.pdf",
     "title": "SOAS Sustainable Finance and Climate Change",
     "source_tier": "known_program", "language": "en"},
    # Edinburgh
    {"url": "http://www.drps.ed.ac.uk/20-21/dpt/cxcmse11498.htm",
     "title": "Edinburgh - International Climate Finance",
     "source_tier": "known_program", "language": "en"},
    # UQAM
    {"url": "https://etudier.uqam.ca/cours?sigle=DSR7621&p=9030",
     "title": "UQAM - Investissement et Financement climatique",
     "source_tier": "known_program", "language": "fr"},
    # CFA Institute Climate Finance
    {"url": "https://www.cfainstitute.org/programs/climate-finance",
     "title": "CFA Institute - Climate Finance Course",
     "source_tier": "known_program", "language": "en"},
    # UN CC:Learn Climate Finance
    {"url": "https://unccelearn.org/course/view.php?id=91&page=overview",
     "title": "UN CC:Learn - Climate Finance",
     "source_tier": "known_program", "language": "en"},
    # MACC Hub workbook
    {"url": "https://macchub.co.uk/wp-content/uploads/2025/02/English-Workbook-Short-Course-1-.pdf",
     "title": "MACC Hub - Basics of Climate Finance",
     "source_tier": "known_program", "language": "en"},
    # MIT OCW — Global Climate Change: Economics, Science, and Policy
    {"url": "https://ocw.mit.edu/courses/15-023j-global-climate-change-economics-science-and-policy-spring-2008/pages/readings/",
     "title": "MIT OCW 15-023J - Global Climate Change Readings",
     "source_tier": "known_program", "language": "en"},
    # Stanford — Ivo Welch Climate Change course
    {"url": "https://www.ivo-welch.info/teaching/climate-change/stanford/",
     "title": "Stanford - Ivo Welch Climate Change Course",
     "source_tier": "known_program", "language": "en"},
]
