class SymbolResolver:


    def __init__(self):

        self.mapping = {}



    def add_symbol(
        self,
        filepath,
        symbols
    ):


        filename = filepath.replace(
            "\\",
            "/"
        )


        module = filename.split(
            "/"
        )[-1].replace(
            ".py",
            ""
        )


        for symbol in symbols:


            if symbol["type"] == "class":


                self.mapping[
                    module
                ] = symbol["name"]



    def resolve(
        self,
        name
    ):


        return self.mapping.get(
            name,
            name
        )



    def get_all(self):

        return self.mapping