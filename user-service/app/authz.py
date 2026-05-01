from app.models import User


def user_has_permission(user: User, code: str) -> bool:
    if user.is_superuser:
        return True
    for role in user.roles:
        for perm in role.permissions:
            if perm.code == code:
                return True
    return False
