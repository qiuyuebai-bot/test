"""
JWT 认证工具模块
提供 Token 生成、校验、密码哈希、鉴权依赖注入
"""
from datetime import timedelta
from app.utils.datetime import utcnow_naive
from typing import Optional, Dict, Any
from jose import JWTError, jwt
import bcrypt
from fastapi import Depends, HTTPException, status, Request
from fastapi.security import OAuth2PasswordBearer, HTTPBearer, HTTPAuthorizationCredentials
from sqlalchemy.orm import Session
from loguru import logger

from app.config import settings
from app.database import get_db
from app.models.user import User, UserRoleEnum


# ===========================================
# 密码哈希工具（直接使用 bcrypt）
# ===========================================

def hash_password(password: str) -> str:
    """
    密码哈希
    
    Args:
        password: 明文密码
        
    Returns:
        哈希后的密码
    """
    # bcrypt 限制密码最大72字节，UTF-8截断
    full_bytes = password.encode("utf-8")
    if len(full_bytes) > 72:
        logger.warning(f"密码长度超过72字节限制，将被静默截断: len={len(full_bytes)}")
    password_bytes = full_bytes[:72]
    salt = bcrypt.gensalt(rounds=12)
    return bcrypt.hashpw(password_bytes, salt).decode("utf-8")


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """
    验证密码
    
    Args:
        plain_password: 明文密码
        hashed_password: 哈希密码
        
    Returns:
        是否匹配
    """
    try:
        full_bytes = plain_password.encode("utf-8")
        if len(full_bytes) > 72:
            logger.warning(f"密码长度超过72字节限制，将被静默截断: len={len(full_bytes)}")
        password_bytes = full_bytes[:72]
        return bcrypt.checkpw(password_bytes, hashed_password.encode("utf-8"))
    except Exception:
        return False


# ===========================================
# OAuth2 Bearer Token 提取器
# ===========================================

oauth2_scheme = OAuth2PasswordBearer(
    tokenUrl=f"{settings.API_PREFIX}/auth/login",
    auto_error=False,
)

security_scheme = HTTPBearer(auto_error=False)


# ===========================================
# JWT Token 工具
# ===========================================

def create_access_token(
    data: Dict[str, Any],
    expires_delta: Optional[timedelta] = None,
) -> str:
    """
    创建访问 Token
    
    Args:
        data: 要编码的数据（user_id, username, role等）
        expires_delta: 过期时间增量
        
    Returns:
        JWT Token 字符串
    """
    to_encode = data.copy()
    
    expire = utcnow_naive() + (
        expires_delta or timedelta(minutes=settings.JWT_EXPIRE_MINUTES)
    )
    to_encode.update({
        "exp": expire,
        "iat": utcnow_naive(),
        "type": "access",
    })
    
    return jwt.encode(
        to_encode,
        settings.SECRET_KEY,
        algorithm=settings.JWT_ALGORITHM,
    )


def create_refresh_token(
    data: Dict[str, Any],
    expires_delta: Optional[timedelta] = None,
) -> str:
    """
    创建刷新 Token
    
    Args:
        data: 要编码的数据
        expires_delta: 过期时间增量
        
    Returns:
        JWT Refresh Token 字符串
    """
    to_encode = data.copy()
    
    expire = utcnow_naive() + (
        expires_delta or timedelta(days=7)
    )
    to_encode.update({
        "exp": expire,
        "iat": utcnow_naive(),
        "type": "refresh",
    })
    
    return jwt.encode(
        to_encode,
        settings.SECRET_KEY,
        algorithm=settings.JWT_ALGORITHM,
    )


def decode_token(token: str) -> Optional[Dict[str, Any]]:
    """
    解码 Token
    
    Args:
        token: JWT Token 字符串
        
    Returns:
        解码后的数据字典，解码失败返回 None
    """
    try:
        payload = jwt.decode(
            token,
            settings.SECRET_KEY,
            algorithms=[settings.JWT_ALGORITHM],
        )
        return payload
    except JWTError as e:
        logger.debug(f"Token解码失败: {e}")
        return None
    except Exception as e:
        logger.error(f"Token解码异常: {e}")
        return None


def verify_access_token(token: str) -> Optional[Dict[str, Any]]:
    """
    验证并解码访问 Token
    
    Args:
        token: JWT Token 字符串
        
    Returns:
        解码后的payload，验证失败返回 None
    """
    payload = decode_token(token)
    if payload is None:
        return None
    
    # 验证 Token 类型
    if payload.get("type") != "access":
        logger.warning("Token类型错误: 期望access_token")
        return None
    
    return payload


def verify_refresh_token(token: str) -> Optional[Dict[str, Any]]:
    """
    验证并解码刷新 Token
    
    Args:
        token: JWT Refresh Token 字符串
        
    Returns:
        解码后的payload，验证失败返回 None
    """
    payload = decode_token(token)
    if payload is None:
        return None
    
    if payload.get("type") != "refresh":
        logger.warning("Token类型错误: 期望refresh_token")
        return None
    
    return payload


def create_tokens_for_user(user: User) -> Dict[str, str]:
    """
    为用户创建访问Token和刷新Token
    
    Args:
        user: 用户对象
        
    Returns:
        包含 access_token 和 refresh_token 的字典
    """
    token_data = {
        "user_id": user.id,
        "username": user.username,
        "role": user.role.value if hasattr(user.role, 'value') else user.role,
    }
    
    access_token = create_access_token(token_data)
    refresh_token = create_refresh_token(token_data)
    
    return {
        "access_token": access_token,
        "refresh_token": refresh_token,
        "token_type": "bearer",
    }


# ===========================================
# 鉴权依赖注入
# ===========================================

class CurrentUser:
    """当前用户信息容器"""
    
    def __init__(self, user_id: int, username: str, role: str):
        self.user_id = user_id
        self.username = username
        self.role = role
    
    @property
    def is_admin(self) -> bool:
        return self.role == UserRoleEnum.ADMIN.value
    
    @property
    def is_teacher(self) -> bool:
        return self.role == UserRoleEnum.TEACHER.value
    
    @property
    def is_learner(self) -> bool:
        return self.role == UserRoleEnum.LEARNER.value
    
    @property
    def is_enterprise(self) -> bool:
        return self.role == UserRoleEnum.ENTERPRISE.value
    
    def has_role(self, *roles: str) -> bool:
        return self.role in roles


def get_token_from_request(
    request: Request,
    credentials: Optional[HTTPAuthorizationCredentials] = None,
    token: Optional[str] = None,
) -> Optional[str]:
    """
    从请求中提取 Token（支持多种方式）
    
    优先级: Header > OAuth2 > Query参数
    
    Args:
        request: FastAPI Request对象
        credentials: HTTPBearer凭据
        token: OAuth2PasswordBearer提取的token
        
    Returns:
        Token字符串或None
    """
    # 方式1: Authorization Header (Bearer)
    if credentials:
        return credentials.credentials
    
    # 方式2: OAuth2PasswordBearer
    if token:
        return token
    
    # 方式3: 从请求头直接读取
    auth_header = request.headers.get("Authorization")
    if auth_header and auth_header.startswith("Bearer "):
        return auth_header.replace("Bearer ", "")
    
    # 方式4: 从查询参数读取（用于WebSocket或文件下载等场景）
    query_token = request.query_params.get("token")
    if query_token:
        return query_token
    
    return None


async def get_current_user(
    request: Request,
    db: Session = Depends(get_db),
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(security_scheme),
    token: Optional[str] = Depends(oauth2_scheme),
) -> CurrentUser:
    """
    获取当前登录用户（强制鉴权）
    
    用于需要登录的接口，未登录返回401
    
    Raises:
        HTTPException: 未登录或Token无效
    """
    token_str = get_token_from_request(request, credentials, token)
    
    if not token_str:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="未提供认证Token",
            headers={"WWW-Authenticate": "Bearer"},
        )
    
    payload = verify_access_token(token_str)
    if not payload:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token无效或已过期",
            headers={"WWW-Authenticate": "Bearer"},
        )
    
    user_id = payload.get("user_id")
    if user_id is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token数据异常",
            headers={"WWW-Authenticate": "Bearer"},
        )
    
    # 验证用户是否存在且激活
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="用户不存在",
            headers={"WWW-Authenticate": "Bearer"},
        )
    
    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="用户已被禁用",
            headers={"WWW-Authenticate": "Bearer"},
        )
    
    return CurrentUser(
        user_id=user.id,
        username=user.username,
        role=user.role.value if hasattr(user.role, 'value') else user.role,
    )


async def get_current_user_optional(
    request: Request,
    db: Session = Depends(get_db),
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(security_scheme),
    token: Optional[str] = Depends(oauth2_scheme),
) -> Optional[CurrentUser]:
    """
    获取当前登录用户（可选鉴权）
    
    用于登录非必须的接口，未登录返回None
    """
    try:
        token_str = get_token_from_request(request, credentials, token)
        if not token_str:
            return None
        
        payload = verify_access_token(token_str)
        if not payload:
            return None
        
        user_id = payload.get("user_id")
        if user_id is None:
            return None
        
        user = db.query(User).filter(User.id == user_id).first()
        if not user or not user.is_active:
            return None
        
        return CurrentUser(
            user_id=user.id,
            username=user.username,
            role=user.role.value if hasattr(user.role, 'value') else user.role,
        )
    except Exception:
        return None


def require_role(*roles: str):
    """
    角色权限校验依赖工厂
    
    用法:
        @router.get("/admin")
        def admin_endpoint(
            current_user: CurrentUser = Depends(require_role("admin", "teacher"))
        ):
            ...
    
    Args:
        *roles: 允许访问的角色列表
        
    Returns:
        FastAPI依赖函数
    """
    async def role_checker(
        current_user: CurrentUser = Depends(get_current_user),
    ) -> CurrentUser:
        if current_user.role not in roles:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"权限不足，需要角色: {', '.join(roles)}",
            )
        return current_user
    
    return role_checker


# ===========================================
# 便捷鉴权装饰器
# ===========================================

# 管理员权限
require_admin = require_role(UserRoleEnum.ADMIN.value)

# 教师/管理员权限
require_teacher = require_role(UserRoleEnum.ADMIN.value, UserRoleEnum.TEACHER.value)

# 企业管理员权限
require_enterprise = require_role(UserRoleEnum.ADMIN.value, UserRoleEnum.ENTERPRISE.value)