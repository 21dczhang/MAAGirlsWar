# 在这里导入所有自定义 action / recognition
# import 即触发 @AgentServer 装饰器完成注册

from .action.traverse import TraverseAndExecute  # noqa: F401

__all__ = ["TraverseAndExecute"]
