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

from durable.lang import *
from durable.engine import *
from func_module.health_monitor.logger import logger


# 互斥校验: 同一个event触发的runnable, 其RteBswActivationOffset/RteActivationOffset 必须一致
class Rte013026Rule(BasicRule):
    ruleset_name = "RTE013026"

    def __init__(self, logs, validation_data: ValidationData, rte_common_data: RteCommonData) -> None:
        super().__init__()
        self.logs = logs
        self.validation_code = self.__class__.ruleset_name
        self.validation_summary = "The activation offset of runnable triggered by the same event should be same!"

        self.bsw_ecuc_cfg_class_dict = validation_data.bsw_ecuc_dict
        self.rte_common_data = rte_common_data

    def get_validation_info_dict(self):
        validation_info_dict = {}
        event_name = None
        activation_offset = None

        ecuc_rte_dict = self.bsw_ecuc_cfg_class_dict['Rte']['ArPackages']['ActiveEcuC']['Rte']
        for rte_key, rte_instance in ecuc_rte_dict.items():
            if not isinstance(rte_instance, dict):
                continue
            for instance_key, instance_item in rte_instance.items():
                if not isinstance(instance_item, dict):
                    continue

                if "RteBswEventToTaskMapping" in instance_item['DefinitionRef']:
                    event_name = instance_item['RteBswUsedOsEventRef']['ValueRef']
                    activation_offset = instance_item['RteBswActivationOffset']['Value']
                    param_path = instance_item['RteBswMappedToTaskRef']['reference_item_path']
                    find_pos = param_path.rfind("/")
                    param_path = param_path[0:find_pos] + '/RteBswActivationOffset'

                elif "RteEventToTaskMapping" in instance_item['DefinitionRef']:
                    event_name = instance_item['RteUsedOsEventRef']['ValueRef']
                    activation_offset = instance_item['RteActivationOffset']['Value']
                    param_path = instance_item['RteMappedToTaskRef']['reference_item_path']
                    find_pos = param_path.rfind("/")
                    param_path = param_path[0:find_pos] + '/RteActivationOffset'
                else:
                    continue

                # NOTE: 如果event_name为空，则直接忽略
                if event_name is None:
                    continue
                # NOTE: 如果activation_offset为空，则默认值为0
                if activation_offset in (None, 'empty', ""):
                    activation_offset = 0

                if event_name not in validation_info_dict:
                    validation_info_dict[event_name] = {"activation_offset_list": [], "param_path_list": []}

                validation_info_dict[event_name]["activation_offset_list"].append(activation_offset)
                validation_info_dict[event_name]["param_path_list"].append(param_path)

        return validation_info_dict

    def check_validation_run(self):
        if not RteUtils.task_mapping_instance_is_constructed(self.rte_common_data.task_mapping_instance):
            return False
        return True

    @timing_decorator
    def validation_run(self):
        validation_info_dict = self.get_validation_info_dict()

        for event_name, validation_info in validation_info_dict.items():
            activation_offset_list = validation_info['activation_offset_list']
            param_path_list = validation_info['param_path_list']

            offset_count = len(set(activation_offset_list))

            messages = f"event name: {event_name}, activation offset list: {activation_offset_list}"
            if offset_count <= 1:
                self.vlog(self.validation_code, self.validation_summary, messages, param_path_list, "pass")
            else:
                auto_solve_list = []
                offset_set = set(activation_offset_list)
                for offset in offset_set:
                    auto_solve_list.append({
                        "solve_info": f"Set the offset value of all parameters to {offset}.",
                        "solve_type": "SetValue",
                        "parameter": param_path_list,
                        "value": offset
                    })

                self.vlog(self.validation_code, self.validation_summary, messages, param_path_list, "fail",
                          auto_solve_list)
