from flask import Flask, jsonify, redirect, request, send_from_directory, session, url_for
from flask_restful import Api
from flask_sqlalchemy import SQLAlchemy
from flask_cors import CORS
from flask_jwt_extended import JWTManager, create_access_token, jwt_required, get_jwt_identity
from datetime import datetime, timedelta
from werkzeug.utils import secure_filename
from collections.abc import Mapping
from werkzeug.security import generate_password_hash, check_password_hash
import os

app = Flask(__name__)
api = Api(app)
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///db_library.sqlite3'
app.config['SECRET_KEY'] = "random string"
app.config['UPLOAD_FOLDER'] = 'uploads'
app.config['JWT_SECRET_KEY'] = 'super-secret'
UPLOAD_FOLDER = 'uploads'
ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'gif'}
db = SQLAlchemy(app)
jwt = JWTManager(app)  
CORS(app)

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

class Users(db.Model):
    user_id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(100), unique=True, nullable=False)
    password_hash = db.Column(db.String(100), nullable=False)
    role = db.Column(db.String(20), nullable=False)

    def __init__(self, username, password, role, customer_id=None):
        self.username = username
        self.password_hash = generate_password_hash(password)
        self.role = role
        
class Loans(db.Model):
    loans_id = db.Column(db.Integer, primary_key=True)
    customer = db.Column(db.Integer, db.ForeignKey('customers.customer_id'), nullable=False)
    book = db.Column(db.Integer, db.ForeignKey('books.book_id'), nullable=False)
    loandate = db.Column(db.Date, nullable=False)
    returndate = db.Column(db.Date, nullable=False)
    returned = db.Column(db.String, nullable=False)
    status = db.Column(db.String, nullable=True)

    def __init__(self, customer, book, loandate, returndate, returned):
        self.customer = customer
        self.book = book
        self.loandate = loandate
        self.returndate = returndate
        self.returned = returned
        self.set_status()  # Appel de la méthode pour définir le statut

    def set_status(self):
        today = datetime.now().date()

        print('loandate:', self.loandate)
        print('returndate:', self.returndate)
        print('today:', today)
        # Vérifiez si le livre est retourné
        if self.returned == "Not returned":
            # Vérifiez si la date de retour est dépassée
            if datetime.combine(self.returndate, datetime.min.time()) < datetime.now():
                self.status = "Late"
            else:
                self.status = "On time"
        elif self.returned == "Returned":
            self.status = "Returned"
        else:
            # Si la valeur de 'returned' n'est ni "Not returned" ni "Returned", définissez le statut comme inconnu
            self.status = "Unknown"

    def update_status(self):
        # Appel de la méthode pour mettre à jour le statut lorsqu'un prêt est modifié
        self.set_status()
        db.session.commit()

class Customers(db.Model):
    customer_id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.user_id'), nullable=True)  # Change nullable to True
    customer_name = db.Column(db.String(120), nullable=False)
    city = db.Column(db.String(120), nullable=False)
    age = db.Column(db.Integer, nullable=False)
    loans = db.relationship('Loans', backref='customers', lazy=True)

    def __init__(self, customer_name, city, age, user_id=None):  # Provide a default value for user_id
        self.user_id = user_id
        self.customer_name = customer_name
        self.city = city
        self.age = age

class Books(db.Model):
    
    book_id = db.Column(db.Integer, primary_key=True)
    book_name = db.Column(db.String(50), nullable=False)
    author = db.Column(db.String(50), nullable=False)
    year = db.Column(db.Integer, nullable=False)
    type = db.Column(db.Integer, nullable=False)
    loans= db.relationship('Loans', backref='books')
    image_filename = db.Column(db.String(255), nullable=True)




    def __init__(self,  book_name, author,year,type, image_filename=None):
        
        self.book_name = book_name
        self.author = author
        self.year = year
        self.type = type
        self.image_filename = image_filename

# def manager_required(fn):
    # @jwt_required()
    # def wrapper(*args, **kwargs):
    #     current_user = Users.query.filter_by(username=get_jwt_identity()).first()
    #     if not current_user or current_user.role != 'manager':
    #         return jsonify({'message': 'Managers only!'}), 403
    #     request.current_user = current_user
    #     return fn(*args, **kwargs)

    # # Dynamically set a unique name for the wrapper function
    # wrapper.__name__ = f"manager_wrapper_{fn.__name__}"

    # return wrapper
@app.route('/new_customer', methods=['POST'])
def new_customer():
    request_data = request.get_json()
    user_id = request_data.get('user')  # Utilisez get avec une valeur par défaut de None
    customer_name = request_data['customer_name']
    city = request_data['city']
    age = request_data['age']

    new_customer = Customers(user_id=user_id, customer_name=customer_name, city=city, age=age)
    db.session.add(new_customer)
    db.session.commit()

    # Retournez également le nom d'utilisateur associé au customer ajouté
    user = Users.query.filter_by(user_id=new_customer.user_id).first()
    return jsonify({"message": "Customer added successfully", "username": user.username}), 200

@app.route('/get_customers', methods=['GET'])
# @manager_required
def get_customers():
    customers = Customers.query.all()
    customer_list = []

    for customer in customers:
        # Utilisez une requête pour obtenir le nom d'utilisateur du user associé
        user = Users.query.filter_by(user_id=customer.user_id).first()

        customer_list.append({
            'customer_id': customer.customer_id,
            'user_id': customer.user_id,  # Retournez également l'ID de l'utilisateur
            'username': user.username if user else None,  # Utilisez le nom d'utilisateur s'il existe, sinon None
            'customer_name': customer.customer_name,
            'city': customer.city,
            'age': customer.age
        })

    return jsonify({'customers': customer_list})



@app.route('/delete_customer/<int:customer_id>', methods=['DELETE'])
# @manager_required
def delete_customer(customer_id):
    customer = Customers.query.get(customer_id)
    if customer:
        # Retournez le nom du client supprimé
        deleted_customer_name = customer.customer_name
        db.session.delete(customer)
        db.session.commit()
        return jsonify({'message': f'Customer {deleted_customer_name} deleted successfully'}), 200
    return jsonify({'message': 'Customer not found'}), 404



@app.route('/new_books', methods=['POST'])
# @manager_required
def new_books():
    request_data = request.form
    book_name = request_data['book_name']
    author = request_data['author']
    year = request_data['year']
    book_type = request_data['type']

    # Check if the post request has the file part
    if 'file' not in request.files or request.files['file'].filename == '':
        # Set a default image filename if no image is provided
        default_image_filename = 'livre.png'
        new_book = Books(book_name=book_name, author=author, year=year, type=book_type, image_filename=default_image_filename)
        db.session.add(new_book)
        db.session.commit()

        return jsonify({"message": "Book added successfully"}), 200

    file = request.files['file']

    if file and allowed_file(file.filename):
        filename = secure_filename(file.filename)
        filename, file_extension = os.path.splitext(filename)
        unique_filename = f"{filename}_{datetime.now().strftime('%Y%m%d%H%M%S')}{file_extension}"
        file.save(os.path.join(app.config['UPLOAD_FOLDER'], unique_filename))
        default_image_filename = unique_filename
    else:
        return jsonify({"message": "Invalid file format"}), 400

    new_book = Books(book_name=book_name, author=author, year=year, type=book_type, image_filename=default_image_filename)
    db.session.add(new_book)
    db.session.commit()

    return jsonify({"message": "Book added successfully"}), 200



@app.route('/get_books', methods=['GET'])
def get_books():
    books = Books.query.all()
    book_list = []
    for book in books:
        book_list.append({'book_id': book.book_id,'book_name': book.book_name,'author': book.author,'year': book.year,'type': book.type,'image_filename': book.image_filename})
    return jsonify({'books': book_list})


@app.route('/delete_book/<int:book_id>', methods=['DELETE'])
# @manager_required
def delete_book(book_id):
    book = Books.query.get(book_id)
    if book:
        db.session.delete(book)
        db.session.commit()
        return jsonify({'message': 'Book deleted successfully'}), 200
    return jsonify({'message': 'Book not found'}), 404




@app.route('/new_loans', methods=['POST'])
# @manager_required
def new_loans():
    request_data = request.get_json()
    customer = request_data['customer']
    book = request_data['book']
    loandate = datetime.strptime(request_data['loandate'], '%Y-%m-%d').date()

    # Utilize the method query.filter_by to get the type of the book
    book_type = Books.query.filter_by(book_id=book).first().type

    if book_type == "up to 10 days":
        returndate = loandate + timedelta(days=10)
    elif book_type == "up to 5 days":
        returndate = loandate + timedelta(days=5)
    elif book_type == "up to 2 days":
        returndate = loandate + timedelta(days=2)

    returned = "Not returned"

    print('loandate (server):', loandate)
    print('returndate (server):', returndate)

    new_loan = Loans(customer=customer, book=book, loandate=loandate, returndate=returndate, returned=returned)
    new_loan.set_status()
    db.session.add(new_loan)
    db.session.commit()

    return jsonify({"message": "Loan added successfully"}), 200




@app.route('/get_loans', methods=['GET'])
def get_loans():
    loans = Loans.query.all()
    today = datetime.now().date()

    loan_list = []
    for loan in loans:
        if loan.customers:
            # Vérifiez si le livre est retourné
            if loan.returned == "Not returned":
                # Vérifiez si la date de retour est dépassée
                if loan.returndate < today:
                    status = "Late"
                    color = "red"  # Mettez la couleur en rouge pour les retours en retard
                else:
                    status = "On time"
                    color = "green"  # Mettez la couleur en vert pour les retours à temps
            elif loan.returned == "Returned":
                status = "Returned"
                color = "yellow"  # Mettez la couleur en jaune pour les livres retournés
            else:
                # Si la valeur de 'returned' n'est ni "Not returned" ni "Returned", définissez le statut comme inconnu
                status = "Unknown"
                color = "black"  # Couleur par défaut

            loan_list.append({
                'loans_id': loan.loans_id,
                'customer': loan.customers.customer_name if loan.customers else None,
                'book': loan.books.book_name if loan.books else None,
                'loandate': loan.loandate,
                'returndate': loan.returndate,
                'returned': loan.returned,
                'status': status,
                'color': color  # Ajoutez la couleur à la réponse JSON
            })
        else:
            # Handle the case where loan.customers is None
            loan_list.append({
                'loans_id': loan.loans_id,
                'customer': None,
                'book': loan.books.book_name if loan.books else None,
                'loandate': loan.loandate,
                'returndate': loan.returndate,
                'returned': loan.returned,
                'status': "Unknown",
                'color': "black"  # Couleur par défaut
            })

    return jsonify({'loans': loan_list})


@app.route('/delete_loan/<int:loan_id>', methods=['DELETE'])
# @manager_required
def delete_loan(loan_id):
    loan = Loans.query.get(loan_id)
    if loan:
        db.session.delete(loan)
        db.session.commit()
        return jsonify({'message': 'Loan deleted successfully'}), 200
    return jsonify({'message': 'Loan not found'}), 404


@app.route('/toggle_returned_status/<int:loan_id>', methods=['PUT'])
# @manager_required
def toggle_returned_status(loan_id):
    loan = Loans.query.get(loan_id)
    if loan:
        new_status = request.json['returned']
        loan.returned = new_status
        loan.update_status()  # Mettre à jour le statut
        return jsonify({'message': 'Book returned successfully'}), 200
    return jsonify({'error': 'Loan not found'}), 404


@app.route('/search_customers', methods=['GET'])
# @manager_required
def search_customers():
    name = request.args.get('name', '').lower()

    if not name:
        return jsonify({"customers": []})

    # Filtrez les clients dont le nom contient la chaîne spécifiée (insensible à la casse)
    filtered_customers = Customers.query.filter(Customers.customer_name.ilike(f"%{name}%")).all()

    customer_list = []
    for customer in filtered_customers:
        customer_list.append({'customer_id': customer.customer_id, 'customer_name': customer.customer_name, 'city': customer.city, 'age': customer.age})

    return jsonify({"customers": customer_list})

@app.route('/search_books', methods=['GET'])
def search_books():
    name = request.args.get('name', '').lower()

    if not name:
        return jsonify({"books": []})

    # Filtrez les livres dont le nom contient la chaîne spécifiée (insensible à la casse)
    filtered_books = Books.query.filter(Books.book_name.ilike(f"%{name}%")).all()

    book_list = []
    for book in filtered_books:
        book_list.append({'book_id': book.book_id, 'book_name': book.book_name, 'author': book.author, 'year': book.year, 'type': book.type})

    return jsonify({"books": book_list})

@app.route('/uploads/<filename>')
# @manager_required
def uploaded_file(filename):
    return send_from_directory(app.config['UPLOAD_FOLDER'], filename)

@app.route('/test_data', methods=['POST'])
# @manager_required
def test_data():
    # Create a new customer without specifying the user
    new_customer = Customers(customer_name='Reouven', city='Ra\'anana', age=24)
    db.session.add(new_customer)
    db.session.commit()

    # Create a new book
    new_book = Books(book_name='Harry Potter I', author='J.K Rowling', year=1997, type='up to 10 days', image_filename='livre.png')
    db.session.add(new_book)
    db.session.commit()

    return jsonify({"message": "Test data added successfully"}), 200


@app.route('/register', methods=['POST'])
def register():
    request_data = request.get_json()
    username = request_data['username']
    password = request_data['password']
    role = request_data['role']

    if Users.query.filter_by(username=username).first():
        return jsonify({"message": "Username already exists"}), 400

    new_user = Users(username=username, password=password, role=role)
    db.session.add(new_user)
    db.session.commit()

    return jsonify({"message": "User registered successfully"}), 200

@app.route('/login', methods=['POST'])
def login():
    request_data = request.get_json()
    username = request_data['username']
    password = request_data['password']

    user = Users.query.filter_by(username=username).first()

    if user and check_password_hash(user.password_hash, password):
        expires = timedelta(minutes=10)
        access_token = create_access_token(identity=username, expires_delta=expires)
        return jsonify(access_token=access_token, role=user.role), 200
    else:
        return jsonify({"message": "Invalid credentials"}), 401

@app.route('/get_user_loans', methods=['GET'])
@jwt_required()
def get_user_loans():
    current_username = get_jwt_identity()
    user = Users.query.filter_by(username=current_username).first()

    if user.role == "user":
        loans = Loans.query.join(Customers, Customers.customer_id == Loans.customer).filter_by(user_id=user.user_id).all()

    else:
        loans = Loans.query.all()

    loan_list = []
    for loan in loans:
        loan_list.append({
            'loans_id': loan.loans_id,
            'customer': loan.customers.customer_name,
            'book': loan.books.book_name,
            'loandate': loan.loandate,
            'returndate': loan.returndate,
            'returned': loan.returned,
            'status': loan.status,
            'color': loan.color
        })

    return jsonify({'loans': loan_list})
    

@app.route('/get_users', methods=['GET'])
def get_users():
    users = Users.query.all()
    user_list = [{'user_id': user.user_id, 'username': user.username} for user in users]
    return jsonify({'users': user_list})

@app.route('/get_user/<int:user_id>', methods=['GET'])
def get_user_by_id(user_id):
    user = Users.query.get(user_id)
    if user:
        return jsonify({"username": user.username}), 200
    else:
        return jsonify({"error": "User not found"}), 404
    
@app.route('/logout', methods=['POST'])
def logout():
    # Your logout logic here, e.g., clearing the session
    session.clear()

    # Return a response
    return jsonify({'message': 'Logout successful'})

if __name__ == '__main__':
    with app.app_context():
        db.create_all()
    app.run(debug=True)

