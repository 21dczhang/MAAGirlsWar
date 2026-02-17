"""
该文件的作用为：
截取当前屏幕并保存为 PNG 文件，文件名包含截图类型和时间戳。截图文件保存在 "debug" 目录中，且会定期清理三天前的旧截图文件。
"""

import os
import json
from maa.context import Context
from maa.custom_action import CustomAction
from datetime import datetime
from PIL import Image
from utils import logger


class ScreenShot(CustomAction):
    """
    自定义截图动作，保存当前屏幕截图到指定目录。

    参数格式:
    {
        "save_dir": "保存截图的目录路径"
    }
    """

    def run(
        self,
        context: Context,
        argv: CustomAction.RunArg,
    ) -> CustomAction.RunResult:

        # image array(BGR)
        screen_array = context.tasker.controller.cached_image

        # Check resolution aspect ratio
        height, width = screen_array.shape[:2]
        aspect_ratio = width / height
        target_ratio = 16 / 9
        # Allow small deviation (within 1%)
        if abs(aspect_ratio - target_ratio) / target_ratio > 0.01:
            logger.error(f"当前模拟器分辨率不是16:9! 当前分辨率: {width}x{height}")

        # BGR2RGB
        if len(screen_array.shape) == 3 and screen_array.shape[2] == 3:
            rgb_array = screen_array[:, :, ::-1]
        else:
            rgb_array = screen_array
            logger.warning("当前截图并非三通道")

        img = Image.fromarray(rgb_array)

        save_dir = json.loads(argv.custom_action_param)["save_dir"]
        os.makedirs(save_dir, exist_ok=True)
        now = datetime.now()
        img.save(f"{save_dir}/{self._get_format_timestamp(now)}.png")
        logger.info(f"截图保存至 {save_dir}/{self._get_format_timestamp(now)}.png")

        task_detail = context.tasker.get_task_detail(argv.task_detail.task_id)
        logger.debug(
            f"task_id: {task_detail.task_id}, task_entry: {task_detail.entry}, status: {task_detail.status._status}"
        )

        return CustomAction.RunResult(success=True)

    def _get_format_timestamp(self, now):

        date = now.strftime("%Y.%m.%d")
        time = now.strftime("%H.%M.%S")
        milliseconds = f"{now.microsecond // 1000:03d}"

        return f"{date}-{time}.{milliseconds}"


class CheckResolution(CustomAction):
    """
    检查当前模拟器分辨率是否符合预期（16:9）。
    """

    def run(
        self,
        context: Context,
        argv: CustomAction.RunArg,
    ) -> CustomAction.RunResult:

        width, height = context.tasker.controller.resolution
        aspect_ratio = width / height
        target_ratio = 16 / 9

        # 允许 1% 的误差
        if abs(aspect_ratio - target_ratio) / target_ratio > 0.01:
            logger.error(f"当前模拟器/游戏分辨率不是16:9! 当前: {width}x{height}")
        elif height < 720:
            logger.warning(f"当前模拟器/游戏分辨率高度低于720! 当前: {width}x{height}")
        else:
            return CustomAction.RunResult(success=True)
        logger.info("建议调整至16:9（如1280x720）")
        return CustomAction.RunResult(success=True)