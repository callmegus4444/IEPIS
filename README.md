# IEPIS
# AI-Driven Endpoint Risk & Compliance – README

A Windows-focused framework that audits endpoint controls, classifies device risk (GPT + TabNet), checks policy compliance, and returns a 0–100 final score via a Flask API or a packaged executable.

---

## 1) Overview

**Goal.** Tailor security to device context. We combine:
- **Security audit** → collect actual control states (BitLocker, TPM, SmartScreen, etc.).
- **GPT risk** → classify device risk (Low/Medium/High) from *user-installed* software.
- **Policy compare** → expected vs actual per risk tier → mismatches.
- **TabNet ML** → predict ML risk from control vector.
- **Final score** → fuse risk alignment + compliance into a single 0–100 metric.

**High-level Flow**

```text
Security Audit (controls)      Installed Software → GPT → System Risk
          |                                      |
          v                                      v
  Policy Compare (per risk)   TabNet ML (control vector) → ML Risk
          |                                      |
          +------------→ Mismatches & Compliance |
                        \________________________/
                          Final Score (0–100)
```

---

## 2) Project Structure

```
.
├── compare_controls.py            # GPT risk + parse audit log + policy compare → JSON result
├── comapre_controls_modified.py   # Full Windows audit + GPT software filtering + risk
├── ml_model_api.py                # Flask API: runs compare_controls, TabNet predict, final score
├── TabnetRfHybrid.h5              # Trained TabNet model (required at runtime)
├── tabnet_encoders.pkl            # Encoders for categorical features (required at runtime)
├── run.bat                        # (Provided by you) Helper to run the EXE / API
└── README.md
```

Windows artifacts at runtime:
- `C:\SecurityDataset\security_audit_log.txt` (audit output)
- `C:\SecurityDataset\latest_controls.json` (control data used by TabNet and compare steps)

**Note:** If you don’t have `risk_assisment.py`, use `comapre_controls_modified.py` which contains the GPT calls and full audit pipeline.

---

## 3) Prerequisites

- **OS:** Windows 10/11 (required for audit commands/registry paths).  
- **Python:** 3.10+ (recommended).
- **API Key:** `OPENAI_API_KEY` set in your environment (needed for GPT steps).
- **Python packages:**
  ```bash
  pip install flask numpy joblib pytorch-tabnet openai
  # Install a CPU-only PyTorch matching your Python (see pytorch.org for exact command)
  ```

**Set environment variable (Windows PowerShell):**
```powershell
setx OPENAI_API_KEY "sk-******"
```

---

## 4) Required Data Files

- `TabnetRfHybrid.h5` – TabNet model weights.  
- `tabnet_encoders.pkl` – encoders for 11 features.  
- `C:\SecurityDataset\latest_controls.json` – the latest control snapshot your model/API reads.

**Example `latest_controls.json` skeleton** (ensure keys exist; values are strings or numbers as expected):
```json
{
  "SmartScreen": "Enabled",
  "TPM": "Enabled",
  "BitLocker": "Enabled",
  "GuestUser": "Disabled",
  "PasswordLength": 12,
  "FIPS": "Disabled",
  "UAC": "Enabled",
  "AutoPlay": "Disabled",
  "AVProductsInstalled": 2,
  "Census_IsSecureBootEnabled": 1,
  "Census_IsVirtualDevice": 0
}
```

---

## 5) How It Works (Detailed)

1. **Security Audit (Windows)** – `comapre_controls_modified.py`  
   - Queries registry & OS commands to record controls like BitLocker/TPM/UAC/SmartScreen/AutoPlay/password policy into `C:\SecurityDataset\security_audit_log.txt`.
   - Also extracts installed software via PowerShell, filters **user-installed** apps with GPT, and classifies **system risk** (Low/Medium/High).

2. **Policy Compare & Mismatch Report** – `compare_controls.py`  
   - Parses the **latest timestamp** entries in the audit log + merges values from `latest_controls.json`.
   - For the `system_risk`, loads the corresponding **expected policy** and compares with actuals, producing **mismatches**.

3. **ML Prediction (TabNet)** – `ml_model_api.py`  
   - Loads encoders + TabNet model; builds a numeric feature vector from `latest_controls.json`.
   - Predicts **ML risk** (Low/Medium/High).

4. **Final Score**  
   - **Base score** from risk alignment matrix (agreement earns higher base).  
   - **Compliance bonus** = `compliance_rate * 10` (up to +10), where `compliance_rate = (total_controls - mismatches) / total_controls`.  
   - **Final score = min(100, base + bonus)**.

---

## 6) Run – Development Mode (Python)

### A) Run the full audit + GPT risk (Windows, requires OPENAI key)
```bash
python comapre_controls_modified.py
```

### B) Start the API
```bash
python ml_model_api.py
```
- Starts Flask on `http://0.0.0.0:7000`
- Endpoint: `POST /api/evaluate`
- Response JSON fields: `system_risk`, `ml_risk`, `mismatches`, `final_score`, `total_controls`, `compliant_controls`

**Quick test (PowerShell):**
```powershell
Invoke-RestMethod -Uri http://localhost:7000/api/evaluate -Method Post
```

---

## 7) Run – Using the Executable + run.bat

> You’ll provide the `.exe` (built from `ml_model_api.py` or from your CLI runner). Place it in the project root next to model files.

**Folder checklist (same directory):**
```
YourApp.exe
TabnetRfHybrid.h5
tabnet_encoders.pkl
run.bat
```

**Ensure runtime data:**
- `C:\SecurityDataset\latest_controls.json` present.
- `OPENAI_API_KEY` set if the EXE triggers GPT workflows (e.g., if it calls the audit/GPT path).

**run.bat** (example template if you need one):
```bat
@echo off
set OPENAI_API_KEY=sk-******
REM Optional: activate venv if using Python EXE wrapper
REM call venv\Scripts\activate
REM Start API server EXE
start "" "%~dp0YourApp.exe"
echo Server starting on port 7000. Press any key to exit this window.
pause >nul
```

**Launch:** double-click `run.bat` (or run from cmd). Then call `http://localhost:7000/api/evaluate`.

> If your EXE is a one-shot CLI that prints results, adapt `run.bat` to just call it:
> `"%~dp0YourApp.exe" && pause`

**(Optional) Build your own EXE with PyInstaller:**
```bash
pyinstaller --onefile --name YourApp ^
  --add-data "TabnetRfHybrid.h5;." ^
  --add-data "tabnet_encoders.pkl;." ^
  ml_model_api.py
```
The generated EXE will be in `dist/YourApp.exe`.

---

## 8) GitHub – Push Step‑by‑Step

1. **Sign in** to GitHub and click **New repository** → name it (e.g., `ai-endpoint-risk-compliance`).  
2. **Local init**
   ```bash
   git init
   git branch -M main
   ```
3. **.gitignore** – create a file to keep secrets & noisy artifacts out:
   ```text
   # Python
   __pycache__/
   .venv/
   *.pyc
   # Models & local data
   TabnetRfHybrid.h5
   tabnet_encoders.pkl
   /dist/
   /build/
   *.spec
   # Windows dataset / logs
   C:/SecurityDataset/
   # Keys
   *.env
   ```
4. **Commit & connect**
   ```bash
   git add .
   git commit -m "Initial commit: audit + GPT risk + TabNet + API"
   git remote add origin https://github.com/<your-username>/ai-endpoint-risk-compliance.git
   git push -u origin main
   ```
5. **Large files?** If you must version model files, use **Git LFS**:
   ```bash
   git lfs install
   git lfs track "*.h5" "*.pkl"
   git add .gitattributes
   git commit -m "Track model files with LFS"
   git push
   ```
6. **Protect secrets** – never commit API keys; use GitHub **Actions secrets** or an `.env` ignored by git.

---

## 9) Troubleshooting

- **Model can’t load** → ensure `TabnetRfHybrid.h5` and `tabnet_encoders.pkl` are beside the EXE/API script; verify compatible library versions.  
- **Controls file not found** → create `C:\SecurityDataset\latest_controls.json` with the required keys.  
- **OPENAI key error** → set `OPENAI_API_KEY` and restart.  
- **Windows commands missing** → run on Windows with admin PowerShell for BitLocker/TPM queries.  
- **Port in use** → change Flask port in `ml_model_api.py` (e.g., `port=7001`).

---

## 10) License & Contact

Add your license (MIT/BSD/Apache-2.0). For questions, open a GitHub issue or contact the author.
