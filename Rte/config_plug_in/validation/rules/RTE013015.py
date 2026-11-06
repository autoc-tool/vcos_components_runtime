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


# 互斥校验：Mode Switch Event 触发的Runnable TaskMapping时需要验证Mapping顺序
class Rte013015Rule(BasicRule):
    ruleset_name = "RTE013015"
    validation_result = False

    def __init__(self, logs, validation_data: ValidationData, rte_common_data: RteCommonData) -> None:
        super().__init__()
        self.logs = logs
        self.asw_autosar_dict = validation_data.autosar_asw_class
        self.bsw_ecuc_cfg_class_dict = validation_data.bsw_ecuc_dict
        self.validation_code = self.__class__.ruleset_name
        self.validation_summary = "The runnable triggered by mode switch event should be in special order"

    def get_event_info_by_ref(self, event_ref):
        trigger_port = ""
        trigger_category = ""

        asw = self.asw_autosar_dict
        if asw is None:
            logger.warning("Please import ASW arxml.")
            return trigger_port, trigger_category
        event = asw.find(event_ref)
        if not event:
            logger.error(f"Error EventRef: {event_ref}")
            return trigger_port, trigger_category

        event_tag = event.get_tag()
        if event_tag != "SWC-MODE-SWITCH-EVENT":
            return trigger_port, trigger_category

        trigger_category = event.ACTIVATION.valueOf_
        if trigger_category == "ON-ENTRY":
            entry_mode_iref = event.MODE_IREFS.MODE_IREF[0]
            trigger_port = entry_mode_iref.CONTEXT_PORT_REF.valueOf_.split("/").pop()
        elif trigger_category == "ON-TRANSITION":
            exit_mode_iref = event.MODE_IREFS.MODE_IREF[0]
            entry_mode_iref = event.MODE_IREFS.MODE_IREF[1]
            trigger_port = entry_mode_iref.CONTEXT_PORT_REF.valueOf_.split("/").pop()
        elif trigger_category == "ON-EXIT":
            exit_mode_iref = event.MODE_IREFS.MODE_IREF[0]
            trigger_port = exit_mode_iref.CONTEXT_PORT_REF.valueOf_.split("/").pop()
        return trigger_port, trigger_category

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
            validation_dict = {}
            for instance_item in rte_instance.values():
                if not isinstance(instance_item, dict):
                    continue

                if "RteEventToTaskMapping" not in instance_item['DefinitionRef']:
                    continue

                event_ref = instance_item['RteEventRef']['ValueRef']
                trigger_port, trigger_category = self.get_event_info_by_ref(event_ref)
                if not trigger_port or not trigger_category:
                    continue

                task_name = instance_item['RteMappedToTaskRef']['ValueRef'].split("/")[-1]
                position_id = instance_item['RtePositionInTask']['Value']

                param_path = instance_item['RteMappedToTaskRef']['reference_item_path']
                if trigger_port not in validation_dict.keys():
                    validation_dict.update(
                        {trigger_port: {
                            "mapped_task_set": set(),
                            "mapped_list": list(),
                            "param_path": param_path
                        }})
                validation_dict[trigger_port]["mapped_task_set"].add(task_name)
                validation_dict[trigger_port]["mapped_list"].append({
                    "trigger_category": trigger_category,
                    "position_id": position_id
                })

            if not validation_dict:
                continue

            for validation_value in validation_dict.values():
                on_entry_position = None
                on_trans_position = None
                on_exit_position = None

                for mapped_info in validation_value['mapped_list']:
                    if mapped_info['trigger_category'] == 'ON-ENTRY':
                        on_entry_position = mapped_info['position_id']
                    elif mapped_info['trigger_category'] == 'ON-TRANSITION':
                        on_trans_position = mapped_info['position_id']
                    elif mapped_info['trigger_category'] == 'ON-EXIT':
                        on_exit_position = mapped_info['position_id']

                self.__class__.validation_result = True
                task_set_len = len(validation_value['mapped_task_set'])
                if task_set_len != 1:
                    self.__class__.validation_result = False

                if on_exit_position and on_trans_position:
                    if on_exit_position >= on_trans_position:
                        self.__class__.validation_result = False

                if on_exit_position and on_entry_position:
                    if on_exit_position >= on_entry_position:
                        self.__class__.validation_result = False

                if on_trans_position and on_entry_position:
                    if on_trans_position >= on_entry_position:
                        self.__class__.validation_result = False

                # 格式："错误码", "摘要", "错误信息", "错误索引路径" "结果"
                message_head = f"all OnTransition triggered runnables need to be mapped after the OnExit and before the OnEntry triggered runnables of the same mode machine.\n"
                mesage_detail = f"mapped task count: {task_set_len}, OnExit position: {on_exit_position}, OnTransition position: {on_trans_position}, OnEntry position: {on_entry_position}"
                message = f"{message_head}{mesage_detail}"
                if self.__class__.validation_result:
                    self.vlog(self.validation_code, self.validation_summary, message, param_path, "pass")
                else:
                    self.vlog(self.validation_code, self.validation_summary, message, param_path, "fail")
