import os
import json
from risk_assisment import (
    classify_risk,
    refine_user_software,
    save_installed_software_to_file
)


def check_compliance(actual, expected):
    """Check if actual value meets expected requirement"""
    try:
        if expected.startswith(">="):
            return int(actual) >= int(expected[2:])
        elif expected.startswith("<="):
            return int(actual) <= int(expected[2:])
        else:
            return str(actual).lower() == str(expected).lower()
    except:
        return False


def get_system_risk_level():
    """Get system risk level from GPT analysis"""
    try:
        save_installed_software_to_file("software_list.txt")
        refined_list = refine_user_software("software_list.txt")
        risk_level = classify_risk(refined_list).strip().capitalize()
        return risk_level if risk_level in ["Low", "Medium", "High"] else "Medium"
    except Exception as e:
        print(f"Warning: Could not get system risk assessment: {e}")
        return "Medium"  # default fallback


def parse_audit_log():
    """Parse the latest audit log entries to get actual settings"""
    logfile = r"C:\SecurityDataset\security_audit_log.txt"
    
    if not os.path.exists(logfile):
        raise FileNotFoundError("Audit log not found")

    with open(logfile, "r") as f:
        lines = [line.strip() for line in f if line.strip() and not line.startswith("===")]

    if not lines:
        raise ValueError("No data in audit log")

    # Get the most recent timestamp entries
    latest_timestamp = None
    latest_entries = []
    
    for line in reversed(lines):
        parts = line.split()
        if len(parts) >= 7:  # Need at least 7 parts for complete log entry
            timestamp = f"{parts[0]} {parts[1]}"
            if latest_timestamp is None:
                latest_timestamp = timestamp
                
            if timestamp == latest_timestamp:
                latest_entries.insert(0, line)  # Insert at beginning to maintain order
            else:
                break  # We've found all entries for the latest timestamp

    # Parse entries into settings dictionary
    actual_settings = {}
    for line in latest_entries:
        try:
            parts = line.split()
            if len(parts) >= 7:
                # Correct parsing based on your log format:
                # parts[0] = Date, parts[1] = Time, parts[2] = Device
                # parts[3] = Setting name, parts[4] = Actual value, parts[5] = Expected, parts[6] = Compliant
                setting = parts[3]    # Setting name (e.g., "GuestUser")
                actual = parts[4]     # Actual value (e.g., "Disabled")
                actual_settings[setting] = actual
        except Exception as e:
            print(f"Warning: Could not parse line: {line}, Error: {e}")
            continue

    # Also read from latest_controls.json for additional settings
    json_path = r"C:\SecurityDataset\latest_controls.json"
    if os.path.exists(json_path):
        try:
            with open(json_path, "r") as f:
                json_data = json.load(f)
            
            # Add any missing settings from JSON that aren't in audit log
            for key, value in json_data.items():
                if key not in actual_settings:
                    actual_settings[key] = str(value)
        except Exception as e:
            print(f"Warning: Could not read JSON file: {e}")

    return actual_settings


def get_risk_policy():
    """Define security policies for different risk levels"""
    return {
        "Low": {
            "GuestUser": "Disabled",
            "GuestGroup": "NoMembers", 
            "BitLocker": "Disabled",
            "PasswordLength": ">=8",
            "FIPS": "Disabled",
            "TPM": "Disabled",
            "SmartScreen": "Enabled",
            "UAC": "Enabled",
            "AutoPlay": "Enabled"
        },
        "Medium": {
            "GuestUser": "Disabled",
            "GuestGroup": "NoMembers",
            "BitLocker": "Enabled", 
            "PasswordLength": ">=12",
            "FIPS": "Disabled",
            "TPM": "Enabled",
            "SmartScreen": "Enabled",
            "UAC": "Enabled",
            "AutoPlay": "Disabled"
        },
        "High": {
            "GuestUser": "Disabled",
            "GuestGroup": "NoMembers",
            "BitLocker": "Enabled",
            "PasswordLength": ">=16", 
            "FIPS": "Enabled",
            "TPM": "Enabled",
            "SmartScreen": "Disabled",
            "UAC": "Disabled",
            "AutoPlay": "Disabled"
        }
    }


def calculate_final_score(system_risk, ml_risk, mismatches, total_controls):
    """Calculate final score based on system risk, ML risk, and compliance"""
    
    # Score matrix based on risk level alignment
    risk_alignment_scores = {
        ("Low", "Low"): 90,
        ("Low", "Medium"): 70, 
        ("Low", "High"): 50,
        ("Medium", "Low"): 80,
        ("Medium", "Medium"): 85,
        ("Medium", "High"): 60,
        ("High", "Low"): 60,
        ("High", "Medium"): 75,
        ("High", "High"): 90
    }
    
    # Base score from risk alignment
    base_score = risk_alignment_scores.get((system_risk.lower(), ml_risk.lower()), 70)
    
    # Penalty for mismatches (reduce score based on compliance)
    compliance_rate = (total_controls - len(mismatches)) / total_controls
    compliance_bonus = compliance_rate * 10  # Up to 10 points bonus for full compliance
    
    final_score = min(100, base_score + compliance_bonus)
    return int(final_score)


def compare_with_policy(actual_settings, system_risk):
    """Compare actual settings with policy requirements"""
    risk_policy = get_risk_policy()
    expected_settings = risk_policy[system_risk]
    
    mismatches = []
    for setting, expected_value in expected_settings.items():
        actual_value = actual_settings.get(setting, "Missing")
        if not check_compliance(actual_value, expected_value):
            mismatches.append({
                "setting": setting,
                "actual": actual_value,
                "expected": expected_value
            })
    
    return mismatches


if __name__ == "__main__":
    try:
        # Step 1: Get system risk level from GPT
        system_risk = get_system_risk_level()
        
        # Step 2: Parse actual settings from audit log
        actual_settings = parse_audit_log()
        
        # Step 3: Compare with policy
        mismatches = compare_with_policy(actual_settings, system_risk)
        
        # Step 4: Output result as JSON only
        result = {
            "system_risk": system_risk,
            "mismatches": mismatches,
            "parsed_settings": actual_settings
        }
        
        print(json.dumps(result, indent=2))
        
    except Exception as e:
        print(json.dumps({"error": f"Script execution failed: {str(e)}"}))
        exit(1)