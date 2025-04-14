const express = require('express');
const admin = require('firebase-admin');
const http = require('http');
const { Server } = require('socket.io');
const path = require('path');

// Initialize the Express app and HTTP server
const app = express();
const server = http.createServer(app);
const io = new Server(server);

// Firebase Admin SDK initialization
const serviceAccount = require('./serviceAccountKey.json'); // Your Firebase credentials
admin.initializeApp({
  credential: admin.credential.cert(serviceAccount),
  databaseURL: 'https://agri-firebase-d2c85-default-rtdb.europe-west1.firebasedatabase.app/' // Your Firebase database URL
});

// Add after database initialization
const db = admin.database();
db.ref().once('value')
  .then((snapshot) => {
    console.log('Firebase connection successful');
    console.log('Initial data:', snapshot.val());
  })
  .catch(error => {
    console.error('Firebase connection failed:', error);
  });

// Serve static files from the "public" directory
app.use(express.static(path.join(__dirname, 'public')));

// Firebase database reference
const ref = db.ref('NPK'); // This path should match your Firebase database structure

// Serve the HTML file
app.get('/', (req, res) => {
  res.sendFile(path.join(__dirname, 'index.html'));
});

// Handle WebSocket connections
io.on('connection', (socket) => {
  console.log('Client connected.');

  // Send the latest data to a newly connected client
  ref.once('value', (snapshot) => {
    const data = snapshot.val();
    if (data) {
      socket.emit('dataUpdate', data); // Emit the data to the connected client
    }
  });

  // In browser console
  socket.connected // Should return true

  socket.on('dataUpdate', (data) => {
    console.log('Raw data:', data);
    console.log('Nitrogen:', data.nitrogen);
    console.log('Phosphorus:', data.phosphorus);
    console.log('Potassium:', data.potassium);
    // ... rest of the code
  });

  // Handle client disconnect
  socket.on('disconnect', () => {
    console.log('Client disconnected.');
  });
});

// Listen for changes in Firebase Realtime Database
ref.on('value', (snapshot) => {
  const data = snapshot.val();
  if (data) {
    console.log('Firebase data received:', data);
    io.emit('dataUpdate', data);
  } else {
    console.log('No data available in Firebase');
  }
});

// Start the server
const PORT = process.env.PORT || 3000;
server.listen(PORT, () => {
  console.log(`Server is running on http://localhost:${PORT}`);
});
