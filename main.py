import uvicorn

from app.core import config

if __name__ == "__main__":
    uvicorn.run("app.main:app", host=config.HTTP_HOST, port=config.HTTP_PORT, reload=True)