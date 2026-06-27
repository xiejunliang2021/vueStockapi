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


import uuid
from django.contrib.auth.models import User
from basic.models import UserKey, BrowseRecord

@extend_schema(
    summary="Key登录",
    description="提交Key，返回 JWT Access Token 和 User 信息。",
    request=inline_serializer(
        name="KeyLoginRequest",
        fields={"key": serializers.CharField(help_text="登录密钥")}
    ),
    responses={
        200: inline_serializer(
            name="KeyLoginResponse",
            fields={
                "access": serializers.CharField(),
                "refresh": serializers.CharField(),
                "user": inline_serializer(
                    name="KeyUserInfo",
                    fields={
                        "id": serializers.IntegerField(),
                        "username": serializers.CharField(),
                        "email": serializers.EmailField(),
                        "is_superuser": serializers.BooleanField(),
                    }
                )
            }
        ),
        400: inline_serializer(
            name="KeyLoginError",
            fields={"error": serializers.CharField()}
        )
    },
    tags=["认证"]
)
@api_view(['POST'])
@permission_classes([AllowAny])
def login_by_key(request):
    key_str = request.data.get('key')
    if not key_str:
        return Response({'error': 'Key不能为空'}, status=status.HTTP_400_BAD_REQUEST)
        
    try:
        user_key = UserKey.objects.select_related('user').get(key=key_str)
        user = user_key.user
        if not user.is_active:
            return Response({'error': '该Key关联的用户已被禁用'}, status=status.HTTP_400_BAD_REQUEST)
    except UserKey.DoesNotExist:
        return Response({'error': '无效的Key'}, status=status.HTTP_400_BAD_REQUEST)

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


@extend_schema(
    summary="生成Key",
    description="管理员为特定用户生成登录Key。",
    request=inline_serializer(
        name="GenerateKeyRequest",
        fields={"username": serializers.CharField(help_text="目标用户名")}
    ),
    responses={
        200: inline_serializer(
            name="GenerateKeyResponse",
            fields={
                "username": serializers.CharField(),
                "key": serializers.CharField(),
                "created": serializers.BooleanField()
            }
        ),
        403: inline_serializer(name="GenKeyForbidden", fields={"error": serializers.CharField()})
    },
    tags=["认证"]
)
@api_view(['POST'])
@permission_classes([IsAuthenticated])
def generate_key(request):
    if not request.user.is_superuser and not request.user.is_staff:
        return Response({'error': '权限不足，只有管理员可以生成Key'}, status=status.HTTP_403_FORBIDDEN)
        
    target_username = request.data.get('username')
    if not target_username:
        return Response({'error': '目标用户名不能为空'}, status=status.HTTP_400_BAD_REQUEST)
        
    try:
        target_user = User.objects.get(username=target_username)
    except User.DoesNotExist:
        return Response({'error': '目标用户不存在'}, status=status.HTTP_400_BAD_REQUEST)
        
    new_key_str = str(uuid.uuid4()).replace('-', '')
    
    user_key, created = UserKey.objects.update_or_create(
        user=target_user,
        defaults={'key': new_key_str}
    )
    
    return Response({
        'username': target_user.username,
        'key': new_key_str,
        'created': created
    }, status=status.HTTP_200_OK)


@extend_schema(
    summary="查看所有用户的浏览记录",
    description="管理员可以查看系统中所有用户的最新500条浏览历史记录。",
    responses={
        200: inline_serializer(
            name="BrowseRecordListResponse",
            fields={
                "id": serializers.IntegerField(),
                "username": serializers.CharField(),
                "path": serializers.CharField(),
                "method": serializers.CharField(),
                "ip": serializers.CharField(),
                "user_agent": serializers.CharField(),
                "created_at": serializers.CharField()
            }
        )
    },
    tags=["审计"]
)
@api_view(['GET'])
@permission_classes([IsAuthenticated])
def get_browse_records(request):
    if not request.user.is_superuser and not request.user.is_staff:
        return Response({'error': '权限不足，只有管理员可以查看浏览记录'}, status=status.HTTP_403_FORBIDDEN)
        
    records = BrowseRecord.objects.select_related('user').all()[:500]
    res_list = []
    for r in records:
        res_list.append({
            'id': r.id,
            'username': r.user.username if r.user else 'Anonymous',
            'path': r.path,
            'method': r.method,
            'ip': r.ip,
            'user_agent': r.user_agent,
            'created_at': r.created_at.strftime('%Y-%m-%d %H:%M:%S')
        })
    return Response(res_list, status=status.HTTP_200_OK)
