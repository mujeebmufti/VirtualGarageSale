from flask import Flask, render_template, request, redirect, url_for, flash
from flask_sqlalchemy import SQLAlchemy
from flask_mail import Mail, Message
from flask_login import LoginManager, UserMixin, login_user, login_required, logout_user
from datetime import datetime
import os

app = Flask(__name__)
app.config['SECRET_KEY'] = 'secret-key'
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///garage.db'
app.config['UPLOAD_FOLDER'] = 'static/images'
app.config['MAIL_SERVER'] = 'smtp.gmail.com'
app.config['MAIL_PORT'] = 587
app.config['MAIL_USE_TLS'] = True
app.config['MAIL_USERNAME'] = 'mujeebmufti@gmail.com'
app.config['MAIL_PASSWORD'] = 'cjec rqzj vbgp exre'
app.config['MAIL_DEFAULT_SENDER'] = ('Virtual Garage Sale', 'mujeebmufti@gmail.com')

db = SQLAlchemy(app)
mail = Mail(app)
login_manager = LoginManager()
login_manager.init_app(app)

class User(UserMixin, db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True)
    password = db.Column(db.String(120))

class Item(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100))
    description = db.Column(db.Text)
    price = db.Column(db.Float)
    status = db.Column(db.String(20), default='available')
    image_filenames = db.Column(db.Text)
    thumbnail_index = db.Column(db.Integer, default=0)

class Dibs(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    item_id = db.Column(db.Integer, db.ForeignKey('item.id'))
    name = db.Column(db.String(100))
    email = db.Column(db.String(100))
    price = db.Column(db.Float)
    timestamp = db.Column(db.DateTime, default=datetime.utcnow)

@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))

@app.route('/')
def index():
    items = Item.query.order_by(Item.id.desc()).all()
    dibs_map = {d.item_id: True for d in Dibs.query.all()}
    return render_template('index.html', items=items, dibs_map=dibs_map)

@app.route('/item/<int:item_id>')
def item_detail(item_id):
    item = Item.query.get_or_404(item_id)
    images = item.image_filenames.split(',') if item.image_filenames else []
    return render_template('item_detail.html', item=item, images=images)

@app.route('/reserve/<int:item_id>', methods=['POST'])
def reserve(item_id):
    item = Item.query.get_or_404(item_id)
    name = request.form['name']
    email = request.form['email']
    phone = request.form['phone']
    offer_price = request.form.get('first_dibs')

    if offer_price:
        try:
            offer_price = float(offer_price)
        except ValueError:
            offer_price = None

    if offer_price:
        dib = Dibs(item_id=item.id, name=name, email=email, price=offer_price)
        db.session.add(dib)
        db.session.commit()
        msg_body = f"{name} has entered dibs for {item.name} at CAD ${offer_price}.\nPhone: {phone}\nEmail: {email}"
        msg = Message(subject=f"{name} is interested in {item.name}",
                      recipients=["mujeebmufti@gmail.com", "anam.habib90@gmail.com"],
                      cc=[email],
                      body=msg_body)
        mail.send(msg)
    else:
        msg_body = f"{name} has reserved {item.name}.\nPhone: {phone}\nEmail: {email}"
        msg = Message(subject=f"{name} is interested in {item.name}",
                      recipients=["mujeebmufti@gmail.com", "anam.habib90@gmail.com"],
                      cc=[email],
                      body=msg_body)
        try:
            mail.send(msg)
            item.status = 'reserved'
            db.session.commit()
        except Exception:
            flash('Email sending failed. Item not reserved.', 'danger')
            return redirect(url_for('index'))

    flash('Your interest has been recorded!', 'success')
    return redirect(url_for('index'))

from werkzeug.utils import secure_filename  # add to imports (top)

@app.route('/add', methods=['POST'])
@login_required
def add_item():
    name        = request.form['name']
    price       = float(request.form['price'])
    description = request.form['description']
    files       = request.files.getlist('images')

    filenames = []
    for f in files:
        if f and f.filename:
            fname = secure_filename(f.filename)
            save_path = os.path.join(app.config['UPLOAD_FOLDER'], fname)
            f.save(save_path)
            filenames.append(fname)

    item = Item(name=name,
                price=price,
                description=description,
                image_filenames=','.join(filenames),
                thumbnail_index=0)
    db.session.add(item)
    db.session.commit()
    flash('New item added!', 'success')
    return redirect(url_for('admin'))

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        if request.form['password'] == 'kaboocha10':
            user = User.query.first()
            if not user:
                user = User(username='admin', password='password')
                db.session.add(user)
                db.session.commit()
            login_user(user)
            return redirect(url_for('admin'))
        else:
            flash('Incorrect password', 'danger')
    return render_template('login.html')

@app.route('/logout')
@login_required
def logout():
    logout_user()
    return redirect(url_for('index'))

@app.route('/admin', methods=['GET', 'POST'])
@login_required
def admin():
    if request.method == 'POST':
        item_id = int(request.form['item_id'])
        item = Item.query.get_or_404(item_id)
        item.status = request.form['status']
        try:
            item.thumbnail_index = int(request.form.get('thumbnail_index') or 0)
        except ValueError:
            item.thumbnail_index = 0
        db.session.commit()
        flash('Item updated.', 'success')
        return redirect(url_for('admin'))

    items = Item.query.order_by(Item.id.desc()).all()
    dibs_list = Dibs.query.order_by(Dibs.timestamp.desc()).all()

    # Build dictionary for faster access in Jinja2
    dibs_by_item = {}
    for dib in dibs_list:
        dibs_by_item.setdefault(dib.item_id, []).append(dib)

    return render_template('admin.html', items=items, dibs_list=dibs_list, dibs_by_item=dibs_by_item)


if __name__ == '__main__':
    with app.app_context():
        db.create_all()
    app.run(debug=True)


@app.route('/create-admin')
def create_admin():
    from werkzeug.security import generate_password_hash
    user = User(username='admin', password='admin123')
    db.session.add(user)
    db.session.commit()
    return "Admin user created: admin / admin123"
