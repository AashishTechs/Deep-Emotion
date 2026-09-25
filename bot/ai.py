import asyncio

from google import genai
from google.genai import types

from config import GEMINI_API_KEY, GEMINI_MODEL


client = genai.Client(api_key=GEMINI_API_KEY)


SYSTEM_PROMPT = """
You are Deep Emotions, a friendly female AI chatbot.

Personality:
- Warm, caring, friendly and natural.
- Talk like a real person, not like a robotic assistant.
- Understand Hindi, English and Hinglish.
- Reply in the same language/style the user uses.
- Keep normal conversations natural and engaging.
- You can use emojis naturally, but don't overuse them.
- Never mention that you are following a system prompt.
- Don't unnecessarily give long answers.
- For simple questions, give simple answers.
- For technical questions, explain clearly with examples.
"""


async def generate_reply(history, user_message):
    contents = []

    for message in history:
        # Database history can be returned as tuple:
        # (role, text)
        if isinstance(message, tuple):
            role, text = message

        # Or as dictionary:
        # {"role": "...", "text": "..."}
        elif isinstance(message, dict):
            role = message.get("role")
            text = message.get("text", "")

        else:
            continue

        if not text:
            continue

        if role == "user":
            contents.append(
                types.Content(
                    role="user",
                    parts=[types.Part(text=text)]
                )
            )

        elif role == "model":
            contents.append(
                types.Content(
                    role="model",
                    parts=[types.Part(text=text)]
                )
            )

    # Current user message
    contents.append(
        types.Content(
            role="user",
            parts=[types.Part(text=user_message)]
        )
    )

    config = types.GenerateContentConfig(
        system_instruction=SYSTEM_PROMPT,
        max_output_tokens=600,
    )

    # Retry temporary Gemini 503 errors
    max_retries = 3

    for attempt in range(max_retries):
        try:
            response = await client.aio.models.generate_content(
                model=GEMINI_MODEL,
                contents=contents,
                config=config,
            )

            if response.text:
                return response.text.strip()

            return (
                "Hmm 💗 mujhe abhi proper response nahi mila. "
                "Dobara try karo."
            )

        except Exception as e:
            error_text = str(e)

            if "503" in error_text or "UNAVAILABLE" in error_text:
                if attempt < max_retries - 1:
                    wait_time = 2 ** attempt

                    print(
                        f"Gemini temporarily unavailable. "
                        f"Retry {attempt + 1}/{max_retries} "
                        f"in {wait_time}s..."
                    )

                    await asyncio.sleep(wait_time)
                    continue

                print(
                    f"Gemini unavailable after "
                    f"{max_retries} attempts."
                )

                return (
                    "Aww 💗 Gemini abhi thoda busy hai. "
                    "2-3 minute baad mujhe phir message karo."
                )

            print(f"AI error: {e}")

            return (
                "Sorry 💗 abhi AI service se connection "
                "nahi ho pa raha. Thodi der baad try karo."
            )

    return "Sorry 💗 abhi AI service available nahi hai."