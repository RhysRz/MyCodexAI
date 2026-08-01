class ConversationMemory:

    def __init__(self):
        self.messages = []

    def add_user(self, message: str):
        self.messages.append(
            {
                "role": "user",
                "content": message
            }
        )

    def add_assistant(self, message: str):
        self.messages.append(
            {
                "role": "assistant",
                "content": message
            }
        )

    def get_messages(self):
        return self.messages

    def clear(self):
        self.messages = []


memory = ConversationMemory()