from flask import Flask, jsonify
import os
import json
import numpy as np
import joblib
import subprocess
import re
from pytorch_tabnet.tab_model import TabNetClassifier

app = Flask(__name__)

# === ALL 11 features based on your actual data ===
TABNET_FEATURE_COLUMNS = [
    "SmartScreen",
    "TPM",
    "BitLocker", 
    "GuestUser",
    "PasswordLength",
    "FIPS",
    "UAC",
    "AutoPlay",
    "AVProductsInstalled",
    "Census_IsSecureBootEnabled",
    "Census_IsVirtualDevice"
]

# === Load model and encoders ===
def load_model_safely():
    global model, encoders
    try:
        model = TabNetClassifier()
        model.load_model("TabnetRfHybrid.h5")
        encoders = joblib.load("tabnet_encoders.pkl")
        print("✅ Model and encoders loaded successfully")
        print(f"✅ Model expects {len(TABNET_FEATURE_COLUMNS)} features")
        return True
    except Exception as e:
        print(f"❌ Model loading failed: {e}")
        return False

if not load_model_safely():
    print("❌ Exiting due to model loading failure")
    exit(1)


def get_system_risk_and_mismatches():
    """Get system risk level and mismatches by running compare_controls.py"""
    try:
        result = subprocess.run(
            ["python", "compare_controls.py"], 
            capture_output=True, 
            text=True, 
            cwd=os.getcwd()
        )
        
        if result.returncode != 0:
            raise Exception(f"compare_controls.py failed: {result.stderr}")
        
        # Parse output - handle the case where there might be print statements before JSON
        output = result.stdout.strip()
        print(f"📥 GPT Script Output: {output}")
        
        # Try to extract JSON from the output
        json_match = re.search(r'\{.*\}', output, re.DOTALL)
        if json_match:
            json_str = json_match.group(0)
            return json.loads(json_str)
        else:
            # If no JSON found, try to parse line by line
            lines = output.split('\n')
            for line in lines:
                line = line.strip()
                if line.startswith('{'):
                    # Try to parse this line and subsequent lines as JSON
                    json_start = output.find(line)
                    potential_json = output[json_start:]
                    try:
                        return json.loads(potential_json)
                    except:
                        continue
            
            raise Exception("No valid JSON found in output")
        
    except Exception as e:
        print(f"⚠️ Could not parse GPT risk level: {e}")
        print(f"Raw output: {result.stdout if 'result' in locals() else 'No output'}")
        return {
            "system_risk": "Medium",
            "mismatches": [],
            "parsed_settings": {}
        }


def calculate_final_score(system_risk, ml_risk, mismatches_count, total_controls):
    """Calculate final score based on system risk, ML risk, and compliance"""
    
    # Score matrix based on risk level alignment
    risk_alignment_scores = {
        ("low", "low"): 90,
        ("low", "medium"): 70, 
        ("low", "high"): 50,
        ("medium", "low"): 80,
        ("medium", "medium"): 85,
        ("medium", "high"): 60,
        ("high", "low"): 60,
        ("high", "medium"): 75,
        ("high", "high"): 90
    }
    
    # Base score from risk alignment
    base_score = risk_alignment_scores.get(
        (system_risk.lower(), ml_risk.lower()), 70
    )
    
    # Penalty for mismatches
    if total_controls > 0:
        compliance_rate = (total_controls - mismatches_count) / total_controls
        compliance_bonus = compliance_rate * 10  # Up to 10 points bonus
    else:
        compliance_bonus = 0
    
    final_score = min(100, base_score + compliance_bonus)
    return int(final_score)


# === Evaluate endpoint ===
@app.route("/api/evaluate", methods=["POST"])
def evaluate():
    try:
        print("🔄 API HIT: /api/evaluate")

        # Step 1: Get system risk and mismatches
        system_data = get_system_risk_and_mismatches()
        system_risk = system_data.get("system_risk", "Medium")
        system_mismatches = system_data.get("mismatches", [])
        
        print(f"📊 System Risk Level: {system_risk}")
        print(f"📊 System Mismatches: {len(system_mismatches)}")

        # Step 2: Load control data for ML prediction
        json_path = r"C:\SecurityDataset\latest_controls.json"
        print(f"📁 Reading control file: {json_path}")

        if not os.path.exists(json_path):
            return jsonify({
                "error": "Controls file not found",
                "detail": f"File not found: {json_path}"
            }), 404

        with open(json_path, "r") as f:
            data = json.load(f)

        print("✅ Control data loaded:", data)

        # Step 3: Build ML model input
        feature_vector = []
        for col in TABNET_FEATURE_COLUMNS:
            value = data.get(col, "Missing")
            
            encoder = encoders.get(col)

            try:
                if encoder and hasattr(encoder, 'transform'):
                    if value == "Missing" or value == "Unknown":
                        encoded_value = 0  # Default fallback
                    else:
                        encoded_value = encoder.transform([str(value)])[0]
                else:
                    # Numerical feature
                    encoded_value = float(value) if value not in ["Missing", "Unknown"] else 0.0
            except Exception as e:
                print(f"⚠️ '{col}' had invalid value '{value}' — using fallback 0. Error: {e}")
                encoded_value = 0

            feature_vector.append(encoded_value)

        # Convert to numpy array
        feature_vector = [float(x) for x in feature_vector]
        X = np.array([feature_vector], dtype=np.float32)
        
        print(f"📊 Final input vector ({len(feature_vector)} features):", feature_vector)
        print("✅ Shape before predict:", X.shape)

        # Step 4: Predict ML risk
        y_pred = model.predict(X)[0]
        ml_risk = ["Low", "Medium", "High"][int(y_pred)]
        print("🤖 Predicted ML Risk:", ml_risk)

        # Step 5: Calculate final score
        total_controls = 9  # Number of security controls we check
        final_score = calculate_final_score(
            system_risk, 
            ml_risk, 
            len(system_mismatches), 
            total_controls
        )
        
        print("📈 Final Score:", final_score)

        return jsonify({
            "system_risk": system_risk,
            "ml_risk": ml_risk,
            "mismatches": system_mismatches,
            "final_score": final_score,
            "total_controls": total_controls,
            "compliant_controls": total_controls - len(system_mismatches)
        })

    except Exception as e:
        import traceback
        traceback.print_exc()
        return jsonify({
            "error": "Evaluation failed",
            "detail": str(e)
        }), 500


# === Run Flask app ===
if __name__ == "__main__":
    app.run(host="0.0.0.0", port=7000)