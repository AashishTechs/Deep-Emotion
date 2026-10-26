# ==========================================================
# Deep Emotions — Words Game
# Wordle-style game for private chats and groups.
# ==========================================================

import html
import json
import random
from datetime import datetime, timezone, timedelta
from zoneinfo import ZoneInfo

import aiosqlite
from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.constants import ChatMemberStatus
from telegram.ext import ContextTypes, ApplicationHandlerStop

from bot.database import DB_PATH

UPDATES_URL = "https://t.me/BotUpdates0fficial"
DISCUSSION_URL = "https://t.me/+cGoEVo7d8YtjOTI9"
WORD_GAME_IMAGE_URL = (
    "https://raw.githubusercontent.com/"
    "AashishTechs/Deep-Emotion/main/Welcome2.jpg"
)
# Cache Telegram's file_id after the first upload so later panels reuse the
# already-uploaded photo instead of asking Telegram to fetch the image URL again.
WORD_GAME_IMAGE_FILE_ID = None
WELCOME_CAPTION = (
    "Welcome to Word Game!\n\n"
    "A fun and competitive Wordle-style game that you can play directly on Telegram.\n\n"
    "Quick Start:\n"
    "• Use /new to start a new game\n"
    "• Add me to a group with admin permissions to play with friends\n"
    "• Use /helpwords for detailed instructions and command list\n\n"
    "Ready to test your word skills? Let's play!"
)
MAX_GUESSES = 30

WORDS = {
    4: ["ABLE", "ACID", "AGED", "ALSO", "AREA", "ARMY", "AWAY", "BABY", "BACK", "BALL", "BAND", "BANK", "BASE", "BATH", "BEAR", "BEAT", "BEEN", "BELL", "BELT", "BEST", "BILL", "BIRD", "BLOW", "BLUE", "BOAT", "BODY", "BOLD", "BONE", "BOOK", "BOOM", "BORN", "BOSS", "BOTH", "BOWL", "BULK", "BURN", "BUSY", "CALL", "CALM", "CAME", "CAMP", "CARD", "CARE", "CASE", "CASH", "CITY", "CLUB", "COAL", "COAT", "CODE", "COLD", "COME", "COOK", "COOL", "COPY", "COST", "CREW", "CROP", "DARK", "DATA", "DATE", "DAWN", "DAYS", "DEAD", "DEAL", "DEAR", "DEEP", "DESK", "DIAL", "DICE", "DIET", "DIRT", "DISH", "DOOR", "DOWN", "DRAW", "DREW", "DROP", "DRUG", "DUAL", "DUST", "DUTY", "EACH", "EARN", "EASE", "EAST", "EASY", "EDGE", "ELSE", "EVEN", "EVER", "FACE", "FACT", "FADE", "FAIL", "FAIR", "FALL", "FAME", "FARM", "FAST", "FATE", "FEAR", "FEED", "FEEL", "FILE", "FILL", "FILM", "FIND", "FINE", "FIRE", "FIRM", "FISH", "FIVE", "FLAG", "FLAT", "FLOW", "FOOD", "FOOT", "FORD", "FORM", "FORT", "FOUR", "FREE", "FROM", "FUEL", "FULL", "FUND", "GAIN", "GAME", "GATE", "GAVE", "GEAR", "GIFT", "GIRL", "GIVE", "GLAD", "GOAL", "GOES", "GOLD", "GOLF", "GONE", "GOOD", "GRAY", "GREW", "GROW", "GULF", "HAIR", "HALF", "HALL", "HAND", "HANG", "HARD", "HARM", "HATE", "HAVE", "HEAD", "HEAR", "HEAT", "HELD", "HELP", "HERE", "HERO", "HIGH", "HILL", "HOLD", "HOME", "HOPE", "HOST", "HOUR", "HUGE", "HUNG", "HUNT", "HURT", "IDEA", "INCH", "INTO", "IRON", "ITEM", "JACK", "JANE", "JOBS", "JOIN", "JUMP", "JUST", "KEEN", "KEEP", "KEPT", "KICK", "KIND", "KING", "KNEW", "KNOW", "LACK", "LADY", "LAKE", "LAND", "LANE", "LAST", "LATE", "LEAD", "LEFT", "LESS", "LIFE", "LIFT", "LIKE", "LINE", "LINK", "LIST", "LIVE", "LOAD", "LOAN", "LOCK", "LONG", "LOOK", "LORD", "LOSE", "LOSS", "LOST", "LOVE", "LUCK", "MADE", "MAIL", "MAIN", "MAKE", "MALE", "MANY", "MARK", "MASS", "MATE", "MEAL", "MEAN", "MEAT", "MEET", "MENU", "MERE", "MILE", "MILK", "MIND", "MINE", "MISS", "MODE", "MOOD", "MOON", "MORE", "MOST", "MOVE", "MUCH", "MUST", "NAME", "NEAR", "NEAT", "NECK", "NEED", "NEWS", "NEXT", "NICE", "NINE", "NODE", "NONE", "NOSE", "NOTE", "ONCE", "ONLY", "ONTO", "OPEN", "ORAL", "OVER", "PACE", "PACK", "PAGE", "PAID", "PAIN", "PAIR", "PARK", "PART", "PASS", "PAST", "PATH", "PEAK", "PICK", "PINK", "PIPE", "PLAN", "PLAY", "PLOT", "PLUS", "POEM", "POET", "POLL", "POOL", "POOR", "PORT", "POST", "PULL", "PURE", "PUSH", "QUIT", "RACE", "RAIL", "RAIN", "RANK", "RATE", "READ", "REAL", "REAR", "RELY", "RENT", "REST", "RICE", "RICH", "RIDE", "RING", "RISE", "RISK", "ROAD", "ROCK", "ROLE", "ROLL", "ROOF", "ROOM", "ROOT", "ROSE", "RULE", "RUSH", "SAFE", "SAGE", "SAID", "SAIL", "SALE", "SALT", "SAME", "SAND", "SAVE", "SEAT", "SEED", "SEEK", "SEEM", "SEEN", "SELF", "SELL", "SEND", "SENT", "SHIP", "SHOP", "SHOT", "SHOW", "SHUT", "SICK", "SIDE", "SIGN", "SILK", "SING", "SITE", "SIZE", "SKIN", "SLOW", "SNOW", "SOFT", "SOIL", "SOLD", "SOLE", "SOME", "SONG", "SOON", "SORT", "SOUL", "STAR", "STAY", "STEP", "STOP", "SUCH", "SUIT", "SURE", "TAKE", "TALE", "TALK", "TALL", "TANK", "TAPE", "TASK", "TEAM", "TECH", "TELL", "TEND", "TERM", "TEST", "TEXT", "THAN", "THAT", "THEM", "THEN", "THEY", "THIN", "THIS", "THUS", "TILL", "TIME", "TINY", "TOLD", "TONE", "TOOK", "TOOL", "TOUR", "TOWN", "TREE", "TRIP", "TRUE", "TUNE", "TURN", "TYPE", "UNIT", "UPON", "USED", "USER", "VARY", "VAST", "VERY", "VIEW", "VOTE", "WAGE", "WAIT", "WAKE", "WALK", "WALL", "WANT", "WARD", "WARM", "WARN", "WASH", "WAVE", "WAYS", "WEAK", "WEAR", "WEEK", "WELL", "WENT", "WERE", "WEST", "WHAT", "WHEN", "WIDE", "WIFE", "WILD", "WILL", "WIND", "WINE", "WING", "WIRE", "WISE", "WISH", "WITH", "WOOD", "WORD", "WORE", "WORK", "YARD", "YEAH", "YEAR", "YOUR", "ZERO", "ZONE", "ACHE", "ACRE", "ACTS", "ADDS", "AGES", "AIDS", "AIMS", "AIRS", "AIRY", "ALES", "ALLY", "AMID", "AMPS", "ANEW", "ANTS", "APEX", "ARCH", "ARTS", "ATOM", "AUNT", "AUTO", "AXIS", "AXLE", "BAKE", "BALD", "BALE", "BALK", "BANE", "BANG", "BANS", "BARE", "BARK", "BARN", "BARS", "BASK", "BASS", "BATS", "BEAD", "BEAK", "BEAM", "BEAN", "BEDS", "BEEF", "BEEP", "BEER", "BEES", "BEGS", "BEND", "BENT", "BIAS", "BIDE", "BIKE", "BIND", "BINS", "BITE", "BITS", "BLED", "BLEW", "BLOB", "BLOC", "BLOT", "BLUR", "BOAR", "BOAS", "BOIL", "BOLT", "BOMB", "BOND", "BONY", "BOON", "BOOT", "BORE", "BURY", "BUST", "BUTS", "CABS", "CAGE", "CAKE", "CALF", "CANS", "CAPE", "CAPS", "CART", "CATS", "CAVE", "CEIL", "CELL", "CENT", "CHAP", "CHAR", "CHAT", "CHEF", "CHEW", "CHIC", "CHIN", "CHIP", "CHOP", "CHUM", "CITE", "CLAD", "CLAM", "CLAN", "CLAP", "CLAY", "CLOG", "CLOT", "CLUE", "COAX", "COBB", "COCK", "COBS", "COIL", "COIN", "COKE", "COLA", "COLT", "COMB", "CONE", "CONS", "COPE", "CORD", "CORE", "CORK", "CORN", "COVE", "COWL", "CRAB", "CRAM", "CRAP", "CRIB", "CUES", "CURE", "CURL", "CUTE", "DABS", "DADS", "DAME", "DAMP", "DARE", "DART", "DASH", "DAZE", "DEAN", "DECK", "DEED", "DEEM", "DEER", "DELL", "DEMO", "DENS", "DENT", "DEPT", "DIME", "DIMS", "DINE", "DING", "DINO", "DIPS", "DIRE", "DISC", "DIVE", "DOCK", "DOES", "DOME", "DONE", "DONG", "DOPE", "DOVE", "DRAB", "DRAG", "DRAM", "DRAT", "DRIP", "DUCK", "DUDE", "DUES", "DUET", "DULL", "DUMP", "DUNE", "DUNK", "DUPE", "DUSK", "EARS", "EATS", "ECHO", "EDIT", "EELS", "EGGS", "ELMS", "EMIT", "ENDS", "ENVY", "EPIC", "ERAS", "ERGO", "ETCH", "EURO", "EXAM", "EXPO"],
    5: ["ABOUT", "ABOVE", "ABUSE", "ACTOR", "ACUTE", "ADMIT", "ADOPT", "ADULT", "AFTER", "AGAIN", "AGENT", "AGREE", "AHEAD", "ALARM", "ALBUM", "ALERT", "ALIEN", "ALIGN", "ALIKE", "ALIVE", "ALLOW", "ALONE", "ALONG", "ALTER", "ANGEL", "ANGER", "ANGLE", "ANGRY", "APART", "APPLE", "APPLY", "ARENA", "ARGUE", "ARISE", "ARRAY", "ASIDE", "ASSET", "AUDIO", "AUDIT", "AVOID", "AWARD", "AWARE", "BADLY", "BAKER", "BASES", "BASIC", "BASIS", "BEACH", "BEGAN", "BEGIN", "BEING", "BELOW", "BENCH", "BILLY", "BIRTH", "BLACK", "BLAME", "BLANK", "BLAST", "BLIND", "BLOCK", "BLOOD", "BOARD", "BOOST", "BOOTH", "BOUND", "BRAIN", "BRAND", "BREAD", "BREAK", "BREED", "BRIEF", "BRING", "BROAD", "BROKE", "BROWN", "BUILD", "BUILT", "BUYER", "CABIN", "CABLE", "CALIF", "CARRY", "CATCH", "CAUSE", "CHAIN", "CHAIR", "CHAOS", "CHARM", "CHART", "CHASE", "CHEAP", "CHECK", "CHEST", "CHIEF", "CHILD", "CHINA", "CHOSE", "CIVIL", "CLAIM", "CLASS", "CLEAN", "CLEAR", "CLICK", "CLOCK", "CLOSE", "COACH", "COAST", "COULD", "COUNT", "COURT", "COVER", "CRAFT", "CRASH", "CREAM", "CRIME", "CROSS", "CROWD", "CROWN", "CURVE", "CYCLE", "DAILY", "DANCE", "DATED", "DEALT", "DEATH", "DEBUT", "DELAY", "DEPTH", "DOING", "DOUBT", "DOZEN", "DRAFT", "DRAMA", "DRAWN", "DREAM", "DRESS", "DRINK", "DRIVE", "EARLY", "EARTH", "EIGHT", "ELITE", "EMPTY", "ENEMY", "ENJOY", "ENTER", "ENTRY", "EQUAL", "ERROR", "EVENT", "EVERY", "EXACT", "EXIST", "EXTRA", "FAITH", "FALSE", "FAULT", "FIBER", "FIELD", "FIFTH", "FIFTY", "FIGHT", "FINAL", "FIRST", "FIXED", "FLASH", "FLEET", "FLOOR", "FOCUS", "FORCE", "FORTH", "FORTY", "FORUM", "FOUND", "FRAME", "FRANK", "FRAUD", "FRESH", "FRONT", "FRUIT", "FULLY", "FUNNY", "GIANT", "GIVEN", "GLASS", "GLOBE", "GOING", "GRACE", "GRADE", "GRAND", "GRANT", "GRASS", "GREAT", "GREEN", "GROSS", "GROUP", "GROWN", "GUARD", "GUESS", "GUEST", "GUIDE", "HAPPY", "HEART", "HEAVY", "HENCE", "HONEY", "HORSE", "HOTEL", "HOUSE", "HUMAN", "IDEAL", "IMAGE", "INDEX", "INNER", "INPUT", "ISSUE", "JAPAN", "JOINT", "JUDGE", "KNOWN", "LABEL", "LARGE", "LASER", "LATER", "LAUGH", "LAYER", "LEARN", "LEASE", "LEAST", "LEAVE", "LEGAL", "LEVEL", "LIGHT", "LIMIT", "LOCAL", "LOGIC", "LOOSE", "LOWER", "LUCKY", "LUNCH", "MAJOR", "MAKER", "MARCH", "MATCH", "MAYBE", "MAYOR", "MEANT", "MEDIA", "METAL", "MIGHT", "MINOR", "MINUS", "MIXED", "MODEL", "MONEY", "MONTH", "MORAL", "MOTOR", "MOUNT", "MOUSE", "MOUTH", "MOVED", "MOVIE", "MUSIC", "NEEDS", "NEVER", "NEWLY", "NIGHT", "NOISE", "NORTH", "NOTED", "NOVEL", "NURSE", "OCCUR", "OCEAN", "OFFER", "OFTEN", "ORDER", "OTHER", "OUGHT", "PAINT", "PANEL", "PAPER", "PARTY", "PEACE", "PHASE", "PHONE", "PHOTO", "PIANO", "PIECE", "PILOT", "PITCH", "PLACE", "PLAIN", "PLANE", "PLANT", "PLATE", "POINT", "POUND", "POWER", "PRESS", "PRICE", "PRIDE", "PRIME", "PRINT", "PRIOR", "PRIZE", "PROOF", "PROUD", "PROVE", "QUEEN", "QUICK", "QUIET", "QUITE", "RADIO", "RAISE", "RANGE", "RAPID", "RATIO", "REACH", "READY", "REFER", "RIGHT", "RIVAL", "RIVER", "ROBOT", "ROGER", "ROUGH", "ROUND", "ROUTE", "ROYAL", "RURAL", "SCALE", "SCENE", "SCOPE", "SCORE", "SENSE", "SERVE", "SEVEN", "SHALL", "SHAPE", "SHARE", "SHARP", "SHEET", "SHELF", "SHELL", "SHIFT", "SHINE", "SHIRT", "SHOCK", "SHOOT", "SHORT", "SHOWN", "SIGHT", "SINCE", "SIXTH", "SKILL", "SLEEP", "SLICE", "SLIDE", "SMALL", "SMART", "SMILE", "SMITH", "SMOKE", "SOLID", "SOLVE", "SORRY", "SOUND", "SOUTH", "SPACE", "SPARE", "SPEAK", "SPEED", "SPEND", "SPENT", "SPLIT", "SPOKE", "SPORT", "STAFF", "STAGE", "STAKE", "STAND", "START", "STATE", "STEAM", "STEEL", "STICK", "STILL", "STOCK", "STONE", "STOOD", "STORE", "STORM", "STORY", "STRIP", "STUCK", "STUDY", "STUFF", "STYLE", "SUGAR", "SUITE", "SUPER", "SWEET", "TABLE", "TAKEN", "TASTE", "TAXES", "TEACH", "TEAMS", "TEETH", "TERRY", "THANK", "THEFT", "THEIR", "THEME", "THERE", "THESE", "THICK", "THING", "THINK", "THIRD", "THOSE", "THREE", "THREW", "THROW", "TIGHT", "TIMES", "TIRED", "TITLE", "TODAY", "TOPIC", "TOTAL", "TOUCH", "TOUGH", "TOWER", "TRACK", "TRADE", "TRAIN", "TREAT", "TREND", "TRIAL", "TRIED", "TRIES", "TRUCK", "TRULY", "TRUST", "TRUTH", "TWICE", "UNDER", "UNDUE", "UNION", "UNITY", "UNTIL", "UPPER", "UPSET", "URBAN", "USAGE", "USUAL", "VALID", "VALUE", "VIDEO", "VIRUS", "VISIT", "VITAL", "VOICE", "WASTE", "WATCH", "WATER", "WHEEL", "WHERE", "WHICH", "WHILE", "WHITE", "WHOLE", "WHOSE", "WOMAN", "WOMEN", "WORLD", "WORRY", "WORSE", "WORST", "WORTH", "WOULD", "WRITE", "WRONG", "WROTE", "YOUNG", "YOUTH", "ABACK", "ABAFT", "ABASH", "ABBEY", "ABBOT", "ABIDE", "ABODE", "ABORT", "ADORE", "ADORN", "AFFIX", "AFOOT", "AFOUL", "AGATE", "AGAVE", "AGILE", "AGING", "AGLOW", "AGONY", "AGORA", "AIDED", "AIMED", "AIRED", "AISLE", "ALGAE", "ALIBI", "ALLOT", "ALLOY", "ALOFT", "ALPHA", "ALTAR", "AMASS", "AMBER", "AMBLE", "AMEND", "AMINO", "AMISS", "AMITY", "AMPLE", "AMPLY", "AMUSE", "ANIME", "ANKLE", "ANNEX", "ANNOY", "ANODE", "ANTIC", "ANVIL", "APING", "APNEA", "APRON", "APTLY", "ARBOR", "ARDOR", "AREAS", "ARGON", "ARMED", "ARMOR", "AROMA", "ASCOT", "ASHEN", "ATLAS", "ATONE", "ATTIC", "AXIAL", "AXIOM", "BACON", "BADGE", "BAGEL", "BAGGY", "BAIZE", "BALER", "BALMY", "BANAL", "BANJO", "BARON", "BASIL", "BATCH", "BATHE", "BATON", "BATTY", "BAYOU", "BEADY", "BEARD", "BEAST", "BEFIT", "BEFOG", "BEGAT", "BEGET", "BEGUN", "BELCH", "BELIE", "BELLE", "BELLY", "BERET", "BERRY", "BERTH", "BESET", "BESOT", "BETEL", "BEVEL", "BICEP", "BIDDY", "BILGE", "BINGE", "BINGO", "BIPED", "BIRCH", "BISON", "BITCH", "BLADE", "BLAND", "BLARE", "BLAZE", "BLEAK", "BLEAT", "BLEED", "BLEND", "BLESS", "BLIMP", "BLISS", "BLITZ", "BLOND", "BLURB", "BLUSH", "BOBBY", "BOGUS", "BONEY", "BONUS", "BOOZE", "BORAX", "BORNE", "BOSOM", "BOSSY", "BOTCH", "BOWEL", "BOXER", "BRACE", "BRAID", "BRAKE", "BRASS", "BRAVE", "BRAVO", "BRAWL", "BRAWN", "BREAM", "BRIBE", "BRICK", "BRIDE", "BRINE", "BRISK", "BROIL", "BROOD", "BROOK", "BROTH", "BRUNT", "BRUSH", "BRUTE", "BUDDY", "BUGGY", "BUGLE", "BULGE", "BULKY", "BULLY", "BUNCH", "BUNNY", "BURLY", "BURNT", "BURST", "BUSHY", "BUTCH", "BYLAW", "CABAL", "CAMEO", "CAMEL", "CANAL", "CANDY", "CANNY", "CANOE", "CANON", "CAPER", "CARAT", "CARGO", "CAROL", "CAROM", "CARVE", "CASTE", "CATER", "CATTY", "CAVIL", "CEASE", "CEDAR", "CELLO", "CENSE", "CHAFE", "CHAFF", "CHALK", "CHAMP", "CHANT", "CHARD"],
    6: ["ACTION", "ACTIVE", "ACTUAL", "ADVICE", "ADVISE", "AFFECT", "AFFORD", "AFRAID", "AGENCY", "AGENDA", "ALMOST", "ALWAYS", "AMOUNT", "ANIMAL", "ANNUAL", "ANSWER", "ANYONE", "ANYWAY", "APPEAL", "APPEAR", "AROUND", "ARRIVE", "ARTIST", "ASPECT", "ASSIGN", "ASSIST", "ASSUME", "ATTACK", "ATTEND", "AUTHOR", "AUTUMN", "AVENUE", "BACKED", "BARELY", "BATTLE", "BEAUTY", "BECAME", "BECOME", "BEFORE", "BEHALF", "BEHIND", "BELIEF", "BELONG", "BERLIN", "BETTER", "BORDER", "BOTTLE", "BOTTOM", "BOUGHT", "BRANCH", "BREATH", "BRIDGE", "BRIGHT", "BROKEN", "BUDGET", "BURIED", "BUTTON", "CAMERA", "CANCER", "CANNOT", "CAREER", "CASTLE", "CAUGHT", "CAUSED", "CENTER", "CENTRE", "CHANCE", "CHANGE", "CHARGE", "CHOICE", "CHOOSE", "CHOSEN", "CHURCH", "CIRCLE", "CLIENT", "CLOSED", "CLOSER", "COFFEE", "COLUMN", "COMBAT", "COMING", "COMMON", "COMPET", "COMPLY", "COPIED", "CORNER", "COSTLY", "COUNTY", "COUPLE", "COURSE", "CREATE", "CREDIT", "CRISIS", "CUSTOM", "DAMAGE", "DANGER", "DEBATE", "DECADE", "DECIDE", "DEEPER", "DEFEAT", "DEFEND", "DEFINE", "DEGREE", "DEMAND", "DEPEND", "DEPUTY", "DESERT", "DESIGN", "DESIRE", "DETAIL", "DEVICE", "DIFFER", "DINNER", "DIRECT", "DOCTOR", "DOLLAR", "DOMAIN", "DOUBLE", "DRIVEN", "DRIVER", "DURING", "EASILY", "EATING", "EDITOR", "EFFECT", "EFFORT", "EIGHTH", "EITHER", "ELEVEN", "EMERGE", "EMPIRE", "EMPLOY", "ENABLE", "ENDING", "ENERGY", "ENGAGE", "ENGINE", "ENOUGH", "ENSURE", "ENTIRE", "EQUITY", "ESCAPE", "ESTATE", "ETHNIC", "EXCEPT", "EXCITE", "EXCUSE", "EXPAND", "EXPECT", "EXPERT", "EXPORT", "EXTEND", "EXTENT", "FACTOR", "FAILED", "FAIRLY", "FAMILY", "FAMOUS", "FATHER", "FELLOW", "FEMALE", "FIGURE", "FILING", "FINGER", "FINISH", "FLIGHT", "FOLLOW", "FORCED", "FOREST", "FORMAL", "FORMAT", "FORMER", "FOSTER", "FRANCE", "FRIEND", "FUTURE", "GARDEN", "GATHER", "GENDER", "GENTLE", "GLOBAL", "GROUND", "GROWTH", "HANDLE", "HAPPEN", "HEALTH", "HEAVEN", "HEIGHT", "HELPED", "HONEST", "HORSES", "HOSPITAL", "HOTELS", "HUMOUR", "HUNDRED", "IMPACT", "IMPORT", "INCOME", "INDEED", "INJURY", "INSIDE", "INSIST", "INTEND", "INTENT", "INVEST", "ISLAND", "ITSELF", "JERSEY", "JIMMY", "JOSEPH", "JUNIOR", "KILLED", "LABOUR", "LATEST", "LATTER", "LAUNCH", "LAWYER", "LEADER", "LEAGUE", "LENGTH", "LESSON", "LETTER", "LIKELY", "LINKED", "LISTEN", "LITTLE", "LIVING", "LOSING", "LONDON", "MAINLY", "MAKING", "MANAGE", "MANNER", "MARKET", "MASTER", "MATTER", "MEDIUM", "MEMBER", "MEMORY", "MENTAL", "METHOD", "MIDDLE", "MILLION", "MINUTE", "MIRROR", "MOBILE", "MODERN", "MODEST", "MOMENT", "MOSTLY", "MOTHER", "MOTION", "MOVING", "MURDER", "MUSEUM", "MUTUAL", "MYSELF", "NATURE", "NEARLY", "NIGHTS", "NORMAL", "NOTICE", "NUMBER", "OBJECT", "OBTAIN", "OFFICE", "ONLINE", "OPTION", "ORANGE", "ORIGIN", "OUTPUT", "OXYGEN", "PALACE", "PARENT", "PARTLY", "PEOPLE", "PERIOD", "PERSON", "PLANET", "PLAYER", "PLEASE", "PLENTY", "POCKET", "POLICY", "POLICE", "POLICY", "POPULAR", "POTATO", "PRETTY", "PRINCE", "PRISON", "PROBLEM", "PRODUCE", "PROFIT", "PROPER", "PROPOSE", "PUBLIC", "PURPOSE", "PURSUE", "RANDOM", "READER", "REALLY", "REASON", "RECALL", "RECENT", "RECORD", "REDUCE", "REFORM", "REGARD", "REGION", "RELATE", "RELIEF", "REMAIN", "REMIND", "REMOVE", "REPLACE", "REPORT", "RESULT", "RETURN", "REVEAL", "REVIEW", "RIGHTS", "RISING", "ROBERT", "ROCKET", "RUNNER", "SAMPLE", "SAVING", "SCHOOL", "SCREEN", "SEARCH", "SEASON", "SECOND", "SECRET", "SECTOR", "SECURE", "SELECT", "SELLER", "SENIOR", "SERIES", "SERVES", "SETTLE", "SEVERE", "SHOULD", "SIGNAL", "SIMPLE", "SIMPLY", "SINGLE", "SISTER", "SITUAL", "SOCIAL", "SOCCER", "SOURCE", "SPEECH", "SPIRIT", "SPREAD", "SPRING", "SQUARE", "STABLE", "STATUS", "STRAIN", "STRANGE", "STREET", "STRIKE", "STRING", "STRONG", "STRUGGLE", "STUDENT", "SUBJECT", "SUCCESS", "SUDDEN", "SUFFER", "SUMMER", "SUPPLY", "SUPPORT", "SURELY", "SURVEY", "SYSTEM", "TAKING", "TARGET", "TAUGHT", "THEORY", "THIRTY", "THOUGHT", "THROUGH", "TICKET", "TIMING", "TISSUE", "TOWARD", "TRAVEL", "TREATY", "TRYING", "TURNED", "TWELVE", "UNABLE", "UNIQUE", "UNITED", "UNLESS", "UNLIKE", "UPDATE", "USEFUL", "VALLEY", "VARIED", "VICTIM", "VIEWER", "VISION", "VISUAL", "VOLUME", "WALKED", "WEALTH", "WEAPON", "WEEKLY", "WEIGHT", "WINDOW", "WINNER", "WINTER", "WITHIN", "WONDER", "WORKER", "WRITER", "YELLOW", "ABACUS", "ABATED", "ABATES", "ABBOTS", "ABDUCT", "ABJECT", "ABJURE", "ABLAZE", "ABLEST", "ABROAD", "ABSENT", "ABSORB", "ABUSED", "ABUSER", "ACCENT", "ACCEPT", "ACCESS", "ACCORD", "ACCRUE", "ACCUSE", "ACETIC", "ACIDIC", "ACROSS", "ACTING", "ACTORS", "ACUITY", "ACUMEN", "ADAGES", "ADDICT", "ADDING", "ADDLED", "ADHERE", "ADJOIN", "ADJUST", "ADMIRE", "ADMITS", "ADOPTS", "ADORER", "ADORNS", "ADULTS", "ADVENT", "ADVERB", "AERIAL", "AFFAIR", "AFFIRM", "AFIELD", "AFLOAT", "AGHAST", "AGINGS", "AGLEAM", "AGNATE", "AGONIC", "AGORAS", "AGREED", "AGREES", "AIDING", "AIMING", "AIRING", "ALARMS", "ALBINO", "ALBUMS", "ALCOVE", "ALERTS", "ALIGHT", "ALKALI", "ALLIED", "ALLIES", "ALMOND", "ALPINE", "ALTARS", "AMBUSH", "AMENDS", "AMIDST", "AMUSED", "AMUSER", "ANCHOR", "ANGELS", "ANGLED", "ANGLER", "ANGLES", "ANKLES", "ANNEXE", "ANTICS", "APACHE", "APATHY", "APPEND", "APPLES", "APRONS", "ARABLE", "ARCADE", "ARCHER", "ARCHES", "ARDENT", "ARENAS", "ARGENT", "ARGUES", "ARMADA", "ARMIES", "ARMING", "ARMORS", "AROUSE", "ARRAYS", "ASCEND", "ASHORE", "ASIDES", "ASPENS", "ASSAIL", "ASSAYS", "ASSETS", "ASSORT", "ASSURE", "ASTERN", "ASTHMA", "ASTUTE", "ASYLUM", "ATOMIC", "ATONED", "ATONES", "ATTACH", "ATTAIN", "ATTICS", "ATTIRE", "ATTUNE", "AUBURN", "AUDIOS", "AUGUST", "AUNTIE", "AUTISM", "AVATAR", "AVERTS", "AVIARY", "AWAKEN", "AWARDS", "AWNING", "BABBLE", "BABIES", "BACKER", "BACKUP", "BADGER", "BADGES", "BAGGED", "BAILER", "BAKING", "BALDER", "BALLET", "BALLOT", "BALSAM", "BAMBOO", "BANANA", "BANDIT", "BANGED", "BANNER", "BARBER", "BARING", "BARKED", "BARLEY", "BARREL", "BARREN", "BARTER", "BASALT", "BASICS", "BASKET", "BASTED", "BASTES", "BATTED", "BATTER", "BAUBLE", "BAWLED", "BEACON", "BEADED", "BEAKER", "BEAMED", "BEANED", "BEARDS", "BEATEN", "BEATER", "BEAVER", "BEDDED", "BEDDER", "BEDLAM", "BEDPAN", "BEEFED", "BEFALL", "BEGINS", "BEGONE", "BEHAVE", "BEHOLD", "BEHOVE", "BELIES", "BELLED", "BELLOW", "BELTED", "BENDER", "BENIGN", "BERATE", "BERETS", "BESIDE", "BESTED", "BEVELS", "BEWARE"]
}
WORDS = {size: sorted({word for word in words if len(word) == size}) for size, words in WORDS.items()}

def _connect():
    return aiosqlite.connect(DB_PATH)

async def init_word_game_db():
    async with _connect() as db:
        await db.execute("""
            CREATE TABLE IF NOT EXISTS word_games (
                chat_id INTEGER PRIMARY KEY,
                owner_user_id INTEGER NOT NULL,
                word TEXT NOT NULL,
                word_length INTEGER NOT NULL,
                guesses_json TEXT NOT NULL DEFAULT '[]',
                active INTEGER NOT NULL DEFAULT 1,
                panel_message_id INTEGER,
                started_at TEXT NOT NULL,
                daily_mode INTEGER NOT NULL DEFAULT 0,
                daily_date TEXT,
                thread_id INTEGER
            )
        """)
        cur = await db.execute("PRAGMA table_info(word_games)")
        columns = {row[1] for row in await cur.fetchall()}
        if "daily_mode" not in columns:
            await db.execute("ALTER TABLE word_games ADD COLUMN daily_mode INTEGER NOT NULL DEFAULT 0")
        if "daily_date" not in columns:
            await db.execute("ALTER TABLE word_games ADD COLUMN daily_date TEXT")
        if "thread_id" not in columns:
            await db.execute("ALTER TABLE word_games ADD COLUMN thread_id INTEGER")
        await db.execute("""
            CREATE TABLE IF NOT EXISTS word_game_allowed_topics (
                chat_id INTEGER NOT NULL,
                thread_id INTEGER NOT NULL,
                topic_name TEXT NOT NULL DEFAULT '',
                updated_by INTEGER NOT NULL,
                updated_at TEXT NOT NULL,
                PRIMARY KEY (chat_id, thread_id)
            )
        """)
        await db.execute("""
            CREATE TABLE IF NOT EXISTS word_game_topic_lengths (
                chat_id INTEGER NOT NULL,
                thread_id INTEGER NOT NULL,
                allowed_lengths_json TEXT NOT NULL,
                default_length INTEGER NOT NULL,
                updated_by INTEGER NOT NULL,
                updated_at TEXT NOT NULL,
                PRIMARY KEY (chat_id, thread_id)
            )
        """)
        await db.execute("""
            CREATE TABLE IF NOT EXISTS word_game_authorized_users (
                chat_id INTEGER NOT NULL,
                user_id INTEGER NOT NULL,
                display_name TEXT NOT NULL,
                added_by INTEGER NOT NULL,
                added_at TEXT NOT NULL,
                PRIMARY KEY (chat_id, user_id)
            )
        """)
        await db.execute("""
            CREATE TABLE IF NOT EXISTS word_game_scores (
                user_id INTEGER PRIMARY KEY,
                display_name TEXT NOT NULL,
                wins INTEGER NOT NULL DEFAULT 0,
                games INTEGER NOT NULL DEFAULT 0,
                total_guesses INTEGER NOT NULL DEFAULT 0
            )
        """)
        await db.commit()

def _button(label, callback_data=None, url=None, style=None):
    return InlineKeyboardButton(
        label,
        callback_data=callback_data,
        url=url,
        style=style,
    )

def game_keyboard():
    # Keep the welcome panel buttons: Update, Help, and Discussion.
    return InlineKeyboardMarkup([
        [_button("🔔 Update", url=UPDATES_URL, style="success"), _button("Help", callback_data="wg:help", style="danger"), _button("💬 Discussion", url=DISCUSSION_URL, style="primary")],
    ])


def mode_keyboard():
    return InlineKeyboardMarkup([
        [_button("4-Letter", callback_data="wg:mode:4"), _button("5-Letter", callback_data="wg:mode:5"), _button("6-Letter", callback_data="wg:mode:6")],
        [_button("🔙 Words Game", callback_data="wg:home", style="danger")],
    ])

def footer_keyboard():
    return InlineKeyboardMarkup([
        [_button("🔔 Updates", url=UPDATES_URL, style="success"), _button("Help", callback_data="wg:help", style="danger"), _button("💬 Discussion", url=DISCUSSION_URL, style="primary")],
        [_button("🏆 Leaderboard", callback_data="wg:leaderboard", style="success"), _button("📊 My Stats", callback_data="wg:stats")],
        [_button("🛑 End Round", callback_data="wg:cancel")],
        [_button("🔙 Words Game", callback_data="wg:home", style="danger")],
    ])

def help_keyboard():
    return InlineKeyboardMarkup([
        [_button("🎮 How To Play", callback_data="wg:howto", style="primary"), _button("🏆 Leaderboard", callback_data="wg:leaderboard", style="success")],
        [_button("⚙️ Group Settings", callback_data="wg:groupsettings", style="danger"), _button("📋 Other Commands", callback_data="wg:commands", style="primary")],
        [_button("🔔 Update", url=UPDATES_URL, style="success"), _button("💬 Discussion", url=DISCUSSION_URL, style="primary")],
        [_button("🔙 Words Game", callback_data="wg:home", style="danger")],
    ])

def _game_text(length, guesses, word=None, ended=False, winner=None, max_guesses=MAX_GUESSES):
    # Keep a little breathing room between the header and the guess history.
    lines = [
        "🎮 DEEP EMOTIONS · WORDS GAME",
        f"{length}-letter mode · {len(guesses)}/{max_guesses} guesses",
        "",
        "",
    ]
    for guess in guesses:
        feedback = _feedback(guess, word) if word else guess.get("feedback", "")
        lines.append(f"{feedback}  {guess['word']}")
    if winner:
        lines.extend(["", f"🏆 {winner} guessed the word correctly!", f"Answer: {word}"])
    elif ended:
        lines.extend(["", f"Round over! The word was: {word}"])
    return "\n".join(lines)

def _feedback(guess, answer):
    remaining = {}
    result = ["🟥"] * len(answer)
    for index, letter in enumerate(answer):
        if guess["word"][index] == letter:
            result[index] = "🟩"
        else:
            remaining[letter] = remaining.get(letter, 0) + 1
    for index, letter in enumerate(guess["word"]):
        if result[index] == "🟩":
            continue
        if remaining.get(letter, 0) > 0:
            result[index] = "🟨"
            remaining[letter] -= 1
    return " ".join(result)

async def _fetch_game(chat_id):
    async with _connect() as db:
        db.row_factory = aiosqlite.Row
        cur = await db.execute("SELECT * FROM word_games WHERE chat_id=?", (chat_id,))
        return await cur.fetchone()

async def _show_game(context, chat_id, row, winner=None, ended=False):
    guesses = json.loads(row["guesses_json"])
    guess_limit = 6 if row["daily_mode"] else MAX_GUESSES
    text = _game_text(row["word_length"], guesses, row["word"], ended=ended, winner=winner, max_guesses=guess_limit)
    try:
        await context.bot.edit_message_text(
            chat_id=chat_id,
            message_id=row["panel_message_id"],
            text=text,
        )
    except Exception:
        # The original panel may have been deleted or become uneditable.
        # Keep feedback visible by sending a fresh panel instead of failing silently.
        await context.bot.send_message(
            chat_id=chat_id,
            text=text,
        )

async def _start_word_round(update: Update, context: ContextTypes.DEFAULT_TYPE, length: int, daily: bool = False, daily_date: str = None, fixed_word: str = None):
    message = update.effective_message
    chat = update.effective_chat
    user = update.effective_user
    if not message or not chat or not user:
        return
    if daily and chat.type != "private":
        await message.reply_text("📅 Daily WordSeek is available only in my private chat. Open @DeepEmotionsBot and use /daily.")
        return
    if length not in WORDS:
        await message.reply_text("Choose a word length: /new4, /new5, or /new6.")
        return
    if chat.type in ("group", "supergroup"):
        thread_id = getattr(message, "message_thread_id", None)
        if not await _topic_is_allowed(chat.id, thread_id):
            await message.reply_text("❌ WordSeek is restricted to the configured forum topic(s). Start the game in an allowed topic.")
            return
    old = await _fetch_game(chat.id)
    if old and old["active"]:
        hint = " Use /pausedaily to leave Daily mode." if old["daily_mode"] else " Finish it first with /end."
        await message.reply_text("⏳ A Words Game round is already active in this chat." + hint)
        return
    word = fixed_word or random.choice(WORDS[length])
    limit = 6 if daily else MAX_GUESSES
    title = "📅 DAILY WORDSEEK" if daily else "🎮 DEEP EMOTIONS · WORDS GAME"
    panel = await message.reply_text(
        f"{title}\n{length}-letter mode · 0/{limit} guesses\n\n",
    )
    async with _connect() as db:
        await db.execute(
            """INSERT INTO word_games(chat_id, owner_user_id, word, word_length, guesses_json, active, panel_message_id, started_at, daily_mode, daily_date, thread_id)
               VALUES(?,?,?,?, '[]', 1, ?, ?, ?, ?, ?)
               ON CONFLICT(chat_id) DO UPDATE SET owner_user_id=excluded.owner_user_id, word=excluded.word,
               word_length=excluded.word_length, guesses_json='[]', active=1, panel_message_id=excluded.panel_message_id,
               started_at=excluded.started_at, daily_mode=excluded.daily_mode, daily_date=excluded.daily_date,
               thread_id=excluded.thread_id""",
            (chat.id, user.id, word, length, panel.message_id, datetime.now(timezone.utc).isoformat(), 1 if daily else 0, daily_date, getattr(message, "message_thread_id", None)),
        )
        await db.commit()


async def _topic_is_allowed(chat_id: int, thread_id):
    async with _connect() as db:
        cur = await db.execute(
            "SELECT thread_id FROM word_game_allowed_topics WHERE chat_id=?",
            (chat_id,),
        )
        rows = await cur.fetchall()
    if not rows:
        return True
    if thread_id is None:
        return False
    return any(int(row[0]) == int(thread_id) for row in rows)


async def setgametopic_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    message, chat, user = update.effective_message, update.effective_chat, update.effective_user
    if not message or not chat or not user:
        return
    if chat.type not in ("group", "supergroup"):
        await message.reply_text("This command must be used inside a group forum topic.")
        return
    # Telegram's is_forum flag may be missing on some message/chat objects.
    # A message_thread_id is the reliable signal that this command came from a topic.
    thread_id = getattr(message, "message_thread_id", None)
    if thread_id is None:
        await message.reply_text("Please run /setgametopic inside the forum topic you want to allow for WordSeek.")
        return
    try:
        member = await context.bot.get_chat_member(chat.id, user.id)
        if member.status not in (ChatMemberStatus.ADMINISTRATOR, "creator"):
            await message.reply_text("❌ Only group administrators can configure game topics.")
            return
    except Exception:
        await message.reply_text("❌ I couldn't verify your admin permissions. Please try again.")
        return
    async with _connect() as db:
        await db.execute(
            """INSERT INTO word_game_allowed_topics (chat_id, thread_id, topic_name, updated_by, updated_at)
               VALUES (?, ?, '', ?, ?)
               ON CONFLICT(chat_id, thread_id) DO UPDATE SET
                 updated_by=excluded.updated_by, updated_at=excluded.updated_at""",
            (chat.id, thread_id, user.id, datetime.now(timezone.utc).isoformat()),
        )
        cur = await db.execute("SELECT COUNT(*) FROM word_game_allowed_topics WHERE chat_id=?", (chat.id,))
        count = (await cur.fetchone())[0]
        await db.commit()
    await message.reply_text(f"✅ This topic is now allowed for WordSeek games.\nAllowed topics configured: {count}.")


async def unsetgametopic_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    message, chat, user = update.effective_message, update.effective_chat, update.effective_user
    if not message or not chat or not user:
        return
    if chat.type not in ("group", "supergroup"):
        await message.reply_text("This command must be used inside a group forum topic.")
        return
    # Use the topic ID instead of relying on the optional is_forum flag.
    thread_id = getattr(message, "message_thread_id", None)
    if thread_id is None:
        await message.reply_text("Please run /unsetgametopic inside the forum topic you want to remove.")
        return
    try:
        member = await context.bot.get_chat_member(chat.id, user.id)
        if member.status not in (ChatMemberStatus.ADMINISTRATOR, "creator"):
            await message.reply_text("❌ Only group administrators can configure game topics.")
            return
    except Exception:
        await message.reply_text("❌ I couldn't verify your admin permissions. Please try again.")
        return
    async with _connect() as db:
        await db.execute(
            "DELETE FROM word_game_allowed_topics WHERE chat_id=? AND thread_id=?",
            (chat.id, thread_id),
        )
        cur = await db.execute("SELECT COUNT(*) FROM word_game_allowed_topics WHERE chat_id=?", (chat.id,))
        count = (await cur.fetchone())[0]
        await db.commit()
    if count:
        await message.reply_text(f"✅ This topic has been removed from allowed WordSeek topics. Games are limited to the {count} remaining configured topic(s).")
    else:
        await message.reply_text("✅ No topic restriction remains. WordSeek can run in any topic in this forum group.")


async def _topic_length_settings(chat_id: int, thread_id: int):
    if thread_id is None:
        return None
    async with _connect() as db:
        cur = await db.execute(
            "SELECT allowed_lengths_json, default_length FROM word_game_topic_lengths WHERE chat_id=? AND thread_id=?",
            (chat_id, thread_id),
        )
        row = await cur.fetchone()
    if not row:
        return None
    try:
        allowed = {int(length) for length in json.loads(row[0])}
    except (TypeError, ValueError, json.JSONDecodeError):
        return None
    return {"allowed": allowed, "default": int(row[1])}


async def allowonlylen_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    message, chat, user = update.effective_message, update.effective_chat, update.effective_user
    if not message or not chat or not user:
        return
    if chat.type not in ("group", "supergroup") or not getattr(chat, "is_forum", False):
        await message.reply_text("This command can only be used in forum groups.")
        return
    thread_id = getattr(message, "message_thread_id", None)
    if thread_id is None:
        await message.reply_text("Please run /allowonlylen inside the forum topic you want to configure.")
        return
    try:
        member = await context.bot.get_chat_member(chat.id, user.id)
        if member.status not in (ChatMemberStatus.ADMINISTRATOR, "creator"):
            await message.reply_text("❌ Only group administrators can change allowed word lengths.")
            return
    except Exception:
        await message.reply_text("❌ I couldn't verify your admin permissions. Please try again.")
        return
    args = [arg.strip().lower() for arg in (context.args or [])]
    if len(args) == 1 and args[0] in ("off", "reset", "clear"):
        async with _connect() as db:
            await db.execute("DELETE FROM word_game_topic_lengths WHERE chat_id=? AND thread_id=?", (chat.id, thread_id))
            await db.commit()
        await message.reply_text("✅ Word length restriction removed for this topic. All lengths (4, 5, 6) are allowed.")
        return
    if not args or any(arg not in ("4", "5", "6") for arg in args):
        await message.reply_text("Usage: /allowonlylen 4\nor /allowonlylen 5 6\nUse /allowonlylen off to allow all lengths again.\nAllowed lengths: 4, 5, 6.")
        return
    lengths = list(dict.fromkeys(int(arg) for arg in args))
    async with _connect() as db:
        await db.execute(
            """INSERT INTO word_game_topic_lengths
               (chat_id, thread_id, allowed_lengths_json, default_length, updated_by, updated_at)
               VALUES (?, ?, ?, ?, ?, ?)
               ON CONFLICT(chat_id, thread_id) DO UPDATE SET
                 allowed_lengths_json=excluded.allowed_lengths_json,
                 default_length=excluded.default_length,
                 updated_by=excluded.updated_by, updated_at=excluded.updated_at""",
            (chat.id, thread_id, json.dumps(lengths), lengths[0], user.id, datetime.now(timezone.utc).isoformat()),
        )
        await db.commit()
    await message.reply_text(f"✅ Allowed word lengths for this topic: {', '.join(map(str, lengths))}.\nDefault for /new: {lengths[0]}-letter mode.")


async def new_word_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    message, chat = update.effective_message, update.effective_chat
    length = 5
    if chat and getattr(chat, 'is_forum', False) and message:
        settings = await _topic_length_settings(chat.id, getattr(message, 'message_thread_id', None))
        if settings:
            length = settings['default']
    if context.args:
        try:
            length = int(context.args[0])
        except ValueError:
            await update.effective_message.reply_text("Usage: /new or /new 4, /new 5, /new 6")
            return
    if chat and getattr(chat, 'is_forum', False) and message:
        settings = await _topic_length_settings(chat.id, getattr(message, 'message_thread_id', None))
        if settings and length not in settings['allowed']:
            await message.reply_text(f"❌ This topic only allows {', '.join(map(str, sorted(settings['allowed'])))}-letter words.")
            return
    await _start_word_round(update, context, length)


async def new4_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    message, chat = update.effective_message, update.effective_chat
    if chat and getattr(chat, 'is_forum', False) and message:
        settings = await _topic_length_settings(chat.id, getattr(message, 'message_thread_id', None))
        if settings and 4 not in settings['allowed']:
            await message.reply_text(f"❌ This topic only allows {', '.join(map(str, sorted(settings['allowed'])))}-letter words.")
            return
    await _start_word_round(update, context, 4)


async def new5_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    message, chat = update.effective_message, update.effective_chat
    if chat and getattr(chat, 'is_forum', False) and message:
        settings = await _topic_length_settings(chat.id, getattr(message, 'message_thread_id', None))
        if settings and 5 not in settings['allowed']:
            await message.reply_text(f"❌ This topic only allows {', '.join(map(str, sorted(settings['allowed'])))}-letter words.")
            return
    await _start_word_round(update, context, 5)


async def new6_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    message, chat = update.effective_message, update.effective_chat
    if chat and getattr(chat, 'is_forum', False) and message:
        settings = await _topic_length_settings(chat.id, getattr(message, 'message_thread_id', None))
        if settings and 6 not in settings['allowed']:
            await message.reply_text(f"❌ This topic only allows {', '.join(map(str, sorted(settings['allowed'])))}-letter words.")
            return
    await _start_word_round(update, context, 6)


async def end_word_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    message, chat, user = update.effective_message, update.effective_chat, update.effective_user
    if not message or not chat or not user:
        return
    row = await _fetch_game(chat.id)
    if not row or not row["active"]:
        await message.reply_text("There is no active Words Game round.")
        return
    authorized = False
    if row["owner_user_id"] != user.id:
        async with _connect() as db:
            cur = await db.execute(
                "SELECT 1 FROM word_game_authorized_users WHERE chat_id=? AND user_id=?",
                (chat.id, user.id),
            )
            authorized = await cur.fetchone() is not None
        if not authorized:
            await message.reply_text("Only the player who started this round or a user authorized with /seekauth can end it.")
            return
    async with _connect() as db:
        await db.execute("UPDATE word_games SET active=0 WHERE chat_id=?", (chat.id,))
        await db.commit()
    await message.reply_text("🛑 Words Game round ended.")


async def score_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Show a player's persistent WordSeek score."""
    message = update.effective_message
    user = update.effective_user
    if not message or not user:
        return

    target_id = user.id
    target_name = user.full_name or user.first_name or str(user.id)
    if context.args:
        target = context.args[0].strip()
        if target.isdigit():
            target_id = int(target)
            target_name = target
        elif target.startswith("@") and len(target) > 1:
            username = target[1:].casefold()
            cache = context.application.bot_data.get("moderation_members", {})
            match = next(
                (
                    member
                    for group_members in cache.values()
                    for member in group_members.values()
                    if (member.get("username") or "").casefold() == username
                ),
                None,
            )
            if not match:
                await message.reply_text(
                    "❌ I couldn't find that username in the groups I've seen. "
                    "Ask the user to send a message in a group where I'm present, then try again."
                )
                return
            target_id = int(match["id"])
            target_name = match.get("full_name") or target
        else:
            await message.reply_text(
                "Usage: /score [@username or user_id]"
            )
            return

    async with _connect() as db:
        cur = await db.execute(
            "SELECT display_name, wins, games, total_guesses "
            "FROM word_game_scores WHERE user_id=?",
            (target_id,),
        )
        row = await cur.fetchone()

    if not row:
        await message.reply_text(
            "You have no scores recorded yet. Start playing to earn some points! 🎮"
        )
        return

    target_name, wins, games, total_guesses = row
    win_rate = round((wins / games) * 100) if games else 0
    await message.reply_text(
        f"📊 WORDSEEK SCORE\n\n"
        f"👤 Player: {target_name}\n"
        f"🆔 User ID: {target_id}\n"
        f"🏆 Wins: {wins}\n"
        f"🎮 Rounds played: {games}\n"
        f"🎯 Total guesses: {total_guesses}\n"
        f"📈 Win rate: {win_rate}%"
    )


async def leaderboard_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Show the global all-time Word Game leaderboard, ranked by recorded wins."""
    message = update.effective_message
    if not message:
        return

    async with _connect() as db:
        cur = await db.execute(
            """
            SELECT display_name, wins
            FROM word_game_scores
            WHERE wins > 0
            ORDER BY wins DESC, games DESC, display_name COLLATE NOCASE ASC
            LIMIT 10
            """
        )
        rows = await cur.fetchall()

    lines = [
        "🏆 <b>GLOBAL LEADERBOARD</b> 🏆",
        "━━━━━━━━━━━━━━━━━━",
        "",
    ]

    if not rows:
        lines.extend([
            "No winners yet!",
            "🎮 Start a Word Game and be the first champion.",
        ])
    else:
        medals = ("🥇", "🥈", "🥉")
        for index, (display_name, wins) in enumerate(rows, start=1):
            safe_name = html.escape(display_name or "Unknown Player")
            badge = medals[index - 1] if index <= 3 else "🔅"
            lines.append(
                f"{badge} <b>{index}.</b> {safe_name} — "
                f"<code>{wins:,} wins</code>"
            )

        lines.extend([
            "",
            "━━━━━━━━━━━━━━━━━━",
            "💫 Keep playing to climb the ranks!",
        ])

    await message.reply_text(
        "\n".join(lines),
        parse_mode="HTML",
        disable_web_page_preview=True,
    )


async def seekauth_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Let group administrators manage users who may end a Words Game round."""
    message = update.effective_message
    chat = update.effective_chat
    actor = update.effective_user
    if not message or not chat or not actor:
        return
    if chat.type not in ("group", "supergroup"):
        await message.reply_text("Use /seekauth inside the group where WordSeek is running.")
        return
    try:
        member = await context.bot.get_chat_member(chat.id, actor.id)
        if member.status not in ("administrator", "creator", "owner"):
            await message.reply_text(
                "❌ You don't have permission to use this command. Only administrators can manage authorized users."
            )
            return
    except Exception:
        await message.reply_text("⚠️ I couldn't verify your admin permissions. Please try again.")
        return

    args = list(context.args or [])
    action = args[0].lower() if args else "help"
    if action in ("list", "show"):
        async with _connect() as db:
            cur = await db.execute(
                "SELECT user_id, display_name FROM word_game_authorized_users WHERE chat_id=? ORDER BY display_name COLLATE NOCASE",
                (chat.id,),
            )
            rows = await cur.fetchall()
        if not rows:
            await message.reply_text("🔐 No users are authorized to end WordSeek rounds in this group.")
            return
        lines = ["🔐 <b>Authorized WordSeek Users</b>", ""]
        lines.extend(f"• {display_name} — <code>{user_id}</code>" for user_id, display_name in rows)
        await message.reply_text("\n".join(lines), parse_mode="HTML")
        return

    if action in ("help",):
        await message.reply_text(
            "🔐 <b>WordSeek Authorization</b>\n\n"
            "Reply to a user and send <code>/seekauth</code> — authorize them\n"
            "<code>/seekauth USER_ID</code> — authorize by Telegram user ID\n"
            "<code>/seekauth remove USER_ID</code> — remove authorization\n"
            "<code>/seekauth list</code> — list authorized users\n\n"
            "Only group administrators can manage this list.",
            parse_mode="HTML",
        )
        return

    remove = action in ("remove", "del", "delete", "revoke")
    target_id = None
    display_name = None
    if message.reply_to_message and message.reply_to_message.from_user and (remove and len(args) == 1 or not remove and len(args) == 1):
        target = message.reply_to_message.from_user
        target_id = target.id
        display_name = target.full_name or target.first_name or str(target.id)
    else:
        raw_target = args[1] if remove and len(args) > 1 else (args[0] if not remove else "")
        if raw_target.isdigit():
            target_id = int(raw_target)
            display_name = f"User {target_id}"
        elif raw_target.startswith("@"):
            cache = context.application.bot_data.get("moderation_members", {}).get(chat.id, {})
            matches = [v for v in cache.values() if (v.get("username") or "").casefold() == raw_target[1:].casefold()]
            if len(matches) == 1:
                target_id = int(matches[0]["id"])
                display_name = matches[0].get("full_name") or matches[0].get("name") or raw_target
    if target_id is None:
        await message.reply_text(
            "Usage:\n• Reply to a user's message: /seekauth\n"
            "• Authorize by ID: /seekauth USER_ID\n"
            "• Remove by ID: /seekauth remove USER_ID\n"
            "• List: /seekauth list\n\n"
            "For @username, the user must have sent a message in this group while I was online."
        )
        return
    async with _connect() as db:
        if remove:
            cur = await db.execute(
                "DELETE FROM word_game_authorized_users WHERE chat_id=? AND user_id=?",
                (chat.id, target_id),
            )
            await db.commit()
            if cur.rowcount:
                await message.reply_text(f"✅ Authorization removed for {display_name} (<code>{target_id}</code>).", parse_mode="HTML")
            else:
                await message.reply_text("ℹ️ That user was not on this group's authorization list.")
        else:
            await db.execute(
                """INSERT INTO word_game_authorized_users(chat_id, user_id, display_name, added_by, added_at)
                   VALUES(?,?,?,?,?)
                   ON CONFLICT(chat_id, user_id) DO UPDATE SET
                     display_name=excluded.display_name, added_by=excluded.added_by, added_at=excluded.added_at""",
                (chat.id, target_id, display_name, actor.id, datetime.now(timezone.utc).isoformat()),
            )
            await db.commit()
            await message.reply_text(f"✅ {display_name} (<code>{target_id}</code>) can now end WordSeek rounds in this group.", parse_mode="HTML")


async def helpwords_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    message = update.effective_message
    if not message:
        return
    help_text = (
        "📋 WORD GAME COMMANDS\n\n"
        "/new — Start a 5-letter word game\n"
        "/new4 — Start a 4-letter word game\n"
        "/new5 — Start a 5-letter word game\n"
        "/new6 — Start a 6-letter word game\n"
        "/end — End the current game (if permitted)\n"
        "/helpwords — Show this command guide\n"
        "/daily — Play today's puzzle in private chat (6 guesses)\n"
        "/pausedaily — Leave Daily mode and return to normal games"
    )
    await message.reply_text(help_text)


async def daily_word_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat = update.effective_chat
    if not chat or chat.type != "private":
        await update.effective_message.reply_text("📅 Daily WordSeek is available only in my private chat. Open @DeepEmotionsBot and use /daily.")
        return
    now = datetime.now(ZoneInfo("Asia/Kathmandu"))
    puzzle_day = now.date() if now.hour >= 6 else (now.date() - timedelta(days=1))
    daily_date = puzzle_day.isoformat()
    chooser = random.Random("Deep-Emotion-WordSeek-" + daily_date)
    word = chooser.choice(WORDS[5])
    await _start_word_round(update, context, 5, daily=True, daily_date=daily_date, fixed_word=word)


async def pause_daily_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    message, chat, user = update.effective_message, update.effective_chat, update.effective_user
    if not message or not chat or not user:
        return
    if chat.type != "private":
        await message.reply_text("Use /pausedaily in my private chat.")
        return
    row = await _fetch_game(chat.id)
    if not row or not row["active"] or not row["daily_mode"]:
        await message.reply_text("Daily WordSeek is not active. You can start a normal game with /new.")
        return
    if row["owner_user_id"] != user.id:
        await message.reply_text("Only the player who started this Daily WordSeek can pause it.")
        return
    async with _connect() as db:
        await db.execute("UPDATE word_games SET active=0 WHERE chat_id=?", (chat.id,))
        await db.commit()
    await message.reply_text("⏸️ Daily WordSeek paused. You can now start a normal game with /new.")


async def wordgame_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Open the image welcome panel directly with /wordgame."""
    message = update.effective_message
    if not message:
        return
    global WORD_GAME_IMAGE_FILE_ID
    sent = await message.reply_photo(
        photo=WORD_GAME_IMAGE_FILE_ID or WORD_GAME_IMAGE_URL,
        caption=WELCOME_CAPTION,
        reply_markup=game_keyboard(),
    )
    if WORD_GAME_IMAGE_FILE_ID is None and sent.photo:
        WORD_GAME_IMAGE_FILE_ID = sent.photo[-1].file_id


async def _edit_callback_panel(query, text, reply_markup, parse_mode=None):
    """Edit text panels in place; Telegram photo captions have a 1024-char limit."""
    if query.message and query.message.photo:
        if len(text) <= 1024:
            return await query.edit_message_caption(
                caption=text,
                parse_mode=parse_mode,
                reply_markup=reply_markup,
            )
        # Long help panels cannot fit in a photo caption.
        await query.message.delete()
        return await query.get_bot().send_message(
            chat_id=query.message.chat_id,
            text=text,
            parse_mode=parse_mode,
            reply_markup=reply_markup,
        )
    return await query.edit_message_text(
        text=text,
        parse_mode=parse_mode,
        reply_markup=reply_markup,
    )


async def _remove_callback_panel(query):
    try:
        await query.message.delete()
    except Exception:
        # If Telegram will not delete the old panel, still show the requested view.
        pass


async def _send_game_home(context, chat_id):
    global WORD_GAME_IMAGE_FILE_ID
    sent = await context.bot.send_photo(
        chat_id=chat_id,
        photo=WORD_GAME_IMAGE_FILE_ID or WORD_GAME_IMAGE_URL,
        caption=WELCOME_CAPTION,
        reply_markup=game_keyboard(),
    )
    if WORD_GAME_IMAGE_FILE_ID is None and sent.photo:
        WORD_GAME_IMAGE_FILE_ID = sent.photo[-1].file_id


async def word_game_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    if not query or not query.message:
        return
    await query.answer()
    data = query.data or ""
    chat_id = query.message.chat_id
    user = query.from_user

    if data == "wg:home":
        if query.message.photo:
            await query.edit_message_caption(
                caption=WELCOME_CAPTION,
                reply_markup=game_keyboard(),
            )
        else:
            await _remove_callback_panel(query)
            await _send_game_home(context, chat_id)
        return
    if data == "wg:play":
        await _edit_callback_panel(
            query,
            text="""🎮 Choose your word length:

4 letters · 5 letters · 6 letters
You get up to 30 guesses.""",
            reply_markup=mode_keyboard(),
        )
        return
    if data == "wg:cancel":
        row = await _fetch_game(chat_id)
        if not row or not row["active"]:
            await context.bot.send_message(chat_id=chat_id, text="There is no active Words Game round.")
            return
        if row["owner_user_id"] != user.id:
            await context.bot.send_message(
                chat_id=chat_id,
                text="Only the player who started this round can end it.",
            )
            return
        async with _connect() as db:
            await db.execute("UPDATE word_games SET active=0 WHERE chat_id=?", (chat_id,))
            await db.commit()
        await query.edit_message_text(
            "🛑 Words Game round ended. Tap Play to start a new round.",
            reply_markup=game_keyboard(),
        )
        return
    if data == "wg:help":
        await _edit_callback_panel(
            query,
            text="""▸ HOW TO PLAY WORD GAME!

> 1. Start a game using /new, /new4, /new5, or /new6
> 2. Guess the hidden word.
> 3. After each guess, you'll get color hints:
>    🟩 Correct letter in the right spot
>    🟨 Correct letter in the wrong spot
>    🟥 Letter not in the word
> 4. First person to guess correctly wins!
> 5. Maximum 30 guesses per game.

WORD LENGTH MODES

> • /new → Start the default 5-letter game
> • /new 4, /new 5, or /new 6 → Choose a word length
> • /new4 → Start a 4-letter game
> • /new5 → Start a 5-letter game
> • /new6 → Start a 6-letter game

BASIC COMMANDS

• /new - Start a new game (default 5 letters)
• /new4 - Start a 4-letter game
• /new5 - Start a 5-letter game
• /new6 - Start a 6-letter game
• /end - End the current game (subject to game permissions)
• /helpwords - Show this help menu
• /daily - Play Daily WordSeek (private chat only)
• /pausedaily - Pause Daily mode and return to normal games

DAILY MODE (PRIVATE CHAT ONLY)

> • Start a daily puzzle using /daily.
> • Each day has one fixed word.
> • You get only 6 guesses per daily puzzle.
> • A new puzzle unlocks daily at 06:00 Kathmandu time (UTC+5:45).
> • Build a streak by solving puzzles without failing.
> • Normal and Daily modes cannot run at the same time:
>   - If a normal game is running, end it before using /daily.
>   - If Daily mode is active, use /pausedaily to return to normal games.""",
            reply_markup=help_keyboard(),
        )
        return
    if data == "wg:howto":
        await _edit_callback_panel(
            query,
            text="""▸ HOW TO PLAY WORD GAME!

> 1. Start a game using /new, /new4, /new5, or /new6
> 2. Guess the hidden word.
> 3. After each guess, you'll get color hints:
>    🟩 Correct letter in the right spot
>    🟨 Correct letter in the wrong spot
>    🟥 Letter not in the word
> 4. First person to guess correctly wins!
> 5. Maximum 30 guesses per game.

WORD LENGTH MODES

> • /new → Start the default 5-letter game
> • /new 4, /new 5, or /new 6 → Choose a word length
> • /new4 → Start a 4-letter game
> • /new5 → Start a 5-letter game
> • /new6 → Start a 6-letter game

BASIC COMMANDS

• /new - Start a new game (default 5 letters)
• /new4 - Start a 4-letter game
• /new5 - Start a 5-letter game
• /new6 - Start a 6-letter game
• /end - End the current game (subject to game permissions)
• /helpwords - Show this help menu
• /daily - Play Daily WordSeek (private chat only)
• /pausedaily - Pause Daily mode and return to normal games

DAILY MODE (PRIVATE CHAT ONLY)

> • Start a daily puzzle using /daily.
> • Each day has one fixed word.
> • You get only 6 guesses per daily puzzle.
> • A new puzzle unlocks daily at 06:00 Kathmandu time (UTC+5:45).
> • Build a streak by solving puzzles without failing.
> • Normal and Daily modes cannot run at the same time:
>   - If a normal game is running, end it before using /daily.
>   - If Daily mode is active, use /pausedaily to return to normal games.""",
            reply_markup=help_keyboard(),
        )
        return
    if data == "wg:groupsettings":
        await _edit_callback_panel(
            query,
            text="""<b>▸ Group Settings (Admin Only)</b>

<b>Authorized Users</b>

<code>/seekauth</code> — Manage users who can end games without a vote.

<b>Usage:</b>
• <code>/seekauth @username</code> — Authorize a user
• <code>/seekauth remove @username</code> — Remove authorization
• <code>/seekauth list</code> — List all authorized users

You can also use a user ID or reply to a message instead of @username.

<b>Game Topic (Forum Groups)</b>

<code>/setgametopic</code> — Restrict games to one or more topics

Run this command <i>inside the topic</i> where you want games to be played.
After setting, the bot will only run games in that topic.

<code>/unsetgametopic</code> — Remove topic restriction

<b>Usage:</b> <code>/unsetgametopic</code>

After unsetting, the bot can run games in any topic in the group again. If there are other topics set, the bot will only run in those topics.

<code>/allowonlylen</code> — Restrict allowed word lengths in this topic

<b>Usage:</b> <code>/allowonlylen 4</code> or <code>/allowonlylen 5 6</code>

Run this inside a game topic.

You can allow one or more of: 4, 5, 6.
The first number you specify becomes the default length for /new in that topic.

If not configured, all lengths (4, 5, 6) are allowed by default.

<code>/recreatetopic</code> — Auto-recreate topic when it expires

<b>Usage:</b> <code>/recreatetopic on</code> or <code>/recreatetopic off</code>

Run this command inside a game topic.

When enabled, if the topic automatically expires (Telegram forum feature), the bot will recreate the same topic so games can continue.""",
            parse_mode="HTML",
            reply_markup=help_keyboard(),
        )
        return
    if data == "wg:commands":
        await _edit_callback_panel(
            query,
            text="""📋 WORD GAME COMMANDS

/new — Start the default 5-letter game
/new4 — Start a 4-letter game
/new5 — Start a 5-letter game
/new6 — Start a 6-letter game
/end — End the current game when permitted
/helpwords — Open Word Game help
/daily — Start Daily WordSeek in a private chat
/pausedaily — Leave Daily mode and return to normal games""",
            reply_markup=help_keyboard(),
        )
        return
    if data == "wg:leaderboard":
        await _edit_callback_panel(
            query,
            text="""<b>▸ Leaderboard &amp; Scores</b>

<b>Quick Examples:</b>

<code>/leaderboard</code> — Group, today (default 5-letter)
<code>/leaderboard 4</code> — 4-letter leaderboard (group, today)
<code>/leaderboard global week 6</code> — Global rankings this week (6-letter mode)
<code>/leaderboard month</code> — This group's monthly leaderboard

<code>/score</code> — Your score (group, today, 5-letter by default)
<code>/score 6</code> — Your 6-letter stats
<code>/score @username global all 4</code> — Full 4-letter global history for a user
<code>/score 123456789 month</code> — Monthly stats for a user

<b>Leaderboard Command</b>

<b>Syntax:</b> <code>/leaderboard [scope] [period] [length]</code>

All parameters are optional and can be used in any order.

<b>Scope:</b>
• group (default) — Current group only
• global — All groups combined

<b>Period:</b>
• today (default)
• week
• month
• year
• all

<b>Length:</b>
• 4 — 4-letter mode
• 5 — 5-letter mode (default)
• 6 — 6-letter mode

<b>Score Command</b>

<b>Syntax:</b> <code>/score [target] [scope] [period] [length]</code>

All parameters are optional and can be used in any order.

<b>Target (optional):</b>
• Leave empty for your own score
• @username — Look up by username
• user_id — Look up by Telegram user ID

<b>Scope, period &amp; length:</b>
Same as /leaderboard""",
            parse_mode="HTML",
            reply_markup=help_keyboard(),
        )
        return
    if data == "wg:stats":
        async with _connect() as db:
            cur = await db.execute("SELECT wins, games, total_guesses FROM word_game_scores WHERE user_id=?", (user.id,))
            row = await cur.fetchone()
        if row:
            wins, games, total_guesses = row
            rate = round((wins / games) * 100) if games else 0
            text = f"""📊 YOUR WORDS GAME STATS

🏆 Wins: {wins}
🎮 Rounds played: {games}
🎯 Total guesses: {total_guesses}
📈 Win rate: {rate}%"""
        else:
            text = """📊 YOUR WORDS GAME STATS

You have not played yet. Tap Play to start!"""
        await _edit_callback_panel(
            query,
            text=text,
            reply_markup=footer_keyboard(),
        )
        return
    if data.startswith("wg:mode:"):
        try:
            length = int(data.rsplit(":", 1)[1])
        except ValueError:
            return
        if length not in WORDS:
            return
        topic_message = query.message
        if topic_message and topic_message.chat.type in ("group", "supergroup"):
            if not await _topic_is_allowed(topic_message.chat.id, getattr(topic_message, "message_thread_id", None)):
                await query.answer("WordSeek is restricted to configured forum topic(s).", show_alert=True)
                return
        topic_chat = topic_message.chat if topic_message else None
        if topic_chat and getattr(topic_chat, "is_forum", False):
            settings = await _topic_length_settings(
                topic_chat.id,
                getattr(topic_message, "message_thread_id", None),
            )
            if settings and length not in settings["allowed"]:
                await query.answer(
                    f"Only {', '.join(map(str, sorted(settings['allowed'])))}-letter words are allowed in this topic.",
                    show_alert=True,
                )
                return
        old = await _fetch_game(chat_id)
        if old and old["active"]:
            await context.bot.send_message(
                chat_id=chat_id,
                text="⏳ A Words Game round is already active in this chat. Finish it first, or use 🛑 End Round on the game panel.",
                reply_markup=footer_keyboard(),
            )
            return
        word = random.choice(WORDS[length])
        await query.edit_message_text(
            f"""🎮 DEEP EMOTIONS · WORDS GAME
{length}-letter mode · 0/{MAX_GUESSES}

""",
        )
        panel_id = query.message.message_id
        async with _connect() as db:
            await db.execute(
                """INSERT INTO word_games(chat_id, owner_user_id, word, word_length, guesses_json, active, panel_message_id, started_at, daily_mode, daily_date, thread_id)
                   VALUES(?,?,?,?, '[]', 1, ?, ?, 0, NULL, ?)
                   ON CONFLICT(chat_id) DO UPDATE SET owner_user_id=excluded.owner_user_id, word=excluded.word, word_length=excluded.word_length, guesses_json='[]', active=1, panel_message_id=excluded.panel_message_id, started_at=excluded.started_at, daily_mode=0, daily_date=NULL, thread_id=excluded.thread_id""",
                (chat_id, user.id, word, length, panel_id, datetime.now(timezone.utc).isoformat(), getattr(query.message, "message_thread_id", None)),
            )
            await db.commit()
        return

async def word_guess_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    message = update.effective_message
    chat = update.effective_chat
    user = update.effective_user
    if not message or not chat or not user or not message.text or user.is_bot:
        return

    # Remove the previous invalid-word notice when a new text message arrives.
    previous_notice_id = context.chat_data.pop("word_game_invalid_notice_id", None)
    if previous_notice_id:
        try:
            await context.bot.delete_message(
                chat_id=chat.id,
                message_id=previous_notice_id,
            )
        except Exception:
            pass  # The notice may already have been deleted.

    guess = message.text.strip().upper()
    if not guess.isalpha() or len(guess) not in (4, 5, 6):
        return
    row = await _fetch_game(chat.id)
    if not row or not row["active"]:
        return
    if chat.type in ("group", "supergroup") and row["thread_id"] != getattr(message, "message_thread_id", None):
        return
    if chat.type == "private" and row["owner_user_id"] != user.id:
        return
    if len(guess) != row["word_length"]:
        await context.bot.send_message(
            chat_id=chat.id,
            text=(
                f"🔤 This round needs a {row['word_length']}-letter word. "
                f"Your guess has {len(guess)} letters. Try again!"
            ),
        )
        try:
            await message.delete()
        except Exception:
            pass  # Deletion can fail if the bot lacks permission or the message is too old.
        raise ApplicationHandlerStop
    # Accept only meaningful words present in this game's dictionary.
    # Invalid words must not consume a turn or appear in the game history.
    if guess not in WORDS[row["word_length"]]:
        notice = await context.bot.send_message(
            chat_id=chat.id,
            text=f"<code>{guess}</code> is not a valid {row['word_length']}-letter word. 💗",
            parse_mode="HTML",
        )
        context.chat_data["word_game_invalid_notice_id"] = notice.message_id
        try:
            await message.delete()
        except Exception:
            pass  # Deletion requires bot permission in groups.
        raise ApplicationHandlerStop

    guesses = json.loads(row["guesses_json"])
    guess_limit = 6 if row["daily_mode"] else MAX_GUESSES
    if len(guesses) >= guess_limit:
        return
    guesses.append({"word": guess, "feedback": _feedback({"word": guess}, row["word"]), "user_id": user.id, "name": user.full_name or user.first_name or "Player"})
    correct = guess == row["word"]
    ended = correct or len(guesses) >= guess_limit
    async with _connect() as db:
        await db.execute(
            "UPDATE word_games SET guesses_json=?, active=? WHERE chat_id=?",
            (json.dumps(guesses), 0 if ended else 1, chat.id),
        )
        await db.execute(
            """INSERT INTO word_game_scores(user_id, display_name, wins, games, total_guesses)
               VALUES(?,?,0,0,1)
               ON CONFLICT(user_id) DO UPDATE SET
                 display_name=excluded.display_name,
                 total_guesses=word_game_scores.total_guesses+1""",
            (user.id, user.full_name or user.first_name or "Player"),
        )
        if ended:
            participants = {}
            for item in guesses:
                participants[item["user_id"]] = item["name"]
            for participant_id, participant_name in participants.items():
                won = 1 if correct and participant_id == user.id else 0
                await db.execute(
                    """INSERT INTO word_game_scores(user_id, display_name, wins, games, total_guesses)
                       VALUES(?,?,?,1,0)
                       ON CONFLICT(user_id) DO UPDATE SET
                         display_name=excluded.display_name,
                         wins=word_game_scores.wins+excluded.wins,
                         games=word_game_scores.games+1""",
                    (participant_id, participant_name, won),
                )
        await db.commit()
    row = await _fetch_game(chat.id)
    if correct:
        await _show_game(context, chat.id, row, winner=user.full_name or user.first_name or "Player")
        await context.bot.send_message(
            chat_id=chat.id,
            text=f"🏆 {user.first_name or 'Player'} won the round! The word was {row['word']}.",
        )
    elif ended:
        await _show_game(context, chat.id, row, ended=True)
    else:
        await _show_game(context, chat.id, row)
    # Keep the single game panel; remove the player's standalone guess message.
    try:
        await message.delete()
    except Exception:
        pass  # Telegram may reject deletion when the bot lacks permission.
    raise ApplicationHandlerStop
