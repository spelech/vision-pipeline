import os
import secrets
import shutil
import subprocess
import sys
from pathlib import Path

def generate_encryption_key():
    try:
        from cryptography.fernet import Fernet
        return Fernet.generate_key().decode()
    except ImportError:
        # Fallback if cryptography isn't installed locally
        import base64
        return base64.urlsafe_b64encode(secrets.token_bytes(32)).decode()

def setup():
    print("🚀 Starting Vision Pipeline setup...")
    
    base_path = Path(__file__).parent
    env_file = base_path / ".env"
    env_example = base_path / ".env.example"
    
    # 1. Create .env if it doesn't exist
    if not env_file.exists():
        if env_example.exists():
            print(f"📄 Creating .env from .env.example...")
            shutil.copy(env_example, env_file)
            
            # Generate and insert encryption key
            key = generate_encryption_key()
            content = env_file.read_text()
            content = content.replace("ENCRYPTION_KEY=", f"ENCRYPTION_KEY={key}")
            env_file.write_text(content)
            print(f"✅ .env created with fresh ENCRYPTION_KEY.")
        else:
            print(f"⚠️  Warning: .env.example not found. Creating a blank .env.")
            env_file.touch()
    else:
        print(f"ℹ️  .env already exists, skipping creation.")

    # 2. Ensure data directories exist
    print("📁 Preparing data directories...")
    directories = [
        base_path / "data" / "postgres",
        base_path / "data" / "uploads",
        base_path / "config"
    ]
    
    for d in directories:
        d.mkdir(parents=True, exist_ok=True)
        # On Linux/Mac, set permissions for uploads
        if os.name != 'nt' and "uploads" in str(d):
            try:
                os.chmod(d, 0o777)
            except Exception as e:
                print(f"ℹ️  Could not set permissions on {d}: {e}")

    # 3. Check for Docker
    docker_cmd = shutil.which("docker")
    if not docker_cmd:
        print("❌ Error: 'docker' command not found. Please install Docker Desktop or Docker Engine.")
        return

    # 4. Pull/Build images
    print("🐳 Pulling/Building containers (this may take a few minutes)...")
    try:
        # We use 'docker compose' (v2) but fallback to 'docker-compose' (v1) if needed
        result = subprocess.run(["docker", "compose", "build"], cwd=base_path)
        if result.returncode != 0:
            print("Trying legacy 'docker-compose'...")
            subprocess.run(["docker-compose", "build"], cwd=base_path)
    except Exception as e:
        print(f"⚠️  Could not run docker build: {e}")
        print("Please run 'docker compose build' manually.")

    print("\n✨ Setup complete!")
    print(f"👉 Edit your .env file at: {env_file.absolute()}")
    print("👉 Run 'docker compose up -d' to start the application.")
    print("👉 Application will be available at http://localhost:8460 (default)")

if __name__ == "__main__":
    setup()
