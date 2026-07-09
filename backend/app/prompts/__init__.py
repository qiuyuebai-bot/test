"""
Prompt 工程标准化模块（P3-4）

提供模板化的 prompt 加载、渲染与版本管理：
- 从 backend/app/prompts/templates/ 加载 .txt 模板文件
- 使用 str.format_map 安全渲染（缺失变量返回空字符串，不抛 KeyError）
- 通过 manifest.json 记录每个 prompt 的版本号与元信息
- LLMUtil.call_with_prompt_template() 调用入口

使用示例：
    from app.prompts import PromptManager

    rendered = PromptManager.render(
        "hallucination_check",
        reference_knowledge="...",
        content="...",
        suspicious_points="...",
    )
    response, usage = LLMUtil.sync_call(
        prompt=rendered.text,
        system_prompt=rendered.system_prompt,
        temperature=0.1,
    )
"""
from app.prompts.manager import PromptManager, RenderedPrompt

__all__ = ["PromptManager", "RenderedPrompt"]
