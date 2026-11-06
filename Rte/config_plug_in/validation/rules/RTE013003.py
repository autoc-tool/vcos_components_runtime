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
from .Rte_common import RteCommonData
from func_module.validation.common.validation_def import ValidationData


# 互斥校验：Background事件触发的Runnable必须映射到该核心的最低优先级的Task
class Rte013003Rule(BasicRule):
    ruleset_name = "RTE013003"
    validation_result = False

    def __init__(self, logs, validation_data: ValidationData, rte_common_data: RteCommonData) -> None:
        super().__init__()
        self.logs = logs
        self.validation_code = self.__class__.ruleset_name
        self.validation_summary = "The runnable triggered by background event should be mapped to the task with the lowest priority task of that core"
        self.bsw_ecuc_cfg_class_dict = validation_data.bsw_ecuc_dict
        self.asw_autosar_dict = validation_data.autosar_asw_class
        self.autosar_bsw_class = validation_data.autosar_bsw_class

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

    def get_low_priority_task(self, target_task_name, os_tasks):
        target_core_id = None
        target_priority = None
        task_dict = {}
        for task_info in os_tasks:
            core_id = task_info.get('CoreId', None)
            if core_id is None:
                continue
            task_name = task_info['OsTaskName']
            priority = int(task_info['OsTaskPriority'])

            if task_name == target_task_name:
                target_core_id = core_id
                target_priority = priority
            if core_id not in task_dict:
                task_dict.update({core_id: {'lowest_priority': 255, "task_list": []}})

            if priority < task_dict[core_id]['lowest_priority']:
                task_dict[core_id]['lowest_priority'] = priority
                task_dict[core_id]['task_list'] = []
                task_dict[core_id]['task_list'].append(task_name)
            elif priority == task_dict[core_id]['lowest_priority']:
                task_dict[core_id]['task_list'].append(task_name)
        if not target_core_id or not target_priority:
            return None, None
        return target_priority, task_dict[target_core_id]['lowest_priority']

    @timing_decorator
    def validation_run(self):
        # 1）准备校验数据并依次校验
        ecuc_rte_dict = self.bsw_ecuc_cfg_class_dict['Rte']['ArPackages']['ActiveEcuC']['Rte']
        os_autosar = self.autosar_bsw_class['Os']
        ecuc_autosar = self.autosar_bsw_class['EcuC']
        from components.runtime.Rte.config_plug_in.bsw_process.os_process import OsManager
        os_tasks = OsManager.get_sorted_tasks(os_autosar, ecuc_autosar)

        for rte_key, rte_instance in ecuc_rte_dict.items():
            if not isinstance(rte_instance, dict):
                continue
            for instance_key, instance_item in rte_instance.items():
                if not isinstance(instance_item, dict):
                    continue

                if "RteEventToTaskMapping" not in instance_item['DefinitionRef']:
                    continue

                task_name = instance_item['RteMappedToTaskRef']['ValueRef'].split("/")[-1]
                event_ref = instance_item['RteEventRef']['ValueRef']
                param_path = [instance_item['RteMappedToTaskRef']['reference_item_path'], f'/ActiveEcuC/Os/{task_name}']

                event_tag = self.get_event_tag_by_ref(event_ref)
                if event_tag != "BACKGROUND-EVENT":
                    continue

                target_priority, lowest_priority = self.get_low_priority_task(task_name, os_tasks)
                # 格式："错误码", "摘要", "错误信息", "错误索引路径" "结果"
                if target_priority > lowest_priority:
                    self.vlog(
                        self.validation_code, self.validation_summary,
                        f"task name: {task_name}, task priority: {target_priority}, lowest task priority: {lowest_priority}",
                        param_path, "fail")
                else:
                    self.vlog(
                        self.validation_code, self.validation_summary,
                        f"task name: {task_name}, task priority: {target_priority}, lowest task priority: {lowest_priority}",
                        param_path, "pass")
