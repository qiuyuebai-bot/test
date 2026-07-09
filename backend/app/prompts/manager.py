"""
Prompt 模板管理器（P3-4）

特性：
1. 文件级模板：所有 prompt 集中存放于 backend/app/prompts/templates/*.txt
2. 双段模板：单个 .txt 文件可包含 `--- SYSTEM ---` 与 `--- USER ---` 分隔符，
   分别对应 system_prompt 与 user_prompt；仅一段时整体作为 user_prompt
3. 安全渲染：使用 str.format_map + defaultdict 兜底，缺失变量返回空字符串
4. 版本管理：manifest.json 记录每个模板的 version、description、variables
5. 缓存加载：模板文件读取后缓存在内存，避免重复 IO
"""
import json
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple
from threading import RLock

from loguru import logger


_PROMPTS_DIR: Path = Path(__file__).parent / "templates"
_MANIFEST_PATH: Path = Path(__file__).parent / "manifest.json"

_SYSTEM_DELIMITER = "--- SYSTEM ---"
_USER_DELIMITER = "--- USER ---"


class _SafeDict(dict):
    """缺失键返回空字符串，避免 format_map 抛 KeyError"""

    def __missing__(self, key: str) -> str:
        logger.warning(f"[PromptManager] 模板变量缺失: {key}")
        return ""


class RenderedPrompt:
    """渲染后的 prompt（包含 system 与 user 两段）"""

    __slots__ = ("text", "system_prompt", "user_prompt", "version", "name")

    def __init__(
        self,
        text: str,
        system_prompt: Optional[str],
        user_prompt: str,
        version: str,
        name: str,
    ):
        # text: 完整的渲染后文本（如果 system_prompt 存在则为 user_prompt，否则为整个内容）
        # 兼容旧调用：text 与 user_prompt 一致
        self.text = text
        self.system_prompt = system_prompt
        self.user_prompt = user_prompt
        self.version = version
        self.name = name

    def __repr__(self) -> str:
        return (
            f"RenderedPrompt(name={self.name!r}, version={self.version!r}, "
            f"system_len={len(self.system_prompt or '')}, user_len={len(self.user_prompt)})"
        )


class PromptManager:
    """Prompt 模板管理器"""

    _template_cache: Dict[str, str] = {}
    _manifest_cache: Optional[Dict[str, Any]] = None
    _lock: RLock = RLock()

    # ===========================================
    # 模板加载（带内存缓存）
    # ===========================================

    @classmethod
    def _load_template_raw(cls, name: str) -> str:
        """从磁盘加载模板原始内容（带缓存）"""
        with cls._lock:
            if name in cls._template_cache:
                return cls._template_cache[name]

            path = _PROMPTS_DIR / f"{name}.txt"
            if not path.exists():
                raise FileNotFoundError(f"Prompt 模板不存在: {path}")
            content = path.read_text(encoding="utf-8")
            cls._template_cache[name] = content
            return content

    @classmethod
    def _load_manifest(cls) -> Dict[str, Any]:
        """加载 manifest.json（带缓存）"""
        if cls._manifest_cache is not None:
            return cls._manifest_cache
        with cls._lock:
            if cls._manifest_cache is not None:
                return cls._manifest_cache
            if _MANIFEST_PATH.exists():
                try:
                    cls._manifest_cache = json.loads(
                        _MANIFEST_PATH.read_text(encoding="utf-8")
                    )
                except json.JSONDecodeError as e:
                    logger.error(f"[PromptManager] manifest.json 解析失败: {e}")
                    cls._manifest_cache = {}
            else:
                cls._manifest_cache = {}
            return cls._manifest_cache

    @classmethod
    def _split_segments(cls, raw: str) -> Tuple[Optional[str], str]:
        """
        将模板原始内容切分为 (system_prompt, user_prompt)

        支持 3 种格式：
        1. 无分隔符 → (None, 全部内容)
        2. 仅 --- SYSTEM --- → (system 段, 其余作为 user)
        3. 仅 --- USER --- → (None, user 段)
        4. 同时包含两者 → (system 段, user 段)
        """
        has_system = _SYSTEM_DELIMITER in raw
        has_user = _USER_DELIMITER in raw

        if not has_system and not has_user:
            return None, raw.strip()

        system_part: Optional[str] = None
        user_part: str = ""

        if has_system:
            sys_idx = raw.find(_SYSTEM_DELIMITER)
            sys_end = sys_idx + len(_SYSTEM_DELIMITER)
            # 系统段从分隔符后开始，到 USER 分隔符前结束
            if has_user:
                usr_idx = raw.find(_USER_DELIMITER)
                if usr_idx > sys_idx:
                    system_part = raw[sys_end:usr_idx].strip()
                    user_part = raw[usr_idx + len(_USER_DELIMITER):].strip()
                else:
                    # USER 在 SYSTEM 前，分别提取
                    user_part = raw[len(_USER_DELIMITER):sys_idx].strip()
                    system_part = raw[sys_end:].strip()
            else:
                system_part = raw[sys_end:].strip()
        else:
            # 仅有 USER 分隔符
            usr_idx = raw.find(_USER_DELIMITER)
            user_part = raw[usr_idx + len(_USER_DELIMITER):].strip()

        return system_part, user_part

    # ===========================================
    # 公共 API
    # ===========================================

    @classmethod
    def render(cls, name: str, **variables: Any) -> RenderedPrompt:
        """
        加载并渲染 prompt 模板

        Args:
            name: 模板名（不含 .txt 扩展名）
            **variables: 模板变量

        Returns:
            RenderedPrompt 对象

        Raises:
            FileNotFoundError: 模板不存在
        """
        raw = cls._load_template_raw(name)
        system_raw, user_raw = cls._split_segments(raw)

        safe_vars = _SafeDict(variables)
        system_rendered = system_raw.format_map(safe_vars) if system_raw else None
        user_rendered = user_raw.format_map(safe_vars) if user_raw else ""

        manifest = cls._load_manifest()
        entry = manifest.get(name, {})
        version = entry.get("version", "1.0.0")

        return RenderedPrompt(
            text=user_rendered,
            system_prompt=system_rendered,
            user_prompt=user_rendered,
            version=version,
            name=name,
        )

    @classmethod
    def get_version(cls, name: str) -> str:
        """获取模板版本号"""
        manifest = cls._load_manifest()
        return manifest.get(name, {}).get("version", "1.0.0")

    @classmethod
    def get_description(cls, name: str) -> str:
        """获取模板描述"""
        manifest = cls._load_manifest()
        return manifest.get(name, {}).get("description", "")

    @classmethod
    def list_templates(cls) -> List[str]:
        """列出所有已注册的模板名（跳过以下划线开头的元字段）"""
        manifest = cls._load_manifest()
        return sorted(k for k in manifest.keys() if not k.startswith("_"))

    @classmethod
    def clear_cache(cls) -> None:
        """清空模板缓存（开发期热加载用）"""
        with cls._lock:
            cls._template_cache.clear()
            cls._manifest_cache = None
