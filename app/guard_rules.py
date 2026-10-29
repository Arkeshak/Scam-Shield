"""Instant, local scam-pressure detector for LIVE calls (no AI, no network, runs in microseconds).
It runs on every finished speech turn. Muse Spark adds a deeper check right after.
These are English heuristics plus a few common phrases. Muse Spark covers other languages."""
import re

WEIGHTS = {"code": 2, "payment": 2, "remote": 2, "secrecy": 1, "urgency": 1, "authority": 1}

CATEGORIES = {
    "secrecy": [
        r"don'?t tell (anyone|anybody|your)", r"do not tell", r"keep (this|it)( a)? secret", r"between (you and me|us)",
        r"nobody (needs|should) (to )?know", r"don'?t (hang up|talk to)",
    ],
    "code": [
        r"\botp\b", r"one[- ]time (code|password|pin)", r"verification code", r"security code", r"\bcvv\b",
        r"(read|tell|give|send|share|say)( me)?( out)? (the |your |that )?(code|pin|password|otp)",
        r"(six|6)[- ]digit", r"\bpin number\b",
    ],
    "urgency": [
        r"right now", r"immediately", r"within (the )?(hour|next \w+ minutes)", r"today only", r"before (midnight|closing)",
        r"last chance", r"\bat once\b", r"don'?t delay", r"running out of time",
    ],
    "payment": [
        r"gift cards?", r"wire (the )?(money|transfer)", r"western union", r"bitcoin|crypto", r"transfer (the |your )?(money|funds)",
        r"send (me )?(the )?money", r"pay (the |a )?(fee|fine|tax)", r"processing fee", r"\bmoneygram\b",
    ],
    "authority": [
        r"\barrest(ed)?\b", r"\bwarrant\b", r"\bpolice\b", r"tax (office|department)|\birs\b", r"legal action",
        r"your account (will be|has been|is) (closed|frozen|suspended|blocked|locked)", r"\bcustoms\b",
    ],
    "remote": [
        r"anydesk|teamviewer|quick ?support", r"remote (access|control)", r"install (this|the|an?) (app|software|program)",
        r"download (this|the|an?) (app|software|program)",
    ],
}
_COMPILED = {cat: [re.compile(p, re.IGNORECASE) for p in pats] for cat, pats in CATEGORIES.items()}

LEVELS = {"low": 0, "medium": 1, "high": 2}

NICE = {
    "secrecy": "asks you to keep it secret", "code": "asks for a code or password", "urgency": "pushes you to act right now",
    "payment": "asks for money or gift cards", "authority": "threatens you with police, tax or account closure",
    "remote": "asks you to install or allow remote control",
}

BANNERS = {
    "English": {"high": "HANG UP. Do not share codes or send money.", "medium": "Be careful. Do not share codes or send money yet.", "low": "Listening. No danger signs so far."},
    "Spanish": {"high": "CUELGUE. No comparta códigos ni envíe dinero.", "medium": "Tenga cuidado. No comparta códigos ni envíe dinero todavía.", "low": "Escuchando. Sin señales de peligro por ahora."},
    "Hindi": {"high": "फ़ोन काट दें। कोई कोड साझा न करें और पैसे न भेजें।", "medium": "सावधान रहें। अभी कोड साझा न करें और पैसे न भेजें।", "low": "सुन रहे हैं। अभी तक कोई ख़तरे का संकेत नहीं।"},
    "Tamil": {"high": "அழைப்பைத் துண்டிக்கவும். குறியீடுகளைப் பகிர வேண்டாம், பணம் அனுப்ப வேண்டாம்.", "medium": "கவனமாக இருங்கள். இப்போது குறியீடுகளைப் பகிரவோ பணம் அனுப்பவோ வேண்டாம்.", "low": "கேட்டுக்கொண்டிருக்கிறோம். இதுவரை ஆபத்து அறிகுறி இல்லை."},
    "Arabic": {"high": "أنهِ المكالمة. لا تشارك أي رموز ولا ترسل أموالاً.", "medium": "كن حذراً. لا تشارك أي رموز ولا ترسل أموالاً الآن.", "low": "نستمع. لا توجد علامات خطر حتى الآن."},
}


def scan_turn(text: str) -> list[dict]:
    """Returns the first match for each category found in one finished turn."""
    found = []
    for cat, patterns in _COMPILED.items():
        for pat in patterns:
            m = pat.search(text or "")
            if m:
                found.append({"category": cat, "phrase": m.group(0)[:40]})
                break
    return found


def level_from_categories(cats: set[str]) -> str:
    score = sum(WEIGHTS[c] for c in cats if c in WEIGHTS)
    hard = bool(cats & {"code", "payment", "remote"})
    if (score >= 3 and hard) or score >= 4:
        return "high"
    if score >= 2:
        return "medium"
    return "low"


def max_level(a: str, b: str) -> str:
    return a if LEVELS.get(a, 0) >= LEVELS.get(b, 0) else b


def banner_for(level: str, language: str = "English") -> str:
    table = BANNERS.get(language, BANNERS["English"])
    return table.get(level, table["low"])


def describe(cats: set[str]) -> str:
    return ", ".join(NICE[c] for c in sorted(cats) if c in NICE)
