const express = require("express");
const app = express();
const bodyParser = require("body-parser");
const cors = require("cors");
const eventRoutes = require("./routes/events");
const fileRoutes = require("./routes/files");
const session = require("express-session");
const authRoutes = require("./routes/auth");
require('dotenv').config();

const port = process.env.PORT || 8080;

// Initialize MongoDB connection via models/index.js
require('./models');

app.use('/', express.static('public'));
app.set('view engine', 'html');

// Configure middleware
app.use(bodyParser.json());
app.use(cors({
    origin: ['http://localhost:5050', 'http://localhost:8080'],
    credentials: true
}));

app.use(session({
    secret: process.env.SESSION_SECRET || 'your-secret-key-here',
    resave: false,
    saveUninitialized: false,
    cookie: {
        secure: process.env.NODE_ENV === "production",
        httpOnly: true,
        maxAge: 24 * 60 * 60 * 1000
    }
}));

// API Routes
app.use("/api/events", eventRoutes);
app.use("/auth", authRoutes);
app.use("/api/files", fileRoutes);


// Error handling
app.use((req, res, next) => {
    let err = new Error("NOT FOUND");
    err.status = 404;
    next(err);
});

app.listen(port, () => {
    console.log(`Server started on port ${port}`);
});