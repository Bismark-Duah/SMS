"""
Offline Name-Based Gender Detection Service.
Automatically infers gender ('Male' or 'Female') from Ghanaian, Christian, Islamic,
and international naming conventions when gender is omitted or unknown.
Functions 100% offline without external APIs.
"""

import re
from typing import Optional

# Comprehensive Akan Day Names
AKAN_DAY_FEMALE = {
    "akosua", "adwoa", "adjoa", "abena", "abenaa", "yaba",
    "akua", "ekua", "yaa", "afia", "afua", "effia", "ama", "amma"
}

AKAN_DAY_MALE = {
    "kwasi", "kwesi", "akwasi", "kwadwo", "kojo", "jojo",
    "kwabena", "kobina", "kobby", "kwaku", "kweku", "kuuku",
    "yaw", "nanayaw", "kofi", "fiifi", "yoofi", "kwame", "kwamina"
}

# Traditional Ghanaian Female Names & Suffixes
FEMALE_NAMES_GHANA = {
    "serwaa", "asieduwaa", "agyeiwaa", "adoma", "pokua", "pokuaa", "ampofoaa", "twumwaa",
    "dufie", "kyerewaa", "mansa", "boakyewaa", "oforiwaa", "danquahwaa", "frimpomaa",
    "badu", "baduotiwaa", "konadu", "dentaa", "animwaa", "acheampomaa", "antwiwaa",
    "ohemaa", "ohenewaa", "boatemaa", "fordjourwaa", "gyamfua", "gyamfuaa", "nketiaa",
    "korantemaa", "darkowaa", "bempomaa", "dansowaa", "appiahwaa", "amoakoaa",
    "owusuwaa", "asantewaa", "mirekua", "achiaa", "boafowaa", "frimponmaa", "gyasiwaa",
    "kyeremaa", "rosalinda", "rosina", "mina", "jemima", "mavis", "bryna", "josephine",
    "mawuse", "celestina", "henrietta", "lawrencia", "dominica", "ohenmaa", "yaa-serwaa",
    "akua-serwaa", "afia-serwaa", "ama-serwaa", "adwoa-serwaa", "naa", "dedei", "korkor",
    "kai", "tsotsoo", "dromo", "delali", "enam", "eyram", "fafa", "kekeli", "makafui",
    "senam", "dzifa", "eli"
}

# Christian & English Female Names
FEMALE_NAMES_EN = {
    "abigail", "abigial", "alice", "agatha", "agnes", "agness", "angela", "angelina", "anita",
    "ann", "anna", "anne", "anastasia", "adelaide", "barbara", "beatrice", "belinda", "bernice",
    "bertha", "blessing", "brenda", "bridget", "catherine", "cecilia", "charity", "charis",
    "charlotte", "christabel", "christable", "christiana", "clara", "comfort", "constance", "ciara",
    "cynthia", "daisy", "davina", "deborah", "denise", "diana", "dorcas", "doreen", "doris", "dorothy",
    "edna", "elizabeth", "eliza", "ella", "ellen", "emily", "emma", "emmanuella", "erica",
    "esther", "estell", "estella", "eunice", "evelyn", "faith", "faustina",
    "felicia", "florence", "francesca", "freda", "fredrica", "georgina", "gertrude", "gifty", "gladys", "gloria",
    "grace", "godslove", "gwendolyn", "hannah", "harriet", "helen", "helena", "hope", "irene",
    "isabella", "ivonne", "ivy", "jacqueline", "jacquline", "jacklyn", "jane", "janet", "jennifer",
    "jessica", "joan", "joy", "joyce", "joycelyn", "judith", "julia", "juliana", "justina",
    "kate", "keziah", "laura", "leticia", "linda", "lora", "lorinda", "louisa", "lovia", "lucy", "luciana",
    "lydia", "mabel", "margaret", "martha", "mary", "marilyn", "matilda", "mercy", "millicient", "miriam",
    "mizpah", "monica", "naomi", "nancy", "olivia", "pamela", "patience", "patricia",
    "paula", "pauline", "peace", "pearl", "perpetual", "philomena", "phoebe",
    "portia", "precious", "princess", "priscilla", "prisca", "prospera", "prudence",
    "queen", "queenie", "rachel", "racheal", "rebecca", "regina", "rita", "rosemary", "rose",
    "rubina", "ruby", "ruth", "sabina", "salome", "sandra", "sarah", "selina",
    "shirley", "sophia", "spendylove", "solomina", "stacy", "stella", "stephanie", "susan", "susana",
    "sybil", "sylvia", "theresa", "theresah", "tracy", "valerie", "vanessa", "vera", "veronica",
    "victoria", "vida", "violet", "vivian", "winifred", "winnefred", "yvonne",
    "ernestina", "enerstina", "suzzy", "philipa", "phillipa"
}

# Islamic Female Names
FEMALE_NAMES_ISLAMIC = {
    "hubaida", "amina", "aminatu", "fatima", "fatimatu", "fati", "aisha", "ayisha",
    "mariam", "zinatu", "rashida", "habiba", "halima", "rukiya", "safia", "hamida", "hamdiya",
    "samira", "zainab", "hafsa", "khadija", "fadila", "farida", "madina", "rukaiya",
    "munira", "najat", "yasmin", "zubaida", "rabiatu", "asana", "hawa", "mariama", "zakiya",
    "sumaiya", "suweiba", "lubaba", "rahinatu", "firdause", "nadia", "fuseina", "fusena", "faiza"
}


ALL_FEMALE_LEXICON = AKAN_DAY_FEMALE | FEMALE_NAMES_GHANA | FEMALE_NAMES_EN | FEMALE_NAMES_ISLAMIC

# Traditional Ghanaian Male Names
MALE_NAMES_GHANA = {
    "barima", "opanyin", "agyeman", "acheampong", "boakye", "agyapong", "ohene",
    "twumasi", "asante", "kyei", "sarfo", "bonsu", "gyasi", "fordjour", "kankam",
    "agyenim", "baffour", "nketia", "amankwah", "owusu", "appiah", "danso", "bempah",
    "frimpong", "darko", "koranteng", "ampofo", "pokuo", "asiedu", "danquah", "boakye-danquah",
    "tetteh", "tettey", "narh", "mensah", "ayitey", "laryea", "kotey", "quaye", "annang",
    "nii", "dodzi", "elorm", "selorm", "senyo", "korku", "komla", "kudzo", "kofi-mensah"
}

# Christian & English Male Names
MALE_NAMES_EN = {
    "aaron", "abraham", "adam", "aikins", "albert", "alex", "alexander", "alfred", "allan",
    "allen", "alvin", "amos", "andrew", "andrews", "andy", "anthony", "antony", "aristotle", "arnold", "arthur", "augustine", "austin",
    "barnabas", "benjamin", "benedict", "benard", "bernard", "bismark", "brian", "bright", "caleb", "calvin", "campbell", "cephas",
    "charles", "christian", "christopher", "clement", "clinton", "clifford",
    "collins", "cornelius", "crespo", "cyril", "daniel", "darlington", "david", "dennis",
    "derrick", "desmond", "desmomd", "dickson", "divine", "dominic", "douglas", "ebenezer", "ebenenzer", "edmond", "edward",
    "edwin", "elijah", "elvis", "elvin", "emmanuel", "emmanue", "enoch", "ephraim", "eric", "ernest", "eugene", "euguene", "evans", "ezekiel",
    "felix", "foster", "francis", "frank", "franklin", "frederick", "fred", "fredrick",
    "gabriel", "gad", "garvyn", "george", "gerald", "gideon", "gilbert", "godfred", "godfrey", "godbless", "godwill",
    "godson", "godwin", "graham", "gregory", "harrison", "harry", "hayford", "henry", "herbert", "hilary", "hubert", "ian", "isaac",
    "isiah", "isaiah", "israel", "ivan", "jacob", "james", "jason", "jeffrey", "jefferey", "jeffery", "jeff", "jeremiah", "jerry",
    "joel", "john", "jonah", "jonathan", "joseph", "joshua", "jude", "judah", "julius", "julian", "junior", "justice",
    "justin", "kelvin", "kendrick", "kenneth", "kennedy", "kingsley", "kingsford", "lawrence", "lawson", "leonard", "leslie",
    "lionel", "livingstone", "louis", "lukas", "luke", "malvin", "manasseh", "manase", "manuel",
    "mark", "martin", "marvin", "matthew", "maurice", "maxwell", "meshack", "michael", "micheal", "morris",
    "moses", "nathan", "nathaniel", "nelson", "nicholas", "obed", "patrick", "paul", "perez",
    "peter", "philip", "prince", "prosper", "ramzy", "randy", "ransford", "raymond", "reuben",
    "richard", "richmond", "robert", "rockson", "roland", "rolland", "romeo", "ronald", "samuel", "samson", "sampson", "seth",
    "shadrack", "simon", "solomon", "stephen", "steven", "sylvester", "theophilus", "thomas", "timothy", "victor", "vincent",
    "wilberforce", "william", "wisdom", "elisha", "rapheal", "shaban", "kadmiel", "seedolf", "slyvester", "raynold", "jephter",
    "armstrong", "bortnick", "philimond", "lordken", "pious", "ballard", "macarthy",
    "energy", "josh", "benhen", "jacken", "clavert", "kemuel", "kish", "jeffinting",
    "hilkiah", "dosty", "essel", "akomeah", "goodluck", "marvelous", "blessed", "courage", "casy",
    "rabbi", "enders", "batabonga", "chegabatia", "abotere", "hoyte", "williams"
}

# Islamic Male Names
MALE_NAMES_ISLAMIC = {
    "abdul", "abubakar", "abubakari", "adam", "ahmed", "alhassan", "ali", "alidu", "aminu",
    "anwar", "azeez", "bashiru", "bilal", "dauda", "faisal", "fusheini", "ganiu", "habib",
    "halifah", "hamid", "hamza", "haruna", "hassan", "ibrahim", "idddrisu", "idris", "ismail", "issa",
    "issah", "issifu", "khalil", "latif", "mahmud", "majeed", "malik", "mohammed", "muhammad",
    "musa", "mustapha", "nasir", "nuhu", "osman", "rashid", "rauff", "rayyan", "razak", "sadik",
    "said", "salifu", "suleman", "sulemana", "suraj", "tahir", "umar", "usman", "wahab",
    "yahaya", "yakubu", "yussif", "zakaria", "sadiq", "kamal", "muniru"
}

ALL_MALE_LEXICON = AKAN_DAY_MALE | MALE_NAMES_GHANA | MALE_NAMES_EN | MALE_NAMES_ISLAMIC


def detect_gender_from_name(full_name: Optional[str], class_hint: Optional[str] = None) -> str:
    """
    Intelligently determines 'Male' or 'Female' from student's name tokens.
    Uses Ghanaian day names, Akan suffixes, Christian, and Islamic lexicons.
    Prioritizes given names (first/second tokens) over patronymic surnames.
    100% offline and deterministic.
    """
    if not full_name or not full_name.strip():
        return "Male"

    clean = re.sub(r"[^a-zA-Z\s]", " ", full_name).lower()
    tokens = clean.split()
    if not tokens:
        return "Male"

    f_score = 0
    m_score = 0

    num_tokens = len(tokens)
    for idx, token in enumerate(tokens):
        # Weight given names (earlier tokens) higher than patronymic surnames (last token)
        is_given_name = (idx < 2) if num_tokens > 1 else True
        pos_multiplier = 1.5 if is_given_name else 1.0

        # Akan day names are direct indicators of personal gender
        if token in AKAN_DAY_FEMALE:
            f_score += 5 * pos_multiplier
        elif token in AKAN_DAY_MALE:
            m_score += 5 * pos_multiplier

        # Feminine suffixes like -waa or -maa or -fua (e.g., Boakyewaa, Dufie)
        elif token.endswith("waa") or token.endswith("maa") or token.endswith("fua") or token.endswith("twaa"):
            f_score += 4 * pos_multiplier

        # Female given lexicons
        elif token in FEMALE_NAMES_GHANA or token in FEMALE_NAMES_EN or token in FEMALE_NAMES_ISLAMIC:
            f_score += 3 * pos_multiplier

        # Male given / traditional lexicons
        elif token in MALE_NAMES_EN or token in MALE_NAMES_ISLAMIC or token in MALE_NAMES_GHANA:
            # If it's the last token (surname), it might just be the father's name (patronymic)
            # so we give it normal weight, but give first name higher weight
            m_score += (3 if is_given_name else 1.5)

    if f_score > m_score:
        return "Female"
    elif m_score > f_score:
        return "Male"

    # Tie-breaking logic based on class or academic stream hints
    if class_hint:
        hint_low = class_hint.lower().strip()
        if "home" in hint_low or "econ" in hint_low or hint_low.startswith("1h") or hint_low.startswith("2h") or hint_low.startswith("3h"):
            return "Female"
        if "tech" in hint_low or hint_low.startswith("1t") or hint_low.startswith("2t") or hint_low.startswith("3t"):
            return "Male"

    return "Male"

