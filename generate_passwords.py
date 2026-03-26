"""
Run this ONCE locally to generate hashed passwords.
Then paste the output into auth_config.yaml

Usage:
    python generate_passwords.py
"""
import bcrypt

users = {
    "hamza":  "changeme123",   # <-- change these
    "friend": "changeme456",   # <-- change these
}

print("Paste these into auth_config.yaml under credentials > usernames > <user> > password:\n")
for username, password in users.items():
    hashed = bcrypt.hashpw(password.encode(), bcrypt.gensalt()).decode()
    print(f"{username}:")
    print(f"  password: {hashed}\n")
