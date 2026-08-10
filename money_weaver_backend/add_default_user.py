#!/usr/bin/env python3
"""
Add default user to database
"""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from src.database import db
from src.models.user import User
from src.models.project import Project
from werkzeug.security import generate_password_hash

# Initialize the database
from src.main import app

def add_default_user():
    with app.app_context():
        # Check if user already exists
        existing_user = User.query.filter_by(username='johndoe').first()
        if existing_user:
            print("Default user already exists")
            return existing_user.id
            
        # Create default user with hashed password
        user = User(
            username='johndoe',
            email='john.doe@example.com'
        )
        user.set_password('password123')  # Set a default password
        db.session.add(user)
        db.session.commit()
        print(f"Created default user with ID: {user.id}")
        return user.id

def add_sample_project(user_id):
    with app.app_context():
        # Check if sample project already exists
        existing_project = Project.query.filter_by(title='Sample Project').first()
        if existing_project:
            print("Sample project already exists")
            return
            
        # Create sample project
        project = Project(
            title='Sample Project',
            description='A sample project for testing',
            user_id=user_id,
            status='draft',
            workflow_type='assembler'
        )
        db.session.add(project)
        db.session.commit()
        print(f"Created sample project with ID: {project.id}")

if __name__ == '__main__':
    user_id = add_default_user()
    add_sample_project(user_id)