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
from func_module.validation.common.basic_rule import BasicRule, timing_decorator
from .Rte_common import RteCommonData, RteUtils
from func_module.validation.common.validation_def import ValidationData


# 对于Schedule Entity中以太相关模块的mainfunction来说，要求必须mapped到一个同一个核
class Rte016001Rule(BasicRule):
    ruleset_name = "RTE016001"

    def __init__(self, logs, validation_data: ValidationData, rte_common_data: RteCommonData) -> None:
        super().__init__()
        self.logs = logs
        self.validation_code = self.__class__.ruleset_name
        self.validation_summary = "The mainfunction runnable related to eth in schedulable entities should be mapped to the same core"
        self.rte_common_data = rte_common_data
        self.bsw_ecuc_cfg_class_dict = validation_data.bsw_ecuc_dict

        task_mapping_instance = self.rte_common_data.get_task_mapping_instance()
        self.swc_core_dict = RteUtils.get_swc_runnable_core_dict(task_mapping_instance)

    def check_validation_run(self):
        if not self.modules_are_exist(["EcuC", "Os", "Eth"], self.bsw_ecuc_cfg_class_dict):
            return False

        return True

    def get_dict_by_definition_ref(self, input_dict: dict, definition_ref: str) -> dict:
        for key, value in input_dict.items():
            if isinstance(value, dict):
                if "DefinitionRef" in value.keys():
                    if value["DefinitionRef"].split("/")[-1] == definition_ref:
                        return key, value
        return "", {}

    @timing_decorator
    def validation_run(self):
        category_name_list = ["Schedulable Entities"]
        eth_swcname_list = ["EthIf", "EthSM", "EthTSyn", "SoAd", "DoIP", "TcpIp", "Xcp", "StbM"]
        eth_ecuc_dict = self.bsw_ecuc_cfg_class_dict['Eth']['ArPackages']['ActiveEcuC']['Eth']
        ethcfg_name, ethcfg_dict = self.get_dict_by_definition_ref(eth_ecuc_dict, "EthConfigSet")
        ethcore = None
        ethcore = None
        for k, v in ethcfg_dict.items():
            if not isinstance(v, dict):
                continue
            if "EthCtrlConfig" == v["DefinitionRef"].split("/")[-1]:
                for k1, v1 in v.items():
                    if not isinstance(v1, dict):
                        continue
                    if "EthCoreRef" == v1["DefinitionRef"].split("/")[-1]:
                        if v1["ValueRef"]:
                            ethcore = v1["ValueRef"][-1]
                            break

        for category_name, category_instance in self.swc_core_dict.items():
            if category_name not in category_name_list:
                continue
            for swc_name, swc_instance in category_instance.items():
                if swc_name in eth_swcname_list:
                    for ele in swc_instance:
                        result = True
                        if ele["CoreId"] != ethcore:
                            result = False
                            if swc_name == "Xcp" and 'eth' not in ele["RunnableName"].lower():
                                result = True

                        if not result:
                            self.vlog(self.validation_code, self.validation_summary,
                                      f"Core of runnable {ele['RunnableName']} is not consistent with Eth.",
                                      ele["EventRef"], "fail")
                        else:
                            self.vlog(self.validation_code, self.validation_summary,
                                      f"Core of runnable {ele['RunnableName']} is consistent with Eth.",
                                      ele["EventRef"], "pass")
                        pass
        pass
