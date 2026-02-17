import json

from maa.agent.agent_server import AgentServer
from maa.context import Context
from maa.custom_action import CustomAction
from maa.pipeline import JTemplateMatch, JRecognitionType, JOCR


@AgentServer.custom_action("TraverseAndExecute")
class TraverseAndExecute(CustomAction):
    """
    通用多目标遍历执行器

    custom_action_param 示例：
    {
        "template":         "target.png",
        "threshold":        0.8,
        "roi":              [0, 200, 1080, 700],
        "action_sequence":  ["TaskA", "TaskB"],
        "after_all":        "TaskC",
        "stop_condition": {
            "type":   "ocr",
            "target": "料理屋",
            "roi":    [0, 0, 500, 100]
        }
    }
    """

    _states: dict = {}  # node_name → {"matches": [...], "index": int}

    def run(
        self,
        context: Context,
        argv: CustomAction.RunArg,
    ) -> CustomAction.RunResult:

    
        # ── 1. 解析参数 ────────────────────────────────────────────
        param: dict = json.loads(argv.custom_action_param) if argv.custom_action_param else {}
        node_name: str = argv.node_name

        template: str         = param.get("template", "")
        threshold: float      = param.get("threshold", 0.8)
        roi                   = param.get("roi")
        action_sequence: list = param.get("action_sequence", [])
        after_all: str        = param.get("after_all", "")
        stop_cond             = param.get("stop_condition")

        # ── 2. 截图（本轮复用）────────────────────────────────────
        image = context.tasker.controller.post_screencap().wait().get()

        # ── 3. 检查终止条件 ────────────────────────────────────────
        if stop_cond and self._check_stop(context, image, stop_cond):
            self._states.pop(node_name, None)
            context.override_pipeline({node_name: {"next": []}})
            return CustomAction.RunResult(success=True)

        # ── 4. 新一轮开始：重新识别所有目标 ───────────────────────
        state = self._states.get(node_name)
        if state is None or state["index"] >= len(state["matches"]):
            matches = self._find_all(context, image, template, threshold, roi)
            self._states[node_name] = {"matches": matches, "index": 0}
            state = self._states[node_name]

            if not matches:
                self._states.pop(node_name, None)
                context.override_pipeline({node_name: {"next": []}})
                return CustomAction.RunResult(success=True)

        # ── 5. 当前轮遍历完：执行 after_all，开启下一轮 ───────────
        if state["index"] >= len(state["matches"]):
            state["index"] = 0
            next_tasks = ([after_all] if after_all else []) + [node_name]
            context.override_pipeline({node_name: {"next": next_tasks}})
            return CustomAction.RunResult(success=True)

        # ── 6. 点击当前目标 ────────────────────────────────────────
        hit = state["matches"][state["index"]]
        x, y, w, h = hit.box
        cx, cy = x + w // 2, y + h // 2
        context.tasker.controller.post_click(cx, cy).wait()
        state["index"] += 1

        # ── 7. 执行动作序列，结束后回到自身继续下一个 ──────────────
        context.override_pipeline({
            node_name: {"next": action_sequence + [node_name]}
        })
        return CustomAction.RunResult(success=True)

    # ── 内部方法 ──────────────────────────────────────────────────

    def _find_all(
        self,
        context: Context,
        image,
        template: str,
        threshold: float,
        roi,
    ) -> list:
        """调用框架内置 TemplateMatch 获取所有匹配结果。"""
        # roi 格式：[x, y, w, h] 或 None
        # JTemplateMatch.roi 接受 tuple (x, y, w, h)，默认 (0,0,0,0) 表示全屏
        reco_param = JTemplateMatch(
            template=[template],
            threshold=[threshold],
            order_by="Score",
            roi=tuple(roi) if roi else (0, 0, 0, 0),
        )

        detail = context.run_recognition_direct(
            JRecognitionType.TemplateMatch,
            reco_param,
            image,
        )
        if not detail or not detail.hit:
            return []

        return detail.all_results

    def _check_stop(
        self,
        context: Context,
        image,
        condition: dict,
    ) -> bool:
        """检查终止条件，支持 ocr 和 template 两种类型。"""
        ctype  = condition.get("type", "ocr")
        target = condition.get("target", "")
        roi    = condition.get("roi")
        roi_t  = tuple(roi) if roi else (0, 0, 0, 0)

        if ctype == "ocr":
            reco_param = JOCR(
                expected=[target],
                roi=roi_t,
            )
            detail = context.run_recognition_direct(
                JRecognitionType.OCR,
                reco_param,
                image,
            )

        elif ctype == "template":
            reco_param = JTemplateMatch(
                template=[target],
                threshold=[condition.get("threshold", 0.8)],
                roi=roi_t,
            )
            detail = context.run_recognition_direct(
                JRecognitionType.TemplateMatch,
                reco_param,
                image,
            )

        else:
            return False

        return bool(detail and detail.hit)