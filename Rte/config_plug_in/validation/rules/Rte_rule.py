# This Python file uses the following encoding: utf-8
############################################################################
# Copyright (c) 2025 Li Auto Inc. and its affiliates
# Licensed under the Apache License, Version 2.0(the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
############################################################################
from func_module.validation.common.validation_def import ValidationData, ExceptionRuleLog
from .Rte_common import RteCommonData
from func_module.health_monitor.logger import logger
import importlib

VALIDATE_MARK_LIST = [
    "011001", "011002", "012002", "012003", "013001", "013002", "013003", "013004", "013005", "013013", "013014",
    "013015", "013018", "013019", "013022", "013026", "016001", "016002", "113004", "113006"
]


class RteRule:

    def __init__(self) -> None:
        self.logs = {}

    def check_config(self, validation_data: ValidationData):
        if not validation_data:
            logger.warning("validation data error!")
            return False

        if not validation_data.autosar_asw_class:
            logger.warning("validation autosar_asw_class data error!")
            return False

        if not validation_data.autosar_bsw_class:
            logger.warning("validation autosar_bsw_class data error!")
            return False

        if not validation_data.autosar_ib_class:
            logger.warning("validation autosar_ib_class data error!")
            return False

        if not validation_data.autosar_mod_class:
            logger.warning("validation autosar_mod_class data error!")
            return False

        if not validation_data.autosar_system_class:
            logger.warning("validation autosar_system_class data error!")
            return False

        return True

    def validate(self, validation_data: ValidationData):
        if not self.check_config(validation_data):
            return

        rte_common_data = RteCommonData(validation_data)

        for validate_code in VALIDATE_MARK_LIST:
            try:
                validate_rule_package = importlib.import_module(f'.RTE{validate_code}', __package__)
                validate_rule_class = getattr(validate_rule_package, f'Rte{validate_code}Rule')
                bsw_module_rule_obj = validate_rule_class(self.logs, validation_data, rte_common_data)
                # 校验当前校验规则的前置条件是否满足
                if bsw_module_rule_obj.check_validation_run():
                    bsw_module_rule_obj.validation_run()
            except Exception as e:
                ExceptionRuleLog.set_rule_exception_log(self.logs, "Rte", validate_code, f"{type(e)}: {str(e)}")

        return self.logs
