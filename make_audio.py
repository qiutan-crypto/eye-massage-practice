#!/usr/bin/env python3
"""Generate the spoken cues for the eye-massage page with Gemini TTS.
Reads data.js, writes audio/<id>.mp3 (step instructions), mantra.mp3, intro.mp3, outro.mp3.
Usage: python make_audio.py /path/to/.env   (needs GEMINI_API_KEY, google-genai, ffmpeg)
Env: ONLY=mantra,s03 to regenerate just those; VOICE=...; OUT=dir (default audio)."""
import json, os, sys, base64, pathlib, subprocess, time, re
from google import genai

here = pathlib.Path(__file__).resolve().parent
if len(sys.argv) > 1:
    for line in pathlib.Path(sys.argv[1]).read_text().splitlines():
        if "=" in line and not line.strip().startswith("#"):
            k, v = line.split("=", 1)
            os.environ.setdefault(k.strip(), v.strip().strip('"').strip("'"))
client = genai.Client(api_key=os.environ["GEMINI_API_KEY"], http_options={"timeout": 90000})
MODEL = os.environ.get("GEMINI_TTS_MODEL", "gemini-3.8-flash-tts")
VOICE = os.environ.get("VOICE", "Sulafat")
GUIDE = ("a calm, gentle Mandarin Chinese instructor guiding a self-massage session. "
         "Speak standard Mandarin, clear, warm and unhurried.")
CHANT = ("a calm Mandarin voice briskly chanting a short Buddhist verse the way a group recites in unison: "
         "four phrases of four characters, steady quick beat, the whole verse in about four seconds, "
         "no pauses between phrases, level tone.")

data = json.loads(re.sub(r"^window\.DATA\s*=\s*", "", (here / "data.js").read_text()).rstrip().rstrip(";"))
out = here / os.environ.get("OUT", "audio"); out.mkdir(exist_ok=True)

def tts(name, text, style):
    for attempt in range(5):
        try:
            r = client.interactions.create(
                model=MODEL,
                input=[{"type": "user_input", "content": [{"type": "text", "text": text,
                        "annotations": [{"type": "speech_metadata", "style": style}]}]}],
                response_format={"type": "audio", "mime_type": "audio/wav", "sample_rate": 24000},
                generation_config={"speech_config": [{"voice": VOICE}]})
            a = r.output_audio.data
            wav = base64.b64decode(a) if isinstance(a, str) else a
            subprocess.run(["ffmpeg", "-v", "error", "-y", "-i", "pipe:0", "-af",
                            "silenceremove=start_periods=1:start_threshold=-50dB,areverse,"
                            "silenceremove=start_periods=1:start_threshold=-50dB,areverse,loudnorm=I=-18",
                            "-ac", "1", "-b:a", "64k", str(out / f"{name}.mp3")], input=wav, check=True)
            print("ok", name, flush=True); return
        except Exception as e:
            print("retry", name, str(e)[:200], flush=True); time.sleep(3 * (attempt + 1))
    raise SystemExit("failed: " + name)

only = set(filter(None, os.environ.get("ONLY", "").split(",")))
jobs = [("mantra", "，".join(data["mantra"]) + "。", CHANT),
        ("intro", data["intro"]["say"], GUIDE), ("outro", data["outro"]["say"], GUIDE)]
jobs += [(s["id"], s["say"], GUIDE) for s in data["steps"]]
for name, text, style in jobs:
    if only and name not in only: continue
    tts(name, text, style)
