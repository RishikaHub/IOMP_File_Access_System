const mongoose = require("mongoose");
mongoose.set("debug", true);
mongoose.Promise = Promise;

const MONGODB_URI = process.env.MONGODB_URI || "mongodb+srv://lokig090807:sSSPe1m93Tzb0bk4@facerecog.hal6m.mongodb.net/";

mongoose.connection.on('error', (err) => {
    console.error('MongoDB connection error:', err);
});

mongoose.connection.on('disconnected', () => {
    console.log('MongoDB disconnected');
});

mongoose.connection.on('connected', () => {
    console.log('MongoDB connected successfully');
});

// Handle process termination
process.on('SIGINT', async () => {
    try {
        await mongoose.connection.close();
        console.log('MongoDB connection closed through app termination');
        process.exit(0);
    } catch (err) {
        console.error('Error closing MongoDB connection:', err);
        process.exit(1);
    }
});

const connectDB = async () => {
    try {
        await mongoose.connect(MONGODB_URI, {
            keepAlive: true,
            useNewUrlParser: true,
            useUnifiedTopology: true
        });
    } catch (err) {
        console.error('Initial MongoDB connection error:', err);
        process.exit(1);
    }
};

// Initialize connection
connectDB();

module.exports.User = require("./user");
module.exports.File = require("./file");