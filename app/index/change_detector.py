class ChangeDetector:


    def is_changed(self, old_file, new_file):

        if old_file is None:
            return True


        return (
            old_file.get("modified")
            != new_file.get("modified")
        )
