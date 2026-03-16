import uvicorn
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.api.alps_router import router as alps_router

app = FastAPI(title="Amazon NACF Digital Twin Backend", version="5.0")

# Allow the Vue.js frontend to communicate with this backend
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Mount the ALPS engine
app.include_router(alps_router, prefix="/api/alps", tags=["ALPS Flow Engine"])

@app.get("/")
def root():
    return {"message": "Amazon ALPS Backend is Active. Operational metrics standing by."}

if __name__ == "__main__":
    print("=========================================================")
    print(" 🚀 INITIALIZING AMAZON ALPS DIGITAL TWIN BACKEND")
    print("=========================================================")
    uvicorn.run(app, host="0.0.0.0", port=8000)