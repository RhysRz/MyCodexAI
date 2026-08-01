import os
import time


class FileTracker:


    def get_file_info(self, filepath):

        return {
            "path": filepath,
            "modified": os.path.getmtime(filepath)
        }


    def has_changed(self, old_info, filepath):

        current_time = os.path.getmtime(filepath)

        return (
            old_info["modified"]
            != current_time
        )