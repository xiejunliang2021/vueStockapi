"""
认证相关 API Views
"""
from rest_framework import status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.response import Response
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework_simplejwt.tokens import RefreshToken
from django.contrib.auth import authenticate


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


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def logout(request):
    """登出（主要是前端清除 Token）"""
    return Response({'message': '登出成功'})


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
