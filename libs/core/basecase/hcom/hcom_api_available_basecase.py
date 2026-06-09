"""HCOMAPIAvailableBaseCase - Base class for HCOM API availability tests.

Migrated from: legency/testcase/ubscomm/hcom/lib/basecase/hcom/HCOMAPIAvailableBaseCase.py
"""

from concurrent.futures import ThreadPoolExecutor

from libs.core.basecase.hcom.hcom_basecase import HCOMBaseCase


class HCOMAPIAvailableBaseCase(HCOMBaseCase):
    """Base class for HCOM API availability test cases.
    
    Sets specific run_dir for API availability tests.
    """
    
    def __init__(self, nodes, resource, custom_params) -> None:
        super().__init__(nodes, resource, custom_params)
        self.executor = ThreadPoolExecutor(max_workers=4)
        self.run_dir = f"{self.base_dir}/hcom_api_availability"