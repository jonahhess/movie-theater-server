import os
import jwt

SECRET_KEY = os.getenv("MAGIC_LINK_SECRET_KEY", "your-very-secret-key")
ALGORITHM = os.getenv("MAGIC_LINK_ALGORITHM", "HS256")


def generate_magic_link(receipt_number: str):
    """
    Generates a secure magic link token for the given receipt number.
    The token is valid for 7 days.
    """
    expiration_time = 7 * 24 * 60 * 60  # 7 days
    payload = {
        "sub": receipt_number,
        "exp": jwt.datetime.utcnow() + jwt.timedelta(seconds=expiration_time)
    }
    
    token = jwt.encode(payload, SECRET_KEY, algorithm=ALGORITHM)
    return token