# server/__init__.py
import uvicorn

if __name__ == "__main__":
    # This automatically handles the path tracking from the server/ root
    uvicorn.run("main_site.main:app", host="127.0.0.1", port=8000, reload=True, 
                log_level="debug")
