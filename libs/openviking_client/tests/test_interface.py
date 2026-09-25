from openviking_client import OpenVikingClient


class _MinimalClient(OpenVikingClient):
    async def get_relevant_knowledge(self, topic):
        return []

    async def write_knowledge(self, record):
        pass

    async def get_knowledge_by_id(self, knowledge_id):
        return None

    async def list_conflicts(self):
        return []

    async def list_by_type(self, knowledge_type):
        return []

    async def list_all(self):
        return []

    async def update_knowledge_status(self, knowledge_id, status):
        pass

    async def update_knowledge_fields(self, knowledge_id, updates, edited_by):
        pass


def test_subclass_implementing_all_methods_can_be_instantiated():
    instance = _MinimalClient()
    assert isinstance(instance, OpenVikingClient)
