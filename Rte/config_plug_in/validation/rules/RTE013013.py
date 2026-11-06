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
from func_module.health_monitor.logger import logger
from .Rte_common import RteCommonData, RteUtils
from func_module.validation.common.validation_def import ValidationData


# 互斥校验：Basic Task只允许配置Init或Timing Event触发的Runnable
class Rte013013Rule(BasicRule):
    ruleset_name = "RTE013013"
    validation_result = False

    def __init__(self, logs, validation_data: ValidationData, rte_common_data: RteCommonData) -> None:
        super().__init__()
        self.logs = logs
        self.validation_code = self.__class__.ruleset_name
        self.validation_summary = "The trigger event of a runnable mapped to a basic task should be either init or timing event"
        self.asw_autosar_dict = validation_data.autosar_asw_class
        self.bsw_ecuc_cfg_class_dict = validation_data.bsw_ecuc_dict

    def get_event_tag_by_ref(self, event_ref):
        event_tag = None
        asw = self.asw_autosar_dict
        if asw is None:
            logger.warning("Please import ASW arxml.")
            return event_tag
        event = asw.find(event_ref)
        if not event:
            logger.error(f"Error EventRef: {event_ref}")
            return event_tag
        event_tag = event.get_tag()
        return event_tag

    def check_validation_run(self):
        if not self.modules_are_exist(["Os"], self.bsw_ecuc_cfg_class_dict):
            return False
        return True

    @timing_decorator
    def validation_run(self):
        # 1）准备校验数据
        ecuc_os_dict = self.bsw_ecuc_cfg_class_dict['Os']['ArPackages']['ActiveEcuC']['Os']
        ecuc_rte_dict = self.bsw_ecuc_cfg_class_dict['Rte']['ArPackages']['ActiveEcuC']['Rte']
        for rte_instance in ecuc_rte_dict.values():
            if not isinstance(rte_instance, dict):
                continue
            for instance_item in rte_instance.values():
                if not isinstance(instance_item, dict):
                    continue

                if "RteEventToTaskMapping" not in instance_item['DefinitionRef']:
                    continue

                task_name = instance_item['RteMappedToTaskRef']['ValueRef'].split("/")[-1]
                event_ref = instance_item['RteEventRef']['ValueRef']
                task_param_path = f'/ActiveEcuC/Os/{task_name}/OsTaskType'
                param_path = [instance_item['RteMappedToTaskRef']['reference_item_path'], task_param_path]

                task_type = ecuc_os_dict[task_name]['OsTaskType']['Value']
                if task_type != 'BASIC':
                    continue

                event_tag = self.get_event_tag_by_ref(event_ref)
                if event_tag not in ["INIT-EVENT", "TIMING-EVENT"]:
                    runnable_name = RteUtils.get_runnable_name_in_asw(event_ref, self.asw_autosar_dict)
                    auto_solve_list = []
                    if runnable_name:
                        auto_solve_list.append({
                            "solve_info": f"Unmap {runnable_name} for {task_name}.",
                            "solve_type": "UnmapRunnable",
                            "parameter": task_name,
                            "value": runnable_name
                        })
                    auto_solve_list.append({
                        "solve_info": f"Set the OsTaskType value of {task_name} to extended.",
                        "solve_type": "SetValue",
                        "parameter": task_param_path,
                        "value": 'EXTENDED'
                    })

                    self.vlog(self.validation_code, self.validation_summary,
                              f"task name: {task_name}, task type: {task_type}, event type: {event_tag}", param_path,
                              "fail", auto_solve_list)
                else:
                    self.vlog(self.validation_code, self.validation_summary,
                              f"task name: {task_name}, task type: {task_type}, event type: {event_tag}", param_path,
                              "pass")
