// index.js
const express = require("express");
const bodyParser = require("body-parser");
const cors = require("cors");

const auditRoutes = require("./routes/auditRoutes");

const app = express();
const PORT = 5000;

app.use(cors());
app.use(bodyParser.json());

// Mount the route
app.use("/api/audit", auditRoutes);

app.listen(PORT, () => {
  console.log(`🚀 Server running at http://localhost:${PORT}`);
});
