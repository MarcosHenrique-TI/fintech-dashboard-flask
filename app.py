import os
from flask import Flask, flash, render_template, request, redirect, url_for, session
from werkzeug.security import generate_password_hash, check_password_hash
import psycopg2
from psycopg2.extras import RealDictCursor
from dotenv import load_dotenv

load_dotenv()
app  = Flask(__name__)
app.secret_key = os.getenv("SECRET_KEY", "your_secret_key_here")

def get_db_connection():
    print("--- A TESTAR VARIÁVEIS DO .ENV ---")
    print("DB_HOST:", os.getenv("DB_HOST"))
    print("DB_NAME:", os.getenv("DB_NAME"))
    print("DB_USER:", os.getenv("DB_USER"))
    print("DB_PASSWORD:", repr(os.getenv("DB_PASSWORD"))) # Usa o repr para ver se tem espaços ou se é None
    print("-----------------------------------")

    conn = psycopg2.connect(
        host=os.getenv("DB_HOST"),
        database=os.getenv("DB_NAME"),
        user=os.getenv("DB_USER"),
        password=os.getenv("DB_PASSWORD"),
        cursor_factory=RealDictCursor
    )
    return conn

@app.route('/')
def index():
    if 'user_id' in session:
        return redirect(url_for('dashboard'))
    return render_template('login.html')

@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        email = request.form['email']
        password = request.form['password']

        hashed_password = generate_password_hash(password)

        try:
            conn = get_db_connection()
            cur = conn.cursor()

            # Verificação da existência do email
            cur.execute("SELECT * FROM users WHERE email = %s", (email,))
            if cur.fetchone():
                flash("Email already registered. Please use a different email.", "error")
                return redirect(url_for('register'))

            cur.execute(
                "INSERT INTO users (email, password) VALUES (%s, %s) RETURNING id",
                (email, hashed_password)
            )
            conn.commit()
            cur.close()
            conn.close()

            flash("Registration successful! Please log in.", "success")
            return redirect(url_for('login'))
        except Exception as e:
            flash(f"An error occurred: {str(e)}", "error")
            return redirect(url_for('register'))
    return render_template('register.html')

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        email = request.form['email']
        password = request.form['password']

        try:
            conn = get_db_connection()
            cur = conn.cursor()

            cur.execute("SELECT * FROM users WHERE email = %s", (email,))
            user = cur.fetchone()

            cur.close()
            conn.close()

            if user and check_password_hash(user['password'], password):
                session['user_id'] = user['id']
                flash("Login successful!", "success")
                return redirect(url_for('dashboard'))
            else:
                flash("Invalid email or password.", "error")
                return redirect(url_for('login'))
        except Exception as e:
            flash(f"An error occurred: {str(e)}", "error")
            return redirect(url_for('login'))

    return render_template('login.html')

@app.route('/dashboard')
def dashboard():
    if 'user_id' not in session:
        flash("Please log in to access the dashboard.", "error")
        return redirect(url_for('login'))
    return render_template('dashboard.html')

@app.route('/logout')
def logout():
    session.pop('user_id', None)
    flash("You have been logged out.", "success")
    return redirect(url_for('login'))

if __name__ == '__main__':
    app.run(debug=True)
