import os
import uvicorn
from dotenv import load_dotenv

load_dotenv()
if __name__ == "__main__":
    port = int(os.getenv("PORT", "8000"))
    if not 1 <= port <= 65535:
        raise ValueError("PORT deve essere compresa tra 1 e 65535")
    uvicorn.run("app.main:app", host="0.0.0.0", port=port)
