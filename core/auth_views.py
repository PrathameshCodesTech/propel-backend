from django.contrib.auth import authenticate

from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.authtoken.models import Token

from core.models import Employee


class LoginAPIView(APIView):
    """
    Token-based login for SPA frontend.

    POST /api/auth/login/
    Body: { "username": "...", "password": "..." }
    Response: { "token", "username", "org_code", "is_staff", "role" }
    """

    permission_classes = [AllowAny]

    def post(self, request):
        username = request.data.get("username")
        password = request.data.get("password")

        if not username or not password:
            return Response({"error": "Username and password are required."}, status=400)

        user = authenticate(request, username=username, password=password)
        if not user:
            return Response({"error": "Invalid credentials."}, status=401)

        token, _ = Token.objects.get_or_create(user=user)

        emp = getattr(user, "employee_profile", None)
        org_code = emp.organization.code if emp and emp.organization else None
        role = emp.role if emp else None

        return Response(
            {
                "token": token.key,
                "username": user.get_username(),
                "org_code": org_code,
                "is_staff": bool(user.is_staff),
                "role": role,
            }
        )


class LogoutAPIView(APIView):
    """
    Simple token logout – deletes the current user's token.

    POST /api/auth/logout/
    Header: Authorization: Token <token>
    """

    permission_classes = [IsAuthenticated]

    def post(self, request):
        Token.objects.filter(user=request.user).delete()
        return Response({"message": "Logged out."})

