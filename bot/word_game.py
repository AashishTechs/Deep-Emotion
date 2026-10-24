# ==========================================================
# Deep Emotions — Words Game
# Wordle-style game for private chats and groups.
# ==========================================================

import json
import random
from datetime import datetime, timezone

import aiosqlite
from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.ext import ContextTypes, ApplicationHandlerStop

from bot.database import DB_PATH

UPDATES_URL = "https://t.me/BotUpdates0fficial"
DISCUSSION_URL = "https://t.me/+cGoEVo7d8YtjOTI9"
MAX_GUESSES = 30

WORDS = {
    4: ["ABLE", "ACID", "AGED", "ALSO", "AREA", "ARMY", "AWAY", "BABY", "BACK", "BALL", "BAND", "BANK", "BASE", "BATH", "BEAR", "BEAT", "BEEN", "BELL", "BELT", "BEST", "BILL", "BIRD", "BLOW", "BLUE", "BOAT", "BODY", "BOLD", "BONE", "BOOK", "BOOM", "BORN", "BOSS", "BOTH", "BOWL", "BULK", "BURN", "BUSY", "CALL", "CALM", "CAME", "CAMP", "CARD", "CARE", "CASE", "CASH", "CITY", "CLUB", "COAL", "COAT", "CODE", "COLD", "COME", "COOK", "COOL", "COPY", "COST", "CREW", "CROP", "DARK", "DATA", "DATE", "DAWN", "DAYS", "DEAD", "DEAL", "DEAR", "DEEP", "DESK", "DIAL", "DICE", "DIET", "DIRT", "DISH", "DOOR", "DOWN", "DRAW", "DREW", "DROP", "DRUG", "DUAL", "DUST", "DUTY", "EACH", "EARN", "EASE", "EAST", "EASY", "EDGE", "ELSE", "EVEN", "EVER", "FACE", "FACT", "FADE", "FAIL", "FAIR", "FALL", "FAME", "FARM", "FAST", "FATE", "FEAR", "FEED", "FEEL", "FILE", "FILL", "FILM", "FIND", "FINE", "FIRE", "FIRM", "FISH", "FIVE", "FLAG", "FLAT", "FLOW", "FOOD", "FOOT", "FORD", "FORM", "FORT", "FOUR", "FREE", "FROM", "FUEL", "FULL", "FUND", "GAIN", "GAME", "GATE", "GAVE", "GEAR", "GIFT", "GIRL", "GIVE", "GLAD", "GOAL", "GOES", "GOLD", "GOLF", "GONE", "GOOD", "GRAY", "GREW", "GROW", "GULF", "HAIR", "HALF", "HALL", "HAND", "HANG", "HARD", "HARM", "HATE", "HAVE", "HEAD", "HEAR", "HEAT", "HELD", "HELP", "HERE", "HERO", "HIGH", "HILL", "HOLD", "HOME", "HOPE", "HOST", "HOUR", "HUGE", "HUNG", "HUNT", "HURT", "IDEA", "INCH", "INTO", "IRON", "ITEM", "JACK", "JANE", "JOBS", "JOIN", "JUMP", "JUST", "KEEN", "KEEP", "KEPT", "KICK", "KIND", "KING", "KNEW", "KNOW", "LACK", "LADY", "LAKE", "LAND", "LANE", "LAST", "LATE", "LEAD", "LEFT", "LESS", "LIFE", "LIFT", "LIKE", "LINE", "LINK", "LIST", "LIVE", "LOAD", "LOAN", "LOCK", "LONG", "LOOK", "LORD", "LOSE", "LOSS", "LOST", "LOVE", "LUCK", "MADE", "MAIL", "MAIN", "MAKE", "MALE", "MANY", "MARK", "MASS", "MATE", "MEAL", "MEAN", "MEAT", "MEET", "MENU", "MERE", "MILE", "MILK", "MIND", "MINE", "MISS", "MODE", "MOOD", "MOON", "MORE", "MOST", "MOVE", "MUCH", "MUST", "NAME", "NEAR", "NEAT", "NECK", "NEED", "NEWS", "NEXT", "NICE", "NINE", "NODE", "NONE", "NOSE", "NOTE", "ONCE", "ONLY", "ONTO", "OPEN", "ORAL", "OVER", "PACE", "PACK", "PAGE", "PAID", "PAIN", "PAIR", "PARK", "PART", "PASS", "PAST", "PATH", "PEAK", "PICK", "PINK", "PIPE", "PLAN", "PLAY", "PLOT", "PLUS", "POEM", "POET", "POLL", "POOL", "POOR", "PORT", "POST", "PULL", "PURE", "PUSH", "QUIT", "RACE", "RAIL", "RAIN", "RANK", "RATE", "READ", "REAL", "REAR", "RELY", "RENT", "REST", "RICE", "RICH", "RIDE", "RING", "RISE", "RISK", "ROAD", "ROCK", "ROLE", "ROLL", "ROOF", "ROOM", "ROOT", "ROSE", "RULE", "RUSH", "SAFE", "SAGE", "SAID", "SAIL", "SALE", "SALT", "SAME", "SAND", "SAVE", "SEAT", "SEED", "SEEK", "SEEM", "SEEN", "SELF", "SELL", "SEND", "SENT", "SHIP", "SHOP", "SHOT", "SHOW", "SHUT", "SICK", "SIDE", "SIGN", "SILK", "SING", "SITE", "SIZE", "SKIN", "SLOW", "SNOW", "SOFT", "SOIL", "SOLD", "SOLE", "SOME", "SONG", "SOON", "SORT", "SOUL", "STAR", "STAY", "STEP", "STOP", "SUCH", "SUIT", "SURE", "TAKE", "TALE", "TALK", "TALL", "TANK", "TAPE", "TASK", "TEAM", "TECH", "TELL", "TEND", "TERM", "TEST", "TEXT", "THAN", "THAT", "THEM", "THEN", "THEY", "THIN", "THIS", "THUS", "TILL", "TIME", "TINY", "TOLD", "TONE", "TOOK", "TOOL", "TOUR", "TOWN", "TREE", "TRIP", "TRUE", "TUNE", "TURN", "TYPE", "UNIT", "UPON", "USED", "USER", "VARY", "VAST", "VERY", "VIEW", "VOTE", "WAGE", "WAIT", "WAKE", "WALK", "WALL", "WANT", "WARD", "WARM", "WARN", "WASH", "WAVE", "WAYS", "WEAK", "WEAR", "WEEK", "WELL", "WENT", "WERE", "WEST", "WHAT", "WHEN", "WIDE", "WIFE", "WILD", "WILL", "WIND", "WINE", "WING", "WIRE", "WISE", "WISH", "WITH", "WOOD", "WORD", "WORE", "WORK", "YARD", "YEAH", "YEAR", "YOUR", "ZERO", "ZONE"],
    5: ["ABOUT", "ABOVE", "ABUSE", "ACTOR", "ACUTE", "ADMIT", "ADOPT", "ADULT", "AFTER", "AGAIN", "AGENT", "AGREE", "AHEAD", "ALARM", "ALBUM", "ALERT", "ALIEN", "ALIGN", "ALIKE", "ALIVE", "ALLOW", "ALONE", "ALONG", "ALTER", "ANGEL", "ANGER", "ANGLE", "ANGRY", "APART", "APPLE", "APPLY", "ARENA", "ARGUE", "ARISE", "ARRAY", "ASIDE", "ASSET", "AUDIO", "AUDIT", "AVOID", "AWARD", "AWARE", "BADLY", "BAKER", "BASES", "BASIC", "BASIS", "BEACH", "BEGAN", "BEGIN", "BEING", "BELOW", "BENCH", "BILLY", "BIRTH", "BLACK", "BLAME", "BLANK", "BLAST", "BLIND", "BLOCK", "BLOOD", "BOARD", "BOOST", "BOOTH", "BOUND", "BRAIN", "BRAND", "BREAD", "BREAK", "BREED", "BRIEF", "BRING", "BROAD", "BROKE", "BROWN", "BUILD", "BUILT", "BUYER", "CABIN", "CABLE", "CALIF", "CARRY", "CATCH", "CAUSE", "CHAIN", "CHAIR", "CHAOS", "CHARM", "CHART", "CHASE", "CHEAP", "CHECK", "CHEST", "CHIEF", "CHILD", "CHINA", "CHOSE", "CIVIL", "CLAIM", "CLASS", "CLEAN", "CLEAR", "CLICK", "CLOCK", "CLOSE", "COACH", "COAST", "COULD", "COUNT", "COURT", "COVER", "CRAFT", "CRASH", "CREAM", "CRIME", "CROSS", "CROWD", "CROWN", "CURVE", "CYCLE", "DAILY", "DANCE", "DATED", "DEALT", "DEATH", "DEBUT", "DELAY", "DEPTH", "DOING", "DOUBT", "DOZEN", "DRAFT", "DRAMA", "DRAWN", "DREAM", "DRESS", "DRINK", "DRIVE", "EARLY", "EARTH", "EIGHT", "ELITE", "EMPTY", "ENEMY", "ENJOY", "ENTER", "ENTRY", "EQUAL", "ERROR", "EVENT", "EVERY", "EXACT", "EXIST", "EXTRA", "FAITH", "FALSE", "FAULT", "FIBER", "FIELD", "FIFTH", "FIFTY", "FIGHT", "FINAL", "FIRST", "FIXED", "FLASH", "FLEET", "FLOOR", "FOCUS", "FORCE", "FORTH", "FORTY", "FORUM", "FOUND", "FRAME", "FRANK", "FRAUD", "FRESH", "FRONT", "FRUIT", "FULLY", "FUNNY", "GIANT", "GIVEN", "GLASS", "GLOBE", "GOING", "GRACE", "GRADE", "GRAND", "GRANT", "GRASS", "GREAT", "GREEN", "GROSS", "GROUP", "GROWN", "GUARD", "GUESS", "GUEST", "GUIDE", "HAPPY", "HEART", "HEAVY", "HENCE", "HONEY", "HORSE", "HOTEL", "HOUSE", "HUMAN", "IDEAL", "IMAGE", "INDEX", "INNER", "INPUT", "ISSUE", "JAPAN", "JOINT", "JUDGE", "KNOWN", "LABEL", "LARGE", "LASER", "LATER", "LAUGH", "LAYER", "LEARN", "LEASE", "LEAST", "LEAVE", "LEGAL", "LEVEL", "LIGHT", "LIMIT", "LOCAL", "LOGIC", "LOOSE", "LOWER", "LUCKY", "LUNCH", "MAJOR", "MAKER", "MARCH", "MATCH", "MAYBE", "MAYOR", "MEANT", "MEDIA", "METAL", "MIGHT", "MINOR", "MINUS", "MIXED", "MODEL", "MONEY", "MONTH", "MORAL", "MOTOR", "MOUNT", "MOUSE", "MOUTH", "MOVED", "MOVIE", "MUSIC", "NEEDS", "NEVER", "NEWLY", "NIGHT", "NOISE", "NORTH", "NOTED", "NOVEL", "NURSE", "OCCUR", "OCEAN", "OFFER", "OFTEN", "ORDER", "OTHER", "OUGHT", "PAINT", "PANEL", "PAPER", "PARTY", "PEACE", "PHASE", "PHONE", "PHOTO", "PIANO", "PIECE", "PILOT", "PITCH", "PLACE", "PLAIN", "PLANE", "PLANT", "PLATE", "POINT", "POUND", "POWER", "PRESS", "PRICE", "PRIDE", "PRIME", "PRINT", "PRIOR", "PRIZE", "PROOF", "PROUD", "PROVE", "QUEEN", "QUICK", "QUIET", "QUITE", "RADIO", "RAISE", "RANGE", "RAPID", "RATIO", "REACH", "READY", "REFER", "RIGHT", "RIVAL", "RIVER", "ROBOT", "ROGER", "ROUGH", "ROUND", "ROUTE", "ROYAL", "RURAL", "SCALE", "SCENE", "SCOPE", "SCORE", "SENSE", "SERVE", "SEVEN", "SHALL", "SHAPE", "SHARE", "SHARP", "SHEET", "SHELF", "SHELL", "SHIFT", "SHINE", "SHIRT", "SHOCK", "SHOOT", "SHORT", "SHOWN", "SIGHT", "SINCE", "SIXTH", "SKILL", "SLEEP", "SLICE", "SLIDE", "SMALL", "SMART", "SMILE", "SMITH", "SMOKE", "SOLID", "SOLVE", "SORRY", "SOUND", "SOUTH", "SPACE", "SPARE", "SPEAK", "SPEED", "SPEND", "SPENT", "SPLIT", "SPOKE", "SPORT", "STAFF", "STAGE", "STAKE", "STAND", "START", "STATE", "STEAM", "STEEL", "STICK", "STILL", "STOCK", "STONE", "STOOD", "STORE", "STORM", "STORY", "STRIP", "STUCK", "STUDY", "STUFF", "STYLE", "SUGAR", "SUITE", "SUPER", "SWEET", "TABLE", "TAKEN", "TASTE", "TAXES", "TEACH", "TEAMS", "TEETH", "TERRY", "THANK", "THEFT", "THEIR", "THEME", "THERE", "THESE", "THICK", "THING", "THINK", "THIRD", "THOSE", "THREE", "THREW", "THROW", "TIGHT", "TIMES", "TIRED", "TITLE", "TODAY", "TOPIC", "TOTAL", "TOUCH", "TOUGH", "TOWER", "TRACK", "TRADE", "TRAIN", "TREAT", "TREND", "TRIAL", "TRIED", "TRIES", "TRUCK", "TRULY", "TRUST", "TRUTH", "TWICE", "UNDER", "UNDUE", "UNION", "UNITY", "UNTIL", "UPPER", "UPSET", "URBAN", "USAGE", "USUAL", "VALID", "VALUE", "VIDEO", "VIRUS", "VISIT", "VITAL", "VOICE", "WASTE", "WATCH", "WATER", "WHEEL", "WHERE", "WHICH", "WHILE", "WHITE", "WHOLE", "WHOSE", "WOMAN", "WOMEN", "WORLD", "WORRY", "WORSE", "WORST", "WORTH", "WOULD", "WRITE", "WRONG", "WROTE", "YOUNG", "YOUTH"],
    6: ["ACTION", "ACTIVE", "ACTUAL", "ADVICE", "ADVISE", "AFFECT", "AFFORD", "AFRAID", "AGENCY", "AGENDA", "ALMOST", "ALWAYS", "AMOUNT", "ANIMAL", "ANNUAL", "ANSWER", "ANYONE", "ANYWAY", "APPEAL", "APPEAR", "AROUND", "ARRIVE", "ARTIST", "ASPECT", "ASSIGN", "ASSIST", "ASSUME", "ATTACK", "ATTEND", "AUTHOR", "AUTUMN", "AVENUE", "BACKED", "BARELY", "BATTLE", "BEAUTY", "BECAME", "BECOME", "BEFORE", "BEHALF", "BEHIND", "BELIEF", "BELONG", "BERLIN", "BETTER", "BORDER", "BOTTLE", "BOTTOM", "BOUGHT", "BRANCH", "BREATH", "BRIDGE", "BRIGHT", "BROKEN", "BUDGET", "BURIED", "BUTTON", "CAMERA", "CANCER", "CANNOT", "CAREER", "CASTLE", "CAUGHT", "CAUSED", "CENTER", "CENTRE", "CHANCE", "CHANGE", "CHARGE", "CHOICE", "CHOOSE", "CHOSEN", "CHURCH", "CIRCLE", "CLIENT", "CLOSED", "CLOSER", "COFFEE", "COLUMN", "COMBAT", "COMING", "COMMON", "COMPET", "COMPLY", "COPIED", "CORNER", "COSTLY", "COUNTY", "COUPLE", "COURSE", "CREATE", "CREDIT", "CRISIS", "CUSTOM", "DAMAGE", "DANGER", "DEBATE", "DECADE", "DECIDE", "DEEPER", "DEFEAT", "DEFEND", "DEFINE", "DEGREE", "DEMAND", "DEPEND", "DEPUTY", "DESERT", "DESIGN", "DESIRE", "DETAIL", "DEVICE", "DIFFER", "DINNER", "DIRECT", "DOCTOR", "DOLLAR", "DOMAIN", "DOUBLE", "DRIVEN", "DRIVER", "DURING", "EASILY", "EATING", "EDITOR", "EFFECT", "EFFORT", "EIGHTH", "EITHER", "ELEVEN", "EMERGE", "EMPIRE", "EMPLOY", "ENABLE", "ENDING", "ENERGY", "ENGAGE", "ENGINE", "ENOUGH", "ENSURE", "ENTIRE", "EQUITY", "ESCAPE", "ESTATE", "ETHNIC", "EXCEPT", "EXCITE", "EXCUSE", "EXPAND", "EXPECT", "EXPERT", "EXPORT", "EXTEND", "EXTENT", "FACTOR", "FAILED", "FAIRLY", "FAMILY", "FAMOUS", "FATHER", "FELLOW", "FEMALE", "FIGURE", "FILING", "FINGER", "FINISH", "FLIGHT", "FOLLOW", "FORCED", "FOREST", "FORMAL", "FORMAT", "FORMER", "FOSTER", "FRANCE", "FRIEND", "FUTURE", "GARDEN", "GATHER", "GENDER", "GENTLE", "GLOBAL", "GROUND", "GROWTH", "HANDLE", "HAPPEN", "HEALTH", "HEAVEN", "HEIGHT", "HELPED", "HONEST", "HORSES", "HOSPITAL", "HOTELS", "HUMOUR", "HUNDRED", "IMPACT", "IMPORT", "INCOME", "INDEED", "INJURY", "INSIDE", "INSIST", "INTEND", "INTENT", "INVEST", "ISLAND", "ITSELF", "JERSEY", "JIMMY", "JOSEPH", "JUNIOR", "KILLED", "LABOUR", "LATEST", "LATTER", "LAUNCH", "LAWYER", "LEADER", "LEAGUE", "LENGTH", "LESSON", "LETTER", "LIKELY", "LINKED", "LISTEN", "LITTLE", "LIVING", "LOSING", "LONDON", "MAINLY", "MAKING", "MANAGE", "MANNER", "MARKET", "MASTER", "MATTER", "MEDIUM", "MEMBER", "MEMORY", "MENTAL", "METHOD", "MIDDLE", "MILLION", "MINUTE", "MIRROR", "MOBILE", "MODERN", "MODEST", "MOMENT", "MOSTLY", "MOTHER", "MOTION", "MOVING", "MURDER", "MUSEUM", "MUTUAL", "MYSELF", "NATURE", "NEARLY", "NIGHTS", "NORMAL", "NOTICE", "NUMBER", "OBJECT", "OBTAIN", "OFFICE", "ONLINE", "OPTION", "ORANGE", "ORIGIN", "OUTPUT", "OXYGEN", "PALACE", "PARENT", "PARTLY", "PEOPLE", "PERIOD", "PERSON", "PLANET", "PLAYER", "PLEASE", "PLENTY", "POCKET", "POLICY", "POLICE", "POLICY", "POPULAR", "POTATO", "PRETTY", "PRINCE", "PRISON", "PROBLEM", "PRODUCE", "PROFIT", "PROPER", "PROPOSE", "PUBLIC", "PURPOSE", "PURSUE", "RANDOM", "READER", "REALLY", "REASON", "RECALL", "RECENT", "RECORD", "REDUCE", "REFORM", "REGARD", "REGION", "RELATE", "RELIEF", "REMAIN", "REMIND", "REMOVE", "REPLACE", "REPORT", "RESULT", "RETURN", "REVEAL", "REVIEW", "RIGHTS", "RISING", "ROBERT", "ROCKET", "RUNNER", "SAMPLE", "SAVING", "SCHOOL", "SCREEN", "SEARCH", "SEASON", "SECOND", "SECRET", "SECTOR", "SECURE", "SELECT", "SELLER", "SENIOR", "SERIES", "SERVES", "SETTLE", "SEVERE", "SHOULD", "SIGNAL", "SIMPLE", "SIMPLY", "SINGLE", "SISTER", "SITUAL", "SOCIAL", "SOCCER", "SOURCE", "SPEECH", "SPIRIT", "SPREAD", "SPRING", "SQUARE", "STABLE", "STATUS", "STRAIN", "STRANGE", "STREET", "STRIKE", "STRING", "STRONG", "STRUGGLE", "STUDENT", "SUBJECT", "SUCCESS", "SUDDEN", "SUFFER", "SUMMER", "SUPPLY", "SUPPORT", "SURELY", "SURVEY", "SYSTEM", "TAKING", "TARGET", "TAUGHT", "THEORY", "THIRTY", "THOUGHT", "THROUGH", "TICKET", "TIMING", "TISSUE", "TOWARD", "TRAVEL", "TREATY", "TRYING", "TURNED", "TWELVE", "UNABLE", "UNIQUE", "UNITED", "UNLESS", "UNLIKE", "UPDATE", "USEFUL", "VALLEY", "VARIED", "VICTIM", "VIEWER", "VISION", "VISUAL", "VOLUME", "WALKED", "WEALTH", "WEAPON", "WEEKLY", "WEIGHT", "WINDOW", "WINNER", "WINTER", "WITHIN", "WONDER", "WORKER", "WRITER", "YELLOW"]
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
                started_at TEXT NOT NULL
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

def _button(label, callback_data=None, url=None):
    return InlineKeyboardButton(label, callback_data=callback_data, url=url)

def game_keyboard():
    return InlineKeyboardMarkup([
        [_button("▶️ Play", callback_data="wg:play"), _button("🏆 Leaderboard", callback_data="wg:leaderboard")],
        [_button("📊 My Stats", callback_data="wg:stats")],
        [_button("🔔 Updates", url=UPDATES_URL), _button("❔ Help", callback_data="wg:help"), _button("💬 Discussion", url=DISCUSSION_URL)],
        [_button("🔙 Back to Games", callback_data="help_main")],
    ])

def mode_keyboard():
    return InlineKeyboardMarkup([
        [_button("4-Letter", callback_data="wg:mode:4"), _button("5-Letter", callback_data="wg:mode:5"), _button("6-Letter", callback_data="wg:mode:6")],
        [_button("🔙 Words Game", callback_data="wg:home")],
    ])

def footer_keyboard():
    return InlineKeyboardMarkup([
        [_button("🔔 Updates", url=UPDATES_URL), _button("❔ Help", callback_data="wg:help"), _button("💬 Discussion", url=DISCUSSION_URL)],
        [_button("🏆 Leaderboard", callback_data="wg:leaderboard"), _button("📊 My Stats", callback_data="wg:stats")],
        [_button("🔙 Words Game", callback_data="wg:home")],
    ])

def _game_text(length, guesses, word=None, ended=False, winner=None):
    lines = [f"🎮 DEEP EMOTIONS · WORDS GAME", f"{length}-letter mode · {len(guesses)}/{MAX_GUESSES} guesses", ""]
    for guess in guesses:
        feedback = _feedback(guess, word) if word else guess.get("feedback", "")
        lines.append(f"{feedback}  {guess['word']}")
    if not guesses:
        lines.extend(["No guesses yet. Send a word in this chat to begin!", ""])
    if winner:
        lines.extend(["", f"🏆 {winner} guessed the word correctly!", f"Answer: {word}"])
    elif ended:
        lines.extend(["", f"Round over! The word was: {word}"])
    else:
        lines.extend(["", "🟩 Correct place   🟨 Wrong place   🟥 Not in word", "Send your guess as a message."])
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
    text = _game_text(row["word_length"], guesses, row["word"], ended=ended, winner=winner)
    try:
        await context.bot.edit_message_text(
            chat_id=chat_id,
            message_id=row["panel_message_id"],
            text=text,
            reply_markup=footer_keyboard(),
        )
    except Exception:
        pass

async def wordgame_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Open the Words Game panel directly with /wordgame in private or group chats."""
    message = update.effective_message
    if not message:
        return
    await message.reply_text(
        "🎮 DEEP EMOTIONS · WORDS GAME\n\n"
        "Guess the hidden word in 4, 5, or 6 letters.\n\n"
        "🟩 Correct position · 🟨 Wrong position · 🟥 Not in word\n\n"
        "Choose an option:",
        reply_markup=game_keyboard(),
    )


async def word_game_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    if not query or not query.message:
        return
    await query.answer()
    data = query.data or ""
    chat_id = query.message.chat_id
    user = query.from_user

    if data == "wg:home":
        await query.edit_message_text(
            """🎮 DEEP EMOTIONS · WORDS GAME

Guess the hidden word in 4, 5, or 6 letters.

🟩 Correct position · 🟨 Wrong position · 🟥 Not in word

Choose an option:""",
            reply_markup=game_keyboard(),
        )
        return
    if data == "wg:play":
        await query.edit_message_text(
            """🎮 Choose your word length:

4 letters · 5 letters · 6 letters
You get up to 30 guesses.""",
            reply_markup=mode_keyboard(),
        )
        return
    if data == "wg:help":
        await query.edit_message_text(
            """❔ WORDS GAME HELP

1. Choose 4-, 5-, or 6-letter mode.
2. Send a word of the selected length in this chat.
3. 🟩 letter is correct and in the right place.
4. 🟨 letter exists but is in the wrong place.
5. 🟥 letter is not in the word.
6. The round ends when someone guesses correctly or after 30 guesses.

In groups, everyone can guess and the first correct player wins.""",
            reply_markup=footer_keyboard(),
        )
        return
    if data == "wg:leaderboard":
        async with _connect() as db:
            cur = await db.execute("SELECT display_name, wins, games FROM word_game_scores ORDER BY wins DESC, games ASC LIMIT 10")
            rows = await cur.fetchall()
        lines = ["🏆 WORDS GAME LEADERBOARD", ""]
        if not rows:
            lines.append("No scores yet. Be the first to play!")
        else:
            for idx, (name, wins, games) in enumerate(rows, 1):
                lines.append(f"{idx}. {name} — {wins} wins / {games} rounds")
        await query.edit_message_text("\n".join(lines), reply_markup=footer_keyboard())
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
        await query.edit_message_text(text, reply_markup=footer_keyboard())
        return
    if data.startswith("wg:mode:"):
        try:
            length = int(data.rsplit(":", 1)[1])
        except ValueError:
            return
        if length not in WORDS:
            return
        old = await _fetch_game(chat_id)
        if old and old["active"]:
            await context.bot.send_message(
                chat_id=chat_id,
                text="⏳ A Words Game round is already active in this chat. Finish it first.",
            )
            return
        word = random.choice(WORDS[length])
        await query.edit_message_text(
            f"""🎮 DEEP EMOTIONS · WORDS GAME

{length}-letter mode · 0/{MAX_GUESSES}

No guesses yet. Send a {length}-letter word in this chat to begin!

🟩 Correct place   🟨 Wrong place   🟥 Not in the word""",
            reply_markup=footer_keyboard(),
        )
        panel_id = query.message.message_id
        async with _connect() as db:
            await db.execute(
                """INSERT INTO word_games(chat_id, owner_user_id, word, word_length, guesses_json, active, panel_message_id, started_at)
                   VALUES(?,?,?,?, '[]', 1, ?, ?)
                   ON CONFLICT(chat_id) DO UPDATE SET owner_user_id=excluded.owner_user_id, word=excluded.word, word_length=excluded.word_length, guesses_json='[]', active=1, panel_message_id=excluded.panel_message_id, started_at=excluded.started_at""",
                (chat_id, user.id, word, length, panel_id, datetime.now(timezone.utc).isoformat()),
            )
            await db.commit()
        return

async def word_guess_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    message = update.effective_message
    chat = update.effective_chat
    user = update.effective_user
    if not message or not chat or not user or not message.text or user.is_bot:
        return
    guess = message.text.strip().upper()
    if not guess.isalpha() or len(guess) not in (4, 5, 6):
        return
    row = await _fetch_game(chat.id)
    if not row or not row["active"]:
        return
    if chat.type == "private" and row["owner_user_id"] != user.id:
        return
    if len(guess) != row["word_length"]:
        return
    guesses = json.loads(row["guesses_json"])
    if len(guesses) >= MAX_GUESSES:
        return
    guesses.append({"word": guess, "feedback": _feedback({"word": guess}, row["word"]), "user_id": user.id, "name": user.full_name or user.first_name or "Player"})
    correct = guess == row["word"]
    ended = correct or len(guesses) >= MAX_GUESSES
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
        await message.reply_text(f"🏆 {user.first_name or 'Player'} won the round! The word was {row['word']}.")
    elif ended:
        await _show_game(context, chat.id, row, ended=True)
    else:
        await _show_game(context, chat.id, row)
    raise ApplicationHandlerStop
