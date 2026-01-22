class CustomException(Exception):
    """自定义异常基类"""
    def __init__(self, msg: str, code: int = 500):
        self.msg = msg
        self.code = code
        super().__init__(self.msg)
