class NotFoundError(Exception):
    def __init__(self, resource: str, resource_id: int | str):
        self.resource = resource
        self.resource_id = resource_id
        super().__init__(f"{resource} with id {resource_id} not found")
