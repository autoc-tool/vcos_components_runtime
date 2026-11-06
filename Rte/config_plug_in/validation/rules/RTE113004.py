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
from .Rte_common import RteCommonData, RteUtils
from func_module.validation.common.validation_def import ValidationData


# 互斥校验：被init event触发的runnable需要map到task的相对最前面
class Rte113004Rule(BasicRule):
    ruleset_name = "RTE113004"
    validation_result = False

    def __init__(self, logs, validation_data: ValidationData, rte_common_data: RteCommonData) -> None:
        super().__init__()
        self.logs = logs
        self.asw_autosar_dict = validation_data.autosar_asw_class
        self.bsw_ecuc_cfg_class_dict = validation_data.bsw_ecuc_dict
        self.validation_code = self.__class__.ruleset_name
        self.validation_summary = "This runnable triggered by init event should be mapped before other event in one task"

    def get_event_info_by_ref(self, event_ref):
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

    @timing_decorator
    def validation_run(self):
        task_event_dict = {}
        # 1）准备校验数据
        ecuc_rte_dict = self.bsw_ecuc_cfg_class_dict['Rte']['ArPackages']['ActiveEcuC']['Rte']
        for rte_key, rte_instance in ecuc_rte_dict.items():
            if not isinstance(rte_instance, dict):
                continue

            for instance_item in rte_instance.values():
                if not isinstance(instance_item, dict):
                    continue

                if "RteEventToTaskMapping" not in instance_item['DefinitionRef']:
                    continue

                task_name = instance_item['RteMappedToTaskRef']['ValueRef'].split("/")[-1]
                position_id = instance_item['RtePositionInTask']['Value']
                event_ref = instance_item['RteEventRef']['ValueRef']
                event_type = self.get_event_info_by_ref(event_ref)
                if task_name not in task_event_dict:
                    task_event_dict.update({task_name: list()})
                task_event_dict[task_name].append({
                    "event_type": event_type,
                    "position_id": position_id,
                    'event_ref': event_ref
                })

        # 2) 开始校验
        for task_name, event_list in task_event_dict.items():
            max_init_event_position = None
            min_other_event_position = None
            max_pos_event_ref = ''
            for event_item in event_list:
                if event_item["event_type"] == "INIT-EVENT":
                    if not max_init_event_position or max_init_event_position < event_item["position_id"]:
                        max_init_event_position = event_item["position_id"]
                        max_pos_event_ref = event_item["event_ref"]
                else:
                    min_other_event_position = min(
                        min_other_event_position, event_item["position_id"]
                    ) if min_other_event_position is not None else event_item["position_id"]

            # 如果一方不存在，则默认为true
            self.__class__.validation_result = True
            if max_init_event_position is not None and min_other_event_position is not None:
                if max_init_event_position >= min_other_event_position:
                    self.__class__.validation_result = False

            # 格式："错误码", "摘要", "错误信息", "错误索引路径" "结果"
            message = f"max init event position: {max_init_event_position}, min other event position: {min_other_event_position}"
            param_path = f'/ActiveEcuC/Os/{task_name}'
            if self.__class__.validation_result:
                self.vlog(self.validation_code, self.validation_summary, message, param_path, "pass")
            else:
                runnable_name = RteUtils.get_runnable_name_in_asw(max_pos_event_ref, self.asw_autosar_dict)
                auto_solve_list = []
                if runnable_name:
                    auto_solve_list = [{
                        "solve_info": f"Remap {runnable_name} to {task_name} at position {min_other_event_position}.",
                        "solve_type": "MapRunnable",
                        "parameter": {
                            'origin_task': task_name,
                            'dest_task': task_name,
                            'runnable_name': runnable_name
                        },
                        "value": min_other_event_position
                    }]
                self.vlog(self.validation_code, self.validation_summary, message, param_path, "fail", auto_solve_list)
