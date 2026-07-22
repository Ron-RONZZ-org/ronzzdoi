from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
import asyncio


class AuthMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        # Simulate authentication logic here.
        # For example, check for an Authorization header or session cookie.
        
        if "Authorization" not in request.headers:
            print("Authentication failed: Missing Authorization header.")
            return Response(status_code=401, content="Unauthorized")

        # If authentication succeeds, proceed to the next middleware/endpoint
        response = await call_next(request)
        return response


# --- Minimal imports needed for the code to run standalone for testing purposes ---
from starlette.responses import Response


# Example usage demonstrating how this class would be applied (requires an ASGI app setup):
"""
async def homepage(request: Request):
    return HTMLResponse("Welcome!")

app = Starlette(middleware=[Middleware(AuthMiddleware)])
routes = [Route("/", endpoint=homepage)]
app.add_routes(routes) 
# When deployed, the framework handles the middleware call.
"""