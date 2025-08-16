import os, re, json, time, subprocess, sys
from openai import OpenAI

API_KEY = os.getenv("OPENAI_API_KEY")
if not API_KEY:
    print("❌ OPENAI_API_KEY not set"); sys.exit(1)

RAW_FILE = "software_list.txt"
PS = r"C:\Windows\System32\WindowsPowerShell\v1.0\powershell.exe"
PS_SCRIPT = r"""
$list1 = Get-ItemProperty 'HKLM:\Software\Microsoft\Windows\CurrentVersion\Uninstall\*' | ? { $_.DisplayName } | % { $_.DisplayName }
$list2 = Get-ItemProperty 'HKLM:\Software\Wow6432Node\Microsoft\Windows\CurrentVersion\Uninstall\*' | ? { $_.DisplayName } | % { $_.DisplayName }
($list1 + $list2) | Sort-Object -Unique
"""

client = OpenAI(api_key=API_KEY)

def save_installed_software_to_file(path: str):
    try:
        out = subprocess.check_output([PS, "-Command", PS_SCRIPT], text=True, stderr=subprocess.STDOUT, timeout=60)
        lines = [ln.strip() for ln in out.splitlines() if ln.strip()]
        with open(path, "w", encoding="utf-8") as f: f.write("\n".join(lines))
        print(f"✅ Saved {len(lines)} entries → {path}")
    except Exception as e:
        with open(path, "w", encoding="utf-8") as f: f.write("Error: Unable to retrieve installed software.\n")
        print(f"❌ PowerShell error: {e}")

def gpt_call(prompt: str, tries=3, delay=2):
    for i in range(tries):
        try:
            r = client.chat.completions.create(
                model="gpt-4-1106-preview",  # OK; or a newer gpt-4o-mini if you prefer
                messages=[
                    {"role":"system","content":"Reply concisely. If asked for a class label, reply with a single word."},
                    {"role":"user","content": prompt}
                ],
                temperature=0
            )
            return r.choices[0].message.content.strip()
        except Exception as e:
            if i == tries-1: raise
            time.sleep(delay*(i+1))

def refine_user_software(path: str) -> str:
    raw = open(path, "r", encoding="utf-8").read()
    if "Unable to retrieve" in raw:
        print("⚠️ Skipping refinement"); return ""
    prompt = "From the following list, return ONLY end-user applications (one per line). Do not include system components:\n\n" + raw
    refined = gpt_call(prompt)
    print("✅ Refined list ready"); return refined

def classify_risk(refined: str) -> str:
    if not refined: return "UNKNOWN"
    prompt = f"Classify system risk as one word (Low, Medium, or High) based ONLY on this end-user software list:\n\n{refined}\n\nReturn exactly one of: Low | Medium | High."
    label = gpt_call(prompt)
    m = re.search(r"\b(low|medium|high)\b", label, re.I)
    risk = m.group(1).capitalize() if m else "UNKNOWN"
    print(f"📊 SYSTEM RISK LEVEL: {risk}")
    return risk

if __name__ == "__main__":
    save_installed_software_to_file(RAW_FILE)
    refined = refine_user_software(RAW_FILE)
    risk = classify_risk(refined)
    print(json.dumps({"user_software": refined.splitlines(), "system_risk": risk}, ensure_ascii=False))
