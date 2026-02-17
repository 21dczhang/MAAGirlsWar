import json

from maa.agent.agent_server import AgentServer
from maa.context import Context
from maa.custom_action import CustomAction
from maa.pipeline import JTemplateMatch, JRecognitionType, JOCR
from utils.mfaalog import info, warning, error


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
        node_name: str = argv.node_name
        info(f"[TraverseAndExecute] 节点开始执行: {node_name}")
        
        try:
            param: dict = json.loads(argv.custom_action_param) if argv.custom_action_param else {}
        except json.JSONDecodeError as e:
            error(f"[TraverseAndExecute] 参数解析失败: {e}")
            return CustomAction.RunResult(success=False)
        
        template: str         = param.get("template", "")
        threshold: float      = param.get("threshold", 0.8)
        roi                   = param.get("roi")
        action_sequence: list = param.get("action_sequence", [])
        after_all: str        = param.get("after_all", "")
        stop_cond             = param.get("stop_condition")

        info(f"[TraverseAndExecute] 参数: template={template}, threshold={threshold}, roi={roi}")
        info(f"[TraverseAndExecute] 动作序列: {action_sequence}, after_all={after_all}")

        # ── 2. 截图（本轮复用）────────────────────────────────────
        try:
            image = context.tasker.controller.post_screencap().wait().get()
            info(f"[TraverseAndExecute] 截图成功")
        except Exception as e:
            error(f"[TraverseAndExecute] 截图失败: {e}")
            return CustomAction.RunResult(success=False)

        # ── 3. 检查终止条件 ────────────────────────────────────────
        if stop_cond:
            info(f"[TraverseAndExecute] 检查终止条件: {stop_cond}")
            if self._check_stop(context, image, stop_cond):
                info(f"[TraverseAndExecute] 满足终止条件，清理状态并退出")
                self._states.pop(node_name, None)
                context.override_pipeline({node_name: {"next": []}})
                return CustomAction.RunResult(success=True)
            else:
                info(f"[TraverseAndExecute] 未满足终止条件，继续执行")

        # ── 4. 新一轮开始：重新识别所有目标 ───────────────────────
        state = self._states.get(node_name)
        if state is None or state["index"] >= len(state["matches"]):
            info(f"[TraverseAndExecute] 开始新一轮目标识别 (state={state is not None})")
            matches = self._find_all(context, image, template, threshold, roi)
            info(f"[TraverseAndExecute] 识别到 {len(matches)} 个目标")
            
            self._states[node_name] = {"matches": matches, "index": 0}
            state = self._states[node_name]

            if not matches:
                warning(f"[TraverseAndExecute] 未找到任何匹配目标，结束遍历")
                self._states.pop(node_name, None)
                context.override_pipeline({node_name: {"next": []}})
                return CustomAction.RunResult(success=True)

        # ── 5. 当前轮遍历完：执行 after_all，开启下一轮 ───────────
        if state["index"] >= len(state["matches"]):
            info(f"[TraverseAndExecute] 当前轮遍历完成 (共 {len(state['matches'])} 个目标)")
            state["index"] = 0
            next_tasks = ([after_all] if after_all else []) + [node_name]
            info(f"[TraverseAndExecute] 下一轮任务序列: {next_tasks}")
            context.override_pipeline({node_name: {"next": next_tasks}})
            return CustomAction.RunResult(success=True)

        # ── 6. 点击当前目标 ────────────────────────────────────────
        hit = state["matches"][state["index"]]
        x, y, w, h = hit.box
        cx, cy = x + w // 2, y + h // 2
        info(f"[TraverseAndExecute] 点击目标 #{state['index']+1}/{len(state['matches'])} @ ({cx}, {cy}) [box: {x},{y},{w},{h}]")
        
        try:
            context.tasker.controller.post_click(cx, cy).wait()
        except Exception as e:
            error(f"[TraverseAndExecute] 点击失败: {e}")
            return CustomAction.RunResult(success=False)
        
        state["index"] += 1

        # ── 7. 执行动作序列，结束后回到自身继续下一个 ──────────────
        next_pipeline = action_sequence + [node_name]
        info(f"[TraverseAndExecute] 设置后续任务序列: {next_pipeline}")
        context.override_pipeline({
            node_name: {"next": next_pipeline}
        })
        info(f"[TraverseAndExecute] 节点执行完成")
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
        info(f"[TraverseAndExecute._find_all] 开始模板匹配: template={template}, threshold={threshold}, roi={roi}")
        
        # roi 格式：[x, y, w, h] 或 None
        # JTemplateMatch.roi 接受 tuple (x, y, w, h)，默认 (0,0,0,0) 表示全屏
        reco_param = JTemplateMatch(
            template=[template],
            threshold=[threshold],
            order_by="Score",
            roi=tuple(roi) if roi else (0, 0, 0, 0),
        )

        try:
            detail = context.run_recognition_direct(
                JRecognitionType.TemplateMatch,
                reco_param,
                image,
            )
        except Exception as e:
            error(f"[TraverseAndExecute._find_all] 模板匹配异常: {e}")
            return []

        if not detail or not detail.hit:
            info(f"[TraverseAndExecute._find_all] 未匹配到任何目标")
            return []

        result_count = len(detail.all_results) if detail.all_results else 0
        info(f"[TraverseAndExecute._find_all] 匹配成功，共 {result_count} 个结果")
        
        # 打印每个匹配结果的详细信息（debug 级别可用）
        if detail.all_results:
            for i, res in enumerate(detail.all_results[:5]):  # 只打印前5个避免日志过多
                info(f"[TraverseAndExecute._find_all]   结果#{i+1}: box={res.box}, score={getattr(res, 'score', 'N/A')}")
            if len(detail.all_results) > 5:
                info(f"[TraverseAndExecute._find_all]   ... 还有 {len(detail.all_results) - 5} 个结果")

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

        info(f"[TraverseAndExecute._check_stop] 检查终止条件: type={ctype}, target={target}, roi={roi}")

        try:
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
                hit = bool(detail and detail.hit)
                info(f"[TraverseAndExecute._check_stop] OCR 识别结果: {'命中' if hit else '未命中'}")

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
                hit = bool(detail and detail.hit)
                info(f"[TraverseAndExecute._check_stop] 模板匹配结果: {'命中' if hit else '未命中'}")

            else:
                warning(f"[TraverseAndExecute._check_stop] 未知的终止条件类型: {ctype}")
                return False

            return hit
            
        except Exception as e:
            error(f"[TraverseAndExecute._check_stop] 终止条件检查异常: {e}")
            return False