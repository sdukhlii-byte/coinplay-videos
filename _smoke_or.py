"""
_smoke_or.py — быстрый смоук OpenRouter (картинка + короткое видео).

Зачем: до полного прогона за пару центов убедиться, что OPENROUTER_API_KEY
рабочий, а слаги моделей (OR_IMAGE_MODEL / OR_VIDEO_MODEL_*) актуальны.

Запуск (на Railway shell или локально с заданными env):
    IMAGE_PROVIDER=openrouter VIDEO_PROVIDER=openrouter python _smoke_or.py
    # видео-этап можно пропустить (он дольше/дороже):
    SMOKE_SKIP_VIDEO=1 python _smoke_or.py
"""

import os
import logging
import tempfile

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s %(message)s")
log = logging.getLogger("smoke-or")

# Гарантируем, что config не потребует FAL_KEY на время смоука.
os.environ.setdefault("IMAGE_PROVIDER", "openrouter")
os.environ.setdefault("VIDEO_PROVIDER", "openrouter")

import config as C
from pipeline import orclient


def main() -> None:
    wd = tempfile.mkdtemp(prefix="smoke_or_")
    log.info("workdir=%s  image_model=%s", wd, C.OR_IMAGE_MODEL)

    # 1) Картинка
    img = orclient.generate_image_bytes(
        "A cheerful cartoon strawberry character, full body, clean studio background, "
        "vertical poster, bold colors",
        aspect_ratio="9:16", label="smoke")
    img_path = os.path.join(wd, "smoke.png")
    with open(img_path, "wb") as f:
        f.write(img)
    log.info("IMAGE OK → %s (%d bytes)", img_path, len(img))

    if os.environ.get("SMOKE_SKIP_VIDEO"):
        log.info("SMOKE_SKIP_VIDEO set — пропускаю видео. Готово.")
        return

    # 2) Видео из этого кадра (короткое)
    import base64
    import mimetypes
    mt = mimetypes.guess_type(img_path)[0] or "image/png"
    frame_url = f"data:{mt};base64,{base64.b64encode(img).decode()}"

    log.info("video_model=%s — сабмит i2v (это займёт ~минуту)...", C.OR_VIDEO_MODEL_VEO)
    vid = orclient.generate_video_bytes(
        model=C.OR_VIDEO_MODEL_VEO,
        prompt="The strawberry character waves and smiles, gentle camera push-in",
        frame_image_url=frame_url,
        duration_sec=C.VEO_DURATION, resolution=C.VEO_RESOLUTION,
        aspect_ratio=C.VEO_ASPECT, generate_audio=C.VEO_GENERATE_AUDIO,
        label="smoke")
    vid_path = os.path.join(wd, "smoke.mp4")
    with open(vid_path, "wb") as f:
        f.write(vid)
    log.info("VIDEO OK → %s (%d bytes). Всё работает.", vid_path, len(vid))


if __name__ == "__main__":
    main()
