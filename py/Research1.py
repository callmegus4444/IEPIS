import datetime
import socket
import subprocess
import os
import winreg
import json

folder = r"C:\SecurityDataset"
os.makedirs(folder, exist_ok=True)
logfile = os.path.join(folder, "security_audit_log.txt")

timestamp = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
device = socket.gethostname()

results = {}

def write_result(setting, actual, ideal, compliant=None):
    if compliant is None:
        compliant = "Yes" if actual == ideal else "No"
    with open(logfile, "a") as f:
        f.write(f"{timestamp:<19} {device:<14} {setting:<19} {actual:<14} {ideal:<14} {compliant:<10}\n")
    results[setting] = actual

# 1. GuestUser
try:
    out = subprocess.check_output(["net", "user", "Guest"], stderr=subprocess.DEVNULL, text=True)
    active = [line for line in out.splitlines() if "Account active" in line]
    actual = "Enabled" if active and active[0].strip().endswith("Yes") else "Disabled"
except:
    actual = "Unknown"
write_result("GuestUser", actual, "Disabled")

# 2. GuestGroup
try:
    out = subprocess.check_output(["net", "localgroup", "Guests"], stderr=subprocess.DEVNULL, text=True)
    actual = "HasMembers" if sum(1 for line in out.splitlines() if line.strip()) > 6 else "NoMembers"
except:
    actual = "Unknown"
write_result("GuestGroup", actual, "NoMembers")

# 3. BitLocker
try:
    out = subprocess.check_output(["manage-bde", "-status", "C:"], stderr=subprocess.DEVNULL, text=True)
    actual = "Enabled" if "Protection Status" in out and "On" in out else "Disabled"
except:
    actual = "Unknown"
write_result("BitLocker", actual, "Enabled")

# 4. PasswordLength
try:
    out = subprocess.check_output(["net", "accounts"], stderr=subprocess.DEVNULL, text=True)
    pwdlen = next((int(line.split()[-1]) for line in out.splitlines() if "Minimum password length" in line), 0)
    actual = str(pwdlen)
except:
    actual = "0"
write_result("PasswordLength", actual, ">=8")

# 5. FIPS
try:
    key = winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, r"SYSTEM\CurrentControlSet\Control\Lsa\FipsAlgorithmPolicy")
    val, _ = winreg.QueryValueEx(key, "Enabled")
    actual = "Enabled" if val == 1 else "Disabled"
    winreg.CloseKey(key)
except:
    actual = "Disabled"
write_result("FIPS", actual, "Enabled")

# 6. TPM
try:
    out = subprocess.check_output(["powershell", "-Command", "(Get-Tpm).TpmPresent"], stderr=subprocess.DEVNULL, text=True)
    actual = "Enabled" if "True" in out else "Disabled"
except:
    actual = "Unknown"
write_result("TPM", actual, "Enabled")

# 7. SmartScreen
try:
    key = winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, r"SOFTWARE\Microsoft\Windows\CurrentVersion\Explorer")
    val, _ = winreg.QueryValueEx(key, "SmartScreenEnabled")
    actual = "Enabled" if str(val) in ("RequireAdmin", "Warn") else "Disabled"
    winreg.CloseKey(key)
except:
    actual = "Disabled"
write_result("SmartScreen", actual, "Enabled")

# 8. UAC
try:
    key = winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, r"SOFTWARE\Microsoft\Windows\CurrentVersion\Policies\System")
    val, _ = winreg.QueryValueEx(key, "EnableLUA")
    actual = "Enabled" if val == 1 else "Disabled"
    winreg.CloseKey(key)
except:
    actual = "Disabled"
write_result("UAC", actual, "Enabled")

# 9. AutoPlay
try:
    key = winreg.OpenKey(winreg.HKEY_CURRENT_USER, r"Software\Microsoft\Windows\CurrentVersion\Explorer\AutoplayHandlers")
    val, _ = winreg.QueryValueEx(key, "DisableAutoplay")
    actual = "Disabled" if val == 1 else "Enabled"
    winreg.CloseKey(key)
except:
    actual = "Enabled"
write_result("AutoPlay", actual, "Disabled")

# 10. AVProductsInstalled (via PowerShell Defender)
try:
    out = subprocess.check_output(["powershell", "-Command", "(Get-MpComputerStatus).AntivirusEnabled"], stderr=subprocess.DEVNULL, text=True)
    actual = int("True" in out.strip())
except:
    actual = 0
results["AVProductsInstalled"] = actual

# 11. Census_IsSecureBootEnabled
try:
    out = subprocess.check_output(["powershell", "-Command", "Confirm-SecureBootUEFI"], stderr=subprocess.DEVNULL, text=True)
    actual = int("True" in out.strip())
except:
    actual = 0
results["Census_IsSecureBootEnabled"] = actual

# 12. Census_IsVirtualDevice
try:
    out = subprocess.check_output(["powershell", "-Command", "(Get-WmiObject Win32_ComputerSystem).Model"], stderr=subprocess.DEVNULL, text=True)
    actual = 1 if any(v in out.lower() for v in ["vmware", "virtual", "qemu", "kvm", "hyper-v"]) else 0
except:
    actual = 0
results["Census_IsVirtualDevice"] = actual

# Save JSON for ML use
with open(os.path.join(folder, "latest_controls.json"), "w") as jf:
    json.dump(results, jf, indent=2)

print("All system controls collected (real values) and saved.")

