from app.workspace.file_manager import FileManager


class IntentRouter:
    LIST_KEYWORDS = (
        "list files",
        "show files",
        "แสดงไฟล์",
        "ดูไฟล์",
        "รายการไฟล์",
    )

    READ_KEYWORDS = (
        "read file",
        "open file",
        "อ่านไฟล์",
        "เปิดไฟล์",
    )

    @staticmethod
    def _filename_from_message(message: str):
        for word in reversed(message.split()):
            candidate = word.strip(" '`\"“”")
            if "." in candidate and not candidate.startswith("."):
                return candidate

        return None

    @staticmethod
    def handle(message: str):
        text = message.lower().strip()

        if any(keyword in text for keyword in IntentRouter.LIST_KEYWORDS):
            files = FileManager.list_files()

            if not files:
                return True, "ไม่พบไฟล์ใน workspace"

            return True, "\n".join(files)

        if any(keyword in text for keyword in IntentRouter.READ_KEYWORDS):
            filename = IntentRouter._filename_from_message(message)

            if filename:
                content = FileManager.read_file(filename)

                if content is None:
                    return True, "ไม่พบไฟล์หรือไม่อนุญาตให้เข้าถึงไฟล์นี้"

                return True, content

        if text.startswith("write "):
            return True, "การเขียนไฟล์ต้องใช้ /api/agent/runs เพื่อแสดง diff และรอการอนุมัติก่อน"

        return False, None
