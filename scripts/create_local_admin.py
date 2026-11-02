import json
import os
import secrets
from pathlib import Path

from werkzeug.security import generate_password_hash


project_root = Path(__file__).resolve().parents[1]
instance_dir = project_root / "instance"
config_path = instance_dir / "local_admin.json"
instance_dir.mkdir(parents=True, exist_ok=True)

admin_password = secrets.token_urlsafe(24)
admin_config = {
    "secret_key": secrets.token_hex(32),
    "username": "admin",
    "password_hash": generate_password_hash(admin_password),
}

try:
    with config_path.open("x", encoding="utf-8") as config_file:
        json.dump(admin_config, config_file)
        config_file.write("\n")
except FileExistsError:
    raise SystemExit(
        "A local admin account already exists. Keep its credentials safe; "
        "the stored password cannot be displayed again."
    )

print("Local development admin account created.")
print(f"Username: {admin_config['username']}")
print(f"Password: {admin_password}")
print("Store this password securely; it is not saved in plain text.")
