"""用户交互工具模块"""

from logging import PlaceHolder
from typing import Any, TypedDict

from langchain.tools import tool
from langgraph.types import interrupt
from pydantic import BaseModel, Field

class UserInputField(BaseModel):
    """向用户收集的一条字段定义。"""
    question: str = Field(description="问题描述，用于展示给用户")
    field_key: str = Field(description="字段名称（表单 key / 展示标签）")
    field_label: str = Field(description="字段标签，用于展示给用户")
    field_type: str = Field(description="字段类型，如 input,radio,checkbox 等")
    placeholder: str = Field(description="字段占位符，用于指导用户如何填写或选择,当type为input时必填",default=None)
    choices: list[str] = Field(description="字段选项，用于选择类型时展示给用户",default=None)
    


class AskUserQuestion(BaseModel):
    """ask_user_question 工具的入参：模型应一次传齐 reason 与 questions。"""

    reason: str = Field(description="为什么要向用户问这些问题（简短说明）")
    questions: list[UserInputField] = Field(
        min_length=1,
        description="需要用户填写或确认的字段列表，至少一项",
    )
    


@tool("ask_user_question", args_schema=AskUserQuestion,description="向用户询问开放式问题，获取用户提供的自由文本/数字/路径等。当你需要用户给出具体值或原始材料（如：项目名、文件路径、命令输出、错误栈、需求描述、配置内容、账号/邮箱、时间范围等），且无法提前列出合理选项。")
def ask_user_question(
    reason: str,
    questions: list[UserInputField],
) -> str:
    """当上下文不足或需用户确认时，先 interrupt 展示表单定义，再用 resume 带回用户填写结果。

    前端恢复示例：Command(resume={"data": {"字段名": "用户输入", ...}})
    或 Command(resume={"cancel": true}) 表示用户放弃。
    """
    payload = {
        "type": "ask_user_question",
        "reason": reason,
        "questions": [q.model_dump() for q in questions],
    }
    result = "用户放弃,停止任务"
    while True:
        user_input = interrupt(payload)
        print("======ask_user_question==============")
        print(user_input)
        print("======ask_user_question==============")
        if user_input.get("cancel"):
            break
        else:
            input_data = user_input.get("data")
            if input_data:
                # 检查用户输入是否齐全
                is_all_input = True
                for field in questions:
                    if not input_data.get(field.field_key):
                        is_all_input = False
                if is_all_input:
                    field_lable_map = {field.field_key: field.field_label for field in questions}
                    result = "".join([f"{field_lable_map.get(key)}: {value}" for key, value in input_data.items()])
                    break

    return result






    
