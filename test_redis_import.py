import redis
import sys
try:
    print(f"Redis module: {redis}")
    print(f"Redis class: {redis.Redis}")
    r = redis.Redis(host='localhost', port=6379, db=0)
    print(f"Redis connection: {r.ping()}")
except Exception as e:
    print(f"Error: {e}")
    import traceback
    traceback.print_exc()
