from typing import List

from pydantic import BaseModel



class MemInfo(BaseModel):
    numa_id: int
    size: int
    is_local: bool


class GenerateXmlParams(BaseModel):
    vm_name: str
    vm_size: int
    numa_infos: List[MemInfo]
    image_full_path: str
