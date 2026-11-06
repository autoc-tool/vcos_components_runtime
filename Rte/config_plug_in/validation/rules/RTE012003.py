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


# 动态缺失校验：对于Schedule Entity范围内的main_function来说，要求必须mapped到一个Task
class Rte012003Rule(BasicRule):
    ruleset_name = "RTE012003"

    def __init__(self, logs, validation_data: ValidationData, rte_common_data: RteCommonData) -> None:
        super().__init__()
        self.logs = logs
        self.validation_code = self.__class__.ruleset_name
        self.validation_summary = ("RTE012003: BSW MainFunction (Schedulable Entities) must be mapped to an OsTask via RteEventToTaskMapping.")
        self.rte_common_data = rte_common_data

        self.bsw_ecuc_cfg_class_dict = validation_data.bsw_ecuc_dict

        self.root_item = rte_common_data.get_root_item()
        self.runnable_dict = RteUtils.get_runnable_dict(self.root_item)

    def check_validation_run(self):
        if not self.modules_are_exist(["EcuC", "Os"], self.bsw_ecuc_cfg_class_dict):
            return False

        return True

    @timing_decorator
    def validation_run(self):
        category_name_list = ["Schedulable Entities"]
        for category_name, category_instance in self.runnable_dict.items():
            if category_name not in category_name_list:
                continue
            for swc_name, swc_instance in category_instance.items():
                for runnable_name, runnable_instance in swc_instance.items():
                    mapped_status = runnable_instance['mapped_status']
                    param_path = runnable_instance['event_ref']
                    if not mapped_status:
                        rte_path = f"/ActiveEcuC/Rte/{swc_name}"
                        self.vlog(
                            self.validation_code, self.validation_summary,
                            (
                                f"BSW MainFunction '{runnable_name}' of module '{swc_name}' "
                                f"(Schedulable Entities) is not mapped to any OsTask. "
                                f"Create RteEventToTaskMapping under {rte_path}: set RteEventRef "
                                f"to the MainFunction trigger event ({param_path}) and "
                                f"RteMappedToTaskRef to a periodic OsTask "
                                f"(e.g. OsTask_Bsw_5ms / OsTask_Bsw_10ms)."
                            ),
                            param_path if param_path else rte_path,
                            "fail",
                            [],
                            [
                                f"Map {swc_name}/{runnable_name} to an OsTask via "
                                f"Rte/{swc_name}/RteEventToTaskMapping "
                                f"(RteEventRef + RteMappedToTaskRef)."
                            ],
                        )
                    else:
                        self.vlog(
                            self.validation_code, self.validation_summary,
                            f"swc={swc_name} runnable={runnable_name}: mapped.",
                            param_path, "pass")
