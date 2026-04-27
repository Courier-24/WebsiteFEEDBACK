import sqlite3
from flask import Flask, render_template, url_for, request, redirect, session
from werkzeug.security import generate_password_hash, check_password_hash
import random
import string

app = Flask(__name__)
app.secret_key='supersecret'

wsgi_app = app.wsgi_app

def databaseConnection():
    conn = sqlite3.connect('database.db')
    conn.row_factory = sqlite3.Row 
    return conn

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/login', methods=['GET','POST'])
def login():
    if request.method == 'POST':
        email = request.form.get('email')
        password = request.form.get('password')
        conn = databaseConnection()
        user = conn.execute('SELECT * FROM users WHERE email = ?', (email,)).fetchone()
        conn.close()
        if user and check_password_hash(user['password'], password):
            session['user_email'] = user['email']
            session['user_type'] = user['usertype']
            return redirect(url_for('index')) 
        else:
            return "Wrong email or password."        
    return render_template('login.html')

@app.route('/signin', methods=['GET','POST'])
def signin():
    if request.method == 'POST':
        email = request.form.get('email')
        password = request.form.get('password')
        usertype = request.form.get('usertype')
        hashedPass = generate_password_hash(password)
        try:
            conn = databaseConnection()
            conn.execute('INSERT INTO users (email, password, usertype) VALUES (?, ?, ?)', 
                         (email, hashedPass, usertype))
            if usertype == 'producer':
                conn.execute('INSERT INTO stores (producer_email) VALUES (?)', (email,))
            conn.commit()
            conn.close()
            return redirect(url_for('login'))
        except sqlite3.IntegrityError:
            return "Email already exists."
    return render_template('signin.html')


@app.route('/logout')
def logout():
    session.pop('user_email', None) 
    return redirect(url_for('index'))

@app.route('/legal')
def legal():
    return render_template('legal.html')

@app.route('/account')
def account():
    if 'user_email' not in session:
        return redirect(url_for('login'))
    return render_template('account.html')

@app.route('/orders')
def orders():
    if 'user_email' not in session:
        return redirect(url_for('login'))
    conn = databaseConnection()
    user_orders = conn.execute('SELECT * FROM orders WHERE customer_email = ?', (session['user_email'],)).fetchall()
    conn.close()
    return render_template('orders.html', orders=user_orders)

@app.route('/cancel_order/<int:order_id>', methods=['POST'])
def cancel_order(order_id):
    if 'user_email' not in session:
        return redirect(url_for('login'))
    conn = databaseConnection()
    conn.execute('DELETE FROM orders WHERE id = ? AND customer_email = ?', (order_id, session['user_email']))
    conn.commit()
    conn.close()
    return redirect(url_for('orders'))

@app.route('/editstore', methods=['GET', 'POST'])
def editstore():
    if 'user_email' not in session or session.get('user_type') != 'producer':
        return redirect(url_for('login')) 
    email = session['user_email']
    conn = databaseConnection()    
    if request.method == 'POST':
        form_type = request.form.get('form_type')       
        if form_type == 'update_store':
            new_name = request.form.get('store_name')
            new_desc = request.form.get('description')
            conn.execute('UPDATE stores SET store_name = ?, description = ? WHERE producer_email = ?',
                         (new_name, new_desc, email))                         
        elif form_type == 'add_product':
            name = request.form.get('name')
            price = request.form.get('price')
            stock = request.form.get('stock')
            conn.execute('INSERT INTO products (producer_email, name, price, stock) VALUES (?, ?, ?, ?)',
                         (email, name, price, stock))                         
        elif form_type == 'edit_product':
            p_id = request.form.get('product_id')
            p_name = request.form.get('name')
            p_price = request.form.get('price')
            p_stock = request.form.get('stock')
            conn.execute('UPDATE products SET name = ?, price = ?, stock = ? WHERE id = ? AND producer_email = ?',
                         (p_name, p_price, p_stock, p_id, email))            
        elif form_type == 'delete_product':
            p_id = request.form.get('product_id')
            conn.execute('DELETE FROM products WHERE id = ? AND producer_email = ?', (p_id, email))
        conn.commit()
        conn.close() 
        return redirect(url_for('editstore'))
    store = conn.execute('SELECT * FROM stores WHERE producer_email = ?', (email,)).fetchone()
    products = conn.execute('SELECT * FROM products WHERE producer_email = ?', (email,)).fetchall()
    conn.close()
    return render_template('editstore.html', store=store, products=products)

@app.route('/storelist')
def storelist():
    conn = databaseConnection()
    stores = conn.execute('SELECT * FROM stores').fetchall()
    conn.close()
    return render_template('storelist.html', stores=stores)

@app.route('/store/<int:store_id>', methods=['GET', 'POST'])
def storepage(store_id):
    conn = databaseConnection()
    store = conn.execute('SELECT * FROM stores WHERE id = ?', (store_id,)).fetchone()
    if request.method == 'POST':
        if 'user_email' not in session:
            return redirect(url_for('login'))    
        p_name = request.form.get('product_name')
        p_price = request.form.get('product_price')
        o_type = request.form.get('order_type')
        conn.execute('''UPDATE products SET stock = stock - 1 
                     WHERE name = ? AND producer_email = ? AND stock > 0''', 
                     (p_name, store['producer_email']))
        tracker = "GF-" + ''.join(random.choices(string.digits, k=5))
        conn.execute('''INSERT INTO orders 
                     (customer_email, producer_email, product_name, price, order_type, tracking_code) 
                     VALUES (?, ?, ?, ?, ?, ?)''',
                     (session['user_email'], store['producer_email'], p_name, p_price, o_type, tracker))
        conn.commit()
        conn.close() 
        return redirect(url_for('orders'))
    products = conn.execute('SELECT * FROM products WHERE producer_email = ?', (store['producer_email'],)).fetchall()
    conn.close() 
    return render_template('storepage.html', store=store, products=products)

@app.route('/pagesettings')
def pagesettings():
    return render_template('pagesettings.html')

if __name__ == '__main__':
    import os
    db_path = os.path.join(os.path.dirname(__file__), 'database.db')
    conn = sqlite3.connect(db_path)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            email TEXT NOT NULL UNIQUE,
            password TEXT NOT NULL,
            usertype TEXT NOT NULL
        )
    """)

    conn.execute("""
        CREATE TABLE IF NOT EXISTS stores (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            producer_email TEXT NOT NULL UNIQUE,
            store_name TEXT DEFAULT 'STORE',
            description TEXT DEFAULT 'DESCRIPTION',
            FOREIGN KEY (producer_email) REFERENCES users (email)
        )
    """)
      
    conn.execute("""
        CREATE TABLE IF NOT EXISTS products (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            producer_email TEXT NOT NULL,
            name TEXT NOT NULL,
            price REAL NOT NULL,
            stock INTEGER NOT NULL,
            FOREIGN KEY (producer_email) REFERENCES users (email)
        )
    """)

    conn.execute("""
        CREATE TABLE IF NOT EXISTS orders (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            customer_email TEXT NOT NULL,
            producer_email TEXT NOT NULL,
            product_name TEXT NOT NULL,
            price REAL NOT NULL,
            order_type TEXT NOT NULL,
            tracking_code TEXT NOT NULL
        )
    """)


    conn.commit()
    conn.close()

if __name__ == '__main__':
    import os
    HOST = os.environ.get('SERVER_HOST', 'localhost')
    try:
        PORT = int(os.environ.get('SERVER_PORT', '5555'))
    except ValueError:
        PORT = 5555
    app.run(HOST, PORT)
