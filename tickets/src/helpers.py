import uuid

from fastapi import Request, Response


# assign uuid in http cookie
async def get_or_create_user_uuid(request: Request, response: Response) -> str:
    """
    Dependency that retrieves an existing user_uuid from cookies,
    or generates a new one for guests and stores it in a secure cookie.
    """
    # 1. Try to find an existing UUID in the incoming request cookies
    user_uuid = request.cookies.get("user_uuid")
    
    if not user_uuid:
        # 2. If it doesn't exist, they are a guest. Generate a fresh UUID.
        user_uuid = str(uuid.uuid7())
        
        # 3. Set the cookie on the response so the browser remembers it
        response.set_cookie(
            key="user_uuid",
            value=user_uuid,
            max_age=3600 * 24,  # Expires in 24 hours (adjust as needed for seat holds)
            httponly=True,      # Prevents client-side scripts from stealing the cookie
            samesite="lax",     # Protects against CSRF attacks
            secure=False        # Set to True in production over HTTPS
        )
        print(f"Generated new guest UUID: {user_uuid}")
    else:
        print(f"Found existing user UUID: {user_uuid}")
        
    return user_uuid