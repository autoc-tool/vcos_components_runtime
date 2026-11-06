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
from func_module.health_monitor.logger import logger
from .Rte_common import RteCommonData
from func_module.validation.common.validation_def import ValidationData


# 互斥校验：Basic Task配置了Timing Event触发的Runnable后，不允许再配置其他类型的runnable
class Rte013004Rule(BasicRule):
    ruleset_name = "RTE013004"
    validation_result = False

    def __init__(self, logs, validation_data: ValidationData, rte_common_data: RteCommonData) -> None:
        super().__init__()
        self.logs = logs
        self.validation_code = self.__class__.ruleset_name
        self.validation_summary = "If the trigger event of a runnable mapped to a basic task is timing, other events are not allowed"
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
        task_dict = {}
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
                param_path = instance_item['RteMappedToTaskRef']['reference_item_path']

                task_type = ecuc_os_dict[task_name]['OsTaskType']['Value']
                if task_type != 'BASIC':
                    continue
                if task_name not in task_dict:
                    task_dict.update({task_name: {'event_list': [], 'param_path': param_path}})

                event_tag = self.get_event_tag_by_ref(event_ref)
                if event_tag not in task_dict[task_name]:
                    task_dict[task_name]["event_list"].append(event_tag)

        for task_name, instance in task_dict.items():
            if "TIMING-EVENT" not in instance["event_list"]:
                continue
            other_event_list = [i for i in instance["event_list"] if i != 'TIMING-EVENT']
            param_path = [instance["param_path"], f'/ActiveEcuC/Os/{task_name}']

            if len(other_event_list) > 0:
                self.vlog(self.validation_code, self.validation_summary, f"task_name: {task_name}", param_path, "fail")
            else:
                self.vlog(self.validation_code, self.validation_summary, f"task_name: {task_name}", param_path, "pass")
