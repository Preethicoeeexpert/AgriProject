from flask import Flask, render_template, request, redirect, url_for, flash
from flask_sqlalchemy import SQLAlchemy
from werkzeug.security import generate_password_hash, check_password_hash
import firebase_admin
from firebase_admin import credentials, db
import flask_socketio
import os
import json

app = Flask(__name__)
app.secret_key = 'your_secret_key'
socketio = flask_socketio.SocketIO(app, cors_allowed_origins="*")

# Configure the SQLite database
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///database.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

db_sql = SQLAlchemy(app)

# Initialize Firebase Admin
cred = credentials.Certificate("Graph/serviceAccountKey.json")
firebase_admin.initialize_app(cred, {
    'databaseURL': 'https://agri-firebase-d2c85-default-rtdb.europe-west1.firebasedatabase.app/'
})

# Get Firebase database reference
firebase_db = db.reference('NPK')

class User(db_sql.Model):
    id = db_sql.Column(db_sql.Integer, primary_key=True)
    username = db_sql.Column(db_sql.String(100), unique=True, nullable=False)
    password = db_sql.Column(db_sql.String(100), nullable=False)

with app.app_context():
    db_sql.create_all()

@app.route('/')
def home():
    return render_template('home.html')

@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        re_password = request.form['re_password']

        if password != re_password:
            flash("Passwords do not match!", 'error')
            return redirect(url_for('register'))

        user = User.query.filter_by(username=username).first()
        if user:
            flash("Username already exists.", 'error')
            return redirect(url_for('register'))

        hashed_password = generate_password_hash(password, method='pbkdf2:sha256', salt_length=16)
        new_user = User(username=username, password=hashed_password)
        db_sql.session.add(new_user)
        db_sql.session.commit()

        flash("Registration successful! Please log in.", 'success')
        return redirect(url_for('login'))

    return render_template('register.html')

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']

        user = User.query.filter_by(username=username).first()
        if user and check_password_hash(user.password, password):
            flash("Login successful!", 'success')
            return redirect(url_for('dashboard'))
        else:
            flash("Invalid credentials. Please try again.", 'error')
            return redirect(url_for('login'))

    return render_template('login.html')

@app.route('/dashboard')
def dashboard():
    return render_template('dashboard.html')

# Socket.IO event handlers
@socketio.on('connect')
def handle_connect():
    print('Client connected')
    # Send initial data
    data = firebase_db.get()
    if data:
        print('Sending initial NPK data:', data)
        socketio.emit('dataUpdate', data)

@socketio.on('disconnect')
def handle_disconnect():
    print('Client disconnected')

def combine_npk_data(current_data, new_data, path=None):
    """Combine existing NPK data with new updates"""
    if isinstance(new_data, dict):
        return {**current_data, **new_data}
    elif path:
        current_data[path] = new_data
        return current_data
    return current_data

# Keep track of latest NPK values
current_npk_data = {'nitrogen': 0, 'phosphorus': 0, 'potassium': 0}

# Firebase data change listener
def firebase_stream_handler(event):
    """Handle Firebase real-time updates"""
    global current_npk_data
    
    try:
        if event.data is not None:
            print('Raw event data:', event.data)
            print('Event path:', event.path)
            
            # Handle different data update scenarios
            if isinstance(event.data, dict):
                current_npk_data.update(event.data)
            elif event.path:
                # Remove leading slash and get path
                path = event.path[1:] if event.path.startswith('/') else event.path
                if path in ['nitrogen', 'phosphorus', 'potassium']:
                    current_npk_data[path] = float(event.data)
            
            print('Updated NPK data:', current_npk_data)
            
            # Ensure all values are numbers and properly formatted
            sanitized_data = {}
            for k, v in current_npk_data.items():
                try:
                    sanitized_data[k] = float(v)
                except (ValueError, TypeError):
                    sanitized_data[k] = 0.0
            
            print('Emitting data:', sanitized_data)
            socketio.emit('dataUpdate', sanitized_data)
            
    except Exception as e:
        print('Error in firebase_stream_handler:', str(e))

# Start Firebase listener
firebase_db.listen(firebase_stream_handler)

if __name__ == '__main__':
    socketio.run(app, debug=True, port=3000)
