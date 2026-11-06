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
from .Rte_common import RteCommonData, RteUtils
from func_module.validation.common.validation_def import ValidationData


# 当前不支持 basic task 关联的 runnable 中对应的 C/S Port 带有 wait point event
class Rte013018Rule(BasicRule):
    ruleset_name = "RTE013018"

    def __init__(self, logs, validation_data: ValidationData, rte_common_data: RteCommonData) -> None:
        super().__init__()
        self.logs = logs
        self.validation_code = self.__class__.ruleset_name
        self.validation_summary = "The corresponding C/S Port in the runnable associated with the basic task is not supported with wait point event."
        self.asw_cfg = rte_common_data.get_asw_cfg()
        self.asw_autosar_dict = validation_data.autosar_asw_class
        self.bsw_ecuc_cfg_class_dict = validation_data.bsw_ecuc_dict
        self.task_mapping_instance = rte_common_data.get_task_mapping_instance()

    def check_validation_run(self):
        if not self.modules_are_exist(["Os"], self.bsw_ecuc_cfg_class_dict):
            return False
        return True

    def get_basic_task_mapping_info(self):
        ''' 获取所有 basic task 对应的 runnable 的 mapping 信息 '''
        all_mapping_info = {}
        ecuc_os_dict = self.bsw_ecuc_cfg_class_dict['Os']['ArPackages']['ActiveEcuC']['Os']
        ecuc_rte_dict = self.bsw_ecuc_cfg_class_dict['Rte']['ArPackages']['ActiveEcuC']['Rte']
        for rte_instance in ecuc_rte_dict.values():
            if not isinstance(rte_instance, dict):
                continue
            for instance_item in rte_instance.values():
                if not isinstance(instance_item, dict) or "RteEventToTaskMapping" not in instance_item['DefinitionRef']:
                    continue
                task_name = instance_item['RteMappedToTaskRef']['ValueRef'].split("/")[-1]
                if task_name in all_mapping_info:
                    continue
                if ecuc_os_dict[task_name]['OsTaskType']['Value'] != 'BASIC':
                    continue
                mapping_info = RteUtils.get_task_mapping_info_by_task_name(task_name, self.task_mapping_instance)
                all_mapping_info[task_name] = mapping_info

        return all_mapping_info

    @timing_decorator
    def validation_run(self):
        mapping_info_list = self.get_basic_task_mapping_info()
        for task_name, mapping_info in mapping_info_list.items():
            runnable_list = [taks_mapping["RunnableName"] for taks_mapping in mapping_info]
            for runnable in runnable_list:
                for swc_cfg in self.asw_cfg.values():
                    for port_name, port_cfg in swc_cfg.get("rports", {}).items():
                        if "sync client" != port_cfg.get("type", "").lower() or not port_cfg.get("ioc", False):
                            continue

                        if not runnable in port_cfg.get("runnable", []):
                            continue
                        if not port_cfg['connected_ports'].get('ports', []):
                            continue
                        if not port_cfg['connected_ports']['ports'][0]['task']:
                            continue
                        # 如果只有一个 task，则会生成与该 task 相关的 wait point event
                        if len(set(port_cfg.get("task", []))) == 1:
                            param_path_list = [f"/ActiveEcuC/Os/{task_name}"]
                            message = f"{task_name} is a basic task, a wait point event will be generated in the code, and an error will be reported when the code is compiled later, port name: {port_name}, Please remap the runnable(runnable name: {runnable})."
                            self.vlog(self.validation_code, self.validation_summary, message, param_path_list, "fail")
                            break
