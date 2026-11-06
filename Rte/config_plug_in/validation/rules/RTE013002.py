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
from durable.lang import *
from durable.engine import *
from func_module.validation.common.validation_def import ValidationData
from .Rte_common import RteCommonData, RteUtils


# 互斥校验：要求Application Components中的SWC中至少有一个runnable是mapped状态
# 如果swc中的任何runnable都没有mapped，但是swc在ecuc partition中有了ref也是可以的
# (PARAMETER-SW-COMPONENT-TYPE除外，这种类型的SWC没有internal behaviors，也就没有runnable)
class Rte013002Rule(BasicRule):
    ruleset_name = "RTE013002"
    validation_result = False

    def __init__(self, logs, validation_data: ValidationData, rte_common_data: RteCommonData) -> None:
        super().__init__()
        self.logs = logs
        self.validation_code = self.__class__.ruleset_name
        self.validation_summary = "The swc in Application Components should at least have one mapped runnable or reffered by one ecuc partition "

        self.bsw_ecuc_cfg_class_dict = validation_data.bsw_ecuc_dict
        self.rte_common_data = rte_common_data
        self.root_item = rte_common_data.get_root_item()
        _, self.swc_osa_from_ep, _, _ = rte_common_data.get_ecuc_partition_info()
        self.runnable_dict = RteUtils.get_runnable_dict(self.root_item)

    def check_validation_run(self):
        if not self.modules_are_exist(["EcuC", "Os"], self.bsw_ecuc_cfg_class_dict):
            return False
        if not RteUtils.task_mapping_instance_is_constructed(self.rte_common_data.task_mapping_instance):
            return False

        return True

    @timing_decorator
    def validation_run(self):
        category_name_list = ['Application Components']
        for category_name, category_instance in self.runnable_dict.items():
            if category_name not in category_name_list:
                continue
            for swc_name, swc_instance in category_instance.items():
                swc_mapped_status = False
                index = 0
                for runnable_name, runnable_instance in swc_instance.items():
                    mapped_status = runnable_instance['mapped_status']
                    swc_mapped_status = swc_mapped_status or mapped_status
                    index += 1

                message = f"swc category: {category_name}, swc name: {swc_name} runnable name: {runnable_name}"
                path = f"{category_name}_{swc_name}_{runnable_name}"

                if not swc_mapped_status and len(self.swc_osa_from_ep.get(swc_name, [])) == 0:
                    self.vlog(self.validation_code, self.validation_summary, message, path, "fail")
                else:
                    self.vlog(self.validation_code, self.validation_summary, message, path, "pass")
