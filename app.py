'''app.py'''
from flask import Flask, render_template, request, redirect, url_for, flash, send_file
from flask_sqlalchemy import SQLAlchemy
from flask_login import UserMixin, LoginManager, login_user, logout_user, current_user, login_required
from functools import wraps
from werkzeug.security import generate_password_hash, check_password_hash
import pandas as pd
import io
from reportlab.lib.pagesizes import letter
from reportlab.platypus import SimpleDocTemplate, Table, Paragraph, Spacer
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.lib import colors

app = Flask(__name__)
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///customers.db'
app.config['SECRET_KEY'] = 'your_secret_key'  # Güvenlik için gerçek bir anahtarla değiştirin
db = SQLAlchemy(app)
login_manager = LoginManager(app)
login_manager.login_view = 'login'

@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))

def admin_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not current_user.is_authenticated or current_user.role != 'admin':
            flash('Bu sayfaya erişim yetkiniz yok.', 'danger')
            return redirect(url_for('index'))
        return f(*args, **kwargs)
    return decorated_function

# Model tanımlamaları buraya gelecek
class User(db.Model, UserMixin):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(20), unique=True, nullable=False)
    password_hash = db.Column(db.String(128), nullable=False)
    role = db.Column(db.String(20), default='user') # 'admin' or 'user'

    def set_password(self, password):
        self.password_hash = generate_password_hash(password)

    def check_password(self, password):
        return check_password_hash(self.password_hash, password)

    def __repr__(self):
        return f'<User {self.username}>'

class Customer(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    phone = db.Column(db.String(20), nullable=False)
    address = db.Column(db.String(200), nullable=False)
    job_type = db.Column(db.String(100), nullable=False)
    date = db.Column(db.String(20), nullable=False)  # Tarih string olarak saklanacak
    status = db.Column(db.String(50), default='Beklemede') # Beklemede, Devam Ediyor, Tamamlandı
    note = db.Column(db.Text, nullable=True)

    def __repr__(self):
        return f'<Customer {self.name}>'



@app.route('/')
def index():
    total_customers = Customer.query.count()
    in_progress_customers = Customer.query.filter_by(status='Devam Ediyor').count()
    completed_customers = Customer.query.filter_by(status='Tamamlandı').count()
    return render_template('index.html', 
                           total_customers=total_customers, 
                           in_progress_customers=in_progress_customers, 
                           completed_customers=completed_customers)

@app.route('/login', methods=['GET', 'POST'])
def login():
    if current_user.is_authenticated:
        return redirect(url_for('index'))

    if request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password')
        user = User.query.filter_by(username=username).first()

        if user and user.check_password(password):
            login_user(user)
            flash('Giriş başarılı!', 'success')
            return redirect(url_for('customer_list')) # Giriş sonrası müşteri listesine yönlendir
        else:
            flash('Geçersiz kullanıcı adı veya parola.', 'danger')

    return render_template('login.html')

@app.route('/logout')
@login_required
def logout():
    logout_user()
    flash('Çıkış yaptınız.', 'info')
    return redirect(url_for('index'))

@app.route('/add_customer', methods=['GET', 'POST'])
@login_required
@admin_required
def add_customer():
    if request.method == 'POST':
        name = request.form.get('name')
        phone = request.form.get('phone')
        address = request.form.get('address')
        job_type = request.form.get('job_type')
        date = request.form.get('date')
        note = request.form.get('note')

        new_customer = Customer(name=name, phone=phone, address=address, job_type=job_type, date=date, note=note)
        db.session.add(new_customer)
        db.session.commit()
        flash('Yeni müşteri başarıyla eklendi!', 'success')
        return redirect(url_for('customer_list')) # Müşteri listesine yönlendir

    return render_template('add_customer.html')

@app.route('/customer_list')
@login_required
def customer_list():
    customers = Customer.query.order_by(Customer.date).all()
    return render_template('customer_list.html', customers=customers)

@app.route('/update_customer_status/<int:customer_id>', methods=['POST'])
@login_required
@admin_required
def update_customer_status(customer_id):
    customer = Customer.query.get_or_404(customer_id)
    new_status = request.form.get('status')
    if new_status in ['Beklemede', 'Devam Ediyor', 'Tamamlandı']:
        customer.status = new_status
        db.session.commit()
        flash('Müşteri durumu başarıyla güncellendi!', 'success')
    else:
        flash('Geçersiz durum seçimi.', 'danger')
    return redirect(url_for('customer_list'))

@app.route('/edit_customer/<int:customer_id>', methods=['GET', 'POST'])
@login_required
@admin_required
def edit_customer(customer_id):
    customer = Customer.query.get_or_404(customer_id)
    if request.method == 'POST':
        customer.name = request.form.get('name')
        customer.phone = request.form.get('phone')
        customer.address = request.form.get('address')
        customer.job_type = request.form.get('job_type')
        customer.date = request.form.get('date')
        customer.note = request.form.get('note')
        db.session.commit()
        flash('Müşteri bilgileri başarıyla güncellendi!', 'success')
        return redirect(url_for('customer_list'))
    return render_template('edit_customer.html', customer=customer)

@app.route('/delete_customer/<int:customer_id>', methods=['POST'])
@login_required
@admin_required
def delete_customer(customer_id):
    customer = Customer.query.get_or_404(customer_id)
    db.session.delete(customer)
    db.session.commit()
    flash('Müşteri başarıyla silindi!', 'success')
    return redirect(url_for('customer_list'))

@app.route('/export/excel')
@login_required
@admin_required
def export_excel():
    customers = Customer.query.all()
    data = [{
        'Ad-Soyad': c.name,
        'Telefon': c.phone,
        'Adres': c.address,
        'İş Türü': c.job_type,
        'Durum': c.status,
        'Tarih': c.date,
        'Not': c.note
    } for c in customers]
    df = pd.DataFrame(data)

    output = io.BytesIO()
    writer = pd.ExcelWriter(output, engine='xlsxwriter')
    df.to_excel(writer, index=False, sheet_name='Müşteriler')
    writer.close()
    output.seek(0)

    return send_file(output, 
                     mimetype='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
                     download_name='musteri_listesi.xlsx',
                     as_attachment=True)

@app.route('/export/pdf')
@login_required
@admin_required
def export_pdf():
    customers = Customer.query.all()
    
    buffer = io.BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=letter)
    styles = getSampleStyleSheet()
    
    story = []
    story.append(Paragraph("Tadilat & Boya Badana Müşteri Listesi", styles['h1']))
    story.append(Spacer(1, 0.2 * 100)) # 0.2 inch of space

    # Table Data
    data = [["Ad-Soyad", "Telefon", "Adres", "İş Türü", "Durum", "Tarih", "Not"]]
    for c in customers:
        data.append([c.name, c.phone, c.address, c.job_type, c.status, c.date, c.note])
    
    table = Table(data)
    
    # Table Style
    table.setStyle([('BACKGROUND', (0, 0), (-1, 0), colors.grey),
                    ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
                    ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
                    ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
                    ('BOTTOMPADDING', (0, 0), (-1, 0), 12),
                    ('BACKGROUND', (0, 1), (-1, -1), colors.beige),
                    ('GRID', (0, 0), (-1, -1), 1, colors.black)])
    
    story.append(table)
    doc.build(story)
    
    buffer.seek(0)
    return send_file(buffer,
                     mimetype='application/pdf',
                     download_name='musteri_listesi.pdf',
                     as_attachment=True)

if __name__ == '__main__':
    with app.app_context():
        db.create_all()
        # Sadece ilk çalıştırmada admin oluşturmak için
        if not User.query.filter_by(username='admin').first():
            admin = User(username='admin', role='admin')
            admin.set_password('adminpass') # Güvenli bir parola ile değiştirin
            db.session.add(admin)
            db.session.commit()
    app.run(debug=True)
