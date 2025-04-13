const express = require('express');
const router = express.Router();
const jwt = require('jsonwebtoken');
const db = require('../models');

router.post('/signup', async (req, res, next) => {
    try {
        if (!req.body.email || !req.body.password) {
            return res.status(400).json({
                status: "error",
                message: "Email and password are required"
            });
        }

        if (!process.env.JWT_SECRET_KEY) {
            console.error('JWT_SECRET_KEY not configured');
            return res.status(500).json({
                status: "error",
                message: "Server configuration error"
            });
        }

        // Create user
        const user = await db.User.create({
            email: req.body.email,
            password: req.body.password
        });

        // Generate token
        const token = jwt.sign(
            { id: user.id, email: user.email },
            process.env.JWT_SECRET_KEY,
            { expiresIn: '1d' }
        );

        return res.status(200).json({
            status: "success",
            token,
            email: user.email,
            message: "User created successfully"
        });
    } catch (err) {
        console.error('Signup error:', err);
        if (err.code === 11000) {
            return res.status(400).json({
                status: "error",
                message: "Email already taken"
            });
        }
        if (err.name === 'ValidationError') {
            return res.status(400).json({
                status: "error",
                message: "Invalid input data"
            });
        }
        return res.status(500).json({
            status: "error",
            message: "Error creating user"
        });
    }
});

router.post('/login', async (req, res, next) => {
    try {
        const user = await db.User.findOne({ email: req.body.email });
        if (!user) {
            return next({
                status: 400,
                message: "Invalid Email/Password"
            });
        }
        
        const isMatch = await user.comparePassword(req.body.password);
        if (isMatch) {
            // Update last login
            user.lastLogin = new Date();
            await user.save();

            const token = jwt.sign(
                { 
                    id: user.id, 
                    email: user.email,
                    lastLogin: user.lastLogin 
                },
                process.env.JWT_SECRET_KEY,
                { expiresIn: '1d' }
            );
            
            return res.status(200).json({
                status: "success",
                token,
                email: user.email,
                message: "Logged in successfully"
            });
        } else {
            return next({
                status: 400,
                message: "Invalid Email/Password"
            });
        }
    } catch (err) {
        return next(err);
    }
});

router.post('/verify-token', async (req, res, next) => {
    try {
        const token = req.headers.authorization.split(' ')[1];
        const decoded = jwt.verify(token, process.env.JWT_SECRET_KEY);
        const user = await db.User.findById(decoded.id);
        
        if (!user) {
            return res.status(401).json({
                status: "error",
                message: "User not found"
            });
        }

        return res.json({
            status: "success",
            user: {
                email: user.email,
                id: user.id,
                lastLogin: user.lastLogin
            }
        });
    } catch (err) {
        return res.status(401).json({
            status: "error",
            message: "Invalid token"
        });
    }
});

router.post('/logout', (req, res) => {
    // Since we're using JWT, we just send a success response
    // The client should remove the token
    res.json({
        status: "success",
        message: "Logged out successfully"
    });
});

module.exports = router;