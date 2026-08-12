from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse
from starlette import status

router = APIRouter()

@router.get("/auth/google/callback")
async def google_auth_callback(request: Request):
    code = request.query_params.get("code")
    state = request.query_params.get("state")

    if not code:
        return HTMLResponse("❌ Google authorization failed: authorization code missing.",
            status_code=400,)
    return HTMLResponse(
        """
        <html>
            <body>
                <h2>✅ Google authorization successful!</h2>
                <p>You can return to Telegram.</p>
            </body>
        </html>
        """
    )