DEBUG = True
def debug(*args, **kwargs):
    if not DEBUG: return
    print(*args, **kwargs)
