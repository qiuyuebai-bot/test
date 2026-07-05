"""
Agent 基类
定义所有智能体的通用接口和基础能力
"""
import time
from abc import ABC, abstractmethod
from typing import Dict, Any, Optional
from loguru import logger


class AgentStatus:
    """Agent状态枚举"""
    IDLE = "idle"           # 空闲
    RUNNING = "running"     # 执行中
    VALIDATING = "validating"  # 校验中
    ERROR = "error"         # 报错


class BaseAgent(ABC):
    """
    Agent 抽象基类
    
    所有智能体必须继承此类并实现 execute 方法
    """
    
    def __init__(self, agent_type: str, agent_name: str):
        """
        初始化Agent
        
        Args:
            agent_type: Agent类型标识
            agent_name: Agent显示名称
        """
        self.agent_type = agent_type
        self.agent_name = agent_name
        self.status = AgentStatus.IDLE
        self.current_task_id: Optional[int] = None
        self.last_error: Optional[str] = None
        self.execution_log = []
    
    @abstractmethod
    def execute(self, input_data: Dict[str, Any], context: Dict[str, Any] = None) -> Dict[str, Any]:
        """
        执行Agent核心逻辑（抽象方法，子类必须实现）
        
        Args:
            input_data: 输入数据
            context: 上下文数据（可选）
            
        Returns:
            执行结果字典
        """
        pass
    
    def run(self, task_id: int, input_data: Dict[str, Any], context: Dict[str, Any] = None) -> Dict[str, Any]:
        """
        运行Agent（带状态管理和日志记录）
        
        Args:
            task_id: 任务ID
            input_data: 输入数据
            context: 上下文数据
            
        Returns:
            执行结果字典
        """
        self.status = AgentStatus.RUNNING
        self.current_task_id = task_id
        self.last_error = None
        
        start_time = time.time()
        
        log_entry = {
            "agent_type": self.agent_type,
            "agent_name": self.agent_name,
            "task_id": task_id,
            "action": "start",
            "timestamp": time.strftime("%Y-%m-%d %H:%M:%S"),
        }
        self._add_log(log_entry)
        
        logger.info(f"[{self.agent_name}] 开始执行任务: task_id={task_id}")
        
        try:
            result = self.execute(input_data, context)
            
            duration_ms = int((time.time() - start_time) * 1000)
            result["_meta"] = {
                "agent_type": self.agent_type,
                "agent_name": self.agent_name,
                "duration_ms": duration_ms,
                "success": True,
            }
            
            self.status = AgentStatus.IDLE
            
            log_entry = {
                "agent_type": self.agent_type,
                "agent_name": self.agent_name,
                "task_id": task_id,
                "action": "complete",
                "duration_ms": duration_ms,
                "timestamp": time.strftime("%Y-%m-%d %H:%M:%S"),
            }
            self._add_log(log_entry)
            
            logger.info(f"[{self.agent_name}] 任务完成: task_id={task_id}, duration={duration_ms}ms")
            
            return result
            
        except Exception as e:
            self.status = AgentStatus.ERROR
            self.last_error = str(e)
            
            duration_ms = int((time.time() - start_time) * 1000)
            
            log_entry = {
                "agent_type": self.agent_type,
                "agent_name": self.agent_name,
                "task_id": task_id,
                "action": "error",
                "error": str(e),
                "duration_ms": duration_ms,
                "timestamp": time.strftime("%Y-%m-%d %H:%M:%S"),
            }
            self._add_log(log_entry)
            
            logger.error(f"[{self.agent_name}] 任务失败: task_id={task_id}, error={e}")
            
            return {
                "success": False,
                "error": str(e),
                "_meta": {
                    "agent_type": self.agent_type,
                    "agent_name": self.agent_name,
                    "duration_ms": duration_ms,
                    "success": False,
                }
            }
    
    def validate(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """
        校验输出数据质量
        
        Args:
            data: 待校验的数据
            
        Returns:
            校验结果
        """
        self.status = AgentStatus.VALIDATING
        
        result = {
            "passed": True,
            "issues": [],
            "score": 100,
        }
        
        # 基础校验
        if not data or not isinstance(data, dict):
            result["passed"] = False
            result["issues"].append("输出数据为空或格式错误")
            result["score"] = 0
        
        self.status = AgentStatus.IDLE
        
        return result
    
    def get_status(self) -> Dict[str, Any]:
        """
        获取Agent状态信息
        
        Returns:
            状态字典
        """
        return {
            "agent_type": self.agent_type,
            "agent_name": self.agent_name,
            "status": self.status,
            "current_task_id": self.current_task_id,
            "last_error": self.last_error,
        }
    
    def _add_log(self, log_entry: Dict[str, Any]) -> None:
        """
        添加执行日志
        
        Args:
            log_entry: 日志条目
        """
        self.execution_log.append(log_entry)
        # 最多保留100条日志
        if len(self.execution_log) > 100:
            self.execution_log = self.execution_log[-100:]
    
    def reset(self) -> None:
        """
        重置Agent状态
        """
        self.status = AgentStatus.IDLE
        self.current_task_id = None
        self.last_error = None
    
    def __repr__(self) -> str:
        return f"<{self.__class__.__name__}(type={self.agent_type}, status={self.status})>"