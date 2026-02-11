import os
import psycopg2
from flask import Flask, render_template, request, redirect, session, url_for, flash
from werkzeug.security import generate_password_hash, check_password_hash
import feedparser
from threading import Thread
import time

app = Flask(__name__)
# Секретний ключ для сесій (обов'язково для безпеки)
app.secret_key = 'super_secret_key_change_me'

DB_URL = os.environ.get('DATABASE_URL')

def get_db_connection():
    return psycopg2.connect(DB_URL)

def init_db():
    """Створює таблиці новин та користувачів"""
    conn = get_db_connection()
    cur = conn.cursor()
    
    # Таблиця новин
    cur.execute('''
        CREATE TABLE IF NOT EXISTS news (
            id SERIAL PRIMARY KEY,
            title TEXT NOT NULL,
            link TEXT UNIQUE NOT NULL,
            source TEXT NOT NULL,
            published TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );
    ''')
    
    # Таблиця користувачів (Вимога Тижня 4)
    cur.execute('''
        CREATE TABLE IF NOT EXISTS users (
            id SERIAL PRIMARY KEY,
            username TEXT UNIQUE NOT NULL,
            password TEXT NOT NULL
        );
    ''')
    
    conn.commit()
    cur.close()
    conn.close()

# --- ПАРСЕР (залишається без змін) ---
def parse_news():
    rss_feeds = [
        ('DOU.ua', 'https://dou.ua/feed/'),
        ('TechCrunch', 'https://techcrunch.com/feed/'),
    ]
    while True:
        try:
            conn = get_db_connection()
            cur = conn.cursor()
            for source_name, url in rss_feeds:
                feed = feedparser.parse(url)
                for entry in feed.entries[:3]:
                    try:
                        cur.execute('''
                            INSERT INTO news (title, link, source, published)
                            VALUES (%s, %s, %s, %s)
                            ON CONFLICT (link) DO NOTHING
                        ''', (entry.title, entry.link, source_name, entry.get('published', '')))
                    except:
                        pass
            conn.commit()
            cur.close()
            conn.close()
            print("✅ RSS оновлено")
        except Exception as e:
            print(f"❌ Помилка парсера: {e}")
        time.sleep(3600)

Thread(target=parse_news, daemon=True).start()

# --- ГОЛОВНА СТОРІНКА ---
@app.route('/')
def index():
    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute('SELECT title, source, published, link FROM news ORDER BY id DESC LIMIT 20')
    news_data = cur.fetchall()
    cur.close()
    conn.close()
    
    news_list = [{"title": r[0], "source": r[1], "published": r[2], "link": r[3]} for r in news_data]
    # Передаємо в шаблон інформацію, чи увійшов користувач (session.get('user_id'))
    return render_template('index.html', news=news_list, user=session.get('user_id'))

@app.route('/about')
def about():
    return render_template('about.html')

# --- АВТОРИЗАЦІЯ ТА АДМІНКА (Нове для Тижня 4) ---

@app.route('/register', methods=['GET', 'POST'])
def register():
    """Сторінка реєстрації"""
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        
        # Хешуємо пароль (Безпека!)
        hashed_pw = generate_password_hash(password)
        
        conn = get_db_connection()
        cur = conn.cursor()
        try:
            cur.execute('INSERT INTO users (username, password) VALUES (%s, %s)', (username, hashed_pw))
            conn.commit()
            flash('Реєстрація успішна! Тепер увійдіть.')
            return redirect(url_for('login'))
        except psycopg2.IntegrityError:
            flash('Такий користувач вже існує!')
        finally:
            cur.close()
            conn.close()
            
    return render_template('register.html')

@app.route('/login', methods=['GET', 'POST'])
def login():
    """Сторінка входу"""
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        
        conn = get_db_connection()
        cur = conn.cursor()
        cur.execute('SELECT id, password FROM users WHERE username = %s', (username,))
        user = cur.fetchone()
        cur.close()
        conn.close()
        
        # Перевіряємо хеш пароля
        if user and check_password_hash(user[1], password):
            session['user_id'] = user[0]
            session['username'] = username
            return redirect(url_for('admin'))
        else:
            flash('Невірний логін або пароль')
            
    return render_template('login.html')

@app.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('index'))

@app.route('/admin', methods=['GET', 'POST'])
def admin():
    """Адмін-панель: додавання та видалення новин"""
    if 'user_id' not in session:
        return redirect(url_for('login'))
    
    conn = get_db_connection()
    cur = conn.cursor()
    
    # Додавання новини вручну
    if request.method == 'POST':
        title = request.form['title']
        link = request.form['link']
        source = "Admin (" + session['username'] + ")"
        cur.execute('INSERT INTO news (title, link, source, published) VALUES (%s, %s, %s, NOW())', 
                    (title, link, source))
        conn.commit()
    
    # Отримуємо всі новини для таблиці управління
    cur.execute('SELECT id, title, source FROM news ORDER BY id DESC LIMIT 50')
    news_list = cur.fetchall()
    cur.close()
    conn.close()
    
    return render_template('admin.html', news=news_list, username=session['username'])

@app.route('/delete/<int:id>')
def delete_news(id):
    """Видалення новини"""
    if 'user_id' not in session:
        return redirect(url_for('login'))
        
    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute('DELETE FROM news WHERE id = %s', (id,))
    conn.commit()
    cur.close()
    conn.close()
    return redirect(url_for('admin'))

if __name__ == '__main__':
    time.sleep(5)
    try:
        init_db()
    except Exception as e:
        print(f"DB Error: {e}")
    app.run(debug=True, host='0.0.0.0')