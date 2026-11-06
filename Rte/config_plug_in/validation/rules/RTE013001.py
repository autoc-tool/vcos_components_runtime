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
from .Rte_common import RteCommonData
from func_module.validation.common.validation_def import ValidationData


# 互斥校验：同一个SWC的Runnables只能部署到同一个OS Application的Task
class Rte013001Rule(BasicRule):
    ruleset_name = "RTE013001"
    validation_result = False

    def __init__(self, logs, validation_data: ValidationData, rte_common_data: RteCommonData) -> None:
        super().__init__()
        self.logs = logs
        self.bsw_ecuc_cfg_class_dict = validation_data.bsw_ecuc_dict
        self.validation_code = self.__class__.ruleset_name
        self.validation_summary = "The runnables in the same swc should be placed in the same os application"
        self.durable_init()

    def durable_init(self):
        # 注：固定名称的规则集只能初始化一次，否则会异常报错
        try:
            get_host().get_ruleset(self.__class__.ruleset_name)
        except Exception as e:
            # print('get_ruleset() exception message: {0}'.format(e.args))
            with ruleset(self.__class__.ruleset_name):

                @when_all(c.first << +m.swc_name, c.second << m.application_name != c.first.application_name)
                def action(c):
                    self.__class__.validation_result = False

            pass

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

        # 2）准备校验数据并校验
        ecuc_rte_dict = self.bsw_ecuc_cfg_class_dict['Rte']['ArPackages']['ActiveEcuC']['Rte']
        for rte_key, rte_instance in ecuc_rte_dict.items():
            if not isinstance(rte_instance, dict):
                continue
            swc_name = rte_key
            frist_validation_data = {}
            for instance_item in rte_instance.values():
                if not isinstance(instance_item, dict):
                    continue

                if "RteEventToTaskMapping" not in instance_item['DefinitionRef']:
                    continue

                task_name = instance_item['RteMappedToTaskRef']['ValueRef'].split("/")[-1]
                param_path = instance_item['RteMappedToTaskRef']['reference_item_path']
                if task_name not in task_info_dict.keys():
                    print('task: {0} not exsit'.format(task_name))
                    continue

                validation_data = {}
                application_name = task_info_dict[task_name]
                validation_data['swc_name'] = swc_name
                validation_data['application_name'] = task_info_dict[task_name]
                if not frist_validation_data:
                    frist_validation_data = validation_data
                    try:
                        assert_fact(self.__class__.ruleset_name, frist_validation_data)
                    except Exception as e:
                        # print('assert_fact() exception message {0}'.format(e.args))
                        pass
                    continue

                # 只有一个frist_validation_data的话，没有校验的必要性，必然pass
                try:
                    self.__class__.validation_result = True
                    post(self.__class__.ruleset_name, validation_data)
                except Exception as e:
                    self.__class__.validation_result = True
                    # print('post() exception message {0}'.format(e.args))
                    pass
                if self.__class__.validation_result:
                    self.vlog(self.validation_code, self.validation_summary,
                              f"swc: {swc_name}, application: {application_name}", param_path, "pass")
                else:
                    self.vlog(self.validation_code, self.validation_summary,
                              f"swc: {swc_name}, application: {application_name}", param_path, "fail")
                pass
            if frist_validation_data:
                retract_fact(self.__class__.ruleset_name, frist_validation_data)
