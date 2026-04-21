"""
认证相关 API Views
"""
from rest_framework import status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.response import Response
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework_simplejwt.tokens import RefreshToken
from django.contrib.auth import authenticate
from drf_spectacular.utils import extend_schema, OpenApiExample, inline_serializer
from rest_framework import serializers


# ──────────────────────────────────────────
# 登录接口
# ──────────────────────────────────────────
@extend_schema(
    summary="用户登录",
    description="提交用户名和密码，返回 JWT Access Token 和 Refresh Token。",
    request=inline_serializer(
        name="LoginRequest",
        fields={
            "username": serializers.CharField(help_text="用户名"),
            "password": serializers.CharField(help_text="密码"),
        }
    ),
    responses={
        200: inline_serializer(
            name="LoginResponse",
            fields={
                "access": serializers.CharField(help_text="Access Token"),
                "refresh": serializers.CharField(help_text="Refresh Token"),
                "user": inline_serializer(
                    name="UserInfo",
                    fields={
                        "id": serializers.IntegerField(),
                        "username": serializers.CharField(),
                        "email": serializers.EmailField(),
                        "is_superuser": serializers.BooleanField(),
                    }
                ),
            }
        ),
        401: inline_serializer(
            name="LoginError",
            fields={"error": serializers.CharField(help_text="错误信息")}
        ),
    },
    examples=[
        OpenApiExample(
            "登录示例",
            value={"username": "admin", "password": "yourpassword"},
            request_only=True,
        )
    ],
    tags=["认证"],
)
@api_view(['POST'])
@permission_classes([AllowAny])
def login(request):
    """用户登录"""
    username = request.data.get('username')
    password = request.data.get('password')

    if not username or not password:
        return Response(
            {'error': '用户名和密码不能为空'},
            status=status.HTTP_400_BAD_REQUEST
        )

    user = authenticate(username=username, password=password)

    if user is not None:
        refresh = RefreshToken.for_user(user)

        return Response({
            'access': str(refresh.access_token),
            'refresh': str(refresh),
            'user': {
                'id': user.id,
                'username': user.username,
                'email': user.email,
                'is_superuser': user.is_superuser,
            }
        })
    else:
        return Response(
            {'error': '用户名或密码错误'},
            status=status.HTTP_401_UNAUTHORIZED
        )


# ──────────────────────────────────────────
# 获取当前用户信息
# ──────────────────────────────────────────
@extend_schema(
    summary="获取当前用户信息",
    description="通过 Bearer Token 获取当前登录用户的基本信息。",
    responses={
        200: inline_serializer(
            name="UserInfoResponse",
            fields={
                "id": serializers.IntegerField(),
                "username": serializers.CharField(),
                "email": serializers.EmailField(),
                "is_superuser": serializers.BooleanField(),
            }
        )
    },
    tags=["认证"],
)
@api_view(['GET'])
@permission_classes([IsAuthenticated])
def get_user_info(request):
    """获取当前用户信息"""
    user = request.user
    return Response({
        'id': user.id,
        'username': user.username,
        'email': user.email,
        'is_superuser': user.is_superuser,
    })


# ──────────────────────────────────────────
# 登出
# ──────────────────────────────────────────
@extend_schema(
    summary="用户登出",
    description="登出接口（主要由前端清除本地 Token，服务端返回成功状态）。",
    responses={
        200: inline_serializer(
            name="LogoutResponse",
            fields={"message": serializers.CharField()}
        )
    },
    tags=["认证"],
)
@api_view(['POST'])
@permission_classes([IsAuthenticated])
def logout(request):
    """登出（主要是前端清除 Token）"""
    return Response({'message': '登出成功'})


# ──────────────────────────────────────────
# 更新用户信息
# ──────────────────────────────────────────
@extend_schema(
    summary="更新用户信息",
    description="更新当前登录用户的邮箱等基本信息。",
    request=inline_serializer(
        name="UpdateUserInfoRequest",
        fields={
            "email": serializers.EmailField(required=False, help_text="新邮箱地址"),
        }
    ),
    responses={
        200: inline_serializer(
            name="UpdateUserInfoResponse",
            fields={
                "id": serializers.IntegerField(),
                "username": serializers.CharField(),
                "email": serializers.EmailField(),
                "is_superuser": serializers.BooleanField(),
            }
        )
    },
    tags=["认证"],
)
@api_view(['PUT'])
@permission_classes([IsAuthenticated])
def update_user_info(request):
    """更新用户信息"""
    user = request.user
    email = request.data.get('email')

    if email is not None:
        user.email = email

    user.save()

    return Response({
        'id': user.id,
        'username': user.username,
        'email': user.email,
        'is_superuser': user.is_superuser,
    })


# ──────────────────────────────────────────
# 修改密码
# ──────────────────────────────────────────
@extend_schema(
    summary="修改密码",
    description="使用旧密码验证身份后，将密码更新为新密码。",
    request=inline_serializer(
        name="ChangePasswordRequest",
        fields={
            "old_password": serializers.CharField(help_text="当前密码"),
            "new_password": serializers.CharField(help_text="新密码"),
        }
    ),
    responses={
        200: inline_serializer(
            name="ChangePasswordResponse",
            fields={"message": serializers.CharField()}
        ),
        400: inline_serializer(
            name="ChangePasswordError",
            fields={"error": serializers.CharField()}
        ),
    },
    tags=["认证"],
)
@api_view(['POST'])
@permission_classes([IsAuthenticated])
def change_password(request):
    """修改密码"""
    user = request.user
    old_password = request.data.get('old_password')
    new_password = request.data.get('new_password')

    if not old_password or not new_password:
        return Response(
            {'error': '旧密码和新密码不能为空'},
            status=status.HTTP_400_BAD_REQUEST
        )

    if not user.check_password(old_password):
        return Response(
            {'error': '旧密码错误'},
            status=status.HTTP_400_BAD_REQUEST
        )

    user.set_password(new_password)
    user.save()

    return Response({'message': '密码修改成功'})
