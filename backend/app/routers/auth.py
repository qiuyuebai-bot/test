"""
认证模块 API 路由
提供登录、注册、Token刷新、用户信息、密码修改等接口
"""
from app.utils.datetime import utcnow_naive
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from loguru import logger

from app.database import get_db
from app.models.user import User, UserRoleEnum
from app.schemas.response import success, error, bad_request, unauthorized
from app.schemas.auth import (
    LoginRequest,
    RegisterRequest,
    RefreshTokenRequest,
    ChangePasswordRequest,
)
from app.utils.auth import (
    hash_password,
    verify_password,
    create_tokens_for_user,
    verify_refresh_token,
    get_current_user,
    CurrentUser,
)
from app.utils.logger import LoggerUtil, _sanitize_value

router = APIRouter(prefix="/auth", tags=["认证"])


_AUTH_RESPONSES = {
    400: {"description": "请求参数错误（用户名已占用、邮箱已注册等）"},
    401: {"description": "未授权（凭据无效或Token过期）"},
    422: {"description": "请求体验证失败（字段格式不符合要求）"},
    500: {"description": "服务器内部错误"},
}


def _mask_username(username: str) -> str:
    """脱敏用户名，避免在登录失败日志中暴露完整用户名"""
    if not username:
        return "***"
    return _sanitize_value(username)


# ===========================================
# 1. 用户注册
# ===========================================

@router.post("/register", summary="用户注册", responses=_AUTH_RESPONSES)
def register(
    request: RegisterRequest,
    db: Session = Depends(get_db),
):
    """
    新用户注册
    
    - 默认角色为 learner
    - 密码自动哈希存储
    """
    try:
        # 检查用户名是否已存在
        existing_user = db.query(User).filter(
            User.username == request.username
        ).first()
        if existing_user:
            return bad_request("用户名已被占用")
        
        # 检查邮箱是否已存在
        if request.email:
            existing_email = db.query(User).filter(
                User.email == request.email
            ).first()
            if existing_email:
                return bad_request("邮箱已被注册")
        
        # 验证角色
        role = request.role or "learner"
        valid_roles = [r.value for r in UserRoleEnum]
        if role not in valid_roles:
            return bad_request(f"无效的角色: {role}，支持: {valid_roles}")
        
        # 创建用户
        user = User(
            username=request.username,
            password_hash=hash_password(request.password),
            email=request.email,
            role=UserRoleEnum(role),
            is_active=True,
            is_verified=True,
        )
        db.add(user)
        db.commit()
        db.refresh(user)
        
        # 生成Token
        tokens = create_tokens_for_user(user)
        
        logger.info(f"用户注册成功: username={user.username}, id={user.id}")
        
        return success({
            "user_id": user.id,
            "username": user.username,
            "role": role,
            **tokens,
        }, "注册成功")
        
    except Exception as e:
        logger.error(f"注册失败: {e}")
        db.rollback()
        return error(message=f"注册失败: {str(e)}")


# ===========================================
# 2. 用户登录
# ===========================================

@router.post("/login", summary="用户登录", responses=_AUTH_RESPONSES)
def login(
    request: LoginRequest,
    db: Session = Depends(get_db),
):
    """
    用户登录，返回访问Token和刷新Token
    
    - 支持用户名登录
    - 返回JWT Token对
    """
    try:
        # 查找用户
        user = db.query(User).filter(
            User.username == request.username
        ).first()
        
        if not user:
            logger.warning(f"[登录失败] 用户名不存在: username={_mask_username(request.username)}")
            return unauthorized("用户名或密码错误")
        
        # 验证密码
        if not verify_password(request.password, user.password_hash):
            logger.warning(f"[登录失败] 密码错误: username={_mask_username(request.username)}, user_id={user.id}")
            return unauthorized("用户名或密码错误")
        
        # 检查账户状态
        if not user.is_active:
            logger.warning(f"[登录失败] 账户已禁用: username={_mask_username(request.username)}, user_id={user.id}")
            return unauthorized("账户已被禁用，请联系管理员")
        
        # 更新最后登录时间
        user.last_login_at = utcnow_naive()
        db.commit()
        
        # 生成Token
        tokens = create_tokens_for_user(user)
        
        LoggerUtil.log_api_request(
            "POST /auth/login",
            {"username": request.username},
        )
        
        logger.info(f"用户登录成功: username={user.username}")
        
        return success({
            "user_id": user.id,
            "username": user.username,
            "role": user.role.value if hasattr(user.role, 'value') else user.role,
            **tokens,
        }, "登录成功")
        
    except Exception as e:
        logger.error(f"登录失败: {e}")
        return error(message=f"登录失败: {str(e)}")


# ===========================================
# 3. Token 刷新
# ===========================================

@router.post("/refresh", summary="刷新Token", responses=_AUTH_RESPONSES)
def refresh_token(
    request: RefreshTokenRequest,
    db: Session = Depends(get_db),
):
    """
    使用刷新Token获取新的访问Token
    
    - 刷新Token有效期7天
    - 返回新的访问Token和刷新Token
    """
    try:
        # 验证刷新Token
        payload = verify_refresh_token(request.refresh_token)
        if not payload:
            return unauthorized("刷新Token无效或已过期")
        
        user_id = payload.get("user_id")
        if not user_id:
            return unauthorized("刷新Token数据异常")
        
        # 验证用户状态
        user = db.query(User).filter(User.id == user_id).first()
        if not user:
            return unauthorized("用户不存在")
        
        if not user.is_active:
            return unauthorized("账户已被禁用")
        
        # 生成新Token
        tokens = create_tokens_for_user(user)
        
        logger.info(f"Token刷新成功: user_id={user_id}")
        
        return success(tokens, "Token刷新成功")
        
    except Exception as e:
        logger.error(f"Token刷新失败: {e}")
        return error(message=f"Token刷新失败: {str(e)}")


# ===========================================
# 4. 获取当前用户信息
# ===========================================

@router.get("/me", summary="获取当前用户信息", responses=_AUTH_RESPONSES)
def get_current_user_info(
    current_user: CurrentUser = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    获取当前登录用户的详细信息
    
    - 需要登录
    - 返回用户基本信息、角色、权限等
    """
    try:
        user = db.query(User).filter(User.id == current_user.user_id).first()
        if not user:
            return unauthorized("用户不存在")
        
        return success({
            "user_id": user.id,
            "username": user.username,
            "email": user.email,
            "phone": user.phone,
            "role": user.role.value if hasattr(user.role, 'value') else user.role,
            "is_active": user.is_active,
            "is_verified": user.is_verified,
            "enterprise_name": user.enterprise_name,
            "last_login_at": user.last_login_at.isoformat() if user.last_login_at else None,
            "created_at": user.created_at.isoformat() if user.created_at else None,
        }, "查询成功")
        
    except Exception as e:
        logger.error(f"获取用户信息失败: {e}")
        return error(message=f"获取用户信息失败: {str(e)}")


# ===========================================
# 5. 修改密码
# ===========================================

@router.post("/change-password", summary="修改密码", responses=_AUTH_RESPONSES)
def change_password(
    request: ChangePasswordRequest,
    current_user: CurrentUser = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    修改当前用户密码
    
    - 需要验证旧密码
    - 新密码需满足复杂度要求
    """
    try:
        user = db.query(User).filter(User.id == current_user.user_id).first()
        if not user:
            return unauthorized("用户不存在")
        
        # 验证旧密码
        if not verify_password(request.old_password, user.password_hash):
            return bad_request("旧密码不正确")
        
        # 不能与旧密码相同
        if request.old_password == request.new_password:
            return bad_request("新密码不能与旧密码相同")
        
        # 更新密码
        user.password_hash = hash_password(request.new_password)
        db.commit()
        
        logger.info(f"密码修改成功: user_id={current_user.user_id}")
        
        return success(None, "密码修改成功")
        
    except Exception as e:
        logger.error(f"修改密码失败: {e}")
        db.rollback()
        return error(message=f"修改密码失败: {str(e)}")


# ===========================================
# 6. 登出
# ===========================================

@router.post("/logout", summary="用户登出")
def logout(
    current_user: CurrentUser = Depends(get_current_user),
):
    """
    用户登出（前端清除Token即可，服务端记录登出日志）
    """
    logger.info(f"用户登出: user_id={current_user.user_id}, username={current_user.username}")
    return success(None, "登出成功")


# ===========================================
# 7. 验证Token有效性
# ===========================================

@router.get("/verify", summary="验证Token有效性", responses=_AUTH_RESPONSES)
def verify_token(
    current_user: CurrentUser = Depends(get_current_user),
):
    """
    验证当前Token是否有效
    
    - 用于前端检查登录状态
    - 有效Token返回用户基本信息
    """
    return success({
        "user_id": current_user.user_id,
        "username": current_user.username,
        "role": current_user.role,
        "valid": True,
    }, "Token有效")