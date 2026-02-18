"""
Custom Action: TraverseAndClick
================================
功能：
  1. 用模板匹配或 OCR 识别当前屏幕，收集所有 score > threshold 的结果
  2. 若无匹配项，执行 task_after_round 后继续下一轮
  3. 遍历所有匹配结果：点击中心 → 执行 task_each
  4. 遍历完成后重新截图检查终止条件，满足则退出
  5. 不满足终止条件则执行 task_after_round，进入下一轮
  6. 达到 max_rounds 上限时强制退出

Pipeline JSON 调用示例：
─────────────────────────────────────────────────────────────
{
    "StartTraverse": {
        "action": "Custom",
        "custom_action": "TraverseAndClick",
        "custom_action_param": {

            // ── 识别方式 ──────────────────────────────────────
            // "method": "template" | "ocr"
            "method": "template",

            // [template] 待匹配的模板图片文件名（resource 目录下的路径）
            "template": "items/target_item.png",

            // [ocr] 待匹配的文字列表，命中其中任意一项即算匹配
            // "ocr_text": ["词A", "词B"],

            // 匹配分数阈值（0~1），高于此值才纳入遍历
            "threshold": 0.85,

            // 主识别 ROI，格式 [x, y, w, h]，不传则默认全屏
            // "roi": [100, 200, 800, 600],

            // ── 终止条件 ──────────────────────────────────────
            // "stop_method": "template" | "ocr"
            "stop_method": "template",

            // [template] 终止条件：识别到该图片则停止
            "stop_template": "ui/end_screen.png",

            // [ocr] 终止条件：OCR 识别到包含以下任一字符串则停止
            // "stop_ocr_text": ["结束", "完成"],

            // 终止条件识别 ROI，格式 [x, y, w, h]，不传则默认全屏
            // "stop_roi": [0, 0, 400, 100],

            // ── 任务配置 ──────────────────────────────────────
            // 点击每个匹配项后执行的任务节点名
            "task_each": "TaskA",

            // 每轮遍历全部结束后执行的任务节点名
            "task_after_round": "TaskC",

            // ── 可选配置 ──────────────────────────────────────
            // 两次识别之间的等待时间（秒），默认 0.5
            "round_delay": 0.5,

            // 每次点击后、执行 task_each 前的等待时间（秒），默认 0.3
            "click_delay": 0.3,

            // 最大循环轮数，防止死循环，默认 50，设为 -1 表示不限制
            "max_rounds": 50
        }
    }
}
─────────────────────────────────────────────────────────────
"""

import json
import time
import logging
import sys
from typing import Optional, Union

from maa.agent.agent_server import AgentServer
from maa.custom_action import CustomAction
from maa.context import Context


def _setup_logger() -> logging.Logger:
    log = logging.getLogger("MAAProject")
    log.setLevel(logging.DEBUG)

    handler = logging.StreamHandler(sys.stdout)
    handler.setLevel(logging.DEBUG)

    fmt = logging.Formatter(
        "[%(asctime)s][%(levelname)s] %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )
    handler.setFormatter(fmt)
    log.addHandler(handler)
    return log


logger = _setup_logger()


@AgentServer.custom_action("TraverseAndClick")
class TraverseAndClick(CustomAction):

    def run(
        self,
        context: Context,
        argv: CustomAction.RunArg,
    ) -> CustomAction.RunResult:

        # ── 解析参数 ────────────────────────────────────────────
        try:
            param: dict = json.loads(argv.custom_action_param)
        except (json.JSONDecodeError, TypeError) as e:
            logger.error(f"[TraverseAndClick] 参数解析失败: {e}")
            return CustomAction.RunResult(success=False)

        method: str           = param.get("method", "template")          # "template" | "ocr"
        template: str         = param.get("template", "")                # 模板图片路径
        ocr_text: list        = param.get("ocr_text", [])                # OCR 目标词列表
        threshold: float      = float(param.get("threshold", 0.8))       # 匹配阈值
        roi: list | None      = param.get("roi", None)                   # 主识别 ROI [x,y,w,h]，None 表示全屏

        stop_method: str      = param.get("stop_method", "template")     # 终止条件识别方式
        stop_template: str    = param.get("stop_template", "")           # 终止条件模板图片
        stop_ocr_text: list   = param.get("stop_ocr_text", [])           # 终止条件 OCR 词列表
        stop_roi: list | None = param.get("stop_roi", None)              # 终止条件 ROI [x,y,w,h]，None 表示全屏

        task_each: str        = param.get("task_each", "")               # 每项匹配后执行的任务
        task_after_round: str = param.get("task_after_round", "")        # 每轮结束后执行的任务

        round_delay: float    = float(param.get("round_delay", 0.5))     # 两轮之间等待（秒）
        click_delay: float    = float(param.get("click_delay", 0.3))     # 点击后等待（秒）
        max_rounds: int       = int(param.get("max_rounds", 50))         # 最大轮数

        # ── 参数校验 ────────────────────────────────────────────
        if method == "template" and not template:
            logger.error("[TraverseAndClick] method=template 时必须提供 template 参数")
            return CustomAction.RunResult(success=False)

        if method == "ocr" and not ocr_text:
            logger.error("[TraverseAndClick] method=ocr 时必须提供 ocr_text 参数")
            return CustomAction.RunResult(success=False)

        if not task_each:
            logger.error("[TraverseAndClick] 必须提供 task_each 参数")
            return CustomAction.RunResult(success=False)

        # ── 主循环 ──────────────────────────────────────────────
        round_count = 0

        while max_rounds < 0 or round_count < max_rounds:
            round_count += 1
            logger.info(f"[TraverseAndClick] ── 第 {round_count} 轮 ──")

            # 1. 截图
            img = context.tasker.controller.post_screencap().wait().get()

            # 2. 识别目标，获取所有匹配项
            matches = self._recognize_all(context, img, method, template, ocr_text, threshold, roi)

            if not matches:
                logger.info("[TraverseAndClick] 本轮无匹配项，执行 task_after_round 后继续")
                if task_after_round:
                    context.run_task(task_after_round)
                if round_delay > 0:
                    time.sleep(round_delay)
                continue

            logger.info(f"[TraverseAndClick] 本轮匹配到 {len(matches)} 个目标")

            # 3. 遍历每个匹配项
            for idx, (cx, cy) in enumerate(matches):
                logger.info(f"[TraverseAndClick]   [{idx + 1}/{len(matches)}] 点击 ({cx}, {cy})")

                # 点击匹配区域中心
                context.tasker.controller.post_click(cx, cy).wait()

                if click_delay > 0:
                    time.sleep(click_delay)

                # 执行 task_each
                if task_each:
                    context.run_task(task_each)

            # 4. 遍历完毕后，重新截图检查终止条件
            img = context.tasker.controller.post_screencap().wait().get()
            if self._check_stop(context, img, stop_method, stop_template, stop_ocr_text, stop_roi):
                logger.info("[TraverseAndClick] 终止条件触发，退出循环")
                break

            # 5. 不满足终止条件，执行 task_after_round，然后继续下一轮
            if task_after_round:
                logger.info(f"[TraverseAndClick] 本轮结束，执行 {task_after_round}")
                context.run_task(task_after_round)

            # 6. 等待后进入下一轮
            if round_delay > 0:
                time.sleep(round_delay)

        logger.info(f"[TraverseAndClick] 共执行 {round_count} 轮，结束")
        return CustomAction.RunResult(success=True)

    # ────────────────────────────────────────────────────────────
    # 内部方法
    # ────────────────────────────────────────────────────────────

    def _recognize_all(
        self,
        context: Context,
        img,
        method: str,
        template: str,
        ocr_text: list,
        threshold: float,
        roi: list | None = None,
    ) -> list[tuple[int, int]]:
        """
        返回所有命中的目标中心坐标列表 [(cx, cy), ...]，按 score 降序。
        roi 为 [x, y, w, h]，None 表示全屏。
        """
        centers = []

        if method == "template":
            centers = self._match_template_all(context, img, template, threshold, roi)
        elif method == "ocr":
            centers = self._match_ocr_all(context, img, ocr_text, threshold, roi)
        else:
            logger.warning(f"[TraverseAndClick] 未知识别方式: {method}")

        return centers

    def _match_template_all(
        self,
        context: Context,
        img,
        template: str,
        threshold: float,
        roi: list | None = None,
    ) -> list[tuple[int, int]]:
        """
        使用 MaaFramework 的 TemplateMatch 识别节点收集所有结果。
        通过临时注入一个 pipeline 节点来触发识别，读取 all_results。
        """
        tmp_node = "__TraverseAndClick_template_tmp__"

        node_cfg: dict = {
            "recognition": "TemplateMatch",
            "template": template,
            "threshold": threshold,
            "order_by": "Score",
            "action": "DoNothing",
        }
        if roi is not None:
            node_cfg["roi"] = roi

        context.override_pipeline({tmp_node: node_cfg})

        reco_detail = context.run_recognition(tmp_node, img)
        return self._extract_centers_from_detail(reco_detail, threshold, kind="template")

    def _match_ocr_all(
        self,
        context: Context,
        img,
        ocr_text: list,
        threshold: float,
        roi: list | None = None,
    ) -> list[tuple[int, int]]:
        """
        使用 OCR 识别并过滤包含目标文字的结果。
        """
        tmp_node = "__TraverseAndClick_ocr_tmp__"

        node_cfg: dict = {
            "recognition": "OCR",
            "expected": ocr_text,
            "threshold": threshold,
            "order_by": "Score",
            "action": "DoNothing",
        }
        if roi is not None:
            node_cfg["roi"] = roi

        context.override_pipeline({tmp_node: node_cfg})

        reco_detail = context.run_recognition(tmp_node, img)
        return self._extract_centers_from_detail(reco_detail, threshold, kind="ocr")

    def _extract_centers_from_detail(
        self,
        reco_detail,
        threshold: float,
        kind: str,
    ) -> list[tuple[int, int]]:
        """
        从 reco_detail.all_results 中提取 score >= threshold 的结果中心坐标。
        """
        if reco_detail is None:
            return []

        centers = []
        all_results = getattr(reco_detail, "all_results", [])

        for result in all_results:
            score = getattr(result, "score", 0.0)
            if score < threshold:
                continue

            box = getattr(result, "box", None)  # [x, y, w, h]
            if box is None or len(box) < 4:
                continue

            cx = box[0] + box[2] // 2
            cy = box[1] + box[3] // 2
            logger.debug(f"[TraverseAndClick] {kind} 命中: box={box}, score={score:.3f}, center=({cx},{cy})")
            centers.append((cx, cy))

        return centers

    def _check_stop(
        self,
        context: Context,
        img,
        stop_method: str,
        stop_template: str,
        stop_ocr_text: list,
        stop_roi: list | None = None,
    ) -> bool:
        """
        检查终止条件。
        - stop_method="template"：识别到 stop_template 图片则返回 True
        - stop_method="ocr"：OCR 识别到 stop_ocr_text 中任意字符串则返回 True
        stop_roi 为 [x, y, w, h]，None 表示全屏。
        返回 False 表示不满足终止条件，继续循环。
        """
        if stop_method == "template":
            if not stop_template:
                return False
            tmp_node = "__TraverseAndClick_stop_template_tmp__"
            node_cfg: dict = {
                "recognition": "TemplateMatch",
                "template": stop_template,
                "threshold": 0.8,
                "action": "DoNothing",
            }
            if stop_roi is not None:
                node_cfg["roi"] = stop_roi
            context.override_pipeline({tmp_node: node_cfg})
            detail = context.run_recognition(tmp_node, img)
            return detail is not None and getattr(detail, "hit", False)

        elif stop_method == "ocr":
            if not stop_ocr_text:
                return False
            tmp_node = "__TraverseAndClick_stop_ocr_tmp__"
            node_cfg: dict = {
                "recognition": "OCR",
                "expected": stop_ocr_text,
                "action": "DoNothing",
            }
            if stop_roi is not None:
                node_cfg["roi"] = stop_roi
            context.override_pipeline({tmp_node: node_cfg})
            detail = context.run_recognition(tmp_node, img)
            return detail is not None and getattr(detail, "hit", False)

        return False