const express = require("express");
const router = express.Router();
const { exec } = require("child_process");
const axios = require("axios");
const path = require("path");
const fs = require("fs");

router.get("/evaluate-all", async (req, res) => {
  console.log("📍 Route hit: /api/audit/evaluate-all");

  // Step 1: Run Research1.py to collect latest control settings
  const pythonScript = path.join(__dirname, "..", "py", "Research1.py");

  exec(`python "${pythonScript}"`, async (error, stdout, stderr) => {
    if (error) {
      console.error("❌ Failed to run Research1.py:", error.message);
      console.error("Stderr:", stderr);
      return res.status(500).json({ error: "Failed to collect system controls", detail: error.message });
    }

    console.log("✅ Research1.py executed");
    console.log("Output:", stdout);

    // Step 2: Check if controls file was created
    const controlsFile = path.join("C:", "SecurityDataset", "latest_controls.json");
    const auditLogFile = path.join("C:", "SecurityDataset", "security_audit_log.txt");
    
    if (!fs.existsSync(controlsFile)) {
      console.error("❌ Controls file not created");
      return res.status(500).json({ error: "Controls file not created" });
    }

    // Step 2.5: Wait for files to be fully written (fix race condition)
    console.log("⏳ Waiting for files to be fully written...");
    await new Promise(resolve => setTimeout(resolve, 2000)); // 2 second delay

    // Step 2.6: Verify audit log has recent data
    try {
      const auditLogStats = fs.statSync(auditLogFile);
      const timeSinceModified = Date.now() - auditLogStats.mtime.getTime();
      console.log(`📊 Audit log last modified: ${timeSinceModified}ms ago`);
      
      if (timeSinceModified > 10000) { // If older than 10 seconds
        console.warn("⚠️ Audit log seems stale, but continuing...");
      }
    } catch (err) {
      console.error("❌ Could not check audit log:", err.message);
      return res.status(500).json({ error: "Audit log not accessible" });
    }

    // Step 3: Call ML API with better error handling
    try {
      console.log("🤖 Calling ML API...");
      const response = await axios.post("http://localhost:7000/api/evaluate", {}, {
        timeout: 30000,
        headers: { 'Content-Type': 'application/json' }
      });

      console.log("✅ ML API responded:", response.data);

      // Step 4: Run compare_controls.py to get GPT-based risk level
      const compareScript = path.join(__dirname, "..", "py", "compare_controls.py");
      exec(`python "${compareScript}"`, (gptErr, gptOut, gptStderr) => {
        if (gptErr) {
          console.error("⚠️ GPT risk fetch failed:", gptErr.message);
          console.error("GPT Stderr:", gptStderr);
          return res.status(200).json({ 
            system_risk: "Unknown", 
            ...response.data, 
            gpt_error: "GPT risk level unavailable" 
          });
        }

        console.log("📥 GPT Script Output:", gptOut);

        let systemRisk = "Unknown";
        try {
          // Extract JSON from the output (handle extra text before JSON)
          const jsonMatch = gptOut.match(/\{[\s\S]*\}/);
          if (jsonMatch) {
            const jsonStr = jsonMatch[0];
            const parsed = JSON.parse(jsonStr);
            systemRisk = parsed.system_risk;
          } else {
            console.warn("⚠️ No JSON found in GPT output");
            console.warn("Raw output:", gptOut);
          }
        } catch (parseError) {
          console.warn("⚠️ Could not parse GPT risk level:", parseError.message);
          console.warn("Raw output:", gptOut);
        }

        // Final combined response
        res.json({
          system_risk: systemRisk,
          ml_risk: response.data.ml_risk,
          score: response.data.final_score,
          mismatches: response.data.mismatches
        });
      });

    } catch (mlErr) {
      console.error("❌ ML API failed:");
      if (mlErr.response) {
        console.error("Status:", mlErr.response.status);
        console.error("Data:", mlErr.response.data);
      } else if (mlErr.code === 'ECONNREFUSED') {
        console.error("ML API server is not running on port 7000");
      } else {
        console.error("Message:", mlErr.message);
      }

      return res.status(500).json({ 
        error: "ML evaluation failed", 
        detail: mlErr.response?.data?.detail || mlErr.message || "ML API connection failed"
      });
    }
  });
});

module.exports = router;