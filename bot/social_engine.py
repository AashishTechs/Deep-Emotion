# ==========================================================
# DEEP EMOTION — SMART SOCIAL ENGINE
# ==========================================================

import random
import re
import time


# Group-level AI reply cooldown is disabled for normal messages.
# Direct mentions/replies also always get a response.
GROUP_AI_COOLDOWN = 0
_last_group_reply = {}

POSITIVE = {
    "happy", "khush", "love", "mast", "awesome", "great", "nice",
    "haha", "lol", "😂", "❤️", "😍", "🥰", "party"
}
NEGATIVE = {
    "sad", "dukhi", "pareshan", "tension", "depressed", "cry",
    "rona", "ro raha", "ro rahi", "problem", "bura", "hurt"
}
QUESTION_WORDS = {
    "kya", "kyu", "kyun", "kaise", "kaisa", "kon", "kaun",
    "where", "what", "why", "how", "when", "who"
}
SOCIAL_WORDS = {
    "single", "relationship", "crush", "love", "shaadi", "marriage",
    "gf", "bf", "date", "flirt", "bored", "akela", "akele"
}


def analyze_message(text):
    """Lightweight local analysis used before deciding whether to speak."""
    lowered = (text or "").lower()
    words = set(re.findall(r"[a-zA-ZÀ-ÿ]+", lowered))

    return {
        "question": "?" in lowered or bool(words & QUESTION_WORDS),
        "positive": bool(words & POSITIVE),
        "negative": bool(words & NEGATIVE),
        "social": bool(words & SOCIAL_WORDS),
        "short": len(lowered.split()) <= 3,
        "long": len(lowered.split()) >= 25,
        "has_emoji": any(ch in lowered for ch in "😂❤️🥰😍😭😏🤭"),
    }


def should_reply_group(
    chat_id,
    text,
    mentioned=False,
    replied_to_bot=False,
    other_user_mentioned=False,
):
    """
    Reply to normal group messages, bot mentions, and replies to the bot.

    If a message explicitly mentions another user (but not the bot),
    treat it as a direct conversation between users and stay silent.
    """
    if mentioned or replied_to_bot:
        return True

    if other_user_mentioned:
        return False

    return True


def mark_group_reply(chat_id):
    _last_group_reply[chat_id] = time.monotonic()


def social_game(game):
    """Small no-API games for group entertainment."""
    truth = [
        "GC mein sabse zyada kiski vibe pasand hai? 👀",
        "Tumhara current crush hai ya secret hai? 😏",
        "Aaj ki sabse funny baat kya hui?",
        "Ek aisi habit batao jo tum hide karte ho 😂",
        "Kis member ke saath late-night chai best lagegi?",
    ]

    dare = [
        "GC mein kisi ko genuine compliment do 💜",
        "Apna last-used emoji spam kiye bina explain karo 😂",
        "10 seconds mein ek funny pickup line banao 😏",
        "Kisi active member ko 'aaj tum suspiciously quiet ho' bolo 👀",
        "Apna mood sirf 3 emojis mein batao.",
    ]

    would_you_rather = [
        "1 saal bina Instagram ya 1 saal bina YouTube? 👀",
        "Crush ko text ya crush se face-to-face baat? 😏",
        "Unlimited money but no travel, ya unlimited travel but normal income?",
        "Past change karna ya future dekhna?",
        "GC ka king/queen banna ya invisible rehna? 😂",
    ]

    jokes = [
        "Mera social battery 1% hai, charger kaun banega? 😂",
        "GC mein '5 minute' bolne wale 2 ghante baad aate hain 😭",
        "Aaj attendance lagao: jo online hai woh ek emoji drop kare 👀",
        "Important question: chai first ya gossip first? 😏",
    ]

    key = (game or "").lower()
    if key in {"truth", "truth_or_dare"}:
        return "🎯 Truth: " + random.choice(truth)
    if key == "dare":
        return "🔥 Dare: " + random.choice(dare)
    if key in {"wyr", "would", "would_you_rather"}:
        return "🤔 Would you rather: " + random.choice(would_you_rather)
    return "😂 " + random.choice(jokes)


def activity_prompt(context, recent_target=None):
    """Prompt used by proactive mode to vary social behavior."""
    styles = [
        "warm check-in",
        "funny observation",
        "playful teasing",
        "topic follow-up",
        "light mood check",
        "casual conversation starter",
    ]
    style = random.choice(styles)

    return f"""
You are starting a natural group conversation.
Style: {style}
Recent group context:
{context}

Create ONE short Hinglish message, 1-2 sentences.
You may mention one active member naturally.
Possible themes: good morning, what are you doing, why so quiet,
a harmless joke, checking if someone is okay, or a playful question.
Mild flirting is okay only as harmless banter. No explicit sexual content.
Do not guilt-trip, manipulate, pressure, or encourage dependency.
Do not reveal private information or claim this is automated.
Return only the message.
"""