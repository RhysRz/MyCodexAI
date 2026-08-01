class CodeReader:


    def read_lines(
        self,
        filepath,
        start,
        end
    ):

        with open(
            filepath,
            "r",
            encoding="utf-8"
        ) as f:

            lines = f.readlines()


        result = []


        # เพิ่ม import ด้านบนไฟล์

        for line in lines[:start]:

            if (
                line.startswith("import ")
                or line.startswith("from ")
            ):

                result.append(line)



        # เพิ่ม code ของ symbol

        result.extend(
            lines[start-1:end]
        )


        return "".join(result)