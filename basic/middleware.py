from rest_framework_simplejwt.authentication import JWTAuthentication

class BrowseRecordMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        # 先执行 response 流程，以便在 DRF 进行 JWT 鉴权解析后获取真实的 user
        response = self.get_response(request)

        # 过滤只记录 /api/ 下的请求
        if request.path.startswith('/api/') and request.method != 'OPTIONS':
            # 过滤查看日志本身的接口，避免无限循环生成记录
            if '/api/auth/browse_records/' in request.path:
                return response
                
            user = None
            # 尝试使用 DRF JWTAuthentication 手动提取 user
            try:
                auth = JWTAuthentication()
                header = auth.get_header(request)
                if header:
                    raw_token = auth.get_raw_token(header)
                    validated_token = auth.get_validated_token(raw_token)
                    user = auth.get_user(validated_token)
            except Exception:
                pass
                
            if not user and request.user and request.user.is_authenticated:
                user = request.user

            # 获取 IP
            x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
            if x_forwarded_for:
                ip = x_forwarded_for.split(',')[0].strip()
            else:
                ip = request.META.get('REMOTE_ADDR', '')
                
            from basic.models import BrowseRecord
            try:
                BrowseRecord.objects.create(
                    user=user,
                    path=request.path,
                    method=request.method,
                    ip=ip,
                    user_agent=request.META.get('HTTP_USER_AGENT', '')[:500]
                )
            except Exception:
                pass
                
        return response
