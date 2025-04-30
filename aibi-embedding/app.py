import pandas as pd
from flask import Flask, jsonify, send_from_directory, session, request, redirect, url_for
from flask_jwt_extended import JWTManager, create_access_token, jwt_required, get_jwt_identity, get_jwt
from flask_sqlalchemy import SQLAlchemy
from flask_cors import CORS
import logging
import secrets
from backend.models import db, User
from backend.dashboard_embedding import get_dashboard_embedding_oauth_token
from backend.genie_embedding import get_databricks_oauth_token, get_genie_space_id, new_genie_conversation, continue_genie_conversation
from dotenv import load_dotenv
import os

log = logging.getLogger('werkzeug')
log.setLevel(logging.ERROR)

app = Flask(__name__, static_folder='frontend/build', static_url_path='/')
CORS(app, resources={r"/api/*": {"origins": ["https://aibi-embedding-demo-984752964297111.11.azure.databricksapps.com", "http://localhost:3000"]}})

# Configuration
app.config['SECRET_KEY'] = secrets.token_hex(32)
app.config["JWT_SECRET_KEY"] = secrets.token_hex(32)
app.config['JWT_TOKEN_LOCATION'] = ['headers']

# Dummy Database for storing user information
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///db.sqlite'

# JWT Initialization
jwt = JWTManager(app)

# Pull Environment Variables
load_dotenv()
databricks_host = os.environ['DATABRICKS_HOST']
databricks_client_id = os.environ['DATABRICKS_CLIENT_ID']
databricks_client_secret = os.environ['DATABRICKS_CLIENT_SECRET']

db.init_app(app)
with app.app_context():
    db.create_all()

@app.route('/')
@app.route('/login')
@app.route('/home')
@app.route('/genie')
@app.route('/analytics')
def serve():
    return send_from_directory(app.static_folder, 'index.html')

# This is the endpoint the front-end will hit to verify login information
@app.route('/api/login', methods=['POST'])
def login():    
    data = request.get_json()
    email = data['email']
    password = data['password']
    print('Received data:', email , password)

    user = User.query.filter_by(email=email).first()

    if user and user.password==password:
        access_token = create_access_token(identity=user.id)
        databricks_token = get_databricks_oauth_token()
        return jsonify({'message': 'Login Success', 'databricks_token':databricks_token,'first_name': user.first_name, 'last_name': user.last_name,'email': email, 'access_token': access_token,'company': user.company})
    else:
        return jsonify({'message': 'Login Failed'}), 401

@app.route('/api/data', methods=['GET'])
def get_data():
    return jsonify({"message": "Hello from Flask!"})


@app.route('/api/dashboard/config', methods=['POST'])
def dashboard_config():
    return jsonify({
        "instance_url": "https://" + os.environ['DATABRICKS_HOST'],
        "workspace_id": os.environ['DATABRICKS_WORKSPACE_ID'],
        "dashboard_id": os.environ['DATABRICKS_DASHBOARD_ID']
    })

# This is the endpoint the front-end will hit to embed the dashboard
@app.route('/api/dashboard/get_token', methods=['POST'])
def dashboard_get_token():
    # Unwrap the payload sent from the front-end. This includes the user's question as well as additional information about the user
    data = request.get_json()

    # Inputs sent from the front-end
    external_data = data['external_data']
    external_viewer_id = data['external_viewer_id']
    dashboard_name = data['dashboard_name']

    # Call the continue_genie_conversation from 'backend/dashboard_embedding.py'
    response = get_dashboard_embedding_oauth_token(external_data = external_data, external_viewer_id = external_viewer_id, dashboard_name = dashboard_name)
    return response

# This is the endpoint the front-end will hit to start a new conversation
@app.route('/api/genie/start_conversation', methods=['POST'])
def genie_start_conversation():
    # Unwrap the payload sent from the front-end. This includes the user's question as well as additional information about the user
    data = request.get_json()

    # Inputs sent from the front-end
    initial_message = data['question']
    databricks_token = data['databricks_token']
    user_company = data['user_company']
    databricks_genie_space_id = get_genie_space_id(user_company)

    # Call the new_genie_conversation from 'backend/genie_embedding.py'
    response = new_genie_conversation(space_id = databricks_genie_space_id, content=initial_message, token = databricks_token, databricks_host = databricks_host)
    return response

# This is the endpoint the front-end will hit to continue an existing conversation
@app.route('/api/genie/continue_conversation', methods=['POST'])
def genie_continue_conversation():
    # Unwrap the payload sent from the front-end. This includes the user's question as well as additional information about the user
    data = request.get_json()

    # Inputs sent from the front-end
    followup_message = data['question']
    conversation_id = data['conversation_id']
    databricks_token = data['databricks_token']
    user_company = data['user_company']
    databricks_genie_space_id = get_genie_space_id(user_company)

    # Call the continue_genie_conversation from 'backend/genie_embedding.py'
    response = continue_genie_conversation(space_id = databricks_genie_space_id, content=followup_message, conversation_id = conversation_id, token = databricks_token, databricks_host = databricks_host)
    return response

if __name__ == '__main__':
    app.run(debug=True)
