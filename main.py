from fastapi import FastAPI

app = FastAPI()

@app.get("/")
def health_check():
    return {"status": "ok", "message": "AI Personal Accounting Bot is running"}