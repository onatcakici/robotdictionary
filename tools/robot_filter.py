"""Rules for deciding whether a Wikidata item is a real robot, and where it belongs."""
import re

ACCEPT = {"robot", "humanoid robot", "android", "gynoid", "entertainment robot", "robotic dog", "social robot", "autonomous robot",
          "mobile robot", "industrial robot", "robotic arm", "medical robots", "surgical robot", "service robot", "delivery robot", "agricultural robot",
          "legged robot", "bipedal robot", "rescue robot", "robotic vacuum cleaner", "domestic robot", "personal robot", "telepresence robot",
          "educational robot", "Robot kit", "robot kit", "lunar rover", "Mars rover", "rover", "autonomous underwater vehicle",
          "remotely operated underwater vehicle", "powered exoskeleton", "automaton", "Spherical robot", "snake robot",
          "swarm robot", "microbot", "phototrope", "cocktail robot", "companion robot", "robot scientist", "shopping robot", "liquid handling robot",
          "articulated robot", "selective compliance assembly robot arm", "unmanned surface vehicle", "autonomous watercraft", "underwater glider",
          "robotic lawn mower", "quadruped robot", "toy robot", "collaborative robot", "cobot", "hexapod robot", "walking robot", "planetary rover",
          "security robot", "cleaning robot", "robotic hand", "animatronics", "mobile manipulator", "rehabilitation robot",
          "inspection robot", "firefighting robot", "unmanned underwater vehicle"}
REJECT = {"CubeSat", "space probe", "spacecraft", "spacecraft model", "artificial satellite", "satellite", "lander", "Mars lander", "lunar lander",
          "orbiter", "space telescope", "star", "exoplanet", "aircraft", "aircraft model", "unmanned aerial vehicle", "type of drone", "missile model",
          "loitering munition", "weapon model", "car model", "vehicle model", "autonomous car", "self-driving car", "autonomous bus", "autonomous truck",
          "company", "business", "enterprise", "public company", "organization", "human", "fictional robot", "fictional character", "fictional android",
          "fictional humanoid", "video game character", "film character", "television character", "literary character", "character", "anime character",
          "comics character", "film", "television series", "video game", "literary work", "album", "song", "single", "Wikimedia list article",
          "Wikimedia disambiguation page", "type of robot", "Five Nights at Freddy's animatronic", "robotics competition", "competition",
          "recurring event", "software", "operating system", "toy line", "media franchise", "miniature action figure", "sex robot", "sex doll",
          "combat robot", "uncrewed spaceflight", "space mission", "research project", "technical standard",
          "military robot", "unmanned ground vehicle", "EOD robots", "bomb disposal robot", "military vehicle", "military equipment",
          "unmanned combat ground vehicle", "armoured fighting vehicle", "tank", "warship", "naval mine", "military drone",
          "unmanned combat vehicle", "sentry gun", "military unmanned ground vehicle"}
FICT = re.compile(r"fictional|character|in the (film|series|novel|game|anime|manga|comic)|video game|television series|comic|novel by|film by|toy line|"
                  r"transformers|star wars|doctor who|gundam|cartoon|mascot")
NONROBOT = re.compile(r"\b(company|corporation|manufacturer|startup|competition|contest|award|conference|festival|university|laboratory|institute|"
                      r"programme|program|software|framework|algorithm|museum|film|album|song|band|person|engineer|scientist)\b")
SECTION_OF = {"humanoid robot": "humanoids", "android": "humanoids", "gynoid": "humanoids", "bipedal robot": "humanoids",
              "robotic dog": "quadrupeds", "quadruped robot": "quadrupeds", "legged robot": "quadrupeds", "walking robot": "quadrupeds", "hexapod robot": "quadrupeds",
              "lunar rover": "rovers", "Mars rover": "rovers", "rover": "rovers", "planetary rover": "rovers",
              "autonomous underwater vehicle": "marine", "remotely operated underwater vehicle": "marine", "unmanned surface vehicle": "marine",
              "autonomous watercraft": "marine", "underwater glider": "marine", "unmanned underwater vehicle": "marine",
              "industrial robot": "arms", "robotic arm": "arms", "articulated robot": "arms", "selective compliance assembly robot arm": "arms",
              "liquid handling robot": "arms", "collaborative robot": "arms", "cobot": "arms", "robotic hand": "arms", "cocktail robot": "arms",
              "robot scientist": "arms", "medical robots": "medical", "surgical robot": "medical", "powered exoskeleton": "medical",
              "rehabilitation robot": "medical", "robotic vacuum cleaner": "wheeled", "robotic lawn mower": "wheeled", "delivery robot": "wheeled",
              "unmanned ground vehicle": "wheeled", "telepresence robot": "wheeled", "security robot": "wheeled", "shopping robot": "wheeled",
              "agricultural robot": "wheeled", "cleaning robot": "wheeled", "mobile robot": "wheeled", "EOD robots": "wheeled",
              "bomb disposal robot": "wheeled", "firefighting robot": "wheeled", "mobile manipulator": "wheeled", "military robot": "wheeled"}
KIND_OF = {"robotic dog": "robot dog", "medical robots": "medical robot", "EOD robots": "bomb disposal robot", "Robot kit": "robot kit",
           "robotic vacuum cleaner": "robot vacuum cleaner", "robotic arm": "robot arm", "animatronics": "animatronic figure"}
COUNTRY = {"People's Republic of China": "China", "United States of America": "United States", "Kingdom of the Netherlands": "Netherlands",
           "Republic of China": "Taiwan", "Russian Federation": "Russia", "Republic of Korea": "South Korea", "Czech Republic": "Czechia",
           "Union of Soviet Socialist Republics": "Soviet Union", "State of Israel": "Israel", "Kingdom of Denmark": "Denmark"}

WEAPON = re.compile(r"\b(attack|kamikaze|explosive|strike|suicide|munition|missile|weapon|armed|combat|lethal|torpedo)\b")
# Military machines are left out of the dictionary altogether.
MILITARY = re.compile(r"\b(military|army|navy|naval|marine corps|armed forces|defen[cs]e (forces|ministry|contractor|research|company)|warfare|battlefield|"
                      r"soldiers?|troops|infantry|mine ?(hunting|countermeasures?|clearance|disposal)|minehunt\w*|reconnaissance|bomb disposal|"
                      r"explosive ordnance|ordnance disposal|sentry|tactical|uncrewed (ground|surface) (combat )?vehicle|unmanned (ground|surface|combat) vehicle)\b")

def is_robot(classes, description):
    cls = set(c for c in classes if c)
    d = (description or "").lower()
    if cls & REJECT: return False, "rejected class"
    if FICT.search(d): return False, "fiction"
    if WEAPON.search(d): return False, "weapon"
    if MILITARY.search(d): return False, "military"
    if cls & ACCEPT: return True, "class"
    if re.search(r"\brobot|\brover\b|android|exoskeleton|automaton|underwater vehicle", d) and not NONROBOT.search(d):
        return True, "description"
    return False, "not a robot class"

def section_for(classes, description):
    for c in classes:
        if c in SECTION_OF: return SECTION_OF[c]
    d = (description or "").lower()
    if "humanoid" in d or "android" in d: return "humanoids"
    if "rover" in d and re.search(r"moon|lunar|mars|planet", d): return "rovers"
    if re.search(r"underwater|submarine|boat|vessel", d): return "marine"
    if re.search(r"surgical|surgery|exoskeleton|rehabilitation", d): return "medical"
    if re.search(r"\barm\b|industrial robot|manipulator", d): return "arms"
    if re.search(r"quadruped|legged|dog", d): return "quadrupeds"
    if re.search(r"wheel|vacuum|mower|delivery|ground vehicle|tracked", d): return "wheeled"
    return "other"

def kind_for(classes, description):
    for c in classes:
        if c in ACCEPT and c != "robot": return KIND_OF.get(c, c)
    return "robot"
