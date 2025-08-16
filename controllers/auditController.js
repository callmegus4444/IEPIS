const { exec } = require('child_process');
const path = require('path');

exports.runAudit = (req, res) => {
  const scriptPath = path.join(__dirname, '..', 'py', 'compare_controls.py');

  exec(`python "${scriptPath}"`, (error, stdout, stderr) => {
    if (error) {
      console.error(`❌ Error executing script: ${error.message}`);
      return res.status(500).json({ error: 'Failed to run Python script' });
    }

    if (stderr) {
      console.warn(`⚠️ STDERR: ${stderr}`);
    }

    //  Parse stdout into JSON if structured; else return as text
    res.status(200).json({ output: stdout });
  });
};
