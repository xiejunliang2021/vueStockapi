from django.contrib.auth import get_user_model

User = get_user_model()

# 创建超级用户（如果不存在）
if not User.objects.filter(username='admin').exists():
    user = User.objects.create_superuser(
        username='admin',
        email='admin@example.com',
        password='admin123456'
    )
    print(f"✅ 超级用户创建成功: {user.username}")
else:
    print("ℹ️  超级用户 'admin' 已存在")
