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


# 互斥校验：main_function映射task所在application，需要具有OsIsPrivileged属性
class Rte013005Rule(BasicRule):
    ruleset_name = "RTE013005"
    validation_result = False

    def __init__(self, logs, validation_data: ValidationData, rte_common_data: RteCommonData) -> None:
        super().__init__()
        self.logs = logs
        self.validation_code = self.__class__.ruleset_name
        self.validation_summary = "The application where the task mapped by main function runnable is located needs to enable OsIsPrivileged"
        self.bsw_ecuc_cfg_class_dict = validation_data.bsw_ecuc_dict
        self.rte_common_data = rte_common_data

    def check_validation_run(self):
        if not self.modules_are_exist(["Os"], self.bsw_ecuc_cfg_class_dict):
            return False
        if not RteUtils.task_mapping_instance_is_constructed(self.rte_common_data.task_mapping_instance):
            return False
        return True

    @timing_decorator
    def validation_run(self):
        ecuc_os_dict = self.bsw_ecuc_cfg_class_dict['Os']['ArPackages']['ActiveEcuC']['Os']
        task_mapping_instance = self.rte_common_data.get_task_mapping_instance()

        if not task_mapping_instance or not task_mapping_instance.item_list:
            return

        col_count = task_mapping_instance.get_col_count()
        table_size = len(task_mapping_instance.item_list)
        for i in range(table_size - 1, -1, -1):
            table_item = task_mapping_instance.get_item(i)
            if not table_item or not table_item.item_data:
                continue
            cur_col = i % col_count
            task_info = task_mapping_instance.get_task_info_by_col(cur_col)
            app_name = task_info['OsApplName']
            item_data = table_item.item_data
            bind_item_list = task_mapping_instance.get_bind_item_list(item_data)
            for j, bind_item in enumerate(bind_item_list):
                is_service_component = bind_item.data['IsServiceComponent']
                is_main_function = bind_item.data['IsMainFunction']
                component = bind_item.data['Component']
                runnable = bind_item.data['RunnableName']
                param_path = bind_item.data['EventRef']
                if not is_service_component and is_main_function:
                    if app_name not in ecuc_os_dict:
                        continue
                    privilieged_path = f"/ActiveEcuC/Os/{app_name}/OsIsPrivileged"
                    param_path_list = [param_path, privilieged_path]
                    is_privilieged = ecuc_os_dict[app_name]['OsIsPrivileged']['Value']

                    auto_solve_list = [{
                        "solve_info": f"Set the value true for {privilieged_path}.",
                        "solve_type": "SetValue",
                        "parameter": privilieged_path,
                        "value": True
                    }]

                    if not is_privilieged:
                        self.vlog(
                            self.validation_code, self.validation_summary,
                            f"swc: {component}, runnable name: {runnable}, application name: {app_name}, OsIsPrivileged: {is_privilieged}",
                            param_path_list, "fail", auto_solve_list)
                    else:
                        self.vlog(
                            self.validation_code, self.validation_summary,
                            f"swc: {component}, runnable name: {runnable}, application name: {app_name}, OsIsPrivileged: {is_privilieged}",
                            param_path_list, "pass")
