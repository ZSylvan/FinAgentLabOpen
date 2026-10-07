import base64
import mimetypes
import os
from pathlib import Path

from openai import OpenAI


# Windows 路径前加 r，避免 \t、\n 等被识别为转义字符
IMAGE_PATH = Path(
    r"D:\Agent\agent_project\FinAgentLab-main"
    r"\FinAgentLab-main\docs\code_Explain\test\test.png"
)

MODEL_NAME = "gpt-5.6-terra"

QUESTION = """
请详细分析这张图片的内容，并回答：

1. 图片整体展示了什么？
2. 图片中有哪些文字、代码、图表或界面元素？
3. 如果图片包含代码，请解释代码的作用。
4. 如果图片包含错误信息，请分析可能的原因和解决方案。
5. 请使用中文回答。
""".strip()


def image_to_data_url(image_path: Path) -> str:
    """将本地图片转换为可发送给 API 的 Base64 Data URL。"""

    if not image_path.exists():
        raise FileNotFoundError(f"找不到图片文件：{image_path}")

    if not image_path.is_file():
        raise ValueError(f"该路径不是文件：{image_path}")

    mime_type, _ = mimetypes.guess_type(image_path.name)

    supported_types = {
        "image/png",
        "image/jpeg",
        "image/webp",
        "image/gif",
    }

    if mime_type not in supported_types:
        raise ValueError(
            f"不支持的图片格式：{mime_type}。"
            "请使用 PNG、JPEG、WEBP 或非动态 GIF。"
        )

    image_bytes = image_path.read_bytes()
    encoded_image = base64.b64encode(image_bytes).decode("utf-8")

    return f"data:{mime_type};base64,{encoded_image}"


def main() -> None:
    api_key = os.getenv("OPENAI_API_KEY")

    if not api_key:
        raise RuntimeError("请设置 OPENAI_API_KEY 环境变量")

    image_data_url = image_to_data_url(IMAGE_PATH)

    client = OpenAI(api_key=api_key,
                    base_url="https://www.zeoapi.com/v1"
                    )

    try:
        response = client.responses.create(
            model=MODEL_NAME,
            input=[
                {
                    "role": "user",
                    "content": [
                        {
                            "type": "input_text",
                            "text": QUESTION,
                        },
                        {
                            "type": "input_image",
                            "image_url": image_data_url,
                            # high 适合截图、代码和文字识别
                            "detail": "high",
                        },
                    ],
                }
            ],
        )

        print("\n========== 图片分析结果 ==========\n")
        print(response.output_text)

    except Exception as exc:
        print("\n调用 OpenAI API 失败：")
        print(f"{type(exc).__name__}: {exc}")
        raise


if __name__ == "__main__":
    main()
