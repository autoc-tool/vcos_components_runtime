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


# 重复校验: RteBswPositionInTask/RtePositionInTask
class Rte011001Rule(BasicRule):
    ruleset_name = "RTE011001"
    validation_result = False

    def __init__(self, logs, validation_data: ValidationData, rte_common_data: RteCommonData) -> None:
        super().__init__()
        self.logs = logs
        self.validation_code = self.__class__.ruleset_name
        self.validation_summary = "The mappd position of runnable to one task should not be same!"

        self.bsw_ecuc_cfg_class_dict = validation_data.bsw_ecuc_dict
        self.rte_common_data = rte_common_data
        self.item_map = rte_common_data.get_item_map()

        self.durable_init()

    def durable_init(self):
        # 注：固定名称的规则集只能初始化一次，否则会异常报错
        try:
            get_host().get_ruleset(self.__class__.ruleset_name)
        except Exception as e:
            # print('get_ruleset() exception message: {0}'.format(e.args))
            with ruleset(self.__class__.ruleset_name):

                @when_all(+m.status)
                def event(c):
                    pass

                @when_all((+m.task_name) & (+m.position_id))
                def fact(c):
                    self.__class__.validation_result = True

            pass

    def get_validation_info_by_event_ref(self, event_ref):
        task_name = None
        position_id = None
        param_path = None

        ecuc_rte_dict = self.bsw_ecuc_cfg_class_dict['Rte']['ArPackages']['ActiveEcuC']['Rte']
        for rte_key, rte_instance in ecuc_rte_dict.items():
            if not isinstance(rte_instance, dict):
                continue
            for instance_key, instance_item in rte_instance.items():
                if not isinstance(instance_item, dict):
                    continue

                if "RteBswEventToTaskMapping" in instance_item['DefinitionRef']:
                    rte_event_ref = instance_item['RteBswEventRef']['ValueRef']
                    if event_ref != rte_event_ref:
                        continue

                    task_name = instance_item['RteBswMappedToTaskRef']['ValueRef'].split("/")[-1]
                    position_id = instance_item['RteBswPositionInTask']['Value']
                    param_path = instance_item['RteBswMappedToTaskRef']['reference_item_path']
                    find_pos = param_path.rfind("/")
                    param_path = param_path[0:find_pos] + '/RteBswPositionInTask'

                elif "RteEventToTaskMapping" in instance_item['DefinitionRef']:
                    rte_event_ref = instance_item['RteEventRef']['ValueRef']
                    if event_ref != rte_event_ref:
                        continue

                    task_name = instance_item['RteMappedToTaskRef']['ValueRef'].split("/")[-1]
                    position_id = instance_item['RtePositionInTask']['Value']
                    param_path = instance_item['RteMappedToTaskRef']['reference_item_path']
                    find_pos = param_path.rfind("/")
                    param_path = param_path[0:find_pos] + '/RtePositionInTask'
                else:
                    continue

        return task_name, position_id, param_path

    def check_validation_run(self):
        if not RteUtils.task_mapping_instance_is_constructed(self.rte_common_data.task_mapping_instance):
            return False
        return True

    @timing_decorator
    def validation_run(self):
        validation_data_list = []
        # 现在的问题在于task mapping提供的数据是否充足？有EventRef就可以去查询了
        for id in self.item_map.keys():
            item_data = self.rte_common_data.get_item_data_by_id(id)
            event_ref = item_data['EventRef']
            task_name, position_id, param_path = self.get_validation_info_by_event_ref(event_ref)
            if task_name is None or position_id is None or param_path is None:
                logger.error(f"get validation info faild {task_name}, {position_id}, {param_path}")
                continue

            validation_data = {}
            validation_data['task_name'] = task_name
            validation_data['position_id'] = position_id
            validation_data_list.append(validation_data)

            try:
                self.__class__.validation_result = False
                assert_fact(self.__class__.ruleset_name, validation_data)
            except Exception as e:
                self.__class__.validation_result = False
                # print('assert_fact() exception message {0}'.format(e.args))
                pass

            if self.__class__.validation_result:
                self.vlog(self.validation_code, self.validation_summary,
                          f"task: {task_name}, position: {position_id}, task bind event: {event_ref}", param_path,
                          "pass")
            else:
                self.vlog(self.validation_code, self.validation_summary,
                          f"task: {task_name}, position: {position_id}, task bind event: {event_ref}", param_path,
                          "fail")

        # 2）清空ruleset中的所有fact，为下一次校验做准备
        if validation_data_list:
            retract_facts(self.__class__.ruleset_name, validation_data_list)
        pass
