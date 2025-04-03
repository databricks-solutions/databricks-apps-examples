from flask_sqlalchemy import SQLAlchemy

db = SQLAlchemy()

# Database for storing user credentials (DEMO PURPOSES ONLY! DO NOT USE THIS AS YOUR PRODUCTION DATABASE)
class User(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    email = db.Column(db.String(20), unique=True, nullable=False)
    password = db.Column(db.String(80), nullable=False)
    company = db.Column(db.String(20), nullable=False)
    first_name = db.Column(db.String(50))
    last_name = db.Column(db.String(50))
   

    def __repr__(self):
        return f'<email={self.email}, company={self.company}>'