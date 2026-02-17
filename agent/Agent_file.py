"""
Agent调试启动器
该文件的作用为：
将自定义的Agent功能注册到Agent服务器中，便于在调试时使用
"""

from maa.agent.agent_server import AgentServer

from custom.action.Count import Count
from custom.action.ScreenShot import ScreenShot,CheckResolution
from custom.action.Node import DisableNode,NodeOverride
from custom.action.Traverse import TraverseAndExecute

@AgentServer.custom_action("TraverseAndExecute")
class Agent_TraverseAndExecute(TraverseAndExecute):
    pass

@AgentServer.custom_action("Count")
class Agent_Count(Count):
    pass


@AgentServer.custom_action("DisableNode")
class Agent_DisableNode(DisableNode):
    pass

@AgentServer.custom_action("NodeOverride")
class Agent_DisableNode(NodeOverride):
    pass


@AgentServer.custom_action("ScreenShot")
class Agent_ScreenShot(ScreenShot):
    pass

@AgentServer.custom_action("CheckResolution")
class Agent_CheckResolution(CheckResolution):
    pass