import os
import io
import uuid
import tempfile
from flask import Flask, render_template, request, redirect, url_for, flash
from flask_sqlalchemy import SQLAlchemy
from flask_mail import Mail, Message
from flask_login import LoginManager, UserMixin, login_user, login_required, logout_user
from datetime import datetime
from PIL import Image
from supabase import create_client
from supabase_client import supabase
from dotenv import load_dotenv

load_dotenv()

app = Flask(__name__)
app.config['SECRET_KEY'] = 'secret-key'
app.config['SQLALCHEMY_DATABASE_URI'] = 'postgresql://garage_db_5m16_user:kD7zwmDloBuB9k55HXFjPWs2pW2Ojthy@dpg-d0mfkpemcj7s7399aihg-a/garage_db_5m16'
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

# Uncomment to create DB first time
#with app.app_context():
#   db.create_all()

@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))

@app.route('/')
def index():
    items = Item.query.order_by(Item.id.desc()).all()
    dibs_map = {d.item_id: True for d in Dibs.query.all()}

    # ✅ For each item, generate fresh signed URLs
    for item in items:
        paths = item.image_filenames.split(',') if item.image_filenames else []
        item.signed_image_urls = [get_signed_url(p) for p in paths]

    return render_template('index.html', items=items, dibs_map=dibs_map)

@app.route('/item/<int:item_id>')
def item_detail(item_id):
    item = Item.query.get_or_404(item_id)
    paths = item.image_filenames.split(',') if item.image_filenames else []
    item.signed_image_urls = [get_signed_url(p) for p in paths]

    return render_template('item_detail.html', item=item)


@app.route('/delete/<int:item_id>')
@login_required
def delete_item(item_id):
    item = Item.query.get_or_404(item_id)

    # Optionally, delete associated image files (uncomment if needed)
    # if item.image_filenames:
    #     for filename in item.image_filenames.split(','):
    #         filepath = os.path.join(app.config['UPLOAD_FOLDER'], filename)
    #         if os.path.exists(filepath):
    #             os.remove(filepath)

    db.session.delete(item)
    db.session.commit()
    flash("Item deleted.", "success")
    return redirect(url_for('admin'))


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

def compress_image(file_storage, max_width=1024, quality=75):
    image = Image.open(file_storage)
    image = image.convert('RGB')  # to handle PNGs or other modes

    # Resize if it's too wide
    if image.width > max_width:
        height = int(max_width * image.height / image.width)
        image = image.resize((max_width, height))

    # Save to a BytesIO buffer
    buffer = io.BytesIO()
    image.save(buffer, format='JPEG', optimize=True, quality=quality)
    buffer.seek(0)

    return buffer

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
            compressed = compress_image(f)
            fname = secure_filename(f.filename).rsplit('.', 1)[0] + '.jpg'
            url = upload_to_supabase(compressed, fname)
            if url:
                filenames.append(url)

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


@app.route('/edit/<int:item_id>', methods=['GET', 'POST'])
@login_required
def edit_item(item_id):
    item = Item.query.get_or_404(item_id)
    existing_images = item.image_filenames.split(',') if item.image_filenames else []

    if request.method == 'POST':
        item.name = request.form.get('name')
        item.description = request.form.get('description')
        item.price = float(request.form.get('price')) if request.form.get('price') else None
        item.status = request.form.get('status')

        # Handle image deletion
        delete_images = request.form.getlist('delete_images')
        item.image_filenames = ','.join([img for img in existing_images if img not in delete_images])
        existing_images = item.image_filenames.split(',') if item.image_filenames else []

        # Handle new image uploads
        new_images = request.files.getlist('images')
        for image in new_images:
            if image and image.filename:
                compressed = compress_image(image)
                fname = secure_filename(image.filename).rsplit('.', 1)[0] + '.jpg'
                url = upload_to_supabase(compressed, fname)
                if url:
                    existing_images.append(url)

        item.image_filenames = ','.join(existing_images)

        db.session.commit()
        flash('Item updated successfully!', 'success')
        return redirect(url_for('admin'))

    # ✅ Generate signed_image_urls for display in template
    signed_image_urls = [get_signed_url(p) for p in existing_images]

    return render_template('edit_item.html', item=item, existing_images=existing_images, signed_image_urls=signed_image_urls)

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

    # GET request - load items
    items = Item.query.order_by(Item.id.desc()).all()
    dibs_list = Dibs.query.order_by(Dibs.timestamp.desc()).all()

    # Build dictionary for faster access in Jinja2
    dibs_by_item = {}
    for dib in dibs_list:
        dibs_by_item.setdefault(dib.item_id, []).append(dib)

    # ✅ Add signed_image_urls to each item
    for item in items:
        paths = item.image_filenames.split(',') if item.image_filenames else []
        item.signed_image_urls = [get_signed_url(p) for p in paths]

    return render_template('admin.html', items=items, dibs_list=dibs_list, dibs_by_item=dibs_by_item)

SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_SECRET_KEY = os.getenv("SUPABASE_SECRET_KEY")

supabase = create_client(SUPABASE_URL, SUPABASE_SECRET_KEY)


def upload_to_supabase(file_obj, filename, bucket="images"):
    unique_name = f"{uuid.uuid4().hex}_{filename}"
    file_path = f"uploads/{unique_name}"

    try:
        # Write buffer to temp file
        with tempfile.NamedTemporaryFile(delete=False, suffix=".jpg") as tmp:
            tmp.write(file_obj.read())
            tmp.flush()
            tmp_path = tmp.name

        # Upload temp file by path
        supabase.storage.from_(bucket).upload(
            path=file_path,
            file=tmp_path,
            file_options={"content-type": "image/jpeg", "x-upsert": "true"}
        )

        # CHANGE: ✅ Just return path, do not create signed URL here anymore
        return file_path

    except Exception as e:
        print("Supabase upload error:", e)
        return None
def get_signed_url(path):
    if not path:
        return ""
    try:
        response = supabase.storage.from_("images").create_signed_url(path, 3600)
        signed_url = response.get("signedURL") or response.get("signedUrl")
        if signed_url:
            return signed_url
        else:
            print("Error generating signed URL:", response)
            return ""
    except Exception as e:
        print("Exception in get_signed_url:", e)
        return ""
