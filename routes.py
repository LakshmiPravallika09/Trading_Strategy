from flask import Flask, request, jsonify, render_template, redirect, url_for
from flask_login import login_user, logout_user, current_user, login_required
from werkzeug.security import generate_password_hash, check_password_hash
from pycoingecko import CoinGeckoAPI
from app import app, db, login_manager
from models import User, Order

cg = CoinGeckoAPI()

@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))

# Function to get current price from CoinGecko API
def get_current_price(token):
    token_mapping = {'BTC': 'bitcoin', 'ETH': 'ethereum'}
    if token not in token_mapping:
        return None
    price_data = cg.get_price(ids=token_mapping[token], vs_currencies='usd')
    return price_data[token_mapping[token]]['usd']

# Function to check buy conditions
def check_buy_conditions(token, price):
    buy_tokens = {'BTC': 30000, 'ETH': 2000}
    return price < buy_tokens[token]

# Function to check sell conditions
def check_sell_conditions(token, price):
    sell_tokens = {'BTC': 1.05, 'ETH': 1.05}
    buy_tokens = {'BTC': 30000, 'ETH': 2000}
    return price > buy_tokens[token] * sell_tokens[token]

@app.route('/')
@login_required
def index():
    return render_template('index.html', username=current_user.username, balance=current_user.balance)

@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        balance = float(request.form['balance'])

        if User.query.filter_by(username=username).first():
            return jsonify({'error': 'Username already exists'}), 400

        hashed_password = generate_password_hash(password, method='sha256')
        user = User(username=username, password_hash=hashed_password, balance=balance)
        db.session.add(user)
        db.session.commit()

        return redirect(url_for('login'))
    return render_template('register.html')

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        user = User.query.filter_by(username=username).first()
        if user and check_password_hash(user.password_hash, password):
            login_user(user)
            return redirect(url_for('index'))
        return jsonify({'error': 'Invalid credentials'}), 401
    return render_template('login.html')

@app.route('/logout')
@login_required
def logout():
    logout_user()
    return redirect(url_for('login'))

@app.route('/order', methods=['POST'])
@login_required
def handle_order():
    data = request.json
    token = data['token']
    amount = data['amount']
    order_type = data['order_type']

    current_price = get_current_price(token)
    if order_type == 'buy':
        if check_buy_conditions(token, current_price):
            current_user.balance -= amount * current_price
            db.session.add(Order(user_id=current_user.id, token=token, amount=amount, order_type='buy'))
            db.session.commit()
            return jsonify({'message': 'Buy order executed'}), 200
        else:
            return jsonify({'message': 'Buy conditions not met'}), 400
    elif order_type == 'sell':
        if check_sell_conditions(token, current_price):
            current_user.balance += amount * current_price
            db.session.add(Order(user_id=current_user.id, token=token, amount=amount, order_type='sell'))
            db.session.commit()
            return jsonify({'message': 'Sell order executed'}), 200
        else:
            return jsonify({'message': 'Sell conditions not met'}), 400
    else:
        return jsonify({'message': 'Invalid order type'}), 400

@app.route('/orders', methods=['GET'])
@login_required
def view_orders():
    orders = Order.query.filter_by(user_id=current_user.id).all()
    orders_list = [{'id': order.id, 'token': order.token, 'amount': order.amount, 'order_type': order.order_type} for order in orders]
    return jsonify(orders_list)
