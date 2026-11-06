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
from basic_func_module.autosar_utils.utils import get_short_name
from .Rte_common import RteCommonData
from func_module.validation.common.validation_def import ValidationData


# 重复校验：不同SWC下的同名Runnables不能部署同一个OS Application的Task
class Rte011002Rule(BasicRule):
    ruleset_name = "RTE011002"
    validation_result = False

    def __init__(self, logs, validation_data: ValidationData, rte_common_data: RteCommonData) -> None:
        super().__init__()
        self.logs = logs
        self.asw_autosar_dict = validation_data.autosar_asw_class
        self.bsw_ecuc_cfg_class_dict = validation_data.bsw_ecuc_dict
        self.validation_code = self.__class__.ruleset_name
        self.validation_summary = "The runnables with same name but in different swc should not exist in one application"
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

                @when_all((+m.runnable_name) & (+m.application_name))
                def fact(c):
                    self.__class__.validation_result = True

            pass

    def get_event_info_by_ref(self, event_ref):
        runnable_name = ""
        asw = self.asw_autosar_dict
        if asw is None:
            # logger.warning("Please import ASW arxml.")
            return runnable_name
        event = asw.find(event_ref)
        if not event:
            # logger.error(f"Error EventRef: {event_ref}")
            return runnable_name

        start_on_event_ref = event.START_ON_EVENT_REF.valueOf_
        runnable = event.find(start_on_event_ref)
        runnable_name = runnable.SYMBOL.valueOf_ if runnable.SYMBOL else get_short_name(runnable)

        return runnable_name

    def check_validation_run(self):
        if not self.modules_are_exist(["Os"], self.bsw_ecuc_cfg_class_dict):
            return False
        return True

    @timing_decorator
    def validation_run(self):
        # 1）准备Os相关dict
        ecuc_os_dict = self.bsw_ecuc_cfg_class_dict['Os']['ArPackages']['ActiveEcuC']['Os']
        task_info_dict = {}
        for os_key, os_instance in ecuc_os_dict.items():
            if not isinstance(os_instance, dict):
                continue
            if "OsApplication" not in os_instance['DefinitionRef']:
                continue

            if 'OsAppTaskRef' not in os_instance.keys():
                continue

            # os_key=application_name
            if isinstance(os_instance['OsAppTaskRef']['ValueRef'], list):
                for task_name in os_instance['OsAppTaskRef']['ValueRef']:
                    task_name = task_name.split("/")[-1]
                    task_info_dict[task_name] = os_key
            elif isinstance(os_instance['OsAppTaskRef']['ValueRef'], str):
                task_name = os_instance['OsAppTaskRef']['ValueRef'].split("/")[-1]
                task_info_dict[task_name] = os_key

        # 2）准备校验数据
        validation_data_list = []
        param_list = []
        ecuc_rte_dict = self.bsw_ecuc_cfg_class_dict['Rte']['ArPackages']['ActiveEcuC']['Rte']
        for rte_key, rte_instance in ecuc_rte_dict.items():
            if not isinstance(rte_instance, dict):
                continue
            swc_name = rte_key
            runnable_set = set()
            for instance_key, instance_item in rte_instance.items():
                if not isinstance(instance_item, dict):
                    continue
                if "RteEventToTaskMapping" not in instance_item['DefinitionRef']:
                    continue

                task_name = instance_item['RteMappedToTaskRef']['ValueRef'].split("/")[-1]
                if task_name not in task_info_dict.keys():
                    continue
                application_name = task_info_dict[task_name]
                event_ref = instance_item['RteEventRef']['ValueRef']
                runnable_name = self.get_event_info_by_ref(event_ref)
                param_path = instance_item['RteMappedToTaskRef']['reference_item_path']
                if runnable_name not in runnable_set:
                    runnable_set.add(runnable_name)
                    validation_data_list.append({"runnable_name": runnable_name, "application_name": application_name})
                    param_list.append({"swc_name": swc_name, "param_path": param_path})

        # 3）依次校验
        for index, validation_data in enumerate(validation_data_list):
            try:
                self.__class__.validation_result = False
                assert_fact(self.__class__.ruleset_name, validation_data)
            except Exception as e:
                self.__class__.validation_result = False
                # print('assert_fact() exception message {0}'.format(e.args))
                pass

            if self.__class__.validation_result:
                self.vlog(
                    self.validation_code, self.validation_summary,
                    f"runnable: {validation_data['runnable_name']}, swc: {param_list[index]['swc_name']}, application: {validation_data['application_name']}",
                    param_list[index]['param_path'], "pass")
            else:
                self.vlog(
                    self.validation_code, self.validation_summary,
                    f"runnable: {validation_data['runnable_name']}, swc: {param_list[index]['swc_name']}, application: {validation_data['application_name']}",
                    param_list[index]['param_path'], "fail")

        # 4）清空ruleset中的所有fact，为下一次校验做准备
        if validation_data_list:
            retract_facts(self.__class__.ruleset_name, validation_data_list)
        pass
