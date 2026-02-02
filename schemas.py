from typing_extensions import TypedDict
from typing import Annotated, List


class ChatbotState(TypedDict):
    lastet_user_message: str
    message: Annotated[List[bytes], lambda x, y: x + y]
