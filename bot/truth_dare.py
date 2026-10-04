import random

from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.ext import ContextTypes


TRUTHS = [
    "👀 Group mein kiski profile tumne sabse recently check ki?",
    "😂 Aisa kaunsa jhooth hai jo tum aaj tak confidently bolte aaye ho?",
    "❤️ Agar abhi kisi ek person ko date par le jaana ho, kaun?",
    "🤭 Kya tumne kabhi kisi ko impress karne ke liye apni personality fake ki?",
    "😏 Tumhara current crush hai? Naam nahi batana ho to initial batao.",
    "🫣 Tumhari sabse embarrassing chat kis type ki thi?",
    "😂 Group mein sabse zyada drama kaun karta hai?",
    "💭 Kya tumne kabhi message type karke send nahi kiya? Kisko?",
    "🔥 Agar 24 hours ke liye invisible ho jao, pehla kaam kya karoge?",
    "😈 Kisi ek habit ko turant delete kar sakte ho — kaunsi?",
    "🥹 Last time kab kisi ki wajah se genuinely emotional hue the?",
    "👀 Kya tumne kabhi kisi ka last seen/profile picture baar-baar check kiya?",
    "💌 Agar purane crush ko ek honest message bhejna ho, kya likhoge?",
    "🤣 Tumhari life ka sabse funny fail kya hai?",
    "😶 Kya tumne kabhi 'busy hoon' bola jab actually reply nahi karna tha?",
    "💘 Personality ya looks — attraction mein pehle kya notice karte ho?",
    "🫢 Kya tumne kabhi kisi friend ka secret accidentally leak kiya?",
    "🌙 Late night mein sabse zyada kis type ke thoughts aate hain?",
    "😂 Tumhara sabse useless talent kya hai?",
    "👑 Group mein kis person ko 1 day ke liye admin banana chahoge?",
    "😏 Agar tumhe ek person ke saath 6-hour road trip karni ho, kaun?",
    "📱 Last 5 searches mein sabse weird search kya tha?",
    "💔 Kya tumne kabhi kisi ko miss kiya but message nahi kiya?",
    "🤫 Aisi kaunsi baat hai jo tum normally kisi ko nahi batate?",
    "🎭 Log tumhe kis baat mein galat samajhte hain?",
    "💸 Agar ₹1 crore mil jaye but phone permanently chhodna pade, deal?",
    "🧠 Tumne apne baare mein recently kya realize kiya?",
    "😂 Tumhara sabse bada 'maine ye kyun kiya?' moment kya tha?",
    "❤️ Love mein first move karna pasand hai ya saamne wale ka wait?",
    "👀 Kya tumne kabhi kisi ko online stalk kiya? Honest answer.",
    "😈 Agar group ke kisi member ki thoughts 10 minutes padh sako, kiske?",
    "🫣 Kya tumne kabhi wrong person ko message bheja? Kya hua?",
    "🌚 Raat ko 2 baje tumhe kaun call kare to turant uthaoge?",
    "🔥 Tumhari sabse attractive quality kya hai?",
    "🤭 Kya tum kabhi kisi se jealous hue ho but accept nahi kiya?",
    "🎯 Ek decision jo tum apni life mein change karna chahoge?",
    "😂 Tumhara most-used excuse kya hai?",
    "💗 Kisi ko like karte ho to sabse pehle kya notice karte ho?",
    "👀 Agar tumhara phone 1 minute ke liye group ke paas ho, sabse zyada dar kis cheez ka hai?",
]

DARES = [
    "😂 Group mein kisi active member ko ek genuine funny compliment do.",
    "😏 Apne mood ko sirf 3 emojis mein describe karo.",
    "🔥 10 seconds mein ek funny pickup line banao aur bhejo.",
    "👀 Kisi member ko tag karke bolo: 'Tum suspiciously quiet ho aaj.'",
    "🤣 Apne next message mein sirf emojis use karo.",
    "💗 Kisi ek member ki ek achhi quality honestly batao.",
    "🎭 Apna naam 1 minute ke liye kisi funny nickname se imagine karo aur announce karo.",
    "😂 Ek intentionally terrible joke sunao.",
    "😈 Group ke last message ka funny but harmless reply do.",
    "🎤 Apni favourite song ka sirf 1 line ka text share karo.",
    "🫣 Apni most-used emoji batao aur reason explain karo.",
    "🔥 Kisi friend ko 'aaj tum VIP ho' message bhejo.",
    "🤣 3 words mein apni love life describe karo.",
    "👑 Kisi group member ko 'aaj se tum legend ho' bolo.",
    "🌚 Apna current mood ek movie title ki tarah likho.",
    "😏 Ek clean, funny pickup line kisi willing friend ke liye banao.",
    "😂 5 seconds mein apne naam ka funny full form banao.",
    "💭 Ek unpopular opinion share karo — respectful rehna.",
    "🎯 Apni dream destination ka naam dramatic style mein announce karo.",
    "🤭 Ek harmless embarrassing habit confess karo.",
    "🔥 Group mein kisi ko challenge karo ki woh bhi Truth or Dare choose kare.",
    "😂 Apni typing style ko 3 emojis mein roast karo.",
    "💌 Kisi friend ko ek wholesome 'thank you' message bhejo.",
    "😈 Apne next 2 messages mein 'bro' word use karna mandatory.",
    "🎬 Apni life ka current scene ek movie dialogue mein describe karo.",
    "👀 Kisi active member se ek interesting question poochho.",
    "🤣 Ek fake breaking-news headline apne baare mein banao.",
    "❤️ Kisi friend ko genuinely batao ki tum unki kaunsi quality pasand karte ho.",
    "🧠 Ek random fact share karo jo tumhe interesting lagta hai.",
    "😎 Apne aap ko ek funny one-line bio do.",
]

def _keyboard():
    return InlineKeyboardMarkup([
        [
            InlineKeyboardButton("🎯 Truth", callback_data="td:truth"),
            InlineKeyboardButton("🔥 Dare", callback_data="td:dare"),
        ],
        [
            InlineKeyboardButton("🎲 Random", callback_data="td:random"),
        ],
    ])

def _pick(kind):
    if kind == "truth":
        return "🎯 **TRUTH**\n\n" + random.choice(TRUTHS)
    if kind == "dare":
        return "🔥 **DARE**\n\n" + random.choice(DARES)
    return _pick(random.choice(["truth", "dare"]))

async def truth_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.message:
        await update.message.reply_text(_pick("truth"), parse_mode="Markdown", reply_markup=_keyboard())

async def dare_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.message:
        await update.message.reply_text(_pick("dare"), parse_mode="Markdown", reply_markup=_keyboard())

async def truth_dare_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.message:
        await update.message.reply_text(
            "🎮 **Truth or Dare**\n\nChoose your challenge 👇",
            parse_mode="Markdown",
            reply_markup=_keyboard(),
        )

async def truth_dare_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    if not query or not query.message:
        return
    await query.answer()
    data = query.data or ""
    if data == "td:truth":
        text = _pick("truth")
    elif data == "td:dare":
        text = _pick("dare")
    elif data == "td:random":
        text = _pick("random")
    else:
        return
    await query.edit_message_text(text, parse_mode="Markdown", reply_markup=_keyboard())
